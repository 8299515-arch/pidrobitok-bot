from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from app.domain.jobs import EmploymentType, Job, JobSource
from app.storage import SQLiteStorage


class TelegramJobSource:
    """Searches Telegram channel posts captured by the bot."""

    _JOB_MARKERS = (
        "ваканс", "вакансі", "требуется", "требуємо", "потрібен", "потрібна",
        "потрібні", "ищем", "шукаємо", "зарплат", "оплата", "ставка", "грн",
        "uah", "обязанност", "обов'язк", "обов’язк", "требован", "вимог",
        "график", "графік", "занятост", "зайнятіст", "подработ", "підробіт",
        "резюме", "відгук", "отклик",
    )
    _NON_JOB_MARKERS = ("тест", "test")
    _USER_REQUEST_MARKERS = (
        "найди", "найти", "ищи", "поищи", "покажи", "подбери", "найти актуаль",
        "найди актуаль", "пошукай", "шукаю", "ищу",
    )

    def __init__(self, channels: Sequence[str], database_path: str) -> None:
        self._channels = tuple(
            self._normalize_channel(channel) for channel in channels if channel.strip()
        )
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

        salary_min, salary_max = self._extract_salary_constraint(query)
        terms = [part.casefold() for part in query.split() if part.strip() and not any(char.isdigit() for char in part)]
        if location and location.casefold() not in terms:
            terms.append(location.casefold())

        storage = SQLiteStorage(self._database_path)
        try:
            rows = storage.list_telegram_jobs(self._channels, limit=max(limit * 5, 50))
        finally:
            storage.close()

        jobs: list[Job] = []
        for row in rows:
            text = str(row["description"])
            title = str(row["title"])
            if not self._is_job_post(title, text) or not self._matches(text, terms):
                continue

            job_salary_min, job_salary_max, currency = self._extract_salary(text)
            if salary_min is not None:
                if job_salary_max is None or job_salary_max < salary_min:
                    continue
            if salary_max is not None and job_salary_min is not None and job_salary_min > salary_max:
                continue
            if salary_max is not None and job_salary_min is None:
                continue

            published_at = self._parse_datetime(str(row["published_at"]))
            jobs.append(
                Job(
                    title=title,
                    url=str(row["url"]),
                    source=JobSource.TELEGRAM,
                    city=str(row["city"]) if row["city"] else location,
                    salary_min=job_salary_min,
                    salary_max=job_salary_max,
                    currency=currency,
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
        return {"source": self.name, "available": bool(self._channels), "channels_configured": len(self._channels), "mode": "telegram_bot_api_ingestion"}

    @staticmethod
    def _normalize_channel(value: str) -> str:
        return value.strip().removeprefix("@").removeprefix("https://t.me/").strip("/")

    @classmethod
    def _is_job_post(cls, title: str, text: str) -> bool:
        normalized = text.casefold().strip()
        if len(normalized) < 20 or any(marker in normalized for marker in cls._NON_JOB_MARKERS):
            return False
        if any(marker in normalized for marker in cls._USER_REQUEST_MARKERS):
            return False
        return any(marker in normalized for marker in cls._JOB_MARKERS)

    @staticmethod
    def _matches(text: str, terms: list[str]) -> bool:
        if not terms:
            return True
        normalized = text.casefold()
        return all(term in normalized for term in terms)

    @staticmethod
    def _extract_salary_constraint(text: str) -> tuple[Decimal | None, Decimal | None]:
        values, minimum_marked = TelegramJobSource._salary_values(text)
        if not values:
            return None, None
        if len(values) >= 2 and any(marker in text.casefold() for marker in ("-", "до", "–")):
            return min(values), max(values)
        if minimum_marked:
            return min(values), None
        return min(values), None

    @staticmethod
    def _extract_salary(text: str) -> tuple[Decimal | None, Decimal | None, str | None]:
        values, _ = TelegramJobSource._salary_values(text)
        if not values:
            return None, None, None
        if len(values) >= 2 and any(marker in text.casefold() for marker in ("-", "до", "–")):
            return min(values), max(values), "UAH"
        return min(values), None, "UAH"

    @staticmethod
    def _salary_values(text: str) -> tuple[list[Decimal], bool]:
        values: list[Decimal] = []
        minimum_marked = False
        pattern = r"(?P<prefix>от|від|минимум|не менее|не менше)?\s*(?P<value>\d[\d\s.,]*)(?:\s*(?P<unit>к|k|тыс|тис|тысяч|тисяч|грн|uah|usd|\$|€))?"
        for match in re.finditer(pattern, text.casefold()):
            raw = match.group("value").strip()
            cleaned = raw.replace(" ", "").replace(",", ".")
            try:
                value = Decimal(cleaned)
            except InvalidOperation:
                continue
            unit = match.group("unit") or ""
            if value < 1000 and unit in {"к", "k", "тыс", "тис", "тысяч", "тисяч"}:
                value *= 1000
            if Decimal("1000") <= value <= Decimal("10000000"):
                values.append(value)
                if match.group("prefix"):
                    minimum_marked = True
        return values, minimum_marked

    @staticmethod
    def _extract_employment_type(text: str) -> EmploymentType:
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
        return True if re.search(r"remote|віддал|удален|дистанцион", text.casefold()) else None

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
