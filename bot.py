import os
import sys
import time
import sqlite3
import logging
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

print("🚀 V13.5 LIGHT STARTED")

# ================= LOGGING =================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ================= SIMPLE LOCK (NO PSUTIL) =================

LOCK_FILE = "bot.lock"

if os.path.exists(LOCK_FILE):
    print("⛔ BOT LOCK DETECTED (maybe already running)")
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

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
text TEXT
)
""")

conn.commit()

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 V13.5 LIGHT BOT ACTIVE")

async def postjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("❌ empty")
        return

    cur.execute("INSERT INTO jobs (text) VALUES (?)", (text,))
    conn.commit()

    await update.message.reply_text("🏢 added")

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT text FROM jobs ORDER BY id DESC")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("📭 no jobs")
        return

    for r in rows[:10]:
        await update.message.reply_text(f"💼 {r[0]}")

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

    while True:
        try:
            print("✅ BOT RUNNING LIGHT MODE")

            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )

        except (TimedOut, NetworkError, Conflict) as e:
            print(f"⚠️ restart due to: {e}")
            time.sleep(3)

        except Exception as e:
            print(f"🔥 fatal error: {e}")
            time.sleep(5)

# ================= START =================

if __name__ == "__main__":
    main()
