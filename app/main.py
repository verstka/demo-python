"""FastAPI entry: CMS, Verstka callbacks, lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from verstka_sdk import AsyncVerstkaClient, VerstkaConfig
from verstka_sdk.integrations.fastapi import build_callback_router, install_exception_handlers

from app.config import get_settings
from app.database import init_db
from app.debug_request_logging import DebugRequestLoggingMiddleware
from app.routers import cms as cms_router
from app.services import publish
from app.verstka_handlers import build_verstka_hooks
from app.verstka_storage import CmsVerstkaStorage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db(settings)
    publish.ensure_default_favicon(settings)
    await publish.write_sitemap(settings)

    vconf = VerstkaConfig(
        api_key=settings.verstka_api_key,
        api_secret=settings.verstka_api_secret,
        callback_url=settings.verstka_callback_url,
        api_url=settings.verstka_api_url,
        debug=settings.debug,
    )
    client = AsyncVerstkaClient(vconf)
    storage = CmsVerstkaStorage(settings)
    pre_c, pre_f, fin_c, fin_f = build_verstka_hooks(settings)
    vr = build_callback_router(
        client,
        storage=storage,
        on_content_finalize=fin_c,
        on_fonts_finalize=fin_f,
        on_content_pre_save=pre_c,
        on_fonts_pre_save=pre_f,
    )
    app.include_router(vr)
    app.state.verstka_client = client
    app.state.settings = settings
    app.state.storage = storage
    yield
    await client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Verstka CMS demo", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=False,
    )
    if settings.debug:
        app.add_middleware(DebugRequestLoggingMiddleware)
    install_exception_handlers(app)
    app.include_router(cms_router.router)
    return app


app = create_app()
