from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Iterable

from app.domain.jobs import Job


@dataclass(frozen=True, slots=True)
class ProcessedJob:
    job: Job
    quality_score: int
    is_valid: bool
    rejection_reason: str | None = None


class JobValidator:
    _SCAM_MARKERS = (
        "оплата за регистрацию", "платная регистрация", "внесите предоплату",
        "вступительный взнос", "купите обучение", "переведите деньги",
    )

    def validate(self, job: Job) -> tuple[bool, str | None]:
        text = f"{job.title}\n{job.description or ''}".casefold()
        if not job.title.strip() or not job.url:
            return False, "missing_required_fields"
        if any(marker in text for marker in self._SCAM_MARKERS):
            return False, "suspicious_payment_request"
        return True, None


class JobDeduplicator:
    def filter(self, jobs: Iterable[Job]) -> list[Job]:
        result: list[Job] = []
        seen: set[str] = set()
        semantic: set[str] = set()
        for job in jobs:
            key = job.deduplication_key
            if key in seen:
                continue
            seen.add(key)
            fingerprint = self._semantic_key(job)
            if fingerprint in semantic:
                continue
            semantic.add(fingerprint)
            result.append(job)
        return result

    @staticmethod
    def _semantic_key(job: Job) -> str:
        title = re.sub(r"\s+", " ", job.title.casefold()).strip()
        company = re.sub(r"\s+", " ", (job.company or "").casefold()).strip()
        city = re.sub(r"\s+", " ", (job.city or "").casefold()).strip()
        return "|".join((title, company, city))


class JobQualityScorer:
    def score(self, job: Job) -> int:
        score = 0
        if job.title.strip():
            score += 25
        if job.description and len(job.description.strip()) >= 80:
            score += 20
        elif job.description:
            score += 10
        if job.company:
            score += 15
        if job.city:
            score += 10
        if job.salary_min is not None:
            score += 15
        if job.published_at is not None:
            age = datetime.now(timezone.utc) - self._aware(job.published_at)
            if age.total_seconds() <= 72 * 3600:
                score += 15
            elif age.total_seconds() <= 7 * 24 * 3600:
                score += 8
        return min(score, 100)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class JobProcessingPipeline:
    def __init__(self) -> None:
        self._validator = JobValidator()
        self._deduplicator = JobDeduplicator()
        self._scorer = JobQualityScorer()

    def process(self, jobs: Iterable[Job], *, minimum_quality: int = 50) -> list[ProcessedJob]:
        unique = self._deduplicator.filter(jobs)
        processed: list[ProcessedJob] = []
        for job in unique:
            valid, reason = self._validator.validate(job)
            score = self._scorer.score(job)
            if not valid or score < minimum_quality:
                processed.append(ProcessedJob(job, score, False, reason or "quality_below_threshold"))
                continue
            processed.append(ProcessedJob(job, score, True))
        return processed
