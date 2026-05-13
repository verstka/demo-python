from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.paths import is_valid_article_path
from app.services import publish, render


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
        root = Path(self.tmp.name)
        static_dir = root / "static"
        (static_dir / "verstka-viewer").mkdir(parents=True)
        (static_dir / "verstka-viewer" / "index.js").write_text(
            "export async function initArticles(){ return [] }\n",
            encoding="utf-8",
        )
        self.settings = Settings(
            VERSTKA_API_KEY="key",
            VERSTKA_API_SECRET="secret",
            VERSTKA_CALLBACK_URL="https://cms.example.test/verstka/callback",
            VERSTKA_API_URL="https://api-stage.verstka.org/integration",
            VERSTKA_VIEWER_DEV="1",
            PUBLIC_BASE_URL="https://cms.example.test",
            SESSION_SECRET="test-secret",
            DATABASE_URL=f"sqlite+aiosqlite:///{root / 'data.db'}",
            ADMINS="{}",
            storage_dir=root / "storage",
            static_dir=static_dir,
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
        self.assertIn('import { initArticles } from "/verstka-viewer/index.js";', html)
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

    def test_viewer_asset_is_copied_to_storage(self) -> None:
        publish.ensure_viewer_asset(self.settings)

        copied = self.settings.storage_dir / "verstka-viewer" / "index.js"
        self.assertTrue(copied.is_file())
        self.assertIn("initArticles", copied.read_text(encoding="utf-8"))

    def test_viewer_asset_path_is_reserved_for_articles(self) -> None:
        self.assertFalse(is_valid_article_path("/verstka-viewer"))
        self.assertFalse(is_valid_article_path("/verstka-viewer/index"))


if __name__ == "__main__":
    unittest.main()
