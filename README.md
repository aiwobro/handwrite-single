# handwrite

会议资料排版、打印和创意展示工具 — 将已有文字排版到纸张模板，生成程序模拟手写效果的图片与 PDF。输出不代表真实手写、签署或会议事实认证。

## 功能特性

- 支持会议元数据与正文的手写风格渲染
- 支持多字体随机混排、轻微旋转和字距抖动
- 支持自动换行、自动翻页（正反面模板交替）
- 支持按 `paper_type` 选择纸张预设（背景图与坐标参数联动）
- 提供 Flask Web 页面，支持在线填写表单并生成预览
- Web 端支持分阶段生成状态提示
- Web 端支持按纸张类型实时查看背景预览图
- Web 端支持缩略图预览、点击大图、左右切换、缩放与拖拽查看
- Web 端统一生成 JPG 单页图片，并提供 PDF 与 ZIP 图片包下载
- Web 表单支持 TXT 导入、正文字符上限提示和当前标签页草稿保留
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
python handwrite.py --paper-type default # 显式指定纸张类型（覆盖 config 内 paper_type）
python handwrite.py --meta-only         # 仅写入元数据（预览用）
python handwrite.py --check-config      # 仅检查配置与资源，不生成图片
python handwrite.py --debug-box         # 输出图片附带布局调试框
python handwrite.py --seed 42           # 固定随机种子，结果可复现
python handwrite.py --format pdf        # 输出为 PDF 文件

# 如果你在 conda 环境中，也可用：
conda run -n <你的环境名> python handwrite.py -c config.yaml
```

### 3. 输出

生成的文件保存在 `./output/` 目录下。

- **图片格式**（默认）：每页生成一个单独的 JPG/PNG 文件
- **PDF 格式**：所有页面合并为一个 PDF 文件（同时也会生成单页 JPG 图片）

配置文件中设置 `output.format: "pdf"` 或使用命令行参数 `--format pdf`。

## Web 方式（Flask）

项目提供了网页入口，用户可以填写会议元数据与正文并在线生成结果图片。

### 启动

```bash
python app.py
```

启动后访问：`http://127.0.0.1:5000`

### 使用流程

1. 通过缩略图卡片选择纸张模板，右侧会同步显示对应纸张预览。
2. 粘贴会议正文或导入 UTF-8 TXT 文件；会议信息为选填项，日期使用统一日期控件。
3. 点击“开始生成”，页面会依次提示准备排版、计算分页、渲染笔迹和整理导出文件。
4. 生成完成后，可下载 PDF、图片 ZIP，或在大图预览中单独保存某一页。
5. 如需另一种随机笔迹，可直接点击“换一种笔迹”；无需填写技术性的随机种子。
6. 大图模式支持左右切换、按钮缩放、`Ctrl + 滚轮`缩放、拖拽平移以及键盘快捷键。
7. 未重置表单前，完整正文草稿会保留在当前浏览器标签页中，便于继续编辑。

### Web 端说明

- 生成结果文件保存在 `./output/` 目录。
- Web 端统一输出 JPG 单页图片，每次生成都会同时尝试生成 PDF；命令行仍支持 JPG / PNG / PDF。
- 网页端纸张类型选项来自 `paper_presets.yaml`，默认值由 `config.yaml` 的 `paper_type` 控制。
- 默认监听 `127.0.0.1:5000`，当前配置为 `debug=False`。
- 建议在生产环境设置 `FLASK_SECRET_KEY`；未设置时程序会自动生成并保存在项目根目录 `.flask_secret_key`。
- Web 端默认限制正文长度（`MAX_CONTENT_CHARS`，默认 `12000`）和最大页数（`MAX_GENERATED_PAGES`，默认 `20`），可通过环境变量调整。

## 公开说明页面

- `/info/guide`：使用教程、打印建议与常见问题。
- `/info/about`：项目定位、适用场景与反馈方式。
- `/info/privacy`：表单上传、浏览器草稿、Cookie、结果文件和隐私限制。
- `/info/terms`：服务范围、合法使用、素材许可与输出责任。

首页及说明页均提供导航。页面没有引入广告或第三方统计脚本。

**部署维护提醒：** 当前结果链接没有账号级权限保护，也没有固定自动删除期限，请勿提交机密或敏感资料。重置页面不删除服务器文件。公开政策依据当前实现编写；变更托管、广告、存储或数据用途时，应同步更新日期和内容。维护者仍需确认素材商业授权，并按实际运营主体、适用法律及私密联系方式补全政策，必要时取得专业审阅。

验证公开页面：

```bash
python3 -m unittest discover -s tests -v
```

## 常用参数

- `--check-config`：运行前检查字体、背景图、正文来源、布局范围等配置问题。
- `--paper-type <name>`：指定纸张类型（优先级高于 `config.yaml` 中的 `paper_type`）。
- `--debug-box`：在页面中绘制正文区域、基线和首页元数据框，便于快速调坐标。
- `--seed <int>`：设置随机种子，保证同一输入可复现相同风格输出。
- `--format <jpg|png|pdf>`：指定输出格式（优先级高于配置文件）。

## 标点排版规则说明

当前版本在正文排版（`write_text`）中实现了基础国标断行规则：

- 行首禁则：逗号、句号、顿号、分号、冒号、问号、叹号及右半括号/引号等不应出现在行首
- 行尾禁则：左半括号/引号等不应出现在行尾
- 不可拆分：`——`、`……` 不会被拆到两行

实现方式为"先分词(token)并计算行宽，再按禁则选择断点，最后绘制"。

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

# 纸张类型（默认值：default）
paper_type: "default"

# 纸张预设统一在 paper_presets.yaml 中维护
# 这里只需要选择 paper_type

# 正文：指定外部文件
content_file: "content.txt"

# 或者直接写在这里（适合内容短）
# content: |
#   本次会议主要讨论了关于下季度项目推进的相关事宜。

# 输出配置
output:
  prefix: "meeting_record"   # 输出文件名前缀
  format: "jpg"              # 输出格式（jpg / png / pdf）

# 字体路径（可选，默认使用内嵌配置）
fonts:
  - "./fonts/font0.ttf"
```

## 纸张与布局配置说明

纸张资源与坐标参数采用"资源目录 + 注册表"结构：

```text
papers/
  default/
    front.jpg
    back.jpg
paper_presets.yaml
```

- `papers/<paper_type>/`：存放该纸张的背景图（建议固定为 `front.jpg` / `back.jpg`）
- `paper_presets.yaml`：维护 `paper_type -> front/back 坐标参数 + bg_file` 的映射
- `config.yaml`：只负责选择当前 `paper_type`

默认使用 `paper_type: default`，对应 `papers/default/front.jpg` + `papers/default/back.jpg`。

若 `paper_type` 指定了不存在的类型，程序会报错并列出可选值（例如 `default, notebook_a`）。

`paper_presets.yaml` 示例：

```yaml
default:
  display_name: "默认会议记录本"  # Web 页面显示名称
  front:
    bg_file: "./papers/default/front.jpg"
    start_y: 567
    line_spacing: 71
    font_size: 50
    left_margin: 150
    right_margin: 130
    bottom_margin: 150
    meta_position:
      year: {x: 818, y: 133, width: 140, height: 80}
      # ...
  back:
    bg_file: "./papers/default/back.jpg"
    start_y: 215
    line_spacing: 71
    font_size: 50
    left_margin: 130
    right_margin: 150
    bottom_margin: 150
```

预设级可选字段 `display_name` 用于设置纸张模板在 Web 页面中的显示名称；未设置时回退为纸张类型 ID。

每个 `front/back` 配置中的公共参数如下：

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
