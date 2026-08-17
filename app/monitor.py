from __future__ import annotations

import asyncio
import logging

from telegram import Bot

from app.agent import CareerAgent
from app.saved_searches import SavedSearchStore

logger = logging.getLogger(__name__)


class SavedSearchMonitor:
    def __init__(self, bot: Bot, agent: CareerAgent, searches: SavedSearchStore, poll_seconds: int = 60) -> None:
        self._bot = bot
        self._agent = agent
        self._searches = searches
        self._poll_seconds = max(30, poll_seconds)
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopped.clear()
            self._task = asyncio.create_task(self._run(), name="saved-search-monitor")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is None:
            return
        try:
            await self._task
        finally:
            self._task = None

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                await self._tick()
            except Exception:
                logger.exception("Saved-search monitor tick failed")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self._poll_seconds)
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        for search in self._searches.active():
            if self._stopped.is_set():
                return
            if not self._searches.due(search):
                continue
            try:
                ranked_jobs = await self._agent.search_ranked_jobs(search.user_id, search.query)
                new_jobs = [
                    ranked for ranked in ranked_jobs
                    if not self._searches.was_delivered(search.search_id, ranked.job.url)
                ]
                for ranked in reversed(new_jobs[:5]):
                    await self._bot.send_message(
                        chat_id=search.user_id,
                        text=self._agent.format_ranked_job(ranked),
                        disable_web_page_preview=True,
                    )
                    self._searches.mark_delivered(search.search_id, ranked.job.url)
            except Exception:
                logger.exception("Saved search %s failed", search.search_id)
            finally:
                self._searches.mark_checked(search.search_id)
