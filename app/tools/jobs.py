from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Job:
    title: str
    source: str
    url: str


class JobSearchTool:
    _url = "https://robota.ua/zapros/python-kyiv"

    async def search(self, limit: int = 10) -> list[Job]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PidrobitokBot/1.0)"}
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.get(self._url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        jobs: list[Job] = []
        seen: set[str] = set()

        for heading in soup.find_all("h2"):
            title = heading.get_text(" ", strip=True)
            if not title or title in seen:
                continue
            seen.add(title)
            jobs.append(Job(title=title, source="robota.ua", url=self._url))
            if len(jobs) >= limit:
                break

        return jobs
