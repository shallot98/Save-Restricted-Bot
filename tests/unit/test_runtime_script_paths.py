"""
Unit tests for runtime calibration script resolution (scripts/runtime/).

Covers report task #11 / P1-7:
- the two calibration helpers must be found at their new location;
- a missing script must be reported at ERROR level, not silently swallowed.
"""

from __future__ import annotations

import logging

import pytest

from src.core.utils import script_paths
from src.core.utils.script_paths import RUNTIME_SCRIPTS_DIR, resolve_runtime_script


@pytest.fixture(autouse=True)
def _reset_missing_state():
    script_paths._missing_reported.clear()
    yield
    script_paths._missing_reported.clear()


@pytest.mark.parametrize(
    "script_name",
    ["calibrate_qbt_helper.py", "calibrate_bot_helper.py"],
)
def test_production_helpers_resolve_in_scripts_runtime(script_name):
    resolved = resolve_runtime_script(script_name)

    assert resolved is not None, f"{script_name} 必须存在于 scripts/runtime/"
    assert resolved.is_file()
    assert resolved.parent == RUNTIME_SCRIPTS_DIR


def test_missing_script_is_logged_as_error(caplog):
    with caplog.at_level(logging.ERROR, logger=script_paths.__name__):
        resolved = resolve_runtime_script("definitely_missing_helper.py")

    assert resolved is None
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "definitely_missing_helper.py" in errors[0].getMessage()


def test_missing_script_error_is_rate_limited(caplog):
    with caplog.at_level(logging.DEBUG, logger=script_paths.__name__):
        resolve_runtime_script("definitely_missing_helper.py")
        resolve_runtime_script("definitely_missing_helper.py")

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1


def test_mixin_script_path_uses_runtime_dir():
    from bot.services.calibration_scripts import CalibrationScriptMixin

    path = CalibrationScriptMixin._script_path("calibrate_qbt_helper.py")

    assert path == str(RUNTIME_SCRIPTS_DIR / "calibrate_qbt_helper.py")
    assert CalibrationScriptMixin._script_path("definitely_missing_helper.py") is None


def test_workflow_service_script_path_uses_runtime_dir():
    from src.application.services.calibration_workflow_service import (
        CalibrationWorkflowService,
    )

    path = CalibrationWorkflowService._get_script_path("calibrate_bot_helper.py")

    assert path == str(RUNTIME_SCRIPTS_DIR / "calibrate_bot_helper.py")
    assert (
        CalibrationWorkflowService._get_script_path("definitely_missing_helper.py")
        is None
    )
