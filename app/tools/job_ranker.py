from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.jobs import Job
from app.profile import CandidateProfile
from app.query_parser import JobQuery


@dataclass(frozen=True, slots=True)
class RankedJob:
    job: Job
    score: int
    reasons: tuple[str, ...]
    query_score: int
    candidate_score: int | None


class JobRanker:
    """Deterministic ranking with separate query and candidate compatibility scores."""

    def rank(self, jobs: list[Job], profile: CandidateProfile, query: JobQuery | None = None) -> list[RankedJob]:
        ranked = [self._score(job, profile, query) for job in jobs]
        return sorted(ranked, key=lambda item: (-item.score, item.job.title.casefold()))

    def _score(self, job: Job, profile: CandidateProfile, query: JobQuery | None) -> RankedJob:
        query_score, query_reasons = self._query_score(job, query)
        candidate_score = self._candidate_score(job, profile)

        if query is not None and self._has_explicit_constraints(query):
            score = query_score
        elif candidate_score is not None:
            score = candidate_score
        else:
            score = query_score

        reasons = list(query_reasons)
        if candidate_score is not None:
            profile_reasons = self._candidate_reasons(job, profile)
            reasons.extend(profile_reasons)

        if not reasons:
            reasons.append("Подходит по заданным условиям")

        return RankedJob(
            job=job,
            score=min(score, 100),
            reasons=tuple(reasons),
            query_score=query_score,
            candidate_score=candidate_score,
        )

    @staticmethod
    def _has_explicit_constraints(query: JobQuery) -> bool:
        return bool(
            query.skills
            or query.city
            or query.remote is True
            or query.salary_min is not None
            or query.salary_max is not None
            or query.employment
        )

    def _query_score(self, job: Job, query: JobQuery | None) -> tuple[int, list[str]]:
        if query is None:
            return 0, []

        haystack = " ".join(part for part in (job.title, job.company, job.city, job.description) if part).casefold()
        criteria = 0
        matched = 0
        reasons: list[str] = []

        if query.skills:
            criteria += 1
            matches = [skill for skill in query.skills if skill.casefold() in haystack]
            if matches:
                matched += 1
                reasons.append(f"Совпадают навыки: {', '.join(matches[:5])}")

        if query.city:
            criteria += 1
            if job.city and query.city.casefold() in job.city.casefold():
                matched += 1
                reasons.append("Совпадает город")

        if query.remote is True:
            criteria += 1
            if job.remote is True:
                matched += 1
                reasons.append("Подходит удалённая работа")

        if query.salary_min is not None:
            criteria += 1
            if self._salary_matches(job, query.salary_min):
                matched += 1
                reasons.append("Зарплата соответствует минимуму")

        if query.salary_max is not None:
            criteria += 1
            if job.salary_min is None or job.salary_min <= query.salary_max:
                matched += 1
                reasons.append("Зарплата входит в диапазон")

        if query.employment:
            criteria += 1
            if job.employment_type.value == query.employment:
                matched += 1
                reasons.append("Подходит тип занятости")

        if criteria == 0:
            return 0, reasons
        return round((matched / criteria) * 100), reasons

    def _candidate_score(self, job: Job, profile: CandidateProfile) -> int | None:
        criteria = 0
        matched = 0
        haystack = " ".join(part for part in (job.title, job.company, job.city, job.description) if part).casefold()

        if profile.skills:
            criteria += 1
            if any(skill.casefold() in haystack for skill in profile.skills):
                matched += 1

        if profile.city:
            criteria += 1
            if job.city and profile.city.casefold() in job.city.casefold():
                matched += 1

        if profile.remote:
            criteria += 1
            if job.remote is True:
                matched += 1

        if profile.salary_min is not None:
            criteria += 1
            if self._salary_matches(job, profile.salary_min):
                matched += 1

        return round((matched / criteria) * 100) if criteria else None

    @staticmethod
    def _candidate_reasons(job: Job, profile: CandidateProfile) -> list[str]:
        haystack = " ".join(part for part in (job.title, job.company, job.city, job.description) if part).casefold()
        reasons: list[str] = []
        matches = [skill for skill in profile.skills if skill.casefold() in haystack]
        if matches:
            reasons.append(f"Профиль: навыки {', '.join(matches[:5])}")
        if profile.city and job.city and profile.city.casefold() in job.city.casefold():
            reasons.append("Город совпадает с профилем")
        if profile.remote and job.remote is True:
            reasons.append("Подходит удалённая работа по профилю")
        if profile.salary_min is not None and JobRanker._salary_matches(job, profile.salary_min):
            reasons.append("Зарплата соответствует профилю")
        return reasons

    @staticmethod
    def _salary_matches(job: Job, minimum: Decimal) -> bool:
        return job.salary_max is not None and job.salary_max >= minimum
