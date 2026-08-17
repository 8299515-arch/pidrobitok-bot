from __future__ import annotations

from dataclasses import dataclass

from app.domain.jobs import Job
from app.profile import CandidateProfile
from app.query_parser import JobQuery


@dataclass(frozen=True, slots=True)
class RankedJob:
    job: Job
    score: int
    reasons: tuple[str, ...]


class JobRanker:
    """Deterministic ranking; hard constraints are handled by the pipeline."""

    def rank(self, jobs: list[Job], profile: CandidateProfile, query: JobQuery | None = None) -> list[RankedJob]:
        ranked = [self._score(job, profile, query) for job in jobs]
        return sorted(ranked, key=lambda item: (-item.score, item.job.title.casefold()))

    def _score(self, job: Job, profile: CandidateProfile, query: JobQuery | None) -> RankedJob:
        score = 0
        reasons: list[str] = []
        haystack = " ".join(part for part in (job.title, job.company, job.city, job.description) if part).casefold()
        skills = tuple(query.skills) if query and query.skills else profile.skills
        matches = [skill for skill in skills if skill.casefold() in haystack]
        if matches:
            score += min(50, len(matches) * 10)
            reasons.append(f"Совпадают навыки: {', '.join(matches[:5])}")

        requested_city = query.city if query else profile.city
        if requested_city and job.city and requested_city.casefold() in job.city.casefold():
            score += 20
            reasons.append("Совпадает город")

        requested_remote = query.remote is True if query else profile.remote
        if requested_remote and job.remote is True:
            score += 20
            reasons.append("Подходит удалённая работа")

        requested_salary = query.salary_min if query and query.salary_min is not None else profile.salary_min
        if requested_salary is not None and job.salary_max is not None and job.salary_max >= requested_salary:
            score += 10
            reasons.append("Зарплата соответствует минимуму")

        return RankedJob(job=job, score=min(score, 100), reasons=tuple(reasons))
