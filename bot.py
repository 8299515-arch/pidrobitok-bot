import asyncio
import logging
import os
import random
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ----------------- LOAD ENV -----------------

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ----------------- CONFIG -----------------

POST_INTERVAL = 3 * 60 * 60
MAX_VACANCIES = 3
published_urls = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- HEADERS -----------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/124",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "uk-UA,ru;q=0.8,en-US;q=0.6",
    }

# ----------------- FETCH -----------------

async def fetch_html(url: str):
    try:
        async with httpx.AsyncClient(timeout=20, headers=get_headers()) as client:
            r = await client.get(url)
            return r.text if r.status_code == 200 else None
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return None

# ----------------- PARSER (WORK.UA FIXED) -----------------

async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%BE%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/"
    html = await fetch_html(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select("a[href*='/jobs/']")

    jobs = []

    for c in cards[:20]:
        title = c.get_text(strip=True)
        href = c.get("href")

        if not href:
            continue

        link = "https://www.work.ua" + href

        if link in published_urls:
            continue

        if len(title) < 5:
            continue

        jobs.append({
            "title": title,
            "salary": "—",
            "link": link
        })

    return jobs

# ----------------- FORMAT -----------------

def format_job(v):
    return (
        f"💼 {v['title']}\n"
        f"💰 {v['salary']}\n"
        f"🔗 {v['link']}"
    )

# ----------------- POST -----------------

async def collect_and_post(bot):
    jobs = await parse_work()

    if not jobs:
        logger.warning("No jobs found")
        return

    count = 0

    for j in jobs:
        if count >= MAX_VACANCIES:
            break

        try:
            text = format_job(j)

            await bot.send_message(chat_id=CHANNEL_ID, text=text)

            published_urls.add(j["link"])
            count += 1

            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Telegram error: {e}")

# ----------------- SCHEDULER -----------------

async def scheduler(bot):
    await asyncio.sleep(5)

    while True:
        await collect_and_post(bot)
        await asyncio.sleep(POST_INTERVAL)

# ----------------- COMMANDS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔨 Бот работает")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("POST CALLED")

    await update.message.reply_text("🚀 /post работает")

    jobs = await parse_work()

    await update.message.reply_text(f"DEBUG: найдено {len(jobs)}")

    if not jobs:
        await update.message.reply_text("❌ пусто")
        return

    for j in jobs[:3]:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=format_job(j)
        )

    await update.message.reply_text("✅ DONE")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("TEXT:", update.message.text)
    await update.message.reply_text(f"📩 {update.message.text}")

# ----------------- MAIN -----------------

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("No TELEGRAM_TOKEN")
    if not CHANNEL_ID:
        raise ValueError("No CHANNEL_ID")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # scheduler
    asyncio.get_event_loop().create_task(scheduler(app.bot))

    app.run_polling()

if __name__ == "__main__":
    main()
