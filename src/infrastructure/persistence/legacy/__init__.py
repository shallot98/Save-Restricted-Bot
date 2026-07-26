"""
Legacy Persistence Facade
=========================

仓库根四个 ``database_*.py`` 实现模块的归位处：

===========================  ==================================
原位置                        现位置
===========================  ==================================
``database_notes.py``        ``legacy/note_facade.py``
``database_note_requests.py``  ``legacy/note_arguments.py``
``database_auth.py``         ``legacy/auth.py``
``database_calibration.py``  ``legacy/calibration.py``
===========================  ==================================

前两个在 Phase 2 ④「拆 src.compat ⇄ 根目录双向桥」时下沉，后两个在 Phase 3
收尾时下沉（报告 §5.4 迁移映射末三行）。四个根模块均已删除。

这一层不是仓储，而是**遗留调用形态的适配器**：把根 ``database.py`` 暴露的
dict / 位置参数式旧 API 翻译成 ``NoteService`` / ``NoteRepository`` 的调用。
它放在 infrastructure 而不是 application，是因为它服务的是「旧调用方的形状」
这一外部约束，而不是领域用例。

四个模块的共同前提：所有外部依赖（连接工厂、服务工厂、时区）都由调用方以参数
注入，模块自身对根目录与表现层零 import——这正是它们能被整体搬进 ``src/`` 而
不触发 import-linter 契约 1 的原因。
"""

from src.infrastructure.persistence.legacy.auth import (
    update_password,
    verify_user,
)
from src.infrastructure.persistence.legacy.calibration import (
    CalibrationDeps,
    CalibrationTaskCreate,
    CalibrationTaskQuery,
    CalibrationTaskUpdate,
    add_calibration_task,
    clear_completed_calibration_tasks,
    delete_calibration_task,
    delete_calibration_tasks_by_note_id,
    get_all_calibration_tasks,
    get_calibration_config,
    get_calibration_stats,
    get_pending_calibration_tasks,
    update_calibration_config,
    update_calibration_task,
)
from src.infrastructure.persistence.legacy.note_arguments import (
    legacy_note_create_request,
    legacy_note_query,
)
from src.infrastructure.persistence.legacy.note_facade import (
    LegacyNoteCreateRequest,
    LegacyNoteQuery,
    NoteCompatibilityDeps,
    add_note,
    apply_calibrated_magnets,
    get_note_by_id,
    get_notes,
)

__all__ = [
    # note 侧
    "LegacyNoteCreateRequest",
    "LegacyNoteQuery",
    "NoteCompatibilityDeps",
    "add_note",
    "apply_calibrated_magnets",
    "get_note_by_id",
    "get_notes",
    "legacy_note_create_request",
    "legacy_note_query",
    # auth 侧
    "update_password",
    "verify_user",
    # calibration 侧
    "CalibrationDeps",
    "CalibrationTaskCreate",
    "CalibrationTaskQuery",
    "CalibrationTaskUpdate",
    "add_calibration_task",
    "clear_completed_calibration_tasks",
    "delete_calibration_task",
    "delete_calibration_tasks_by_note_id",
    "get_all_calibration_tasks",
    "get_calibration_config",
    "get_calibration_stats",
    "get_pending_calibration_tasks",
    "update_calibration_config",
    "update_calibration_task",
]
