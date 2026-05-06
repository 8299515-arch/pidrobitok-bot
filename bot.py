import os
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

print("🚀 V20 FIX START")

# ================= ENV =================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not found")

# ================= DB =================
conn = sqlite3.connect("v20.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY,
role TEXT
)
""")

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
user_job_index = {}

# ================= HELPERS =================
def set_role(uid, role):
    cur.execute("INSERT OR REPLACE INTO users (id, role) VALUES (?, ?)", (uid, role))
    conn.commit()

def get_role(uid):
    cur.execute("SELECT role FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else None

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👷 Ищу работу", callback_data="candidate")],
        [InlineKeyboardButton("🏢 Работодатель", callback_data="employer")]
    ]

    await update.message.reply_text(
        "🚀 V20 FIX JOB PLATFORM",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= ROLE =================
async def role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "candidate":
        set_role(uid, "candidate")
        user_job_index[uid] = 0

        keyboard = [
            [InlineKeyboardButton("📋 Вакансии", callback_data="jobs")]
        ]

        await q.edit_message_text(
            "👷 Вы кандидат",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif q.data == "employer":
        set_role(uid, "employer")
        user_state[uid] = "create_job"

        await q.edit_message_text(
            "🏢 Введите вакансию:\nНазвание | от | до | описание"
        )

# ================= CREATE JOB =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if user_state.get(uid) == "create_job":
        try:
            title, s_from, s_to, desc = [x.strip() for x in text.split("|")]

            cur.execute("""
                INSERT INTO jobs (employer_id, title, salary_from, salary_to, text)
                VALUES (?, ?, ?, ?, ?)
            """, (uid, title, int(s_from), int(s_to), desc))

            conn.commit()
            user_state.pop(uid)

            await update.message.reply_text("🏢 Вакансия добавлена")

        except:
            await update.message.reply_text("❌ Ошибка формата")
        return

# ================= JOB LIST =================
async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user_job_index[q.from_user.id] = 0
    await show_job(q, q.from_user.id)

# ================= SHOW JOB =================
async def show_job(query, uid):
    cur.execute("SELECT id, title, salary_from, salary_to, text FROM jobs ORDER BY id DESC")
    jobs = cur.fetchall()

    if not jobs:
        await query.edit_message_text("📭 вакансий нет")
        return

    idx = user_job_index.get(uid, 0)

    if idx >= len(jobs):
        idx = 0

    job = jobs[idx]
    job_id, title, s_from, s_to, text = job

    keyboard = [
        [InlineKeyboardButton("📩 Отклик", callback_data=f"apply_{job_id}")],
        [InlineKeyboardButton("➡️ Далее", callback_data="next")]
    ]

    await query.edit_message_text(
        f"💼 {title}\n💰 {s_from}-{s_to}\n\n{text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= NEXT JOB =================
async def next_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    user_job_index[uid] = user_job_index.get(uid, 0) + 1

    await show_job(q, uid)

# ================= APPLY =================
async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    job_id = int(q.data.split("_")[1])

    cur.execute("SELECT employer_id FROM jobs WHERE id=?", (job_id,))
    emp = cur.fetchone()

    if not emp:
        await q.edit_message_text("❌ ошибка")
        return

    employer_id = emp[0]

    cur.execute("""
        INSERT INTO chats (job_id, candidate_id, employer_id)
        VALUES (?, ?, ?)
    """, (job_id, uid, employer_id))

    conn.commit()

    await q.edit_message_text("✅ Отклик отправлен")
    await context.bot.send_message(employer_id, "📨 Новый отклик")

# ================= MAIN =================
def main():
    request = HTTPXRequest(connect_timeout=10, read_timeout=30)

    app = ApplicationBuilder().token(TOKEN).request(request).build()

    # ================= HANDLERS (ИСПРАВЛЕНО) =================
    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(role_handler, pattern="candidate|employer"))
    app.add_handler(CallbackQueryHandler(jobs, pattern="jobs"))
    app.add_handler(CallbackQueryHandler(next_job, pattern="next"))
    app.add_handler(CallbackQueryHandler(apply, pattern="apply_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ V20 FIX RUNNING")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
   
