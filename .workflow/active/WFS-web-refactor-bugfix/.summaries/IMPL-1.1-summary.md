# Task: IMPL-1.1 提取notes.html内联CSS到独立文件

## 实现摘要

### 文件修改
- `templates/notes.html`: 移除内联CSS (行8-629),添加外部CSS引用,文件从1843行精简至1221行
- `static/css/notes.css`: 新建文件,包含所有提取的CSS规则 (620行)

### 内容添加
- **notes.css** (`/root/Save-Restricted-Bot/static/css/notes.css`): 包含所有笔记页面特定样式
  - 侧边栏切换修复样式
  - 顶部搜索栏优化样式和动画
  - 筛选面板动画
  - 欢迎页面样式
  - 统计卡片样式
  - 笔记网格和卡片样式
  - 媒体展示样式
  - 分页组件样式
  - 模态框样式
  - 懒加载图片状态样式
  - 移动端响应式优化 (@media queries)

### 输出供依赖任务使用

### 可用组件
```html
<!-- 在 notes.html 中引用 -->
<link rel="stylesheet" href="/static/css/notes.css?v=1.0">
```

### 集成点
- **CSS文件引用**: 在 `templates/notes.html` 第8行添加 `<link rel="stylesheet" href="/static/css/notes.css?v=1.0">`
- **版本控制**: 使用 `?v=1.0` 参数支持缓存控制
- **CSS变量依赖**: notes.css 依赖 main.css 中定义的CSS变量 (如 `--spacing-*`, `--radius-*`, `--bg-*`, `--text-*` 等)

### 使用示例
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>笔记管理 - Telegram 笔记</title>
    <link rel="stylesheet" href="/static/css/main.css?v=2.1">
    <link rel="stylesheet" href="/static/css/notes.css?v=1.0">
</head>
<body>
    <!-- 页面内容 -->
</body>
</html>
```

## 技术细节

### CSS规则统计
- **总行数**: 620行
- **选择器数量**: 约80个
- **媒体查询**: 2个 (@media (max-width: 768px) 和 @media (max-width: 480px))
- **动画定义**: 2个 (@keyframes searchSlideIn 和 @keyframes modalIn)

### CSS架构
1. **侧边栏修复**: `.sidebar.collapsed ~ .main-content` 使用兄弟选择器修复布局
2. **组件样式**: 包含搜索栏、筛选面板、统计卡片、笔记卡片等完整组件样式
3. **状态管理**: 使用 `.active`、`.expanded`、`.image-loading` 等状态类
4. **响应式设计**: 移动优先,包含768px和480px断点
5. **CSS变量**: 完全依赖 main.css 中的设计令牌系统

### 兼容性保证
- **选择器优先级**: 保持与原内联CSS完全一致
- **CSS变量作用域**: 所有变量引用保持不变
- **媒体查询**: 断点与 main.css 保持一致
- **动画**: 使用标准CSS动画,无浏览器前缀依赖

## 验收标准检查

- ✅ notes.html中的`<style>`标签已完全移除
- ✅ static/css/notes.css文件创建成功,包含所有CSS规则 (620行)
- ✅ 页面样式结构完整,CSS选择器优先级无冲突
- ✅ 添加CSS文件版本号支持缓存控制 (?v=1.0)
- ✅ 移动端和桌面端样式规则均已保留

## 后续任务建议

1. **浏览器测试**: 在实际浏览器中验证页面渲染结果与原页面完全一致
2. **移动端测试**: 使用浏览器开发者工具测试不同屏幕尺寸的响应式布局
3. **主题测试**: 测试明暗主题切换,确保CSS变量正确应用
4. **性能测试**: 验证外部CSS文件加载不影响页面性能

## 状态: ✅ 完成

**完成时间**: 2025-12-07
**文件变更**:
- 新增: `/root/Save-Restricted-Bot/static/css/notes.css` (620行)
- 修改: `/root/Save-Restricted-Bot/templates/notes.html` (1843行 → 1221行, 减少622行)
