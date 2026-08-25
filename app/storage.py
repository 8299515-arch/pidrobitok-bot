from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import re
from threading import Lock

from app.saved_searches import SavedSearch


class SQLiteStorage:
    _TELEGRAM_CHANNEL_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

    def __init__(self, database_path: str) -> None:
        path = Path(database_path)
        if path.parent != Path('.'):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = Lock()
        self._closed = False
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
            columns = {str(row[1]) for row in self._connection.execute("PRAGMA table_info(saved_searches)").fetchall()}
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
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_jobs (
                    source_id TEXT PRIMARY KEY,
                    channel_username TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    city TEXT,
                    published_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_channels (
                    username TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def get_admin_stats(self) -> dict[str, int | str | None]:
        with self._lock:
            users = int(self._connection.execute("SELECT COUNT(*) FROM candidate_profiles").fetchone()[0])
            jobs = int(self._connection.execute("SELECT COUNT(*) FROM telegram_jobs").fetchone()[0])
            searches = int(self._connection.execute("SELECT COUNT(*) FROM saved_searches").fetchone()[0])
            deliveries = int(self._connection.execute("SELECT COUNT(*) FROM search_deliveries").fetchone()[0])
            channels = int(self._connection.execute("SELECT COUNT(*) FROM telegram_channels WHERE enabled = 1").fetchone()[0])
            disabled_channels = int(self._connection.execute("SELECT COUNT(*) FROM telegram_channels WHERE enabled = 0").fetchone()[0])
            job_channels = int(self._connection.execute("SELECT COUNT(DISTINCT lower(channel_username)) FROM telegram_jobs").fetchone()[0])
            row = self._connection.execute("SELECT published_at FROM telegram_jobs ORDER BY published_at DESC LIMIT 1").fetchone()
        return {
            "users": users,
            "jobs": jobs,
            "searches": searches,
            "deliveries": deliveries,
            "channels": channels,
            "disabled_channels": disabled_channels,
            "job_channels": job_channels,
            "last_job": str(row["published_at"]) if row is not None else None,
        }

    def seed_telegram_channels(self, channels: tuple[str, ...]) -> None:
        normalized_channels = []
        for channel in channels:
            try:
                normalized_channels.append(self.normalize_telegram_channel(channel))
            except ValueError:
                continue
        with self._lock, self._connection:
            for username in dict.fromkeys(normalized_channels):
                self._connection.execute(
                    "INSERT OR IGNORE INTO telegram_channels (username) VALUES (?)",
                    (username,),
                )

    def add_telegram_channel(self, channel: str) -> tuple[str, bool]:
        username = self.normalize_telegram_channel(channel)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            existing = self._connection.execute(
                "SELECT enabled FROM telegram_channels WHERE username = ?",
                (username,),
            ).fetchone()
            if existing is None:
                self._connection.execute(
                    "INSERT INTO telegram_channels (username, enabled, created_at, updated_at) VALUES (?, 1, ?, ?)",
                    (username, now, now),
                )
                return username, True
            self._connection.execute(
                "UPDATE telegram_channels SET enabled = 1, updated_at = ? WHERE username = ?",
                (now, username),
            )
        return username, False

    def set_telegram_channel_enabled(self, channel: str, enabled: bool) -> bool:
        username = self.normalize_telegram_channel(channel)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE telegram_channels SET enabled = ?, updated_at = ? WHERE username = ?",
                (int(enabled), now, username),
            )
        return cursor.rowcount == 1

    def list_telegram_channels(self) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT
                    telegram_channels.username,
                    telegram_channels.enabled,
                    telegram_channels.created_at,
                    telegram_channels.updated_at,
                    COUNT(telegram_jobs.source_id) AS jobs
                FROM telegram_channels
                LEFT JOIN telegram_jobs
                    ON lower(telegram_jobs.channel_username) = telegram_channels.username
                GROUP BY
                    telegram_channels.username,
                    telegram_channels.enabled,
                    telegram_channels.created_at,
                    telegram_channels.updated_at
                ORDER BY telegram_channels.enabled DESC, telegram_channels.username
                """
            ).fetchall()
        return [
            {
                "username": str(row["username"]),
                "enabled": bool(row["enabled"]),
                "jobs": int(row["jobs"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]

    def list_active_telegram_channels(self) -> tuple[str, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT username FROM telegram_channels WHERE enabled = 1 ORDER BY username"
            ).fetchall()
        return tuple(str(row["username"]) for row in rows)

    def has_telegram_channels(self) -> bool:
        with self._lock:
            row = self._connection.execute("SELECT 1 FROM telegram_channels LIMIT 1").fetchone()
        return row is not None

    def is_telegram_channel_enabled(self, channel: str) -> bool:
        try:
            username = self.normalize_telegram_channel(channel)
        except ValueError:
            return False
        with self._lock:
            row = self._connection.execute(
                "SELECT enabled FROM telegram_channels WHERE username = ?",
                (username,),
            ).fetchone()
        return row is not None and bool(row["enabled"])

    @classmethod
    def normalize_telegram_channel(cls, value: str) -> str:
        channel = value.strip()
        for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
            if channel.casefold().startswith(prefix):
                channel = channel[len(prefix):]
                break
        username = channel.strip().removeprefix("@").strip().strip("/").split("/", 1)[0].strip()
        if not username or not cls._TELEGRAM_CHANNEL_RE.fullmatch(username):
            raise ValueError("Telegram channel must be a public username like @channel_name")
        return username.casefold()

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
            rows = self._connection.execute("SELECT id, user_id, query, interval_minutes, enabled, created_at FROM saved_searches WHERE enabled = 1 ORDER BY id").fetchall()
        return [self._saved_search_from_row(row) for row in rows]

    def mark_saved_search_checked(self, search_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute("UPDATE saved_searches SET last_checked_at = ? WHERE id = ?", (now, search_id))

    def saved_search_due(self, search: SavedSearch) -> bool:
        with self._lock:
            row = self._connection.execute("SELECT last_checked_at FROM saved_searches WHERE id = ?", (search.search_id,)).fetchone()
        if row is None or row["last_checked_at"] is None:
            return True
        try:
            last_checked = datetime.fromisoformat(str(row["last_checked_at"]))
        except ValueError:
            return True
        if last_checked.tzinfo is None:
            last_checked = last_checked.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last_checked).total_seconds() >= search.interval_minutes * 60

    def delete_saved_search(self, user_id: int, search_id: int) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute("DELETE FROM saved_searches WHERE id = ? AND user_id = ?", (search_id, user_id))
        return cursor.rowcount == 1

    def has_search_deliveries(self, search_id: int) -> bool:
        with self._lock:
            row = self._connection.execute("SELECT 1 FROM search_deliveries WHERE search_id = ? LIMIT 1", (search_id,)).fetchone()
        return row is not None

    def was_search_job_delivered(self, search_id: int, job_url: str) -> bool:
        with self._lock:
            row = self._connection.execute("SELECT 1 FROM search_deliveries WHERE search_id = ? AND job_url = ?", (search_id, job_url)).fetchone()
        return row is not None

    def mark_search_job_delivered(self, search_id: int, job_url: str) -> None:
        with self._lock, self._connection:
            self._connection.execute("INSERT OR IGNORE INTO search_deliveries (search_id, job_url) VALUES (?, ?)", (search_id, job_url))

    def save_telegram_post(
        self,
        *,
        channel_username: str,
        message_id: int,
        title: str,
        description: str,
        url: str,
        published_at: datetime,
        city: str | None = None,
    ) -> None:
        source_id = f"{channel_username}:{message_id}"
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO telegram_jobs (source_id, channel_username, message_id, title, description, url, city, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    url = excluded.url,
                    city = excluded.city,
                    published_at = excluded.published_at
                """,
                (source_id, channel_username, message_id, title, description, url, city, published_at.astimezone(timezone.utc).isoformat()),
            )

    def list_telegram_jobs(self, channels: tuple[str, ...], limit: int = 50) -> list[sqlite3.Row]:
        normalized = tuple(channel.removeprefix("@").strip().casefold() for channel in channels if channel.strip())
        if not normalized:
            return []
        placeholders = ",".join("?" for _ in normalized)
        with self._lock:
            return self._connection.execute(
                f"SELECT source_id, channel_username, message_id, title, description, url, city, published_at FROM telegram_jobs WHERE lower(channel_username) IN ({placeholders}) ORDER BY published_at DESC LIMIT ?",
                (*normalized, limit),
            ).fetchall()

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
