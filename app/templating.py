from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

# Имя магазина. Пустая строка — логотип и подписи бренда не выводятся.
SHOP_NAME = ""

STATUS_LABELS = {
    "new": "Новый",
    "in_progress": "В работе",
    "done": "Выполнен",
}


def format_price(value: object) -> str:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)
    grouped = f"{number:,}".replace(",", "\u00a0")
    return f"{grouped}\u00a0BYN"


def format_date(value: object) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except ValueError:
        return str(value)


def status_label(value: object) -> str:
    return STATUS_LABELS.get(str(value), str(value))


templates.env.filters["byn"] = format_price
templates.env.filters["date"] = format_date
templates.env.filters["status"] = status_label
templates.env.globals["STATUS_LABELS"] = STATUS_LABELS
templates.env.globals["SHOP_NAME"] = SHOP_NAME
