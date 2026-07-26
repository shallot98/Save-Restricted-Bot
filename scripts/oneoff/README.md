# scripts/oneoff

历史一次性运维 / 排障脚本归档。**无任何生产代码 import 或调用**（归档前已逐个用
`rg` 在 `bot/ src/ web/ main.py app.py database*.py Dockerfile .github/ docker/` 中复核）。

约定：

- 不入镜像：`.dockerignore` 是白名单式，`scripts/*` 被排除、只放行 `scripts/runtime`。
- 不做类型检查：`mypy.ini` 的 `exclude` 含 `^scripts/oneoff/`。
- 不进 pytest：`pytest.ini` 的 `testpaths = tests/unit`。
- 这里的脚本大多针对当时的数据形态一次性执行，**再次运行前必须先读代码确认语义**，
  部分会直接写生产库。

需要长期运行的组件放 `scripts/runtime/`（见该目录 README），不要放这里。
