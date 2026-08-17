from dataclasses import dataclass, replace
import re


@dataclass(frozen=True)
class CandidateProfile:
    skills: tuple[str, ...] = ()
    city: str | None = None
    salary_min: int | None = None
    remote: bool = False


class CandidateProfileStore:
    def __init__(self) -> None:
        self._profiles: dict[int, CandidateProfile] = {}

    def get(self, user_id: int) -> CandidateProfile:
        return self._profiles.get(user_id, CandidateProfile())

    def update_from_text(self, user_id: int, text: str) -> CandidateProfile:
        current = self.get(user_id)
        normalized = text.casefold()

        skills = list(current.skills)
        known_skills = (
            "python", "django", "fastapi", "flask", "postgresql", "sql",
            "javascript", "typescript", "react", "flutter", "java", "c++",
        )
        for skill in known_skills:
            if skill in normalized and skill not in skills:
                skills.append(skill)

        city = current.city
        for candidate_city in ("киев", "київ", "львов", "одесса", "днепр", "харьков"):
            if candidate_city in normalized:
                city = candidate_city
                break

        salary_min = current.salary_min
        salary_match = re.search(r"(?:от|минимум|зарплата)\s*(\d[\d\s]{2,})", normalized)
        if salary_match:
            salary_min = int(salary_match.group(1).replace(" ", ""))

        remote = current.remote or any(
            phrase in normalized for phrase in ("удален", "удалён", "remote", "дистанцион")
        )

        profile = replace(
            current,
            skills=tuple(skills),
            city=city,
            salary_min=salary_min,
            remote=remote,
        )
        self._profiles[user_id] = profile
        return profile
