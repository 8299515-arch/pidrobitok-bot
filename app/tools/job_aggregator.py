from __future__ import annotations

from collections.abc import Iterable

from app.domain.jobs import Job


class JobAggregator:
    """Combines source results and removes exact and cross-source duplicates."""

    def aggregate(self, results: Iterable[Iterable[Job]]) -> list[Job]:
        unique: dict[str, Job] = {}
        for source_jobs in results:
            for job in source_jobs:
                keys = (f"url:{job.canonical_url}", f"fingerprint:{job.fingerprint}")
                existing_key = next((key for key in keys if key in unique), None)
                if existing_key is None:
                    unique[keys[0]] = job
                    unique[keys[1]] = job
                    continue

                current = unique[existing_key]
                preferred = self._prefer_richer_job(current, job)
                for key in keys:
                    unique[key] = preferred

        return self._unique_values(unique)

    @staticmethod
    def _unique_values(values: dict[str, Job]) -> list[Job]:
        result: list[Job] = []
        seen: set[int] = set()
        for job in values.values():
            marker = id(job)
            if marker in seen:
                continue
            seen.add(marker)
            result.append(job)
        return result

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
