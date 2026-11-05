from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .db import UPLOADS_DIR, fetch_one, get_conn

CATEGORIES = [
    {"name": "Чехлы", "slug": "cases"},
    {"name": "Кабели и зарядка", "slug": "cables"},
    {"name": "Подставки и органайзеры", "slug": "stands"},
]

PRODUCTS = [
    {
        "category": "cases",
        "name": "Чехол Soft Shell",
        "slug": "soft-shell-case",
        "price": 79,
        "description": "Матчевый чехол из мягкого силикона с точной посадкой и защитой блока камер.",
    },
    {
        "category": "cases",
        "name": "Чехол Clear Frame",
        "slug": "clear-frame-case",
        "price": 89,
        "description": "Прозрачный корпус с усиленными углами, который не желтеет со временем.",
    },
    {
        "category": "cases",
        "name": "Чехол Folio Grey",
        "slug": "folio-grey-case",
        "price": 119,
        "description": "Тонкая обложка с магнитным креплением и внутренним карманом для карты.",
    },
    {
        "category": "cases",
        "name": "Чехол Leather Black",
        "slug": "leather-black-case",
        "price": 149,
        "description": "Кожаный чехол с мягкой подкладкой и аккуратной строчкой по краю.",
    },
    {
        "category": "cables",
        "name": "Кабель USB-C 1 м",
        "slug": "usb-c-cable-1m",
        "price": 39,
        "description": "Плотная оплётка и разъёмы с усиленной фиксацией для ежедневной зарядки.",
    },
    {
        "category": "cables",
        "name": "Кабель USB-C 2 м",
        "slug": "usb-c-cable-2m",
        "price": 49,
        "description": "Увеличенная длина для работы за столом, поддерживает быструю зарядку.",
    },
    {
        "category": "cables",
        "name": "Кабель Lightning 1 м",
        "slug": "lightning-cable-1m",
        "price": 45,
        "description": "Компактный кабель для зарядки и передачи данных без лишних узлов.",
    },
    {
        "category": "cables",
        "name": "Зарядный блок 30 Вт",
        "slug": "charger-30w",
        "price": 99,
        "description": "Компактный адаптер питания с одним портом USB-C и защитой от перегрева.",
    },
    {
        "category": "stands",
        "name": "Подставка Laptop Rise",
        "slug": "laptop-rise-stand",
        "price": 159,
        "description": "Алюминиевая подставка для ноутбука с регулируемым углом и тихими петлями.",
    },
    {
        "category": "stands",
        "name": "Органайзер Cable Tray",
        "slug": "cable-tray-organizer",
        "price": 69,
        "description": "Настольный лоток для кабелей и мелких аксессуаров из матового пластика.",
    },
    {
        "category": "stands",
        "name": "Подставка Phone Dock",
        "slug": "phone-dock-stand",
        "price": 85,
        "description": "Минималистичная док-станция для телефона с силиконовыми вставками.",
    },
    {
        "category": "stands",
        "name": "Сумка Tech Pouch",
        "slug": "tech-pouch-bag",
        "price": 129,
        "description": "Компактный органайзер для зарядок и переходников с эластичными держателями.",
    },
]

BG = (245, 245, 245)
INK = (10, 10, 10)
MUTED = (107, 107, 107)
LINE = (229, 229, 229)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _draw_placeholder(path: Path, label: str, index: int) -> None:
    size = 800
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle((40, 40, size - 40, size - 40), outline=LINE, width=2)

    cx = cy = size // 2
    variant = index % 4

    if variant == 0:
        draw.ellipse((cx - 200, cy - 200, cx + 200, cy + 200), outline=INK, width=6)
        draw.ellipse((cx - 110, cy - 110, cx + 110, cy + 110), fill=INK)
    elif variant == 1:
        draw.rounded_rectangle(
            (cx - 170, cy - 250, cx + 170, cy + 250),
            radius=36,
            outline=INK,
            width=6,
        )
        draw.rounded_rectangle(
            (cx - 100, cy - 160, cx + 100, cy + 160),
            radius=18,
            fill=LINE,
        )
    elif variant == 2:
        for offset in (0, 60, 120):
            draw.rectangle(
                (cx - 240 + offset, cy - 240 + offset, cx + 240 - offset, cy + 240 - offset),
                outline=INK if offset == 0 else MUTED,
                width=4,
            )
    else:
        for offset in range(-240, 241, 80):
            draw.line((cx + offset, cy - 240, cx + offset + 240, cy + 240), fill=LINE, width=6)
        draw.line((cx - 260, cy, cx + 260, cy), fill=INK, width=8)

    label_font = _font(40)
    tiny_font = _font(28)
    draw.text((70, 70), f"{index:02d}", fill=INK, font=tiny_font)
    draw.text((70, size - 110), label.upper()[:24], fill=MUTED, font=label_font)

    img.save(path, "PNG", optimize=True)


def run() -> None:
    """Наполняет БД демо-данными, только если товаров ещё нет."""
    existing = fetch_one("SELECT COUNT(*) AS n FROM products")
    if existing and existing["n"] > 0:
        return

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    try:
        with conn:
            for category in CATEGORIES:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (name, slug) VALUES (?, ?)",
                    (category["name"], category["slug"]),
                )
            category_ids = {
                row["slug"]: row["id"]
                for row in conn.execute("SELECT id, slug FROM categories").fetchall()
            }

            for index, item in enumerate(PRODUCTS, start=1):
                image_name = f"{item['slug']}.png"
                image_path = UPLOADS_DIR / image_name
                if not image_path.exists():
                    _draw_placeholder(image_path, item["slug"].replace("-", " "), index)

                conn.execute(
                    """
                    INSERT OR IGNORE INTO products
                        (category_id, name, slug, description, price, image_path, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        category_ids[item["category"]],
                        item["name"],
                        item["slug"],
                        item["description"],
                        item["price"],
                        f"/static/uploads/{image_name}",
                    ),
                )
    finally:
        conn.close()
