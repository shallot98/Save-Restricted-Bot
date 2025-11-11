# 更新日志 v2.3.0

## 🎉 重大更新：DATA_DIR 环境变量支持与搜索 UI 改进

### ✨ 新功能

#### 1. 完整的 DATA_DIR 环境变量支持
- **统一数据目录管理**：所有文件操作统一使用 `DATA_DIR` 环境变量
- **智能初始化**：启动时自动创建必要的目录和配置文件
- **环境变量配置**：支持从环境变量自动初始化 `config.json`
- **Docker 友好**：完美支持 Docker 容器数据持久化

**目录结构**：
```
/data/save_restricted_bot/          # DATA_DIR 根目录
├── config/                          # 配置文件目录
│   ├── config.json                 # Bot 配置（自动创建）
│   └── watch_config.json           # 监控配置（自动创建）
├── media/                           # 媒体文件目录
├── logs/                            # 日志文件目录
└── notes.db                         # 数据库文件
```

#### 2. 全新搜索和筛选 UI
- **顶部搜索图标**：搜索图标移至顶部导航栏，位于菜单按钮左侧
- **弹出式搜索面板**：点击搜索图标弹出优雅的搜索面板
- **统一搜索界面**：搜索、来源筛选、日期范围筛选整合在一个面板中
- **移动端优化**：搜索面板在移动设备上全屏显示，触摸友好
- **动画效果**：流畅的展开/收起动画，提升用户体验
- **状态指示**：顶部统计栏显示"筛选中"状态

**搜索面板功能**：
- 🔎 关键词搜索（支持笔记内容和来源）
- 📌 来源筛选（下拉选择）
- 📅 日期范围（开始日期、结束日期）
- 🔍 搜索按钮
- 🔄 清除筛选按钮

#### 3. 快速来源切换
- 保留快速来源切换下拉框（独立于搜索面板）
- 更便捷的来源筛选体验

### 🔧 改进和修复

#### 代码改进
1. **main.py**
   - 移除配置文件路径的向后兼容逻辑
   - 统一使用 `DATA_DIR/config/` 目录
   - 从环境变量初始化配置文件
   - 媒体文件路径统一使用 `DATA_DIR/media/`

2. **app.py**
   - 修复媒体文件服务路径问题
   - 正确使用 `DATA_DIR/media/` 目录

3. **setup.py**
   - 更新配置文件保存路径到 `DATA_DIR/config/`
   - 确保配置目录存在

4. **database.py**
   - 已正确使用 DATA_DIR（无需修改）

#### UI 改进
1. **响应式设计**
   - 桌面端：搜索面板居中显示，最大宽度 600px
   - 移动端：搜索面板占据 95% 宽度，更好的触摸体验
   - 日期选择器在移动端单列显示

2. **视觉效果**
   - 搜索图标带渐变背景，悬停时放大
   - 面板带阴影和圆角，优雅的展开动画
   - 输入框聚焦时显示蓝色边框和阴影

3. **交互优化**
   - 点击搜索图标自动聚焦到搜索输入框
   - 点击遮罩层或关闭按钮关闭面板
   - 面板内点击不会关闭面板

### 🐛 修复的问题

1. **配置文件位置问题**
   - 修复：容器内配置文件写入 `/app` 目录而非 DATA_DIR
   - 原因：配置文件路径使用了向后兼容逻辑
   - 解决：统一使用 DATA_DIR，移除向后兼容代码

2. **媒体文件路径问题**
   - 修复：app.py 中媒体文件路径拼接错误
   - 原因：使用 `os.path.join(os.path.dirname(__file__), DATA_DIR, 'media')`
   - 解决：直接使用 `os.path.join(DATA_DIR, 'media')`

3. **Docker 数据持久化问题**
   - 修复：配置文件在容器重启后丢失
   - 原因：配置文件未保存在挂载的卷中
   - 解决：所有配置文件统一保存到 DATA_DIR

### 📝 使用说明

#### Docker 部署（推荐）
```bash
# 1. 设置环境变量
export TOKEN=your_bot_token
export ID=your_api_id
export HASH=your_api_hash
export STRING=your_session_string

# 2. 启动容器
docker-compose up -d

# 3. 验证配置文件
ls -la /data/save_restricted_bot/config/
```

#### 本地部署
```bash
# 1. 设置环境变量（可选，使用默认路径）
export DATA_DIR=/data/save_restricted_bot

# 2. 启动 Bot
python main.py

# 3. 启动 Web 应用
python app.py
```

### 🔄 数据迁移

如果您从旧版本升级，配置文件可能在项目根目录。需要手动迁移：

```bash
# 1. 创建配置目录
mkdir -p /data/save_restricted_bot/config

# 2. 移动配置文件
mv config.json /data/save_restricted_bot/config/
mv watch_config.json /data/save_restricted_bot/config/

# 3. 重启服务
docker-compose restart
```

### 🎯 验证功能

#### 测试 DATA_DIR 配置
```bash
python3 test_data_dir.py
```

#### 测试搜索 UI
1. 访问 Web 界面：http://localhost:5000
2. 点击顶部搜索图标（🔍）
3. 在搜索面板中输入关键词
4. 选择来源和日期范围
5. 点击"搜索"按钮

### 📊 兼容性

- ✅ 向后兼容多媒体功能（最多 9 张）
- ✅ 向后兼容旧版数据库结构
- ✅ Docker 和本地部署都支持
- ✅ 移动端和桌面端都优化

### 🚀 性能

- 无性能影响
- 所有文件操作都已优化
- 搜索功能性能无变化

### 📖 相关文档

- [README.md](README.md) - 完整文档
- [docker-compose.yml](docker-compose.yml) - Docker 配置
- [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md) - 升级指南

### 🙏 致谢

感谢所有用户的反馈和建议！

---

**发布日期**: 2024
**版本**: v2.3.0
**作者**: Save-Restricted-Bot Team
