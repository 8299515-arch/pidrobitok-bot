from __future__ import annotations

from collections.abc import Sequence

from app.domain.jobs import Job
from app.profile import CandidateProfile
from app.query_parser import JobQuery
from app.tools.job_aggregator import JobAggregator
from app.tools.job_ranker import JobRanker, RankedJob


class JobPipeline:
    """Runs normalization, hard filtering and candidate ranking."""

    _CITY_ALIASES = {
        "киев": "kyiv",
        "київ": "kyiv",
        "kiev": "kyiv",
        "kyiv": "kyiv",
        "львов": "lviv",
        "львів": "lviv",
        "lviv": "lviv",
        "одесса": "odesa",
        "одеса": "odesa",
        "odesa": "odesa",
        "днепр": "dnipro",
        "дніпро": "dnipro",
        "dnipro": "dnipro",
        "харьков": "kharkiv",
        "харків": "kharkiv",
        "kharkiv": "kharkiv",
    }

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

    @classmethod
    def _filter(
        cls,
        jobs: list[Job],
        profile: CandidateProfile,
        query: JobQuery | None,
    ) -> list[Job]:
        result: list[Job] = []
        requested_city = (query.city if query is not None else None) or profile.city
        requested_min = (query.salary_min if query is not None else None) or profile.salary_min
        requested_remote = (query.remote is True if query is not None else False) or profile.remote
        requested_skills = set(query.skills) if query is not None else set()

        for job in jobs:
            if requested_city:
                if not job.city or not cls._city_matches(requested_city, job.city):
                    if job.remote is not True:
                        continue

            if requested_remote and job.remote is not True:
                continue

            if requested_min is not None:
                advertised_upper = job.salary_max if job.salary_max is not None else job.salary_min
                if advertised_upper is None or advertised_upper < requested_min:
                    continue

            if query is not None and query.salary_max is not None:
                if job.salary_min is None or job.salary_min > query.salary_max:
                    continue

            if query is not None and query.employment and job.employment_type.value != query.employment:
                continue

            if requested_skills:
                haystack = " ".join(
                    part for part in (job.title, job.description) if part
                ).casefold()
                if not all(skill.casefold() in haystack for skill in requested_skills):
                    continue

            result.append(job)

        return result

    @classmethod
    def _city_matches(cls, requested: str, actual: str) -> bool:
        requested_key = cls._CITY_ALIASES.get(requested.casefold(), requested.casefold())
        actual_key = cls._CITY_ALIASES.get(actual.casefold(), actual.casefold())
        return requested_key == actual_key
