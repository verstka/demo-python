"""Render full HTML page (Jinja2) for static nginx."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings


def _jinja_env(settings: Settings) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(settings.templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_article_page(
    settings: Settings,
    *,
    article: dict[str, Any],
    menu_html: str,
    footer_html: str,
    fonts_css_exists: bool,
) -> str:
    env = _jinja_env(settings)
    tpl = env.get_template("article.html.j2")
    base = settings.public_base_url.rstrip("/")
    og_image = None
    rel = article.get("og_image_relpath")
    if rel:
        p = article["path"].rstrip("/") or article["path"]
        norm = p.lstrip("/")
        og_image = f"{base}/{norm}/{rel}" if not str(rel).startswith("http") else rel
    return tpl.render(
        title=article.get("title") or article["path"],
        body_html=article.get("html") or "",
        menu_html=menu_html,
        footer_html=footer_html,
        og_title=article.get("og_title") or article.get("title") or "",
        og_description=article.get("og_description") or "",
        og_image=og_image,
        fonts_css_exists=fonts_css_exists,
        canonical_url=f"{base}{article['path']}/",
    )


def fonts_css_file_exists(settings: Settings) -> bool:
    p = settings.storage_dir / "fonts" / "fonts.css"
    return p.is_file()
