import os
import unittest
from unittest.mock import patch

os.environ.setdefault("FLASK_SECRET_KEY", "public-page-test-key")

from app import app, PUBLIC_PAGES, MAX_CONTENT_CHARS, MAX_GENERATED_PAGES


class PublicPagesTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_public_pages_are_accessible_without_session(self):
        for page, title in PUBLIC_PAGES.items():
            with self.subTest(page=page):
                response = self.client.get(f"/info/{page}")
                self.assertEqual(response.status_code, 200)
                text = response.get_data(as_text=True)
                self.assertIn(f"<h1>{title}</h1>", text)
                self.assertIn('name="viewport"', text)
                for target in PUBLIC_PAGES:
                    self.assertIn(f'href="/info/{target}"', text)
                self.assertNotIn("Set-Cookie", response.headers)
                self.assertNotIn("adsbygoogle", text)

    def test_unknown_pages_are_not_template_paths(self):
        for path in ("/info/unknown", "/info/index.html", "/info/../app.py"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_policy_discloses_current_limitations(self):
        text = self.client.get("/info/privacy").get_data(as_text=True)
        for phrase in ("没有账号级访问控制", "固定期限自动删除", "sessionStorage", "不是加密存储", "不会删除服务器已有输出"):
            self.assertIn(phrase, text)

    def test_documentation_uses_runtime_limits(self):
        for page in ("guide", "terms"):
            text = self.client.get(f"/info/{page}").get_data(as_text=True)
            self.assertIn(str(MAX_CONTENT_CHARS), text)
            self.assertIn(str(MAX_GENERATED_PAGES), text)

    def test_home_and_result_keep_core_controls(self):
        with patch("app._image_urls_by_prefix", return_value=[]):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("会议资料排版台", text)
        self.assertIn('id="generateForm"', text)
        self.assertIn('href="/info/privacy"', text)
        with self.client.session_transaction() as session:
            session["last_pdf_filename"] = "test.pdf"
        with patch("app._image_urls_by_prefix", return_value=["/output/test.jpg"]):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        for control in ("downloadPdfBtn", "downloadZipBtn", "regenerateVariantBtn", "resetFormLink"):
            self.assertIn(f'id="{control}"', text)


if __name__ == "__main__":
    unittest.main()
