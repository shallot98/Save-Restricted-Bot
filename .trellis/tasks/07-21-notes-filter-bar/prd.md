# 笔记页筛选栏（收藏 / 日期 / 标签）做完整

## Goal

把首页「我的笔记」下三个筛选按钮做成可用、可刷新保持、与分页共存的列表筛选。

## Requirements

* **收藏**：按钮与 `?favorite=1` 同步开关；激活态与 URL/侧栏/底栏一致；可取消收藏筛选
* **日期筛选**：提供起止日期 UI，提交 `date_from` / `date_to`（已有后端）；支持清空
* **标签（来源）**：按钮打开来源选择（复用 `sources` + `?source=`）；可清除来源筛选；不新建 tags 体系
* 筛选与分页、搜索参数共存（翻页不丢筛选）
* 移动端可用（弹层/面板不遮挡关键操作）

## Acceptance Criteria

* [ ] 点击「收藏」进入仅收藏列表；再点或等价操作可恢复全部；刷新后状态保持
* [ ] 「日期筛选」可选起止日期并过滤；清空后恢复；URL 含 date 参数
* [ ] 「标签」可按来源频道筛选；选择后 URL 含 `source=`；可清除
* [ ] 分页链接保留当前 favorite / date / source / search 参数
* [ ] 空结果有明确提示

## Definition of Done

* 相关前端交互可用（手工或自动化冒烟）
* 不破坏现有 toggle 单条收藏、侧栏来源列表
* Lint / 既有相关测试不回归

## Technical Approach

* 以前端接线为主，复用 `web/routes/notes.py` 已有 query 参数
* 收藏：按钮改为导航/切换 `favorite` 查询参数，并反映服务端 `favorite_only` 初始状态
* 日期：下拉或弹层内两个 date input + 应用/清除，跳转 `/notes?...`
* 标签：下拉或弹层列出 `sources`（与侧栏同源），点选写入 `source=`；无来源时禁用或提示
* 组合筛选时保留已有 query（search、page 重置为 1）

## Decision (ADR-lite)

**Context**: 「标签」按钮无后端 tags 模型  
**Decision**: 语义定为「来源筛选」，复用 `source` 参数与 `sources` 数据  
**Consequences**: 与侧栏「来源频道」能力重叠但更适合主内容区触达；完整标签系统不在本任务

## Out of Scope

* 笔记独立标签 schema / CRUD / 打标 UI
* 从正文解析 `#话题`
* 复杂日期快捷（本周/本月）——可选增强，非必须
* 重构侧栏导航结构

## Technical Notes

* Files: `templates/notes.html`, `templates/components/pagination.html`, `web/routes/notes.py`（基本只读复用）, `src/infrastructure/persistence/repositories/note_repository_search.py`（已有 date/favorite/source）
* DB: `is_favorite` 已有；无 tags 列
* Alpine 当前 `filterFavorite: false` 未与服务端同步
