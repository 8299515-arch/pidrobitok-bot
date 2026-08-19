from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from app.domain.jobs import EmploymentType, Job, JobSource


class WorkUaJobSource:
    """Work.ua HTML source adapter used when Robota.ua is unavailable."""

    _origin = "https://www.work.ua"
    _base_url = f"{_origin}/jobs"
    _user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
    _location_slugs = {
        "київ": "kyiv", "киев": "kyiv", "kyiv": "kyiv", "kiev": "kyiv",
        "львів": "lviv", "львов": "lviv", "lviv": "lviv",
        "одеса": "odesa", "одесса": "odesa", "odesa": "odesa",
        "дніпро": "dnipro", "днепр": "dnipro", "dnipro": "dnipro",
        "харків": "kharkiv", "харьков": "kharkiv", "kharkiv": "kharkiv",
    }

    @property
    def name(self) -> str:
        return JobSource.WORK_UA.value

    async def search(
        self,
        query: str = "python",
        *,
        location: str | None = None,
        limit: int = 10,
    ) -> list[Job]:
        normalized_query = "-".join(query.split()).strip("-") or "python"
        location_slug = self._location_slug(location)
        if location_slug:
            url = f"{self._base_url}-{location_slug}-{quote(normalized_query, safe='-')}/"
        else:
            url = f"{self._base_url}-{quote(normalized_query, safe='-')}/"

        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en;q=0.7",
            "Referer": f"{self._origin}/",
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        return self._parse_jobs(response.text, location=location, limit=limit)

    @classmethod
    def _parse_jobs(
        cls,
        html: str,
        *,
        location: str | None,
        limit: int,
    ) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[Job] = []
        seen: set[str] = set()

        for anchor in soup.select("a[href^='/jobs/'], a[href*='/jobs/']"):
            href = anchor.get("href")
            title = anchor.get_text(" ", strip=True)
            if not isinstance(href, str) or not cls._looks_like_job_url(href):
                continue
            if not 3 <= len(title) <= 180:
                continue

            url = cls._absolute_url(href)
            if url in seen:
                continue

            container = anchor.find_parent(["article", "div", "li"])
            context = container.get_text(" ", strip=True) if container else title
            salary_min, salary_max, currency = cls._extract_salary(context)
            city = cls._extract_location(context) or location

            jobs.append(
                Job(
                    title=title,
                    url=url,
                    source=JobSource.WORK_UA,
                    company=cls._extract_company(container, title),
                    city=city,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    remote=cls._extract_remote(context),
                    employment_type=cls._extract_employment_type(context),
                    description=context[:2000],
                    published_at=datetime.now(timezone.utc),
                    source_id=cls._source_id(url),
                )
            )
            seen.add(url)
            if len(jobs) >= limit:
                break

        return jobs

    @staticmethod
    def _looks_like_job_url(href: str) -> bool:
        return bool(re.search(r"/jobs/\d+/?(?:[?#].*)?$", href))

    @classmethod
    def _absolute_url(cls, href: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return f"{cls._origin}{href if href.startswith('/') else '/' + href}"

    @staticmethod
    def _source_id(url: str) -> str | None:
        match = re.search(r"/jobs/(\d+)", url)
        return match.group(1) if match else None

    @staticmethod
    def _extract_company(container: object, title: str) -> str | None:
        if not hasattr(container, "select"):
            return None
        candidates = []
        for selector in ("a[href*='/company/']", "a[href*='/resumes/']"):
            candidates.extend(container.select(selector))
        for candidate in candidates:
            text = candidate.get_text(" ", strip=True)
            if text and text != title:
                return text
        return None

    @classmethod
    def _location_slug(cls, location: str | None) -> str | None:
        if not location:
            return None
        return cls._location_slugs.get(" ".join(location.split()).casefold())

    @staticmethod
    def _extract_location(text: str) -> str | None:
        for location in (
            "Київ", "Киев", "Kyiv", "Львів", "Львов", "Одеса", "Одесса",
            "Дніпро", "Днепр", "Харків", "Харьков", "Україна", "Украина",
        ):
            if location.casefold() in text.casefold():
                return location
        return None

    @staticmethod
    def _extract_salary(text: str) -> tuple[Decimal | None, Decimal | None, str | None]:
        normalized = " ".join(text.split())
        number = r"(?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d+)"
        range_match = re.search(
            rf"({number})\s*[–—-]\s*({number})\s*(грн|uah|\$|€|eur|₴)",
            normalized,
            flags=re.IGNORECASE,
        )
        if range_match:
            first, second, currency = range_match.groups()
        else:
            single_match = re.search(
                rf"({number})\s*(грн|uah|\$|€|eur|₴)",
                normalized,
                flags=re.IGNORECASE,
            )
            if not single_match:
                return None, None, None
            first, currency = single_match.groups()
            second = None

        minimum = WorkUaJobSource._decimal(first)
        maximum = WorkUaJobSource._decimal(second) if second else minimum
        normalized_currency = (
            "$" if currency == "$" else
            "EUR" if currency.casefold() in {"€", "eur"} else
            "UAH"
        )
        return minimum, maximum, normalized_currency

    @staticmethod
    def _decimal(value: str) -> Decimal | None:
        try:
            return Decimal(value.replace(" ", "").replace("\u00a0", ""))
        except InvalidOperation:
            return None

    @staticmethod
    def _extract_remote(text: str) -> bool | None:
        if any(token in text.casefold() for token in ("дистанційно", "дистанционно", "remote", "віддал", "удален")):
            return True
        return None

    @staticmethod
    def _extract_employment_type(text: str) -> EmploymentType:
        normalized = text.casefold()
        if any(token in normalized for token in ("неповна зайнятість", "неполная занятость", "part-time")):
            return EmploymentType.PART_TIME
        if any(token in normalized for token in ("повна зайнятість", "полная занятость", "full-time")):
            return EmploymentType.FULL_TIME
        if any(token in normalized for token in ("контракт", "contract")):
            return EmploymentType.CONTRACT
        return EmploymentType.UNKNOWN
