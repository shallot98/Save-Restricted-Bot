from src.application.services.watch_setup_service import WatchSetupService


class _DummyWatchService:
    def __init__(self) -> None:
        self.config = {}

    def get_all_configs_dict(self):
        return self.config

    def save_config_dict(self, config_dict):
        self.config = config_dict


def test_create_forward_watch_persists_config_and_message() -> None:
    service = WatchSetupService(_DummyWatchService())

    result = service.create_forward_watch(
        user_id="u1",
        source_id="src",
        source_name="Source",
        dest_id="dst",
        dest_name="Dest",
        whitelist=["foo"],
        blacklist=[],
        whitelist_regex=[],
        blacklist_regex=["bar.*"],
        preserve_source=True,
        forward_mode="extract",
        extract_patterns=["id=(\\d+)"],
    )

    assert result.duplicate is False
    assert result.watch_key == "src|dst"
    assert "Source" in result.message_text
    assert "Dest" in result.message_text
    assert "提取规则" in result.message_text
    assert service._watch_service.config["u1"]["src|dst"]["preserve_forward_source"] is True


def test_create_record_watch_detects_duplicate() -> None:
    watch_service = _DummyWatchService()
    watch_service.config = {
        "u1": {
            "src|record": {
                "source": "src",
                "dest": None,
                "whitelist": [],
                "blacklist": [],
                "whitelist_regex": [],
                "blacklist_regex": [],
                "preserve_forward_source": False,
                "forward_mode": "full",
                "extract_patterns": [],
                "record_mode": True,
            }
        }
    }
    service = WatchSetupService(watch_service)

    result = service.create_record_watch(
        user_id="u1",
        source_id="src",
        source_name="Source",
        whitelist=[],
        blacklist=[],
        whitelist_regex=[],
        blacklist_regex=[],
    )

    assert result.duplicate is True
    assert result.watch_key == "src|record"
    assert "该监控任务已存在" in result.message_text
