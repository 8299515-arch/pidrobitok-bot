import os
import asyncio
import logging
import random
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import TelegramError

# ---------- LOAD ENV ----------
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

# ---------- GEMINI ----------
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ---------- HEADERS ----------
USER_AGENTS = [
    "Mozilla/5.0 Chrome/124.0",
    "Mozilla/5.0 Safari/537.36",
]

def get_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}

# ---------- FETCH ----------
async def fetch_html(url):
    try:
        async with httpx.AsyncClient(timeout=20, headers=get_headers()) as client:
            r = await client.get(url)
            return r.text if r.status_code == 200 else None
    except Exception as e:
        logger.error(e)
        return None

# ---------- PARSER ----------
async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-різноробочий/"
    html = await fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".job-link")

    results = []

    for c in cards[:10]:
        try:
            title_el = c.select_one("h2")
            title = title_el.text.strip() if title_el else "Без назви"

            salary_el = c.select_one(".salary")
            salary = salary_el.text.strip() if salary_el else "Договірна"

            link = "https://www.work.ua" + c.get("href")

            if link not in published_urls:
                results.append({
                    "title": title,
                    "salary": salary,
                    "link": link
                })
        except:
            continue

    return results

# ---------- AI ----------
def format_vacancy(v):
    if not GEMINI_API_KEY:
        return f"💼 {v['title']}\n💰 {v['salary']}\n🔗 {v['link']}"

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
Короткий пост Telegram (до 80 слов)
Вакансия: {v['title']}
Зарплата: {v['salary']}
Ссылка: {v['link']}
Украинский язык, эмодзи 💼💰🔨
"""

        res = model.generate_content(prompt)
        return res.text.strip()

    except:
        return f"💼 {v['title']}\n💰 {v['salary']}\n🔗 {v['link']}"

# ---------- POST ----------
async def post_vacancies(bot):
    jobs = await parse_work()

    for i, v in enumerate(jobs[:MAX_VACANCIES]):
        try:
            text = format_vacancy(v)
            await bot.send_message(chat_id=CHANNEL_ID, text=text)

            published_urls.add(v["link"])
            await asyncio.sleep(2)

        except TelegramError as e:
            logger.error(e)

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот працює!")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Шукаю...")
    await post_vacancies(context.bot)
    await update.message.reply_text("✅ Готово")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Опубліковано: {len(published_urls)}\n"
        f"⏰ {datetime.now()}"
    )

# ---------- SCHEDULER ----------
async def scheduler(app):
    await asyncio.sleep(5)
    while True:
        await post_vacancies(app.bot)
        await asyncio.sleep(POST_INTERVAL)

# ---------- MAIN ----------
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("NO TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("status", status))

    async def on_start(app):
        asyncio.create_task(scheduler(app))

    app.post_init = on_start

    app.run_polling()

if __name__ == "__main__":
    main()
   
