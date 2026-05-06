import os
import sys
import sqlite3
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

print("🚀 V12.3 SAFE STARTED")

# ---------------- LOCK SYSTEM ----------------

LOCK_FILE = "bot.lock"

if os.path.exists(LOCK_FILE):
    print("⛔ BOT ALREADY RUNNING (LOCK ACTIVE)")
    sys.exit()

with open(LOCK_FILE, "w") as f:
    f.write("running")

print("🔒 LOCK CREATED")

# ---------------- ENV ----------------

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ---------------- DB ----------------

conn = sqlite3.connect("v12.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS chats (
id INTEGER PRIMARY KEY AUTOINCREMENT,
job_id INTEGER,
candidate_id INTEGER,
employer_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
id INTEGER PRIMARY KEY AUTOINCREMENT,
chat_id INTEGER,
sender_id INTEGER,
text TEXT
)
""")

conn.commit()

# ---------------- HELPERS ----------------

def add_job(title):
    cur.execute("INSERT INTO jobs (title) VALUES (?)", (title,))
    conn.commit()

def get_jobs():
    cur.execute("SELECT * FROM jobs ORDER BY id DESC")
    return cur.fetchall()

def get_chat(user_id):
    cur.execute("""
        SELECT id, candidate_id, employer_id FROM chats
        WHERE candidate_id=? OR employer_id=?
        ORDER BY id DESC LIMIT 1
    """, (user_id, user_id))
    return cur.fetchone()

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V12.3 SAFE BOT\n\n"
        "/jobs — вакансии\n"
        "/postjob текст — добавить вакансию"
    )

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("❌ Введите текст")
        return

    add_job(text)

    await update.message.reply_text("🏢 Вакансия добавлена")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs()

    if not jobs:
        await update.message.reply_text("📭 Нет вакансий")
        return

    for j in jobs:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Отклик", callback_data=f"apply_{j[0]}")]
        ])

        await update.message.reply_text(f"💼 {j[1]}", reply_markup=keyboard)

# ---------------- CHAT CREATE ----------------

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    job_id = int(q.data.replace("apply_", ""))
    candidate_id = q.from_user.id

    cur.execute("""
        INSERT INTO chats (job_id, candidate_id, employer_id)
        VALUES (?, ?, ?)
    """, (job_id, candidate_id, 0))

    conn.commit()

    await q.message.reply_text("💬 Чат создан. Пишите сообщение.")

# ---------------- MESSAGE ROUTING ----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    chat = get_chat(user_id)

    if not chat:
        return

    chat_id, candidate_id, employer_id = chat

    cur.execute("""
        INSERT INTO messages (chat_id, sender_id, text)
        VALUES (?, ?, ?)
    """, (chat_id, user_id, text))

    conn.commit()

    await update.message.reply_text("📨 Сообщение отправлено")

# ---------------- MAIN ----------------

def main():
    try:
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("jobs", jobs))
        app.add_handler(CommandHandler("postjob", postjob))

        app.add_handler(CallbackQueryHandler(callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        print("✅ BOT RUNNING SAFE MODE")

        app.run_polling()

    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            print("🧹 LOCK REMOVED")

if __name__ == "__main__":
    main()
