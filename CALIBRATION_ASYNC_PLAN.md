# 校准异步化最小实现方案

## 问题分析

### 当前问题
1. **Web 路由阻塞**：`web/routes/api.py:400` 中直接使用 `subprocess.run()` 执行校准脚本
2. **资源占用**：校准任务超时（10-30秒）会占用 Web worker，影响其他请求
3. **用户体验差**：前端需要等待校准完成才能继续操作

### 影响范围
- `web/routes/api.py` - Web API 校准接口
- `bot/services/calibration_manager.py` - Bot 侧校准管理器

## 设计方案（KISS + YAGNI）

### 核心原则
- **最小化改动**：只修改必要的部分
- **无额外依赖**：使用 Python 标准库
- **向后兼容**：保持现有接口不变

### 技术选型

#### 方案：ThreadPoolExecutor + 内存任务队列

**优点：**
- Python 标准库 `concurrent.futures`，无需额外依赖
- 适合 I/O 密集型任务（subprocess 调用）
- 实现简单，代码量少
- 支持任务状态查询和结果获取

**缺点：**
- 任务状态存储在内存中，重启后丢失
- 不支持分布式部署（当前不需要）

## 实现步骤

### 1. 创建异步任务管理器

```python
# bot/services/async_calibration_manager.py

import uuid
import time
import logging
from typing import Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    TIMEOUT = "timeout"      # 超时


@dataclass
class CalibrationTask:
    """校准任务"""
    task_id: str
    info_hash: str
    status: TaskStatus
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = None
    completed_at: Optional[float] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class AsyncCalibrationManager:
    """异步校准任务管理器"""

    def __init__(self, max_workers: int = 5, task_ttl: int = 3600):
        """
        初始化管理器

        Args:
            max_workers: 最大并发工作线程数
            task_ttl: 任务结果保留时间（秒），默认1小时
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, CalibrationTask] = {}
        self.futures: Dict[str, Future] = {}
        self.task_ttl = task_ttl
        logger.info(f"AsyncCalibrationManager initialized with {max_workers} workers")

    def submit_task(self, info_hash: str, calibration_func, *args, **kwargs) -> str:
        """
        提交校准任务

        Args:
            info_hash: 磁力链接的 info_hash
            calibration_func: 校准函数
            *args, **kwargs: 传递给校准函数的参数

        Returns:
            task_id: 任务ID
        """
        task_id = str(uuid.uuid4())
        task = CalibrationTask(
            task_id=task_id,
            info_hash=info_hash,
            status=TaskStatus.PENDING
        )
        self.tasks[task_id] = task

        # 提交任务到线程池
        future = self.executor.submit(self._execute_task, task_id, calibration_func, *args, **kwargs)
        self.futures[task_id] = future

        logger.info(f"Task {task_id} submitted for info_hash: {info_hash}")
        return task_id

    def _execute_task(self, task_id: str, calibration_func, *args, **kwargs):
        """执行校准任务（在工作线程中运行）"""
        task = self.tasks.get(task_id)
        if not task:
            return

        try:
            task.status = TaskStatus.RUNNING
            logger.info(f"Task {task_id} started")

            # 执行校准函数
            result, error = calibration_func(*args, **kwargs)

            if result:
                task.status = TaskStatus.COMPLETED
                task.result = result
                logger.info(f"Task {task_id} completed successfully")
            else:
                task.status = TaskStatus.FAILED
                task.error = error or "Unknown error"
                logger.warning(f"Task {task_id} failed: {task.error}")

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Task {task_id} exception: {e}", exc_info=True)

        finally:
            task.completed_at = time.time()
            # 清理 future 引用
            self.futures.pop(task_id, None)

    def get_task_status(self, task_id: str) -> Optional[CalibrationTask]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            CalibrationTask 或 None
        """
        return self.tasks.get(task_id)

    def cleanup_old_tasks(self):
        """清理过期的任务结果"""
        current_time = time.time()
        expired_tasks = [
            task_id for task_id, task in self.tasks.items()
            if task.completed_at and (current_time - task.completed_at) > self.task_ttl
        ]

        for task_id in expired_tasks:
            self.tasks.pop(task_id, None)
            logger.debug(f"Cleaned up expired task: {task_id}")

        if expired_tasks:
            logger.info(f"Cleaned up {len(expired_tasks)} expired tasks")

    def shutdown(self, wait: bool = True):
        """关闭管理器"""
        logger.info("Shutting down AsyncCalibrationManager")
        self.executor.shutdown(wait=wait)


# 全局单例
_async_calibration_manager: Optional[AsyncCalibrationManager] = None


def get_async_calibration_manager() -> AsyncCalibrationManager:
    """获取全局异步校准管理器实例"""
    global _async_calibration_manager
    if _async_calibration_manager is None:
        _async_calibration_manager = AsyncCalibrationManager(max_workers=5)
    return _async_calibration_manager
```

### 2. 修改 Web API 路由

```python
# web/routes/api.py 中添加新的异步接口

from bot.services.async_calibration_manager import (
    get_async_calibration_manager,
    TaskStatus
)

@app.route('/api/calibrate/async', methods=['POST'])
def calibrate_async():
    """异步校准接口 - 立即返回任务ID"""
    if not session.get('logged_in'):
        return jsonify({'error': '未登录'}), 401

    data = request.get_json()
    info_hash = data.get('info_hash')

    if not info_hash:
        return jsonify({'error': '缺少 info_hash 参数'}), 400

    # 提交异步任务
    manager = get_async_calibration_manager()
    task_id = manager.submit_task(
        info_hash=info_hash,
        calibration_func=_run_calibration_script,
        script_path='calibrate_qbt_helper.py',
        info_hash=info_hash,
        timeout=30
    )

    return jsonify({
        'task_id': task_id,
        'status': 'pending'
    })


@app.route('/api/calibrate/status/<task_id>', methods=['GET'])
def calibrate_status(task_id):
    """查询校准任务状态"""
    if not session.get('logged_in'):
        return jsonify({'error': '未登录'}), 401

    manager = get_async_calibration_manager()
    task = manager.get_task_status(task_id)

    if not task:
        return jsonify({'error': '任务不存在'}), 404

    response = {
        'task_id': task.task_id,
        'status': task.status.value,
        'info_hash': task.info_hash
    }

    if task.status == TaskStatus.COMPLETED:
        response['result'] = task.result
    elif task.status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
        response['error'] = task.error

    return jsonify(response)
```

### 3. 前端适配（轮询方案）

```javascript
// static/js/notes.js 中添加异步校准逻辑

async function calibrateAsync(infoHash) {
    // 1. 提交任务
    const submitResponse = await fetch('/api/calibrate/async', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({info_hash: infoHash})
    });

    const {task_id} = await submitResponse.json();

    // 2. 轮询任务状态
    return new Promise((resolve, reject) => {
        const pollInterval = setInterval(async () => {
            const statusResponse = await fetch(`/api/calibrate/status/${task_id}`);
            const status = await statusResponse.json();

            if (status.status === 'completed') {
                clearInterval(pollInterval);
                resolve(status.result);
            } else if (status.status === 'failed' || status.status === 'timeout') {
                clearInterval(pollInterval);
                reject(new Error(status.error));
            }
            // pending 或 running 状态继续轮询
        }, 1000); // 每秒轮询一次

        // 最多轮询 60 秒
        setTimeout(() => {
            clearInterval(pollInterval);
            reject(new Error('轮询超时'));
        }, 60000);
    });
}
```

### 4. 定期清理任务

```python
# main.py 或 app.py 中添加定期清理

from apscheduler.schedulers.background import BackgroundScheduler
from bot.services.async_calibration_manager import get_async_calibration_manager

def cleanup_calibration_tasks():
    """定期清理过期的校准任务"""
    manager = get_async_calibration_manager()
    manager.cleanup_old_tasks()

# 启动定期清理（每小时执行一次）
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_calibration_tasks, 'interval', hours=1)
scheduler.start()
```

## 实施优先级

### P0（立即实施）
1. ✅ 创建 `AsyncCalibrationManager` 类
2. ✅ 添加 Web API 异步接口（`/api/calibrate/async` 和 `/api/calibrate/status/<task_id>`）
3. ✅ 前端适配轮询逻辑

### P1（后续优化）
1. 添加任务取消功能
2. 支持批量校准
3. 添加任务优先级队列
4. 持久化任务状态（使用 SQLite）

### P2（长期规划）
1. 使用 Redis 支持分布式部署
2. WebSocket 实时推送任务状态
3. 任务重试机制

## 测试计划

### 单元测试
```python
# tests/unit/test_async_calibration_manager.py

def test_submit_task():
    """测试提交任务"""
    manager = AsyncCalibrationManager(max_workers=2)

    def mock_calibration(info_hash):
        time.sleep(0.1)
        return f"filename_{info_hash}.mkv", None

    task_id = manager.submit_task("ABC123", mock_calibration, "ABC123")
    assert task_id is not None

    # 等待任务完成
    time.sleep(0.5)
    task = manager.get_task_status(task_id)
    assert task.status == TaskStatus.COMPLETED
    assert task.result == "filename_ABC123.mkv"

def test_task_failure():
    """测试任务失败"""
    manager = AsyncCalibrationManager(max_workers=2)

    def mock_calibration_fail(info_hash):
        return None, "Calibration failed"

    task_id = manager.submit_task("ABC123", mock_calibration_fail, "ABC123")
    time.sleep(0.5)

    task = manager.get_task_status(task_id)
    assert task.status == TaskStatus.FAILED
    assert task.error == "Calibration failed"
```

### 集成测试
1. 测试 Web API 异步接口
2. 测试前端轮询逻辑
3. 测试并发校准任务
4. 测试任务清理机制

## 回滚方案

如果异步方案出现问题，可以快速回滚：

1. 保留原有的同步接口 `/api/calibrate`
2. 前端可以通过配置切换使用同步或异步接口
3. 异步管理器可以独立禁用，不影响其他功能

## 性能预期

### 改进前
- 单个校准请求阻塞 10-30 秒
- 并发请求受限于 Web worker 数量（通常 4-8 个）
- 用户体验差，需要等待

### 改进后
- 请求立即返回（< 100ms）
- 支持更高并发（ThreadPoolExecutor 可配置）
- 用户体验好，可以继续其他操作
- Web worker 不被阻塞，可以处理更多请求

## 代码质量保证

### SOLID 原则应用
- **S (单一职责)**：`AsyncCalibrationManager` 只负责任务调度和状态管理
- **O (开闭原则)**：通过传入 `calibration_func` 支持不同的校准实现
- **D (依赖倒置)**：依赖抽象的校准函数接口，而非具体实现

### KISS 原则
- 使用标准库 `concurrent.futures`，无额外依赖
- 内存存储任务状态，简单直接
- 轮询方案简单可靠

### YAGNI 原则
- 不实现分布式支持（当前不需要）
- 不实现复杂的任务优先级（当前不需要）
- 不实现 WebSocket 推送（轮询足够）

## 总结

这个方案遵循最小化原则，使用 Python 标准库实现异步校准，解决了 Web 路由阻塞问题，提升了系统可用性和用户体验。实现简单、可维护性高，符合 KISS 和 YAGNI 原则。
