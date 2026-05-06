import os
import logging

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

# ---------------- INIT ----------------

print("🔥 BOT FILE LOADED")

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- HTTP ----------------
async def fetch(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,uk;q=0.8,en-US;q=0.7,en;q=0.6"
    }

    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        r = await client.get(url)
        return r.text if r.status_code == 200 else None


# ---------------- PARSER ----------------
async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%BE%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/"
    html = await fetch(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    jobs = []

    cards = soup.select("div.job-link")

    for c in cards:
        a = c.find("a")
        if not a:
            continue

        title = a.get_text(strip=True)
        link = "https://www.work.ua" + a.get("href")

        jobs.append({
            "title": title,
            "link": link
        })

    return jobs[:10]

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start")
    await update.message.reply_text("🤖 Бот работает")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /post")

    jobs = await parse_work()

    await update.message.reply_text(f"📊 найдено: {len(jobs)}")

    if not jobs:
        await update.message.reply_text("❌ вакансий нет")
        return

    for j in jobs[:3]:
        text = f"💼 {j['title']}\n🔗 {j['link']}"
        await update.message.reply_text(text)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 TEXT:", update.message.text)

# ---------------- MAIN ----------------

def main():
    print("🚀 STARTING BOT...")

    if not TELEGRAM_TOKEN:
        print("❌ NO TOKEN")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ BOT READY")

    app.run_polling(drop_pending_updates=True)

# ---------------- RUN ----------------

if __name__ == "__main__":
    main()
   
   
