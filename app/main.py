from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import db, seed
from .auth import NotAuthenticated, SECRET_KEY
from .routes_admin import router as admin_router
from .routes_public import router as public_router

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"


class SecureSessionCookieMiddleware:
    """Добавляет флаг Secure к cookie сессии, если запрос пришёл по HTTPS."""

    def __init__(self, app: ASGIApp, cookie_name: str = "session") -> None:
        self.app = app
        self.cookie_name = cookie_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("scheme") != "https":
            await self.app(scope, receive, send)
            return

        prefix = f"{self.cookie_name}="

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                for index, (name, value) in enumerate(headers):
                    if name.lower() != b"set-cookie":
                        continue
                    cookie = value.decode("latin-1")
                    if cookie.startswith(prefix) and "; secure" not in cookie.lower():
                        headers[index] = (name, (cookie + "; secure").encode("latin-1"))
            await send(message)

        await self.app(scope, receive, send_wrapper)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)
    db.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    seed.run()
    yield


app = FastAPI(title="Интернет-магазин аксессуаров", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=False,
)
app.add_middleware(SecureSessionCookieMiddleware, cookie_name="session")

app.mount(
    "/static/uploads",
    StaticFiles(directory=str(db.UPLOADS_DIR), check_dir=False),
    name="uploads",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(_: Request, __: NotAuthenticated):
    return RedirectResponse("/admin/login", status_code=303)


app.include_router(public_router)
app.include_router(admin_router)
