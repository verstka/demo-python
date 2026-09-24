from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.support import build_cms_test_app, make_test_settings, run_async, seed_admin_and_article


class CmsLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = make_test_settings(Path(self.tmp.name))
        run_async(seed_admin_and_article(self.settings))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _logged_in_client(self):
        client = build_cms_test_app(self.settings)
        response = client.post(
            "/cms/login",
            data={"user_email": "admin@example.test", "password": "password123"},
        )
        self.assertEqual(response.status_code, 303)
        return client

    def test_login_page_uses_new_layout_and_preserves_auth_form(self) -> None:
        client = build_cms_test_app(self.settings)

        response = client.get("/cms/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-testid="login-layout"', response.text)
        self.assertIn('href="/cms/static/cms-login.css?v=login-stats-cards-20260923"', response.text)
        self.assertIn('src="/cms/static/cms.js?v=login-stats-duration-2000-20260923"', response.text)
        self.assertIn('action="/cms/login"', response.text)
        self.assertIn('name="user_email"', response.text)
        self.assertIn('name="password"', response.text)
        self.assertIn("Welcome back.", response.text)
        self.assertIn('data-testid="login-stats"', response.text)
        self.assertIn("Get started with us", response.text)
        self.assertNotIn("Join teams publishing articles, managing access, and connecting editorial brands in one quiet workspace.", response.text)
        self.assertIn('data-count-target="231"', response.text)
        self.assertIn("Users signed in", response.text)
        self.assertIn('data-count-target="2147"', response.text)
        self.assertIn('data-count-format="comma"', response.text)
        self.assertIn("Articles created", response.text)
        self.assertIn('data-count-target="37"', response.text)
        self.assertIn("Journals connected", response.text)
        self.assertNotIn("18K+", response.text)
        self.assertNotIn("72K+", response.text)
        self.assertNotIn("340+", response.text)
        self.assertNotIn("stat-card--featured", response.text)
        self.assertNotIn("Get started with Verstka", response.text)
        self.assertNotIn("step", response.text)
        self.assertNotIn("slider-dots", response.text)
        self.assertNotIn("slider-arrows", response.text)
        self.assertNotIn("Verstka editorial team", response.text)

    def test_articles_page_uses_dashboard_and_preserves_article_actions(self) -> None:
        client = self._logged_in_client()

        response = client.get("/cms/articles")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-testid="cms-shell"', response.text)
        self.assertIn('href="/cms/static/cms.css"', response.text)
        self.assertIn('aria-current="page"', response.text)
        self.assertIn("admin@example.test", response.text)
        self.assertIn("Hello", response.text)
        self.assertIn("/hi", response.text)
        self.assertIn('data-stat="total">1<', response.text)
        self.assertIn('data-stat="published">1<', response.text)
        self.assertIn('data-stat="hidden">0<', response.text)
        self.assertIn('action="/cms/articles/create"', response.text)
        self.assertIn('action="/cms/articles/visibility"', response.text)
        self.assertIn('action="/cms/articles/og"', response.text)
        self.assertIn('action="/cms/articles/delete"', response.text)
        self.assertIn('/cms/articles/open?path=', response.text)
        self.assertNotIn(">Statistics<", response.text)
        self.assertIn('data-testid="logout-button"', response.text)

    def test_users_page_uses_dashboard_and_preserves_user_actions(self) -> None:
        client = self._logged_in_client()

        response = client.get("/cms/users")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-testid="cms-shell"', response.text)
        self.assertIn("Administrators", response.text)
        self.assertIn("admin@example.test", response.text)
        self.assertIn('action="/cms/users/create"', response.text)
        self.assertIn('action="/cms/users/password"', response.text)
        self.assertIn('action="/cms/users/delete"', response.text)

    def test_cms_static_assets_are_served_by_the_application(self) -> None:
        client = TestClient(create_app())

        css_response = client.get("/cms/static/cms.css")
        login_css_response = client.get("/cms/static/cms-login.css")
        js_response = client.get("/cms/static/cms.js")
        image_response = client.get("/cms/static/login-editorial.png")
        favicon_response = client.get("/cms/static/favicon.svg")

        self.assertEqual(css_response.status_code, 200)
        self.assertIn("text/css", css_response.headers["content-type"])
        self.assertEqual(login_css_response.status_code, 200)
        self.assertIn("text/css", login_css_response.headers["content-type"])
        self.assertIn(".stat-card::before", login_css_response.text)
        self.assertIn(".stat-card::after", login_css_response.text)
        self.assertIn(".stat-card__label::before", login_css_response.text)
        self.assertIn("font-variant-numeric: tabular-nums", login_css_response.text)
        self.assertNotIn("stat-card--featured", login_css_response.text)
        self.assertNotIn("color: #111", login_css_response.text)
        self.assertEqual(js_response.status_code, 200)
        self.assertIn("javascript", js_response.headers["content-type"])
        self.assertIn("data-count-target", js_response.text)
        self.assertIn("countStartDelay = 0", js_response.text)
        self.assertIn("duration = 2000", js_response.text)
        self.assertIn("window.setTimeout(startCounter, countStartDelay)", js_response.text)
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.headers["content-type"], "image/png")
        self.assertEqual(favicon_response.status_code, 200)
        self.assertIn("image/svg", favicon_response.headers["content-type"])
        self.assertIn('fill="#2d2d2d"', favicon_response.text)


if __name__ == "__main__":
    unittest.main()
