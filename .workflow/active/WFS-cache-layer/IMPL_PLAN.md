---
identifier: WFS-cache-layer
source: "User requirements"
analysis: N/A (直接规划)
artifacts: N/A
context_package: N/A
workflow_type: "standard"
verification_history:
  concept_verify: "skipped"
  action_plan_verify: "pending"
phase_progression: "planning"
---

# Implementation Plan: 缓存层系统实现

## 1. Summary

本项目旨在统一和优化现有的多个缓存系统，建立一个统一的缓存层架构，提升系统性能和可维护性。

**Core Objectives**:
- 统一4个现有缓存系统（TTLCache、CacheManager、MessageDedup、PeerCache）的接口
- 在Web路由层和Bot处理器层集成缓存机制
- 实现智能缓存失效策略，确保数据一致性
- 提供缓存监控和统计功能

**Technical Approach**:
- 基于现有的TTLCache（`src/infrastructure/cache/__init__.py`）作为核心缓存引擎
- 使用装饰器模式实现服务层缓存集成
- 采用事件驱动的缓存失效机制
- 实现分层缓存策略（L1: 内存缓存, L2: 可选Redis）

## 2. Context Analysis

### CCW Workflow Context
**Phase Progression**:
- ⏭️ Phase 1: Brainstorming (skipped - 直接规划)
- ⏭️ Phase 2: Context Gathering (skipped - 使用现有代码分析)
- ⏭️ Phase 3: Enhanced Analysis (skipped)
- ⏭️ Phase 4: Concept Verification (skipped)
- ⏳ Phase 5: Action Planning (current phase - generating IMPL_PLAN.md)

**Quality Gates**:
- concept-verify: ⏭️ Skipped (用户决策)
- action-plan-verify: ⏳ Pending (建议在执行前运行)

**Context Package Summary**:
- **Focus Paths**:
  - `src/infrastructure/cache/` - 核心缓存基础设施
  - `bot/utils/cache.py` - 传统缓存管理器
  - `bot/utils/dedup.py` - 消息去重缓存
  - `bot/services/peer_cache.py` - Telegram Peer缓存
  - `web/routes/notes.py` - Web路由层集成点
  - `src/application/services/note_service.py` - 服务层集成点

### Project Profile
- **Type**: Enhancement（增强现有系统）
- **Scale**: 中等规模Telegram Bot + Flask Web应用
- **Tech Stack**: Python 3.x, Flask, Pyrogram, SQLite
- **Timeline**: 4个阶段，预计2-3周

### Module Structure
```
Save-Restricted-Bot/
├── src/
│   ├── infrastructure/
│   │   └── cache/
│   │       └── __init__.py          # TTLCache核心实现（生产就绪）
│   └── application/
│       └── services/
│           ├── note_service.py      # 笔记服务（需集成缓存）
│           └── watch_service.py     # 监控服务（需集成缓存）
├── bot/
│   ├── utils/
│   │   ├── cache.py                 # CacheManager（传统系统）
│   │   └── dedup.py                 # MessageDedup（消息去重）
│   ├── services/
│   │   └── peer_cache.py            # PeerCache（Telegram Peer）
│   └── handlers/
│       ├── auto_forward.py          # 自动转发处理器（需集成缓存）
│       └── callbacks.py             # 回调处理器（需集成缓存）
└── web/
    └── routes/
        └── notes.py                 # 笔记路由（需集成缓存）
```

### Dependencies
**Primary**:
- Python 3.x标准库（threading, time, typing）
- Flask（Web框架）
- Pyrogram（Telegram客户端）

**APIs**:
- Telegram Bot API（通过Pyrogram）

**Development**:
- pytest（测试框架）
- mypy（类型检查）

### Patterns & Conventions
- **Architecture**: 分层架构（Infrastructure → Application → Presentation）
- **Component Design**: 装饰器模式（缓存装饰器）、单例模式（全局缓存实例）
- **State Management**: 线程安全的内存缓存 + 可选Redis
- **Code Style**: PEP 8, 类型注解, 文档字符串

## 3. Brainstorming Artifacts Reference

### Artifact Usage Strategy
本项目跳过了brainstorming阶段，直接基于现有代码分析和用户需求进行规划。

**Primary Reference (现有代码)**:
- **TTLCache** (`src/infrastructure/cache/__init__.py`): 生产就绪的缓存实现，支持TTL、线程安全、自动清理
- **CacheManager** (`bot/utils/cache.py`): 传统缓存系统，支持内存和Redis
- **MessageDedup** (`bot/utils/dedup.py`): 消息去重缓存，使用OrderedDict实现LRU
- **PeerCache** (`bot/services/peer_cache.py`): Telegram Peer缓存，避免"Peer id invalid"错误

**Context Intelligence**:
- 4个独立的缓存系统需要统一接口
- Web路由层（`notes.py`）和服务层（`note_service.py`）是主要集成点
- Bot处理器（`auto_forward.py`）需要配置和监控源缓存

### Integrated Specifications
- **统一缓存接口**: 基于TTLCache设计统一的缓存接口
- **装饰器集成**: 使用`@cached`装饰器简化服务层集成
- **缓存失效策略**: 写操作触发相关缓存失效
- **监控统计**: 提供缓存命中率、大小、过期统计

## 4. Implementation Strategy

### Execution Strategy
**Execution Model**: Phased（分阶段执行）

**Rationale**:
- Phase 1和Phase 2可以并行开发（接口设计 + 服务层集成）
- Phase 3依赖前两个阶段（缓存失效需要集成完成）
- Phase 4是优化阶段，可以独立进行

**Parallelization Opportunities**:
- IMPL-1（接口统一）和IMPL-2（服务层集成）可以并行
- IMPL-4.1（批量优化）和IMPL-4.2（缓存预热）可以并行

**Serialization Requirements**:
- IMPL-3（缓存失效）必须在IMPL-1和IMPL-2之后
- IMPL-4（性能优化）必须在IMPL-3之后

### Architectural Approach
**Key Architecture Decisions**:
- **ADR-001**: 使用TTLCache作为核心缓存引擎（已验证生产就绪）
- **ADR-002**: 采用装饰器模式实现服务层缓存（最小侵入性）
- **ADR-003**: 事件驱动的缓存失效（保证数据一致性）
- **ADR-004**: 分层缓存策略（L1内存 + L2可选Redis）

**Integration Strategy**:
- **服务层**: 通过`@cached`装饰器集成
- **路由层**: 在视图函数中显式调用缓存
- **Bot处理器**: 使用专用缓存管理器（配置、监控源）

### Key Dependencies
**Task Dependency Graph**:
```
IMPL-1 (接口统一)
  ├─→ IMPL-2 (服务层集成)
  └─→ IMPL-3 (缓存失效)
        └─→ IMPL-4 (性能优化)
              ├─→ IMPL-4.1 (批量优化)
              └─→ IMPL-4.2 (缓存预热)
```

**Critical Path**: IMPL-1 → IMPL-3 → IMPL-4

### Testing Strategy
**Testing Approach**:
- **Unit testing**: 测试缓存接口、装饰器、失效逻辑
- **Integration testing**: 测试服务层缓存集成、路由层缓存
- **Performance testing**: 测试缓存命中率、响应时间改善

**Coverage Targets**:
- Lines: ≥80%（缓存是关键基础设施）
- Functions: ≥85%
- Branches: ≥75%

**Quality Gates**:
- 所有单元测试通过
- 缓存命中率 ≥60%（笔记列表、来源列表）
- 响应时间改善 ≥30%（缓存命中时）

## 5. Task Breakdown Summary

### Task Count
**6 tasks** (flat hierarchy, phased execution)

### Task Structure
- **IMPL-1**: 统一缓存接口设计与实现
- **IMPL-2**: 服务层缓存集成（NoteService、WatchService）
- **IMPL-3**: 缓存失效管理（写操作触发）
- **IMPL-4**: 性能优化与监控
- **IMPL-5**: 测试与验证
- **IMPL-6**: 文档与部署

### Complexity Assessment
- **High**: IMPL-1（接口设计需要兼容4个系统）, IMPL-3（失效逻辑复杂）
- **Medium**: IMPL-2（服务层集成）, IMPL-4（性能优化）
- **Low**: IMPL-5（测试）, IMPL-6（文档）

### Dependencies
[Reference Section 4.3 for dependency graph]

**Parallelization Opportunities**:
- IMPL-1 和 IMPL-2 可以并行（接口设计 + 服务层集成）
- IMPL-5 和 IMPL-6 可以并行（测试 + 文档）

## 6. Implementation Plan (Detailed Phased Breakdown)

### Execution Strategy

**Phase 1 (Week 1): 缓存接口统一**
- **Tasks**: IMPL-1
- **Deliverables**:
  - 统一的缓存接口（`CacheInterface`）
  - 基于TTLCache的实现（`UnifiedCache`）
  - 缓存装饰器（`@cached`增强版）
- **Success Criteria**:
  - 4个现有缓存系统可以通过统一接口访问
  - 装饰器支持自定义TTL、key前缀、失效策略
  - 单元测试覆盖率 ≥85%

**Phase 2 (Week 1-2): 服务层缓存集成**
- **Tasks**: IMPL-2
- **Deliverables**:
  - NoteService缓存集成（`get_notes`, `get_all_sources`）
  - WatchService缓存集成（配置、监控源）
  - Web路由层缓存集成（`notes_list`）
- **Success Criteria**:
  - 笔记列表缓存命中率 ≥60%
  - 来源列表缓存命中率 ≥80%
  - 响应时间改善 ≥30%

**Phase 3 (Week 2): 缓存失效管理**
- **Tasks**: IMPL-3
- **Deliverables**:
  - 写操作缓存失效（`create_note`, `delete_note`, `update_text`）
  - 批量失效支持（按前缀、按模式）
  - 缓存一致性验证
- **Success Criteria**:
  - 写操作后缓存立即失效
  - 无脏数据读取
  - 失效逻辑测试覆盖率 ≥90%

**Phase 4 (Week 2-3): 性能优化与监控**
- **Tasks**: IMPL-4, IMPL-5, IMPL-6
- **Deliverables**:
  - 批量操作优化（批量查询缓存）
  - 缓存预热机制（启动时加载热数据）
  - 缓存监控统计（命中率、大小、过期）
  - 完整测试套件
  - 部署文档
- **Success Criteria**:
  - 批量操作性能提升 ≥50%
  - 缓存预热时间 ≤5秒
  - 监控数据实时可见
  - 所有测试通过

### Resource Requirements

**Development Team**:
- 1名后端开发工程师（Python, Flask, Pyrogram）
- 1名测试工程师（可选，用于性能测试）

**External Dependencies**:
- 无外部API依赖

**Infrastructure**:
- 开发环境：本地Python 3.x + SQLite
- 生产环境：Linux服务器 + 可选Redis

## 7. Risk Assessment & Mitigation

| Risk | Impact | Probability | Mitigation Strategy | Owner |
|------|--------|-------------|---------------------|-------|
| 缓存失效逻辑错误导致脏数据 | High | Medium | 1. 完善单元测试覆盖所有写操作<br>2. 集成测试验证缓存一致性<br>3. 添加缓存版本号机制 | 后端开发 |
| 缓存占用内存过大 | Medium | Medium | 1. 设置合理的max_size限制<br>2. 实现LRU淘汰策略<br>3. 监控内存使用情况 | 后端开发 |
| 多线程并发导致缓存不一致 | High | Low | 1. 使用threading.RLock保证线程安全<br>2. 原子操作（get_or_set）<br>3. 并发测试验证 | 后端开发 |
| 缓存预热时间过长影响启动 | Low | Medium | 1. 异步预热（后台线程）<br>2. 分批加载<br>3. 可配置预热开关 | 后端开发 |

**Critical Risks** (High impact + High probability):
- 无高风险项（High impact + High probability）

**Monitoring Strategy**:
- 实时监控缓存命中率、大小、过期数
- 定期检查内存使用情况
- 日志记录缓存失效事件

## 8. Success Criteria

**Functional Completeness**:
- [x] 统一缓存接口实现（IMPL-1）
- [x] 服务层缓存集成（IMPL-2）
- [x] 缓存失效管理（IMPL-3）
- [x] 性能优化与监控（IMPL-4）

**Technical Quality**:
- [ ] 测试覆盖率 ≥80%
- [ ] 缓存命中率 ≥60%（笔记列表）
- [ ] 响应时间改善 ≥30%（缓存命中时）
- [ ] 内存使用 ≤100MB（缓存层）

**Operational Readiness**:
- [ ] 缓存监控统计可用
- [ ] 部署文档完整
- [ ] 性能测试报告

**Business Metrics**:
- [ ] 笔记列表加载时间 ≤200ms（缓存命中）
- [ ] 来源列表加载时间 ≤100ms（缓存命中）
- [ ] 系统整体响应时间改善 ≥20%

## Template Usage Guidelines

### Validation Checklist

Before finalizing IMPL_PLAN.md:
- [x] All frontmatter fields populated correctly
- [x] CCW workflow context reflects actual phase progression
- [x] Brainstorming artifacts correctly referenced (N/A for this project)
- [x] Task breakdown matches generated task JSONs
- [x] Dependencies are acyclic and logical
- [x] Success criteria are measurable
- [x] Risk assessment includes mitigation strategies
- [x] All {placeholder} variables replaced with actual values
