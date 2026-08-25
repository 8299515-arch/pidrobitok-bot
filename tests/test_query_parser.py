from decimal import Decimal
import unittest

from app.query_parser import JobQueryParser


class QueryParserTests(unittest.TestCase):
    def test_parse_natural_language_job_request(self) -> None:
        query = JobQueryParser().parse(
            "Ищу Python/FastAPI в Киеве или удалённо, от 60к, full-time"
        )

        self.assertEqual(query.skills, ("python", "fastapi"))
        self.assertEqual(query.city, "Киев")
        self.assertTrue(query.remote)
        self.assertEqual(query.salary_min, Decimal("60000"))
        self.assertEqual(query.employment, "full_time")

    def test_parse_salary_range(self) -> None:
        query = JobQueryParser().parse("зарплата 50000-80000")

        self.assertEqual(query.salary_min, Decimal("50000"))
        self.assertEqual(query.salary_max, Decimal("80000"))


if __name__ == "__main__":
    unittest.main()
