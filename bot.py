import os
import json
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

SEEN_FILE = "seen.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- MEMORY ----------------

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# ---------------- HTTP ----------------

async def fetch(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,uk;q=0.8,en-US;q=0.7"
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
        if a:
            jobs.append({
                "title": a.get_text(strip=True),
                "link": "https://www.work.ua" + a.get("href")
            })

    if not jobs:
        links = soup.select("a[href*='/jobs/']")

        for a in links:
            title = a.get_text(strip=True)
            href = a.get("href")

            if not title or len(title) < 10:
                continue

            jobs.append({
                "title": title,
                "link": "https://www.work.ua" + href
            })

    return jobs[:10]

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start")
    await update.message.reply_text("🤖 Бот работает")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /post")

    jobs = await parse_work()
    seen = load_seen()

    new_jobs = []

    for j in jobs:
        if j["link"] in seen:
            continue
        new_jobs.append(j)
        seen.add(j["link"])

    save_seen(seen)

    await update.message.reply_text(f"📊 новых: {len(new_jobs)}")

    if not new_jobs:
        await update.message.reply_text("❌ новых вакансий нет")
        return

    for j in new_jobs[:3]:
        text = f"💼 {j['title']}\n🔗 {j['link']}"

        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=text
        )

async def auto_post(context: ContextTypes.DEFAULT_TYPE):
    jobs = await parse_work()
    seen = load_seen()

    for j in jobs:
        if j["link"] in seen:
            continue

        seen.add(j["link"])

        text = f"💼 {j['title']}\n🔗 {j['link']}"

        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=text
        )

    save_seen(seen)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 TEXT:", update.message.text)

# ---------------- MAIN ----------------

def main():
    print("🚀 STARTING BOT...")

    if not TELEGRAM_TOKEN:
        print("❌ NO TELEGRAM_TOKEN")
        return

    if not CHANNEL_ID:
        print("❌ NO CHANNEL_ID")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # 🔥 AUTO POSTING каждые 5 минут
    app.job_queue.run_repeating(auto_post, interval=300, first=10)

    print("✅ BOT READY")

    app.run_polling(drop_pending_updates=True)

# ---------------- RUN ----------------

if __name__ == "__main__":
    main()
