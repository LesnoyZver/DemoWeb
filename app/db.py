from __future__ import annotations

import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
DB_PATH = DATA_DIR / "shop.db"
UPLOADS_DIR = DATA_DIR / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    price       INTEGER NOT NULL,
    image_path  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    phone         TEXT NOT NULL,
    email         TEXT NOT NULL,
    address       TEXT NOT NULL,
    total         INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'new',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    qty        INTEGER NOT NULL,
    price      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def fetch_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with closing(get_conn()) as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    with closing(get_conn()) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return int(cur.lastrowid)


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(value: str) -> str:
    """Простой транслит в URL-safe slug."""
    parts: list[str] = []
    for char in value.lower():
        if char in _TRANSLIT:
            parts.append(_TRANSLIT[char])
        elif char.isalnum():
            parts.append(char)
        elif char in " -_/":
            parts.append("-")
    slug = re.sub(r"-+", "-", "".join(parts)).strip("-")
    return slug or "item"


def unique_slug(table: str, base: str, exclude_id: int | None = None) -> str:
    """Подбирает свободный slug. table — только 'products' или 'categories'."""
    if table not in {"products", "categories"}:
        raise ValueError("unsupported table")
    slug = base
    suffix = 2
    while True:
        row = fetch_one(f"SELECT id FROM {table} WHERE slug = ?", (slug,))
        if row is None or (exclude_id is not None and row["id"] == exclude_id):
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def create_order(customer: dict, items: list[dict]) -> int:
    """Сохраняет заказ и позиции в одной транзакции. Возвращает id заказа."""
    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO orders (customer_name, phone, email, address, total, status)
                VALUES (?, ?, ?, ?, ?, 'new')
                """,
                (
                    customer["customer_name"],
                    customer["phone"],
                    customer["email"],
                    customer["address"],
                    customer["total"],
                ),
            )
            order_id = int(cur.lastrowid)
            conn.executemany(
                "INSERT INTO order_items (order_id, product_id, qty, price) VALUES (?, ?, ?, ?)",
                [(order_id, item["id"], item["qty"], item["price"]) for item in items],
            )
        return order_id
    finally:
        conn.close()
