from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import re

import httpx
from bs4 import BeautifulSoup

from app.domain.jobs import Job, JobSource


class TelegramJobSource:
    """Reads recent posts from configured public Telegram channels."""

    _base_url = "https://t.me/s/"
    _user_agent = "Mozilla/5.0 (compatible; PidrobitokBot/1.0)"

    def __init__(self, channels: Sequence[str]) -> None:
        self._channels = tuple(self._normalize_channel(channel) for channel in channels if channel.strip())

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
        if not self._channels:
            return []

        terms = [part.casefold() for part in query.split() if part.strip()]
        if location:
            terms.append(location.casefold())

        headers = {"User-Agent": self._user_agent}
        jobs: list[Job] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for channel in self._channels:
                response = await client.get(f"{self._base_url}{channel}", headers=headers)
                if response.status_code in {403, 404}:
                    continue
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                for post in soup.select("div.tgme_widget_message"):
                    text_node = post.select_one("div.tgme_widget_message_text")
                    text = text_node.get_text(" ", strip=True) if text_node else ""
                    if not text or not self._matches(text, terms):
                        continue

                    post_id = post.get("data-post")
                    if not isinstance(post_id, str) or post_id in seen_ids:
                        continue
                    message_id = post_id.rsplit("/", 1)[-1]
                    url = f"https://t.me/{channel}/{message_id}"
                    title = self._build_title(text)
                    jobs.append(
                        Job(
                            title=title,
                            url=url,
                            source=JobSource.TELEGRAM,
                            city=location,
                            remote=self._extract_remote(text),
                            description=text[:4000],
                            published_at=datetime.now(timezone.utc),
                            source_id=post_id,
                        )
                    )
                    seen_ids.add(post_id)
                    if len(jobs) >= limit:
                        return jobs

        return jobs

    async def health(self) -> dict[str, object]:
        return {
            "source": self.name,
            "available": bool(self._channels),
            "channels_configured": len(self._channels),
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

    @staticmethod
    def _extract_remote(text: str) -> bool | None:
        normalized = text.casefold()
        if re.search(r"remote|віддал|удален|дистанцион", normalized):
            return True
        return None
