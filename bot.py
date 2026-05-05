import os
import asyncio
import logging
import random
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from google import genai

# ---------- ENV ----------
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ---------- CONFIG ----------
POST_INTERVAL = 3 * 60 * 60
MAX_VACANCIES = 3
published_urls = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- AI ----------
client = genai.Client(api_key=GEMINI_API_KEY)

# ---------- KEYBOARD ----------
keyboard = ReplyKeyboardMarkup(
    [["🔍 Вакансии"], ["📊 Статус"]],
    resize_keyboard=True
)

# ---------- HEADERS ----------
USER_AGENTS = [
    "Mozilla/5.0 Chrome/124.0",
    "Mozilla/5.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "uk-UA,ru;q=0.9,en;q=0.8",
    }

# ---------- FETCH ----------
async def fetch_html(url):
    try:
        async with httpx.AsyncClient(timeout=20, headers=get_headers()) as client_http:
            await asyncio.sleep(random.uniform(1.5, 3))
            r = await client_http.get(url)
            return r.text if r.status_code == 200 else None
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return None

# ---------- WORK.UA PARSER ----------
async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%BE%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/"
    html = await fetch_html(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    # 🔥 новый более живой селектор
    cards = soup.select("a[href*='/jobs/']")

    jobs = []

    for c in cards[:20]:
        try:
            title = c.get_text(strip=True)

            href = c.get("href")
            if not href or "/jobs/" not in href:
                continue

            link = "https://www.work.ua" + href

            if link in published_urls:
                continue

            jobs.append({
                "title": title,
                "salary": "—",
                "link": link
            })

        except:
            continue

    return jobs
        )

    
# ---------- POST ----------
async def collect_and_post(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot

    jobs = await collect_jobs()

    if not jobs:
        logger.warning("No jobs found")
        return

    count = 0

    for j in jobs:
        if count >= MAX_VACANCIES:
            break

        text = f"""
🔥 {j['title']}
💰 {j['salary']}
⭐ AI: {j['score']}/10

🔗 {j['link']}
"""

        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
            published_urls.add(j["link"])
            count += 1
        except Exception as e:
            logger.error(f"Send error: {e}")

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Бот вакансий активен",
        reply_markup=keyboard
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Вакансий отправлено: {len(published_urls)}\n⏰ {datetime.now()}"
    )

# ---------- BUTTONS ----------
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Вакансии":
        await update.message.reply_text("🔍 Ищу лучшие вакансии...")
        await collect_and_post(context)
        await update.message.reply_text("✅ Готово")

    elif text == "📊 Статус":
        await status(update, context)

# ---------- MAIN ----------
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("NO TELEGRAM_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # защита от конфликтов
    app.bot.delete_webhook(drop_pending_updates=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    # стабильный автопостинг
    app.job_queue.run_repeating(
        collect_and_post,
        interval=POST_INTERVAL,
        first=10
    )

    logger.info("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
