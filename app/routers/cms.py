"""CMS UI and HTML forms under /cms."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER
from verstka_sdk import VerstkaApiError, VerstkaError

from app.config import Settings, get_settings
from app.database import get_connection
from app import login_guard
from app.paths import is_valid_article_path, normalize_article_path, storage_article_dir
from app import repo
from app.services import publish
from app.validation import is_valid_email

router = APIRouter(prefix="/cms", tags=["cms"])
_ph = PasswordHasher()

_ALLOWED_OG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_MIN_BOOTSTRAP_PASSWORD_LEN = 8


class CmsLoginRequired(Exception):
    """Raised when a CMS route is accessed without an authenticated session."""


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CmsLoginRequired)
    async def _redirect_to_cms_login(request: Request, exc: CmsLoginRequired) -> RedirectResponse:
        return RedirectResponse("/cms/login", status_code=HTTP_303_SEE_OTHER)


def _templates(settings: Settings) -> Jinja2Templates:
    return Jinja2Templates(directory=str(settings.templates_dir))


def require_cms_user(request: Request) -> str:
    user_email = request.session.get("user_email")
    if not user_email:
        raise CmsLoginRequired()
    return str(user_email)


CmsUser = Annotated[str, Depends(require_cms_user)]


def _login_page(
    request: Request,
    settings: Settings,
    *,
    bootstrap: bool,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return _templates(settings).TemplateResponse(
        request,
        "cms/login.html.j2",
        {"request": request, "bootstrap": bootstrap, "error": error},
        status_code=status_code,
    )


def _editor_config_error(settings: Settings) -> str | None:
    missing: list[str] = []
    if not settings.verstka_api_key:
        missing.append("VERSTKA_API_KEY")
    if not settings.verstka_api_secret:
        missing.append("VERSTKA_API_SECRET")
    if not settings.verstka_callback_url:
        missing.append("VERSTKA_CALLBACK_URL")
    if not missing:
        return None
    return "Verstka editor is not configured. Set " + ", ".join(missing) + " and restart the app."


def _editor_error_response(
    request: Request,
    settings: Settings,
    *,
    status_code: int,
    title: str,
    message: str,
) -> HTMLResponse:
    return _templates(settings).TemplateResponse(
        request,
        "cms/editor_error.html.j2",
        {
            "request": request,
            "title": title,
            "message": message,
            "api_url": settings.verstka_api_url,
            "callback_url": settings.verstka_callback_url,
        },
        status_code=status_code,
    )


async def _verify_login(settings: Settings, user_email: str, password: str) -> bool:
    async with get_connection(settings) as db:
        row = await repo.get_cms_user(db, user_email)
    if not row:
        return False
    try:
        _ph.verify(row["password_hash"], password)
        return True
    except VerifyMismatchError:
        return False


async def _is_bootstrap_required(settings: Settings) -> bool:
    async with get_connection(settings) as db:
        return await repo.count_cms_users(db) == 0


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, settings: Settings = Depends(get_settings)) -> Any:
    if request.session.get("user_email"):
        return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)
    return _login_page(request, settings, bootstrap=await _is_bootstrap_required(settings))


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    user_email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> Any:
    email = user_email.strip()
    bootstrap = await _is_bootstrap_required(settings)
    if bootstrap:
        if not is_valid_email(email):
            return _login_page(request, settings, bootstrap=True, error="Invalid email", status_code=400)
        if len(password) < _MIN_BOOTSTRAP_PASSWORD_LEN:
            return _login_page(
                request,
                settings,
                bootstrap=True,
                error=f"Password must be at least {_MIN_BOOTSTRAP_PASSWORD_LEN} characters",
                status_code=400,
            )
        async with get_connection(settings) as db:
            await repo.insert_cms_user(db, email, _ph.hash(password))
            await db.commit()
        request.session["user_email"] = email
        return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)

    if not is_valid_email(email):
        return _login_page(request, settings, bootstrap=False, error="Invalid email", status_code=400)

    if login_guard.is_user_login_blocked(settings, email):
        return _login_page(
            request,
            settings,
            bootstrap=False,
            error="Too many failed attempts. Try again later.",
            status_code=429,
        )
    if await _verify_login(settings, email, password):
        login_guard.clear_user_login_failures(email)
        request.session["user_email"] = email
        return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)
    login_guard.record_user_login_failure(settings, email)
    return _login_page(
        request,
        settings,
        bootstrap=False,
        error="Invalid email or password",
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/cms/login", status_code=HTTP_303_SEE_OTHER)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def cms_root(_user: CmsUser) -> RedirectResponse:
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.get("/articles", response_class=HTMLResponse)
async def articles_list(
    request: Request,
    _user: CmsUser,
    settings: Settings = Depends(get_settings),
) -> Any:
    async with get_connection(settings) as db:
        raw = await repo.list_articles(db)
    articles: list[dict[str, Any]] = []
    for row in raw:
        article = dict(row)
        article["path_q"] = quote(article["path"], safe="")
        articles.append(article)
    return _templates(settings).TemplateResponse(
        request,
        "cms/articles.html.j2",
        {"request": request, "articles": articles},
    )


@router.post("/articles/create")
async def articles_create(
    _user: CmsUser,
    path: Annotated[str, Form()],
    title: Annotated[str, Form()],
    og_title: Annotated[str | None, Form()] = None,
    og_description: Annotated[str | None, Form()] = None,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    p = normalize_article_path(path)
    if not is_valid_article_path(p):
        raise HTTPException(400, "Недопустимый или зарезервированный путь")
    async with get_connection(settings) as db:
        try:
            row = await repo.insert_article(
                db,
                path=p,
                title=title.strip() or p,
                og_title=(og_title or "").strip() or None,
                og_description=(og_description or "").strip() or None,
                og_image_relpath=None,
                is_visible=True,
            )
            await publish.publish_article_change(settings, row, db=db)
            await db.commit()
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.post("/articles/delete")
async def articles_delete(
    _user: CmsUser,
    path: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    p = normalize_article_path(path)
    async with get_connection(settings) as db:
        await repo.delete_article(db, p)
        await db.commit()
    await publish.publish_article_removed(settings, p)
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.post("/articles/visibility")
async def articles_visibility(
    _user: CmsUser,
    path: Annotated[str, Form()],
    is_visible: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    p = normalize_article_path(path)
    vis = is_visible in ("1", "true", "on", "yes")
    async with get_connection(settings) as db:
        await repo.update_article_meta(db, p, is_visible=vis)
        await db.commit()
    await publish.sync_visibility_to_disk(settings, p, vis)
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.post("/articles/og")
async def articles_og(
    _user: CmsUser,
    path: Annotated[str, Form()],
    og_title: Annotated[str | None, Form()] = None,
    og_description: Annotated[str | None, Form()] = None,
    og_image: UploadFile | None = File(None),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    p = normalize_article_path(path)
    async with get_connection(settings) as db:
        row = await repo.article_by_path(db, p)
        if not row:
            raise HTTPException(404)
        rel_img = row.get("og_image_relpath")
        if og_image and og_image.filename:
            suf = Path(og_image.filename).suffix.lower()
            if suf not in _ALLOWED_OG_EXT:
                raise HTTPException(400, "Недопустимый тип файла")
            body = await og_image.read()
            if len(body) > 5 * 1024 * 1024:
                raise HTTPException(400, "Файл слишком большой")
            d = storage_article_dir(settings.storage_dir, p)
            d.mkdir(parents=True, exist_ok=True)
            name = f"og_{secrets.token_hex(4)}{suf}"
            (d / name).write_bytes(body)
            rel_img = name
        row = await repo.update_article_meta(
            db,
            p,
            og_title=(og_title or "").strip() or None,
            og_description=(og_description or "").strip() or None,
            og_image_relpath=rel_img,
        )
        await publish.publish_article_change(settings, row, db=db)
        await db.commit()
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.get("/articles/open")
async def articles_open_editor(
    request: Request,
    user_email: CmsUser,
    path: str = Query(..., description="Логический путь статьи, например /index"),
    settings: Settings = Depends(get_settings),
) -> Any:
    config_error = _editor_config_error(settings)
    if config_error:
        return _editor_error_response(
            request,
            settings,
            status_code=500,
            title="Verstka editor is not configured",
            message=config_error,
        )
    p = normalize_article_path(path)
    client = request.app.state.verstka_client
    async with get_connection(settings) as db:
        row = await repo.article_by_path(db, p)
        if not row:
            raise HTTPException(404)
        vms = repo.parse_vms_json(row.get("vms_json"))
    try:
        url = await client.get_editor_url(
            row["material_id"],
            vms_json=vms,
            metadata={"user_email": user_email},
        )
    except VerstkaApiError as exc:
        message = exc.message
        if exc.status_code == 403 and "not allowed" in exc.message.lower():
            message = (
                "Verstka rejected this callback host for the current API key. "
                f"Current VERSTKA_CALLBACK_URL is {settings.verstka_callback_url!r}. "
                "Use an HTTPS public callback URL that is allowed for this key, "
                "then restart the app."
            )
        return _editor_error_response(
            request,
            settings,
            status_code=exc.status_code or 502,
            title="Could not open Verstka editor",
            message=message,
        )
    except httpx.RequestError as exc:
        return _editor_error_response(
            request,
            settings,
            status_code=502,
            title="Could not reach Verstka API",
            message=f"Request to {settings.verstka_api_url!r} failed: {exc}",
        )
    except (ValueError, VerstkaError) as exc:
        return _editor_error_response(
            request,
            settings,
            status_code=500,
            title="Could not open Verstka editor",
            message=str(exc),
        )
    return RedirectResponse(url, status_code=HTTP_303_SEE_OTHER)


@router.get("/users", response_class=HTMLResponse)
async def users_list(
    request: Request,
    _user: CmsUser,
    settings: Settings = Depends(get_settings),
) -> Any:
    async with get_connection(settings) as db:
        users = await repo.list_cms_users(db)
    return _templates(settings).TemplateResponse(
        request,
        "cms/users.html.j2",
        {"request": request, "users": users},
    )


@router.post("/users/create")
async def users_create(
    _user: CmsUser,
    user_email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    email = user_email.strip()
    if not is_valid_email(email) or not password:
        raise HTTPException(400)
    async with get_connection(settings) as db:
        if await repo.get_cms_user(db, email):
            raise HTTPException(400, "Пользователь уже существует")
        await repo.insert_cms_user(db, email, _ph.hash(password))
        await db.commit()
    return RedirectResponse("/cms/users", status_code=HTTP_303_SEE_OTHER)


@router.post("/users/delete")
async def users_delete(
    session_user: CmsUser,
    user_email: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if user_email == session_user:
        raise HTTPException(400, "Нельзя удалить самого себя")
    async with get_connection(settings) as db:
        await repo.delete_cms_user(db, user_email)
        await db.commit()
    return RedirectResponse("/cms/users", status_code=HTTP_303_SEE_OTHER)


@router.post("/users/password")
async def users_password(
    _user: CmsUser,
    user_email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    async with get_connection(settings) as db:
        if not await repo.get_cms_user(db, user_email):
            raise HTTPException(404)
        await repo.update_cms_user_password(db, user_email, _ph.hash(password))
        await db.commit()
    return RedirectResponse("/cms/users", status_code=HTTP_303_SEE_OTHER)
