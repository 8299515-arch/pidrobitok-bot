import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from telegram.error import TelegramError
import os
from dotenv import load_dotenv
import random
import google.generativeai as genai

# ---------- LOAD ENV ----------
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ---------- CONFIG ----------
POST_INTERVAL = 3 * 60 * 60
MAX_VACANCIES = 3
published_urls = set()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- GEMINI ----------
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ---------- USER AGENTS ----------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "uk-UA,ru;q=0.8,en-US;q=0.6",
    }

# ---------- FETCH ----------
async def fetch_html(url: str):
    try:
        async with httpx.AsyncClient(timeout=20, headers=get_headers()) as client:
            await asyncio.sleep(random.uniform(1, 2))
            r = await client.get(url)
            if r.status_code == 200:
                return r.text
    except Exception as e:
        logger.error(f"Fetch error: {e}")
    return None

# ---------- PARSER ----------
async def parse_work_ua():
    url = "https://www.work.ua/jobs-kyiv-різноробочий/"
    html = await fetch_html(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".job-link")

    vacancies = []

    for card in cards[:10]:
        try:
            title_el = card.select_one("h2")
            title = title_el.text.strip() if title_el else "Без назви"

            salary_el = card.select_one(".salary")
            salary = salary_el.text.strip() if salary_el else "Договірна"

            href = card.get("href")
            if not href:
                continue

            link = f"https://www.work.ua{href}"

            if link not in published_urls:
                vacancies.append({
                    "title": title,
                    "salary": salary,
                    "link": link
                })
        except:
            continue

    return vacancies

# ---------- AI FORMAT ----------
def ai_format_vacancy(v):
    if not GEMINI_API_KEY:
        return f"💼 {v['title']}\n💰 {v['salary']}\n🔗 {v['link']}"

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
Сделай короткий Telegram пост (до 80 слов).
Вакансия: {v['title']}
Зарплата: {v['salary']}
Добавь эмодзи 💼💰🔨
Ссылка: {v['link']}
Пиши на украинском.
"""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        logger.error(f"AI error: {e}")
        return f"💼 {v['title']}\n💰 {v['salary']}\n🔗 {v['link']}"

# ---------- POST ----------
async def collect_and_post(bot):
    vacancies = await parse_work_ua()

    if not vacancies:
        logger.warning("❌ No vacancies found")
        return

    count = 0

    for v in vacancies:
        if count >= MAX_VACANCIES:
            break

        try:
            text = ai_format_vacancy(v)
            await bot.send_message(chat_id=CHANNEL_ID, text=text)

            published_urls.add(v["link"])
            count += 1

            logger.info(f"Posted: {v['title']}")

            await asyncio.sleep(2)

        except TelegramError as e:
            logger.error(f"Telegram error: {e}")

# ---------- SCHEDULER ----------
async def scheduler(bot):
    await asyncio.sleep(5)

    while True:
        await collect_and_post(bot)
        logger.info("Waiting next cycle...")
        await asyncio.sleep(POST_INTERVAL)

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот активний!")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Шукаю вакансії...")
    await collect_and_post(context.bot)
    await update.message.reply_text("✅ Готово")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Опубліковано: {len(published_urls)}\n"
        f"⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )

# ---------- MAIN ----------
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("No TELEGRAM_TOKEN in .env")

    if not CHANNEL_ID:
        raise ValueError("No CHANNEL_ID in .env")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("status", status))

    async def on_start(app):
        logger.info("Bot started")
        asyncio.create_task(scheduler(app.bot))

    app.post_init = on_start

    app.run_polling()

if __name__ == "__main__":
    main()


   
