import os
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ----------------- INIT -----------------

print("🔥 SCRIPT STARTED")

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- HANDLERS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /start")
    await update.message.reply_text("🤖 Бот работает")

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 /post")
    await update.message.reply_text("🚀 /post работает")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 TEXT:", update.message.text)

# ----------------- MAIN -----------------

def main():
    print("🚀 ENTER MAIN")

    # ❗ временно не валим контейнер
    if not TELEGRAM_TOKEN:
        print("❌ NO TELEGRAM_TOKEN")
        return

    print("✅ TOKEN OK")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🚀 START POLLING")

    app.run_polling()

if __name__ == "__main__":
    main()
   
