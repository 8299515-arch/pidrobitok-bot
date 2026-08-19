import unittest

from app.agent import CareerAgent


class AgentRoutingTests(unittest.TestCase):
    def test_career_advice_is_not_job_search(self) -> None:
        text = "Проанализируй мой профиль и посоветуй, какую работу мне лучше искать"
        self.assertFalse(CareerAgent._looks_like_job_search(text))

    def test_explicit_job_search_is_job_search(self) -> None:
        text = "найди работу Python Киев от 35000"
        self.assertTrue(CareerAgent._looks_like_job_search(text))


if __name__ == "__main__":
    unittest.main()