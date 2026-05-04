import asyncio
import logging
from datetime import datetime
from google import genai
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = "8704316956:AAE1h8MnbwvL35GNeiLEUflTKCUIfhMIKgU"
GEMINI_API_KEY = "AIzaSyCQx8bjxFhwCVD1qBGZW3J9MMhEXk7nSnU"
CHANNEL_ID = "@PodrabotkaKiev_1"

POST_INTERVAL = 3 * 60 * 60  # кожні 3 години

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def generate_vacancy_post() -> str:
    prompt = """Ти — менеджер Telegram-каналу "Різноробочі Київ | Підробіток".

Створи оголошення про вакансію для різнорабочого або підробітку в Києві.
Вакансія має бути РЕАЛІСТИЧНОЮ — такою яку справді публікують в Києві.

Типи вакансій: вантажники, прибиральники, підсобні робітники, муляри, маляри, 
двірники, охоронці, кур'єри, комірники, мийники посуду, посудомийники, 
різноробочі на будівництво, грузчики на склад тощо.

Формат посту:
- Назва вакансії з емодзі
- Район Києва або метро
- Зарплата (реальна, від 500 до 1500 грн/день або від 15000 до 30000 грн/міс)
- 2-3 вимоги або умови роботи
- Контакт (придумай реальний номер телефону +380...)
- Хештеги #підробіток #київ #робота

Стиль: живий, без зайвих слів, українська мова або суржик.
Довжина: 80-120 слів."""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return None


async def collect_and_post(bot: Bot):
    logger.info("🤖 Генеруємо вакансію через AI...")
    try:
        post_text = generate_vacancy_post()
        if not post_text:
            logger.error("Не вдалося згенерувати пост")
            return
        await bot.send_message(chat_id=CHANNEL_ID, text=post_text)
        logger.info("✅ Вакансію опубліковано!")
    except Exception as e:
        logger.error(f"Помилка публікації: {e}")


async def auto_post_loop(bot: Bot):
    while True:
        await collect_and_post(bot)
        logger.info(f"⏰ Наступна публікація через {POST_INTERVAL // 3600} год")
        await asyncio.sleep(POST_INTERVAL)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔨 Привіт! Я публікую вакансії в канал.\n\n"
        "/post — опублікувати зараз\n"
        "/status — статус бота"
    )

async def manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Генерую вакансію...")
    await collect_and_post(context.bot)
    await update.message.reply_text("✅ Готово! Перевірте канал.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Канал: {CHANNEL_ID}\n"
        f"🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"✅ Бот працює!"
    )


async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", manual_post))
    app.add_handler(CommandHandler("status", status))
    logger.info("🚀 Бот запущено!")
    async with app:
        await app.start()
        asyncio.create_task(auto_post_loop(app.bot))
        await app.updater.start_polling()
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
