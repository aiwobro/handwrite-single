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

## 管理员纸张模板编辑器

访问 `/admin/templates/`，可直接在扫描件上标注字段，无需 OCR、AI 或新增图像识别依赖。

### 启用与权限

- 在启动应用的环境中设置 `TEMPLATE_ADMIN_PASSWORD`，至少16字符，建议使用密码管理器生成的随机密码。不要提交到仓库或在公开页面填写部署密钥。
- 未设置密码或长度不足时，管理员入口返回404。修改密码会使已登录管理员会话失效。
- 使用原有 Flask 密钥签名管理员会话，有效期一小时；写操作要求 CSRF Token。
- **仅使用 HTTPS 或本机访问**。生产环境建议额外限制管理员来源 IP，并在反向代理配置登录速率限制；内置10次/5分钟限制仅在单个 worker 内生效，不是集群级防暴力破解。
- Flask 最低版本提升为3.1，以使用仅限编辑器的请求体大小限制；不改变公开生成接口的上传限制。
- 本功能不会自动修改部署配置或重启服务。已有服务需要在维护时将环境变量传入实际应用进程并重新加载代码后才能使用。

### 编辑流程

1. 填写唯一模板 ID（小写字母开头，仅含小写字母、数字、下划线、连字符）及显示名称。
2. 上传正面 PNG/JPEG；可切换到背面上传独立背景。未上传背面时重复使用正面背景。
3. 选择主持人、记录人、会议名称、地点、出席人或年月日，在**空白填写区**拖出矩形。没有的字段无需添加；元数据只在第一页填写。
4. 新上传的图片默认采用“按纸张格线排版”：从第一行上边线框到最后一行下边线，宽度与纸上格线一致。填写实际行数，行距自动取“区域高度÷行数”；选择“靠下边线”（默认）或“靠上”，靠下时可调“距下边线”。蓝线对应格子边线，绿虚线对应字体共同下缘参考线（靠上时为文字行框顶部）。行距显示保留3位小数，内部不按显示值累计，最后一行准确落在区域底部。
   - 字号及下边距必须能放入每格，否则提示调整，不自动缩放正文或改变行数。
   - 旧草稿仍按“原起笔位置模式”导入：其矩形顶部代表第一行文字顶部、参考虚线不是纸上横线。若原矩形就是完整格线区域，可手动切换新模式，再确认行数；不会擅自迁移旧标注。
5. 点击“试写当前面”，使用与正式生成相同的 `write_meta()` / `write_text()` 排版流程检查文字位置，再调整区域和字号。试写采用固定随机种子，当前页满即停止，只返回图片，不写入公开输出目录。
6. 点击“保存为新模板”并确认，背景图、`editor.json` 保存到 `papers/<id>/`，注册表追加对应模板。已有模板和资源目录不覆盖，保存后刷新首页即可选择。
7. 也可以导出 ZIP，内含背景图、新增 YAML 条目及 `editor.json`。手动安装时**合并资源目录、追加 YAML 条目，不要覆盖原注册表**。

编辑操作：滚轮滚动、Ctrl + 滚轮缩放、空格 + 拖动平移；已有框可直接拖动或用四角缩放。点击“框选 / 重画”后下一次拖动会重画所选字段。坐标输入框支持精确微调，画布获得焦点后可用方向键移动（Shift 为10像素）。所有坐标按原图像素保存，与显示缩放无关。

### 草稿、兼容性与限制

- 草稿不会自动保存在浏览器。离开或会话过期前，可点击“下载标注草稿”；重新打开后导入 `editor.json` 恢复图片和标注。导入已有模板后请改用新 ID 保存。
- 编辑器生成的模板包含 `coordinate_mode: visual`。原起笔模式的坐标对应文字行框左上角；格线模式另外包含 `body_grid`，只改变正文在格子中的位置。各字形保留共同字体基线：句号、顿号靠下，引号靠上，破折号居中，不按每个字符的墨迹高度分别底部对齐或缩放。“距下边线”控制字体共同参考下缘，具体字形的墨迹可能略高于该参考线。较矮或较窄的元数据字段框仍会自动缩小字号。
- `body_grid` 为显式可选项；没有此项的原有默认模板、18行纸和已保存的 visual 模板继续原逻辑。保存仅新增模板，不修改已有注册表条目。
- 空 `meta_position: {}` 已受支持，无须使用占位字段。正文仍采用固定行距，不支持弯曲纸张或非等距横线，应使用平整扫描件。
- 单张图片最多2400万像素；网页选择文件上限16MB；请求总量上限24MB（包含图片 Base64）。两面大图可能超过请求上限，需要缩小图片后重新标注。图片方向会标准化，坐标与保存背景一致。
- 保存对注册表采用跨进程文件锁及原子替换，并尽量保留原注释。特殊 YAML 结构无法安全追加时拒绝保存，可改用导出。磁盘错误时可能留下新模板资源或临时文件，需要管理员检查，不会自动删除。
- 模板保存后，其背景图及标注文件位于纸张资源目录，**可能通过公开纸张资源接口访问**。只上传可公开使用的空白模板，勿上传敏感会议扫描件。
- 暂不支持网页删除模板、覆盖修改已有模板或列出服务器已有草稿。

格线模板配置示例（`front` / `back` 各自设置；实际区域按图片标注）：

```yaml
coordinate_mode: visual
body_grid:
  region: {x: 190, y: 556, width: 900, height: 1000}
  rows: 14
  alignment: bottom    # bottom / top
  bottom_gap: 2        # 原图像素；top 模式不使用此间距
```

编辑器会同时生成兼容字段 `start_y`、`line_spacing` 和边距等；格线正文以 `body_grid.region` 及行数为准，`line_spacing` 可为小数。草稿的 `body_mode`、`row_count`、`body_alignment` 和 `bottom_gap` 会一同导出/保存，导入时恢复。

部署编辑器更新时，若 Nginx 使用独立静态目录，需要同步 `static/js/template_editor.js`、`static/js/template_grid.js` 和 `static/css/template_editor.css`。页面资源带版本号以避免长期缓存，但版本号不能代替实际文件同步。

验证：`python3 -m unittest discover -s tests -v`；前端几何测试：`node --test tests/test_template_grid.js`；前端语法检查：`node --check static/js/template_editor.js`。

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

> 注意：旧模板坐标需要根据实际背景图测量后调整；新模板可通过管理员编辑器框选、试写并保存。

## License

MIT
