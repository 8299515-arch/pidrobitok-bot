import os
import sqlite3
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

print("🚀 V15 REAL CHAT STARTED")

# ================= ENV =================

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ================= DB =================

conn = sqlite3.connect("v15.db", check_same_thread=False)
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
CREATE TABLE IF NOT EXISTS applications (
id INTEGER PRIMARY KEY AUTOINCREMENT,
job_id INTEGER,
candidate_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS chats (
id INTEGER PRIMARY KEY AUTOINCREMENT,
room_id TEXT,
sender_id INTEGER,
text TEXT
)
""")

conn.commit()

# ================= HELPERS =================

def set_role(user_id, role):
    cur.execute("INSERT OR IGNORE INTO users (id, role) VALUES (?, ?)", (user_id, role))
    cur.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()

def get_role(user_id):
    cur.execute("SELECT role FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else None

def get_employer(job_id):
    cur.execute("SELECT employer_id FROM jobs WHERE id=?", (job_id,))
    row = cur.fetchone()
    return row[0] if row else None

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V15 JOB CHAT\n\n"
        "/candidate — ищу работу\n"
        "/employer — работодатель\n"
        "/postjob текст — вакансия\n"
        "/jobs — список\n"
        "/apply ID — отклик\n"
    )

async def candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_role(update.effective_user.id, "candidate")
    await update.message.reply_text("👷 Вы кандидат")

async def employer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_role(update.effective_user.id, "employer")
    await update.message.reply_text("🏢 Вы работодатель")

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    employer_id = update.effective_user.id

    cur.execute("INSERT INTO jobs (employer_id, text) VALUES (?, ?)", (employer_id, text))
    conn.commit()

    await update.message.reply_text("🏢 вакансия создана")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT id, text FROM jobs ORDER BY id DESC")
    rows = cur.fetchall()

    for r in rows[:10]:
        await update.message.reply_text(f"ID {r[0]}:\n💼 {r[1]}")

# ================= APPLY + CHAT ROOM =================

async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candidate_id = update.effective_user.id
    job_id = context.args[0]

    employer_id = get_employer(job_id)

    if not employer_id:
        await update.message.reply_text("❌ вакансия не найдена")
        return

    room_id = f"{job_id}_{candidate_id}"

    cur.execute(
        "INSERT INTO applications (job_id, candidate_id) VALUES (?, ?)",
        (job_id, candidate_id)
    )
    conn.commit()

    await update.message.reply_text("📩 отклик отправлен")

    await context.bot.send_message(
        employer_id,
        f"📨 Новый отклик на вакансию {job_id}\n"
        f"💬 начат чат (room {room_id})"
    )

# ================= CHAT =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    cur.execute("""
        SELECT job_id, candidate_id FROM applications
        WHERE candidate_id=? OR job_id IN (
            SELECT id FROM jobs WHERE employer_id=?
        )
        ORDER BY id DESC LIMIT 1
    """, (user_id, user_id))

    row = cur.fetchone()

    if not row:
        await update.message.reply_text("❌ нет активного чата")
        return

    job_id, candidate_id = row
    room_id = f"{job_id}_{candidate_id}"

    cur.execute(
        "INSERT INTO chats (room_id, sender_id, text) VALUES (?, ?, ?)",
        (room_id, user_id, text)
    )
    conn.commit()

    employer_id = get_employer(job_id)

    # пересылаем сообщение второй стороне
    if user_id == employer_id:
        target = candidate_id
    else:
        target = employer_id

    await context.bot.send_message(
        target,
        f"💬 сообщение:\n{text}"
    )

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("candidate", candidate))
    app.add_handler(CommandHandler("employer", employer))
    app.add_handler(CommandHandler("postjob", postjob))
    app.add_handler(CommandHandler("jobs", jobs))
    app.add_handler(CommandHandler("apply", apply))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ V15 RUNNING REAL CHAT")

    app.run_polling()

if __name__ == "__main__":
    main()
  
