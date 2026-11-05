from __future__ import annotations

import hmac
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Request

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY не задан. Задайте переменную окружения SECRET_KEY "
        "(длинную случайную строку) перед запуском приложения."
    )
if not ADMIN_PASSWORD:
    raise RuntimeError(
        "ADMIN_PASSWORD не задан. Задайте переменную окружения ADMIN_PASSWORD "
        "перед запуском приложения."
    )


class NotAuthenticated(Exception):
    """Выбрасывается, когда админ-маршрут открыт без активной сессии."""


def check_password(raw: str) -> bool:
    return hmac.compare_digest(raw, ADMIN_PASSWORD)


def is_admin(request: Request) -> bool:
    return request.session.get("admin") is True


def login(request: Request) -> None:
    request.session["admin"] = True


def logout(request: Request) -> None:
    request.session.clear()


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise NotAuthenticated()
