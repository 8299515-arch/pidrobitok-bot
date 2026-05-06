import os
import asyncio
import sqlite3
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.request import HTTPXRequest

print("🚀 BOT STARTING V17 CLEAN")

# ================= ENV =================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not found in .env")

# ================= DB =================
conn = sqlite3.connect("v17.db", check_same_thread=False)
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

# ================= HELPERS =================
def set_role(user_id, role):
    cur.execute("INSERT OR REPLACE INTO users (id, role) VALUES (?, ?)", (user_id, role))
    conn.commit()

def get_role(user_id):
    cur.execute("SELECT role FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else None

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👷 Ищу работу", callback_data="role_candidate")],
        [InlineKeyboardButton("🏢 Работодатель", callback_data="role_employer")]
    ]

    await update.message.reply_text(
        "🚀 JOB PLATFORM\n\nВыберите роль:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= ROLE =================
async def role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "role_candidate":
        set_role(user_id, "candidate")

        keyboard = [
            [InlineKeyboardButton("📋 Вакансии", callback_data="jobs")]
        ]

        await query.edit_message_text(
            "👷 Вы кандидат",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "role_employer":
        set_role(user_id, "employer")
        await query.edit_message_text("🏢 Напишите вакансию текстом")

# ================= JOBS =================
async def show_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cur.execute("SELECT id, text FROM jobs ORDER BY id DESC LIMIT 1")
    job = cur.fetchone()

    if not job:
        await query.edit_message_text("📭 вакансий нет")
        return

    job_id, text = job

    keyboard = [
        [InlineKeyboardButton("📩 Откликнуться", callback_data=f"apply_{job_id}")]
    ]

    await query.edit_message_text(
        f"💼 {text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= APPLY =================
async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    job_id = int(query.data.split("_")[1])

    cur.execute("SELECT employer_id FROM jobs WHERE id=?", (job_id,))
    employer = cur.fetchone()

    if not employer:
        await query.edit_message_text("❌ ошибка")
        return

    employer_id = employer[0]

    cur.execute(
        "INSERT INTO chats (job_id, candidate_id, employer_id) VALUES (?, ?, ?)",
        (job_id, user_id, employer_id)
    )
    conn.commit()

    await query.edit_message_text("✅ Отклик отправлен")

    await context.bot.send_message(
        employer_id,
        "📨 Новый кандидат откликнулся"
    )

# ================= CHAT =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    cur.execute("""
        SELECT job_id, candidate_id, employer_id FROM chats
        WHERE candidate_id=? OR employer_id=?
        ORDER BY id DESC LIMIT 1
    """, (user_id, user_id))

    chat = cur.fetchone()

    if not chat:
        await update.message.reply_text("❌ нет активного чата")
        return

    job_id, candidate_id, employer_id = chat

    target = employer_id if user_id == candidate_id else candidate_id

    await context.bot.send_message(target, f"💬 {text}")

# ================= POST JOB =================
async def post_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = get_role(user_id)

    if role != "employer":
        return

    text = update.message.text

    cur.execute(
        "INSERT INTO jobs (employer_id, text) VALUES (?, ?)",
        (user_id, text)
    )
    conn.commit()

    await update.message.reply_text("🏢 Вакансия добавлена")

# ================= CLEAN =================
async def clean_webhook():
    try:
        bot = Bot(TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)
        print("🧹 webhook cleared")
    except Exception as e:
        print("⚠️ webhook error:", e)

# ================= MAIN =================
def main():
    print("🔒 INIT BOT")

    asyncio.run(clean_webhook())

    request = HTTPXRequest(connect_timeout=10, read_timeout=30)

    app = ApplicationBuilder().token(TOKEN).request(request).build()

    # handlers
    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(role_handler, pattern="role_"))
    app.add_handler(CallbackQueryHandler(show_jobs, pattern="jobs"))
    app.add_handler(CallbackQueryHandler(apply, pattern="apply_"))

    app.add_handler(MessageHandler(filters.Regex("^(🏢|👷)"), post_job))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ BOT RUNNING")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

   
