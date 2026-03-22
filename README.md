# handwrite

手写风格会议记录生成器 — 将纯文本内容渲染到会议记录纸背景图上，模拟真实手写效果。

## 功能特性

- **逐字手写模拟**：每个字符随机微旋转（±3°）、大小浮动（±2px）、垂直位置抖动（±3px）
- **墨迹自然化**：深灰色墨水 + 高斯模糊，模拟真实书写痕迹
- **正反面自动排版**：奇偶页交替使用不同背景图，自动换行、翻页
- **元数据填写**：支持填写年、月、日、地点、会议名称、主持人、记录人、出席人
- **紧凑字距**：通过 kerning factor 0.70 压缩字距，接近手写排版

## 文件结构

```
handwrite.py   # 主脚本
```

## 依赖

```bash
pip install Pillow numpy
```

## 使用方法

1. 准备好字体文件（如 `.ttf`），修改脚本中的 `fonts` 路径
2. 准备好背景图 `page1.jpg`（正面）和 `page2.jpg`（背面，或同一张）
3. 编辑 `content.txt` 写入正文内容
4. 编辑 `meta.txt` 写入元数据，格式：`key: value`
5. 运行：

```bash
python handwrite.py
```

输出的图片保存在 `./output/` 目录下。

## 元数据格式（meta.txt）

```
year: 2025
month: 11
day: 23
location: 会议室A
subject: 项目进度会议
chairperson: 张三
note_taker: 李四
attendees: 王五，赵六
```

## 配置说明

脚本顶部的 `CONFIG_FRONT` / `CONFIG_BACK` 字典控制排版：

| 参数 | 说明 |
|------|------|
| `bg_file` | 背景图文件名 |
| `start_y` | 正文第一行起始纵坐标 |
| `line_spacing` | 行高 |
| `font_size` | 字体大小 |
| `left_margin` / `right_margin` | 左右边距 |
| `bottom_margin` | 底部留白 |
| `meta_position` | 元数据字段在图片上的坐标 |

> 注意：坐标需要根据实际背景图测量后调整。

## License

MIT
