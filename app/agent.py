from google import genai
from google.genai import types
import httpx

from app.config import Settings
from app.memory import ConversationMemory
from app.profile import CandidateProfile, CandidateProfileStore
from app.tools.jobs import JobSearchTool


class CareerAgent:
    _system_instruction = (
        "Ты AI-карьерный агент Pidrobitok. "
        "Помогай пользователю искать работу, анализировать вакансии и карьерные возможности. "
        "Отвечай на русском языке, если пользователь не просит другой язык. "
        "Не выдумывай вакансии, зарплаты, компании или ссылки. "
        "Если пользователь просит актуальные вакансии, используй доступный инструмент поиска. "
        "Учитывай сохранённый профиль кандидата, если он есть."
    )

    def __init__(self, settings: Settings) -> None:
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = settings.ai_model
        self._memory = ConversationMemory(settings.max_history_messages)
        self._profiles = CandidateProfileStore()
        self._jobs = JobSearchTool()

    async def respond(self, user_id: int, text: str) -> str:
        self._memory.add(user_id, "user", text)
        self._profiles.update_from_text(user_id, text)
        normalized = text.casefold()

        if self._looks_like_job_search(normalized):
            answer = await self._search_jobs(user_id, text)
        else:
            answer = await self._ask_model(user_id)

        self._memory.add(user_id, "assistant", answer)
        return answer

    async def _search_jobs(self, user_id: int, text: str) -> str:
        profile = self._profiles.get(user_id)
        query = self._build_job_query(text, profile)

        try:
            jobs = await self._jobs.search(query=query)
        except httpx.HTTPError:
            return "Источник вакансий временно недоступен. Попробуй ещё раз через несколько минут."
        except Exception:
            return "Не удалось получить актуальные вакансии. Попробуй ещё раз через несколько минут."

        if not jobs:
            return "По текущему источнику подходящих вакансий не найдено."

        lines = [f"🔎 Вакансии по запросу: {query}", ""]
        for index, job in enumerate(jobs, start=1):
            lines.append(f"{index}. {job.title}")
            lines.append(f"   Источник: {job.source}")
            if job.location:
                lines.append(f"   📍 {job.location}")
            if job.salary:
                lines.append(f"   💰 {job.salary}")
            lines.append(f"   🔗 {job.url}")
            lines.append("")

        return "\n".join(lines).strip()

    async def _ask_model(self, user_id: int) -> str:
        history = self._memory.history(user_id)
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part(text=message.content)],
            )
            for message in history
        ]

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=self._system_instruction,
            ),
        )
        text = (response.text or "").strip()
        return text or "Не удалось сформировать ответ. Попробуй сформулировать запрос иначе."

    @staticmethod
    def _build_job_query(text: str, profile: CandidateProfile) -> str:
        normalized = text.casefold()
        parts: list[str] = []

        for skill in (
            "python", "django", "fastapi", "flask", "javascript", "typescript",
            "react", "flutter", "java", "c++",
        ):
            if skill in normalized:
                parts.append(skill)

        if profile.city:
            parts.append(profile.city)
        elif "киев" in normalized or "київ" in normalized:
            parts.append("kyiv")

        if profile.remote or any(
            phrase in normalized for phrase in ("remote", "удален", "удалён", "дистанцион")
        ):
            parts.append("remote")

        return " ".join(dict.fromkeys(parts)) or "python kyiv"

    @staticmethod
    def _looks_like_job_search(text: str) -> bool:
        keywords = (
            "ваканс",
            "работ",
            "job",
            "найди работу",
            "ищу работу",
            "поищи работу",
        )
        return any(keyword in text for keyword in keywords)
