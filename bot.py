import os
import sqlite3
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

print("🚀 V12.1 AI JOBS STARTED")

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

# ---------------- DATABASE ----------------

conn = sqlite3.connect("v12.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY,
premium INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT,
boost INTEGER DEFAULT 0,
price INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS apps (
id INTEGER PRIMARY KEY AUTOINCREMENT,
job_id INTEGER,
user_id INTEGER
)
""")

conn.commit()

# ---------------- SIMPLE AI REWRITE ----------------

def ai_rewrite(text: str) -> str:
    """
    Лёгкий 'AI-стиль' без API:
    превращает сырой текст в HR-описание
    """

    t = text.lower()

    city = ""
    if "киев" in t or "київ" in t:
        city = "📍 Киев"

    if "продавец" in t:
        role = "🛒 Продавец-консультант"
    elif "водитель" in t:
        role = "🚗 Водитель"
    elif "офис" in t:
        role = "🏢 Офисный сотрудник"
    else:
        role = "💼 Специалист"

    schedule = ""
    if "5/2" in t:
        schedule = "⏰ График: 5/2"

    return f"""
{role}

{city}

📌 Описание:
{text.capitalize()}

{schedule}

🤝 Требования: базовые навыки и ответственность
💬 Формат: работа с работодателем напрямую
"""

# ---------------- HELPERS ----------------

def add_job(title):
    cur.execute(
        "INSERT INTO jobs (title, boost, price) VALUES (?, 0, 0)",
        (title,)
    )
    conn.commit()

def get_jobs():
    cur.execute("SELECT * FROM jobs ORDER BY id DESC")
    return cur.fetchall()

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V12.1 AI JOB PLATFORM\n\n"
        "/jobs — вакансии\n"
        "/postjob текст — добавить\n"
    )

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("❌ Введите текст вакансии")
        return

    add_job(text)

    await update.message.reply_text("🏢 Вакансия добавлена (AI формат включится в /jobs)")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs()

    if not jobs:
        await update.message.reply_text("📭 Нет вакансий")
        return

    for j in jobs[:5]:
        raw = j[1]
        pretty = ai_rewrite(raw)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Отклик", callback_data=f"apply_{j[0]}")]
        ])

        await update.message.reply_text(pretty, reply_markup=keyboard)

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text("📩 Отклик отправлен работодателю")

# ---------------- MAIN ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("jobs", jobs))
    app.add_handler(CommandHandler("postjob", postjob))

    app.add_handler(CallbackQueryHandler(callback))

    print("✅ V12.1 READY (AI REWRITE ENABLED)")

    app.run_polling()

if __name__ == "__main__":
    main()
