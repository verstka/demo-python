"""CMS UI and HTML forms under /cms."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER

from app.config import Settings, get_settings
from app.database import get_connection
from app.env_bootstrap import default_dotenv_path, merge_admins_into_dotenv
from app.paths import is_valid_article_path, normalize_article_path, storage_article_dir
from app import repo
from app.services import publish

router = APIRouter(prefix="/cms", tags=["cms"])
_ph = PasswordHasher()

_ALLOWED_OG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _templates(settings: Settings) -> Jinja2Templates:
    return Jinja2Templates(directory=str(settings.templates_dir))


def _auth_or_redirect(request: Request) -> str | RedirectResponse:
    u = request.session.get("user_email")
    if not u:
        return RedirectResponse("/cms/login", status_code=HTTP_303_SEE_OTHER)
    return str(u)


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.fullmatch(value.strip()))


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
    """True when ADMINS is empty and cms_users has no rows (first deploy without .env users)."""
    if settings.admins_seed():
        return False
    async with get_connection(settings) as db:
        n = await repo.count_cms_users(db)
    return n == 0


_MIN_BOOTSTRAP_PASSWORD_LEN = 8


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, settings: Settings = Depends(get_settings)) -> Any:
    if request.session.get("user_email"):
        return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)

    pending_restart_email = request.session.get("bootstrap_pending_restart")
    if pending_restart_email:
        async with get_connection(settings) as db:
            seeded = await repo.count_cms_users(db) > 0
        if seeded:
            request.session.pop("bootstrap_pending_restart", None)
        else:
            return _templates(settings).TemplateResponse(
                request,
                "cms/bootstrap_done.html.j2",
                {"request": request, "user_email": str(pending_restart_email)},
            )

    if await _is_bootstrap_required(settings):
        return _templates(settings).TemplateResponse(
            request,
            "cms/bootstrap_login.html.j2",
            {"request": request, "error": None},
        )
    return _templates(settings).TemplateResponse(
        request,
        "cms/login.html.j2",
        {"request": request, "error": None},
    )


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    user_email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> Any:
    email = user_email.strip()
    if await _is_bootstrap_required(settings):
        if not _is_valid_email(email):
            return _templates(settings).TemplateResponse(
                request,
                "cms/bootstrap_login.html.j2",
                {"request": request, "error": "Invalid email"},
                status_code=400,
            )
        if len(password) < _MIN_BOOTSTRAP_PASSWORD_LEN:
            return _templates(settings).TemplateResponse(
                request,
                "cms/bootstrap_login.html.j2",
                {
                    "request": request,
                    "error": f"Password must be at least {_MIN_BOOTSTRAP_PASSWORD_LEN} characters",
                },
                status_code=400,
            )
        merge_admins_into_dotenv(
            dotenv_path=default_dotenv_path(),
            admins={email: _ph.hash(password)},
        )
        get_settings.cache_clear()
        request.session["bootstrap_pending_restart"] = email
        return _templates(settings).TemplateResponse(
            request,
            "cms/bootstrap_done.html.j2",
            {"request": request, "user_email": email},
        )

    if not _is_valid_email(email):
        return _templates(settings).TemplateResponse(
            request,
            "cms/login.html.j2",
            {"request": request, "error": "Invalid email"},
            status_code=400,
        )
    if await _verify_login(settings, email, password):
        request.session["user_email"] = email
        return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)
    return _templates(settings).TemplateResponse(
        request,
        "cms/login.html.j2",
        {"request": request, "error": "Invalid email or password"},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/cms/login", status_code=HTTP_303_SEE_OTHER)


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def cms_root(request: Request) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.get("/articles", response_class=HTMLResponse)
async def articles_list(request: Request, settings: Settings = Depends(get_settings)) -> Any:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    async with get_connection(settings) as db:
        raw = await repo.list_articles(db)
    articles: list[dict[str, Any]] = []
    for r in raw:
        d = dict(r)
        d["path_q"] = quote(d["path"], safe="")
        articles.append(d)
    return _templates(settings).TemplateResponse(
        request,
        "cms/articles.html.j2",
        {"request": request, "articles": articles},
    )


@router.post("/articles/create")
async def articles_create(
    request: Request,
    path: Annotated[str, Form()],
    title: Annotated[str, Form()],
    og_title: Annotated[str | None, Form()] = None,
    og_description: Annotated[str | None, Form()] = None,
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    p = normalize_article_path(path)
    if not is_valid_article_path(p):
        raise HTTPException(400, "Недопустимый или зарезервированный путь")
    row: dict[str, Any] | None = None
    async with get_connection(settings) as db:
        try:
            await repo.insert_article(
                db,
                path=p,
                title=title.strip() or p,
                og_title=(og_title or "").strip() or None,
                og_description=(og_description or "").strip() or None,
                og_image_relpath=None,
                is_visible=True,
            )
            row = await repo.article_by_path(db, p)
            await db.commit()
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
    if row and row.get("is_visible"):
        async with get_connection(settings) as db2:
            await publish.write_article_index(settings, row, db2)
            await db2.commit()
        if p in ("/menu", "/footer"):
            await publish.regenerate_all_visible_indexes(settings)
    await publish.write_sitemap(settings)
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.post("/articles/delete")
async def articles_delete(
    request: Request,
    path: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    p = normalize_article_path(path)
    async with get_connection(settings) as db:
        await repo.delete_article(db, p)
        await db.commit()
    await publish.delete_article_storage(settings, p)
    if p in ("/menu", "/footer"):
        await publish.regenerate_all_visible_indexes(settings)
    await publish.write_sitemap(settings)
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.post("/articles/visibility")
async def articles_visibility(
    request: Request,
    path: Annotated[str, Form()],
    is_visible: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    p = normalize_article_path(path)
    vis = is_visible in ("1", "true", "on", "yes")
    async with get_connection(settings) as db:
        await repo.update_article_meta(db, p, is_visible=vis)
        await db.commit()
    await publish.sync_visibility_to_disk(settings, p, vis)
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.post("/articles/og")
async def articles_og(
    request: Request,
    path: Annotated[str, Form()],
    og_title: Annotated[str | None, Form()] = None,
    og_description: Annotated[str | None, Form()] = None,
    og_image: UploadFile | None = File(None),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
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
        await repo.update_article_meta(
            db,
            p,
            og_title=(og_title or "").strip() or None,
            og_description=(og_description or "").strip() or None,
            og_image_relpath=rel_img,
        )
        row = await repo.article_by_path(db, p)
        await db.commit()
    if row and row.get("is_visible"):
        async with get_connection(settings) as db2:
            await publish.write_article_index(settings, row, db2)
            await db2.commit()
        if p in ("/menu", "/footer"):
            await publish.regenerate_all_visible_indexes(settings)
    await publish.write_sitemap(settings)
    return RedirectResponse("/cms/articles", status_code=HTTP_303_SEE_OTHER)


@router.get("/articles/open")
async def articles_open_editor(
    request: Request,
    path: str = Query(..., description="Логический путь статьи, например /index"),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    p = normalize_article_path(path)
    client = request.app.state.verstka_client
    async with get_connection(settings) as db:
        row = await repo.article_by_path(db, p)
        if not row:
            raise HTTPException(404)
        vms = repo.parse_vms_json(row.get("vms_json"))
    url = await client.get_editor_url(row["material_id"], vms_json=vms, metadata={})
    return RedirectResponse(url, status_code=HTTP_303_SEE_OTHER)


@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, settings: Settings = Depends(get_settings)) -> Any:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    async with get_connection(settings) as db:
        users = await repo.list_cms_users(db)
    return _templates(settings).TemplateResponse(
        request,
        "cms/users.html.j2",
        {"request": request, "users": users},
    )


@router.post("/users/create")
async def users_create(
    request: Request,
    user_email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    email = user_email.strip()
    if not _is_valid_email(email) or not password:
        raise HTTPException(400)
    async with get_connection(settings) as db:
        if await repo.get_cms_user(db, email):
            raise HTTPException(400, "Пользователь уже существует")
        await repo.insert_cms_user(db, email, _ph.hash(password))
        await db.commit()
    return RedirectResponse("/cms/users", status_code=HTTP_303_SEE_OTHER)


@router.post("/users/delete")
async def users_delete(
    request: Request,
    user_email: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    if user_email == auth:
        raise HTTPException(400, "Нельзя удалить самого себя")
    async with get_connection(settings) as db:
        await repo.delete_cms_user(db, user_email)
        await db.commit()
    return RedirectResponse("/cms/users", status_code=HTTP_303_SEE_OTHER)


@router.post("/users/password")
async def users_password(
    request: Request,
    user_email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    auth = _auth_or_redirect(request)
    if isinstance(auth, RedirectResponse):
        return auth
    async with get_connection(settings) as db:
        if not await repo.get_cms_user(db, user_email):
            raise HTTPException(404)
        await repo.update_cms_user_password(db, user_email, _ph.hash(password))
        await db.commit()
    return RedirectResponse("/cms/users", status_code=HTTP_303_SEE_OTHER)
