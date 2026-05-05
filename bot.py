import os
import logging
import asyncio

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- INIT ----------------

print("🔥 BOT FILE LOADED")

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- SAFETY LOCK ----------------

LOCK_FILE = "bot.lock"

def already_running():
    return os.path.exists(LOCK_FILE)

def create_lock():
    with open(LOCK_FILE, "w") as f:
        f.write("running")

def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start")
    await update.message.reply_text("🤖 Бот работает стабильно")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /post")
    await update.message.reply_text("🚀 POST OK")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 TEXT:", update.message.text)

# ---------------- MAIN ----------------

def main():
    print("🚀 STARTING BOT...")

    if not TELEGRAM_TOKEN:
        print("❌ NO TOKEN")
        return

    # 🔴 защита от второго инстанса
    if already_running():
        print("⚠️ BOT ALREADY RUNNING - EXIT")
        return

    create_lock()

    try:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("post", post))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        print("✅ BOT READY")

        # 🔥 ВАЖНО: защита от конфликтов Telegram
        app.run_polling(
            drop_pending_updates=True,
            close_loop=False
        )

    except Exception as e:
        print("❌ ERROR:", e)

    finally:
        remove_lock()
        print("🧹 LOCK REMOVED")

# ---------------- RUN ----------------

if __name__ == "__main__":
    main()
   
   
