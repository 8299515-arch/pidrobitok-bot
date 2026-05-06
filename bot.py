import os
import sys
import time
import psutil
import logging
import sqlite3
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from telegram.request import HTTPXRequest
from telegram.error import TimedOut, NetworkError, Conflict

print("🚀 V13.5 PRO STARTING")

# ================= LOGGING =================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ================= SAFE LOCK =================

LOCK_FILE = "bot.lock"

def is_process_running(pid):
    return psutil.pid_exists(pid)

if os.path.exists(LOCK_FILE):
    try:
        with open(LOCK_FILE, "r") as f:
            old_pid = int(f.read().strip())

        if is_process_running(old_pid):
            print("⛔ BOT ALREADY RUNNING")
            sys.exit()

    except:
        print("🧹 BAD LOCK FIXED")

with open(LOCK_FILE, "w") as f:
    f.write(str(os.getpid()))

print("🔒 SAFE LOCK ACTIVE")

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

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
text TEXT
)
""")

conn.commit()

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 V13.5 PRO BOT WORKING")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT text FROM jobs ORDER BY id DESC")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("📭 Нет вакансий")
        return

    for r in rows[:10]:
        await update.message.reply_text(f"💼 {r[0]}")

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("❌ пусто")
        return

    cur.execute("INSERT INTO jobs (text) VALUES (?)", (text,))
    conn.commit()

    await update.message.reply_text("🏢 добавлено")

# ================= ERROR HANDLER =================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"ERROR: {context.error}")

# ================= MAIN =================

def main():
    request = HTTPXRequest(
        connect_timeout=10,
        read_timeout=30
    )

    app = ApplicationBuilder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("jobs", jobs))
    app.add_handler(CommandHandler("postjob", postjob))

    app.add_error_handler(error_handler)

    # ================= SAFE RETRY LOOP =================

    while True:
        try:
            print("✅ BOT RUNNING (PRO MODE)")
            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )

        except (TimedOut, NetworkError, Conflict) as e:
            print(f"⚠️ RESTARTING BOT DUE TO ERROR: {e}")
            time.sleep(3)

        except Exception as e:
            print(f"🔥 FATAL ERROR: {e}")
            time.sleep(5)

# ================= START =================

if __name__ == "__main__":
    main()
