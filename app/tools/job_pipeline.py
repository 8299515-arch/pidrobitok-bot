from __future__ import annotations

from collections.abc import Sequence

from app.domain.jobs import Job
from app.profile import CandidateProfile
from app.query_parser import JobQuery
from app.tools.job_aggregator import JobAggregator
from app.tools.job_ranker import JobRanker, RankedJob


class JobPipeline:
    """Runs normalization, hard filtering and candidate ranking."""

    def __init__(self, aggregator: JobAggregator, ranker: JobRanker) -> None:
        self._aggregator = aggregator
        self._ranker = ranker

    def run(
        self,
        source_results: Sequence[Sequence[Job]],
        profile: CandidateProfile,
        query: JobQuery | None = None,
        limit: int = 10,
    ) -> list[RankedJob]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        jobs = self._aggregator.aggregate(source_results)
        filtered = self._filter(jobs, profile, query)
        return self._ranker.rank(filtered, profile, query=query)[:limit]

    @staticmethod
    def _filter(jobs: list[Job], profile: CandidateProfile, query: JobQuery | None) -> list[Job]:
        if query is None:
            return jobs
        result: list[Job] = []
        requested_city = query.city or profile.city
        requested_min = query.salary_min or profile.salary_min
        requested_remote = query.remote is True or profile.remote
        requested_skills = set(query.skills)
        for job in jobs:
            if requested_city:
                if not job.city or (requested_city.casefold() not in job.city.casefold() and job.remote is not True):
                    continue
            if requested_remote and job.remote is not True:
                continue
            if requested_min is not None:
                # A salary floor is a hard requirement. For a single advertised
                # salary use salary_min; for a range use salary_max to determine
                # whether the range can satisfy the requested floor.
                advertised_upper = job.salary_max if job.salary_max is not None else job.salary_min
                if advertised_upper is None or advertised_upper < requested_min:
                    continue
            if query.salary_max is not None:
                if job.salary_min is None or job.salary_min > query.salary_max:
                    continue
            if query.employment and job.employment_type.value != query.employment:
                continue
            if requested_skills:
                haystack = " ".join(part for part in (job.title, job.description) if part).casefold()
                if not all(skill.casefold() in haystack for skill in requested_skills):
                    continue
            result.append(job)
        return result
