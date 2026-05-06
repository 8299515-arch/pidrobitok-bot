import os
import sqlite3
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from google import genai

# ======================
# ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ======================
# AI CLIENT
# ======================
client = genai.Client(api_key=GOOGLE_API_KEY)

def ask_ai(text: str):
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=text
    )
    return response.text

# ======================
# DB (простая база вакансий)
# ======================
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    salary INTEGER
)
""")

# тестовые данные (если пусто)
cur.execute("SELECT COUNT(*) FROM jobs")
if cur.fetchone()[0] == 0:
    cur.executemany("""
        INSERT INTO jobs (title, salary)
        VALUES (?, ?)
    """, [
        ("Python Developer", 1500),
        ("Django Developer", 2000),
        ("Frontend React", 1800),
        ("QA Engineer", 1200),
        ("DevOps Engineer", 2500),
    ])
    conn.commit()

# ======================
# KEYBOARD
# ======================
keyboard = ReplyKeyboardMarkup(
    [
        ["📌 Вакансии", "💰 Вакансии 1500+"],
        ["🤖 AI помощник"]
    ],
    resize_keyboard=True
)

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я Job Bot V3\n\n"
        "📌 Вакансии\n"
        "💰 Фильтр зарплат\n"
        "🤖 AI помощник",
        reply_markup=keyboard
    )

# ======================
# VACANCIES
# ======================
async def show_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT title, salary FROM jobs")
    jobs = cur.fetchall()

    text = "📌 Все вакансии:\n\n"
    for j in jobs:
        text += f"• {j[0]} — ${j[1]}\n"

    await update.message.reply_text(text)

# ======================
# FILTER 1500+
# ======================
async def jobs_1500(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT title, salary FROM jobs WHERE salary >= 1500")
    jobs = cur.fetchall()

    text = "💰 Вакансии от $1500:\n\n"
    for j in jobs:
        text += f"• {j[0]} — ${j[1]}\n"

    await update.message.reply_text(text)

# ======================
# AI CHAT
# ======================
async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    answer = ask_ai(user_text)

    await update.message.reply_text(answer)

# ======================
# ROUTER
# ======================
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📌 Вакансии":
        await show_jobs(update, context)

    elif text == "💰 Вакансии 1500+":
        await jobs_1500(update, context)

    elif text == "🤖 AI помощник":
        await update.message.reply_text("Напиши вопрос 👇")

    else:
        await ai_handler(update, context)

# ======================
# MAIN
# ======================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    print("🚀 V3 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
