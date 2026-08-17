from decimal import Decimal

from app.query_parser import JobQueryParser


def test_parse_natural_language_job_request() -> None:
    query = JobQueryParser().parse(
        "Ищу Python/FastAPI в Киеве или удалённо, от 60к, full-time"
    )

    assert query.skills == ("python", "fastapi")
    assert query.city == "Киев"
    assert query.remote is True
    assert query.salary_min == Decimal("60000")
    assert query.employment == "full_time"


def test_parse_salary_range() -> None:
    query = JobQueryParser().parse("зарплата 50000-80000")

    assert query.salary_min == Decimal("50000")
    assert query.salary_max == Decimal("80000")
