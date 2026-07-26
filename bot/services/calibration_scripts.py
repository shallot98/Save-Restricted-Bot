"""External script execution for magnet filename calibration."""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from src.core.utils.script_paths import resolve_runtime_script

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalibrationScript:
    label: str
    path: Optional[str]


class CalibrationScriptMixin:
    def calibrate_magnet(
        self,
        magnet_hash: str,
        timeout: int = 30,
        prefer_bot: bool = True,
    ) -> Optional[str]:
        try:
            scripts = self._ordered_calibration_scripts(prefer_bot)
            for idx, script in enumerate(scripts):
                filename = self._try_calibration_script(script, magnet_hash, timeout)
                if filename:
                    return filename
                self._log_next_script_fallback(scripts, idx)
            logger.error("❌ 所有校准方式都失败了")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️ 校准超时（{timeout}秒）")
            return None
        except Exception as exc:
            logger.error(f"校准过程出错: {exc}", exc_info=True)
            return None

    def _ordered_calibration_scripts(self, prefer_bot: bool) -> list[CalibrationScript]:
        qbt_script = CalibrationScript("qBittorrent API", self._script_path("calibrate_qbt_helper.py"))
        bot_script = CalibrationScript("Telegram机器人", self._script_path("calibrate_bot_helper.py"))
        if prefer_bot:
            logger.info("🔄 自动校准模式：优先使用Telegram机器人")
            return [bot_script, qbt_script]
        logger.info("🔄 手动校准模式：优先使用qBittorrent API")
        return [qbt_script, bot_script]

    @staticmethod
    def _script_path(script_name: str) -> Optional[str]:
        """Resolve a runtime script; missing files are logged by the resolver."""
        path = resolve_runtime_script(script_name)
        return str(path) if path else None

    def _try_calibration_script(
        self,
        script: CalibrationScript,
        magnet_hash: str,
        timeout: int,
    ) -> Optional[str]:
        if not script.path:
            return None
        logger.info(f"🔄 使用{script.label}校准: {magnet_hash[:16]}...")
        result = subprocess.run(
            [sys.executable, script.path, magnet_hash],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return self._parse_calibration_result(script, result)

    @staticmethod
    def _parse_calibration_result(script: CalibrationScript, result) -> Optional[str]:
        if result.returncode == 0 and result.stdout.strip():
            filename = result.stdout.strip()
            logger.info(f"✅ {script.label}校准成功: {filename[:50]}...")
            return filename
        error_msg = result.stderr.strip() if result.stderr else "未知错误"
        logger.warning(f"⚠️ {script.label}校准失败: {error_msg[:100]}")
        return None

    @staticmethod
    def _log_next_script_fallback(scripts: list[CalibrationScript], idx: int) -> None:
        if idx + 1 >= len(scripts):
            return
        next_script = scripts[idx + 1]
        if next_script.path:
            logger.info(f"🔄 回退到{next_script.label}方式...")
