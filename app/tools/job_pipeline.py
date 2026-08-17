from __future__ import annotations

from collections.abc import Sequence

from app.domain.jobs import Job
from app.profile import CandidateProfile
from app.tools.job_aggregator import JobAggregator
from app.tools.job_ranker import JobRanker, RankedJob


class JobPipeline:
    """Runs the common aggregation and candidate-ranking flow."""

    def __init__(self, aggregator: JobAggregator, ranker: JobRanker) -> None:
        self._aggregator = aggregator
        self._ranker = ranker

    def run(
        self,
        source_results: Sequence[Sequence[Job]],
        profile: CandidateProfile,
        limit: int = 10,
    ) -> list[RankedJob]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        jobs = self._aggregator.aggregate(source_results)
        return self._ranker.rank(jobs, profile)[:limit]
