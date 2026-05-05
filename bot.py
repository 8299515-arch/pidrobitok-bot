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
MAX_VACANCIES = 3
published_urls = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- AI ----------
client = genai.Client(api_key=GEMINI_API_KEY)

# ---------- KEYBOARD ----------
keyboard = ReplyKeyboardMarkup(
    [["🔍 Вакансии"], ["📊 Статус"]],
    resize_keyboard=True
)

# ---------- HEADERS ----------
USER_AGENTS = [
    "Mozilla/5.0 Chrome/124.0",
    "Mozilla/5.0 Safari/537.36",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "uk-UA,ru;q=0.9,en;q=0.8",
    }

# ---------- FETCH ----------
async def fetch_html(url):
    try:
        async with httpx.AsyncClient(timeout=20, headers=get_headers()) as client_http:
            await asyncio.sleep(random.uniform(1.5, 3))
            r = await client_http.get(url)
            return r.text if r.status_code == 200 else None
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return None

# ---------- WORK.UA PARSER ----------
async def parse_work():
    url = "https://www.work.ua/jobs-kyiv-різноробочий/"
    html = await fetch_html(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    # устойчивый селектор
    cards = soup.select("div.card")

    jobs = []

    for card in cards[:15]:
        try:
            title_tag = card.select_one("h2, h3")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)

            a_tag = card.select_one("a")
            if not a_tag or not a_tag.get("href"):
                continue

            link = "https://www.work.ua" + a_tag["href"]

            salary_tag = card.select_one(".salary, .text-nowrap")
            salary = salary_tag.get_text(strip=True) if salary_tag else "Договірна"

            if link not in published_urls:
                jobs.append({
                    "title": title,
                    "salary": salary,
                    "link": link
                })

        except Exception as e:
            logger.error(f"Parse error: {e}")

    return jobs

# ---------- AI SCORE ----------
def ai_score(job):
    try:
        prompt = f"""
Оцени вакансию от 0 до 10.
Учитывай:
- зарплату
- адекватность
- пользу

{job['title']}
{job['salary']}

Ответ:
score: X
"""

        res = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        text = res.text.lower()

        for line in text.split("\n"):
            if "score" in line:
                try:
                    return int(''.join(filter(str.isdigit, line)))
                except:
                    return 0

        return 0

    except Exception as e:
        logger.error(f"AI error: {e}")
        return 0

# ---------- CORE LOGIC ----------
async def collect_jobs():
    jobs = await parse_work()

    for j in jobs:
        j["score"] = ai_score(j)

    jobs.sort(key=lambda x: x["score"], reverse=True)
    return jobs

# ---------- POST ----------
async def collect_and_post(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot

    jobs = await collect_jobs()

    if not jobs:
        logger.warning("No jobs found")
        return

    count = 0

    for j in jobs:
        if count >= MAX_VACANCIES:
            break

        text = f"""
🔥 {j['title']}
💰 {j['salary']}
⭐ AI: {j['score']}/10

🔗 {j['link']}
"""

        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=text)
            published_urls.add(j["link"])
            count += 1
        except Exception as e:
            logger.error(f"Send error: {e}")

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Бот вакансий активен",
        reply_markup=keyboard
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Вакансий отправлено: {len(published_urls)}\n⏰ {datetime.now()}"
    )

# ---------- BUTTONS ----------
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Вакансии":
        await update.message.reply_text("🔍 Ищу лучшие вакансии...")
        await collect_and_post(context)
        await update.message.reply_text("✅ Готово")

    elif text == "📊 Статус":
        await status(update, context)

# ---------- MAIN ----------
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("NO TELEGRAM_TOKEN")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # защита от конфликтов
    app.bot.delete_webhook(drop_pending_updates=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    # стабильный автопостинг
    app.job_queue.run_repeating(
        collect_and_post,
        interval=POST_INTERVAL,
        first=10
    )

    logger.info("🚀 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
