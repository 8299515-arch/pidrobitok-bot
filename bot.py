import os
import sqlite3
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

print("🚀 V4 PRO START")

# ================= ENV =================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL = os.getenv("CHANNEL_ID")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN:
    raise ValueError("TOKEN missing")

# ================= DB =================
conn = sqlite3.connect("v4.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
employer_id INTEGER,
title TEXT,
salary_from INTEGER,
salary_to INTEGER,
text TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS applications (
id INTEGER PRIMARY KEY AUTOINCREMENT,
job_id INTEGER,
user_id INTEGER
)
""")

conn.commit()

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👷 Найти работу", callback_data="jobs")],
        [InlineKeyboardButton("🏢 Создать вакансию", callback_data="create")]
    ]

    await update.message.reply_text(
        "🚀 V4 PRO JOB SYSTEM",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= CREATE JOB =================
user_state = {}

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "create":
        user_state[uid] = "create_job"

        await q.edit_message_text(
            "🏢 Введите:\nНазвание | от | до | описание"
        )

    elif q.data == "jobs":
        cur.execute("SELECT id, title, salary_from, salary_to, text FROM jobs ORDER BY id DESC LIMIT 1")
        job = cur.fetchone()

        if not job:
            await q.edit_message_text("📭 вакансий нет")
            return

        job_id, title, s1, s2, text = job

        keyboard = [
            [InlineKeyboardButton("📩 Отклик", callback_data=f"apply_{job_id}")]
        ]

        await q.edit_message_text(
            f"💼 {title}\n💰 {s1}-{s2}\n\n{text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif q.data.startswith("apply_"):
        job_id = int(q.data.split("_")[1])
        uid = q.from_user.id

        cur.execute("INSERT INTO applications (job_id, user_id) VALUES (?, ?)", (job_id, uid))
        conn.commit()

        await q.edit_message_text("✅ Отклик отправлен")

        # 📢 отправка в канал
        try:
            await context.bot.send_message(
                CHANNEL,
                f"📩 Новый отклик на вакансию #{job_id}"
            )
        except:
            pass

# ================= MESSAGE =================
async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if user_state.get(uid) == "create_job":
        try:
            title, s1, s2, desc = [x.strip() for x in text.split("|")]

            cur.execute("""
                INSERT INTO jobs (employer_id, title, salary_from, salary_to, text)
                VALUES (?, ?, ?, ?, ?)
            """, (uid, title, int(s1), int(s2), desc))

            conn.commit()
            user_state.pop(uid)

            await update.message.reply_text("🏢 Вакансия создана и добавлена")

            # 📢 пост в канал
            try:
                await context.bot.send_message(
                    CHANNEL,
                    f"🏢 {title}\n💰 {s1}-{s2}\n\n{desc}"
                )
            except:
                pass

        except:
            await update.message.reply_text("❌ Формат: Название | от | до | описание")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    print("✅ V4 PRO RUNNING")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
  
   
