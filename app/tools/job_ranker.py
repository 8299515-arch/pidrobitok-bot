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


class JobRanker:
    """Deterministic ranking based on explicit search constraints and profile context."""

    def rank(self, jobs: list[Job], profile: CandidateProfile, query: JobQuery | None = None) -> list[RankedJob]:
        ranked = [self._score(job, profile, query) for job in jobs]
        return sorted(ranked, key=lambda item: (-item.score, item.job.title.casefold()))

    def _score(self, job: Job, profile: CandidateProfile, query: JobQuery | None) -> RankedJob:
        reasons: list[str] = []
        haystack = " ".join(part for part in (job.title, job.company, job.city, job.description) if part).casefold()

        requested_skills = tuple(query.skills) if query and query.skills else ()
        requested_city = query.city if query else None
        requested_remote = query.remote is True if query else False
        requested_salary = query.salary_min if query else None
        requested_employment = query.employment if query else None

        criteria = 0
        matched = 0
        score = 0

        if requested_skills:
            criteria += 1
            matches = [skill for skill in requested_skills if skill.casefold() in haystack]
            if matches:
                matched += 1
                score += 50
                reasons.append(f"Совпадают навыки: {', '.join(matches[:5])}")

        if requested_city:
            criteria += 1
            if job.city and requested_city.casefold() in job.city.casefold():
                matched += 1
                score += 25
                reasons.append("Совпадает город")

        if requested_remote:
            criteria += 1
            if job.remote is True:
                matched += 1
                score += 15
                reasons.append("Подходит удалённая работа")

        if requested_salary is not None:
            criteria += 1
            if self._salary_matches(job, requested_salary):
                matched += 1
                score += 10
                reasons.append("Зарплата соответствует минимуму")

        if requested_employment:
            criteria += 1
            if job.employment == requested_employment:
                matched += 1
                score += 10
                reasons.append("Подходит тип занятости")

        if criteria == 0:
            profile_skills = profile.skills
            profile_city = profile.city
            profile_remote = profile.remote
            profile_salary = profile.salary_min

            if profile_skills:
                matches = [skill for skill in profile_skills if skill.casefold() in haystack]
                if matches:
                    score += min(60, len(matches) * 20)
                    reasons.append(f"Профиль: навыки {', '.join(matches[:5])}")
            if profile_city and job.city and profile_city.casefold() in job.city.casefold():
                score += 20
                reasons.append("Город совпадает с профилем")
            if profile_remote and job.remote is True:
                score += 10
                reasons.append("Подходит удалённая работа")
            if profile_salary is not None and self._salary_matches(job, profile_salary):
                score += 10
                reasons.append("Зарплата соответствует профилю")
        else:
            # Normalize explicit-constraint scores so 20% does not appear simply
            # because one city criterion was present. A fully matched query is 100%.
            score = round((matched / criteria) * 100)

        if not reasons:
            reasons.append("Подходит по заданным условиям")

        return RankedJob(job=job, score=min(score, 100), reasons=tuple(reasons))

    @staticmethod
    def _salary_matches(job: Job, minimum: Decimal) -> bool:
        return job.salary_max is not None and job.salary_max >= minimum
