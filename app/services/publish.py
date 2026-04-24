"""Write index.html, sitemap.xml; regenerate visible pages."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import aiosqlite

from app.config import Settings
from app.database import get_connection
from app.paths import storage_article_dir
from app import repo
from app.services import render


async def _menu_footer_blocks(settings: Settings, db: aiosqlite.Connection) -> tuple[str, str]:
    menu_row = await repo.article_by_path(db, "/menu")
    footer_row = await repo.article_by_path(db, "/footer")
    menu_html = ""
    footer_html = ""
    if menu_row and menu_row.get("html") and menu_row.get("is_visible"):
        menu_html = menu_row["html"]
    if footer_row and footer_row.get("html") and footer_row.get("is_visible"):
        footer_html = footer_row["html"]
    return menu_html, footer_html


async def write_article_index(settings: Settings, article: dict[str, Any], db: aiosqlite.Connection) -> None:
    menu_html, footer_html = await _menu_footer_blocks(settings, db)
    fonts_ok = render.fonts_css_file_exists(settings)
    html = render.render_article_page(
        settings,
        article=article,
        menu_html=menu_html,
        footer_html=footer_html,
        fonts_css_exists=fonts_ok,
    )
    d = storage_article_dir(settings.storage_dir, article["path"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html, encoding="utf-8")


async def remove_article_index(settings: Settings, article_path: str) -> None:
    d = storage_article_dir(settings.storage_dir, article_path)
    index = d / "index.html"
    if index.is_file():
        index.unlink()


async def write_sitemap(settings: Settings) -> None:
    async with get_connection(settings) as db:
        paths = await repo.list_visible_article_paths_for_sitemap(db)
    base = settings.public_base_url.rstrip("/")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in paths:
        loc = f"{base}{path}/"
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        lines.append("  </url>")
    lines.append("</urlset>")
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def regenerate_all_visible_indexes(settings: Settings) -> None:
    async with get_connection(settings) as db:
        articles = await repo.list_visible_articles_for_regen(db)
        for a in articles:
            await write_article_index(settings, a, db)
        # menu/footer as standalone pages if visible
        for special in ("/menu", "/footer"):
            row = await repo.article_by_path(db, special)
            if row and row.get("is_visible"):
                await write_article_index(settings, row, db)
        await db.commit()


async def sync_visibility_to_disk(settings: Settings, path: str, is_visible: bool) -> None:
    if path in ("/menu", "/footer"):
        await regenerate_all_visible_indexes(settings)
    else:
        async with get_connection(settings) as db:
            row = await repo.article_by_path(db, path)
            if not row:
                return
            if is_visible:
                await write_article_index(settings, row, db)
            else:
                await remove_article_index(settings, path)
            await db.commit()
    await write_sitemap(settings)


async def delete_article_storage(settings: Settings, article_path: str) -> None:
    d = storage_article_dir(settings.storage_dir, article_path)
    if d.is_dir():
        await asyncio.to_thread(shutil.rmtree, d, ignore_errors=True)


def ensure_default_favicon(settings: Settings) -> None:
    src = settings.static_dir / "favicon.ico"
    dst = settings.storage_dir / "favicon.ico"
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    if not dst.exists() and src.is_file():
        shutil.copy2(src, dst)
