from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

import httpx
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app import repo
from app.config import Settings, get_settings
from app.database import get_connection, init_db
from app.routers import cms


class FakeVerstkaClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.metadata = None

    async def get_editor_url(self, material_id, *, vms_json=None, metadata=None):
        del material_id, vms_json
        self.metadata = metadata
        if self.error:
            raise self.error
        return "https://editor.example/session"


class EditorOpenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.settings = Settings(
            VERSTKA_API_KEY="key",
            VERSTKA_API_SECRET="secret",
            VERSTKA_CALLBACK_URL="https://cms.example.test/verstka/callback",
            VERSTKA_API_URL="https://api-stage.verstka.org/integration",
            PUBLIC_BASE_URL="https://cms.example.test",
            SESSION_SECRET="test-secret",
            DATABASE_URL=f"sqlite+aiosqlite:///{root / 'data.db'}",
            ADMINS="{}",
            storage_dir=root / "storage",
        )
        asyncio.run(self._seed_db())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    async def _seed_db(self) -> None:
        await init_db(self.settings)
        async with get_connection(self.settings) as db:
            await repo.insert_cms_user(
                db,
                "admin@example.test",
                PasswordHasher().hash("password123"),
            )
            await repo.insert_article(
                db,
                path="/hi",
                title="Hello",
                og_title=None,
                og_description=None,
                og_image_relpath=None,
            )
            await db.commit()

    def _client(self, fake_client: FakeVerstkaClient) -> TestClient:
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        app.include_router(cms.router)
        app.state.verstka_client = fake_client
        app.dependency_overrides[get_settings] = lambda: self.settings
        client = TestClient(app, follow_redirects=False)
        response = client.post(
            "/cms/login",
            data={"user_email": "admin@example.test", "password": "password123"},
        )
        self.assertEqual(response.status_code, 303)
        return client

    def test_open_editor_redirects_and_includes_logged_in_email_metadata(self) -> None:
        fake = FakeVerstkaClient()
        client = self._client(fake)

        response = client.get("/cms/articles/open?path=%2Fhi")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "https://editor.example/session")
        self.assertEqual(fake.metadata, {"user_email": "admin@example.test"})

    def test_open_editor_returns_helpful_page_when_api_unreachable(self) -> None:
        error = httpx.ConnectError(
            "could not resolve host",
            request=httpx.Request("POST", "https://api-stage.verstka.org/integration/session/open"),
        )
        client = self._client(FakeVerstkaClient(error=error))

        response = client.get("/cms/articles/open?path=%2Fhi")

        self.assertEqual(response.status_code, 502)
        self.assertIn("Could not reach Verstka API", response.text)
        self.assertIn("https://api-stage.verstka.org/integration", response.text)


if __name__ == "__main__":
    unittest.main()
