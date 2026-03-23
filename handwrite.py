import random
import os
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    import yaml
except ImportError:
    yaml = None

# ================= 配置区域 =================

# --- 首页 (正面) 配置：对应 page1.jpg ---
CONFIG_FRONT = {
    "bg_file": "page1.jpg",
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
}

# --- 背面 (及后续页) 配置：对应 page2.jpg ---
CONFIG_BACK = {
    "bg_file": "page2.jpg",
    "start_y": 215,
    "line_spacing": 71,
    "font_size": 50,
    "left_margin": 130,
    "right_margin": 150,
    "bottom_margin": 150,
}

# ===========================================

class HandWriter:
    def __init__(self, font_paths, config_front, config_back):
        self.font_paths = font_paths
        self.config_front = config_front
        self.config_back = config_back

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
        self.bottom_punct = {'，', '。', '、', '；'}

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

    def _load_new_page(self):
        """加载新页面的逻辑"""
        if self.current_image is not None:
            self.current_image = self.current_image.filter(ImageFilter.GaussianBlur(radius=0.5))
            self.pages.append(self.current_image)

        current_page_index = len(self.pages)

        if current_page_index % 2 == 0:
            config = self.config_front
            print(f"正在创建第 {current_page_index + 1} 页 (正面)...")
        else:
            config = self.config_back
            print(f"正在创建第 {current_page_index + 1} 页 (背面)...")

        try:
            self.current_image = Image.open(config["bg_file"]).convert("RGB")
        except FileNotFoundError:
            print(f"警告：找不到 {config['bg_file']}，使用空白背景。")
            self.current_image = Image.new("RGB", (1240, 1754), (255, 255, 255))

        self.width, self.height = self.current_image.size
        self.current_draw = ImageDraw.Draw(self.current_image)

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
        font_path = random.choice(self.font_paths)
        random_size = self.base_size + random.randint(-2, 2)
        return ImageFont.truetype(font_path, random_size)

    def draw_char_image(self, char, font):
        """生成单个字的带透明度旋转图片"""
        img_size = int(self.base_size * 2)
        img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        ink_color = (
            random.randint(30, 50),
            random.randint(30, 50),
            random.randint(30, 50),
            random.randint(220, 255)
        )

        text_bbox = draw.textbbox((0, 0), char, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        x = (img_size - text_width) // 2
        y = (img_size - text_height) // 2

        draw.text((x, y), char, font=font, fill=ink_color)
        angle = random.uniform(-3, 3)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=1)
        return img, text_width

    def _advance_line(self):
        """进入下一行，必要时自动翻页"""
        next_line_y = self.cursor_y + self.line_height
        if next_line_y > self.bottom_limit:
            self._load_new_page()
        else:
            self.cursor_y = next_line_y
            self.cursor_x = self.margin_left + random.randint(0, 10)

    def _char_paste_y(self, char, base_y):
        """计算字符纵向粘贴位置"""
        offset_y = random.randint(-3, 3)
        paste_y = base_y + offset_y - int(self.base_size * 0.3)

        if char in self.horizontal_chars:
            paste_y -= random.randint(12, 15)
        elif char in self.bottom_punct:
            paste_y -= random.randint(12, 18)

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
            random_jitter = random.randint(-3, 3)
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

        for key, text in meta_data.items():
            if key not in positions:
                continue

            cfg = positions[key]
            local_x = cfg["x"]
            local_y = cfg["y"]
            box_right = cfg["x"] + cfg["width"]
            box_bottom = cfg["y"] + cfg["height"]

            for char in text:
                if char == '\n':
                    local_x = cfg["x"]
                    local_y += self.line_height
                    continue

                font = self.get_random_font()
                char_img, char_w = self.draw_char_image(char, font)

                kerning_factor = 0.76
                actual_width = int(char_w * kerning_factor) + random.randint(-1, 2)

                if local_x + actual_width > box_right:
                    local_x = cfg["x"]
                    local_y += self.line_height

                if local_y + self.line_height > box_bottom:
                    print(f"  字段 [{key}] 内容过长，已截断。")
                    break

                offset_y = random.randint(-2, 2)

                if char in self.horizontal_chars:
                    paste_y = local_y + offset_y - int(self.base_size * 0.3)
                    paste_y -= random.randint(12, 15)
                elif char in self.bottom_punct:
                    paste_y = local_y + offset_y - int(self.base_size * 0.3)
                    paste_y -= random.randint(12, 18)
                else:
                    paste_y = local_y + offset_y - int(self.base_size * 0.3)

                self.current_image.paste(char_img, (local_x, paste_y), char_img)

                local_x += actual_width

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
        """保存所有生成的页面"""
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


def load_content(filename):
    """读取正文文件"""
    if not os.path.exists(filename):
        print(f"【错误】找不到正文文件: {filename}")
        return ""
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="手写风格会议记录生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python handwrite.py                    # 使用默认 config.yaml
  python handwrite.py -c my.yaml         # 指定配置文件
  python handwrite.py --meta-only        # 仅预览元数据效果（不写正文）
        """
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)"
    )
    parser.add_argument(
        "--meta-only",
        action="store_true",
        help="仅写入元数据，不写正文"
    )
    return parser.parse_args()


def load_config(config_path):
    """加载 YAML 配置文件"""
    if not os.path.exists(config_path):
        print(f"【错误】找不到配置文件: {config_path}")
        exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config


# --- 运行部分 ---
if __name__ == "__main__":
    args = parse_args()

    if yaml is None:
        print("【错误】需要 PyYAML，请运行: pip install pyyaml")
        exit(1)

    # 加载配置
    print(f"正在读取配置文件 {args.config} ...")
    config = load_config(args.config)

    # 字体路径
    fonts = config.get("fonts", ["./fonts/font0.ttf"])

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
    output_format = output_config.get("format", "jpg")

    try:
        writer = HandWriter(fonts, CONFIG_FRONT, CONFIG_BACK)

        if meta_info:
            writer.write_meta(meta_info)

        if not args.meta_only and content:
            writer.write_text(content.strip())

        writer.save_all(output_prefix, output_format)

    except Exception as e:
        print(f"运行出错: {e}")
        import traceback
        traceback.print_exc()
