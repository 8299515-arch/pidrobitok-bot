from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from app.domain.jobs import EmploymentType, Job, JobSource


class JobSearchTool:
    """Robota.ua source adapter."""

    _base_url = "https://robota.ua/zapros"
    _origin = "https://robota.ua"
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
        "запоріжжя": "zaporizhzhia", "запорожье": "zaporizhzhia",
        "zaporizhzhia": "zaporizhzhia", "вінниця": "vinnytsia",
        "винница": "vinnytsia", "vinnytsia": "vinnytsia",
        "україна": "ukraine", "украина": "ukraine", "ukraine": "ukraine",
    }

    @property
    def name(self) -> str:
        return JobSource.ROBOTA_UA.value

    async def search(self, query: str = "python", *, location: str | None = None, limit: int = 10) -> list[Job]:
        normalized_query = " ".join(query.split()).strip() or "python"
        location_slug = self._location_slug(location)
        if location:
            location_tokens = {token.casefold() for token in location.split()}
            normalized_query = " ".join(
                token for token in normalized_query.split()
                if token.casefold() not in location_tokens
            ).strip() or "python"

        search_url = f"{self._base_url}/{quote(normalized_query, safe='')}/{location_slug}"
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en;q=0.7",
            "Referer": f"{self._origin}/",
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            response.raise_for_status()
        return self._parse_jobs(response.text, location=location, limit=limit)

    @classmethod
    def _parse_jobs(cls, html: str, *, location: str | None, limit: int) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[Job] = []
        seen: set[str] = set()

        for payload in cls._structured_payloads(soup):
            for data in cls._walk(payload):
                job = cls._job_from_mapping(data, location=location)
                if job is None or job.canonical_url in seen:
                    continue
                jobs.append(job)
                seen.add(job.canonical_url)
                if len(jobs) >= limit:
                    return jobs

        # Conservative fallback for HTML links. Only actual vacancy URLs are accepted.
        for anchor in soup.select("a[href]"):
            href = anchor.get("href")
            title = anchor.get_text(" ", strip=True)
            if not isinstance(href, str) or not cls._looks_like_job_url(href):
                continue
            if not 3 <= len(title) <= 180:
                continue
            url = urljoin(cls._origin, href)
            if url in seen:
                continue
            context = anchor.parent.get_text(" ", strip=True) if anchor.parent else title
            salary_min, salary_max, currency = cls._extract_salary(context)
            jobs.append(Job(
                title=title,
                url=url,
                source=JobSource.ROBOTA_UA,
                city=cls._extract_location(context) or location,
                salary_min=salary_min,
                salary_max=salary_max,
                currency=currency,
                remote=cls._extract_remote(context),
                employment_type=cls._extract_employment_type(context),
                description=context[:2000],
                published_at=datetime.now(timezone.utc),
            ))
            seen.add(url)
            if len(jobs) >= limit:
                break
        return jobs

    @staticmethod
    def _structured_payloads(soup: BeautifulSoup) -> list[object]:
        payloads: list[object] = []
        for script in soup.select("script[type='application/ld+json'], script#__NEXT_DATA__"):
            raw = script.string or script.get_text()
            if not raw.strip():
                continue
            try:
                payloads.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return payloads

    @classmethod
    def _walk(cls, value: object) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        if isinstance(value, dict):
            if cls._is_job_mapping(value):
                result.append(value)
            for child in value.values():
                result.extend(cls._walk(child))
        elif isinstance(value, list):
            for child in value:
                result.extend(cls._walk(child))
        return result

    @staticmethod
    def _is_job_mapping(value: dict[str, object]) -> bool:
        title = value.get("title") or value.get("name")
        url = value.get("url") or value.get("absoluteUrl") or value.get("link")
        return isinstance(title, str) and isinstance(url, str) and "robota.ua" in url

    @classmethod
    def _job_from_mapping(cls, data: dict[str, object], *, location: str | None) -> Job | None:
        title = cls._first_string(data, "title", "name")
        raw_url = cls._first_string(data, "url", "absoluteUrl", "link")
        if not title or not raw_url:
            return None
        url = urljoin(cls._origin, raw_url)
        if not cls._looks_like_job_url(url):
            return None

        organization = data.get("hiringOrganization") or data.get("company") or data.get("employer")
        company = cls._first_string(organization, "name") if isinstance(organization, dict) else cls._string(organization)
        city = cls._location_from_value(data.get("jobLocation") or data.get("location")) or location
        description = cls._strip_html(cls._string(data.get("description")))
        salary_text = cls._salary_text(data.get("baseSalary") or data.get("salary"))
        context = " ".join(x for x in (title, company, city, description, salary_text, cls._string(data.get("employmentType"))) if x)
        salary_min, salary_max, currency = cls._extract_salary(salary_text or context)

        return Job(
            title=title,
            url=url,
            source=JobSource.ROBOTA_UA,
            company=company,
            city=city,
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            remote=cls._extract_remote(context),
            employment_type=cls._extract_employment_type(context),
            description=(description or context)[:2000],
            published_at=cls._parse_datetime(cls._first_string(data, "datePosted", "publishedAt")) or datetime.now(timezone.utc),
            source_id=cls._first_string(data, "id", "sourceId", "vacancyId"),
        )

    @staticmethod
    def _first_string(value: object, *keys: str) -> str | None:
        if not isinstance(value, dict):
            return None
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if isinstance(candidate, (int, float)):
                return str(candidate)
        return None

    @staticmethod
    def _string(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @classmethod
    def _location_from_value(cls, value: object) -> str | None:
        if isinstance(value, list):
            for item in value:
                result = cls._location_from_value(item)
                if result:
                    return result
        elif isinstance(value, dict):
            for key in ("address", "city", "name"):
                result = cls._location_from_value(value.get(key))
                if result:
                    return result
        elif isinstance(value, str):
            return cls._extract_location(value)
        return None

    @staticmethod
    def _salary_text(value: object) -> str | None:
        if isinstance(value, str):
            return value
        if not isinstance(value, dict):
            return None
        return " ".join(str(value[key]) for key in ("minValue", "value", "maxValue", "currency") if value.get(key) is not None)

    @staticmethod
    def _strip_html(value: str | None) -> str | None:
        return BeautifulSoup(value, "html.parser").get_text(" ", strip=True) if value else None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _looks_like_job_url(url: str) -> bool:
        normalized = url.casefold()
        return "robota.ua" in normalized and any(token in normalized for token in ("/vacancy", "/job/", "/jobs/"))

    async def health(self) -> dict[str, object]:
        return {"source": self.name, "available": True}

    @classmethod
    def _location_slug(cls, location: str | None) -> str:
        if not location:
            return "ukraine"
        return cls._location_slugs.get(" ".join(location.split()).casefold(), "ukraine")

    @staticmethod
    def _extract_location(text: str) -> str | None:
        for location in ("Київ", "Киев", "Kyiv", "Львів", "Львов", "Одеса", "Одесса", "Дніпро", "Днепр", "Харків", "Харьков", "Україна", "Украина"):
            if location.casefold() in text.casefold():
                return location
        return None

    @staticmethod
    def _extract_salary(text: str) -> tuple[Decimal | None, Decimal | None, str | None]:
        matches = re.findall(r"(\d[\d\s]{2,})(?:\s*[–—-]\s*(\d[\d\s]{2,}))?\s*(грн|uah|\$|€|eur|₴)", " ".join(text.split()), re.IGNORECASE)
        if not matches:
            return None, None, None
        first, second, currency = matches[0]
        minimum = JobSearchTool._decimal(first)
        maximum = JobSearchTool._decimal(second) if second else minimum
        normalized_currency = "$" if currency == "$" else "EUR" if currency.casefold() in {"€", "eur"} else "UAH"
        return minimum, maximum, normalized_currency

    @staticmethod
    def _decimal(value: str) -> Decimal | None:
        try:
            return Decimal(value.replace(" ", ""))
        except InvalidOperation:
            return None

    @staticmethod
    def _extract_remote(text: str) -> bool | None:
        if any(token in text.casefold() for token in ("remote", "віддал", "удален", "дистанцион")):
            return True
        return None

    @staticmethod
    def _extract_employment_type(text: str) -> EmploymentType:
        normalized = text.casefold()
        if any(token in normalized for token in ("неповна зайнятість", "неполная занятость", "part-time")):
            return EmploymentType.PART_TIME
        if any(token in normalized for token in ("контракт", "contract")):
            return EmploymentType.CONTRACT
        if any(token in normalized for token in ("повна зайнятість", "полная занятость", "full-time")):
            return EmploymentType.FULL_TIME
        return EmploymentType.UNKNOWN
