import random
import os
import argparse
import sys
import copy
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    import yaml
except ImportError:
    yaml = None

# ================= 配置区域 =================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PAPER_TYPE = "default"
PAPER_PRESETS_FILE = os.path.join(PROJECT_DIR, "paper_presets.yaml")

# 内置兜底预设：当 paper_presets.yaml 不存在时仍可运行
DEFAULT_PAPER_PRESETS = {
    DEFAULT_PAPER_TYPE: {
        "front": {
            "bg_file": os.path.join(PROJECT_DIR, "papers", "default", "front.jpg"),
            "start_y": 567,
            "line_spacing": 71,
            "font_size": 50,
            "left_margin": 150,
            "right_margin": 130,
            "bottom_margin": 150,
            # 会议元数据坐标配置：每个字段为独立矩形区域 (x, y, width, height)
            "meta_position": {
                "year":          {"x": 818, "y": 133, "width": 140, "height": 80},
                "month":         {"x": 923, "y": 138, "width": 80,  "height": 80},
                "day":           {"x": 980, "y": 138, "width": 80,  "height": 80},
                "venue":         {"x": 577, "y": 235, "width": 220, "height": 80},
                "meeting_title": {"x": 303, "y": 345, "width": 700, "height": 120},
                "recorder":      {"x": 888, "y": 350, "width": 200, "height": 80},
                "chairperson":   {"x": 900, "y": 273, "width": 200, "height": 80},
                "attendees":     {"x": 309, "y": 450, "width": 800, "height": 150},
            }
        },
        "back": {
            "bg_file": os.path.join(PROJECT_DIR, "papers", "default", "back.jpg"),
            "start_y": 215,
            "line_spacing": 71,
            "font_size": 50,
            "left_margin": 130,
            "right_margin": 150,
            "bottom_margin": 150,
        },
    }
}

# 运行时基准预设（由 build_paper_presets 合并外部注册表）
PAPER_PRESETS = copy.deepcopy(DEFAULT_PAPER_PRESETS)

# 向后兼容：保留原常量名给已有调用方（例如 app.py）
CONFIG_FRONT = PAPER_PRESETS[DEFAULT_PAPER_TYPE]["front"]
CONFIG_BACK = PAPER_PRESETS[DEFAULT_PAPER_TYPE]["back"]

LAYOUT_REQUIRED_FIELDS = (
    "bg_file",
    "start_y",
    "line_spacing",
    "font_size",
    "left_margin",
    "right_margin",
    "bottom_margin",
)

# ===========================================

class HandWriter:
    def __init__(self, font_paths, config_front, config_back, debug_box=False, max_pages=None, rng=None):
        self.font_paths = font_paths
        self.config_front = config_front
        self.config_back = config_back
        self.debug_box = debug_box
        self.max_pages = max_pages
        self.rng = rng if rng is not None else random.Random()

        self.pages = []
        self.current_image = None
        self.current_draw = None

        # 布局参数
        self.cursor_x = 0
        self.cursor_y = 0
        self.bottom_limit = 0
        self.line_height = 0
        self.base_size = 0
        self.margin_right = 0
        self.margin_left = 0

        # 句号逗号顿号分号：字形小且书写靠下，旋转后容易下垂，额外上移
        self.bottom_punct = {'，', '。', '、', '；', '.'}

        # 横线类符号：字高极小，按原公式会掉到行底，需要少提一些
        self.horizontal_chars = {'—', '－', '-', '一'}

        # GB/T 15834-2011 行末行首禁则（常用集合）
        # 行首禁则：点号和右半标号通常不出现在一行之首
        self.no_line_start = {
            '，', '。', '、', '；', '：', '！', '？',
            ')', '）', ']', '】', '}', '｝', '〉', '》', '」', '』',
            '”', '’', '〗', '〕'
        }
        # 行尾禁则：左半标号不出现在一行之末
        self.no_line_end = {
            '(', '（', '[', '【', '{', '｛', '〈', '《', '「', '『',
            '“', '‘', '〖', '〔'
        }

        # 初始化第一页
        self._load_new_page()

    def _draw_debug_overlay(self, config, page_type):
        """绘制调试框：正文区域与元数据区域"""
        if not self.debug_box:
            return

        overlay = ImageDraw.Draw(self.current_image)

        # 正文可写区域
        text_left = config["left_margin"]
        text_top = config["start_y"]
        text_right = self.width - config["right_margin"]
        text_bottom = self.height - config["bottom_margin"]
        overlay.rectangle((text_left, text_top, text_right, text_bottom), outline=(0, 170, 255), width=2)

        # 基线（每行起笔 y）
        y = text_top
        while y <= text_bottom:
            overlay.line((text_left, y, text_right, y), fill=(180, 220, 255), width=1)
            y += config["line_spacing"]

        if page_type == "front":
            meta_positions = self.config_front.get("meta_position", {})
            for cfg in meta_positions.values():
                x = cfg["x"]
                y = cfg["y"]
                w = cfg["width"]
                h = cfg["height"]
                overlay.rectangle((x, y, x + w, y + h), outline=(255, 120, 0), width=2)

    def _load_new_page(self):
        """加载新页面的逻辑"""
        if self.current_image is not None:
            self.current_image = self.current_image.filter(ImageFilter.GaussianBlur(radius=0.5))
            self.pages.append(self.current_image)

        current_page_index = len(self.pages)
        if self.max_pages is not None and current_page_index >= self.max_pages:
            raise ValueError(f"生成页数超过限制（最多 {self.max_pages} 页）。请缩短正文后重试。")

        if current_page_index % 2 == 0:
            config = self.config_front
            page_type = "front"
            print(f"正在创建第 {current_page_index + 1} 页 (正面)...")
        else:
            config = self.config_back
            page_type = "back"
            print(f"正在创建第 {current_page_index + 1} 页 (背面)...")

        try:
            self.current_image = Image.open(config["bg_file"]).convert("RGB")
        except FileNotFoundError:
            print(f"警告：找不到 {config['bg_file']}，使用空白背景。")
            self.current_image = Image.new("RGB", (1240, 1754), (255, 255, 255))

        self.width, self.height = self.current_image.size
        self.current_draw = ImageDraw.Draw(self.current_image)
        self._draw_debug_overlay(config, page_type)

        self.base_size = config["font_size"]
        self.line_height = config["line_spacing"]
        self.margin_left = config["left_margin"]
        self.margin_right = config["right_margin"]
        self.bottom_limit = self.height - config["bottom_margin"]

        if current_page_index % 2 == 0:
            self.cursor_x = self.margin_left + 80
        else:
            self.cursor_x = self.margin_left

        self.cursor_y = config["start_y"]

    def get_random_font(self):
        font_path = self.rng.choice(self.font_paths)
        random_size = self.base_size + self.rng.randint(-2, 2)
        try:
            return ImageFont.truetype(font_path, random_size)
        except OSError as e:
            raise RuntimeError(
                f"字体加载失败：{font_path}（size={random_size}）。"
                "请检查字体文件是否存在、路径是否正确、文件是否损坏。"
            ) from e

    def draw_char_image(self, char, font):
        """生成单个字的带透明度旋转图片"""
        img_size = int(self.base_size * 2)
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        ink_color = (
            self.rng.randint(30, 50),
            self.rng.randint(30, 50),
            self.rng.randint(30, 50),
            self.rng.randint(220, 255)
        )

        # Pillow 旧版本没有 textbbox，回退到 textsize 保持兼容性
        if hasattr(draw, "textbbox"):
            text_bbox = draw.textbbox((0, 0), char, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        else:
            text_width, text_height = draw.textsize(char, font=font)
        x = (img_size - text_width) // 2
        y = (img_size - text_height) // 2

        draw.text((x, y), char, font=font, fill=ink_color)
        angle = self.rng.uniform(-3, 3)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=1)
        return img, text_width

    def _advance_line(self):
        """进入下一行，必要时自动翻页"""
        next_line_y = self.cursor_y + self.line_height
        if next_line_y > self.bottom_limit:
            self._load_new_page()
        else:
            self.cursor_y = next_line_y
            self.cursor_x = self.margin_left + self.rng.randint(0, 10)

    def _char_paste_y(self, char, base_y):
        """计算字符纵向粘贴位置"""
        offset_y = self.rng.randint(-3, 3)
        paste_y = base_y + offset_y - int(self.base_size * 0.3)

        if char in self.horizontal_chars:
            paste_y -= self.rng.randint(12, 15)
        elif char in self.bottom_punct:
            paste_y -= self.rng.randint(12, 18)

        return paste_y

    def _tokenize_text(self, text):
        """
        将文本切分为排版 token。
        规则：
        1) 保留换行符为独立 token；
        2) 破折号“——”和省略号“……”合并为不可拆分 token（满足国标“两字位置，中间不断开”）。
        """
        tokens = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '\n':
                tokens.append('\n')
                i += 1
                continue

            pair = text[i:i+2]
            if pair in {'——', '……'}:
                tokens.append(pair)
                i += 2
            else:
                tokens.append(ch)
                i += 1
        return tokens

    def _build_token(self, token):
        """构建 token 的字形与宽度信息"""
        glyphs = []
        width = 0
        for ch in token:
            font = self.get_random_font()
            char_img, char_w = self.draw_char_image(ch, font)
            kerning_factor = 0.76
            random_jitter = self.rng.randint(-3, 3)
            advance = max(1, int(char_w * kerning_factor) + random_jitter)
            glyphs.append({"char": ch, "img": char_img, "advance": advance})
            width += advance
        return {"text": token, "glyphs": glyphs, "width": width}

    def _draw_line_tokens(self, line_tokens):
        """将一行 token 绘制到当前页面"""
        if not line_tokens:
            return

        x = self.cursor_x
        for token in line_tokens:
            for glyph in token["glyphs"]:
                char = glyph["char"]
                paste_y = self._char_paste_y(char, self.cursor_y)
                self.current_image.paste(glyph["img"], (x, paste_y), glyph["img"])
                x += glyph["advance"]

    def _find_break_pos(self, combined_tokens):
        """
        在当前行+新 token 的组合中，寻找可接受的断行位置。
        返回 break_pos：前半部分留在当前行，后半部分移到下一行。
        """
        if len(combined_tokens) <= 1:
            return 1

        # 默认把最后一个 token（新 token）放到下一行
        default_pos = len(combined_tokens) - 1
        break_pos = default_pos

        # 避免下一行以行首禁则字符开头
        while break_pos > 0 and combined_tokens[break_pos]["text"] in self.no_line_start:
            break_pos -= 1

        # 避免当前行以行尾禁则字符结尾
        while break_pos > 0 and combined_tokens[break_pos - 1]["text"] in self.no_line_end:
            break_pos -= 1

        # 如果退无可退，使用默认断点（极端窄行时兜底）
        if break_pos == 0:
            break_pos = default_pos

        return break_pos

    def write_meta(self, meta_data):
        """
        写会议元信息，每个字段限制在独立矩形区域内。
        超出宽度自动换行，超出高度自动截断。
        """
        if len(self.pages) > 0:
            print("警告：尝试在非第一页写入元数据，已跳过。")
            return

        positions = self.config_front.get("meta_position", {})
        print("正在写入元数据...")
        # 这些字段通常不涉及标点禁则，保持原有逐字逻辑
        simple_fields = {"year", "month", "day", "chairperson", "recorder"}

        for key, text in meta_data.items():
            if key not in positions:
                continue

            cfg = positions[key]
            local_x = cfg["x"]
            local_y = cfg["y"]
            box_right = cfg["x"] + cfg["width"]
            box_bottom = cfg["y"] + cfg["height"]

            if key in simple_fields:
                for char in text:
                    if char == '\n':
                        local_x = cfg["x"]
                        local_y += self.line_height
                        continue

                    font = self.get_random_font()
                    char_img, char_w = self.draw_char_image(char, font)

                    kerning_factor = 0.76
                    actual_width = int(char_w * kerning_factor) + self.rng.randint(-1, 2)

                    if local_x + actual_width > box_right:
                        local_x = cfg["x"]
                        local_y += self.line_height

                    if local_y + self.line_height > box_bottom:
                        print(f"  字段 [{key}] 内容过长，已截断。")
                        break

                    offset_y = self.rng.randint(-2, 2)

                    if char in self.horizontal_chars:
                        paste_y = local_y + offset_y - int(self.base_size * 0.3)
                        paste_y -= self.rng.randint(12, 15)
                    elif char in self.bottom_punct:
                        paste_y = local_y + offset_y - int(self.base_size * 0.3)
                        paste_y -= self.rng.randint(12, 18)
                    else:
                        paste_y = local_y + offset_y - int(self.base_size * 0.3)

                    self.current_image.paste(char_img, (local_x, paste_y), char_img)

                    local_x += actual_width
                continue

            # 其余字段应用与正文一致的基础标点禁则断行
            max_line_width = cfg["width"]
            line_tokens = []
            line_width = 0
            truncated = False

            def flush_meta_line():
                nonlocal local_y, line_tokens, line_width, truncated
                if truncated:
                    return

                if local_y + self.line_height > box_bottom:
                    truncated = True
                    print(f"  字段 [{key}] 内容过长，已截断。")
                    return

                x = cfg["x"]
                for token in line_tokens:
                    for glyph in token["glyphs"]:
                        char = glyph["char"]
                        paste_y = self._char_paste_y(char, local_y)
                        self.current_image.paste(glyph["img"], (x, paste_y), glyph["img"])
                        x += glyph["advance"]

                line_tokens = []
                line_width = 0
                local_y += self.line_height

            tokens = self._tokenize_text(text)
            for char in tokens:
                if truncated:
                    break

                if char == '\n':
                    if line_tokens:
                        flush_meta_line()
                    else:
                        # 空行：直接下移一行
                        if local_y + self.line_height > box_bottom:
                            truncated = True
                            print(f"  字段 [{key}] 内容过长，已截断。")
                        else:
                            local_y += self.line_height
                    continue

                token = self._build_token(char)

                if line_width + token["width"] <= max_line_width:
                    line_tokens.append(token)
                    line_width += token["width"]
                    continue

                if not line_tokens:
                    # 单个 token 过宽：兜底直接占一行，避免死循环
                    line_tokens.append(token)
                    line_width += token["width"]
                    flush_meta_line()
                    continue

                combined = line_tokens + [token]
                break_pos = self._find_break_pos(combined)

                current_line = combined[:break_pos]
                carry_line = combined[break_pos:]

                line_tokens = current_line
                line_width = sum(t["width"] for t in line_tokens)
                flush_meta_line()

                if truncated:
                    break

                line_tokens = carry_line
                line_width = sum(t["width"] for t in line_tokens)

                while line_tokens and (line_width > max_line_width):
                    overflow_tokens = line_tokens
                    first = overflow_tokens[0]
                    line_tokens = [first]
                    line_width = first["width"]
                    flush_meta_line()
                    if truncated:
                        break
                    line_tokens = overflow_tokens[1:]
                    line_width = sum(t["width"] for t in line_tokens)

            if not truncated and line_tokens:
                flush_meta_line()

    def write_text(self, text):
        """
        写正文内容（含基础国标断行规则）：
        1) 点号/右半标号尽量不排在行首；
        2) 左半标号不排在行末；
        3) 破折号“——”、省略号“……”作为不可拆分 token，不跨行拆开。
        """
        print("正在写入正文...")
        max_line_width = self.width - self.margin_right

        line_tokens = []
        line_width = 0

        tokens = self._tokenize_text(text)
        for raw_token in tokens:
            if raw_token == '\n':
                self._draw_line_tokens(line_tokens)
                line_tokens = []
                line_width = 0
                self._advance_line()
                continue

            token = self._build_token(raw_token)

            if self.cursor_x + line_width + token["width"] <= max_line_width:
                line_tokens.append(token)
                line_width += token["width"]
                continue

            if not line_tokens:
                # 当前行为空且 token 仍超宽：兜底直接绘制，避免死循环
                line_tokens.append(token)
                self._draw_line_tokens(line_tokens)
                line_tokens = []
                line_width = 0
                self._advance_line()
                continue

            combined = line_tokens + [token]
            break_pos = self._find_break_pos(combined)

            current_line = combined[:break_pos]
            carry_line = combined[break_pos:]

            self._draw_line_tokens(current_line)
            self._advance_line()

            line_tokens = carry_line
            line_width = sum(t["width"] for t in line_tokens)

            # 如果“携带到下一行”的 token 仍然超宽，分次写入（极端情况兜底）
            while line_tokens and (self.cursor_x + line_width > max_line_width):
                first = line_tokens[0]
                self._draw_line_tokens([first])
                self._advance_line()
                line_tokens = line_tokens[1:]
                line_width = sum(t["width"] for t in line_tokens)

        self._draw_line_tokens(line_tokens)

    def save_all(self, output_prefix="output", output_format="jpg"):
        """保存所有生成的页面为单独的图片文件"""
        if self.current_image:
            self.current_image = self.current_image.filter(ImageFilter.GaussianBlur(radius=0.5))
            self.pages.append(self.current_image)
            self.current_image = None

        folder_path = "./output"

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        for i, page in enumerate(self.pages):
            filename = f"{folder_path}/{output_prefix}_page_{i+1}.{output_format}"
            page.save(filename)
            print(f"已保存: {filename}")

    def save_pdf(self, output_prefix="output", resolution=150):
        """将所有页面合并为一个 PDF 文件，使用 Pillow 内置 PDF 导出

        Args:
            output_prefix: 输出文件名前缀，PDF 文件名为 {prefix}.pdf
            resolution: PDF 分辨率（DPI），默认 150

        Returns:
            str: 生成的 PDF 文件路径
        """
        if self.current_image:
            self.current_image = self.current_image.filter(ImageFilter.GaussianBlur(radius=0.5))
            self.pages.append(self.current_image)
            self.current_image = None

        if not self.pages:
            print("【警告】没有可导出的页面，跳过 PDF 生成。")
            return None

        folder_path = "./output"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        filename = f"{folder_path}/{output_prefix}.pdf"
        self.pages[0].save(
            filename, "PDF",
            save_all=True,
            append_images=self.pages[1:],
            resolution=resolution,
        )
        print(f"已保存 PDF: {filename}")
        return filename


def load_content(filename):
    """读取正文文件"""
    if not os.path.exists(filename):
        print(f"【错误】找不到正文文件: {filename}。请检查 `content_file` 路径是否正确。")
        return ""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except PermissionError:
        print(f"【错误】没有权限读取正文文件: {filename}")
    except UnicodeDecodeError:
        print(f"【错误】正文文件编码不是 UTF-8: {filename}")
    except Exception as e:
        print(f"【错误】读取正文文件失败: {filename} ({e})")
    return ""


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="手写风格会议记录生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python handwrite.py                    # 使用默认 config.yaml
  python handwrite.py -c my.yaml         # 指定配置文件
  python handwrite.py --paper-type default # 显式指定纸张类型
  python handwrite.py --meta-only        # 仅预览元数据效果（不写正文）
  python handwrite.py --check-config     # 仅检查配置与资源，不生成图片
  python handwrite.py --debug-box        # 输出图片附带布局调试框
  python handwrite.py --seed 42          # 固定随机种子，结果可复现
  python handwrite.py --format pdf        # 输出为 PDF 文件
        """
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)"
    )
    parser.add_argument(
        "--paper-type",
        default=None,
        help="纸张类型（覆盖配置文件中的 paper_type）"
    )
    parser.add_argument(
        "--meta-only",
        action="store_true",
        help="仅写入元数据，不写正文"
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="仅检查配置与资源有效性，不生成图片"
    )
    parser.add_argument(
        "--debug-box",
        action="store_true",
        help="在输出图中绘制正文区域/元数据区域调试框"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="固定随机种子（用于可复现结果）"
    )
    parser.add_argument(
        "--format",
        default=None,
        choices=["jpg", "png", "pdf"],
        help="输出格式 (覆盖配置文件中的 output.format)"
    )
    return parser.parse_args()


def load_config(config_path):
    """加载 YAML 配置文件"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到配置文件: {config_path}")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except PermissionError as e:
        raise PermissionError(f"没有权限读取配置文件: {config_path}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析失败，请检查语法: {config_path}\n{e}") from e

    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ValueError("配置文件根节点必须是映射（key-value）。")
    return config


def get_available_paper_types(presets):
    """返回可选纸张类型列表（排序后）"""
    return sorted(presets.keys())


def _normalize_paper_presets(raw_presets, source_name):
    """校验并归一化纸张预设对象"""
    if not isinstance(raw_presets, dict):
        raise ValueError(f"{source_name} 必须是对象（key 为纸张类型，value 为配置）。")

    normalized = {}
    for name, preset in raw_presets.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{source_name} 中存在非法纸张类型名（必须是非空字符串）。")
        if not isinstance(preset, dict):
            raise ValueError(f"{source_name}.{name} 必须是对象。")

        front = preset.get("front")
        back = preset.get("back")
        if not isinstance(front, dict) or not isinstance(back, dict):
            raise ValueError(f"{source_name}.{name} 必须同时包含 `front` 和 `back` 对象。")

        normalized[name.strip()] = copy.deepcopy(preset)

    return normalized


def _resolve_preset_bg_paths(preset, base_dir):
    """将预设中的相对 bg_file 解析为绝对路径"""
    resolved = copy.deepcopy(preset)
    for side in ("front", "back"):
        layout = resolved.get(side)
        if not isinstance(layout, dict):
            continue
        bg = layout.get("bg_file")
        if not isinstance(bg, str) or not bg.strip():
            continue
        if not os.path.isabs(bg):
            layout["bg_file"] = os.path.normpath(os.path.join(base_dir, bg))
    return resolved


def _resolve_path_from_base(path_value, base_dir):
    if not isinstance(path_value, str) or not path_value.strip():
        return path_value
    if os.path.isabs(path_value):
        return os.path.normpath(path_value)
    return os.path.normpath(os.path.join(base_dir, path_value))


def normalize_config_paths(config, config_path):
    """
    将配置中的相对路径统一解析为“相对配置文件目录”。
    主要处理：
    - fonts
    - content_file
    - config.paper_presets.*.front/back.bg_file
    """
    normalized = copy.deepcopy(config)
    config_dir = os.path.dirname(os.path.abspath(config_path))

    fonts = normalized.get("fonts")
    if isinstance(fonts, list):
        normalized["fonts"] = [
            _resolve_path_from_base(fp, config_dir) if isinstance(fp, str) else fp
            for fp in fonts
        ]

    content_file = normalized.get("content_file")
    if isinstance(content_file, str):
        normalized["content_file"] = _resolve_path_from_base(content_file, config_dir)

    custom_presets = normalized.get("paper_presets")
    if isinstance(custom_presets, dict):
        resolved_presets = {}
        for name, preset in custom_presets.items():
            if isinstance(preset, dict):
                resolved_presets[name] = _resolve_preset_bg_paths(preset, config_dir)
            else:
                resolved_presets[name] = preset
        normalized["paper_presets"] = resolved_presets

    return normalized


def load_paper_presets_registry(presets_path=PAPER_PRESETS_FILE):
    """
    从 paper_presets.yaml 读取纸张注册表。
    兼容两种格式：
    1) 根节点直接为纸张映射
    2) 根节点包含 `paper_presets` 字段
    """
    if not os.path.exists(presets_path):
        return {}

    registry = load_config(presets_path)
    if "paper_presets" in registry:
        registry = registry.get("paper_presets")
        if registry is None:
            return {}

    normalized = _normalize_paper_presets(registry, f"`{presets_path}`")
    registry_dir = os.path.dirname(os.path.abspath(presets_path))
    resolved = {}
    for name, preset in normalized.items():
        resolved[name] = _resolve_preset_bg_paths(preset, registry_dir)
    return resolved


def build_paper_presets(config):
    """
    构建最终可用纸张预设：
    - 内置 DEFAULT_PAPER_PRESETS 始终可用
    - 自动加载 paper_presets.yaml 中的纸张注册
    - 可通过 config.paper_presets 临时追加/覆盖
    """
    presets = copy.deepcopy(DEFAULT_PAPER_PRESETS)

    registry_presets = load_paper_presets_registry()
    presets.update(registry_presets)

    custom_presets = config.get("paper_presets")
    if custom_presets is None:
        return presets

    normalized_custom = _normalize_paper_presets(custom_presets, "`config.paper_presets`")
    presets.update(normalized_custom)

    return presets


def resolve_paper_type(config, paper_type_override=None):
    """解析最终纸张类型：命令行优先，其次配置，最后默认值"""
    paper_type = paper_type_override if paper_type_override else config.get("paper_type", DEFAULT_PAPER_TYPE)
    if not isinstance(paper_type, str) or not paper_type.strip():
        raise ValueError("`paper_type` 必须是非空字符串。")
    return paper_type.strip()


def resolve_paper_layout(config, paper_type_override=None):
    """
    解析当前使用的纸张配置。
    返回：paper_type, config_front, config_back, all_presets
    """
    all_presets = build_paper_presets(config)
    paper_type = resolve_paper_type(config, paper_type_override=paper_type_override)

    if paper_type not in all_presets:
        choices = ", ".join(get_available_paper_types(all_presets))
        raise ValueError(f"未知纸张类型 `{paper_type}`。可选值：{choices}")

    selected = all_presets[paper_type]
    front = selected.get("front")
    back = selected.get("back")
    if not isinstance(front, dict) or not isinstance(back, dict):
        raise ValueError(f"纸张类型 `{paper_type}` 配置非法：必须包含 front/back 对象。")

    return paper_type, front, back, all_presets


def validate_config(config, config_front, config_back, paper_type):
    """校验配置与资源，返回 (warnings, errors)"""
    warnings = []
    errors = []

    fonts = config.get("fonts", [os.path.join(PROJECT_DIR, "fonts", "font0.ttf")])
    if not isinstance(fonts, list) or not fonts:
        errors.append("`fonts` 必须是非空列表。")
    else:
        for fp in fonts:
            if not isinstance(fp, str) or not fp.strip():
                errors.append("`fonts` 列表中存在非法路径（空或非字符串）。")
                continue
            if not os.path.exists(fp):
                errors.append(f"字体文件不存在: {fp}")

    # 正文来源检查
    has_content_file = "content_file" in config
    has_inline_content = "content" in config
    if has_content_file and has_inline_content:
        warnings.append("同时配置了 `content_file` 和 `content`，将优先读取 `content_file`。")

    if has_content_file:
        cf = config.get("content_file")
        if not isinstance(cf, str) or not cf.strip():
            errors.append("`content_file` 必须是非空字符串路径。")
        elif not os.path.exists(cf):
            errors.append(f"正文文件不存在: {cf}")

    # 输出格式检查
    output_cfg = config.get("output", {})
    if output_cfg and not isinstance(output_cfg, dict):
        errors.append("`output` 必须是对象。")
    else:
        fmt = output_cfg.get("format", "jpg")
        if not isinstance(fmt, str):
            errors.append("`output.format` 必须是字符串。")
        elif fmt.lower() not in {"jpg", "jpeg", "png", "pdf"}:
            warnings.append(f"输出格式 `{fmt}` 未验证，建议使用 jpg/jpeg/png/pdf。")

    if "paper_type" in config and not isinstance(config.get("paper_type"), str):
        errors.append("`paper_type` 必须是字符串。")

    for side_name, layout in (("front", config_front), ("back", config_back)):
        for field in LAYOUT_REQUIRED_FIELDS:
            if field not in layout:
                errors.append(f"`paper_type={paper_type}` 的 `{side_name}` 缺少字段 `{field}`。")

        bg_file = layout.get("bg_file")
        if "bg_file" in layout and (not isinstance(bg_file, str) or not bg_file.strip()):
            errors.append(f"`paper_type={paper_type}` 的 `{side_name}.bg_file` 必须是非空字符串。")

        for f in ("start_y", "line_spacing", "font_size", "left_margin", "right_margin", "bottom_margin"):
            if f in layout and not isinstance(layout[f], int):
                errors.append(f"`paper_type={paper_type}` 的 `{side_name}.{f}` 必须是整数。")

        if isinstance(layout.get("line_spacing"), int) and layout["line_spacing"] <= 0:
            errors.append(f"`paper_type={paper_type}` 的 `{side_name}.line_spacing` 必须大于 0。")
        if isinstance(layout.get("font_size"), int) and layout["font_size"] <= 0:
            errors.append(f"`paper_type={paper_type}` 的 `{side_name}.font_size` 必须大于 0。")

    # front 的元数据坐标必须存在并完整
    meta_positions = config_front.get("meta_position")
    if not isinstance(meta_positions, dict) or not meta_positions:
        errors.append(f"`paper_type={paper_type}` 的 `front.meta_position` 必须是非空对象。")
        meta_positions = {}

    for key, box in meta_positions.items():
        if not isinstance(box, dict):
            errors.append(f"`paper_type={paper_type}` 的 `meta_position.{key}` 必须是对象。")
            continue
        for f in ("x", "y", "width", "height"):
            if f not in box:
                errors.append(f"`paper_type={paper_type}` 的 `meta_position.{key}` 缺少字段 `{f}`")
                continue
            if not isinstance(box[f], int):
                errors.append(f"`paper_type={paper_type}` 的 `meta_position.{key}.{f}` 必须是整数")
        if "width" in box and isinstance(box["width"], int) and box["width"] <= 0:
            errors.append(f"`paper_type={paper_type}` 的 `meta_position.{key}.width` 必须大于 0")
        if "height" in box and isinstance(box["height"], int) and box["height"] <= 0:
            errors.append(f"`paper_type={paper_type}` 的 `meta_position.{key}.height` 必须大于 0")

    # 背景图检查与范围校验
    for side_name, layout in (("front", config_front), ("back", config_back)):
        cfg_name = f"{paper_type}.{side_name}"
        bg = layout.get("bg_file")
        if not isinstance(bg, str) or not bg.strip():
            continue

        if not os.path.exists(bg):
            warnings.append(f"{cfg_name} 背景图不存在: {bg}（运行时将使用空白背景兜底）")
            continue

        try:
            with Image.open(bg) as im:
                w, h = im.size
        except Exception as e:
            errors.append(f"{cfg_name} 背景图无法读取: {bg} ({e})")
            continue

        numeric_fields = ("left_margin", "right_margin", "bottom_margin", "start_y")
        if not all(isinstance(layout.get(f), int) for f in numeric_fields):
            continue

        lm = layout["left_margin"]
        rm = layout["right_margin"]
        by = layout["bottom_margin"]
        sy = layout["start_y"]
        if lm + rm >= w:
            errors.append(f"{cfg_name} 左右边距之和超过页面宽度。")
        if sy >= h - by:
            warnings.append(f"{cfg_name} start_y 接近或超过可写底部，可能没有正文空间。")

        if side_name == "front":
            for key, box in meta_positions.items():
                if not isinstance(box, dict):
                    continue
                coords = ("x", "y", "width", "height")
                if not all(isinstance(box.get(f), int) for f in coords):
                    continue
                x = box["x"]
                y = box["y"]
                bw = box["width"]
                bh = box["height"]
                if x < 0 or y < 0 or x + bw > w or y + bh > h:
                    errors.append(f"`paper_type={paper_type}` 的 `meta_position.{key}` 超出背景图范围（{w}x{h}）。")

    return warnings, errors


# --- 运行部分 ---
if __name__ == "__main__":
    args = parse_args()

    if yaml is None:
        print("【错误】需要 PyYAML，请运行: pip install pyyaml")
        exit(1)

    try:
        # 加载配置
        print(f"正在读取配置文件 {args.config} ...")
        config = load_config(args.config)
        config = normalize_config_paths(config, args.config)
    except Exception as e:
        print(f"【错误】配置读取失败：{e}")
        sys.exit(1)

    try:
        paper_type, config_front, config_back, all_presets = resolve_paper_layout(
            config,
            paper_type_override=args.paper_type
        )
    except Exception as e:
        print(f"【错误】纸张类型配置错误：{e}")
        sys.exit(1)

    print(f"使用纸张类型: {paper_type}")

    warnings, errors = validate_config(config, config_front, config_back, paper_type)
    for w in warnings:
        print(f"【警告】{w}")
    if errors:
        print("【错误】配置检查未通过：")
        for i, e in enumerate(errors, 1):
            print(f"  {i}. {e}")
        sys.exit(1)
    if args.check_config:
        choices = ", ".join(get_available_paper_types(all_presets))
        print(f"配置检查通过。可选纸张类型：{choices}")
        sys.exit(0)

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    if args.seed is not None:
        print(f"已设置随机种子: {args.seed}")

    # 字体路径
    fonts = config.get("fonts", [os.path.join(PROJECT_DIR, "fonts", "font0.ttf")])

    # 获取正文内容
    content = ""
    if "content_file" in config:
        content = load_content(config["content_file"])
    elif "content" in config:
        content = config["content"]

    if not content:
        print("警告：正文内容为空！")

    # 元数据
    meta_info = config.get("meta", {})

    if not meta_info:
        print("警告：元数据为空！请检查配置文件。")

    # 输出配置
    output_config = config.get("output", {})
    output_prefix = output_config.get("prefix", "meeting_record")
    # 命令行 --format 参数优先级高于配置文件
    output_format = args.format if args.format else output_config.get("format", "jpg")

    try:
        writer = HandWriter(
            fonts,
            config_front,
            config_back,
            debug_box=args.debug_box,
            rng=rng,
        )

        if meta_info:
            writer.write_meta(meta_info)

        if not args.meta_only and content:
            writer.write_text(content.strip())

        if output_format.lower() == "pdf":
            # PDF 模式：先保存单页图片，再合并为 PDF
            writer.save_all(output_prefix, "jpg")
            writer.save_pdf(output_prefix)
        else:
            writer.save_all(output_prefix, output_format)

    except Exception as e:
        print(f"运行出错: {e}")
        import traceback
        traceback.print_exc()
