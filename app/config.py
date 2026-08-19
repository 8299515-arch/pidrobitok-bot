from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    google_api_key: str | None
    ai_model: str = "gemini-3.6-flash"
    max_history_messages: int = 12
    telegram_job_channels: tuple[str, ...] = ("@PodrabotkaKiev_1",)
    job_source_limit: int = 10
    database_path: str = "data/pidrobitok.sqlite3"
    monitor_poll_seconds: int = 60
    admin_user_ids: tuple[int, ...] = ()

    @classmethod
    def from_environment(cls) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        google_api_key = os.getenv("GOOGLE_API_KEY", "").strip() or None

        if not bot_token:
            raise RuntimeError("BOT_TOKEN is not configured")

        raw_channels = os.getenv("TELEGRAM_JOB_CHANNELS")
        channels = tuple(
            channel.strip()
            for channel in (raw_channels if raw_channels is not None else ",".join(cls.telegram_job_channels)).split(",")
            if channel.strip()
        )
        try:
            job_source_limit = max(1, int(os.getenv("JOB_SOURCE_LIMIT", "10")))
            monitor_poll_seconds = max(30, int(os.getenv("MONITOR_POLL_SECONDS", "60")))
        except ValueError as exc:
            raise RuntimeError("JOB_SOURCE_LIMIT and MONITOR_POLL_SECONDS must be integers") from exc

        database_path = os.getenv("DATABASE_PATH", "data/pidrobitok.sqlite3").strip()
        if not database_path:
            raise RuntimeError("DATABASE_PATH must not be empty")

        raw_admin_ids = os.getenv("ADMIN_USER_IDS", "")
        try:
            admin_user_ids = tuple(int(value.strip()) for value in raw_admin_ids.split(",") if value.strip())
        except ValueError as exc:
            raise RuntimeError("ADMIN_USER_IDS must contain Telegram numeric user IDs") from exc

        return cls(
            bot_token=bot_token,
            google_api_key=google_api_key,
            ai_model=os.getenv("AI_MODEL", "gemini-3.6-flash").strip(),
            telegram_job_channels=channels,
            job_source_limit=job_source_limit,
            database_path=database_path,
            monitor_poll_seconds=monitor_poll_seconds,
            admin_user_ids=admin_user_ids,
        )
