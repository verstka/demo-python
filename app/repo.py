"""Data access for articles and cms_users."""

from __future__ import annotations

import json
import uuid
from typing import Any

import aiosqlite

from app.paths import is_valid_article_path, normalize_article_path


async def list_cms_users(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    cur = await db.execute("SELECT user_email FROM cms_users ORDER BY user_email")
    rows = await cur.fetchall()
    return [{"user_email": r[0]} for r in rows]


async def count_cms_users(db: aiosqlite.Connection) -> int:
    """Return number of rows in cms_users (for bootstrap / empty checks)."""
    cur = await db.execute("SELECT COUNT(*) FROM cms_users")
    row = await cur.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


async def get_cms_user(db: aiosqlite.Connection, user_email: str) -> dict[str, Any] | None:
    cur = await db.execute(
        "SELECT user_email, password_hash FROM cms_users WHERE user_email = ?",
        (user_email,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return {"user_email": row[0], "password_hash": row[1]}


async def insert_cms_user(db: aiosqlite.Connection, user_email: str, password_hash: str) -> None:
    await db.execute(
        "INSERT INTO cms_users (user_email, password_hash) VALUES (?, ?)",
        (user_email, password_hash),
    )


async def delete_cms_user(db: aiosqlite.Connection, user_email: str) -> None:
    await db.execute("DELETE FROM cms_users WHERE user_email = ?", (user_email,))


async def update_cms_user_password(db: aiosqlite.Connection, user_email: str, password_hash: str) -> None:
    await db.execute(
        "UPDATE cms_users SET password_hash = ? WHERE user_email = ?",
        (password_hash, user_email),
    )


async def article_by_path(db: aiosqlite.Connection, path: str) -> dict[str, Any] | None:
    p = normalize_article_path(path)
    cur = await db.execute("SELECT * FROM articles WHERE path = ?", (p,))
    row = await cur.fetchone()
    if not row:
        return None
    return dict(row)


async def article_by_material_id(db: aiosqlite.Connection, material_id: str) -> dict[str, Any] | None:
    cur = await db.execute("SELECT * FROM articles WHERE material_id = ?", (material_id,))
    row = await cur.fetchone()
    if not row:
        return None
    return dict(row)


async def list_articles(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    cur = await db.execute("SELECT * FROM articles ORDER BY path")
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def list_visible_article_paths_for_sitemap(db: aiosqlite.Connection) -> list[str]:
    cur = await db.execute(
        """
        SELECT path FROM articles
        WHERE is_visible = 1
          AND path NOT IN ('/menu', '/footer')
        ORDER BY path
        """
    )
    rows = await cur.fetchall()
    return [r[0] for r in rows]


async def list_visible_articles_for_regen(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    cur = await db.execute(
        """
        SELECT * FROM articles
        WHERE is_visible = 1
          AND path NOT IN ('/menu', '/footer')
        ORDER BY path
        """
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def insert_article(
    db: aiosqlite.Connection,
    *,
    path: str,
    title: str,
    og_title: str | None,
    og_description: str | None,
    og_image_relpath: str | None,
    is_visible: bool = True,
) -> dict[str, Any]:
    p = normalize_article_path(path)
    if not is_valid_article_path(p):
        raise ValueError("invalid or reserved path")
    material_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO articles (
            path, material_id, title, html, vms_json, is_visible,
            og_title, og_description, og_image_relpath
        ) VALUES (?, ?, ?, '', NULL, ?, ?, ?, ?)
        """,
        (
            p,
            material_id,
            title,
            1 if is_visible else 0,
            og_title,
            og_description,
            og_image_relpath,
        ),
    )
    return (await article_by_path(db, p)) or {}


async def update_article_meta(
    db: aiosqlite.Connection,
    path: str,
    *,
    title: str | None = None,
    og_title: str | None = None,
    og_description: str | None = None,
    og_image_relpath: str | None = None,
    is_visible: bool | None = None,
) -> None:
    p = normalize_article_path(path)
    row = await article_by_path(db, p)
    if not row:
        raise LookupError("article not found")
    fields: list[str] = []
    vals: list[Any] = []
    if title is not None:
        fields.append("title = ?")
        vals.append(title)
    if og_title is not None:
        fields.append("og_title = ?")
        vals.append(og_title)
    if og_description is not None:
        fields.append("og_description = ?")
        vals.append(og_description)
    if og_image_relpath is not None:
        fields.append("og_image_relpath = ?")
        vals.append(og_image_relpath)
    if is_visible is not None:
        fields.append("is_visible = ?")
        vals.append(1 if is_visible else 0)
    if not fields:
        return
    fields.append("updated_at = datetime('now')")
    vals.append(p)
    await db.execute(f"UPDATE articles SET {', '.join(fields)} WHERE path = ?", vals)


async def update_article_from_verstka(
    db: aiosqlite.Connection,
    material_id: str,
    *,
    html: str,
    vms_json: str | None,
) -> None:
    await db.execute(
        """
        UPDATE articles SET html = ?, vms_json = ?, updated_at = datetime('now')
        WHERE material_id = ?
        """,
        (html, vms_json, material_id),
    )


async def delete_article(db: aiosqlite.Connection, path: str) -> None:
    p = normalize_article_path(path)
    await db.execute("DELETE FROM articles WHERE path = ?", (p,))


async def cms_user_exists(db: aiosqlite.Connection, user_email: str) -> bool:
    cur = await db.execute(
        "SELECT 1 FROM cms_users WHERE user_email = ? LIMIT 1",
        (user_email,),
    )
    return await cur.fetchone() is not None


def parse_vms_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
