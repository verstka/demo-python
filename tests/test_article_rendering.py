from __future__ import annotations

import tempfile
import unittest

from app.config import Settings
from app.services import render


CURRENT_ARTICLE_HTML = (
    '<article class="vrstk-article" data-vrstk-article="">'
    '<style data-vrstk-critical-css="">.vrstk-article{display:block}</style>'
    '<div data-vrstk-article-app=""><div class="vrstk-frame">Hello from Verstka</div></div>'
    '<script type="application/json" data-vrstk-article-payload="">{"containers":[]}</script>'
    "</article>"
)


class ArticleRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.settings = Settings(
            VERSTKA_API_KEY="key",
            VERSTKA_API_SECRET="secret",
            VERSTKA_CALLBACK_URL="https://cms.example.test/verstka/callback",
            VERSTKA_API_URL="https://api-stage.verstka.org/integration",
            VERSTKA_VIEWER_SCRIPT_URL="https://cdn.jsdelivr.net/npm/verstka-viewer@latest/dist/index.js",
            VERSTKA_VIEWER_DEV="1",
            PUBLIC_BASE_URL="https://cms.example.test",
            SESSION_SECRET="test-secret",
            DATABASE_URL=f"sqlite+aiosqlite:///{root}/data.db",
            ADMINS="{}",
            storage_dir=f"{root}/storage",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_current_verstka_html_is_preserved_and_bootstrapped(self) -> None:
        html = render.render_article_page(
            self.settings,
            article={
                "path": "/hi",
                "title": "Hello",
                "html": CURRENT_ARTICLE_HTML,
                "og_title": None,
                "og_description": None,
                "og_image_relpath": None,
            },
            menu_html="",
            footer_html="",
            fonts_css_exists=False,
        )

        self.assertIn(CURRENT_ARTICLE_HTML, html)
        self.assertIn("https://cdn.jsdelivr.net/npm/verstka-viewer@latest/dist/index.js", html)
        self.assertIn('type="module" src="https://cdn.jsdelivr.net/npm/verstka-viewer@latest/dist/index.js"', html)
        self.assertIn("import(", html)
        self.assertIn('"dev": true', html)
        self.assertNotIn("go.verstka.org/api.js", html)
        self.assertNotIn('class="verstka-article"', html)

    def test_legacy_html_is_rendered_without_viewer_bootstrap(self) -> None:
        html = render.render_article_page(
            self.settings,
            article={
                "path": "/legacy",
                "title": "Legacy",
                "html": "<p>Legacy body</p>",
                "og_title": None,
                "og_description": None,
                "og_image_relpath": None,
            },
            menu_html="",
            footer_html="",
            fonts_css_exists=False,
        )

        self.assertIn('class="verstka-legacy-article"', html)
        self.assertIn("<p>Legacy body</p>", html)
        self.assertNotIn("initArticles", html)


if __name__ == "__main__":
    unittest.main()
