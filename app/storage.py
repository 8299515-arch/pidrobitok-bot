from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock


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

    def save_profile(
        self,
        user_id: int,
        skills: tuple[str, ...],
        city: str | None,
        salary_min: int | None,
        remote: bool,
    ) -> None:
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
