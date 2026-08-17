from google import genai

from app.config import Settings
from app.memory import ConversationMemory
from app.tools.jobs import JobSearchTool


class CareerAgent:
    _system_instruction = (
        "Ты AI-карьерный агент Pidrobitok. "
        "Помогай пользователю искать работу, анализировать вакансии и резюме. "
        "Отвечай на русском языке, если пользователь не просит другой язык. "
        "Не выдумывай вакансии, зарплаты, компании или ссылки. "
        "Если пользователь просит актуальные вакансии, используй доступный инструмент поиска."
    )

    def __init__(self, settings: Settings) -> None:
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = settings.ai_model
        self._memory = ConversationMemory(settings.max_history_messages)
        self._jobs = JobSearchTool()

    async def respond(self, user_id: int, text: str) -> str:
        self._memory.add(user_id, "user", text)
        normalized = text.casefold()

        if self._looks_like_job_search(normalized):
            answer = await self._search_jobs()
        else:
            answer = await self._ask_model(user_id)

        self._memory.add(user_id, "assistant", answer)
        return answer

    async def _search_jobs(self) -> str:
        try:
            jobs = await self._jobs.search()
        except Exception:
            return "Не удалось получить актуальные вакансии. Попробуй ещё раз через несколько минут."

        if not jobs:
            return "По текущему источнику подходящих вакансий не найдено."

        lines = ["🔎 Актуальные вакансии:", ""]
        for index, job in enumerate(jobs, start=1):
            lines.append(f"{index}. {job.title}")
            lines.append(f"   Источник: {job.source}")
            lines.append(f"   {job.url}")

        return "\n".join(lines)

    async def _ask_model(self, user_id: int) -> str:
        history = self._memory.history(user_id)
        contents = [
            {"role": message.role, "parts": [{"text": message.content}]}
            for message in history
        ]

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config={"system_instruction": self._system_instruction},
        )
        text = (response.text or "").strip()
        return text or "Не удалось сформировать ответ. Попробуй сформулировать запрос иначе."

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
