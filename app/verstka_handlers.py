"""Verstka callback hooks (pre-save + finalize)."""

from __future__ import annotations

import asyncio
import json
import shutil
from verstka_sdk import (
    ContentFinalizeContext,
    ContentFinalizeResult,
    ContentPreSaveContext,
    FontsFinalizeContext,
    FontsFinalizeResult,
    FontsPreSaveContext,
    PreSaveDecision,
)

from app.config import Settings
from app.database import get_connection
from app import repo
from app.services.publish import (
    regenerate_all_visible_indexes,
    remove_article_index,
    write_article_index,
    write_sitemap,
)

_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def build_verstka_hooks(settings: Settings):
    async def on_content_pre_save(ctx: ContentPreSaveContext) -> PreSaveDecision:
        email = str(ctx.metadata.get("user_email") or "").strip()
        if not email or not _EMAIL_RE.fullmatch(email):
            return PreSaveDecision(allow=False, reason="user_email required")
        async with get_connection(settings) as db:
            if not await repo.cms_user_exists(db, email):
                return PreSaveDecision(allow=False, reason="user not in cms_users")
            if not await repo.article_by_material_id(db, ctx.material_id):
                return PreSaveDecision(allow=False, reason="unknown material")
        return PreSaveDecision(allow=True)

    async def on_fonts_pre_save(ctx: FontsPreSaveContext) -> PreSaveDecision:
        email = str(ctx.metadata.get("user_email") or "").strip()
        if not email or not _EMAIL_RE.fullmatch(email):
            return PreSaveDecision(allow=False, reason="user_email required")
        async with get_connection(settings) as db:
            if not await repo.cms_user_exists(db, email):
                return PreSaveDecision(allow=False, reason="user not in cms_users")
        return PreSaveDecision(allow=True)

    async def on_content_finalize(ctx: ContentFinalizeContext) -> ContentFinalizeResult:
        html = ctx.vms_html or ""
        vms_json_str = (
            json.dumps(ctx.vms_json, ensure_ascii=False) if ctx.vms_json is not None else None
        )
        async with get_connection(settings) as db:
            await repo.update_article_from_verstka(
                db, ctx.material_id, html=html, vms_json=vms_json_str
            )
            row = await repo.article_by_material_id(db, ctx.material_id)
            await db.commit()
        if not row:
            await write_sitemap(settings)
            return ContentFinalizeResult(success=True, vms_json=ctx.vms_json)
        path = row["path"]
        is_menu_footer = path in ("/menu", "/footer")
        visible = bool(row.get("is_visible"))
        if is_menu_footer and visible:
            await regenerate_all_visible_indexes(settings)
        elif visible:
            async with get_connection(settings) as db2:
                await write_article_index(settings, row, db2)
                await db2.commit()
        elif not visible:
            await remove_article_index(settings, path)
        await write_sitemap(settings)
        return ContentFinalizeResult(success=True, vms_json=ctx.vms_json)

    async def on_fonts_finalize(ctx: FontsFinalizeContext) -> FontsFinalizeResult:
        del ctx
        src = settings.storage_dir / "fonts" / "vms_fonts.css"
        dst = settings.storage_dir / "fonts" / "fonts.css"
        if src.is_file():
            await asyncio.to_thread(shutil.copy2, src, dst)
        await regenerate_all_visible_indexes(settings)
        await write_sitemap(settings)
        return FontsFinalizeResult(success=True)

    return on_content_pre_save, on_fonts_pre_save, on_content_finalize, on_fonts_finalize
