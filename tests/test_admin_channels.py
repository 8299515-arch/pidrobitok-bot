from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path

from app.storage import SQLiteStorage


def _storage() -> tuple[TemporaryDirectory[str], SQLiteStorage]:
    temp_dir = TemporaryDirectory()
    storage = SQLiteStorage(str(Path(temp_dir.name) / "test.sqlite3"))
    return temp_dir, storage


def test_add_telegram_channel_normalizes_and_reenables_channel():
    temp_dir, storage = _storage()
    try:
        username, created = storage.add_telegram_channel("https://t.me/My_Channel/42")

        assert username == "my_channel"
        assert created is True
        assert storage.list_active_telegram_channels() == ("my_channel",)

        assert storage.set_telegram_channel_enabled("@my_channel", False) is True

        username, created = storage.add_telegram_channel("t.me/my_channel")

        assert username == "my_channel"
        assert created is False
        assert storage.list_active_telegram_channels() == ("my_channel",)
    finally:
        storage.close()
        temp_dir.cleanup()


def test_seed_telegram_channels_does_not_reenable_disabled_channels():
    temp_dir, storage = _storage()
    try:
        storage.seed_telegram_channels(("@FirstChannel",))
        assert storage.list_active_telegram_channels() == ("firstchannel",)

        assert storage.set_telegram_channel_enabled("@FirstChannel", False) is True

        storage.seed_telegram_channels(("@FirstChannel", "@SecondChannel"))

        assert storage.list_active_telegram_channels() == ("secondchannel",)
        channels = {channel["username"]: channel for channel in storage.list_telegram_channels()}
        assert channels["firstchannel"]["enabled"] is False
        assert channels["secondchannel"]["enabled"] is True
    finally:
        storage.close()
        temp_dir.cleanup()


def test_admin_stats_count_configured_channels_separately_from_job_channels():
    temp_dir, storage = _storage()
    try:
        storage.seed_telegram_channels(("@FirstChannel", "@SecondChannel"))
        storage.set_telegram_channel_enabled("@SecondChannel", False)

        stats = storage.get_admin_stats()

        assert stats["channels"] == 1
        assert stats["disabled_channels"] == 1
        assert stats["job_channels"] == 0
    finally:
        storage.close()
        temp_dir.cleanup()
