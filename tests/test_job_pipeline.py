from decimal import Decimal
import unittest

from app.domain.jobs import Job, JobSource
from app.profile import CandidateProfile
from app.tools.job_aggregator import JobAggregator
from app.tools.job_pipeline import JobPipeline
from app.tools.job_ranker import JobRanker


class JobPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = JobPipeline(JobAggregator(), JobRanker())

    def test_same_url_is_deduplicated(self) -> None:
        first = Job(title="Python Developer", url="https://example.com/job/1", source=JobSource.ROBOTA_UA)
        second = Job(title="Python Developer", url="https://example.com/job/1", source=JobSource.OLX)

        result = self.pipeline.run([[first], [second]], CandidateProfile())

        self.assertEqual(len(result), 1)

    def test_company_title_duplicate_prefers_richer_job(self) -> None:
        first = Job(
            title="Python Developer",
            url="https://example.com/a",
            source=JobSource.ROBOTA_UA,
            company="Acme",
        )
        second = Job(
            title="Python Developer",
            url="https://example.com/b",
            source=JobSource.OLX,
            company="Acme",
            city="Київ",
            salary_min=Decimal("60000"),
            salary_max=Decimal("80000"),
            currency="UAH",
        )

        result = self.pipeline.run([[first], [second]], CandidateProfile())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].job.url, second.url)

    def test_matching_skill_and_salary_increase_score(self) -> None:
        job = Job(
            title="Python FastAPI Developer",
            url="https://example.com/job/3",
            source=JobSource.ROBOTA_UA,
            city="Київ",
            salary_min=Decimal("70000"),
            salary_max=Decimal("90000"),
            currency="UAH",
        )
        profile = CandidateProfile(skills=("python", "fastapi"), city="київ", salary_min=60000)

        result = self.pipeline.run([[job]], profile)

        self.assertEqual(result[0].score, 95)
        self.assertTrue(result[0].reasons)


if __name__ == "__main__":
    unittest.main()
