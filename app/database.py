"""SQLite schema init and connection helpers."""

from __future__ import annotations
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.config import Settings


def sqlite_file_path(database_url: str) -> Path:
    prefix = "sqlite+aiosqlite:///"
    if database_url.startswith(prefix):
        return Path(database_url.removeprefix(prefix))
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///"))
    return Path(database_url)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cms_users (
    user_email TEXT PRIMARY KEY NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
    path TEXT PRIMARY KEY NOT NULL,
    material_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    html TEXT NOT NULL DEFAULT '',
    vms_json TEXT,
    is_visible INTEGER NOT NULL DEFAULT 1,
    og_title TEXT,
    og_description TEXT,
    og_image_relpath TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_articles_material_id ON articles(material_id);
"""


async def init_db(settings: Settings) -> None:
    path = sqlite_file_path(settings.database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "fonts").mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA_SQL)
        await _migrate_cms_users_username_to_user_email(db)
        await _seed_admins_if_empty(db, settings)
        await db.commit()


async def _migrate_cms_users_username_to_user_email(db: aiosqlite.Connection) -> None:
    """Backwards-compatible migration for older DBs."""
    cur = await db.execute("PRAGMA table_info(cms_users)")
    rows = await cur.fetchall()
    cols = {str(r[1]) for r in rows}  # (cid, name, type, notnull, dflt_value, pk)
    if "user_email" in cols:
        return
    if "username" not in cols:
        return
    await db.execute("ALTER TABLE cms_users RENAME COLUMN username TO user_email")


async def _seed_admins_if_empty(db: aiosqlite.Connection, settings: Settings) -> None:
    cur = await db.execute("SELECT COUNT(*) FROM cms_users")
    row = await cur.fetchone()
    if row and row[0] > 0:
        return
    admins = settings.admins_seed()
    if not admins:
        return
    for user_email, password_hash in admins.items():
        await db.execute(
            "INSERT OR IGNORE INTO cms_users (user_email, password_hash) VALUES (?, ?)",
            (user_email, password_hash),
        )


@asynccontextmanager
async def get_connection(settings: Settings) -> AsyncIterator[aiosqlite.Connection]:
    path = sqlite_file_path(settings.database_url)
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        yield db
