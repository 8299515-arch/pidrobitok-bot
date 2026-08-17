import asyncio

from google import genai
from google.genai import types
import httpx

from app.config import Settings
from app.memory import ConversationMemory
from app.profile import CandidateProfileStore
from app.storage import SQLiteStorage
from app.tools.job_aggregator import JobAggregator
from app.tools.job_pipeline import JobPipeline
from app.tools.job_ranker import JobRanker
from app.tools.jobs import JobSearchTool
from app.tools.olx import OlxJobSource
from app.tools.telegram_jobs import TelegramJobSource


class CareerAgent:
    _system_instruction = (
        "Ты AI-карьерный агент Pidrobitok. "
        "Помогай пользователю искать работу, анализировать вакансии и карьерные возможности. "
        "Отвечай на русском языке, если пользователь не просит другой язык. "
        "Не выдумывай вакансии, зарплаты, компании или ссылки. "
        "Если пользователь просит актуальные вакансии, используй доступные источники поиска. "
        "Учитывай сохранённый профиль кандидата, если он есть."
    )

    def __init__(self, settings: Settings) -> None:
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = settings.ai_model
        self._memory = ConversationMemory(settings.max_history_messages)
        storage = SQLiteStorage(settings.database_path)
        self._profiles = CandidateProfileStore(storage)
        self._source_limit = settings.job_source_limit
        self._job_sources = (
            JobSearchTool(),
            OlxJobSource(),
            TelegramJobSource(settings.telegram_job_channels),
        )
        self._job_pipeline = JobPipeline(JobAggregator(), JobRanker())

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
        location = profile.city
        source_results = await asyncio.gather(
            *(
                self._safe_source_search(source, query=query, location=location)
                for source in self._job_sources
            )
        )
        ranked_jobs = self._job_pipeline.run(source_results, profile, limit=self._source_limit)

        if not ranked_jobs:
            return "По доступным источникам подходящих вакансий не найдено."

        lines = [f"🔎 Лучшие вакансии по запросу: {query}", ""]
        for index, ranked in enumerate(ranked_jobs, start=1):
            job = ranked.job
            lines.append(f"{index}. {job.title} — совпадение {ranked.score}%")
            lines.append(f"   Источник: {job.source.value}")
            if job.city:
                lines.append(f"   📍 {job.city}")
            if job.salary_min is not None:
                salary = self._format_salary(job.salary_min, job.salary_max, job.currency)
                lines.append(f"   💰 {salary}")
            if job.remote is True:
                lines.append("   🏠 Удалённая работа")
            if ranked.reasons:
                lines.append(f"   ✓ {'; '.join(ranked.reasons)}")
            lines.append(f"   🔗 {job.url}")
            lines.append("")

        return "\n".join(lines).strip()

    @staticmethod
    async def _safe_source_search(source: object, *, query: str, location: str | None) -> list:
        try:
            search = getattr(source, "search")
            return list(await search(query, location=location, limit=10))
        except (httpx.HTTPError, TimeoutError):
            return []
        except Exception:
            return []

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
    def _build_job_query(text: str, profile: object) -> str:
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
    def _format_salary(minimum: object, maximum: object | None, currency: str | None) -> str:
        currency_label = currency or ""
        if maximum is None or minimum == maximum:
            return f"{minimum} {currency_label}".strip()
        return f"{minimum}–{maximum} {currency_label}".strip()

    @staticmethod
    def _looks_like_job_search(text: str) -> bool:
        keywords = (
            "ваканс", "работ", "job", "найди работу", "ищу работу", "поищи работу",
        )
        return any(keyword in text for keyword in keywords)
