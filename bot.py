import os
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import httpx
from bs4 import BeautifulSoup

from google import genai

# ======================
# ENV
# ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN не найден в .env")

# ======================
# AI (НОВЫЙ СТАБИЛЬНЫЙ SDK)
# ======================
client = genai.Client(api_key=GOOGLE_API_KEY)

def ask_ai(text: str):
    try:
        res = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=text
        )
        return res.text
    except Exception as e:
        return f"AI ошибка: {e}"

# ======================
# КНОПКИ
# ======================
keyboard = ReplyKeyboardMarkup(
    [
        ["📍 Киев вакансии", "💼 Вакансии"],
        ["🤖 AI HR"]
    ],
    resize_keyboard=True
)

# ======================
# ВАКАНСИИ (простая версия)
# ======================
def get_jobs():
    try:
        url = "https://robota.ua/zapros/python-kyiv"
        r = httpx.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        jobs = []
        for h in soup.find_all("h2"):
            if h.text.strip():
                jobs.append(h.text.strip())

        return jobs[:7]

    except:
        return ["❌ Не удалось загрузить вакансии"]

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V4 FIXED BOT\n\nВыбери действие:",
        reply_markup=keyboard
    )

# ======================
# JOBS
# ======================
async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_jobs()

    text = "📍 Вакансии Киев:\n\n"
    for j in data:
        text += f"• {j}\n"

    await update.message.reply_text(text)

# ======================
# AI
# ======================
async def ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = ask_ai(update.message.text)
    await update.message.reply_text(answer)

# ======================
# ROUTER
# ======================
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📍 Киев вакансии":
        await jobs(update, context)
        return

    if text == "💼 Вакансии":
        await jobs(update, context)
        return

    if text == "🤖 AI HR":
        await update.message.reply_text("Напиши о себе (опыт, навыки)")
        return

    await ai(update, context)

# ======================
# MAIN
# ======================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

    print("🚀 V4 FIXED RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
