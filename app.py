import random
import uuid
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory, url_for

from handwrite import CONFIG_BACK, CONFIG_FRONT, HandWriter


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_FONT = BASE_DIR / "fonts" / "font0.ttf"

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


def generate_images(meta, content, seed=None):
    fonts = [str(DEFAULT_FONT)]
    if not DEFAULT_FONT.exists():
        raise RuntimeError(f"字体文件不存在: {DEFAULT_FONT}")

    if seed:
        random.seed(seed)

    output_prefix = f"web_{uuid.uuid4().hex[:10]}"
    output_format = "jpg"

    writer = HandWriter(
        fonts,
        _copy_layout_with_absolute_bg(CONFIG_FRONT),
        _copy_layout_with_absolute_bg(CONFIG_BACK),
        debug_box=False,
    )
    writer.write_meta(meta)
    if content:
        writer.write_text(content.strip())
    writer.save_all(output_prefix, output_format)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = sorted(OUTPUT_DIR.glob(f"{output_prefix}_page_*.{output_format}"))
    return [p.name for p in generated]


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", images=None, form_data={})


@app.route("/generate", methods=["POST"])
def generate():
    form_data = {k: v for k, v in request.form.items()}
    content = request.form.get("content", "").strip()
    seed_value = request.form.get("seed", "").strip()

    if not content:
        return render_template(
            "index.html",
            images=None,
            error="会议正文不能为空。",
            form_data=form_data,
        )

    try:
        seed = int(seed_value) if seed_value else None
    except ValueError:
        return render_template(
            "index.html",
            images=None,
            error="随机种子必须是整数。",
            form_data=form_data,
        )

    try:
        images = generate_images(_build_meta_from_form(request.form), content, seed=seed)
    except Exception as exc:
        return render_template(
            "index.html",
            images=None,
            error=f"生成失败: {exc}",
            form_data=form_data,
        )

    image_urls = [url_for("serve_output", filename=name) for name in images]
    return render_template("index.html", images=image_urls, form_data=form_data)


@app.route("/output/<path:filename>", methods=["GET"])
def serve_output(filename):
    return send_from_directory(str(OUTPUT_DIR), filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
