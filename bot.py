import logging
import os
import random

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

# ----------------- ENV -----------------

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# ----------------- LOGGING -----------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- STATE -----------------

published_urls = set()

# ----------------- HTTP -----------------

USER_AGENTS = [
    "Mozilla/5.0 Chrome/124",
    "Mozilla/5.0 Safari/537.36",
]

def headers():
    return {"User-Agent": random.choice(USER_AGENTS)}

async def fetch(url):
    async with httpx.AsyncClient(timeout=20, headers=headers()) as client:
        r = await client.get(url)
        return r.text if r.status_code == 200 else None

# ----------------- PARSER -----------------

async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%BE%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/"
    html = await fetch(url)

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
            "link": link
        })

    return jobs

# ----------------- COMMANDS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот работает")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🔥 POST CALLED")

    await update.message.reply_text("🚀 /post активирован")

    jobs = await parse_work()

    await update.message.reply_text(f"📊 найдено: {len(jobs)}")

    if not jobs:
        await update.message.reply_text("❌ вакансий нет")
        return

    for j in jobs[:3]:
        text = f"💼 {j['title']}\n🔗 {j['link']}"

        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=text
        )

        published_urls.add(j["link"])

    await update.message.reply_text("✅ DONE")

# 🔥 ВАЖНО — ОТЛАДКА
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 TEXT:", update.message.text)
    await update.message.reply_text(f"Ты написал: {update.message.text}")

# ----------------- MAIN -----------------

def main():
    print("🔥 BOT FILE LOADED")

    if not TELEGRAM_TOKEN:
        raise ValueError("NO TELEGRAM_TOKEN")
    if not CHANNEL_ID:
        raise ValueError("NO CHANNEL_ID")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("post", post), group=0)
    app.add_handler(CommandHandler("start", start), group=0)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text), group=1)

    print("🚀 STARTING BOT...")

    while True:
        try:
            app.run_polling()
        except Exception as e:
            print("❌ ERROR:", e)
            print("🔄 RESTARTING BOT...")
   
