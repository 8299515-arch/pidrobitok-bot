from decimal import Decimal

from app.domain.jobs import Job, JobSource
from app.profile import CandidateProfile
from app.tools.job_ranker import JobRanker


def test_profile_salary_and_remote_extraction():
    profile = CandidateProfileStoreFake().build("Python FastAPI, Киев, от 60000 грн, удалёнка")
    assert "python" in profile.skills
    assert "fastapi" in profile.skills
    assert profile.city == "Киев"
    assert profile.salary_min == 60000
    assert profile.remote is True


def test_ranker_filters_incompatible_city_and_salary():
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
    assert [item.job.url for item in ranked] == [good.url]
    assert ranked[0].score > 0


class CandidateProfileStoreFake:
    def build(self, text: str) -> CandidateProfile:
        import re
        normalized = text.casefold()
        skills = tuple(skill for skill in ("python", "fastapi") if skill in normalized)
        city = "Киев" if "киев" in normalized else None
        match = re.search(r"от\s*(\d[\d\s]*)", normalized)
        salary = int(match.group(1).replace(" ", "")) if match else None
        return CandidateProfile(skills=skills, city=city, salary_min=salary, remote="удал" in normalized)
