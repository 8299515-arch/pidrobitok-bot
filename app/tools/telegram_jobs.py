from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
import re

from app.domain.jobs import EmploymentType, Job, JobSource
from app.storage import SQLiteStorage


class TelegramJobSource:
    """Searches Telegram channel posts captured by the bot."""

    def __init__(self, channels: Sequence[str], database_path: str) -> None:
        self._channels = tuple(self._normalize_channel(channel) for channel in channels if channel.strip())
        self._database_path = database_path

    @property
    def name(self) -> str:
        return JobSource.TELEGRAM.value

    @property
    def configured(self) -> bool:
        return bool(self._channels)

    async def search(
        self,
        query: str,
        *,
        location: str | None = None,
        limit: int = 10,
    ) -> list[Job]:
        if not self._channels or limit <= 0:
            return []

        terms = [part.casefold() for part in query.split() if part.strip()]
        if location:
            terms.append(location.casefold())

        storage = SQLiteStorage(self._database_path)
        try:
            rows = storage.list_telegram_jobs(self._channels, limit=max(limit * 5, 50))
        finally:
            storage.close()

        jobs: list[Job] = []
        for row in rows:
            text = str(row["description"])
            if not self._matches(text, terms):
                continue
            published_at = self._parse_datetime(str(row["published_at"]))
            jobs.append(
                Job(
                    title=str(row["title"]),
                    url=str(row["url"]),
                    source=JobSource.TELEGRAM,
                    city=str(row["city"]) if row["city"] else location,
                    employment_type=self._extract_employment_type(text),
                    remote=self._extract_remote(text),
                    description=text[:4000],
                    published_at=published_at,
                    source_id=str(row["source_id"]),
                )
            )
            if len(jobs) >= limit:
                break
        return jobs

    async def health(self) -> dict[str, object]:
        return {
            "source": self.name,
            "available": bool(self._channels),
            "channels_configured": len(self._channels),
            "mode": "telegram_bot_api_ingestion",
        }

    @staticmethod
    def _normalize_channel(value: str) -> str:
        return value.strip().removeprefix("@").removeprefix("https://t.me/").strip("/")

    @staticmethod
    def _matches(text: str, terms: list[str]) -> bool:
        if not terms:
            return True
        normalized = text.casefold()
        return any(term in normalized for term in terms)

    @staticmethod
    def _build_title(text: str) -> str:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), text.strip())
        return first_line[:180]

    @classmethod
    def _extract_employment_type(cls, text: str) -> EmploymentType:
        normalized = text.casefold()
        if re.search(r"full[- ]?time|повна зайнятість|полная занятость", normalized):
            return EmploymentType.FULL_TIME
        if re.search(r"part[- ]?time|неповна зайнятість|частичная занятость|подработка|підробіт", normalized):
            return EmploymentType.PART_TIME
        if re.search(r"contract|контракт|договор", normalized):
            return EmploymentType.CONTRACT
        return EmploymentType.UNKNOWN

    @staticmethod
    def _extract_remote(text: str) -> bool | None:
        normalized = text.casefold()
        if re.search(r"remote|віддал|удален|дистанцион", normalized):
            return True
        return None

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
