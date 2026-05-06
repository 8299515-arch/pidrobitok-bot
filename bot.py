import os
import sqlite3
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

print("🚀 V13 BROADCAST SYSTEM STARTED")

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ---------------- DB ----------------

conn = sqlite3.connect("v13.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY,
role TEXT,
city TEXT DEFAULT '',
notify INTEGER DEFAULT 1
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT,
city TEXT
)
""")

conn.commit()

# ---------------- USERS ----------------

def set_role(user_id, role):
    cur.execute("""
    INSERT OR IGNORE INTO users (id, role, notify)
    VALUES (?, ?, 1)
    """, (user_id, role))

    cur.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()

def set_city(user_id, city):
    cur.execute("UPDATE users SET city=? WHERE id=?", (city, user_id))
    conn.commit()

def get_users(role):
    cur.execute("SELECT id, city FROM users WHERE role=? AND notify=1", (role,))
    return cur.fetchall()

# ---------------- JOBS ----------------

def add_job(title, city):
    cur.execute("INSERT INTO jobs (title, city) VALUES (?, ?)", (title, city))
    conn.commit()

# ---------------- BROADCAST ----------------

async def broadcast_to_candidates(app, job_title, job_city):
    users = get_users("candidate")

    for user_id, city in users:
        if city and city.lower() not in job_city.lower():
            continue

        await app.bot.send_message(
            user_id,
            f"🔥 НОВАЯ ВАКАНСИЯ\n\n{job_title}\n📍 {job_city}"
        )

async def broadcast_to_employers(app, candidate_info):
    users = get_users("employer")

    for user_id, city in users:
        await app.bot.send_message(
            user_id,
            f"👷 НОВЫЙ КАНДИДАТ\n\n{candidate_info}"
        )

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V13 SMART SYSTEM\n\n"
        "/candidate — ищу работу\n"
        "/employer — работодатель\n"
        "/setcity Киев — город\n"
        "/addjob текст город"
    )

async def candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_role(update.effective_user.id, "candidate")
    await update.message.reply_text("👤 Вы кандидат")

async def employer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_role(update.effective_user.id, "employer")
    await update.message.reply_text("🏢 Вы работодатель")

async def setcity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args)
    set_city(update.effective_user.id, city)
    await update.message.reply_text(f"📍 Город установлен: {city}")

# ---------------- ADD JOB + AUTO BROADCAST ----------------

async def addjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = " ".join(context.args).split(",")

    if len(parts) < 2:
        await update.message.reply_text("❌ формат: текст, город")
        return

    title = parts[0].strip()
    city = parts[1].strip()

    add_job(title, city)

    await update.message.reply_text("🏢 Вакансия добавлена")

    # 🔥 авто-рассылка кандидатам
    await broadcast_to_candidates(context.application, title, city)

# ---------------- SIMPLE CANDIDATE POST (SIMULATION) ----------------

async def fake_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👤 Опыт: 2 года\nНавыки: продажи, коммуникация"

    await broadcast_to_employers(context.application, text)

# ---------------- MAIN ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("candidate", candidate))
    app.add_handler(CommandHandler("employer", employer))
    app.add_handler(CommandHandler("setcity", setcity))
    app.add_handler(CommandHandler("addjob", addjob))
    app.add_handler(CommandHandler("candidatepost", fake_candidate))

    print("✅ V13 READY (SMART BROADCAST)")

    app.run_polling()

if __name__ == "__main__":
    main()
