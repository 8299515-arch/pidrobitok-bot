from decimal import Decimal
import unittest

from app.domain.jobs import Job, JobSource
from app.profile import CandidateProfile
from app.tools.job_ranker import JobRanker


class ProfileAndRankerTests(unittest.TestCase):
    def test_profile_salary_and_remote_extraction(self) -> None:
        profile = CandidateProfileStoreFake().build("Python FastAPI, Киев, от 60000 грн, удалёнка")
        self.assertIn("python", profile.skills)
        self.assertIn("fastapi", profile.skills)
        self.assertEqual(profile.city, "Киев")
        self.assertEqual(profile.salary_min, 60000)
        self.assertTrue(profile.remote)

    def test_ranker_places_compatible_job_first(self) -> None:
        profile = CandidateProfile(skills=("python",), city="Киев", salary_min=60000, remote=False)
        good = Job(
            title="Python Developer",
            url="https://example.com/good",
            source=JobSource.ROBOTA_UA,
            city="Киев",
            salary_min=60000,
            salary_max=80000,
            currency="UAH",
            description="Python FastAPI",
        )
        bad = Job(
            title="Python Developer",
            url="https://example.com/bad",
            source=JobSource.ROBOTA_UA,
            city="Львов",
            salary_min=30000,
            salary_max=40000,
            currency="UAH",
        )

        ranked = JobRanker().rank([bad, good], profile)

        self.assertEqual(ranked[0].job.url, good.url)
        self.assertGreater(ranked[0].score, ranked[1].score)


class CandidateProfileStoreFake:
    def build(self, text: str) -> CandidateProfile:
        import re

        normalized = text.casefold()
        skills = tuple(skill for skill in ("python", "fastapi") if skill in normalized)
        city = "Киев" if "киев" in normalized else None
        match = re.search(r"от\s*(\d[\d\s]*)", normalized)
        salary = int(match.group(1).replace(" ", "")) if match else None
        return CandidateProfile(skills=skills, city=city, salary_min=salary, remote="удал" in normalized)


if __name__ == "__main__":
    unittest.main()
