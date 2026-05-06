import os
import sys
import time
import sqlite3
import psutil
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

print("🚀 V16 SAFE ULTIMATE STARTED")

# ================= SAFE GUARD (ANTI-CONFLICT) =================

LOCK_FILE = "bot.lock"

def is_running(pid):
    try:
        return psutil.pid_exists(pid)
    except:
        return False

if os.path.exists(LOCK_FILE):
    try:
        with open(LOCK_FILE, "r") as f:
            old_pid = int(f.read().strip())

        if is_running(old_pid):
            print("⛔ BOT ALREADY RUNNING → EXIT")
            sys.exit()

        else:
            print("🧹 OLD LOCK REMOVED")

    except:
        print("🧹 BROKEN LOCK FIXED")

with open(LOCK_FILE, "w") as f:
    f.write(str(os.getpid()))

print(f"🔒 LOCK ACTIVE | PID {os.getpid()}")

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
text TEXT
)
""")

conn.commit()

# ================= JOB SYSTEM =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V16 SAFE ULTIMATE\n\n"
        "/postjob текст — добавить вакансию\n"
        "/jobs — список вакансий"
    )

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("❌ пустая вакансия")
        return

    cur.execute("INSERT INTO jobs (text) VALUES (?)", (text,))
    conn.commit()

    await update.message.reply_text("🏢 вакансия добавлена")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT text FROM jobs ORDER BY id DESC")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("📭 вакансий нет")
        return

    for r in rows[:10]:
        await update.message.reply_text(f"💼 {r[0]}")

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
    app.add_handler(CommandHandler("jobs", jobs))

    app.add_error_handler(error_handler)

    while True:
        try:
            print("✅ BOT RUNNING SAFE ULTIMATE MODE")

            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )

        except (TimedOut, NetworkError, Conflict) as e:
            print(f"⚠️ RESTARTING BOT: {e}")
            time.sleep(3)

        except Exception as e:
            print(f"🔥 FATAL ERROR: {e}")
            time.sleep(5)

# ================= START =================

if __name__ == "__main__":
    main()
