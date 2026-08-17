from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.saved_searches import SavedSearch


class SQLiteStorage:
    def __init__(self, database_path: str) -> None:
        path = Path(database_path)
        if path.parent != Path('.'):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = Lock()
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_profiles (
                    user_id INTEGER PRIMARY KEY,
                    skills TEXT NOT NULL DEFAULT '',
                    city TEXT,
                    salary_min INTEGER,
                    remote INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_checked_at TEXT
                )
                """
            )
            columns = {
                str(row[1]) for row in self._connection.execute("PRAGMA table_info(saved_searches)").fetchall()
            }
            if "last_checked_at" not in columns:
                self._connection.execute("ALTER TABLE saved_searches ADD COLUMN last_checked_at TEXT")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS search_deliveries (
                    search_id INTEGER NOT NULL,
                    job_url TEXT NOT NULL,
                    delivered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (search_id, job_url),
                    FOREIGN KEY (search_id) REFERENCES saved_searches(id) ON DELETE CASCADE
                )
                """
            )

    def get_profile(self, user_id: int) -> tuple[tuple[str, ...], str | None, int | None, bool] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT skills, city, salary_min, remote FROM candidate_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        skills = tuple(skill for skill in row["skills"].split(",") if skill)
        return skills, row["city"], row["salary_min"], bool(row["remote"])

    def save_profile(self, user_id: int, skills: tuple[str, ...], city: str | None, salary_min: int | None, remote: bool) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO candidate_profiles (user_id, skills, city, salary_min, remote, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    skills = excluded.skills,
                    city = excluded.city,
                    salary_min = excluded.salary_min,
                    remote = excluded.remote,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, ",".join(skills), city, salary_min, int(remote)),
            )

    def create_saved_search(self, user_id: int, query: str, interval_minutes: int) -> SavedSearch:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO saved_searches (user_id, query, interval_minutes) VALUES (?, ?, ?)",
                (user_id, query, interval_minutes),
            )
            search_id = int(cursor.lastrowid)
            row = self._connection.execute(
                "SELECT id, user_id, query, interval_minutes, enabled, created_at FROM saved_searches WHERE id = ?",
                (search_id,),
            ).fetchone()
        return self._saved_search_from_row(row)

    def list_saved_searches(self, user_id: int) -> list[SavedSearch]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, user_id, query, interval_minutes, enabled, created_at FROM saved_searches WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
        return [self._saved_search_from_row(row) for row in rows]

    def list_active_saved_searches(self) -> list[SavedSearch]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, user_id, query, interval_minutes, enabled, created_at FROM saved_searches WHERE enabled = 1 ORDER BY id"
            ).fetchall()
        return [self._saved_search_from_row(row) for row in rows]

    def mark_saved_search_checked(self, search_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE saved_searches SET last_checked_at = ? WHERE id = ?",
                (now, search_id),
            )

    def saved_search_due(self, search: SavedSearch) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT last_checked_at FROM saved_searches WHERE id = ?",
                (search.search_id,),
            ).fetchone()
        if row is None or row["last_checked_at"] is None:
            return True
        try:
            last_checked = datetime.fromisoformat(str(row["last_checked_at"]))
        except ValueError:
            return True
        if last_checked.tzinfo is None:
            last_checked = last_checked.replace(tzinfo=timezone.utc)
        elapsed = datetime.now(timezone.utc) - last_checked
        return elapsed.total_seconds() >= search.interval_minutes * 60

    def delete_saved_search(self, user_id: int, search_id: int) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM saved_searches WHERE id = ? AND user_id = ?",
                (search_id, user_id),
            )
        return cursor.rowcount == 1

    def was_search_job_delivered(self, search_id: int, job_url: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM search_deliveries WHERE search_id = ? AND job_url = ?",
                (search_id, job_url),
            ).fetchone()
        return row is not None

    def mark_search_job_delivered(self, search_id: int, job_url: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO search_deliveries (search_id, job_url) VALUES (?, ?)",
                (search_id, job_url),
            )

    @staticmethod
    def _saved_search_from_row(row: sqlite3.Row) -> SavedSearch:
        return SavedSearch(
            search_id=int(row["id"]),
            user_id=int(row["user_id"]),
            query=str(row["query"]),
            interval_minutes=int(row["interval_minutes"]),
            enabled=bool(row["enabled"]),
            created_at=datetime.fromisoformat(str(row["created_at"]).replace(" ", "T")),
        )
