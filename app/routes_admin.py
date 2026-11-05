from __future__ import annotations

import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from PIL import Image

from . import auth, db
from .templating import templates

router = APIRouter(prefix="/admin")
protected = APIRouter(dependencies=[Depends(auth.require_admin)])

MAX_IMAGE_BYTES = 3 * 1024 * 1024
ALLOWED_STATUSES = ("new", "in_progress", "done")


# ---------------------------------------------------------------- вход / выход

@router.get("")
@router.get("/")
def admin_root(request: Request):
    if auth.is_admin(request):
        return RedirectResponse("/admin/dashboard", status_code=303)
    return RedirectResponse("/admin/login", status_code=303)


@router.get("/login")
def login_form(request: Request):
    if auth.is_admin(request):
        return RedirectResponse("/admin/dashboard", status_code=303)
    return templates.TemplateResponse(
        request, "admin/login.html", {"error": None, "page": "admin-login"}
    )


@router.post("/login")
def login_submit(request: Request, password: str = Form("")):
    if auth.check_password(password):
        auth.login(request)
        return RedirectResponse("/admin/dashboard", status_code=303)
    return templates.TemplateResponse(
        request,
        "admin/login.html",
        {"error": "Неверный пароль. Попробуйте ещё раз.", "page": "admin-login"},
        status_code=400,
    )


@router.post("/logout")
def logout(request: Request):
    auth.logout(request)
    return RedirectResponse("/admin/login", status_code=303)


# ------------------------------------------------------------------- dashboard

@protected.get("/dashboard")
def dashboard(request: Request):
    products_count = db.fetch_one("SELECT COUNT(*) AS n FROM products")["n"]
    active_count = db.fetch_one(
        "SELECT COUNT(*) AS n FROM products WHERE is_active = 1"
    )["n"]
    new_orders = db.fetch_one(
        "SELECT COUNT(*) AS n FROM orders WHERE status = 'new'"
    )["n"]
    latest_orders = db.fetch_all(
        """
        SELECT o.*, (SELECT COALESCE(SUM(qty), 0) FROM order_items WHERE order_id = o.id) AS units
        FROM orders o
        ORDER BY o.created_at DESC, o.id DESC
        LIMIT 5
        """
    )
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "products_count": products_count,
            "active_count": active_count,
            "new_orders": new_orders,
            "latest_orders": latest_orders,
            "page": "admin",
            "active": "dashboard",
        },
    )


# --------------------------------------------------------------------- товары

@protected.get("/products")
def products_list(request: Request):
    products = db.fetch_all(
        """
        SELECT p.*, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        ORDER BY p.created_at DESC, p.id DESC
        """
    )
    return templates.TemplateResponse(
        request,
        "admin/products.html",
        {"products": products, "page": "admin", "active": "products"},
    )


def _render_product_form(
    request: Request,
    form: dict,
    errors: dict[str, str],
    product,
    status_code: int = 200,
):
    categories = db.fetch_all("SELECT * FROM categories ORDER BY name")
    return templates.TemplateResponse(
        request,
        "admin/product_form.html",
        {
            "form": form,
            "errors": errors,
            "product": product,
            "categories": categories,
            "page": "admin",
            "active": "products",
        },
        status_code=status_code,
    )


def _detect_image(data: bytes) -> tuple[str | None, str | None]:
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG", ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG", ".png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP", ".webp"
    return None, None


async def _save_upload(upload: UploadFile) -> tuple[str | None, str | None]:
    data = await upload.read()
    if not data:
        return None, "Файл пустой."
    if len(data) > MAX_IMAGE_BYTES:
        return None, "Файл больше 3 МБ."

    fmt, ext = _detect_image(data)
    if fmt is None:
        return None, "Допустимы только изображения JPG, PNG или WEBP."

    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != fmt:
                return None, "Формат файла не совпадает с содержимым."
            image.verify()
    except Exception:
        return None, "Не удалось прочитать изображение."

    filename = f"{uuid.uuid4().hex}{ext}"
    destination = db.UPLOADS_DIR / filename
    db.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return f"/static/uploads/{filename}", None


def _parse_price(raw: str) -> int | None:
    value = raw.strip().replace(" ", "").replace("\u00a0", "")
    if not value.isdigit():
        return None
    price = int(value)
    return price if price > 0 else None


def _form_from_request(name: str, category_id: str, price: str, description: str, is_active) -> dict:
    return {
        "name": name,
        "category_id": category_id,
        "price": price,
        "description": description,
        "is_active": is_active is not None,
    }


@protected.get("/products/new")
def product_new(request: Request):
    form = {
        "name": "",
        "category_id": "",
        "price": "",
        "description": "",
        "is_active": True,
    }
    return _render_product_form(request, form, {}, None)


@protected.post("/products/new")
async def product_create(
    request: Request,
    name: str = Form(""),
    category_id: str = Form(""),
    price: str = Form(""),
    description: str = Form(""),
    is_active: str | None = Form(None),
    image: UploadFile | None = File(None),
):
    form = _form_from_request(name, category_id, price, description, is_active)
    errors: dict[str, str] = {}

    name = name.strip()
    if len(name) < 2:
        errors["name"] = "Укажите название товара."

    category = None
    if category_id.isdigit():
        category = db.fetch_one("SELECT id FROM categories WHERE id = ?", (int(category_id),))
    if category is None:
        errors["category_id"] = "Выберите категорию."

    parsed_price = _parse_price(price)
    if parsed_price is None:
        errors["price"] = "Цена должна быть целым положительным числом."

    if image is None or not image.filename:
        errors["image"] = "Загрузите изображение товара."

    if errors:
        return _render_product_form(request, form, errors, None, status_code=400)

    image_path, image_error = await _save_upload(image)
    if image_error or image_path is None:
        errors["image"] = image_error or "Не удалось сохранить изображение."
        return _render_product_form(request, form, errors, None, status_code=400)

    slug = db.unique_slug("products", db.slugify(name))
    db.execute(
        """
        INSERT INTO products
            (category_id, name, slug, description, price, image_path, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            category["id"],
            name,
            slug,
            description.strip(),
            parsed_price,
            image_path,
            1 if form["is_active"] else 0,
        ),
    )
    return RedirectResponse("/admin/products", status_code=303)


@protected.get("/products/{product_id}/edit")
def product_edit(request: Request, product_id: int):
    product = db.fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    form = {
        "name": product["name"],
        "category_id": str(product["category_id"]),
        "price": str(product["price"]),
        "description": product["description"],
        "is_active": bool(product["is_active"]),
    }
    return _render_product_form(request, form, {}, product)


@protected.post("/products/{product_id}/edit")
async def product_update(
    request: Request,
    product_id: int,
    name: str = Form(""),
    category_id: str = Form(""),
    price: str = Form(""),
    description: str = Form(""),
    is_active: str | None = Form(None),
    image: UploadFile | None = File(None),
):
    product = db.fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    form = _form_from_request(name, category_id, price, description, is_active)
    errors: dict[str, str] = {}

    name = name.strip()
    if len(name) < 2:
        errors["name"] = "Укажите название товара."

    category = None
    if category_id.isdigit():
        category = db.fetch_one("SELECT id FROM categories WHERE id = ?", (int(category_id),))
    if category is None:
        errors["category_id"] = "Выберите категорию."

    parsed_price = _parse_price(price)
    if parsed_price is None:
        errors["price"] = "Цена должна быть целым положительным числом."

    if errors:
        return _render_product_form(request, form, errors, product, status_code=400)

    image_path = product["image_path"]
    if image is not None and image.filename:
        new_path, image_error = await _save_upload(image)
        if image_error or new_path is None:
            errors["image"] = image_error or "Не удалось сохранить изображение."
            return _render_product_form(request, form, errors, product, status_code=400)
        image_path = new_path

    db.execute(
        """
        UPDATE products
        SET category_id = ?, name = ?, description = ?, price = ?,
            image_path = ?, is_active = ?
        WHERE id = ?
        """,
        (
            category["id"],
            name,
            description.strip(),
            parsed_price,
            image_path,
            1 if form["is_active"] else 0,
            product_id,
        ),
    )
    return RedirectResponse("/admin/products", status_code=303)


@protected.post("/products/{product_id}/toggle")
def product_toggle(product_id: int):
    db.execute(
        "UPDATE products SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (product_id,),
    )
    return RedirectResponse("/admin/products", status_code=303)


@protected.post("/products/{product_id}/delete")
def product_delete(product_id: int):
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    return RedirectResponse("/admin/products", status_code=303)


# ------------------------------------------------------------------ категории

@protected.get("/categories")
def categories_list(request: Request, error: str | None = None):
    categories = db.fetch_all(
        """
        SELECT c.*, (SELECT COUNT(*) FROM products WHERE category_id = c.id) AS product_count
        FROM categories c
        ORDER BY c.name
        """
    )
    return templates.TemplateResponse(
        request,
        "admin/categories.html",
        {
            "categories": categories,
            "error": error,
            "page": "admin",
            "active": "categories",
        },
    )


@protected.post("/categories")
def category_create(name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(
            "/admin/categories?error=Укажите+название+категории", status_code=303
        )
    slug = db.unique_slug("categories", db.slugify(name))
    db.execute("INSERT INTO categories (name, slug) VALUES (?, ?)", (name, slug))
    return RedirectResponse("/admin/categories", status_code=303)


@protected.post("/categories/{category_id}/rename")
def category_rename(category_id: int, name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(
            "/admin/categories?error=Название+не+может+быть+пустым", status_code=303
        )
    db.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
    return RedirectResponse("/admin/categories", status_code=303)


# --------------------------------------------------------------------- заказы

@protected.get("/orders")
def orders_list(request: Request):
    orders = db.fetch_all(
        """
        SELECT o.*,
               (SELECT COALESCE(SUM(qty), 0) FROM order_items WHERE order_id = o.id) AS units
        FROM orders o
        ORDER BY o.created_at DESC, o.id DESC
        """
    )
    return templates.TemplateResponse(
        request,
        "admin/orders.html",
        {"orders": orders, "page": "admin", "active": "orders"},
    )


@protected.get("/orders/{order_id}")
def order_detail(request: Request, order_id: int):
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
        "admin/order_detail.html",
        {
            "order": order,
            "items": items,
            "statuses": list(ALLOWED_STATUSES),
            "page": "admin",
            "active": "orders",
        },
    )


@protected.post("/orders/{order_id}/status")
def order_status(order_id: int, status: str = Form("")):
    if status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Недопустимый статус")
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    return RedirectResponse(f"/admin/orders/{order_id}", status_code=303)


router.include_router(protected)
