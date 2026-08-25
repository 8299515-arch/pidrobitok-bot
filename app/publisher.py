from __future__ import annotations

import logging

from telegram import Bot

from app.pipeline import ProcessedJob

logger = logging.getLogger(__name__)


class TelegramPublisher:
    def __init__(self, bot: Bot, channel_username: str) -> None:
        normalized = channel_username.strip().removeprefix("@").removesuffix("/")
        if not normalized:
            raise ValueError("Publisher channel must not be empty")
        self._bot = bot
        self._channel = f"@{normalized}"

    async def publish(self, processed: ProcessedJob) -> int | None:
        if not processed.is_valid:
            return None
        job = processed.job
        text = self._format(job, processed.quality_score)
        message = await self._bot.send_message(
            chat_id=self._channel,
            text=text,
            disable_web_page_preview=False,
        )
        logger.info("Published job source_id=%s channel=%s message_id=%s", job.source_id, self._channel, message.message_id)
        return message.message_id

    @staticmethod
    def _format(job: object, score: int) -> str:
        title = str(getattr(job, "title"))
        url = str(getattr(job, "url"))
        company = getattr(job, "company", None)
        city = getattr(job, "city", None)
        salary_min = getattr(job, "salary_min", None)
        salary_max = getattr(job, "salary_max", None)
        currency = getattr(job, "currency", None) or ""
        lines = [f"💼 {title}", f"⭐ Якість: {score}%"]
        if company:
            lines.append(f"🏢 {company}")
        if city:
            lines.append(f"📍 {city}")
        if salary_min is not None:
            salary = f"{salary_min}–{salary_max}" if salary_max is not None else str(salary_min)
            lines.append(f"💰 {salary} {currency}".strip())
        description = getattr(job, "description", None)
        if description:
            lines.extend(("", str(description)[:1800]))
        lines.extend(("", f"🔗 {url}"))
        return "\n".join(lines)
