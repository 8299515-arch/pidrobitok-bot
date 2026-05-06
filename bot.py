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

print("🔥 BOT FILE LOADED (V2)")

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
        "User-Agent": "Mozilla/5.0"
    }

    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        r = await client.get(url)
        return r.text if r.status_code == 200 else None

# ---------------- SOURCES ----------------

async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%BE%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/"
    html = await fetch(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    jobs = []

    for a in soup.select("a"):
        title = a.get_text(strip=True)
        href = a.get("href")

        if not title or not href:
            continue

        if len(title) < 10:
            continue

        if "work.ua" not in href:
            href = "https://www.work.ua" + href

        jobs.append({
            "title": title,
            "link": href,
            "source": "work"
        })

    return jobs[:10]

async def parse_olx():
    url = "https://www.olx.ua/uk/rabota/"
    html = await fetch(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    jobs = []

    for a in soup.select("a"):
        title = a.get_text(strip=True)
        href = a.get("href")

        if not title or not href:
            continue

        if len(title) < 10:
            continue

        if "olx.ua" not in href:
            href = "https://www.olx.ua" + href

        jobs.append({
            "title": title,
            "link": href,
            "source": "olx"
        })

    return jobs[:10]

# ---------------- AI LOGIC ----------------

def classify_job(title):
    t = title.lower()

    bad = ["курс", "обуч", "инвест", "crypto", "заработок", "обучение"]
    if any(x in t for x in bad):
        return "bad"

    if any(x in t for x in ["склад", "груз", "разнораб"]):
        return "warehouse"

    if any(x in t for x in ["водитель", "курьер", "доставка"]):
        return "courier"

    if any(x in t for x in ["офис", "менеджер", "админ"]):
        return "office"

    if any(x in t for x in ["строит", "ремонт"]):
        return "construction"

    return "other"

def filter_jobs(jobs):
    result = []

    for j in jobs:
        cat = classify_job(j["title"])

        if cat == "bad":
            continue

        j["category"] = cat
        result.append(j)

    return result

# ---------------- RERAISE TEXT ----------------

async def rewrite_job(job):
    return f"""
💼 {job['title']}

📂 Категория: {job.get('category', 'other')}

Мы нашли свежую вакансию для тебя.

📍 Киев
💰 Условия обсуждаются напрямую с работодателем

🧑‍💼 Как связаться:
Открой оригинальное объявление и напиши работодателю.
"""

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start")
    await update.message.reply_text("🤖 V2 бот работает")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /post V2")

    work = await parse_work()
    olx = await parse_olx()

    jobs = filter_jobs(work + olx)

    seen = load_seen()
    new_jobs = []

    for j in jobs:
        if j["link"] in seen:
            continue
        new_jobs.append(j)
        seen.add(j["link"])

    save_seen(seen)

    await update.message.reply_text(f"📊 V2 найдено: {len(new_jobs)}")

    for j in new_jobs[:3]:
        text = await rewrite_job(j)

        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=text
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 TEXT:", update.message.text)

# ---------------- MAIN ----------------

def main():
    print("🚀 STARTING V2 BOT...")

    if not TELEGRAM_TOKEN:
        print("❌ NO TOKEN")
        return

    if not CHANNEL_ID:
        print("❌ NO CHANNEL")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ V2 READY")

    app.run_polling(drop_pending_updates=True)

# ---------------- RUN ----------------

if __name__ == "__main__":
    main()
 
