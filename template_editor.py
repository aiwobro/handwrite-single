"""管理员纸张编辑器：浏览器标注，服务端校验、试写及保存。"""
import base64
import binascii
import copy
import hashlib
import hmac
import io
import json
import os
import re
import random
import secrets
import tempfile
import time
import warnings
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import fcntl
import yaml
from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_file, session
from PIL import Image, ImageOps, UnidentifiedImageError

from handwrite import HandWriter, DEFAULT_PAPER_PRESETS, validate_body_grid

editor = Blueprint("template_editor", __name__, url_prefix="/admin/templates")
FIELDS = {"year", "month", "day", "venue", "meeting_title", "chairperson", "recorder", "attendees"}
MAX_PIXELS = 24_000_000
MAX_REQUEST = 24 * 1024 * 1024
_login_attempts = {}


def _password():
    return os.environ.get("TEMPLATE_ADMIN_PASSWORD", "")


def _identity():
    key = current_app.secret_key
    return hmac.new(key.encode() if isinstance(key, str) else key, _password().encode(), hashlib.sha256).hexdigest()


def _authorized():
    return (session.get("template_admin_until", 0) > time.time()
            and hmac.compare_digest(session.get("template_admin", ""), _identity()))


@editor.before_request
def guard():
    # 未显式设置足够强的密码时 fail closed，不影响公开生成页面。
    if len(_password()) < 16:
        abort(404)
    request.max_content_length = MAX_REQUEST
    if "template_csrf" not in session:
        session["template_csrf"] = secrets.token_urlsafe(32)
    if request.method == "POST":
        token = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(token, session["template_csrf"]):
            abort(403)
    if request.endpoint not in {"template_editor.index", "template_editor.login"} and not _authorized():
        abort(401)


@editor.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@editor.get("")
@editor.get("/")
def index():
    # 对外 Nginx 静态资源使用长缓存，修改脚本后通过版本号更新浏览器缓存。
    static_root = Path(__file__).resolve().parent / "static"
    assets = (static_root / "css/template_editor.css", static_root / "js/template_editor.js", static_root / "js/template_grid.js")
    version = max(path.stat().st_mtime_ns for path in assets)
    return render_template("template_editor.html", authorized=_authorized(), csrf=session["template_csrf"], asset_version=version)


@editor.post("/login")
def login():
    now = time.monotonic()
    ip = request.remote_addr or "unknown"
    # 简单进程内节流；生产入口仍应由反向代理限制登录速率。
    for key in list(_login_attempts):
        if now - _login_attempts[key][0] > 300:
            del _login_attempts[key]
    start, count = _login_attempts.get(ip, (now, 0))
    if count >= 10 or len(_login_attempts) > 10000:
        return jsonify(error="尝试过多，请五分钟后重试。"), 429
    _login_attempts[ip] = (start, count + 1)
    data = request.get_json(silent=True) or {}
    password = data.get("password", "") if isinstance(data, dict) else ""
    if not isinstance(password, str) or not hmac.compare_digest(password.encode(), _password().encode()):
        return jsonify(error="密码不正确。"), 401
    _login_attempts.pop(ip, None)
    session["template_admin"] = _identity()
    session["template_admin_until"] = time.time() + 3600
    session["template_csrf"] = secrets.token_urlsafe(32)
    return jsonify(ok=True)


@editor.post("/logout")
def logout():
    for key in ("template_admin", "template_admin_until", "template_csrf"):
        session.pop(key, None)
    return jsonify(ok=True)


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} 必须是 {low} 至 {high} 的整数。")
    return value


def _box(raw, width, height, name):
    if not isinstance(raw, dict):
        raise ValueError(f"请标注{name}。")
    x = _integer(raw.get("x"), name + " x", 0, width - 1)
    y = _integer(raw.get("y"), name + " y", 0, height - 1)
    w = _integer(raw.get("width"), name + " 宽", 1, width - x)
    h = _integer(raw.get("height"), name + " 高", 1, height - y)
    return dict(x=x, y=y, width=w, height=h)


def _image(data):
    if not isinstance(data, str) or not data.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
        raise ValueError("只支持 PNG / JPEG 图片。")
    try:
        binary = base64.b64decode(data.split(",", 1)[1], validate=True)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(binary)) as source:
                if source.format not in {"PNG", "JPEG"} or source.width * source.height > MAX_PIXELS:
                    raise ValueError("图片格式不支持或超过 2400 万像素。")
                oriented = ImageOps.exif_transpose(source).convert("RGBA")
                image = Image.new("RGB", oriented.size, "white")
                image.paste(oriented, mask=oriented.getchannel("A"))
        out = io.BytesIO()
        image.save(out, "PNG")
        return image.size, out.getvalue()
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("图片损坏或尺寸过大。") from exc


def parse_template(data):
    if not isinstance(data, dict):
        raise ValueError("请求必须为对象。")
    template_id = data.get("id", "")
    if not isinstance(template_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", template_id):
        raise ValueError("模板 ID 必须以小写字母开头，仅含小写字母、数字、下划线或连字符，最多48字符。")
    title = data.get("display_name")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 80:
        raise ValueError("请输入模板名称（最多80字符）。")
    raw_sides = data.get("sides")
    if not isinstance(raw_sides, dict) or "front" not in raw_sides or set(raw_sides) - {"front", "back"}:
        raise ValueError("请上传正面图片。")
    preset = {"display_name": title.strip()}
    assets = {}
    for side, raw in raw_sides.items():
        if not isinstance(raw, dict):
            raise ValueError("纸张数据无效。")
        (w, h), binary = _image(raw.get("image"))
        body = _box(raw.get("body"), w, h, "正文区域")
        size = _integer(raw.get("font_size"), "字号", 8, min(500, body["height"]))
        mode = raw.get("body_mode", "legacy")
        if mode not in ("legacy", "grid"):
            raise ValueError("正文排版模式无效。")
        grid = None
        if mode == "grid":
            grid = validate_body_grid(dict(region=body, rows=raw.get("row_count"),
                                           alignment=raw.get("body_alignment", "bottom"),
                                           bottom_gap=raw.get("bottom_gap", 2)), w, h, size)
            spacing = body["height"] / grid["rows"]
        else:
            spacing = _integer(raw.get("line_spacing"), "行距", size, h)
        meta = raw.get("meta", {})
        if not isinstance(meta, dict) or set(meta) - FIELDS:
            raise ValueError("字段名称无效。")
        if side == "back" and meta:
            raise ValueError("当前渲染器仅在首页填写元数据，请在正面标注字段。")
        boxes = {key: _box(box, w, h, key) for key, box in meta.items()}
        if any(box["height"] < 8 or box["width"] < 8 for box in boxes.values()):
            raise ValueError("字段区域宽高至少为8像素。")
        preset[side] = dict(bg_file=f"./papers/{template_id}/{side}.png", coordinate_mode="visual",
                            start_y=body["y"], line_spacing=spacing, font_size=size,
                            left_margin=body["x"], right_margin=w-body["x"]-body["width"],
                            bottom_margin=h-body["y"]-body["height"], meta_position=boxes)
        if grid is not None:
            preset[side]["body_grid"] = grid
        assets[side + ".png"] = binary
    if "back" not in preset:
        preset["back"] = copy.deepcopy(preset["front"])
        preset["back"]["meta_position"] = {}
    return template_id, preset, assets


def _payload():
    try:
        return parse_template(request.get_json(silent=True))
    except ValueError as exc:
        abort(400, description=str(exc))


@editor.errorhandler(400)
def invalid(error):
    return jsonify(error=error.description), 400


@editor.errorhandler(yaml.YAMLError)
def invalid_registry(error):
    return jsonify(error="模板注册表无法安全解析或追加，请检查 YAML 格式，或改用导出功能。"), 400


@editor.errorhandler(OSError)
def storage_error(error):
    current_app.logger.exception("模板编辑器文件操作失败")
    return jsonify(error="文件读取或保存失败，请检查字体及目录权限。若保存中断，可能留有新资源目录；不会自动删除，请导出模板包保留标注。"), 500


@editor.post("/preview")
def preview():
    _, preset, assets = _payload()
    side = request.args.get("side", "front")
    if side not in {"front", "back"}:
        abort(400, description="无效的纸面。")
    root = Path(current_app.config["TEMPLATE_PROJECT_DIR"])
    with tempfile.TemporaryDirectory(prefix="paper-preview-") as tmp:
        for filename, binary in assets.items():
            (Path(tmp) / filename).write_bytes(binary)
        layout = copy.deepcopy(preset[side])
        layout["bg_file"] = str(Path(tmp) / Path(layout["bg_file"]).name)
        writer = HandWriter([str(root / "fonts/font0.ttf")], layout, layout, rng=random.Random(42))
        if side == "front":
            writer.write_meta(dict(year="2026", month="12", day="28", venue="第一会议室", meeting_title="项目进度总结会议",
                                   chairperson="张三", recorder="李四", attendees="王五、赵六、张三、李四"))
        # 与正式生成共用换行、字距、标点和字形绘制逻辑，只禁止自动翻页。
        row_count = (writer.body_grid["rows"] if writer.body_grid else
                     max(1, (writer.bottom_limit - layout["start_y"]) // layout["line_spacing"] + 1))
        sample = "正文试写：张三、李四参加会议。检查逗号，句号。顿号、以及“引号”与破折号——的位置。\n"
        writer.write_text(sample * row_count, single_page=True)
        out = io.BytesIO()
        writer.current_image.save(out, "JPEG", quality=88)
    out.seek(0)
    return send_file(out, mimetype="image/jpeg")


@editor.post("/export")
def export():
    template_id, preset, assets = _payload()
    out = io.BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        archive.writestr("paper_presets.yaml", yaml.safe_dump({template_id: preset}, allow_unicode=True, sort_keys=False))
        archive.writestr("editor.json", json.dumps(request.get_json(), ensure_ascii=False))
        for filename, binary in assets.items():
            archive.writestr(f"papers/{template_id}/{filename}", binary)
        archive.writestr("README.txt", "将 papers 目录合并到项目；将 paper_presets.yaml 中的新模板条目追加到项目注册表，不要覆盖原文件。editor.json 可在编辑器中重新导入。\n")
    out.seek(0)
    return send_file(out, mimetype="application/zip", as_attachment=True, download_name=template_id + ".zip")


@editor.post("/save")
def save():
    template_id, preset, assets = _payload()
    root = Path(current_app.config["TEMPLATE_PROJECT_DIR"])
    registry_path = root / "paper_presets.yaml"
    # 独立锁文件兼容多 worker；注册表使用原子替换，读者不会看到半个 YAML。
    with (root / ".template_editor.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        registry = yaml.safe_load(registry_path.read_text("utf-8")) if registry_path.exists() else {}
        registry = registry or {}
        if not isinstance(registry, dict):
            abort(400, description="现有模板注册表格式不正确。")
        entries = registry.get("paper_presets", registry)
        if not isinstance(entries, dict):
            abort(400, description="现有模板注册表格式不正确。")
        target = root / "papers" / template_id
        if template_id in entries or template_id in DEFAULT_PAPER_PRESETS or target.exists():
            return jsonify(error="模板 ID 或资源目录已存在，请换一个 ID；不会覆盖现有模板。"), 409
        # 保留已有注释与排版，只追加新条目（兼容注册表包装格式）。
        original = registry_path.read_text("utf-8") if registry_path.exists() else ""
        addition = yaml.safe_dump({template_id: preset}, allow_unicode=True, sort_keys=False)
        if "paper_presets" in registry:
            addition = "\n".join("  " + line for line in addition.splitlines()) + "\n"
        candidate = original.rstrip() + "\n\n" + addition
        parsed = yaml.safe_load(candidate)
        expected = copy.deepcopy(registry)
        expected.get("paper_presets", expected)[template_id] = preset
        if parsed != expected:
            abort(400, description="注册表无法安全追加，请使用导出功能。")
        # 校验完成后才落盘；异常时保留资源，避免误删文件，换 ID 或导出重试。
        target.mkdir(parents=True)
        for filename, binary in assets.items():
            (target / filename).write_bytes(binary)
        (target / "editor.json").write_text(json.dumps(request.get_json(), ensure_ascii=False), "utf-8")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, prefix=".paper-presets-", delete=False) as temp:
            temp.write(candidate)
            temp.flush()
            os.fsync(temp.fileno())
            temp_path = temp.name
        os.chmod(temp_path, registry_path.stat().st_mode & 0o777 if registry_path.exists() else 0o644)
        os.replace(temp_path, registry_path)
    return jsonify(ok=True, message=f"模板 {template_id} 已保存，刷新首页即可使用。")
