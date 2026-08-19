import unittest
from decimal import Decimal

from app.tools.jobs import JobSearchTool


class JobSearchToolTests(unittest.TestCase):
    def test_parse_json_ld_job_posting(self) -> None:
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@type": "JobPosting",
          "title": "Python Developer",
          "url": "https://robota.ua/company/job/123",
          "hiringOrganization": {"name": "Acme"},
          "jobLocation": {"address": {"addressLocality": "Київ"}},
          "baseSalary": {"minValue": 50000, "maxValue": 80000, "currency": "UAH"},
          "description": "Python backend developer",
          "datePosted": "2026-08-19T10:00:00Z"
        }
        </script></head></html>
        """

        result = JobSearchTool._parse_jobs(html, location="Київ", limit=10)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Python Developer")
        self.assertEqual(result[0].company, "Acme")
        self.assertEqual(result[0].city, "Київ")
        self.assertEqual(result[0].salary_min, Decimal("50000"))
        self.assertEqual(result[0].salary_max, Decimal("80000"))
        self.assertEqual(result[0].currency, "UAH")

    def test_parser_does_not_treat_navigation_links_as_jobs(self) -> None:
        html = """
        <html><body>
          <a href="https://robota.ua/">Головна</a>
          <a href="https://robota.ua/zapros/python/kyiv">Python вакансії</a>
        </body></html>
        """

        result = JobSearchTool._parse_jobs(html, location="Київ", limit=10)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
