import random
import uuid
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory, url_for

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
    return [p.name for p in generated], used_paper_type


@app.route("/", methods=["GET"])
def index():
    return _render_index(images=None, form_data={})


@app.route("/generate", methods=["POST"])
def generate():
    form_data = {k: v for k, v in request.form.items()}
    content = request.form.get("content", "").strip()
    seed_value = request.form.get("seed", "").strip()
    paper_type = request.form.get("paper_type", "").strip() or None
    if paper_type:
        form_data["paper_type"] = paper_type

    if not content:
        return _render_index(images=None, error="会议正文不能为空。", form_data=form_data)

    try:
        seed = int(seed_value) if seed_value else None
    except ValueError:
        return _render_index(images=None, error="随机种子必须是整数。", form_data=form_data)

    try:
        images, used_paper_type = generate_images(
            _build_meta_from_form(request.form),
            content,
            paper_type=paper_type,
            seed=seed,
        )
        form_data["paper_type"] = used_paper_type
    except Exception as exc:
        return _render_index(images=None, error=f"生成失败: {exc}", form_data=form_data)

    image_urls = [url_for("serve_output", filename=name) for name in images]
    return _render_index(images=image_urls, form_data=form_data)


@app.route("/output/<path:filename>", methods=["GET"])
def serve_output(filename):
    return send_from_directory(str(OUTPUT_DIR), filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
