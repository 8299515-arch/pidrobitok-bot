from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from app.domain.jobs import EmploymentType, Job, JobSource
from app.storage import SQLiteStorage


class TelegramJobSource:
    """Searches normalized Telegram job posts captured by the bot."""

    _JOB_MARKERS = (
        "ваканс", "вакансі", "требуется", "требуємо", "потрібен", "потрібна",
        "потрібні", "ищем", "шукаємо", "зарплат", "оплата", "ставка", "грн",
        "uah", "обязанност", "обов'язк", "обов’язк", "требован", "вимог",
        "график", "графік", "занятост", "зайнятіст", "подработ", "підробіт",
        "резюме", "відгук", "отклик",
    )
    _NON_JOB_MARKERS = (
        "тест", "test", "актуальные вакансии ежедневно", "актуальні вакансії щодня",
        "оставить свое объявление", "залишити своє оголошення", "подписывайтесь",
        "підписуйтесь", "этот канал", "цей канал", "все вакансии", "усі вакансії",
    )
    _USER_REQUEST_MARKERS = (
        "найди", "найти", "ищи", "поищи", "покажи", "подбери", "найти актуаль",
        "найди актуаль", "пошукай", "шукаю", "ищу",
    )
    _SALARY_RANGE_RE = re.compile(
        r"(?P<left>\d[\d\s.,]*)\s*[-–—]\s*(?P<right>\d[\d\s.,]*)\s*(?P<unit>к|k|тыс|тис|тысяч|тисяч|грн|uah|usd|\$|€)?",
        re.IGNORECASE,
    )
    _SALARY_VALUE_RE = re.compile(
        r"(?P<prefix>от|від|минимум|не менее|не менше)?\s*"
        r"(?P<value>\d[\d\s.,]*)\s*"
        r"(?P<unit>к|k|тыс|тис|тысяч|тисяч|грн|uah|usd|\$|€)?",
        re.IGNORECASE,
    )

    def __init__(self, channels: Sequence[str], database_path: str) -> None:
        self._channels = tuple(self._normalize_channel(channel) for channel in channels if channel.strip())
        self._database_path = database_path

    @property
    def name(self) -> str:
        return JobSource.TELEGRAM.value

    @property
    def configured(self) -> bool:
        return bool(self._channels)

    async def search(self, query: str, *, location: str | None = None, limit: int = 10) -> list[Job]:
        if limit <= 0:
            return []

        storage = SQLiteStorage(self._database_path)
        try:
            channels = storage.list_active_telegram_channels() if storage.has_telegram_channels() else self._channels
            if not channels:
                return []
            # Fetch candidates first. Query constraints are applied after the post
            # has been normalized so salary/city/skill filters see structured data.
            rows = storage.list_telegram_jobs(channels, limit=max(limit * 20, 100))
        finally:
            storage.close()

        jobs: list[Job] = []
        for row in rows:
            text = str(row["description"])
            title = str(row["title"])
            if not self._is_job_post(title, text):
                continue

            job_salary_min, job_salary_max, currency = self._extract_salary(text)
            published_at = self._parse_datetime(str(row["published_at"]))
            city = str(row["city"]) if row["city"] else self._extract_city(text) or location
            jobs.append(
                Job(
                    title=title,
                    url=str(row["url"]),
                    source=JobSource.TELEGRAM,
                    city=city,
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
        storage = SQLiteStorage(self._database_path)
        try:
            channels = storage.list_active_telegram_channels() if storage.has_telegram_channels() else self._channels
        finally:
            storage.close()
        return {
            "source": self.name,
            "available": bool(channels),
            "channels_configured": len(channels),
            "mode": "telegram_bot_api_ingestion",
        }

    @staticmethod
    def _normalize_channel(value: str) -> str:
        return value.strip().removeprefix("@").removeprefix("https://t.me/").strip("/")

    @classmethod
    def _is_job_post(cls, title: str, text: str) -> bool:
        normalized = f"{title}\n{text}".casefold().strip()
        if len(normalized) < 20:
            return False
        if any(marker in normalized for marker in cls._NON_JOB_MARKERS):
            return False
        if any(marker in normalized for marker in cls._USER_REQUEST_MARKERS):
            return False
        return any(marker in normalized for marker in cls._JOB_MARKERS)

    @classmethod
    def _extract_salary(cls, text: str) -> tuple[Decimal | None, Decimal | None, str | None]:
        currency: str | None = None

        range_match = cls._SALARY_RANGE_RE.search(text.casefold())
        if range_match:
            left = cls._salary_value(range_match.group("left"), range_match.group("unit"))
            right = cls._salary_value(range_match.group("right"), range_match.group("unit"))
            if left is not None and right is not None:
                currency = cls._currency(range_match.group("unit"), text)
                return min(left, right), max(left, right), currency

        values: list[Decimal] = []
        for match in cls._SALARY_VALUE_RE.finditer(text.casefold()):
            value = cls._salary_value(match.group("value"), match.group("unit"))
            if value is None:
                continue
            values.append(value)
            currency = cls._currency(match.group("unit"), text) or currency

        if not values:
            return None, None, None
        return min(values), None, currency or "UAH"

    @staticmethod
    def _salary_value(raw: str, unit: str | None) -> Decimal | None:
        normalized = raw.strip().replace(" ", "").replace(",", ".")
        try:
            value = Decimal(normalized)
        except InvalidOperation:
            return None
        normalized_unit = (unit or "").casefold()
        if value < 1000 and normalized_unit in {"к", "k", "тыс", "тис", "тысяч", "тисяч"}:
            value *= 1000
        if not Decimal("1000") <= value <= Decimal("10000000"):
            return None
        return value

    @staticmethod
    def _currency(unit: str | None, text: str) -> str | None:
        normalized_unit = (unit or "").casefold()
        if normalized_unit in {"грн", "uah"} or "грн" in text.casefold():
            return "UAH"
        if normalized_unit in {"usd", "$"}:
            return "USD"
        if normalized_unit == "€":
            return "EUR"
        return None

    @staticmethod
    def _extract_city(text: str) -> str | None:
        normalized = text.casefold()
        for city in (
            "киев", "київ", "kyiv", "кривой рог", "львов", "львів", "одесса",
            "одеса", "днепр", "дніпро", "харьков", "харків",
        ):
            if city in normalized:
                return city.title()
        return None

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
