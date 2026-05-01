import os
import random
import secrets
import uuid
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_from_directory, session, url_for

from handwrite import (
    DEFAULT_PAPER_TYPE,
    HandWriter,
    build_paper_presets,
    get_available_paper_types,
    load_config,
    normalize_config_paths,
    resolve_paper_layout,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
PAPERS_DIR = BASE_DIR / "papers"
DEFAULT_FONT = BASE_DIR / "fonts" / "font0.ttf"
WEB_CONFIG_PATH = BASE_DIR / "config.yaml"
SECRET_KEY_FILE = BASE_DIR / ".flask_secret_key"

SESSION_FORM_KEY = "last_form_data"
SESSION_ERROR_KEY = "last_error"
SESSION_RESULT_PREFIX_KEY = "last_result_prefix"
SESSION_PDF_FILENAME_KEY = "last_pdf_filename"

MAX_CONTENT_CHARS = 12000
MAX_GENERATED_PAGES = 20
SESSION_FIELD_LIMITS = {
    "year": 16,
    "month": 16,
    "day": 16,
    "venue": 128,
    "meeting_title": 256,
    "chairperson": 64,
    "recorder": 64,
    "attendees": 256,
    "paper_type": 64,
    "seed": 32,
    "content": 900,
    "output_format": 4,
}
SESSION_PAYLOAD_MAX_BYTES = 2800


def _get_int_env(name, default, minimum=1):
    raw = os.environ.get(name)
    if raw is None:
        return default

    try:
        value = int(raw)
    except ValueError:
        return default

    return value if value >= minimum else default


MAX_CONTENT_CHARS = _get_int_env("MAX_CONTENT_CHARS", MAX_CONTENT_CHARS, minimum=100)
MAX_GENERATED_PAGES = _get_int_env("MAX_GENERATED_PAGES", MAX_GENERATED_PAGES, minimum=1)


def _load_secret_key():
    env_key = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if env_key:
        return env_key

    if SECRET_KEY_FILE.exists():
        existing = SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    generated = secrets.token_urlsafe(48)
    try:
        SECRET_KEY_FILE.write_text(generated, encoding="utf-8")
        os.chmod(SECRET_KEY_FILE, 0o600)
    except OSError as exc:
        raise RuntimeError(
            "缺少 FLASK_SECRET_KEY，且无法自动写入本地密钥文件 .flask_secret_key。"
            "请设置环境变量 FLASK_SECRET_KEY。"
        ) from exc
    return generated


app = Flask(__name__)
app.config["SECRET_KEY"] = _load_secret_key()


def _build_meta_from_form(form):
    return {
        "year": form.get("year", "").strip(),
        "month": form.get("month", "").strip(),
        "day": form.get("day", "").strip(),
        "venue": form.get("venue", "").strip(),
        "meeting_title": form.get("meeting_title", "").strip(),
        "chairperson": form.get("chairperson", "").strip(),
        "recorder": form.get("recorder", "").strip(),
        "attendees": form.get("attendees", "").strip(),
    }


def _copy_layout_with_absolute_bg(layout):
    copied = dict(layout)
    copied["bg_file"] = str((BASE_DIR / layout["bg_file"]).resolve())
    return copied


def _load_web_config():
    if WEB_CONFIG_PATH.exists():
        loaded = load_config(str(WEB_CONFIG_PATH))
        return normalize_config_paths(loaded, str(WEB_CONFIG_PATH))
    return {}


def _get_paper_options(config):
    presets = build_paper_presets(config)
    paper_types = get_available_paper_types(presets)

    configured_default = config.get("paper_type", DEFAULT_PAPER_TYPE)
    if isinstance(configured_default, str):
        configured_default = configured_default.strip()
    else:
        configured_default = DEFAULT_PAPER_TYPE

    if configured_default not in presets:
        configured_default = DEFAULT_PAPER_TYPE

    return paper_types, configured_default, presets


def _resolve_paper_asset_url(path_value):
    """将纸张资源路径解析为可访问 URL；失败返回空字符串"""
    if not isinstance(path_value, str) or not path_value.strip():
        return ""

    paper_root = PAPERS_DIR.resolve()
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = (BASE_DIR / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.exists() or not candidate.is_file():
        return ""

    try:
        rel_path = candidate.relative_to(paper_root).as_posix()
    except ValueError:
        return ""

    return url_for("serve_paper_asset", filename=rel_path)


def _build_paper_preview_items(presets):
    """构建纸张预览映射：paper_type -> [{label, url}, ...]"""
    preview_items = {}

    for paper_type, preset in presets.items():
        items = []
        front_url = _resolve_paper_asset_url(preset.get("front", {}).get("bg_file"))
        back_url = _resolve_paper_asset_url(preset.get("back", {}).get("bg_file"))

        if front_url:
            items.append({"label": "正面", "url": front_url})
        if back_url:
            items.append({"label": "背面", "url": back_url})

        # 兼容旧配置：如果 front/back 都无效，再尝试单独 preview_file
        if not items:
            preview_url = _resolve_paper_asset_url(preset.get("preview_file"))
            if preview_url:
                items.append({"label": "预览", "url": preview_url})

        if items:
            preview_items[paper_type] = items

    return preview_items


def _render_index(images=None, form_data=None, error=None, pdf_url=None):
    form_data = dict(form_data or {})
    paper_types = [DEFAULT_PAPER_TYPE]
    default_paper_type = DEFAULT_PAPER_TYPE
    paper_preview_map = {}
    default_paper_previews = []
    config_error = None

    try:
        config = _load_web_config()
        paper_types, default_paper_type, presets = _get_paper_options(config)
        paper_preview_map = _build_paper_preview_items(presets)
        default_paper_previews = paper_preview_map.get(default_paper_type, [])
    except Exception:
        app.logger.exception("加载 Web 配置失败")
        config_error = "配置加载失败，请检查服务器日志。"

    if not form_data.get("paper_type"):
        form_data["paper_type"] = default_paper_type

    if config_error:
        error = f"{error}（另：{config_error}）" if error else config_error

    return render_template(
        "index.html",
        images=images,
        error=error,
        form_data=form_data,
        paper_types=paper_types,
        default_paper_type=default_paper_type,
        paper_preview_map=paper_preview_map,
        default_paper_previews=default_paper_previews,
        pdf_url=pdf_url,
    )


def _image_urls_by_prefix(output_prefix, output_format="jpg"):
    if not isinstance(output_prefix, str) or not output_prefix.strip():
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # 尝试指定格式，如果没有文件则回退到另一种格式
    generated = sorted(OUTPUT_DIR.glob(f"{output_prefix}_page_*.{output_format}"))
    if not generated:
        alt = "png" if output_format.lower() == "jpg" else "jpg"
        generated = sorted(OUTPUT_DIR.glob(f"{output_prefix}_page_*.{alt}"))
    return [url_for("serve_output", filename=p.name) for p in generated]


def _save_page_state(form_data=None, error=None, result_prefix=None, pdf_filename=None):
    session[SESSION_FORM_KEY] = _sanitize_form_data_for_session(form_data)
    session[SESSION_ERROR_KEY] = error
    session[SESSION_RESULT_PREFIX_KEY] = result_prefix
    session[SESSION_PDF_FILENAME_KEY] = pdf_filename


def _clear_page_state():
    session.pop(SESSION_FORM_KEY, None)
    session.pop(SESSION_ERROR_KEY, None)
    session.pop(SESSION_RESULT_PREFIX_KEY, None)
    session.pop(SESSION_PDF_FILENAME_KEY, None)


def _sanitize_form_data_for_session(form_data):
    sanitized = {}
    if not isinstance(form_data, dict):
        return sanitized

    for field, limit in SESSION_FIELD_LIMITS.items():
        value = form_data.get(field, "")
        if not isinstance(value, str):
            continue
        if field != "content":
            value = value.strip()
        if not value:
            continue
        sanitized[field] = value[:limit]

    payload_size = len(str(sanitized).encode("utf-8"))
    if payload_size > SESSION_PAYLOAD_MAX_BYTES and "content" in sanitized:
        sanitized.pop("content", None)

    return sanitized


def generate_images(meta, content, paper_type=None, seed=None, output_format="jpg"):
    fonts = [str(DEFAULT_FONT)]
    if not DEFAULT_FONT.exists():
        raise RuntimeError(f"字体文件不存在: {DEFAULT_FONT}")

    rng = random.Random(seed) if seed is not None else random.Random()

    config = _load_web_config()
    used_paper_type, config_front, config_back, _ = resolve_paper_layout(
        config,
        paper_type_override=paper_type,
    )

    output_prefix = f"web_{uuid.uuid4().hex[:10]}"

    # 图片格式：jpg 或 png
    image_format = "png" if output_format.lower() == "png" else "jpg"

    writer = HandWriter(
        fonts,
        _copy_layout_with_absolute_bg(config_front),
        _copy_layout_with_absolute_bg(config_back),
        debug_box=False,
        max_pages=MAX_GENERATED_PAGES,
        rng=rng,
    )
    writer.write_meta(meta)
    if content:
        writer.write_text(content.strip())
    writer.save_all(output_prefix, image_format)

    # PDF 生成：始终生成，供用户下载
    pdf_filename = None
    try:
        pdf_path = writer.save_pdf(output_prefix)
        if pdf_path:
            pdf_filename = os.path.basename(pdf_path)
    except Exception:
        app.logger.warning("PDF 生成失败，不影响图片展示", exc_info=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = sorted(OUTPUT_DIR.glob(f"{output_prefix}_page_*.{image_format}"))
    return [p.name for p in generated], used_paper_type, output_prefix, pdf_filename


@app.route("/", methods=["GET"])
def index():
    form_data = session.get(SESSION_FORM_KEY, {})
    error = session.get(SESSION_ERROR_KEY)
    result_prefix = session.get(SESSION_RESULT_PREFIX_KEY)
    pdf_filename = session.get(SESSION_PDF_FILENAME_KEY)
    saved_format = form_data.get("output_format", "jpg")
    images = _image_urls_by_prefix(result_prefix, output_format=saved_format)
    pdf_url = url_for("serve_output", filename=pdf_filename) if pdf_filename else None

    return _render_index(images=images or None, form_data=form_data, error=error, pdf_url=pdf_url)


@app.route("/new", methods=["GET"])
def new_generation():
    _clear_page_state()
    return redirect(url_for("index"))


@app.route("/generate", methods=["POST"])
def generate():
    form_data = {k: v for k, v in request.form.items()}
    content = request.form.get("content", "").strip()
    seed_value = request.form.get("seed", "").strip()
    paper_type = request.form.get("paper_type", "").strip() or None
    output_format = request.form.get("output_format", "jpg").strip()
    if paper_type:
        form_data["paper_type"] = paper_type
    form_data["output_format"] = output_format

    if not content:
        _save_page_state(form_data=form_data, error="会议正文不能为空。", result_prefix=None)
        return redirect(url_for("index"))
    if len(content) > MAX_CONTENT_CHARS:
        _save_page_state(
            form_data=form_data,
            error=f"会议正文过长（最多 {MAX_CONTENT_CHARS} 字符）。请缩短后重试。",
            result_prefix=None,
        )
        return redirect(url_for("index"))

    try:
        seed = int(seed_value) if seed_value else None
    except ValueError:
        _save_page_state(form_data=form_data, error="随机种子必须是整数。", result_prefix=None)
        return redirect(url_for("index"))

    try:
        _, used_paper_type, output_prefix, pdf_filename = generate_images(
            _build_meta_from_form(request.form),
            content,
            paper_type=paper_type,
            seed=seed,
            output_format=output_format,
        )
        form_data["paper_type"] = used_paper_type
    except ValueError as exc:
        _save_page_state(form_data=form_data, error=f"生成失败: {exc}", result_prefix=None)
        return redirect(url_for("index"))
    except Exception:
        app.logger.exception("生成手写图片失败")
        _save_page_state(form_data=form_data, error="生成失败：服务端异常，请稍后重试。", result_prefix=None)
        return redirect(url_for("index"))

    _save_page_state(form_data=form_data, error=None, result_prefix=output_prefix, pdf_filename=pdf_filename)
    return redirect(url_for("index"))


@app.route("/output/<path:filename>", methods=["GET"])
def serve_output(filename):
    return send_from_directory(str(OUTPUT_DIR), filename)


@app.route("/paper-assets/<path:filename>", methods=["GET"])
def serve_paper_asset(filename):
    paper_root = PAPERS_DIR.resolve()
    target = (paper_root / filename).resolve()

    try:
        relative_name = target.relative_to(paper_root)
    except ValueError:
        abort(404)

    if not target.exists() or not target.is_file():
        abort(404)

    return send_from_directory(str(paper_root), relative_name.as_posix())


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=False,
    )
