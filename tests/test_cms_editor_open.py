from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import httpx

from tests.support import build_cms_test_app, make_test_settings, run_async, seed_admin_and_article


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
        self.settings = make_test_settings(Path(self.tmp.name))
        run_async(seed_admin_and_article(self.settings))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _logged_in_client(self, fake_client: FakeVerstkaClient):
        client = build_cms_test_app(self.settings, verstka_client=fake_client)
        response = client.post(
            "/cms/login",
            data={"user_email": "admin@example.test", "password": "password123"},
        )
        self.assertEqual(response.status_code, 303)
        return client

    def test_open_editor_redirects_and_includes_logged_in_email_metadata(self) -> None:
        fake = FakeVerstkaClient()
        client = self._logged_in_client(fake)

        response = client.get("/cms/articles/open?path=%2Fhi")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "https://editor.example/session")
        self.assertEqual(fake.metadata, {"user_email": "admin@example.test"})

    def test_open_editor_returns_helpful_page_when_api_unreachable(self) -> None:
        error = httpx.ConnectError(
            "could not resolve host",
            request=httpx.Request("POST", "https://api-stage.verstka.org/integration/session/open"),
        )
        client = self._logged_in_client(FakeVerstkaClient(error=error))

        response = client.get("/cms/articles/open?path=%2Fhi")

        self.assertEqual(response.status_code, 502)
        self.assertIn("Could not reach Verstka API", response.text)
        self.assertIn("https://api-stage.verstka.org/integration", response.text)


if __name__ == "__main__":
    unittest.main()
