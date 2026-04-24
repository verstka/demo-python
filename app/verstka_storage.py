"""Verstka AsyncStorageAdapter: media under article path from DB; fonts under /fonts/."""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.config import Settings
from app.database import get_connection
from app import repo
from app.paths import path_to_storage_relative


class CmsVerstkaStorage:
    """Resolve article directory by material_id from SQLite only."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _article_rel_dir(self, material_id: str) -> str:
        async with get_connection(self.settings) as db:
            row = await repo.article_by_material_id(db, material_id)
        if not row:
            raise RuntimeError(f"unknown material_id for storage: {material_id}")
        return path_to_storage_relative(row["path"])

    async def save_media(
        self,
        filename: str,
        temp_path: Path,
        material_id: str,
        metadata: Mapping[str, Any],
    ) -> str:
        del metadata
        rel = await self._article_rel_dir(material_id)
        dest_dir = (self.settings.storage_dir / rel).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        await asyncio.to_thread(shutil.copy2, temp_path, dest)
        base = self.settings.public_base_url.rstrip("/")
        return f"{base}/{rel}/{filename}".replace("\\", "/")

    async def save_font_file(
        self,
        filename: str,
        temp_path: Path,
        material_id: str,
        metadata: Mapping[str, Any],
    ) -> str:
        del material_id, metadata
        dest_dir = (self.settings.storage_dir / "fonts").resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        await asyncio.to_thread(shutil.copy2, temp_path, dest)
        base = self.settings.public_base_url.rstrip("/")
        return f"{base}/fonts/{filename}".replace("\\", "/")

    async def save_fonts_manifest(
        self,
        filename: str,
        temp_path: Path,
        material_id: str,
        metadata: Mapping[str, Any],
    ) -> str:
        return await self.save_font_file(filename, temp_path, material_id, metadata)
