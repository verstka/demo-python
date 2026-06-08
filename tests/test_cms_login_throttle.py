from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import login_guard
from tests.support import build_cms_test_app, make_test_settings, run_async, seed_admin_and_article


class CmsLoginThrottleTests(unittest.TestCase):
    def setUp(self) -> None:
        login_guard.reset_login_failures()
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_test_settings(
            Path(self.tmp.name),
            CMS_LOGIN_MAX_FAILURES=3,
            CMS_LOGIN_WINDOW_SECONDS=60,
        )
        run_async(seed_admin_and_article(self.settings))
        self.client = build_cms_test_app(self.settings)

    def tearDown(self) -> None:
        login_guard.reset_login_failures()
        self.tmp.cleanup()

    def _login(
        self,
        *,
        email: str = "admin@example.test",
        password: str = "wrong",
    ):
        return self.client.post(
            "/cms/login",
            data={"user_email": email, "password": password},
        )

    def test_blocks_user_across_ips(self) -> None:
        for _ in range(3):
            response = self._login(password="wrong")
            self.assertEqual(response.status_code, 401)

        blocked = self._login(password="wrong")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Too many failed attempts", blocked.text)

    def test_successful_login_clears_failures(self) -> None:
        for _ in range(2):
            self.assertEqual(self._login(password="wrong").status_code, 401)

        ok = self._login(password="password123")
        self.assertEqual(ok.status_code, 303)
        self.assertEqual(ok.headers["location"], "/cms/articles")

        again = self._login(password="wrong")
        self.assertEqual(again.status_code, 401)


if __name__ == "__main__":
    unittest.main()
