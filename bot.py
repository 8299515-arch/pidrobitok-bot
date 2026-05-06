import os
import sqlite3
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

print("🚀 V12 STABLE STARTED")

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

# ---------------- DB HELPERS ----------------

def get_user(user_id):
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()

    if not user:
        cur.execute("INSERT INTO users (id, premium) VALUES (?, 0)", (user_id,))
        conn.commit()

    return user

def add_job(title, boost=False):
    price = 10 if boost else 0

    cur.execute(
        "INSERT INTO jobs (title, boost, price) VALUES (?, ?, ?)",
        (title, int(boost), price)
    )
    conn.commit()

def get_jobs():
    cur.execute("SELECT * FROM jobs ORDER BY boost DESC, id DESC")
    return cur.fetchall()

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id)

    await update.message.reply_text(
        "🚀 V12 STABLE PLATFORM\n\n"
        "/jobs — вакансии\n"
        "/postjob текст — добавить вакансию\n"
        "/premium — PRO"
    )

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("❌ Укажи текст вакансии")
        return

    add_job(text, boost=False)

    await update.message.reply_text("🏢 Вакансия добавлена")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs()

    if not jobs:
        await update.message.reply_text("📭 Нет вакансий")
        return

    for j in jobs[:5]:
        text = f"""
💼 {j[1]}

{"🔥 BOOST" if j[2] else "📌 обычная"}

💰 {j[3]}$
"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Отклик", callback_data=f"apply_{j[0]}")]
        ])

        await update.message.reply_text(text, reply_markup=keyboard)

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("UPDATE users SET premium=1 WHERE id=?", (update.effective_user.id,))
    conn.commit()

    await update.message.reply_text("💎 Premium активирован")

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data.startswith("apply_"):
        job_id = q.data.replace("apply_", "")

        cur.execute(
            "INSERT INTO apps (job_id, user_id) VALUES (?, ?)",
            (job_id, q.from_user.id)
        )
        conn.commit()

        await q.message.reply_text("📩 Отклик отправлен")

# ---------------- MAIN ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("jobs", jobs))
    app.add_handler(CommandHandler("postjob", postjob))
    app.add_handler(CommandHandler("premium", premium))

    app.add_handler(CallbackQueryHandler(callback))

    print("✅ V12 STABLE READY")

    app.run_polling()

if __name__ == "__main__":
    main()
