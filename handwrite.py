import random
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

# ================= 配置区域 =================

# --- 首页 (正面) 配置：对应 page1.jpg ---
CONFIG_FRONT = {
    "bg_file": "page1.jpg",   # 背景文件名
    "start_y": 567,           # 【关键】正面正文第一行文字的起始纵坐标 (避开表头)
    "line_spacing": 71,       # 行高
    "font_size": 50,          # 字体大小
    "left_margin": 150,       # 左边距
    "right_margin": 130,      # 右边距
    "bottom_margin": 150,     # 底部留白
    
    # 会议元数据坐标配置：每个字段为独立矩形区域 (x, y, width, height)
    # x, y: 字段起始坐标
    # width: 字段区域宽度（超出自动换行）
    # height: 字段区域高度（超出自动截断）
    "meta_position": {
        "year":        {"x": 818, "y": 133, "width": 80,  "height": 50},   # 年
        "month":       {"x": 910, "y": 138, "width": 70,  "height": 50},   # 月
        "day":         {"x": 985, "y": 138, "width": 70,  "height": 50},  # 日
        "location":    {"x": 587, "y": 235, "width": 300, "height": 80},   # 地点
        "subject":     {"x": 303, "y": 351, "width": 700, "height": 120},  # 会议名称
        "note_taker":  {"x": 888, "y": 355, "width": 200, "height": 80},   # 记录人
        "chairperson": {"x": 900, "y": 273, "width": 200, "height": 80},   # 主持人
        "attendees":   {"x": 309, "y": 450, "width": 800, "height": 150},  # 出席人
    }
}

# --- 背面 (及后续页) 配置：对应 page2.jpg ---
CONFIG_BACK = {
    "bg_file": "page2.jpg",   
    "start_y": 215,           # 背面起始位置较靠上
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
        
        # 初始化第一页
        self._load_new_page()

    def _load_new_page(self):
        """加载新页面的逻辑"""
        # 暂存当前页
        if self.current_image is not None:
            self.current_image = self.current_image.filter(ImageFilter.GaussianBlur(radius=0.5))
            self.pages.append(self.current_image)
        
        current_page_index = len(self.pages)
        
        # 判断正反面
        if current_page_index % 2 == 0:
            config = self.config_front
            print(f"正在创建第 {current_page_index + 1} 页 (正面)...")
        else:
            config = self.config_back
            print(f"正在创建第 {current_page_index + 1} 页 (背面)...")

        # 加载背景
        try:
            self.current_image = Image.open(config["bg_file"]).convert("RGB")
        except FileNotFoundError:
            # 容错：如果找不到图片，创建一个白底图片
            print(f"警告：找不到 {config['bg_file']}，使用空白背景。")
            self.current_image = Image.new("RGB", (1240, 1754), (255, 255, 255))
            
        self.width, self.height = self.current_image.size
        self.current_draw = ImageDraw.Draw(self.current_image)
        
        # 更新参数
        self.base_size = config["font_size"]
        self.line_height = config["line_spacing"]
        self.margin_left = config["left_margin"]
        self.margin_right = config["right_margin"]
        self.bottom_limit = self.height - config["bottom_margin"]
        
        # 重置正文光标
        if current_page_index % 2 == 0:
            self.cursor_x = self.margin_left + 80 # 首行缩进
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
        
        # 墨水颜色随机（深蓝/黑色系）
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

    def write_meta(self, meta_data):
        """
        写会议元信息，每个字段限制在独立矩形区域内。
        超出宽度自动换行，超出高度自动截断。
        """
        # 确保只在第一页写
        if len(self.pages) > 0:
            print("警告：尝试在非第一页写入元数据，已跳过。")
            return

        positions = self.config_front.get("meta_position", {})
        print("正在写入元数据...")

        for key, text in meta_data.items():
            if key not in positions:
                continue

            cfg = positions[key]
            # 每个字段独立的行光标
            local_x = cfg["x"]
            local_y = cfg["y"]
            box_right = cfg["x"] + cfg["width"]
            box_bottom = cfg["y"] + cfg["height"]

            for char in text:
                # 换行符：强制换行
                if char == '\n':
                    local_x = cfg["x"]
                    local_y += self.line_height
                    continue

                font = self.get_random_font()
                char_img, char_w = self.draw_char_image(char, font)

                # 字实际占宽 = 字宽 * 字距系数 + 随机抖动
                kerning_factor = 0.75
                actual_width = int(char_w * kerning_factor) + random.randint(-1, 2)

                # 超出该字段右边界 → 换到下一行
                if local_x + actual_width > box_right:
                    local_x = cfg["x"]
                    local_y += self.line_height

                # 超出该字段下边界 → 截断，停止该字段
                if local_y + self.line_height > box_bottom:
                    print(f"  字段 [{key}] 内容过长，已截断。")
                    break

                # 上下抖动 + 基线偏移
                offset_y = random.randint(-2, 2)
                paste_y = local_y + offset_y - int(self.base_size * 0.3)

                # 粘贴
                self.current_image.paste(char_img, (local_x, paste_y), char_img)

                local_x += actual_width


    def write_text(self, text):
        """写正文内容"""
        print("正在写入正文...")
        for char in text:
            # --- 换行与翻页逻辑 ---
            if char == '\n' or self.cursor_x > self.width - self.margin_right:
                next_line_y = self.cursor_y + self.line_height
                
                if next_line_y > self.bottom_limit:
                    self._load_new_page() # 翻页
                else:
                    self.cursor_y = next_line_y
                    self.cursor_x = self.margin_left + random.randint(0, 10)

            if char == '\n': continue

            # --- 写字逻辑 ---
            font = self.get_random_font()
            char_img, char_w = self.draw_char_image(char, font)
            
            offset_y = random.randint(-3, 3) 
            paste_y = self.cursor_y + offset_y - int(self.base_size * 0.3) 

            self.current_image.paste(char_img, (self.cursor_x, paste_y), char_img)
            
            kerning_factor = 0.70 
            random_jitter = random.randint(-3, 3)
            move_distance = int(char_w * kerning_factor) + random_jitter
            self.cursor_x += move_distance

    def save_all(self, output_prefix="output"):
        # 保存最后一张
        if self.current_image:
            self.current_image = self.current_image.filter(ImageFilter.GaussianBlur(radius=0.5))
            self.pages.append(self.current_image)
            self.current_image = None

        folder_path = "./output"

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        for i, page in enumerate(self.pages):
            filename = f"{folder_path}/{output_prefix}_page_{i+1}.jpg"
            page.save(filename)
            print(f"已保存: {filename}")

# 读取内容
def load_content(filename):
    """读取正文文件"""
    if not os.path.exists(filename):
        print(f"【错误】找不到正文文件: {filename}")
        return ""
    
    # encoding='utf-8' 防止中文乱码
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()

def load_meta(filename):
    """
    读取元数据文件
    解析格式： key: value
    """
    if not os.path.exists(filename):
        print(f"【错误】找不到元数据文件: {filename}")
        return {}
    
    meta_data = {}
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            # 跳过空行或注释
            if not line or line.startswith("#"):
                continue
            
            # 按第一个冒号分割 (兼容英文冒号: 和 中文冒号：)
            if ":" in line:
                parts = line.split(":", 1)
            elif "：" in line:
                parts = line.split("：", 1)
            else:
                continue
                
            key = parts[0].strip()
            value = parts[1].strip()
            
            if key and value:
                meta_data[key] = value
                
    return meta_data

# --- 运行部分 ---
if __name__ == "__main__":
    # 替换为你实际的字体路径
    fonts = ["./fonts/font0.ttf"]
    
    # 2. 读取外部文件
    print("正在读取 content.txt ...")
    content = load_content("content.txt")
    
    print("正在读取 meta.txt ...")
    meta_info = load_meta("meta.txt")
    
    # 简单的检查
    if not content:
        print("警告：正文内容为空！")
    
    if not meta_info:
        print("警告：元数据为空！请检查 meta.txt 格式 (key: value)")

    try:
        writer = HandWriter(fonts, CONFIG_FRONT, CONFIG_BACK)
        
        # 步骤1：先写元信息 (只会写在第一页)
        if meta_info:
            writer.write_meta(meta_info)
        
        # 步骤2：再写正文 (会自动换行、翻页)
        if content:
            writer.write_text(content.strip())
        
        writer.save_all("meeting_record_auto")
        
    except Exception as e:
        print(f"运行出错: {e}")
        import traceback
        traceback.print_exc()
