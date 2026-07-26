from __future__ import annotations

from random import Random

from bot.services.pt_pay_models import (
    describe_trigger_delay_spec,
    normalize_trigger_delay_spec,
    resolve_trigger_delay_seconds,
)


def test_normalize_trigger_delay_spec_supports_single_value_and_range():
    assert normalize_trigger_delay_spec("5") == "5"
    assert normalize_trigger_delay_spec("0-100") == "0-100"
    assert normalize_trigger_delay_spec("1.500-2") == "1.5-2"


def test_resolve_trigger_delay_seconds_randomizes_within_range():
    value = resolve_trigger_delay_seconds("0-100", rng=Random(0))
    assert 0 <= value <= 100
    assert round(value, 3) == round(84.4421851525048, 3)


def test_describe_trigger_delay_spec_formats_for_display():
    assert describe_trigger_delay_spec("5") == "固定 5 秒"
    assert describe_trigger_delay_spec("0-100") == "随机 0-100 秒"
