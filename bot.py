import os
import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- ENV ----------
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# ---------- CONFIG ----------
published_urls = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- KEYBOARD ----------
keyboard = ReplyKeyboardMarkup(
    [["🔍 Вакансии", "/post"]],
    resize_keyboard=True
)

# ---------- FETCH ----------
async def fetch_html(url):
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        return r.text if r.status_code == 200 else None

# ---------- PARSER ----------
async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-різноробочий/"
    html = await fetch_html(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    jobs = []

    for a in soup.find_all("a"):
        try:
            href = a.get("href", "")

            if "/jobs/" not in href:
                continue

            title = a.get_text(strip=True)

            if len(title) < 10:
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

# ---------- POST TO CHANNEL ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("TEXT RECEIVED:", update.message.text)

    await update.message.reply_text(f"📩 GOT: {update.message.text}")
    try:
        jobs = await parse_work()

        print("JOBS:", jobs)

        await update.message.reply_text(f"DEBUG: найдено {len(jobs)}")

        if not jobs:
            await update.message.reply_text("❌ вакансий нет")
            return

        for j in jobs[:3]:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"🔥 {j['title']}\n{j['link']}"
            )

        await update.message.reply_text("✅ DONE")

    except Exception as e:
        print("ERROR:", e)
        await update.message.reply_text(f"❌ ERROR: {e}")
        raise
# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен", reply_markup=keyboard)

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 ищу вакансии...")
    await collect_and_post(context)
    await update.message.reply_text("✅ готово")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Вакансии":
        await update.message.reply_text("🔍 ищу...")
        await collect_and_post(context)

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.ALL, handle_text))
    app.run_polling()


if __name__ == "__main__":
    main()
