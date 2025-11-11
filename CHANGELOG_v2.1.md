# Changelog v2.1.0 - 多图片支持与数据独立存储

## 🎉 重大更新

### ✨ 新功能

#### 1. 多图片支持
- **媒体组识别**: 自动识别 Telegram 媒体组（多张图片一起发送）
- **完整保存**: 记录模式下保存所有图片，保持原始顺序
- **优雅展示**: Web界面使用网格布局展示多张图片
  - 单张图片：全宽显示
  - 两张图片：并排展示
  - 三张及以上：第一张大图 + 其他小图网格
- **文字合并**: 自动合并媒体组中所有文字说明
- **向后兼容**: 旧的单图片笔记仍可正常显示

#### 2. 数据独立存储
- **统一数据目录**: 所有用户数据集中在 `data/` 目录
- **配置文件管理**: 配置文件移至 `data/config/` 子目录
- **环境变量支持**: 通过 `DATA_DIR` 环境变量自定义数据路径
- **更新安全**: `git pull` 更新代码时数据不受影响
- **备份简化**: 只需备份 `data/` 目录即可

#### 3. Docker 增强
- **完整卷挂载**: `./data:/app/data` 持久化所有数据
- **配置集中化**: 配置文件在挂载的 `data/config/` 目录
- **端口映射**: 同时映射 Bot (10000) 和 Web (5000) 端口
- **环境变量**: `DATA_DIR` 环境变量配置

### 🔧 改进

#### 数据库
- 新增 `note_media` 表存储多媒体关系
- 添加 `media_order` 字段保持顺序
- 外键约束确保数据一致性
- 索引优化查询性能

#### API
- `add_note()` 新增 `media_list` 参数
- `get_note_media()` 新函数获取笔记所有媒体
- `get_notes()` 自动加载 `media_list` 字段
- `delete_note()` 级联删除所有关联媒体

#### Web界面
- 多图片网格布局
- 响应式设计适配移动设备
- 编辑页面支持多图片预览
- CSS优化减少代码重复

#### 代码结构
- 媒体组处理逻辑模块化
- 配置文件路径自动检测
- 环境变量优先级配置
- 更好的错误处理

### 📝 新文件

- `migrate_to_multi_image.py` - 自动迁移脚本
- `MULTI_IMAGE_SUPPORT.md` - 功能详细文档
- `UPGRADE_GUIDE.md` - 升级指南
- `CHANGELOG_v2.1.md` - 本更新日志

### 🔄 迁移

**自动迁移（推荐）**:
```bash
python3 migrate_to_multi_image.py
```

**手动迁移**:
1. 创建 `data/config/` 目录
2. 复制配置文件到 `data/config/`
3. 重启Bot自动创建 `note_media` 表

### ⚠️ 破坏性变更

**无** - 完全向后兼容！

所有旧数据、配置、API调用都继续正常工作。

### 📊 性能影响

- **查询性能**: 增加索引，性能略有提升
- **存储空间**: 多图片笔记占用更多空间（预期行为）
- **内存使用**: 媒体组处理时临时占用少量内存
- **响应速度**: Web界面加载时间略增（毫秒级）

### 🐛 已修复

无新Bug修复（功能性更新）

### 🔐 安全性

- 无新增安全风险
- 配置文件继续不被Git跟踪
- 数据库权限保持一致
- 媒体文件访问仍需登录

### 📚 文档更新

- 更新 README.md 添加多图片说明
- 新增专门的多图片功能文档
- 详细的升级指南
- Docker部署指南更新

### 🚀 性能优化

- 数据库查询优化
- 批量加载媒体列表
- CSS网格布局高效渲染
- 定时器防抖处理媒体组

### 📱 用户界面

**Web界面改进**:
- 多图片网格显示
- 图片悬停放大效果
- 移动端友好布局
- 加载动画优化

**编辑界面**:
- 多图片预览网格
- 响应式图片大小
- 视频缩略图标识

### 🔧 开发者

**新API**:
```python
# 添加多图片笔记
add_note(
    user_id=123,
    source_chat_id="-100123",
    source_name="Test Channel",
    message_text="Multi-image post",
    media_list=[
        {'type': 'photo', 'path': 'image1.jpg'},
        {'type': 'photo', 'path': 'image2.jpg'}
    ]
)

# 获取笔记媒体
media_list = get_note_media(note_id)
```

**配置路径**:
```python
# 优先使用 data/config/，自动回退到根目录
CONFIG_FILE = os.path.join(DATA_DIR, 'config', 'config.json') 
    if os.path.exists(os.path.join(DATA_DIR, 'config', 'config.json')) 
    else 'config.json'
```

### 🎯 未来计划

- [ ] 视频完整播放支持
- [ ] 媒体文件压缩选项
- [ ] 批量下载功能
- [ ] 媒体搜索功能
- [ ] 相册模式展示

### 🙏 致谢

感谢所有用户的反馈和建议！

### 📞 技术支持

- GitHub Issues: 报告问题
- GitHub Discussions: 功能讨论
- 文档: 查看详细文档

---

**发布日期**: 2024
**版本**: v2.1.0
**Git分支**: feat/data-separation-multi-image-notes-docker-volumes
