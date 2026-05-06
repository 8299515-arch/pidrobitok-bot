import os
import sys
import socket
import sqlite3
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

print("🚀 V2.0 ANTI-CONFLICT BOT START")

# ================= LOCK (ГЛАВНАЯ ЗАЩИТА) =================
LOCK_PORT = 5050
lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    lock_socket.bind(("127.0.0.1", LOCK_PORT))
except OSError:
    print("❌ BOT ALREADY RUNNING (LOCK ACTIVE)")
    sys.exit()

# ================= ENV =================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("TOKEN NOT FOUND")

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

# ================= SAFE HANDLER =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 V2.0 BOT ONLINE (NO CONFLICT MODE)")

# ================= GLOBAL ERROR HANDLER =================
async def error_handler(update, context):
    print(f"⚠️ ERROR: {context.error}")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # 🔥 ГЛОБАЛЬНЫЙ АНТИ-КРАШ
    app.add_error_handler(error_handler)

    print("✅ BOT RUNNING SAFE MODE")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )

if __name__ == "__main__":
    main()
   
