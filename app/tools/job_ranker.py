from __future__ import annotations

from dataclasses import dataclass

from app.domain.jobs import Job
from app.memory.profile import CandidateProfile


@dataclass(frozen=True, slots=True)
class RankedJob:
    job: Job
    score: int
    reasons: tuple[str, ...]


class JobRanker:
    """Deterministic first-pass ranking; AI can enrich explanations later."""

    def rank(self, jobs: list[Job], profile: CandidateProfile) -> list[RankedJob]:
        ranked = [self._score(job, profile) for job in jobs]
        return sorted(ranked, key=lambda item: (-item.score, item.job.title.lower()))

    def _score(self, job: Job, profile: CandidateProfile) -> RankedJob:
        score = 0
        reasons: list[str] = []
        haystack = " ".join(
            part for part in (job.title, job.company, job.city, job.description) if part
        ).lower()

        skills = [skill.strip().lower() for skill in profile.skills if skill.strip()]
        matches = [skill for skill in skills if skill in haystack]
        if matches:
            score += min(50, len(matches) * 10)
            reasons.append(f"Совпадают навыки: {', '.join(matches[:5])}")

        if profile.city and job.city and profile.city.lower() in job.city.lower():
            score += 20
            reasons.append("Совпадает город")

        if profile.remote and job.remote is True:
            score += 20
            reasons.append("Подходит удалённая работа")

        if profile.salary_min is not None and job.salary_max is not None:
            try:
                if float(job.salary_max) >= float(profile.salary_min):
                    score += 10
                    reasons.append("Зарплата соответствует минимуму")
            except (TypeError, ValueError):
                pass

        return RankedJob(job=job, score=min(score, 100), reasons=tuple(reasons))
