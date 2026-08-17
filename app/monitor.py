from __future__ import annotations

import asyncio
import logging

from telegram import Bot

from app.agent import CareerAgent
from app.saved_searches import SavedSearch, SavedSearchStore
from app.tools.job_ranker import RankedJob

logger = logging.getLogger(__name__)


class SavedSearchMonitor:
    def __init__(self, bot: Bot, agent: CareerAgent, searches: SavedSearchStore, poll_seconds: int = 60) -> None:
        self._bot = bot
        self._agent = agent
        self._searches = searches
        self._poll_seconds = max(30, poll_seconds)
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._search_tasks: set[asyncio.Task[None]] = set()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopped.clear()
            self._task = asyncio.create_task(self._run(), name="saved-search-monitor")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None
        tasks = tuple(self._search_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._search_tasks.clear()

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
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
            task = asyncio.create_task(self._process_search(search), name=f"saved-search-{search.search_id}")
            self._search_tasks.add(task)
            task.add_done_callback(self._search_tasks.discard)

    async def _process_search(self, search: SavedSearch) -> None:
        try:
            ranked_jobs = await self._agent.search_ranked_jobs(search.user_id, search.query)
            if not self._searches.has_deliveries(search.search_id):
                for ranked in ranked_jobs:
                    self._searches.mark_delivered(search.search_id, ranked.job.url)
                logger.info("Bootstrapped saved search %s with %s existing jobs", search.search_id, len(ranked_jobs))
                return

            new_jobs = [
                ranked
                for ranked in ranked_jobs
                if not self._searches.was_delivered(search.search_id, ranked.job.url)
            ]
            for ranked in reversed(new_jobs[:5]):
                await self._send_ranked_job(search.user_id, ranked)
                self._searches.mark_delivered(search.search_id, ranked.job.url)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Saved search %s failed", search.search_id)
        finally:
            self._searches.mark_checked(search.search_id)

    async def _send_ranked_job(self, chat_id: int, ranked: RankedJob) -> None:
        text = self._agent.format_ranked_job(ranked)
        limit = 3900
        for start in range(0, len(text), limit):
            await self._bot.send_message(
                chat_id=chat_id,
                text=text[start : start + limit],
                disable_web_page_preview=True,
            )
