"""Render full HTML page (Jinja2) for static nginx."""

from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings

VIEWER_SCRIPT_URL = "/verstka-viewer/index.js"


def _jinja_env(settings: Settings) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(settings.templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def is_current_verstka_article_html(html: str) -> bool:
    return "data-vrstk-article" in html and "data-vrstk-article-payload" in html


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
    body_html = article.get("html") or ""
    viewer_bootstrap_enabled = any(
        is_current_verstka_article_html(html) for html in (body_html, menu_html, footer_html)
    )
    return tpl.render(
        title=article.get("title") or article["path"],
        article_html=body_html,
        article_is_current_verstka_html=is_current_verstka_article_html(body_html),
        menu_html=menu_html,
        footer_html=footer_html,
        og_title=article.get("og_title") or article.get("title") or "",
        og_description=article.get("og_description") or "",
        og_image=og_image,
        fonts_css_exists=fonts_css_exists,
        canonical_url=f"{base}{article['path']}/",
        viewer_bootstrap_enabled=viewer_bootstrap_enabled,
        viewer_script_url=VIEWER_SCRIPT_URL,
        viewer_options_json=json.dumps({"dev": True} if settings.verstka_viewer_dev else {}),
    )


def fonts_css_file_exists(settings: Settings) -> bool:
    p = settings.storage_dir / "fonts" / "fonts.css"
    return p.is_file()
