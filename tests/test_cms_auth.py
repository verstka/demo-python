from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import build_cms_test_app, make_test_settings, run_async, seed_admin_and_article


class CmsAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_test_settings(Path(self.tmp.name))
        run_async(seed_admin_and_article(self.settings))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_unauthenticated_articles_redirects_to_login(self) -> None:
        client = build_cms_test_app(self.settings)

        response = client.get("/cms/articles")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/cms/login")

    def test_unauthenticated_users_redirects_to_login(self) -> None:
        client = build_cms_test_app(self.settings)

        response = client.get("/cms/users")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/cms/login")


if __name__ == "__main__":
    unittest.main()
