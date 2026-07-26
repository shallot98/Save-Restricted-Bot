# 多图片显示 URL 路径错误修复

## 问题描述

多图片显示时出现错误的 URL 路径，例如：
- 错误：`/media/https://files.catbox.moe/eymb25.jpeg`
- 正确：`https://files.catbox.moe/eymb25.jpeg`

## 根本原因

在 `templates/components/note_card.html` 中，所有图片路径都统一添加了 `/media/` 前缀：

```jinja2
{{ render_note_media_img('/media/' ~ (note.media_paths[0] | urlencode)) }}
```

但是当使用 WebDAV 存储（如 Catbox）时，`media_paths` 中存储的已经是完整的远程 URL，不应该再添加 `/media/` 前缀。

## 受影响的代码位置

### 文件：`templates/components/note_card.html`

受影响的行：
- 第 36 行：单图显示
- 第 43 行：2图布局
- 第 52 行：3图布局（左边大图）
- 第 58 行：3图布局（右边小图）
- 第 68 行：4+图布局
- 第 82 行：单张照片（旧逻辑）

所有这些行都使用了相同的模式：
```jinja2
'/media/' ~ (media_path | urlencode)
```

## 解决方案

需要在模板中添加 URL 检测逻辑：

### 方案 1：在模板中使用条件判断

```jinja2
{% set img_url = media_path if (media_path.startswith('http://') or media_path.startswith('https://')) else '/media/' ~ (media_path | urlencode) %}
{{ render_note_media_img(img_url) }}
```

### 方案 2：创建 Jinja2 自定义过滤器（推荐）

在 Flask 应用中添加自定义过滤器：

```python
@app.template_filter('media_url')
def media_url_filter(path):
    """Convert media path to proper URL"""
    if not path:
        return ''
    # 如果已经是完整 URL，直接返回
    if path.startswith('http://') or path.startswith('https://'):
        return path
    # 否则添加 /media/ 前缀
    from urllib.parse import quote
    return f'/media/{quote(path)}'
```

然后在模板中使用：
```jinja2
{{ render_note_media_img(media_path | media_url) }}
```

### 方案 3：修改 render_note_media_img 宏

修改宏定义，让它接受原始路径并自动处理：

```jinja2
{% macro render_note_media_img(media_path, alt_text='Note image') %}
{% set img_url = media_path if (media_path.startswith('http://') or media_path.startswith('https://')) else '/media/' ~ (media_path | urlencode) %}
<div class="note-media-skeleton skeleton-loader absolute inset-0" aria-hidden="true"></div>
<img src="{{ img_url }}"
     alt="{{ alt_text }}"
     loading="lazy"
     class="note-media-img absolute inset-0 w-full h-full object-cover opacity-0 image-loading"
     data-note-media-img
     onload="this.classList.remove('opacity-0','image-loading'); this.classList.add('image-loaded'); if (this.previousElementSibling) this.previousElementSibling.remove();"
     onerror="this.classList.remove('opacity-0','image-loading'); this.classList.add('image-error'); if (this.previousElementSibling) this.previousElementSibling.remove();">
{% endmacro %}
```

然后调用时直接传入原始路径：
```jinja2
{{ render_note_media_img(note.media_paths[0]) }}
```

## 推荐实施方案

**推荐使用方案 3**，原因：
1. 集中处理逻辑，避免在多处重复代码
2. 模板调用更简洁
3. 易于维护和测试
4. 不需要修改 Flask 应用代码

## 需要修改的具体位置

### 1. 修改 `render_note_media_img` 宏（第 7-16 行）

```jinja2
{% macro render_note_media_img(media_path, alt_text='Note image') %}
{% set img_url = media_path if (media_path.startswith('http://') or media_path.startswith('https://')) else '/media/' ~ (media_path | urlencode) %}
<div class="note-media-skeleton skeleton-loader absolute inset-0" aria-hidden="true"></div>
<img src="{{ img_url }}"
     alt="{{ alt_text }}"
     loading="lazy"
     class="note-media-img absolute inset-0 w-full h-full object-cover opacity-0 image-loading"
     data-note-media-img
     onload="this.classList.remove('opacity-0','image-loading'); this.classList.add('image-loaded'); if (this.previousElementSibling) this.previousElementSibling.remove();"
     onerror="this.classList.remove('opacity-0','image-loading'); this.classList.add('image-error'); if (this.previousElementSibling) this.previousElementSibling.remove();">
{% endmacro %}
```

### 2. 修改所有调用位置

将所有的：
```jinja2
{{ render_note_media_img('/media/' ~ (media_path | urlencode)) }}
```

改为：
```jinja2
{{ render_note_media_img(media_path) }}
```

具体位置：
- 第 36 行：`{{ render_note_media_img(note.media_paths[0]) }}`
- 第 43 行：`{{ render_note_media_img(media_path) }}`
- 第 52 行：`{{ render_note_media_img(note.media_paths[0]) }}`
- 第 58 行：`{{ render_note_media_img(media_path) }}`
- 第 68 行：`{{ render_note_media_img(media_path) }}`
- 第 82 行：`{{ render_note_media_img(note.media_path) }}`

## 测试验证

修复后需要验证：
1. 本地存储的图片（路径如 `123456_20231220_120000.jpg`）能正常显示
2. WebDAV 远程存储的图片（完整 URL）能正常显示
3. 单图、2图、3图、4+图布局都能正常工作
4. 图片懒加载和骨架屏效果正常

## 相关文件

- `templates/components/note_card.html` - 主要修改文件
- `bot/workers/message_worker.py` - 媒体存储逻辑（无需修改）
- `bot/storage/webdav_client.py` - WebDAV 存储逻辑（无需修改）
