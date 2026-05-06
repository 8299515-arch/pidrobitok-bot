import os
import sqlite3
import requests
from dotenv import load_dotenv

from fastapi import FastAPI
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- INIT ----------------

print("🚀 V12 SAAS STARTING...")

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

API_URL = "http://127.0.0.1:8000"

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

# ---------------- FASTAPI (BACKEND) ----------------

app_api = FastAPI(title="V12 SaaS Core")

@app_api.post("/job")
def create_job(title: str, boost: bool = False):
    price = 10 if boost else 0

    cur.execute(
        "INSERT INTO jobs (title, boost, price) VALUES (?, ?, ?)",
        (title, int(boost), price)
    )
    conn.commit()

    return {"status": "created", "boost": boost, "price": price}

@app_api.get("/jobs")
def get_jobs():
    cur.execute("SELECT * FROM jobs ORDER BY boost DESC, id DESC")
    return cur.fetchall()

@app_api.post("/premium")
def premium(user_id: int):
    cur.execute("INSERT OR REPLACE INTO users (id, premium) VALUES (?, 1)", (user_id,))
    conn.commit()
    return {"status": "premium activated"}

# ---------------- BOT CORE ----------------

def get_user(user_id):
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()

    if not user:
        cur.execute("INSERT INTO users (id, premium) VALUES (?, 0)", (user_id,))
        conn.commit()

    return user

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id)

    await update.message.reply_text(
        "🚀 V12 SAAS PLATFORM\n\n"
        "/jobs — вакансии\n"
        "/premium — PRO доступ"
    )

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = requests.get(f"{API_URL}/jobs")

    try:
        jobs = r.json()
    except:
        await update.message.reply_text("❌ API error")
        return

    if not jobs:
        await update.message.reply_text("📭 Нет вакансий")
        return

    for j in jobs[:5]:
        text = f"""
💼 {j[1]}

{"🔥 BOOSTED" if j[2] else "📌 стандарт"}

💰 цена: {j[3]}$
"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Отклик", callback_data=f"apply_{j[0]}")]
        ])

        await update.message.reply_text(text, reply_markup=keyboard)

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requests.post(f"{API_URL}/premium?user_id={update.effective_user.id}")

    await update.message.reply_text("💎 Premium активирован (V12 demo)")

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    job_id = q.data.replace("apply_", "")

    cur.execute(
        "INSERT INTO apps (job_id, user_id) VALUES (?, ?)",
        (job_id, q.from_user.id)
    )
    conn.commit()

    await q.message.reply_text("📩 Отклик отправлен")

# ---------------- RUN API ----------------

def run_api():
    import uvicorn
    uvicorn.run(app_api, host="127.0.0.1", port=8000)

# ---------------- MAIN ----------------

def main():
    Thread(target=run_api, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("jobs", jobs))
    app.add_handler(CommandHandler("premium", premium))

    app.add_handler(CallbackQueryHandler(callback))

    print("✅ V12 SAAS READY")

    app.run_polling()

if __name__ == "__main__":
    main()
