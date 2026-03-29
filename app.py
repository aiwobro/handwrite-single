import os
import random
import uuid
from pathlib import Path

from flask import redirect, render_template, request, send_from_directory, session, url_for, Flask

from handwrite import (
    DEFAULT_PAPER_TYPE,
    HandWriter,
    build_paper_presets,
    get_available_paper_types,
    load_config,
    resolve_paper_layout,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_FONT = BASE_DIR / "fonts" / "font0.ttf"
WEB_CONFIG_PATH = BASE_DIR / "config.yaml"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "handwrite-dev-secret")

SESSION_FORM_KEY = "last_form_data"
SESSION_ERROR_KEY = "last_error"
SESSION_RESULT_PREFIX_KEY = "last_result_prefix"


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
        return load_config(str(WEB_CONFIG_PATH))
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

    return paper_types, configured_default


def _render_index(images=None, form_data=None, error=None):
    form_data = dict(form_data or {})
    paper_types = [DEFAULT_PAPER_TYPE]
    default_paper_type = DEFAULT_PAPER_TYPE
    config_error = None

    try:
        config = _load_web_config()
        paper_types, default_paper_type = _get_paper_options(config)
    except Exception as exc:
        config_error = f"配置加载失败: {exc}"

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
    )


def _image_urls_by_prefix(output_prefix, output_format="jpg"):
    if not isinstance(output_prefix, str) or not output_prefix.strip():
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = sorted(OUTPUT_DIR.glob(f"{output_prefix}_page_*.{output_format}"))
    return [url_for("serve_output", filename=p.name) for p in generated]


def _save_page_state(form_data=None, error=None, result_prefix=None):
    session[SESSION_FORM_KEY] = dict(form_data or {})
    session[SESSION_ERROR_KEY] = error
    session[SESSION_RESULT_PREFIX_KEY] = result_prefix


def _clear_page_state():
    session.pop(SESSION_FORM_KEY, None)
    session.pop(SESSION_ERROR_KEY, None)
    session.pop(SESSION_RESULT_PREFIX_KEY, None)


def generate_images(meta, content, paper_type=None, seed=None):
    fonts = [str(DEFAULT_FONT)]
    if not DEFAULT_FONT.exists():
        raise RuntimeError(f"字体文件不存在: {DEFAULT_FONT}")

    if seed is not None:
        random.seed(seed)

    config = _load_web_config()
    used_paper_type, config_front, config_back, _ = resolve_paper_layout(
        config,
        paper_type_override=paper_type,
    )

    output_prefix = f"web_{uuid.uuid4().hex[:10]}"
    output_format = "jpg"

    writer = HandWriter(
        fonts,
        _copy_layout_with_absolute_bg(config_front),
        _copy_layout_with_absolute_bg(config_back),
        debug_box=False,
    )
    writer.write_meta(meta)
    if content:
        writer.write_text(content.strip())
    writer.save_all(output_prefix, output_format)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = sorted(OUTPUT_DIR.glob(f"{output_prefix}_page_*.{output_format}"))
    return [p.name for p in generated], used_paper_type, output_prefix


@app.route("/", methods=["GET"])
def index():
    form_data = session.get(SESSION_FORM_KEY, {})
    error = session.get(SESSION_ERROR_KEY)
    result_prefix = session.get(SESSION_RESULT_PREFIX_KEY)
    images = _image_urls_by_prefix(result_prefix)

    return _render_index(images=images or None, form_data=form_data, error=error)


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
    if paper_type:
        form_data["paper_type"] = paper_type

    if not content:
        _save_page_state(form_data=form_data, error="会议正文不能为空。", result_prefix=None)
        return redirect(url_for("index"))

    try:
        seed = int(seed_value) if seed_value else None
    except ValueError:
        _save_page_state(form_data=form_data, error="随机种子必须是整数。", result_prefix=None)
        return redirect(url_for("index"))

    try:
        _, used_paper_type, output_prefix = generate_images(
            _build_meta_from_form(request.form),
            content,
            paper_type=paper_type,
            seed=seed,
        )
        form_data["paper_type"] = used_paper_type
    except Exception as exc:
        _save_page_state(form_data=form_data, error=f"生成失败: {exc}", result_prefix=None)
        return redirect(url_for("index"))

    _save_page_state(form_data=form_data, error=None, result_prefix=output_prefix)
    return redirect(url_for("index"))


@app.route("/output/<path:filename>", methods=["GET"])
def serve_output(filename):
    return send_from_directory(str(OUTPUT_DIR), filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
