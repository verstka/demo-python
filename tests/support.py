"""Shared helpers for unittest-based integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from verstka_sdk import AsyncVerstkaClient, VerstkaConfig
from verstka_sdk.integrations.fastapi import build_callback_router, install_exception_handlers

from app import repo
from app.config import Settings, get_settings
from app.database import get_connection, init_db
from app.routers import cms
from app.verstka_handlers import build_verstka_hooks
from app.verstka_storage import CmsVerstkaStorage

T = TypeVar("T")

DEFAULT_VIEWER_SCRIPT_URL = "https://go.r2.verstka.org/viewer-latest.js"


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def make_test_settings(tmp_root: Path, **overrides: Any) -> Settings:
    root = Path(tmp_root)
    defaults: dict[str, Any] = {
        "VERSTKA_API_KEY": "key",
        "VERSTKA_API_SECRET": "secret",
        "VERSTKA_CALLBACK_URL": "https://cms.example.test/verstka/callback",
        "VERSTKA_API_URL": "https://api-stage.verstka.org/integration",
        "PUBLIC_BASE_URL": "https://cms.example.test",
        "SESSION_SECRET": "test-secret",
        "DATABASE_URL": f"sqlite+aiosqlite:///{root / 'data.db'}",
        "storage_dir": root / "storage",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def build_cms_test_app(
    settings: Settings,
    *,
    verstka_client: Any | None = None,
) -> TestClient:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(cms.router)
    if verstka_client is not None:
        app.state.verstka_client = verstka_client
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app, follow_redirects=False)


async def seed_admin_and_article(
    settings: Settings,
    *,
    user_email: str = "admin@example.test",
    password: str = "password123",
    article_path: str = "/hi",
    article_title: str = "Hello",
) -> None:
    await init_db(settings)
    async with get_connection(settings) as db:
        await repo.insert_cms_user(
            db,
            user_email,
            PasswordHasher().hash(password),
        )
        await repo.insert_article(
            db,
            path=article_path,
            title=article_title,
            og_title=None,
            og_description=None,
            og_image_relpath=None,
        )
        await db.commit()


def build_verstka_callback_client(settings: Settings) -> TestClient:
    client = AsyncVerstkaClient(
        VerstkaConfig(
            api_key=settings.verstka_api_key,
            api_secret=settings.verstka_api_secret,
            callback_url=settings.verstka_callback_url,
            api_url=settings.verstka_api_url,
            debug=True,
        )
    )
    storage = CmsVerstkaStorage(settings)
    pre_c, pre_f, fin_c, fin_f = build_verstka_hooks(settings)
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(
        build_callback_router(
            client,
            storage=storage,
            on_content_finalize=fin_c,
            on_fonts_finalize=fin_f,
            on_content_pre_save=pre_c,
            on_fonts_pre_save=pre_f,
        )
    )
    return TestClient(app)
