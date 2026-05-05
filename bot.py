import os
import logging
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

# ----------------- INIT -----------------

print("🔥 SCRIPT STARTED")

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

published_urls = set()

# ----------------- HTTP -----------------

async def fetch(url):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        return r.text if r.status_code == 200 else None

# ----------------- PARSER -----------------

async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%BE%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/"
    html = await fetch(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    jobs = []

    for a in soup.find_all("a"):
        title = a.get_text(strip=True)
        href = a.get("href")

        if not title or not href:
            continue

        if "/jobs/" not in href:
            continue

        if len(title) < 10:
            continue

        link = "https://www.work.ua" + href

        if link in published_urls:
            continue

        jobs.append({
            "title": title,
            "link": link
        })

    return jobs[:10]

# ----------------- HANDLERS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start")
    await update.message.reply_text("🤖 Бот работает")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /post")

    jobs = await parse_work()

    # 🔥 DEBUG
    await update.message.reply_text(f"DEBUG: {jobs}")

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

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 TEXT:", update.message.text)

# ----------------- MAIN -----------------

def main():
    print("🚀 ENTER MAIN")

    if not TELEGRAM_TOKEN:
        print("❌ NO TELEGRAM_TOKEN")
        return

    print("✅ TOKEN OK")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🚀 START POLLING")

    app.run_polling()

if __name__ == "__main__":
    main()
   
