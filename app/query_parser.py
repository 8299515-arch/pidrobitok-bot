from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True, slots=True)
class JobQuery:
    text: str
    skills: tuple[str, ...] = ()
    city: str | None = None
    remote: bool | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    employment: str | None = None


class JobQueryParser:
    _skills = (
        "python", "django", "fastapi", "flask", "postgresql", "sql",
        "javascript", "typescript", "react", "flutter", "java", "c++",
        "php", "node.js", "node", "go", "golang", "kotlin", "swift",
    )
    _cities = {
        "киев": "Киев", "київ": "Киев", "kyiv": "Киев",
        "львов": "Львов", "львів": "Львов", "lviv": "Львов",
        "одесса": "Одесса", "одеса": "Одесса", "odesa": "Одесса",
        "днепр": "Днепр", "дніпро": "Днепр", "dnipro": "Днепр",
        "харьков": "Харьков", "харків": "Харьков", "kharkiv": "Харьков",
    }

    def parse(self, text: str) -> JobQuery:
        normalized = text.casefold()
        skills = tuple(skill for skill in self._skills if skill in normalized)
        city = next((value for key, value in self._cities.items() if key in normalized), None)
        remote = True if any(value in normalized for value in ("remote", "удален", "удалён", "дистанцион")) else None
        salary_min, salary_max = self._salary(normalized)
        employment = None
        if any(value in normalized for value in ("full-time", "full time", "полная занятость", "фуллтайм")):
            employment = "full_time"
        elif any(value in normalized for value in ("part-time", "part time", "частичная занятость", "парттайм")):
            employment = "part_time"
        elif any(value in normalized for value in ("contract", "контракт")):
            employment = "contract"
        return JobQuery(text=text.strip(), skills=skills, city=city, remote=remote, salary_min=salary_min, salary_max=salary_max, employment=employment)

    @staticmethod
    def _salary(text: str) -> tuple[Decimal | None, Decimal | None]:
        matches = re.findall(r"(?:(?:от|минимум|не менее|от\s*)\s*)?(\d[\d\s.,]{2,})\s*(?:к|k|тыс|тысяч|грн|uah|usd|\$|€)?", text)
        values: list[Decimal] = []
        for raw in matches:
            cleaned = raw.replace(" ", "").replace(",", ".")
            try:
                value = Decimal(cleaned)
            except InvalidOperation:
                continue
            if value < 1000:
                value *= 1000
            if Decimal("1000") <= value <= Decimal("10000000"):
                values.append(value)
        if not values:
            return None, None
        if len(values) >= 2 and any(marker in text for marker in ("-", "до", "–")):
            return min(values), max(values)
        return min(values), None
