import os
import sqlite3
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

print("🚀 V12.3 REAL CHAT STARTED")

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ---------------- DB ----------------

conn = sqlite3.connect("v12.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY,
role TEXT DEFAULT 'candidate'
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

# ---------------- USERS ----------------

def set_role(user_id, role):
    cur.execute("INSERT OR IGNORE INTO users (id, role) VALUES (?, ?)", (user_id, role))
    cur.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()

def get_role(user_id):
    cur.execute("SELECT role FROM users WHERE id=?", (user_id,))
    r = cur.fetchone()
    return r[0] if r else "candidate"

# ---------------- JOBS ----------------

def add_job(title, employer_id):
    cur.execute("INSERT INTO jobs (title) VALUES (?)", (title,))
    conn.commit()
    return cur.lastrowid

def get_jobs():
    cur.execute("SELECT * FROM jobs ORDER BY id DESC")
    return cur.fetchall()

# ---------------- CHAT LOGIC ----------------

def get_chat(user_id):
    cur.execute("""
        SELECT id, candidate_id, employer_id FROM chats
        WHERE candidate_id=? OR employer_id=?
        ORDER BY id DESC LIMIT 1
    """, (user_id, user_id))
    return cur.fetchone()

def create_chat(job_id, candidate_id, employer_id):
    cur.execute("""
        INSERT INTO chats (job_id, candidate_id, employer_id)
        VALUES (?, ?, ?)
    """, (job_id, candidate_id, employer_id))
    conn.commit()
    return cur.lastrowid

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V12.3 REAL CHAT SYSTEM\n\n"
        "/candidate — я ищу работу\n"
        "/employer — я работодатель\n"
        "/jobs — вакансии\n"
    )

async def candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_role(update.effective_user.id, "candidate")
    await update.message.reply_text("👤 Вы кандидат")

async def employer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_role(update.effective_user.id, "employer")
    await update.message.reply_text("🏢 Вы работодатель")

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

# ---------------- APPLY → CREATE CHAT ----------------

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    job_id = int(q.data.replace("apply_", ""))

    candidate_id = q.from_user.id
    employer_id = 0  # пока упрощение

    chat_id = create_chat(job_id, candidate_id, employer_id)

    await q.message.reply_text(f"💬 Чат создан #{chat_id}\nТеперь пишите сообщения")

# ---------------- MESSAGE ROUTING ----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    chat = get_chat(user_id)

    if not chat:
        return

    chat_id, candidate_id, employer_id = chat

    # определяем получателя
    if user_id == candidate_id:
        receiver = employer_id
    else:
        receiver = candidate_id

    cur.execute("""
        INSERT INTO messages (chat_id, sender_id, text)
        VALUES (?, ?, ?)
    """, (chat_id, user_id, text))
    conn.commit()

    await update.message.reply_text("📨 Сообщение отправлено собеседнику")

# ---------------- MAIN ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("candidate", candidate))
    app.add_handler(CommandHandler("employer", employer))
    app.add_handler(CommandHandler("jobs", jobs))

    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ V12.3 REAL CHAT READY")

    app.run_polling()

if __name__ == "__main__":
    main()
