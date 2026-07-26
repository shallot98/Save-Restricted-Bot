#!/usr/bin/env python3
"""对比 mypy 输出与 scripts/mypy_baseline.txt，只有【新增】错误才失败。

用法：`mypy --no-pretty --no-color-output > mypy.out || true`
      `python3 scripts/check_mypy_baseline.py mypy.out [--update]`
基线按 (文件, 错误码, 消息) 归一，忽略行列号，避免无关改动误报。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
import re

BASELINE = Path(__file__).resolve().parent / "mypy_baseline.txt"
HEADER = "# mypy 错误基线，由 scripts/check_mypy_baseline.py --update 生成。\n"
ERROR_RE = re.compile(r"^(?P<file>[^\s:]+):\d+(?::\d+)?: error: (?P<msg>.*?)(?:  \[(?P<code>[\w-]+)\])?$")
# mypy 跑完整轮次必然打印这两种收尾之一；缺失即代表它中途夭折。
COMPLETED_RE = re.compile(
    r"^(?:Success: no issues found in \d+ source files?"
    r"|Found \d+ errors? in \d+ files? \(checked \d+ source files?\))$"
)
ABORTED_MARKER = "errors prevented further checking"


def check_run_completed(lines) -> str | None:
    """确认 mypy 真的跑完了，返回失败原因（None 表示正常）。

    存在的理由：mypy 以退出码 2 夭折时（例如模块重名），它只打印一行不含行号的
    错误 + `(errors prevented further checking)`，两者都匹配不上 ERROR_RE。
    于是「当前 0 / 新增 0」→ 门禁全绿，而实际上一行代码都没检查过。
    这正是报告 §3 P1-2 记录的历史故障，必须由本脚本自己堵住，
    不能依赖 CI 里那句 `|| true` 之后的退出码。
    """
    if any(ABORTED_MARKER in line for line in lines):
        return f"mypy 中途退出（输出含 {ABORTED_MARKER!r}），本次未完成全量检查"
    if not any(COMPLETED_RE.match(line.rstrip("\n")) for line in lines):
        return "未找到 mypy 收尾行，输出可能被截断或 mypy 根本没跑起来"
    return None


def normalize(lines) -> Counter:
    counter: Counter = Counter()
    for line in lines:
        matched = ERROR_RE.match(line.rstrip("\n"))
        if matched:
            counter[f"{matched['file']}\t{matched['code'] or '-'}\t{matched['msg']}"] += 1
    return counter


def load_baseline() -> Counter:
    if not BASELINE.exists():
        return Counter()
    raw = BASELINE.read_text(encoding="utf-8").splitlines()
    return Counter(line for line in raw if line and not line.startswith("#"))


def main(argv: list[str]) -> int:
    paths = [arg for arg in argv if not arg.startswith("--")]
    text = Path(paths[0]).read_text(encoding="utf-8") if paths else sys.stdin.read()
    lines = text.splitlines()

    # 先确认这轮 mypy 有效，再谈基线对比——否则「0 错误」是假绿而非成果。
    aborted = check_run_completed(lines)
    if aborted:
        print(f"mypy 运行无效：{aborted}", file=sys.stderr)
        print("请修复 mypy 自身的报错后重跑，不要在这种输出上更新基线。", file=sys.stderr)
        return 2

    current = normalize(lines)

    if "--update" in argv:
        BASELINE.write_text(HEADER + "\n".join(sorted(current.elements())) + "\n", encoding="utf-8")
        print(f"基线已更新：{sum(current.values())} 个错误")
        return 0

    baseline = load_baseline()
    added = {key: count - baseline[key] for key, count in current.items() if count > baseline[key]}
    fixed = sum(baseline.values()) - sum(current.values()) + sum(added.values())
    print(f"mypy 基线 {sum(baseline.values())} / 当前 {sum(current.values())} / 新增 {sum(added.values())} / 已修 {fixed}")
    if not added:
        return 0
    print("检测到新增 mypy 错误：", file=sys.stderr)
    for key, count in sorted(added.items()):
        file_name, code, msg = key.split("\t", 2)
        print(f"- [{code}] {file_name}: {msg} (x{count})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
