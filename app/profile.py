from dataclasses import dataclass, replace
import re

from app.storage import SQLiteStorage


@dataclass(frozen=True)
class CandidateProfile:
    skills: tuple[str, ...] = ()
    city: str | None = None
    salary_min: int | None = None
    remote: bool = False


class CandidateProfileStore:
    def __init__(self, storage: SQLiteStorage) -> None:
        self._storage = storage
        self._profiles: dict[int, CandidateProfile] = {}

    def get(self, user_id: int) -> CandidateProfile:
        cached = self._profiles.get(user_id)
        if cached is not None:
            return cached
        persisted = self._storage.get_profile(user_id)
        if persisted is None:
            profile = CandidateProfile()
        else:
            skills, city, salary_min, remote = persisted
            profile = CandidateProfile(skills=skills, city=city, salary_min=salary_min, remote=remote)
        self._profiles[user_id] = profile
        return profile

    def update_from_text(self, user_id: int, text: str) -> CandidateProfile:
        current = self.get(user_id)
        normalized = text.casefold()
        skills = list(current.skills)
        known_skills = (
            "python", "django", "fastapi", "flask", "postgresql", "sql",
            "javascript", "typescript", "react", "flutter", "java", "c++",
        )
        for skill in known_skills:
            if re.search(rf"(?<![a-z0-9+#]){re.escape(skill)}(?![a-z0-9+#])", normalized):
                if skill not in skills:
                    skills.append(skill)

        city = current.city
        city_aliases = {
            "киев": "Киев", "київ": "Киев", "kyiv": "Киев",
            "львов": "Львов", "львів": "Львов", "lviv": "Львов",
            "одесса": "Одесса", "одеса": "Одесса", "odesa": "Одесса",
            "днепр": "Днепр", "дніпро": "Днепр", "dnipro": "Днепр",
            "харьков": "Харьков", "харків": "Харьков", "kharkiv": "Харьков",
        }
        for alias, canonical in city_aliases.items():
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
                city = canonical
                break

        salary_min = current.salary_min
        salary_patterns = (
            r"(?:от|минимум|мінімум|зарплата|ставка)\s*(\d[\d\s.,]{2,})\s*(?:грн|uah|₴)?",
            r"(\d[\d\s.,]{3,})\s*(?:грн|uah|₴)\s*(?:и|від|от)?",
        )
        for pattern in salary_patterns:
            salary_match = re.search(pattern, normalized)
            if salary_match:
                digits = re.sub(r"\D", "", salary_match.group(1))
                if digits:
                    salary_min = int(digits)
                    break

        remote = current.remote or any(
            phrase in normalized for phrase in ("удален", "удалён", "remote", "дистанцион", "віддален", "віддалено")
        )
        profile = replace(current, skills=tuple(skills), city=city, salary_min=salary_min, remote=remote)
        self._profiles[user_id] = profile
        self._storage.save_profile(user_id, profile.skills, profile.city, profile.salary_min, profile.remote)
        return profile
