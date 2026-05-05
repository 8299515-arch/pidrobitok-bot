import os
import asyncio
import logging
import random
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import TelegramError

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
        async with httpx.AsyncClient(timeout=20, headers=get_headers()) as client_http:
            r = await client_http.get(url)
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

    jobs = []

    for c in cards[:10]:
        try:
            title_el = c.select_one("h2")
            title = title_el.text.strip() if title_el else "Без назви"

            salary_el = c.select_one(".salary")
            salary = salary_el.text.strip() if salary_el else "Договірна"

            href = c.get("href")
            if not href:
                continue

            link = "https://www.work.ua" + href

            if link not in published_urls:
                jobs.append({
                    "title": title,
                    "salary": salary,
                    "link": link
                })
        except:
            continue

    return jobs

# ---------- AI SCORE ----------
def ai_score(job):
    try:
        prompt = f"""
Оцени вакансию от 0 до 10.

Критерии:
- зарплата
- адекватность
- полезность
- не скам

Вакансия:
{job['title']}
{job['salary']}
{job['link']}

Ответ:
score: X
"""

        res = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        text = res.text.lower()

        score = 0
        for line in text.split("\n"):
            if "score" in line:
                try:
                    score = int(''.join(filter(str.isdigit, line)))
                except:
                    score = 0

        return score

    except:
        return 0

# ---------- POST ----------
async def collect_and_post(bot):
    jobs = await parse_work()

    if not jobs:
        logger.warning("No jobs found")
        return

    # AI scoring
    for j in jobs:
        j["score"] = ai_score(j)

    # sort best first
    jobs.sort(key=lambda x: x["score"], reverse=True)

    count = 0

    for j in jobs:
        if count >= MAX_VACANCIES:
            break

        try:
            text = f"""
🔥 {j['title']}
💰 {j['salary']}
⭐ AI рейтинг: {j['score']}/10

🔗 {j['link']}
"""

            await bot.send_message(chat_id=CHANNEL_ID, text=text)

            published_urls.add(j["link"])
            count += 1

            await asyncio.sleep(2)

        except TelegramError as e:
            logger.error(e)

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 AI бот вакансий работает")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Ищу лучшие вакансии...")
    await collect_and_post(context.bot)
    await update.message.reply_text("✅ Готово")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Постов: {len(published_urls)}\n"
        f"⏰ {datetime.now()}"
    )

# ---------- SCHEDULER ----------
async def scheduler(app):
    await asyncio.sleep(5)

    while True:
        await collect_and_post(app.bot)
        await asyncio.sleep(POST_INTERVAL)

# ---------- MAIN ----------
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("NO TELEGRAM_TOKEN")

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

   
