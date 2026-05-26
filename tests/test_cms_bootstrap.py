from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app import repo
from app.config import Settings, get_settings
from app.database import get_connection, init_db
from app.routers import cms


class CmsBootstrapTests(unittest.TestCase):
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
            storage_dir=root / "storage",
        )
        asyncio.run(init_db(self.settings))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _client(self) -> TestClient:
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        app.include_router(cms.router)
        app.dependency_overrides[get_settings] = lambda: self.settings
        return TestClient(app, follow_redirects=False)

    async def _user_and_count(self, user_email: str):
        async with get_connection(self.settings) as db:
            return await repo.get_cms_user(db, user_email), await repo.count_cms_users(db)

    def test_first_login_creates_admin_in_sqlite_and_signs_in(self) -> None:
        client = self._client()

        response = client.post(
            "/cms/login",
            data={"user_email": "admin@example.test", "password": "password123"},
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/cms/articles")
        row, count = asyncio.run(self._user_and_count("admin@example.test"))
        self.assertEqual(count, 1)
        self.assertIsNotNone(row)
        PasswordHasher().verify(row["password_hash"], "password123")

        articles_response = client.get("/cms/articles")
        self.assertEqual(articles_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
