import asyncio
import logging
from datetime import datetime
from google import genai
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update, Bot
from telegram.error import TelegramError
import os
from dotenv import load_dotenv
import httpx
import re

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8237986787:AAEmWuDMr38QRp3UrsW-phre9F2O_e2khBs")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyC3ebLl8PfdhH4Ey5WTMXAqNaTEtHXFdI4")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@PodrabotkaKiev_1")

if not TELEGRAM_TOKEN:
    raise ValueError("Нет TELEGRAM_TOKEN")
if not GEMINI_API_KEY:
    raise ValueError("Нет GEMINI_API_KEY")
if not CHANNEL_ID:
    raise ValueError("Нет CHANNEL_ID")

POST_INTERVAL = 3 * 60 * 60
MAX_VACANCIES = 3
published_ids = set()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Публичные Telegram-каналы с вакансиями Киева
SOURCE_CHANNELS = [
    "kyivjob",
    "rabota_kiev_ua",
    "pidrobitok_kyiv",
    "workkiev",
    "vakansii_kiev",
]

# Ключевые слова для фильтрации вакансий подработки
KEYWORDS = [
    "різноробочий", "разнорабочий", "вантажник", "грузчик",
    "підсобний", "підробіток", "подработка", "підробіт",
    "будівництво", "склад", "прибирання", "розвантаження",
    "навантаження", "кур'єр", "промоутер", "охоронник",
]


async def fetch_channel_messages(channel_username: str) -> list:
    """Получаем последние сообщения из публичного канала через t.me/s/"""
    messages = []
    url = f"https://t.me/s/{channel_username}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "uk-UA,uk;q=0.9",
            }
            response = await client.get(url, headers=headers)
            logger.info(f"t.me/s/{channel_username} -> {response.status_code}")

            if response.status_code != 200:
                return messages

            html = response.text

            # Вытягиваем тексты сообщений и их ID
            # Ищем блоки сообщений
            msg_pattern = re.findall(
                r'data-post="[^/]+/(\d+)"[^>]*>.*?<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                html,
                re.DOTALL
            )

            for msg_id, msg_html in msg_pattern:
                # Чистим HTML теги
                text = re.sub(r'<[^>]+>', ' ', msg_html)
                text = re.sub(r'\s+', ' ', text).strip()
                text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#34;', '"')

                if len(text) < 20:
                    continue

                unique_id = f"{channel_username}_{msg_id}"
                if unique_id in published_ids:
                    continue

                messages.append({
                    "id": unique_id,
                    "text": text,
                    "link": f"https://t.me/{channel_username}/{msg_id}",
                    "channel": channel_username,
                })

    except Exception as e:
        logger.error(f"Помилка отримання {channel_username}: {e}")

    return messages


def is_vacancy(text: str) -> bool:
    """Проверяем содержит ли сообщение вакансию по ключевым словам"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)


def _format_vacancy_sync(text: str, link: str) -> str:
    prompt = f"""Перепиши це оголошення про роботу як короткий пост для Telegram-каналу підробітків у Києві.
Оригінал: {text[:500]}
Посилання на оригінал: {link}
Вимоги: українська мова, емодзі 💼🔨💰, до 100 слів, в кінці посилання на оригінал."""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        # Фолбек — постим оригинал обрезанный
        short = text[:300] + "..." if len(text) > 300 else text
        return f"💼 Вакансія\n\n{short}\n\n🔗 {link}"


async def format_vacancy(text: str, link: str) -> str:
    return await asyncio.to_thread(_format_vacancy_sync, text, link)


async def collect_and_post(bot):
    logger.info("🔍 Шукаємо вакансії в Telegram-каналах...")
    all_messages = []

    for channel in SOURCE_CHANNELS:
        msgs = await fetch_channel_messages(channel)
        # Фильтруем только вакансии
        vacancy_msgs = [m for m in msgs if is_vacancy(m["text"])]
        logger.info(f"@{channel}: {len(vacancy_msgs)} вакансій")
        all_messages.extend(vacancy_msgs)
        await asyncio.sleep(2)

    logger.info(f"Всього знайдено: {len(all_messages)} вакансій")

    if not all_messages:
        logger.warning("⚠️ Вакансій не знайдено")
        return

    published = 0
    for msg in all_messages:
        if published >= MAX_VACANCIES:
            break
        try:
            post_text = await format_vacancy(msg["text"], msg["link"])
            await bot.send_message(chat_id=CHANNEL_ID, text=post_text)
            published_ids.add(msg["id"])
            published += 1
            logger.info(f"✅ Опубліковано з @{msg['channel']}")
            await asyncio.sleep(5)
        except TelegramError as te:
            logger.error(f"❌ Telegram помилка: {te}")
        except Exception as e:
            logger.error(f"Помилка публікації: {e}")

    logger.info(f"📢 Опубліковано {published} вакансій")


async def scheduler(bot):
    await asyncio.sleep(10)
    while True:
        await collect_and_post(bot)
        logger.info(f"⏰ Наступний пост через {POST_INTERVAL // 3600} год.")
        await asyncio.sleep(POST_INTERVAL)


# ---------- COMMANDS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔨 Привіт! Я бот підробітків у Києві\n"
        "/post — опублікувати зараз\n"
        "/status — статус"
    )

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Шукаю вакансії...")
    await collect_and_post(context.bot)
    await update.message.reply_text("✅ Готово! Перевірте канал.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Канал: {CHANNEL_ID}\n"
        f"Час: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"Опубліковано постів: {len(published_ids)}"
    )

# ---------- MAIN ----------

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("status", status))

    async def on_start(app):
        asyncio.create_task(scheduler(app.bot))

    app.post_init = on_start

    logger.info("🚀 Бот запускається...")

    app.run_polling()

if __name__ == "__main__":
    main()

