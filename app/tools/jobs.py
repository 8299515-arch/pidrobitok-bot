from dataclasses import dataclass
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Job:
    title: str
    source: str
    url: str


class JobSearchTool:
    _base_url = "https://robota.ua/zapros"

    async def search(self, query: str = "python kyiv", limit: int = 10) -> list[Job]:
        normalized_query = " ".join(query.split()).strip() or "python kyiv"
        url = f"{self._base_url}/{quote(normalized_query, safe='') }"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PidrobitokBot/1.0)"}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        jobs: list[Job] = []
        seen: set[str] = set()

        for heading in soup.find_all("h2"):
            title = heading.get_text(" ", strip=True)
            if not title or title in seen:
                continue
            seen.add(title)
            jobs.append(Job(title=title, source="robota.ua", url=url))
            if len(jobs) >= limit:
                break

        return jobs
