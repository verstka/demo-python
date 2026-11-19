from __future__ import annotations

import re
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
        self.assertIn('href="/cms/static/cms-login.css?v=editorial-stats-20261111"', response.text)
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
        self.assertIn(
            'href="/cms/static/cms.css?v=path-editor-button-20261119"',
            response.text,
        )
        self.assertIn(
            '<a class="nav-button" href="/cms/articles" aria-label="Articles" '
            'title="Articles" aria-current="page">',
            response.text,
        )
        self.assertIn(
            '<a class="nav-button" href="/cms/users" aria-label="Administrators" '
            'title="Administrators">',
            response.text,
        )
        self.assertIn('<nav class="breadcrumbs" aria-label="Breadcrumbs">', response.text)
        self.assertIn('<a href="/cms/articles">CMS</a>', response.text)
        self.assertIn("admin@example.test", response.text)
        self.assertIn("Hello", response.text)
        self.assertIn("/hi", response.text)
        self.assertIn('data-stat="total">1<', response.text)
        self.assertIn('data-stat="published">1<', response.text)
        self.assertIn('data-stat="hidden">0<', response.text)
        self.assertIn('action="/cms/articles/create"', response.text)
        self.assertIn('action="/cms/articles/visibility"', response.text)
        self.assertIn('action="/cms/articles/og"', response.text)
        self.assertIn('name="title" value="Hello"', response.text)
        self.assertIn('action="/cms/articles/delete"', response.text)
        self.assertIn('/cms/articles/open?path=', response.text)
        self.assertNotIn(">Statistics<", response.text)
        self.assertIn('data-testid="logout-button"', response.text)

    def test_article_path_is_the_only_editor_entry_point_in_the_table_row(self) -> None:
        client = self._logged_in_client()

        response = client.get("/cms/articles")

        self.assertEqual(response.status_code, 200)
        with self.subTest("path opens the editor in a new tab"):
            self.assertIn(
                '<a class="path" href="/cms/articles/open?path=%2Fhi" '
                'target="_blank" rel="noopener noreferrer" '
                'aria-label="Open /hi in the Verstka editor (opens in a new tab)" '
                'title="Open /hi in the Verstka editor">',
                response.text,
            )

        action_menu = response.text.split('<details class="action-menu">', 1)[1].split(
            "</details>", 1
        )[0]
        with self.subTest("editor action is removed from the dropdown"):
            self.assertNotIn("/cms/articles/open?path=", action_menu)
            self.assertNotIn("Open editor", action_menu)

    def test_article_editor_path_has_visible_button_treatment(self) -> None:
        client = self._logged_in_client()

        page_response = client.get("/cms/articles")
        css_response = TestClient(create_app()).get("/cms/static/cms.css")

        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(css_response.status_code, 200)
        path_button = page_response.text.split('<a class="path"', 1)[1].split(
            "</a>", 1
        )[0]
        self.assertNotIn("<svg", path_button)
        self.assertIn("<span>Open /hi</span>", path_button)
        self.assertRegex(
            css_response.text,
            r"\.path\s*\{[^}]*display:\s*inline-flex;[^}]*"
            r"border:\s*0\.5px\s+solid\s+var\(--panel-border\);[^}]*"
            r"background:\s*var\(--control-bg\);",
        )

    def test_article_path_column_keeps_editor_button_room_at_compact_desktop(self) -> None:
        response = self._logged_in_client().get("/cms/articles")

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.text,
            r'<col style="width:27%">\s*'
            r'<col style="width:28%">\s*'
            r'<col style="width:13%">\s*'
            r'<col class="hide-tablet" style="width:16%">\s*'
            r'<col style="width:16%">',
        )

    def test_articles_og_form_updates_title(self) -> None:
        client = self._logged_in_client()

        response = client.post(
            "/cms/articles/og",
            data={
                "path": "/hi",
                "title": "Renamed Hello",
                "og_title": "Social Hello",
                "og_description": "",
            },
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/cms/articles")

        listing = client.get("/cms/articles")
        self.assertEqual(listing.status_code, 200)
        self.assertIn("Renamed Hello", listing.text)
        self.assertIn('name="title" value="Renamed Hello"', listing.text)
        self.assertNotIn(">Hello<", listing.text)

    def test_cms_templates_escape_article_metadata(self) -> None:
        client = self._logged_in_client()
        unsafe_title = "<b>Unsafe title</b>"

        response = client.post(
            "/cms/articles/og",
            data={
                "path": "/hi",
                "title": unsafe_title,
                "og_title": "",
                "og_description": "",
            },
        )

        self.assertEqual(response.status_code, 303)
        listing = client.get("/cms/articles")
        self.assertEqual(listing.status_code, 200)
        self.assertNotIn(unsafe_title, listing.text)
        self.assertIn("&lt;b&gt;Unsafe title&lt;/b&gt;", listing.text)

    def test_articles_page_uses_named_dialogs_for_every_modal_action(self) -> None:
        client = self._logged_in_client()

        response = client.get("/cms/articles")

        self.assertEqual(response.status_code, 200)
        self.assertIn('aria-labelledby="article-create-dialog-title"', response.text)
        self.assertIn('aria-labelledby="article-og-dialog-1-title"', response.text)
        self.assertIn('data-dialog-open="article-delete-dialog-1"', response.text)
        self.assertIn('id="article-delete-dialog-1"', response.text)
        self.assertIn('aria-labelledby="article-delete-dialog-1-title"', response.text)
        self.assertIn('action="/cms/articles/delete"', response.text)
        self.assertIn("everything published under this path", response.text)
        self.assertNotIn("its published files", response.text)
        self.assertNotIn("confirm(", response.text)

    def test_create_article_path_field_has_no_persistent_help_ui(self) -> None:
        client = self._logged_in_client()

        response = client.get("/cms/articles")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="article-create-path"', response.text)
        self.assertIn('name="path"', response.text)
        self.assertNotIn('aria-describedby="article-create-path-help"', response.text)
        self.assertNotIn('class="input-help__trigger"', response.text)
        self.assertNotIn(
            "Start with /, for example /index or /journal/story.",
            response.text,
        )

    def test_users_page_uses_dashboard_and_preserves_user_actions(self) -> None:
        client = self._logged_in_client()

        response = client.get("/cms/users")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-testid="cms-shell"', response.text)
        self.assertIn(
            '<a class="nav-button" href="/cms/articles" aria-label="Articles" '
            'title="Articles">',
            response.text,
        )
        self.assertIn(
            '<a class="nav-button" href="/cms/users" aria-label="Administrators" '
            'title="Administrators" aria-current="page">',
            response.text,
        )
        self.assertIn("Administrators", response.text)
        self.assertIn("admin@example.test", response.text)
        self.assertIn('action="/cms/users/create"', response.text)
        self.assertIn('action="/cms/users/password"', response.text)
        self.assertIn('action="/cms/users/delete"', response.text)

    def test_users_page_uses_named_dialogs_for_every_modal_action(self) -> None:
        client = self._logged_in_client()

        response = client.get("/cms/users")

        self.assertEqual(response.status_code, 200)
        self.assertIn('aria-labelledby="user-create-dialog-title"', response.text)
        self.assertIn('aria-labelledby="password-dialog-1-title"', response.text)
        self.assertIn('data-dialog-open="user-delete-dialog-1"', response.text)
        self.assertIn('id="user-delete-dialog-1"', response.text)
        self.assertIn('aria-labelledby="user-delete-dialog-1-title"', response.text)
        self.assertIn('action="/cms/users/delete"', response.text)
        self.assertIn("Existing CMS sessions remain active", response.text)
        self.assertNotIn("Access will be revoked", response.text)
        self.assertNotIn("confirm(", response.text)

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

    def test_dialogs_restore_focus_to_a_visible_action_menu_control(self) -> None:
        client = TestClient(create_app())

        response = client.get("/cms/static/cms.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("const dialogReturnFocus = new WeakMap()", response.text)
        self.assertIn("const actionMenu = trigger.closest('.action-menu')", response.text)
        self.assertIn("actionMenu.removeAttribute('open')", response.text)
        self.assertIn("dialog.addEventListener('close'", response.text)
        self.assertIn("returnTarget.focus()", response.text)

    def test_login_submit_keeps_visible_focus_in_forced_colors(self) -> None:
        client = TestClient(create_app())

        response = client.get("/cms/static/cms-login.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn("@media (forced-colors: active)", response.text)
        self.assertRegex(
            response.text,
            r"\.input:focus,\s*\.submit:focus-visible\s*\{[^}]*"
            r"outline:\s*2px\s+solid\s+ButtonText",
        )

    def test_cms_controls_keep_visible_focus_in_forced_colors(self) -> None:
        response = TestClient(create_app()).get("/cms/static/cms.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn("@media (forced-colors: active)", response.text)
        forced_color_styles = response.text.split(
            "@media (forced-colors: active)", 1
        )[1]
        self.assertRegex(
            forced_color_styles,
            r"\.button:focus-visible,\s*"
            r"\.icon-button:focus-visible,\s*"
            r"\.action-button:focus-visible,\s*"
            r"\.menu-item:focus-visible:not\(:disabled\),\s*"
            r"\.nav-button:focus-visible\s*\{[^}]*"
            r"outline:\s*2px\s+solid\s+ButtonText",
        )

    def test_cms_component_outlines_use_half_pixel_hairlines(self) -> None:
        client = TestClient(create_app())
        expected_border_counts = {"cms.css": 25, "cms-login.css": 4}

        for stylesheet in ("cms.css", "cms-login.css"):
            with self.subTest(stylesheet=stylesheet):
                response = client.get(f"/cms/static/{stylesheet}")

                self.assertEqual(response.status_code, 200)
                hairline_borders = re.findall(
                    r"\bborder(?:-(?:top|right|bottom|left))?:\s*0\.5px\s+solid\b",
                    response.text,
                )
                self.assertEqual(len(hairline_borders), expected_border_counts[stylesheet])
                self.assertNotRegex(
                    response.text,
                    r"\bborder(?:-(?:top|right|bottom|left))?:\s*1px\s+solid\b",
                )
                self.assertNotIn("box-shadow: inset 0 0 0 1px", response.text)

        self.assertIn(
            "box-shadow: inset 0 0 0 0.5px",
            client.get("/cms/static/cms-login.css").text,
        )

    def test_tablet_navigation_buttons_use_compact_corners(self) -> None:
        response = TestClient(create_app()).get("/cms/static/cms.css")

        self.assertEqual(response.status_code, 200)
        tablet_query = "@media (min-width: 561px) and (max-width: 780px) {"
        self.assertIn(tablet_query, response.text)
        tablet_styles = response.text.split(tablet_query, 1)[1].split(
            "@media (max-width: 560px) {", 1
        )[0]
        self.assertRegex(
            tablet_styles,
            r"\.nav-button\s*\{[^}]*border-radius:\s*4px;",
        )

    def test_mobile_workspace_rounds_the_navigation_boundary(self) -> None:
        response = TestClient(create_app()).get("/cms/static/cms.css")

        self.assertEqual(response.status_code, 200)
        mobile_styles = response.text.split("@media (max-width: 560px) {", 1)[1]
        self.assertRegex(
            mobile_styles,
            r"\.workspace\s*\{[^}]*border-radius:\s*16px 16px 0 0;",
        )


if __name__ == "__main__":
    unittest.main()
