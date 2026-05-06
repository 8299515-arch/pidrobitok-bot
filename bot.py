import os
import sqlite3
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

pip install google-genai

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ======================
# ENV
# ======================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
print("TOKEN:", BOT_TOKEN)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ======================
# DB (резерв, можно расширять)
# ======================
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT
)
""")

conn.commit()

# ======================
# KEYBOARD
# ======================
keyboard = ReplyKeyboardMarkup(
    [
        ["📍 Киев вакансии", "💰 Вакансии 1500+"],
        ["🤖 AI HR"]
    ],
    resize_keyboard=True
)

# ======================
# AI HR / CHAT
# ======================
def ask_ai(text: str):
    res = model.generate_content(text)
    return res.text

def hr_analyze(vacancy: str, profile: str):
    prompt = f"""
Ты HR эксперт.

Вакансия: {vacancy}
Кандидат: {profile}

Ответ:
- подходит ли (да/нет)
- почему
- советы
"""
    res = model.generate_content(prompt)
    return res.text

# ======================
# SIMPLE SCRAPER (Kyiv jobs)
# ======================
def get_jobs(query="python kyiv"):
    try:
        url = f"https://robota.ua/zapros/{query.replace(' ', '-')}"
        headers = {"User-Agent": "Mozilla/5.0"}

        r = httpx.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        jobs = []

        for item in soup.select("article"):
            title = item.select_one("h2")
            if title:
                jobs.append(title.text.strip())

        return jobs[:8]

    except:
        return ["Ошибка загрузки вакансий 😢"]

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V4 PRO HR BOT\n\n"
        "📍 Киев вакансии\n"
        "💰 зарплата 1500+\n"
        "🤖 AI HR",
        reply_markup=keyboard
    )

# ======================
# KYIV JOBS
# ======================
async def kyiv_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs("kyiv python")

    text = "📍 Вакансии Киев:\n\n"
    for j in jobs:
        text += f"• {j}\n"

    await update.message.reply_text(text)

# ======================
# SALARY FILTER (упрощённый MVP)
# ======================
async def salary_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs("kyiv")

    text = "💰 Вакансии (1500+):\n\n"
    for j in jobs:
        text += f"• {j}\n"

    await update.message.reply_text(text)

# ======================
# AI HR FLOW
# ======================
user_profile = {}

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    # Кнопки
    if text == "📍 Киев вакансии":
        await kyiv_jobs(update, context)
        return

    if text == "💰 Вакансии 1500+":
        await salary_jobs(update, context)
        return

    if text == "🤖 AI HR":
        user_profile[user_id] = "waiting"
        await update.message.reply_text("Напиши: опыт + навыки 👇")
        return

    # HR режим
    if user_profile.get(user_id) == "waiting":
        user_profile[user_id] = text

        jobs = get_jobs("python kyiv")

        result = "🤖 HR анализ:\n\n"

        for j in jobs[:3]:
            result += f"📌 {j}\n"
            result += hr_analyze(j, text)
            result += "\n\n"

        await update.message.reply_text(result)
        return

    # обычный AI чат
    answer = ask_ai(text)
    await update.message.reply_text(answer)

# ======================
# MAIN
# ======================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    print("🚀 V4 PRO RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
