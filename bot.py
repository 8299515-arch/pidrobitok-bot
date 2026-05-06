import os
import sys
import time
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

from telegram.request import HTTPXRequest
from telegram.error import TimedOut, NetworkError, Conflict

print("🚀 V16 CLEAN PRODUCTION STARTED")

# ================= SIMPLE LOCK =================

LOCK_FILE = "bot.lock"

if os.path.exists(LOCK_FILE):
    print("⛔ BOT ALREADY RUNNING")
    sys.exit()

with open(LOCK_FILE, "w") as f:
    f.write("running")

print("🔒 LOCK CREATED")

import atexit

def cleanup():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        print("🧹 LOCK REMOVED")

atexit.register(cleanup)

# ================= ENV =================

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# ================= DB =================

conn = sqlite3.connect("v16.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
text TEXT,
pro INTEGER DEFAULT 0
)
""")

conn.commit()

# ================= AI FORMAT =================

def format_job(text, pro=False):
    tag = "💎 PRO" if pro else "💼"
    return f"""{tag} Вакансия

📌 {text}

💡 Условия: стабильная работа
🤝 Требования: ответственность
📍 Формат: Киев / удалённо
"""

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 JOB BOT\n\n"
        "/postjob текст — вакансия\n"
        "/projob текст — PRO вакансия\n"
        "/jobs — список\n"
    )

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("❌ пусто")
        return

    cur.execute("INSERT INTO jobs (text, pro) VALUES (?, 0)", (text,))
    conn.commit()

    await update.message.reply_text("🏢 добавлено")

async def projob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("❌ пусто")
        return

    cur.execute("INSERT INTO jobs (text, pro) VALUES (?, 1)", (text,))
    conn.commit()

    await update.message.reply_text("💎 PRO добавлено")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT id, text, pro FROM jobs ORDER BY pro DESC, id DESC")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("📭 вакансий нет")
        return

    for r in rows[:10]:
        msg = format_job(r[1], r[2] == 1)
        await update.message.reply_text(f"ID {r[0]}\n{msg}")

# ================= SIMPLE AI CHAT =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if "работа" in text:
        await update.message.reply_text("📌 смотри /jobs")
    elif "зарплата" in text:
        await update.message.reply_text("💰 обсуждается с работодателем")
    else:
        await update.message.reply_text("💬 сообщение принято")

# ================= ERROR HANDLER =================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"⚠️ ERROR: {context.error}")

# ================= MAIN =================

def main():
    request = HTTPXRequest(
        connect_timeout=10,
        read_timeout=30
    )

    app = ApplicationBuilder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("postjob", postjob))
    app.add_handler(CommandHandler("projob", projob))
    app.add_handler(CommandHandler("jobs", jobs))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_error_handler(error_handler)

    while True:
        try:
            print("✅ BOT RUNNING CLEAN MODE")

            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )

        except (TimedOut, NetworkError, Conflict) as e:
            print(f"⚠️ RESTART: {e}")
            time.sleep(3)

        except Exception as e:
            print(f"🔥 FATAL: {e}")
            time.sleep(5)

# ================= START =================

if __name__ == "__main__":
    main()
