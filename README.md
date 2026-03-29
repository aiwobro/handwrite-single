# handwrite

手写风格会议记录生成器 — 将纯文本内容渲染到会议记录纸背景图上，模拟真实手写效果。

## 功能特性

- 支持会议元数据与正文的手写风格渲染
- 支持多字体随机混排、轻微旋转和字距抖动
- 支持自动换行、自动翻页（正反面模板交替）
- 提供 Flask Web 页面，支持在线填写表单并生成预览
- Web 端支持“生成中”进度动画预览区
- Web 端支持缩略图预览、点击大图、左右切换、单张保存与一键保存全部
- Web 页面针对桌面/平板/手机做了响应式布局优化
- 正文支持基础中文标点禁则排版（参考 `GB/T 15834-2011`）
  - 点号和右半标号尽量不出现在行首
  - 左半标号尽量不出现在行尾
  - `——`（破折号）与 `……`（省略号）作为不可拆分单元，不跨行拆开

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 配置

复制示例配置文件并修改：

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入你的元数据和内容
```

配置文件支持两种正文来源：
- `content_file`: 指定外部文本文件路径（适合长文本）
- `content`: 直接写在 YAML 中（适合短文本）

### 2. 运行

```bash
python handwrite.py                    # 使用默认 config.yaml
python handwrite.py -c my.yaml          # 指定其他配置文件
python handwrite.py --meta-only         # 仅写入元数据（预览用）
python handwrite.py --check-config      # 仅检查配置与资源，不生成图片
python handwrite.py --debug-box         # 输出图片附带布局调试框
python handwrite.py --seed 42           # 固定随机种子，结果可复现

# 如果你在 conda 环境中，也可用：
conda run -n <你的环境名> python handwrite.py -c config.yaml
```

### 3. 输出

生成的图片保存在 `./output/` 目录下。

## Web 方式（Flask）

项目提供了网页入口，用户可以填写会议元数据与正文并在线生成结果图片。

### 启动

```bash
python app.py
```

启动后访问：`http://127.0.0.1:5000`

### 使用流程

1. 在页面填写会议元数据（日期、地点、标题、主持人等）与正文。
2. 点击“生成手写图片”。
3. 页面会先展示“图片正在生成中”的进度动画区域。
4. 图片返回后会显示多页缩略图；点击缩略图可打开大图预览。
5. 在大图模式下可用左右箭头（或键盘方向键）切换上一张/下一张。
6. 支持“保存本页”“保存此图”以及“一键保存全部”（浏览器可能提示允许多文件下载）。

### Web 端说明

- 生成结果文件保存在 `./output/` 目录。
- Web 入口当前固定输出为 `jpg`，并使用随机前缀（形如 `web_xxxxx_page_1.jpg`）。
- 开发模式默认监听 `127.0.0.1:5000`，并启用 `debug=True`（仅建议本地开发使用）。

## 常用参数

- `--check-config`：运行前检查字体、背景图、正文来源、布局范围等配置问题。
- `--debug-box`：在页面中绘制正文区域、基线和首页元数据框，便于快速调坐标。
- `--seed <int>`：设置随机种子，保证同一输入可复现相同风格输出。

## 标点排版规则说明

当前版本在正文排版（`write_text`）中实现了基础国标断行规则：

- 行首禁则：逗号、句号、顿号、分号、冒号、问号、叹号及右半括号/引号等不应出现在行首
- 行尾禁则：左半括号/引号等不应出现在行尾
- 不可拆分：`——`、`……` 不会被拆到两行

实现方式为“先分词(token)并计算行宽，再按禁则选择断点，最后绘制”。

注意：
- 正文区域（`write_text`）默认启用上述规则
- 元数据区域（`write_meta`）中，`venue` / `meeting_title` / `attendees` 也启用同样规则
- `year` / `month` / `day` / `chairperson` / `recorder` 保持原逐字写入逻辑（通常不涉及标点断行）

## 配置文件格式 (config.yaml)

```yaml
# 会议元数据
meta:
  year: "2025"
  month: "11"
  day: "23"
  venue: "会议室A"
  meeting_title: "关于2025年第三季度项目进度总结会议"
  chairperson: "张三"
  recorder: "李四"
  attendees: "王五，赵六"

# 正文：指定外部文件
content_file: "content.txt"

# 或者直接写在这里（适合内容短）
# content: |
#   本次会议主要讨论了关于下季度项目推进的相关事宜。

# 输出配置
output:
  prefix: "meeting_record"   # 输出文件名前缀
  format: "jpg"              # 输出格式（jpg / png）

# 字体路径（可选，默认使用内嵌配置）
fonts:
  - "./fonts/font0.ttf"
```

## 布局配置说明

脚本顶部的 `CONFIG_FRONT` / `CONFIG_BACK` 控制排版：

| 参数 | 说明 |
|------|------|
| `bg_file` | 背景图文件名 |
| `start_y` | 正文第一行起始纵坐标 |
| `line_spacing` | 行高 |
| `font_size` | 字体大小 |
| `left_margin` / `right_margin` | 左右边距 |
| `bottom_margin` | 底部留白 |

### 元数据区域 (meta_position)

每个字段为独立矩形 `{x, y, width, height}`：

| 参数 | 说明 |
|------|------|
| `x`, `y` | 字段起始坐标 |
| `width` | 字段区域宽度（超出自动换行） |
| `height` | 字段区域高度（超出自动截断） |

> 注意：坐标需要根据实际背景图测量后调整。

## License

MIT
