import os
import sys
import socket
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

print("🚀 SAFE POLLING BOT START")

# ================= LOCK (100% защита от 2 запусков) =================
LOCK_PORT = 6060
lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    lock.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    print("❌ BOT ALREADY RUNNING — EXIT")
    sys.exit()

# ================= ENV =================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("TOKEN NOT FOUND")

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 BOT WORKING SAFE MODE (NO CONFLICT)")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    print("✅ SAFE POLLING RUNNING")

    app.run_polling(
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
