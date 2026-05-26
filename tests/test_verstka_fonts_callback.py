from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from verstka_sdk import AsyncVerstkaClient, VerstkaConfig
from verstka_sdk.integrations.fastapi import build_callback_router, install_exception_handlers
from verstka_sdk.signatures import sign_material

from app.config import Settings
from app.database import init_db
from app.verstka_handlers import build_verstka_hooks
from app.verstka_storage import CmsVerstkaStorage


class FontsCallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.settings = Settings(
            VERSTKA_API_KEY="key",
            VERSTKA_API_SECRET="secret",
            VERSTKA_CALLBACK_URL="https://cms.example.test/verstka/callback",
            VERSTKA_API_URL="https://api-stage.verstka.org/integration",
            PUBLIC_BASE_URL="https://cms.example.test",
            SESSION_SECRET="test-secret",
            DATABASE_URL=f"sqlite+aiosqlite:///{self.root / 'data.db'}",
            ADMINS="{}",
            storage_dir=self.root / "storage",
        )
        asyncio.run(init_db(self.settings))
        self.zip_path = self.root / "fonts.zip"
        with zipfile.ZipFile(self.zip_path, "w") as zf:
            zf.writestr("vms_fonts/Inter.woff", b"woff-data")
            zf.writestr("vms_fonts/Inter.woff2", b"woff2-data")
            zf.writestr(
                "vms_fonts.css",
                "@font-face{src:url(dummy-Inter.woff2) format('woff2'),"
                "url(dummy-Inter.woff) format('woff');}",
            )
            zf.writestr("vms_fonts.json", '{"families":["Inter"]}')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _client(self) -> TestClient:
        client = AsyncVerstkaClient(
            VerstkaConfig(
                api_key=self.settings.verstka_api_key,
                api_secret=self.settings.verstka_api_secret,
                callback_url=self.settings.verstka_callback_url,
                api_url=self.settings.verstka_api_url,
                debug=True,
            )
        )
        storage = CmsVerstkaStorage(self.settings)
        pre_c, pre_f, fin_c, fin_f = build_verstka_hooks(self.settings)
        app = FastAPI()
        install_exception_handlers(app)
        app.include_router(
            build_callback_router(
                client,
                storage=storage,
                on_content_finalize=fin_c,
                on_fonts_finalize=fin_f,
                on_content_pre_save=pre_c,
                on_fonts_pre_save=pre_f,
            )
        )
        return TestClient(app)

    def test_site_fonts_callback_without_user_metadata_saves_font_files(self) -> None:
        material_id = "site-fonts"
        content_url = "https://content.example.test/fonts.zip"
        payload = {
            "event": "site_fonts_updated",
            "material_id": material_id,
            "content_url": content_url,
            "fonts": {
                "css": {"id": "vms_fonts.css"},
                "list": [
                    {
                        "family": "Inter",
                        "variants": [
                            {
                                "files": {
                                    "woff": {"id": "Inter.woff"},
                                    "woff2": {"id": "Inter.woff2"},
                                }
                            }
                        ],
                    }
                ],
            },
        }
        signature = sign_material(material_id, content_url, self.settings.verstka_api_secret)

        async def fake_download_zip(url, dest_path, *, max_size, timeout, headers=None):
            del url, max_size, timeout, headers
            shutil.copy2(self.zip_path, dest_path)

        with patch("verstka_sdk.callbacks.download_zip_async", fake_download_zip):
            response = self._client().post(
                "/verstka/callback",
                json=payload,
                headers={"X-Verstka-Signature": signature},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["rc"], 1, body)

        fonts_dir = self.settings.storage_dir / "fonts"
        self.assertEqual((fonts_dir / "Inter.woff").read_bytes(), b"woff-data")
        self.assertEqual((fonts_dir / "Inter.woff2").read_bytes(), b"woff2-data")
        self.assertTrue((fonts_dir / "vms_fonts.json").is_file())
        self.assertTrue((fonts_dir / "vms_fonts.css").is_file())
        self.assertTrue((fonts_dir / "fonts.css").is_file())
        self.assertIn("https://cms.example.test/fonts/Inter.woff2", (fonts_dir / "fonts.css").read_text())


if __name__ == "__main__":
    unittest.main()
