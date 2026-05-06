import os
import sys
import socket
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
from telegram.request import HTTPXRequest

print("🚀 PROD BOT START")

# ================= LOCK (защита от 2 запусков) =================
LOCK_PORT = 9999
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    sock.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    print("❌ Bot already running!")
    sys.exit()

# ================= ENV =================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("❌ TOKEN not found")

# ================= DB =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
employer_id INTEGER,
title TEXT,
salary_from INTEGER,
salary_to INTEGER,
text TEXT
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

conn.commit()

# ================= STATE =================
user_state = {}
user_index = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👷 Кандидат", callback_data="cand")],
        [InlineKeyboardButton("🏢 Работодатель", callback_data="emp")]
    ]

    await update.message.reply_text(
        "🚀 JOB BOT PROD",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= ROLE =================
async def role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "cand":
        user_index[uid] = 0

        await q.edit_message_text(
            "👷 Режим кандидата\nОжидайте вакансии"
        )

    if q.data == "emp":
        user_state[uid] = "create"

        await q.edit_message_text(
            "🏢 Введите:\nНазвание | от | до | описание"
        )

# ================= CREATE JOB =================
async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if user_state.get(uid) == "create":
        try:
            title, s1, s2, desc = [x.strip() for x in text.split("|")]

            cur.execute("""
                INSERT INTO jobs (employer_id, title, salary_from, salary_to, text)
                VALUES (?, ?, ?, ?, ?)
            """, (uid, title, int(s1), int(s2), desc))

            conn.commit()
            user_state.pop(uid)

            await update.message.reply_text("✅ Добавлено")

        except:
            await update.message.reply_text("❌ Ошибка формата")

# ================= MAIN =================
def main():
    request = HTTPXRequest(connect_timeout=10, read_timeout=30)

    app = ApplicationBuilder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(role, pattern="cand|emp"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))

    print("✅ RUNNING PROD BOT")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
   
