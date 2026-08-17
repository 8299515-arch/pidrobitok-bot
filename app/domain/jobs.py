from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final
from urllib.parse import urlparse


class JobSource(StrEnum):
    ROBOTA_UA = "robota.ua"
    TELEGRAM = "telegram"
    OLX = "olx"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Job:
    title: str
    url: str
    source: JobSource
    company: str | None = None
    city: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    currency: str | None = None
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    remote: bool | None = None
    description: str | None = None
    published_at: datetime | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Job URL must be an absolute HTTP(S) URL")
        if not self.title.strip():
            raise ValueError("Job title must not be empty")

    @property
    def canonical_url(self) -> str:
        parsed = urlparse(self.url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"

    @property
    def deduplication_key(self) -> str:
        if self.source_id:
            return f"{self.source.value}:{self.source_id.strip().lower()}"
        return self.canonical_url


UNKNOWN_TEXT: Final[str] = "Не указано"
