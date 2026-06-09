from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services import render
from tests.support import DEFAULT_VIEWER_SCRIPT_URL, make_test_settings


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
        self.settings = make_test_settings(
            Path(self.tmp.name),
            VERSTKA_VIEWER_SCRIPT_URL=DEFAULT_VIEWER_SCRIPT_URL,
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
        self.assertIn(json.dumps(DEFAULT_VIEWER_SCRIPT_URL), html)
        self.assertIn("Verstka.initArticles(document)", html)
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
        self.assertNotIn("Verstka.initArticles", html)


if __name__ == "__main__":
    unittest.main()
