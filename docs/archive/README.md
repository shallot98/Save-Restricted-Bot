# docs/archive

仓库根目录历史流水账文档归档（原 78 个 `*.md` + `COMMIT_MESSAGE.txt`）。

**这些文档大面积与当前代码事实矛盾，不要作为事实来源。**
见 `docs/ARCHITECTURE_REFACTOR_REPORT_2026-07-26.md` §3 P2-14 实测举例：

- `MIGRATION_COMPLETE.md` 称 `callbacks.py` 931 行，实测 36 行
- `ARCHITECTURE_ANALYSIS.md` 称 `app.py` 892 行（实测 41）、代码 18,500 行（实测 79,024）
- `CONFIG_PRIORITY_UPDATE.md` 写的配置优先级与实测相反（实测为
  环境变量 > `data/config/config.json` > `.env` > 默认值）

保留原因只有一个：作为改动历史备查。判断当前行为请读代码与测试。
当前有效文档在 `docs/` 的其余子目录与仓库根的 `README.md` / `README.zh-CN.md`。
