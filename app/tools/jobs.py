from dataclasses import dataclass
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Job:
    title: str
    source: str
    url: str
    location: str = ""
    salary: str = ""


class JobSearchTool:
    _base_url = "https://robota.ua/zapros"
    _user_agent = "Mozilla/5.0 (compatible; PidrobitokBot/1.0)"

    async def search(self, query: str = "python kyiv", limit: int = 10) -> list[Job]:
        normalized_query = " ".join(query.split()).strip() or "python kyiv"
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

            url = urljoin("https://robota.ua", href)
            if "robota.ua" not in url or url in seen_urls:
                continue

            parent_text = anchor.parent.get_text(" ", strip=True) if anchor.parent else ""
            location = self._extract_location(parent_text)
            salary = self._extract_salary(parent_text)

            seen_urls.add(url)
            jobs.append(
                Job(
                    title=title,
                    source="robota.ua",
                    url=url,
                    location=location,
                    salary=salary,
                )
            )
            if len(jobs) >= limit:
                break

        return jobs

    @staticmethod
    def _extract_location(text: str) -> str:
        normalized = " ".join(text.split())
        for marker in ("Київ", "Киев", "Kyiv", "Львів", "Львов", "Одеса", "Одесса"):
            if marker.casefold() in normalized.casefold():
                return marker
        return ""

    @staticmethod
    def _extract_salary(text: str) -> str:
        normalized = " ".join(text.split())
        for token in normalized.split():
            if any(char.isdigit() for char in token) and any(
                currency in token.casefold() for currency in ("грн", "uah", "$", "€", "eur")
            ):
                return token
        return ""
