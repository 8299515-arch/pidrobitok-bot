from __future__ import annotations

from collections.abc import Iterable

from app.domain.jobs import Job


class JobAggregator:
    """Combines source results and removes duplicates without losing source priority."""

    def aggregate(self, results: Iterable[Iterable[Job]]) -> list[Job]:
        unique: dict[str, Job] = {}
        for source_jobs in results:
            for job in source_jobs:
                key = job.deduplication_key
                if key not in unique:
                    unique[key] = job
                    continue
                unique[key] = self._prefer_richer_job(unique[key], job)
        return list(unique.values())

    @staticmethod
    def _prefer_richer_job(first: Job, second: Job) -> Job:
        first_score = JobAggregator._completeness(first)
        second_score = JobAggregator._completeness(second)
        return second if second_score > first_score else first

    @staticmethod
    def _completeness(job: Job) -> int:
        fields = (
            job.company,
            job.city,
            job.salary_min,
            job.salary_max,
            job.currency,
            job.description,
            job.published_at,
        )
        return sum(value is not None and value != "" for value in fields)
