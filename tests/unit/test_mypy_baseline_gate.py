"""``scripts/check_mypy_baseline.py`` 的门禁自证。

为什么需要这组用例：报告 §3 P1-2 记录的历史故障是「CI 的类型检查步骤自诞生起
从未检查过一行代码」——mypy 因模块重名以退出码 2 夭折，而 CI 里那句
``mypy ... || true`` 把退出码吞掉了。夭折时 mypy 只打印一行**不含行号**的错误，
匹配不上基线脚本的 ERROR_RE，于是「当前 0 / 新增 0」→ 门禁全绿。

也就是说：这个门禁最危险的失败模式不是「漏报某条错误」，而是「整轮没跑却报绿」。
下面的用例把「必须跑完整轮」这件事本身钉成断言。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "check_mypy_baseline.py"

COMPLETED_TAIL = "Found 2 errors in 1 file (checked 296 source files)"
ABORTED_TAIL = "Found 1 error in 1 file (errors prevented further checking)"


def _run(mypy_output: str, tmp_path: Path) -> subprocess.CompletedProcess:
    out_file = tmp_path / "mypy.out"
    out_file.write_text(mypy_output, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(out_file)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_aborted_run_fails_instead_of_reporting_zero(tmp_path: Path) -> None:
    """mypy 夭折时必须失败——这正是 P1-2 的假绿路径。"""
    result = _run(
        'test_fixes.py: error: Duplicate module named "test_fixes"\n' + ABORTED_TAIL + "\n",
        tmp_path,
    )
    assert result.returncode != 0, f"夭折输出被判为通过：{result.stdout}"
    assert "mypy 运行无效" in result.stderr


def test_empty_output_fails(tmp_path: Path) -> None:
    """空输出（mypy 没跑起来）不得被当成「错误全修完了」。"""
    result = _run("", tmp_path)
    assert result.returncode != 0
    assert "未找到 mypy 收尾行" in result.stderr


def test_completed_run_within_baseline_passes(tmp_path: Path) -> None:
    """跑完且无新增错误时放行——用基线里真实存在的两条，避免误判为新增。"""
    baseline_lines = [
        line
        for line in (PROJECT_ROOT / "scripts" / "mypy_baseline.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ][:2]
    rendered = "\n".join(
        f"{file_name}:1:1: error: {msg}  [{code}]"
        for file_name, code, msg in (line.split("\t", 2) for line in baseline_lines)
    )
    result = _run(rendered + "\n" + COMPLETED_TAIL + "\n", tmp_path)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "新增 0" in result.stdout


def test_new_error_fails(tmp_path: Path) -> None:
    """基线之外的新错误必须让门禁失败。"""
    result = _run(
        "bot/brand_new_module.py:1:1: error: Something broke  [attr-defined]\n"
        + COMPLETED_TAIL
        + "\n",
        tmp_path,
    )
    assert result.returncode == 1
    assert "brand_new_module" in result.stderr
