from __future__ import annotations

from collections.abc import Iterable

from app.domain.jobs import Job


class JobAggregator:
    """Combines source results and removes exact and cross-source duplicates."""

    def aggregate(self, results: Iterable[Iterable[Job]]) -> list[Job]:
        jobs: list[Job] = []
        aliases: dict[str, int] = {}

        for source_jobs in results:
            for job in source_jobs:
                keys = (f"url:{job.canonical_url}", f"fingerprint:{job.fingerprint}")
                existing_index = next((aliases[key] for key in keys if key in aliases), None)
                if existing_index is None:
                    aliases[keys[0]] = len(jobs)
                    aliases[keys[1]] = len(jobs)
                    jobs.append(job)
                    continue

                current = jobs[existing_index]
                preferred = self._prefer_richer_job(current, job)
                jobs[existing_index] = preferred

                for alias, index in list(aliases.items()):
                    if index == existing_index:
                        aliases[alias] = existing_index
                aliases[keys[0]] = existing_index
                aliases[keys[1]] = existing_index

        return jobs

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
