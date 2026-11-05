from __future__ import annotations

import json
import re

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from . import db
from .templating import templates

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+()\-\s]+$")
MAX_QTY = 99

SORT_OPTIONS = {
    "new": "p.created_at DESC, p.id DESC",
    "price_asc": "p.price ASC, p.id DESC",
    "price_desc": "p.price DESC, p.id DESC",
}


@router.get("/")
def index(request: Request):
    products = db.fetch_all(
        """
        SELECT p.*, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT 4
        """
    )
    return templates.TemplateResponse(
        request, "index.html", {"products": products, "page": "home"}
    )


@router.get("/catalog")
def catalog(request: Request, category: str | None = None, sort: str = "new"):
    if sort not in SORT_OPTIONS:
        sort = "new"

    categories = db.fetch_all("SELECT * FROM categories ORDER BY name")
    sql = """
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
    """
    params: list[object] = []
    if category:
        sql += " AND c.slug = ?"
        params.append(category)
    sql += f" ORDER BY {SORT_OPTIONS[sort]}"

    products = db.fetch_all(sql, tuple(params))
    current = next((c for c in categories if c["slug"] == category), None)

    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "products": products,
            "categories": categories,
            "current_category": current,
            "sort": sort,
            "page": "catalog",
        },
    )


@router.get("/product/{slug}")
def product(request: Request, slug: str):
    item = db.fetch_one(
        """
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.slug = ? AND p.is_active = 1
        """,
        (slug,),
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return templates.TemplateResponse(
        request, "product.html", {"product": item, "page": "product"}
    )


@router.get("/cart")
def cart(request: Request):
    return templates.TemplateResponse(request, "cart.html", {"page": "cart"})


@router.get("/checkout")
def checkout_form(request: Request):
    return templates.TemplateResponse(
        request,
        "checkout.html",
        {"errors": {}, "values": {}, "page": "checkout"},
    )


def _parse_items(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    merged: dict[int, int] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            product_id = int(entry.get("id"))
            qty = int(entry.get("qty", 1))
        except (TypeError, ValueError):
            continue
        if product_id <= 0 or qty <= 0:
            continue
        qty = min(qty, MAX_QTY)
        merged[product_id] = min(merged.get(product_id, 0) + qty, MAX_QTY)
    return [{"id": pid, "qty": qty} for pid, qty in merged.items()]


def _validate_customer(customer_name: str, phone: str, email: str, address: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    if len(customer_name.strip()) < 2:
        errors["customer_name"] = "Укажите имя (минимум 2 символа)."
    if not PHONE_RE.match(phone.strip()) or sum(ch.isdigit() for ch in phone) < 7:
        errors["phone"] = "Укажите корректный номер телефона."
    if not EMAIL_RE.match(email.strip()):
        errors["email"] = "Укажите корректный e-mail."
    if len(address.strip()) < 5:
        errors["address"] = "Укажите адрес доставки."
    return errors


@router.post("/checkout")
def checkout_submit(
    request: Request,
    customer_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    items: str = Form(""),
):
    values = {
        "customer_name": customer_name,
        "phone": phone,
        "email": email,
        "address": address,
    }
    errors = _validate_customer(customer_name, phone, email, address)

    cart_items: list[dict] = []
    for entry in _parse_items(items):
        row = db.fetch_one(
            "SELECT id, price FROM products WHERE id = ? AND is_active = 1",
            (entry["id"],),
        )
        if row is None:
            errors["cart"] = "Один из товаров больше недоступен. Обновите корзину."
            break
        cart_items.append(
            {"id": row["id"], "qty": entry["qty"], "price": row["price"]}
        )

    if not cart_items and "cart" not in errors:
        errors["cart"] = "Корзина пуста — добавьте товар перед оформлением."

    if errors:
        return templates.TemplateResponse(
            request,
            "checkout.html",
            {"errors": errors, "values": values, "page": "checkout"},
            status_code=400,
        )

    total = sum(item["price"] * item["qty"] for item in cart_items)
    order_id = db.create_order(
        {
            "customer_name": customer_name.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "address": address.strip(),
            "total": total,
        },
        cart_items,
    )
    return RedirectResponse(url=f"/order/{order_id}", status_code=303)


@router.get("/order/{order_id}")
def order_success(request: Request, order_id: int):
    order = db.fetch_one("SELECT * FROM orders WHERE id = ?", (order_id,))
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    items = db.fetch_all(
        """
        SELECT oi.qty, oi.price, p.name, p.slug, p.image_path
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = ?
        ORDER BY oi.rowid
        """,
        (order_id,),
    )
    return templates.TemplateResponse(
        request,
        "order_success.html",
        {"order": order, "items": items, "page": "order-success"},
    )
