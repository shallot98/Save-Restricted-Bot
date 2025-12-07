# 冲突检测 - 快速参考卡

## 6个检测到的冲突

### 🔴 CON-001: CSS范式冲突
- **严重性**: High | **风险**: Medium | **工作量**: 0天*
- **现状**: 桌面优先CSS架构 (@media max-width)
- **推荐**: 保持现有，记录技术债 ✅
- **理由**: 795行全量重写风险高，现有结构已可支持

### 🔴 CON-002: 侧边栏状态管理
- **严重性**: High | **风险**: Low-Med | **工作量**: 1.5天
- **现状**: 'collapsed' vs 'mobile-open' 两个独立状态类
- **推荐**: 创建SidebarStateManager对象 ✅
- **收益**: SSOT, localStorage持久化, 消除状态失步

### 🔴 CON-003: 触摸事件缺失
- **严重性**: High | **风险**: Low | **工作量**: 1.5+2.5天
- **现状**: 仅支持click事件，无touch处理
- **推荐**: Phase1基础touch+Phase2手势库评估 ✅
- **收益**: swipe-to-close, 300ms延迟消除

### 🔴 CON-004: API超时过长 ⭐ P1
- **严重性**: High | **风险**: Low | **工作量**: 1天
- **现状**: 30秒超时（WebDAV/校准）
- **推荐**: 5秒(WebDAV) + 10秒(校准) ✅
- **收益**: 移动网络成功率↑ 20-30%

### 🟡 CON-005: 图片懒加载 ⭐ P1
- **严重性**: Medium | **风险**: Low | **工作量**: 1+3天
- **现状**: 全分辨率图片，无优化
- **推荐**: Phase1客户端懒加载+Phase2缩略图评估 ✅
- **收益**: 带宽↓ 60%, 加载速度↑ 30-40%

### 🟡 CON-006: 测试框架缺失
- **严重性**: Medium | **风险**: Low | **工作量**: 1+2.5天
- **现状**: 无移动/前端自动化测试
- **推荐**: 渐进式测试(JS单元+端到端可选) ✅
- **收益**: 质量保证↑, 回归防护↑

---

## 📅 实施时间表

### ⭐ P1 优先级 - 第1周 (3.5人天)
```
Day 1-2 (2天)
├─ CON-004: 修改超时配置 (1天)
│  ├─ app.py:373 - 30s → 5s (WebDAV)
│  └─ app.py:641 - 30s → 10s (calibrate)
│
└─ CON-005.P1: 图片懒加载 (1天)
   ├─ loading="lazy" 属性
   └─ IntersectionObserver 垫片

Day 3-4 (1.5天)
└─ CON-003.P1: 触摸事件 (1.5天)
   ├─ touch-action CSS
   └─ swipe-to-close 实现

Day 5 (0.5天)
└─ 集成测试 + 真机验证
```

### 🔧 P2 优先级 - 第2-3周 (2.5人天)
```
├─ CON-002: 侧边栏状态管理 (1.5天)
│  └─ SidebarStateManager + localStorage
│
└─ CON-006: 测试框架 (1天)
   ├─ JavaScript 单元测试
   └─ 移动测试清单
```

### ⚙️ P3 优先级 - 可选 (按需)
```
├─ CON-001: CSS迁移评估
├─ CON-003.P2: 手势库评估
└─ CON-005.P2: 服务端缩略图
```

---

## 🎯 关键决策

### 决策1: CSS架构 (CON-001)
**问题**: 迁移到移动优先？
**答案**: ❌ 否，保持现有
**理由**: 高风险, 低收益, 技术债处理

### 决策2: 手势库 (CON-003)
**问题**: 引入Hammer.js？
**答案**: ⏳ 先不引入，基于反馈评估
**理由**: 零依赖约束, 基础touch已满足需求

### 决策3: 图片优化 (CON-005)
**问题**: 服务端缩略图？
**答案**: ⏳ 先实现客户端懒加载，后评估
**理由**: 存储成本高，先收集数据后决策

---

## 💾 文件位置

**工作目录**: `/root/Save-Restricted-Bot/.workflow/active/WFS-mobile-adaptation-complete/.process/`

### 核心文件
```
📄 CONFLICT_DETECTION.json        (45KB) - 完整冲突分析
📄 CONFLICT_SUMMARY.md            (10KB) - 执行摘要
📄 IMPLEMENTATION_GUIDE.md        (17KB) - 实施指南
📄 README.md                      (10KB) - 索引导航
```

### 支撑文件
```
📊 context-package.json           (36KB) - 项目上下文
📊 exploration-patterns.json      (19KB) - 代码模式分析
📊 exploration-integration-points.json (28KB) - 集成分析
📊 exploration-testing.json       (9KB)  - 测试分析
📊 exploration-dependencies.json  (17KB) - 依赖分析
```

---

## 🔧 P1 实施快速开始

### 改动1: 修改超时配置
```python
# app.py
# 第373行: timeout=30 → timeout=5
# 第641行: timeout=30 → timeout=10
```

### 改动2: 添加图片懒加载
```html
<!-- notes.html -->
<!-- 添加 loading="lazy" -->
<img src="..." loading="lazy">

<!-- 添加 IntersectionObserver 垫片 -->
```

### 改动3: 基本触摸处理
```css
/* main.css */
.sidebar {
    touch-action: manipulation;  /* 新增 */
}
```

```javascript
/* notes.html */
// 添加 touchstart/touchend handlers
document.addEventListener('touchstart', ...)
document.addEventListener('touchend', ...)
```

---

## ✅ 预期成果

### 第1周后（P1）
- ✅ API超时失败率 ↓ 20-30%
- ✅ 首屏加载时间 ↓ 30-40%
- ✅ 带宽消耗 ↓ 60%+ (off-screen)
- ✅ 移动UX改善 (swipe-to-close, touch反馈)

### 第3周后（P1+P2）
- ✅ 状态管理稳定性 ↑ 100%
- ✅ 测试覆盖率 ↑ (自动化)
- ✅ 回归防护 ↑ (防止bug)

### 风险评级
**总体**: 🟢 低 (推荐方案)
- P1改动: 低风险 ✅
- P2改动: 低-中风险 ✅
- P3改动: 中-高风险 (可选)

---

## 📞 如何使用这些文件

### 我是项目经理
→ 阅读 CONFLICT_SUMMARY.md 的"时间表"和"风险评估"

### 我是开发者
→ 按照 IMPLEMENTATION_GUIDE.md 逐步操作
→ 参考代码示例进行修改

### 我是QA/测试
→ 使用 mobile_test_cases.md（P2会生成）
→ 参考 CONFLICT_DETECTION.json CON-006 部分

### 我需要做决策
→ 阅读 CONFLICT_SUMMARY.md "关键决策点"
→ 查看 CONFLICT_DETECTION.json strategies 部分

### 我是架构师
→ 查看 CONFLICT_DETECTION.json "overlap_analysis"
→ 参考 exploration-*.json 文件

---

## 🚀 下一步

### 今天
- [ ] 阅读本快速参考卡（5分钟）
- [ ] 阅读 CONFLICT_SUMMARY.md（15分钟）
- [ ] 确认3个关键决策

### 本周
- [ ] 创建feature分支
- [ ] 实施P1改动（步骤1-3）
- [ ] 本地验证
- [ ] 提交PR

### 下周
- [ ] 代码审查 + 反馈
- [ ] 真机测试（iPhone/Android）
- [ ] Merge到main

---

## 📊 成本-效益分析

| 冲突 | 工作量 | 直接收益 | 技术债 | ROI |
|-----|--------|---------|--------|-----|
| CON-004 | 1天 | 网络成功率↑ | 无 | ⭐⭐⭐⭐⭐ |
| CON-005.P1 | 1天 | 加载速度↑ | 后续缩略图 | ⭐⭐⭐⭐⭐ |
| CON-003.P1 | 1.5天 | 交互体验↑ | 手势库评估 | ⭐⭐⭐⭐ |
| CON-002 | 1.5天 | 稳定性↑ | 无 | ⭐⭐⭐⭐ |
| CON-006 | 1天 | 质量保证↑ | 扩展测试 | ⭐⭐⭐ |
| **总计P1+P2** | **6天** | **整体↑↑↑** | **最小化** | **⭐⭐⭐⭐⭐** |

---

## ❓ 快速问答

**Q: 这会破坏现有功能吗？**
A: 否。所有改动都有fallback，不会影响现有用户。

**Q: 需要修改数据库吗？**
A: 否。纯前端CSS/JS和后端配置改动。

**Q: 需要多少人力？**
A: P1+P2共6人天，1个开发者1-2周完成。

**Q: 哪个改动优先级最高？**
A: CON-004 + CON-005.P1，立即改善用户体验。

**Q: 有代码示例吗？**
A: 是的，IMPLEMENTATION_GUIDE.md 中有完整示例。

**Q: 如何测试这些改动？**
A: 使用Chrome DevTools模拟器 + 真机验证。

---

**生成时间**: 2025-12-07
**文档版本**: 1.0
**保存位置**: `.workflow/active/WFS-mobile-adaptation-complete/.process/`
