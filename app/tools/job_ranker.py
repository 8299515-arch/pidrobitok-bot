from __future__ import annotations

from dataclasses import dataclass

from app.domain.jobs import Job
from app.profile import CandidateProfile


@dataclass(frozen=True, slots=True)
class RankedJob:
    job: Job
    score: int
    reasons: tuple[str, ...]


class JobRanker:
    """Deterministic ranking with hard eligibility filters before scoring."""

    def rank(self, jobs: list[Job], profile: CandidateProfile) -> list[RankedJob]:
        ranked = []
        for job in jobs:
            if not self._eligible(job, profile):
                continue
            ranked.append(self._score(job, profile))
        return sorted(ranked, key=lambda item: (-item.score, item.job.title.casefold()))

    @staticmethod
    def _eligible(job: Job, profile: CandidateProfile) -> bool:
        if profile.city and job.city and profile.city.casefold() not in job.city.casefold():
            if profile.remote and job.remote is True:
                return True
            return False
        if profile.salary_min is not None and job.salary_max is not None:
            if job.salary_max < profile.salary_min:
                return False
        if profile.remote and job.remote is False:
            return False
        return True

    def _score(self, job: Job, profile: CandidateProfile) -> RankedJob:
        score = 0
        reasons: list[str] = []
        haystack = " ".join(
            part for part in (job.title, job.company, job.city, job.description) if part
        ).casefold()

        skills = [skill.strip().casefold() for skill in profile.skills if skill.strip()]
        matches = [skill for skill in skills if skill in haystack]
        if matches:
            score += min(55, len(matches) * 11)
            reasons.append(f"Совпадают навыки: {', '.join(matches[:5])}")
        elif skills:
            reasons.append("Совпадение навыков не найдено")

        if profile.city and job.city and profile.city.casefold() in job.city.casefold():
            score += 20
            reasons.append("Совпадает город")

        if profile.remote and job.remote is True:
            score += 15
            reasons.append("Подходит удалённая работа")

        if profile.salary_min is not None and job.salary_max is not None:
            if job.salary_max >= profile.salary_min:
                score += 10
                reasons.append("Зарплата соответствует минимуму")

        return RankedJob(job=job, score=min(score, 100), reasons=tuple(reasons))
