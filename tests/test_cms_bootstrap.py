from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from argon2 import PasswordHasher

from app import repo
from app.database import get_connection, init_db
from tests.support import build_cms_test_app, make_test_settings, run_async


class CmsBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_test_settings(Path(self.tmp.name))
        run_async(init_db(self.settings))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    async def _user_and_count(self, user_email: str):
        async with get_connection(self.settings) as db:
            return await repo.get_cms_user(db, user_email), await repo.count_cms_users(db)

    def test_first_login_creates_admin_in_sqlite_and_signs_in(self) -> None:
        client = build_cms_test_app(self.settings)

        response = client.post(
            "/cms/login",
            data={"user_email": "admin@example.test", "password": "password123"},
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/cms/articles")
        row, count = run_async(self._user_and_count("admin@example.test"))
        self.assertEqual(count, 1)
        self.assertIsNotNone(row)
        PasswordHasher().verify(row["password_hash"], "password123")

        articles_response = client.get("/cms/articles")
        self.assertEqual(articles_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
