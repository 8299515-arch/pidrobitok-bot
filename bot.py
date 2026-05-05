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
published_urls = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- AI ----------
client = genai.Client(api_key=GEMINI_API_KEY)

# ---------- KEYBOARD ----------
keyboard = ReplyKeyboardMarkup(
    [["🔍 Вакансии", "🧪 TEST"]],
    resize_keyboard=True
)

# ---------- FETCH ----------
async def fetch_html(url):
    async with httpx.AsyncClient(timeout=20) as client_http:
        r = await client_http.get(url)
        return r.text if r.status_code == 200 else None

# ---------- SIMPLE TEST SEND ----------
async def test_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text="🧪 TEST MESSAGE: бот работает"
        )
        await update.message.reply_text("✅ TEST отправлен в канал")
    except Exception as e:
        await update.message.reply_text(f"❌ ERROR: {e}")
        logger.error(e)

# ---------- PARSER (упрощённый) ----------
async def parse_work():
    url = "https://www.work.ua/jobs-kyiv/"
    html = await fetch_html(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    jobs = []

    # берём ВСЕ ссылки
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
# ---------- POST ----------
async def collect_and_post(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    jobs = await parse_work()

    for j in jobs[:3]:
        text = f"""
🔥 {j['title']}
💰 {j['salary']}
🔗 {j['link']}
"""

        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
            published_urls.add(j["link"])
        except Exception as e:
            logger.error(e)

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот работает", reply_markup=keyboard)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🧪 TEST":
        await test_send(update, context)

    elif text == "🔍 Вакансии":
        await update.message.reply_text("🔍 ищу...")
        await collect_and_post(context)

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.bot.delete_webhook(drop_pending_updates=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    app.run_polling()

if __name__ == "__main__":
    main()
