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

print("🚀 V16 SMART JOB PLATFORM STARTED")

# ================= ENV =================

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ================= DB =================

conn = sqlite3.connect("v16.db", check_same_thread=False)
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
text TEXT,
city TEXT,
pro INTEGER DEFAULT 0
)
""")

conn.commit()

# ================= HELPERS =================

def set_role(user_id, role):
    cur.execute("INSERT OR IGNORE INTO users (id, role) VALUES (?, ?)", (user_id, role))
    cur.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()

def ai_format_job(text):
    # простая “AI-имитация” без OpenAI (эконом-режим)
    return f"""
🛒 Вакансия

📌 Описание:
{text}

💡 Условия: стабильная работа
🤝 Требуется: ответственность и базовые навыки
📍 Формат: удалённо / офлайн
"""

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V16 SMART JOB PLATFORM\n\n"
        "/postjob текст — создать вакансию\n"
        "/jobs — список\n"
        "/jobs Киев — поиск по городу\n"
        "/projob текст — PRO вакансия"
    )

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    employer_id = update.effective_user.id

    formatted = ai_format_job(text)

    cur.execute(
        "INSERT INTO jobs (employer_id, text, pro) VALUES (?, ?, 0)",
        (employer_id, formatted)
    )
    conn.commit()

    await update.message.reply_text("🏢 вакансия добавлена")

async def projob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    employer_id = update.effective_user.id

    formatted = ai_format_job(text)

    cur.execute(
        "INSERT INTO jobs (employer_id, text, pro) VALUES (?, ?, 1)",
        (employer_id, formatted)
    )
    conn.commit()

    await update.message.reply_text("💎 PRO вакансия добавлена")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if args:
        city = args[0]
        cur.execute("SELECT id, text, pro FROM jobs WHERE text LIKE ?", (f"%{city}%",))
    else:
        cur.execute("SELECT id, text, pro FROM jobs ORDER BY id DESC")

    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("📭 вакансий нет")
        return

    for r in rows[:10]:
        tag = "💎 PRO" if r[2] == 1 else "💼"
        await update.message.reply_text(f"{tag} ID {r[0]}\n{r[1]}")

# ================= SIMPLE CHAT =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # простой AI-ответ (без API)
    if "зарплата" in text.lower():
        await update.message.reply_text("💰 зарплата обсуждается с работодателем")
    elif "работа" in text.lower():
        await update.message.reply_text("📌 используйте /jobs для поиска")
    else:
        await update.message.reply_text("💬 сообщение отправлено")

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("postjob", postjob))
    app.add_handler(CommandHandler("projob", projob))
    app.add_handler(CommandHandler("jobs", jobs))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ V16 RUNNING")

    app.run_polling()

if __name__ == "__main__":
    main()
