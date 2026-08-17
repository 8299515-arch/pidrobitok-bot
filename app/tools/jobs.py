from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from app.domain.jobs import EmploymentType, Job, JobSource


class JobSearchTool:
    """Compatibility facade for the Robota.ua source adapter."""

    _base_url = "https://robota.ua/zapros"
    _origin = "https://robota.ua"
    _user_agent = "Mozilla/5.0 (compatible; PidrobitokBot/1.0)"

    @property
    def name(self) -> str:
        return JobSource.ROBOTA_UA.value

    async def search(
        self,
        query: str = "python kyiv",
        *,
        location: str | None = None,
        limit: int = 10,
    ) -> list[Job]:
        normalized_query = " ".join(query.split()).strip() or "python"
        if location and location.casefold() not in normalized_query.casefold():
            normalized_query = f"{normalized_query} {location}".strip()

        search_url = f"{self._base_url}/{quote(normalized_query, safe='')}"
        headers = {"User-Agent": self._user_agent}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        jobs: list[Job] = []
        seen_urls: set[str] = set()

        for anchor in soup.select("a[href]"):
            title = anchor.get_text(" ", strip=True)
            href = anchor.get("href")
            if not title or not isinstance(href, str):
                continue
            if len(title) < 3 or len(title) > 180:
                continue

            url = urljoin(self._origin, href)
            if not url.startswith(f"{self._origin}/") or url in seen_urls:
                continue

            context = anchor.parent.get_text(" ", strip=True) if anchor.parent else title
            job = Job(
                title=title,
                url=url,
                source=JobSource.ROBOTA_UA,
                city=self._extract_location(context),
                salary_min=self._extract_salary(context)[0],
                salary_max=self._extract_salary(context)[1],
                currency=self._extract_salary(context)[2],
                remote=self._extract_remote(context),
                employment_type=self._extract_employment_type(context),
                published_at=datetime.now(timezone.utc),
            )
            seen_urls.add(url)
            jobs.append(job)
            if len(jobs) >= limit:
                break

        return jobs

    async def health(self) -> dict[str, object]:
        return {"source": self.name, "available": True}

    @staticmethod
    def _extract_location(text: str) -> str | None:
        normalized = " ".join(text.split())
        locations = (
            "Київ", "Киев", "Kyiv", "Львів", "Львов", "Одеса", "Одесса",
            "Дніпро", "Днепр", "Харків", "Харьков", "Україна", "Украина",
        )
        for location in locations:
            if location.casefold() in normalized.casefold():
                return location
        return None

    @staticmethod
    def _extract_salary(text: str) -> tuple[Decimal | None, Decimal | None, str | None]:
        normalized = " ".join(text.split())
        matches = re.findall(
            r"(\d[\d\s]{2,})(?:\s*[–—-]\s*(\d[\d\s]{2,}))?\s*(грн|uah|\$|€|eur)",
            normalized,
            flags=re.IGNORECASE,
        )
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
        normalized = text.casefold()
        if any(token in normalized for token in ("remote", "віддал", "удален", "дистанцион")):
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
