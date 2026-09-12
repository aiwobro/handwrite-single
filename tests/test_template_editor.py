import base64
import copy
import io
import json
import os
from pathlib import Path
import random
import tempfile
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from flask import Flask
from PIL import Image, ImageChops, ImageFont
import yaml

from handwrite import HandWriter, validate_config
from template_editor import editor, parse_template, _login_attempts, MAX_REQUEST

ROOT = Path(__file__).resolve().parents[1]


def sample():
    out = io.BytesIO()
    Image.new("RGB", (500, 700), "white").save(out, "PNG")
    return {"id": "test_paper", "display_name": "测试纸张", "sides": {"front": {
        "image": "data:image/png;base64," + base64.b64encode(out.getvalue()).decode(),
        "body": {"x": 40, "y": 250, "width": 420, "height": 400},
        "font_size": 24, "line_spacing": 40,
        "meta": {"chairperson": {"x": 120, "y": 100, "width": 170, "height": 30}}
    }}}


class TemplateEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "fonts").symlink_to(ROOT / "fonts", target_is_directory=True)
        self.password = "a-test-admin-password-123456"
        self.env = patch.dict(os.environ, {"TEMPLATE_ADMIN_PASSWORD": self.password})
        self.env.start()
        _login_attempts.clear()
        self.app = Flask(__name__, template_folder=str(ROOT / "templates"))
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret", TEMPLATE_PROJECT_DIR=str(self.root))
        self.app.register_blueprint(editor)
        self.client = self.app.test_client()
        self.data = sample()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def token(self):
        self.client.get("/admin/templates/")
        with self.client.session_transaction() as session:
            return session["template_csrf"]

    def post(self, endpoint, data=None, token=None):
        return self.client.post("/admin/templates/" + endpoint, json=self.data if data is None else data,
                                headers={"X-CSRF-Token": token or self.token()})

    def login(self):
        response = self.post("login", {"password": self.password})
        self.assertEqual(response.status_code, 200)

    def test_disabled_without_strong_password(self):
        for password in ("", "short"):
            with patch.dict(os.environ, {"TEMPLATE_ADMIN_PASSWORD": password}):
                self.assertEqual(self.client.get("/admin/templates/").status_code, 404)
                self.assertEqual(self.client.post("/admin/templates/save").status_code, 404)

    def test_login_csrf_and_private_headers(self):
        page = self.client.get("/admin/templates/")
        self.assertIn(b"loginForm", page.data)
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertEqual(page.headers["X-Frame-Options"], "DENY")
        self.assertEqual(self.client.post("/admin/templates/login", json={"password": self.password}).status_code, 403)
        self.assertEqual(self.post("login", {"password": "wrong"}).status_code, 401)
        old_token = self.token()
        self.login()
        self.assertNotEqual(old_token, self.token())
        self.assertIn(b'id="canvas"', self.client.get("/admin/templates/").data)
        self.assertEqual(self.post("export", token=old_token).status_code, 403)
        self.assertEqual(self.post("logout", {}).status_code, 200)
        self.assertEqual(self.post("export").status_code, 401)

    def test_endpoints_require_login(self):
        for endpoint in ("save", "preview", "export", "logout"):
            self.assertEqual(self.post(endpoint).status_code, 401)
        self.assertFalse((self.root / "papers").exists())

    def test_expired_and_rotated_password_sessions(self):
        self.login()
        with self.client.session_transaction() as session:
            session["template_admin_until"] = time.time() - 1
        self.assertEqual(self.post("export").status_code, 401)
        self.login()
        with patch.dict(os.environ, {"TEMPLATE_ADMIN_PASSWORD": "another-strong-password"}):
            self.assertEqual(self.post("export").status_code, 401)

    def test_login_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.post("login", {"password": "bad"}).status_code, 401)
        self.assertEqual(self.post("login", {"password": self.password}).status_code, 429)

    def test_body_mapping_and_single_side(self):
        _, preset, assets = parse_template(self.data)
        front = preset["front"]
        self.assertEqual(front["start_y"], 250)
        self.assertEqual(front["left_margin"], 40)
        self.assertEqual(front["right_margin"], 40)
        self.assertEqual(front["bottom_margin"], 50)
        self.assertEqual(front["coordinate_mode"], "visual")
        self.assertEqual(preset["back"]["bg_file"], front["bg_file"])
        self.assertEqual(preset["back"]["meta_position"], {})
        self.assertEqual(set(assets), {"front.png"})

    def test_two_sides(self):
        self.data["sides"]["back"] = copy.deepcopy(self.data["sides"]["front"])
        self.data["sides"]["back"]["meta"] = {}
        _, preset, assets = parse_template(self.data)
        self.assertEqual(set(assets), {"front.png", "back.png"})
        self.assertTrue(preset["back"]["bg_file"].endswith("back.png"))
        self.login()
        self.assertEqual(self.post("preview?side=back").status_code, 200)

    def test_invalid_layouts(self):
        invalid = []
        for bad_id in ("../escape", "Default", "a/b", "", 123):
            item = sample(); item["id"] = bad_id; invalid.append(item)
        for key, value in (("x", -1), ("y", 701), ("width", 600), ("height", 0), ("x", True), ("width", 1.5)):
            item = sample(); item["sides"]["front"]["body"][key] = value; invalid.append(item)
        for key, value in (("font_size", 501), ("line_spacing", 0), ("image", "data:image/png;base64,@@@@"), ("meta", {"unknown": {}})):
            item = sample(); item["sides"]["front"][key] = value; invalid.append(item)
        item = sample(); item["sides"]["back"] = copy.deepcopy(item["sides"]["front"]); invalid.append(item)
        invalid.extend([None, [], {"id": "ok", "display_name": "name", "sides": {}}])
        for item in invalid:
            with self.subTest(item=str(item)[:100]):
                with self.assertRaises(ValueError):
                    parse_template(item)

    def test_validation_returns_json(self):
        self.login()
        self.data["sides"]["front"]["body"]["width"] = 9999
        response = self.post("save")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json)
        self.assertFalse((self.root / "papers").exists())

    def test_image_pixel_limit(self):
        with patch("template_editor.MAX_PIXELS", 100):
            with self.assertRaises(ValueError):
                parse_template(self.data)

    def test_visual_pagination_with_different_sides(self):
        back = copy.deepcopy(self.data["sides"]["front"])
        image = io.BytesIO()
        Image.new("RGB", (300, 400), "white").save(image, "PNG")
        back.update(image="data:image/png;base64," + base64.b64encode(image.getvalue()).decode(),
                    body={"x": 30, "y": 80, "width": 240, "height": 280}, font_size=16, line_spacing=30, meta={})
        self.data["sides"]["back"] = back
        _, preset, assets = parse_template(self.data)
        for side in ("front", "back"):
            bg = self.root / (side + ".png")
            bg.write_bytes(assets[side + ".png"])
            preset[side]["bg_file"] = str(bg)
        writer = HandWriter([str(ROOT / "fonts/font0.ttf")], preset["front"], preset["back"], rng=random.Random(42))
        writer.write_text("正文分页测试，核对边距和字号。" * 70)
        pages = writer.pages + [writer.current_image]
        self.assertGreater(len(pages), 2)
        for index, image in enumerate(pages):
            layout = preset["back" if index % 2 else "front"]
            ink = ImageChops.difference(image, Image.new("RGB", image.size, "white")).getbbox()
            if ink:
                self.assertGreaterEqual(ink[0], layout["left_margin"])
                self.assertGreaterEqual(ink[1], layout["start_y"])
                self.assertLessEqual(ink[2], image.width - layout["right_margin"])
                self.assertLessEqual(ink[3], image.height - layout["bottom_margin"])

    def test_request_size_limit(self):
        self.login()
        response = self.client.post("/admin/templates/export", data=b"x" * (MAX_REQUEST + 1),
                                    content_type="application/json", headers={"X-CSRF-Token": self.token()})
        self.assertEqual(response.status_code, 413)

    def test_export_bundle(self):
        self.login()
        response = self.post("export")
        self.assertEqual(response.status_code, 200)
        with ZipFile(io.BytesIO(response.data)) as archive:
            self.assertIn("papers/test_paper/front.png", archive.namelist())
            self.assertEqual(json.loads(archive.read("editor.json")), self.data)
            self.assertIn("test_paper", yaml.safe_load(archive.read("paper_presets.yaml")))
        self.assertFalse((self.root / "papers").exists())

    def test_save_preserves_existing_and_rejects_overwrite(self):
        original = '# 现有注释\nold_paper:\n  display_name: "旧纸张"\n'
        registry = self.root / "paper_presets.yaml"
        registry.write_text(original, "utf-8")
        self.login()
        response = self.post("save")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(registry.read_text("utf-8").startswith(original))
        parsed = yaml.safe_load(registry.read_text("utf-8"))
        self.assertEqual(parsed["old_paper"], {"display_name": "旧纸张"})
        self.assertEqual(parsed["test_paper"]["front"]["coordinate_mode"], "visual")
        self.assertTrue((self.root / "papers/test_paper/front.png").is_file())
        self.assertEqual(json.loads((self.root / "papers/test_paper/editor.json").read_text("utf-8")), self.data)
        after = registry.read_bytes()
        self.assertEqual(self.post("save").status_code, 409)
        self.assertEqual(registry.read_bytes(), after)
        self.data["id"] = "default"
        self.assertEqual(self.post("save").status_code, 409)

    def test_wrapped_registry(self):
        registry = self.root / "paper_presets.yaml"
        registry.write_text("# comment\npaper_presets:\n  old: {}\n", "utf-8")
        self.login()
        self.assertEqual(self.post("save").status_code, 200)
        self.assertIn("test_paper", yaml.safe_load(registry.read_text())["paper_presets"])

    def test_unsafe_registry_is_not_modified(self):
        registry = self.root / "paper_presets.yaml"
        original = 'paper_presets: {}\nother: 1\n'
        registry.write_text(original)
        self.login()
        self.assertEqual(self.post("save").status_code, 400)
        self.assertEqual(registry.read_text(), original)
        self.assertFalse((self.root / "papers/test_paper").exists())

    def test_preview_and_no_persistent_output(self):
        self.login()
        for side in ("front", "back"):
            response = self.post("preview?side=" + side)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "image/jpeg")
            with Image.open(io.BytesIO(response.data)) as image:
                self.assertEqual(image.size, (500, 700))
                self.assertIsNotNone(ImageChops.difference(image.convert("RGB"), Image.new("RGB", image.size, "white")).getbbox())
        self.assertEqual(self.post("preview?side=invalid").status_code, 400)
        self.assertFalse((self.root / "papers").exists())

    def grid_layout(self, rows=6, alignment="bottom", gap=3):
        self.data["sides"]["front"].update(body_mode="grid", row_count=rows,
                                           body_alignment=alignment, bottom_gap=gap)
        _, preset, assets = parse_template(self.data)
        for side in ("front", "back"):
            filename = Path(preset[side]["bg_file"]).name
            bg = self.root / filename
            bg.write_bytes(assets[filename])
            preset[side]["bg_file"] = str(bg)
        return preset

    def test_grid_fractional_spacing_and_exact_last_row(self):
        preset = self.grid_layout()
        front = preset["front"]
        self.assertEqual(front["line_spacing"], 400 / 6)
        self.assertEqual(front["body_grid"]["region"], self.data["sides"]["front"]["body"])
        writer = HandWriter([str(ROOT / "fonts/font0.ttf")], front, preset["back"], rng=random.Random(42))
        self.assertEqual(writer.cursor_y, 250 + 400 / 6 - 3)
        for row in range(1, 6):
            writer._advance_line()
            self.assertEqual(writer.cursor_y, 250 + (row + 1) * 400 / 6 - 3)
        self.assertEqual(writer.cursor_y, 647)
        self.assertEqual(writer.pages, [])
        self.assertFalse(writer._has_next_body_line())
        writer._advance_line()
        self.assertEqual(len(writer.pages), 1)
        self.assertEqual(writer.grid_row, 0)
        self.assertEqual(writer.cursor_y, 250 + 400 / 6 - 3)
        _, errors = validate_config({"fonts": [str(ROOT / "fonts/font0.ttf")]}, front, preset["back"], "grid")
        self.assertEqual(errors, [])

    def test_grid_bottom_alignment_and_cell_bounds(self):
        for alignment in ("bottom", "top"):
            preset = self.grid_layout(alignment=alignment)
            writer = HandWriter([str(ROOT / "fonts/font0.ttf")], preset["front"], preset["back"], rng=random.Random(42))
            writer.write_text("\n".join(["文字、句号。"] * 6), single_page=True)
            self.assertEqual(writer.pages, [])
            self.assertEqual(writer.grid_row, 5)
            diff = ImageChops.difference(writer.current_image, Image.new("RGB", (500, 700), "white"))
            for row in range(6):
                top = round(250 + row * 400 / 6)
                bottom = round(250 + (row + 1) * 400 / 6)
                ink = diff.crop((40, top, 460, bottom)).getbbox()
                self.assertIsNotNone(ink)
                if alignment == "bottom":
                    self.assertGreater(ink[1], (bottom - top) / 2)
                    self.assertLessEqual(ink[3], bottom - top - 3)
                    self.assertGreaterEqual(ink[3], bottom - top - 3 - 6)
                else:
                    self.assertLessEqual(ink[3], 24)
            self.assertIsNone(diff.crop((0, 0, 500, 250)).getbbox())
            self.assertIsNone(diff.crop((0, 650, 500, 700)).getbbox())

    def test_grid_does_not_change_metadata(self):
        preset = self.grid_layout()
        grid = preset["front"]
        legacy = copy.deepcopy(grid)
        legacy.pop("body_grid")
        legacy["line_spacing"] = 40
        writers = [HandWriter([str(ROOT / "fonts/font0.ttf")], layout, layout, rng=random.Random(42)) for layout in (legacy, grid)]
        for writer in writers:
            writer.write_meta({"chairperson": "文、字。"})
        self.assertEqual(writers[0].current_image.tobytes(), writers[1].current_image.tobytes())

    def test_grid_single_page_equals_formal_first_page(self):
        for alignment in ("top", "bottom"):
            preset = self.grid_layout(alignment=alignment)
            writers = [HandWriter([str(ROOT / "fonts/font0.ttf")], preset["front"], preset["back"], rng=random.Random(42)) for _ in range(2)]
            content = "检查格线、换行与标点。" * 70
            writers[0].write_text(content)
            writers[1].write_text(content, single_page=True)
            self.assertGreater(len(writers[0].pages), 0)
            self.assertEqual(writers[1].pages, [])
            self.assertEqual(writers[0].pages[0].tobytes(), writers[1].current_image.tobytes())

    def test_grid_one_row_and_two_distinct_sides(self):
        preset = self.grid_layout(rows=1, gap=0)
        front, back = preset["front"], preset["back"]
        back["body_grid"]["rows"] = 3
        back["body_grid"]["alignment"] = "top"
        writer = HandWriter([str(ROOT / "fonts/font0.ttf")], front, back, rng=random.Random(42))
        writer.write_text("第一面。\n第二面。\n第二行。\n第三行。\n第三面。")
        self.assertEqual(len(writer.pages), 2)
        self.assertEqual(writer.grid_row, 0)
        self.assertEqual(writer.cursor_y, 650)

    def test_grid_options_survive_export_and_save(self):
        self.grid_layout()
        self.login()
        response = self.post("export")
        self.assertEqual(response.status_code, 200)
        with ZipFile(io.BytesIO(response.data)) as archive:
            preset = yaml.safe_load(archive.read("paper_presets.yaml"))["test_paper"]
            self.assertEqual(preset["front"]["body_grid"]["rows"], 6)
            self.assertEqual(preset["front"]["body_grid"], preset["back"]["body_grid"])
            self.assertEqual(json.loads(archive.read("editor.json")), self.data)
        self.assertEqual(self.post("save").status_code, 200)
        registry = yaml.safe_load((self.root / "paper_presets.yaml").read_text())
        self.assertEqual(registry["test_paper"]["front"]["line_spacing"], 400 / 6)

    def test_grid_preview_and_asset_version(self):
        self.grid_layout()
        self.login()
        page = self.client.get("/admin/templates/").data.decode()
        self.assertIn('id="bodyMode"', page)
        self.assertRegex(page, r'template_grid\.js\?v=\d+')
        self.assertRegex(page, r'template_editor\.js\?v=\d+')
        original = HandWriter.write_text
        with patch.object(HandWriter, "write_text", autospec=True, side_effect=original) as render:
            response = self.post("preview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(render.call_args.kwargs, {"single_page": True})
        self.assertEqual(render.call_args.args[0].body_grid["rows"], 6)
        self.assertEqual(render.call_args.args[0].grid_row, 5)
        self.assertEqual(render.call_args.args[0].pages, [])

    def test_grid_rejects_invalid_parameters_without_changing_legacy(self):
        _, preset, _ = parse_template(self.data)
        self.assertNotIn("body_grid", preset["front"])
        self.data["sides"]["front"]["body_mode"] = "legacy"
        self.assertEqual(parse_template(self.data)[1], preset)
        self.data["sides"]["front"].update(body_mode="grid", row_count=6, body_alignment="bottom", bottom_gap=3)
        for key, value in [("body_mode", "unknown"), ("row_count", 0), ("row_count", 501), ("row_count", 1.5),
                           ("row_count", True), ("row_count", 50), ("bottom_gap", -1), ("bottom_gap", 50),
                           ("bottom_gap", 0.1), ("body_alignment", "center")]:
            data = copy.deepcopy(self.data)
            data["sides"]["front"][key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError):
                    parse_template(data)

    def test_visual_punctuation_keeps_font_baseline(self):
        _, preset, assets = parse_template(self.data)
        bg = self.root / "front.png"
        bg.write_bytes(assets["front.png"])
        layout = preset["front"]
        layout["bg_file"] = str(bg)
        for size in (24, 50, 110):
            for seed in (1, 42, 100):
                with self.subTest(size=size, seed=seed):
                    layout["font_size"] = size
                    writer = HandWriter([str(ROOT / "fonts/font0.ttf")], layout, layout, rng=random.Random(seed))
                    font = ImageFont.truetype(str(ROOT / "fonts/font0.ttf"), size)

                    def ink(char):
                        glyph, _ = writer.draw_char_image(char, font)
                        self.assertEqual(glyph.height, size)
                        return glyph.getchannel("A").point(lambda alpha: 255 if alpha >= 32 else 0).getbbox()

                    text = ink("文")
                    for char in "、。，":
                        punctuation = ink(char)
                        self.assertGreater(punctuation[1], (text[1] + text[3]) / 2)
                        self.assertLess(abs(punctuation[3] - text[3]), size * 0.2)
                        self.assertLess(punctuation[3] - punctuation[1], (text[3] - text[1]) * 0.65)
                    for char in "—一":
                        horizontal = ink(char)
                        self.assertGreater((horizontal[1] + horizontal[3]) / 2, text[1] + size * 0.15)
                        self.assertLess((horizontal[1] + horizontal[3]) / 2, text[3] - size * 0.15)
                    for char in "“”":
                        quote = ink(char)
                        self.assertLess((quote[1] + quote[3]) / 2, (text[1] + text[3]) / 2)

    def test_single_page_matches_formal_first_page(self):
        _, preset, assets = parse_template(self.data)
        bg = self.root / "front.png"
        bg.write_bytes(assets["front.png"])
        layout = preset["front"]
        layout["bg_file"] = str(bg)
        for text in ("文、字。检查“引号”、逗号，和破折号——的位置。" * 60,
                     "张三、李四。\n" * 40):
            with self.subTest(text=text[:20]):
                writers = [HandWriter([str(ROOT / "fonts/font0.ttf")], layout, layout, rng=random.Random(42)) for _ in range(2)]
                for writer in writers:
                    writer.write_meta({"chairperson": "张三"})
                writers[0].write_text(text)
                writers[1].write_text(text, single_page=True)
                self.assertGreater(len(writers[0].pages), 0)
                self.assertEqual(writers[1].pages, [])
                self.assertEqual(writers[0].pages[0].tobytes(), writers[1].current_image.tobytes())

    def test_preview_uses_formal_write_text(self):
        self.login()
        original = HandWriter.write_text
        with patch.object(HandWriter, "write_text", autospec=True, side_effect=original) as render:
            response = self.post("preview")
        self.assertEqual(response.status_code, 200)
        render.assert_called_once()
        self.assertEqual(render.call_args.kwargs, {"single_page": True})
        self.assertIn("、", render.call_args.args[1])
        self.assertIn("。", render.call_args.args[1])
        self.assertEqual(render.call_args.args[0].pages, [])

    def test_visual_meta_contained_and_empty_meta_allowed(self):
        _, preset, assets = parse_template(self.data)
        bg = self.root / "front.png"; bg.write_bytes(assets["front.png"])
        front = preset["front"]; front["bg_file"] = str(bg)
        writer = HandWriter([str(ROOT / "fonts/font0.ttf")], front, front, rng=random.Random(42))
        writer.write_meta({"chairperson": "张三"})
        ink = ImageChops.difference(writer.current_image, Image.new("RGB", (500, 700), "white")).getbbox()
        self.assertIsNotNone(ink)
        self.assertGreaterEqual(ink[0], 120); self.assertGreaterEqual(ink[1], 100)
        self.assertLessEqual(ink[2], 290); self.assertLessEqual(ink[3], 130)
        self.assertEqual(writer.base_size, 24); self.assertEqual(writer.line_height, 40)
        self.assertEqual(writer.bottom_limit, 626)
        front["meta_position"] = {}
        _, errors = validate_config({"fonts": [str(ROOT / "fonts/font0.ttf")]}, front, front, "test")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
