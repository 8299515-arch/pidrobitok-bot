from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.storage import SQLiteStorage


@dataclass(frozen=True)
class SavedSearch:
    search_id: int
    user_id: int
    query: str
    interval_minutes: int
    enabled: bool
    created_at: datetime


class SavedSearchStore:
    def __init__(self, storage: SQLiteStorage) -> None:
        self._storage = storage

    def create(self, user_id: int, query: str, interval_minutes: int) -> SavedSearch:
        if not query.strip():
            raise ValueError("query must not be empty")
        if interval_minutes < 5:
            raise ValueError("interval_minutes must be at least 5")
        return self._storage.create_saved_search(user_id, query.strip(), interval_minutes)

    def list_for_user(self, user_id: int) -> list[SavedSearch]:
        return self._storage.list_saved_searches(user_id)

    def delete(self, user_id: int, search_id: int) -> bool:
        return self._storage.delete_saved_search(user_id, search_id)

    def active(self) -> list[SavedSearch]:
        return self._storage.list_active_saved_searches()

    def was_delivered(self, search_id: int, job_url: str) -> bool:
        return self._storage.was_search_job_delivered(search_id, job_url)

    def mark_delivered(self, search_id: int, job_url: str) -> None:
        self._storage.mark_search_job_delivered(search_id, job_url)
