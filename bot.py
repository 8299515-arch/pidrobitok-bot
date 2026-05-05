import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from google import genai
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from telegram.error import TelegramError
import os
from dotenv import load_dotenv
import random

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
published_urls = set()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "uk-UA,ru;q=0.8,en-US;q=0.6",
    }

async def fetch_html(url: str):
    try:
        async with httpx.AsyncClient(timeout=20, headers=get_headers()) as client:
            await asyncio.sleep(random.uniform(1, 3))
            response = await client.get(url)
            if response.status_code == 200:
                return response.text
    except Exception as e:
        logger.error(f"Fetch error: {e}")
    return None

async def parse_work_ua():
    vacancies = []
    url = "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%BE%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/"
    html = await fetch_html(url)
    if not html:
        return vacancies

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".job-link")

    for card in cards[:10]:
        try:
            title = card.select_one("h2").text.strip()
            salary = card.select_one(".salary").text.strip() if card.select_one(".salary") else "Договірна"
            href = card.get("href")
            link = f"https://www.work.ua{href}"

            if link not in published_urls:
                vacancies.append({"title": title, "salary": salary, "link": link})
        except:
            pass

    return vacancies

def format_vacancy(v):
    return f"💼 {v['title']}\n💰 {v['salary']}\n🔗 {v['link']}"

async def collect_and_post(bot):
    vacancies = await parse_work_ua()

    if not vacancies:
        logger.warning("Нет вакансий")
        return

    count = 0
    for v in vacancies:
        if count >= MAX_VACANCIES:
            break
        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=format_vacancy(v))
            published_urls.add(v["link"])
            count += 1
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(e)

async def scheduler(bot):
    await asyncio.sleep(10)
    while True:
        await collect_and_post(bot)
        await asyncio.sleep(POST_INTERVAL)

# ---------- COMMANDS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот вакансий 🔨")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Публикую...")
    await collect_and_post(context.bot)
    await update.message.reply_text("Готово")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Опубликовано: {len(published_urls)}")

# ---------- MAIN ----------

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("status", status))

    async def on_start(app):
        asyncio.create_task(scheduler(app.bot))

    app.post_init = on_start

    logger.info("🚀 Бот запускается...")

    app.run_polling()

if __name__ == "__main__":
    main()

