import logging

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.agent import CareerAgent
from app.config import Settings

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

settings = Settings.from_environment()
agent = CareerAgent(settings)

keyboard = ReplyKeyboardMarkup(
    [
        ["📍 Киев вакансии", "💼 Вакансии"],
        ["🤖 AI HR"],
    ],
    resize_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "🚀 Pidrobitok AI Agent\n\n"
        "Я могу искать вакансии и помогать с карьерой. "
        "Напиши запрос обычным языком.",
        reply_markup=keyboard,
    )


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

    await update.message.reply_text(answer)


def main() -> None:
    application = Application.builder().token(settings.bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    logger.info("Pidrobitok AI Agent is starting")
    application.run_polling()


if __name__ == "__main__":
    main()
