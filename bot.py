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

print("🚀 V2 JOB BOT START")

# ================= ENV =================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("❌ TOKEN NOT FOUND")

# ================= DB =================
conn = sqlite3.connect("jobs.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
employer_id INTEGER,
title TEXT,
salary_from INTEGER,
salary_to INTEGER,
description TEXT
)
""")

conn.commit()

# ================= STATE =================
user_state = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🏢 Добавить вакансию", callback_data="add_job")],
        [InlineKeyboardButton("📋 Вакансии", callback_data="list_jobs")]
    ]

    await update.message.reply_text(
        "💼 JOB BOT V2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # ➕ ДОБАВИТЬ ВАКАНСИЮ
    if query.data == "add_job":
        user_state[user_id] = "create_job"
        await query.edit_message_text(
            "🏢 Введите вакансию:\nНазвание | от | до | описание"
        )

    # 📋 СПИСОК ВАКАНСИЙ
    elif query.data == "list_jobs":
        cur.execute("""
        SELECT id, title, salary_from, salary_to, description
        FROM jobs
        ORDER BY id DESC
        LIMIT 5
        """)
        jobs = cur.fetchall()

        if not jobs:
            await query.edit_message_text("📭 Вакансий нет")
            return

        text = "📋 ВАКАНСИИ:\n\n"

        keyboard = []

        for job in jobs:
            jid, title, s1, s2, desc = job

            text += f"🏢 {title}\n💰 {s1}-{s2}\n\n"

            keyboard.append([
                InlineKeyboardButton(f"📩 Отклик на {title}", callback_data=f"apply_{jid}")
            ])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 📩 ОТКЛИК (ПОКА ПРОСТО)
    elif query.data.startswith("apply_"):
        await query.edit_message_text("✅ Отклик отправлен (чат будет в V3)")

# ================= MESSAGE =================
async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # СОЗДАНИЕ ВАКАНСИИ
    if user_state.get(user_id) == "create_job":
        try:
            title, s1, s2, desc = [x.strip() for x in text.split("|")]

            cur.execute("""
                INSERT INTO jobs (employer_id, title, salary_from, salary_to, description)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, title, int(s1), int(s2), desc))

            conn.commit()
            user_state.pop(user_id)

            await update.message.reply_text("🏢 Вакансия добавлена")

        except:
            await update.message.reply_text(
                "❌ Ошибка формата\n\nПример:\nPython Dev | 1000 | 2000 | Django опыт"
            )

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    print("✅ V2 JOB BOT RUNNING")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
   
