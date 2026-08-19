import unittest
from decimal import Decimal

from app.tools.jobs import JobSearchTool
from app.tools.workua_jobs import WorkUaJobSource


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


class WorkUaJobSourceTests(unittest.TestCase):
    def test_parse_job_card(self) -> None:
        html = """
        <html><body>
          <article>
            <h2><a href="/jobs/1234567/">Python Developer</a></h2>
            <a href="/company/acme/">Acme</a>
            <div>50 000 — 80 000 грн</div>
            <div>Київ</div>
            <div>Повна зайнятість. Досвід роботи від 2 років.</div>
          </article>
        </body></html>
        """

        result = WorkUaJobSource._parse_jobs(html, location="Київ", limit=10)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Python Developer")
        self.assertEqual(result[0].company, "Acme")
        self.assertEqual(result[0].city, "Київ")
        self.assertEqual(result[0].salary_min, Decimal("50000"))
        self.assertEqual(result[0].salary_max, Decimal("80000"))
        self.assertEqual(result[0].currency, "UAH")
        self.assertEqual(result[0].source_id, "1234567")

    def test_navigation_links_are_not_jobs(self) -> None:
        html = """
        <html><body>
          <a href="/jobs/">Усі вакансії</a>
          <a href="/jobs-kyiv-python/">Python у Києві</a>
          <a href="/company/acme/">Acme</a>
        </body></html>
        """

        result = WorkUaJobSource._parse_jobs(html, location="Київ", limit=10)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
