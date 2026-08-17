import logging

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.agent import CareerAgent
from app.config import Settings
from app.monitor import SavedSearchMonitor
from app.saved_searches import SavedSearchStore
from app.storage import SQLiteStorage

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

settings = Settings.from_environment()
agent = CareerAgent(settings)
storage = SQLiteStorage(settings.database_path)
saved_searches = SavedSearchStore(storage)
monitor: SavedSearchMonitor | None = None

keyboard = ReplyKeyboardMarkup(
    [
        ["📍 Киев вакансии", "💼 Вакансии"],
        ["🤖 AI HR"],
    ],
    resize_keyboard=True,
)


def _split_message(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(block) > limit:
            chunks.append(block[:limit])
            block = block[limit:]
        current = block
    if current:
        chunks.append(current)
    return chunks


async def _reply(update: Update, text: str) -> None:
    if update.message is None:
        return
    for chunk in _split_message(text):
        await update.message.reply_text(chunk, disable_web_page_preview=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "🚀 Pidrobitok AI Agent\n\n"
        "Я могу искать вакансии, анализировать их и помогать с карьерой. "
        "Напиши запрос обычным языком.\n\n"
        "Пример:\n"
        "Python/FastAPI, Киев или удалённо, от 60000 грн, full-time\n\n"
        "Для автоматического мониторинга: /watch запрос | интервал_минут\n"
        "Например: /watch Python Киев от 60000 | 60\n"
        "/watches — мои мониторинги\n"
        "/unwatch ID — удалить мониторинг",
        reply_markup=keyboard,
    )


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None:
        return
    raw = " ".join(context.args).strip()
    if "|" not in raw:
        await update.message.reply_text("Формат: /watch Python Киев от 60000 | 60")
        return
    query, interval_text = (part.strip() for part in raw.split("|", 1))
    if not query:
        await update.message.reply_text("Запрос для мониторинга не может быть пустым.")
        return
    try:
        interval = int(interval_text)
        saved = saved_searches.create(update.effective_user.id, query, interval)
    except ValueError as exc:
        await update.message.reply_text(f"Не удалось создать мониторинг: {exc}")
        return
    await update.message.reply_text(
        f"✅ Мониторинг #{saved.search_id} создан.\n"
        f"Запрос: {saved.query}\n"
        f"Интервал: каждые {saved.interval_minutes} мин."
    )


async def watches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None:
        return
    items = saved_searches.list_for_user(update.effective_user.id)
    if not items:
        await update.message.reply_text("У тебя пока нет активных мониторингов.")
        return
    lines = ["🔔 Твои мониторинги:"]
    for item in items:
        status = "активен" if item.enabled else "выключен"
        lines.append(f"#{item.search_id} — {item.query} — каждые {item.interval_minutes} мин. — {status}")
    await _reply(update, "\n".join(lines))


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None or not context.args:
        if update.message is not None:
            await update.message.reply_text("Формат: /unwatch ID")
        return
    try:
        search_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return
    deleted = saved_searches.delete(update.effective_user.id, search_id)
    await update.message.reply_text("🗑 Мониторинг удалён." if deleted else "Мониторинг не найден.")


async def router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_user is None:
        return

    text = update.message.text or ""
    user_id = update.effective_user.id

    if text == "🤖 AI HR":
        await update.message.reply_text(
            "Расскажи о своём опыте, навыках, городе и желаемой зарплате. "
            "Я использую это как основу для карьерного профиля."
        )
        return

    if text in {"📍 Киев вакансии", "💼 Вакансии"}:
        text = "Найди актуальные вакансии Python в Киеве"

    try:
        await update.message.chat.send_action("typing")
        answer = await agent.respond(user_id, text)
    except Exception:
        logger.exception("Agent request failed for user %s", user_id)
        answer = "Произошла внутренняя ошибка. Попробуй ещё раз через минуту."

    await _reply(update, answer)


async def post_init(application: Application) -> None:
    global monitor
    monitor = SavedSearchMonitor(application.bot, agent, saved_searches, settings.monitor_poll_seconds)
    monitor.start()
    logger.info("Saved-search monitor started")


async def post_shutdown(application: Application) -> None:
    if monitor is not None:
        await monitor.stop()
    storage.close()
    logger.info("Saved-search monitor stopped and SQLite storage closed")


def main() -> None:
    application = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("watches", watches))
    application.add_handler(CommandHandler("unwatch", unwatch))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    logger.info("Pidrobitok AI Agent is starting")
    application.run_polling()


if __name__ == "__main__":
    main()
