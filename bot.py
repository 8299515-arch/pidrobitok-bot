import asyncio
import logging
import httpx
from datetime import datetime
from google import genai
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from telegram.error import TelegramError
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8237986787:AAEmWuDMr38QRp3UrsW-phre9F2O_e2khBs")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyC3ebLl8PfdhH4Ey5WTMXAqNaTEtHXFdI4")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@PodrabotkaKiev_1")

if not TELEGRAM_TOKEN:
    raise ValueError("Нет TELEGRAM_TOKEN")
if not GEMINI_API_KEY:
    raise ValueError("Нет GEMINI_API_KEY")
if not CHANNEL_ID:
    raise ValueError("Нет CHANNEL_ID")

POST_INTERVAL = 3 * 60 * 60
MAX_VACANCIES = 3
published_urls = set()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# HH.ua API - официальный, работает с любых IP
HH_API_URL = "https://api.hh.ru/vacancies"
HH_HEADERS = {
    "User-Agent": "pidrobitok-bot/1.0 (telegram bot for job vacancies)",
    "HH-User-Agent": "pidrobitok-bot/1.0 (telegram bot for job vacancies)",
}

async def fetch_hh_vacancies():
    """Получаем вакансии через официальный hh.ua API"""
    vacancies = []
    params = {
        "text": "різноробочий OR разнорабочий OR вантажник OR грузчик OR підсобний",
        "area": 115,          # Киев
        "per_page": 20,
        "order_by": "publication_time",
        "period": 1,          # за последние сутки
    }
    try:
        async with httpx.AsyncClient(timeout=15, headers=HH_HEADERS) as client:
            response = await client.get(HH_API_URL, params=params)
            logger.info(f"HH API -> {response.status_code}")
            if response.status_code != 200:
                logger.error(f"HH API error: {response.status_code}")
                return vacancies

            data = response.json()
            items = data.get("items", [])
            logger.info(f"HH API: знайдено {len(items)} вакансій")

            for item in items:
                try:
                    link = item.get("alternate_url", "")
                    if link in published_urls:
                        continue

                    title = item.get("name", "Без назви")
                    employer = item.get("employer", {}).get("name", "Не вказано")

                    salary_data = item.get("salary")
                    if salary_data:
                        from_s = salary_data.get("from")
                        to_s = salary_data.get("to")
                        currency = salary_data.get("currency", "UAH")
                        if from_s and to_s:
                            salary = f"{from_s}–{to_s} {currency}"
                        elif from_s:
                            salary = f"від {from_s} {currency}"
                        elif to_s:
                            salary = f"до {to_s} {currency}"
                        else:
                            salary = "Договірна"
                    else:
                        salary = "Договірна"

                    vacancies.append({
                        "title": title,
                        "company": employer,
                        "salary": salary,
                        "link": link,
                    })
                except Exception as e:
                    logger.error(f"Помилка обробки вакансії: {e}")

    except Exception as e:
        logger.error(f"HH API fetch error: {e}")

    logger.info(f"HH API: {len(vacancies)} нових вакансій")
    return vacancies


def _format_vacancy_sync(vacancy: dict) -> str:
    prompt = f"""Зроби короткий пост для Telegram-каналу про підробіток у Києві:
Назва: {vacancy['title']}
Компанія: {vacancy['company']}
Зарплата: {vacancy['salary']}
Посилання: {vacancy['link']}
Використовуй емодзі 💼🔨💰, українська мова, до 80 слів, в кінці обов'язково посилання."""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"💼 {vacancy['title']}\n🏢 {vacancy['company']}\n💰 {vacancy['salary']}\n🔗 {vacancy['link']}"


async def format_vacancy(vacancy: dict) -> str:
    return await asyncio.to_thread(_format_vacancy_sync, vacancy)


async def collect_and_post(bot):
    logger.info("🔍 Збираємо вакансії з HH API...")
    vacancies = await fetch_hh_vacancies()

    if not vacancies:
        logger.warning("⚠️ Вакансій не знайдено")
        return

    published = 0
    for vacancy in vacancies:
        if published >= MAX_VACANCIES:
            break
        try:
            post_text = await format_vacancy(vacancy)
            await bot.send_message(chat_id=CHANNEL_ID, text=post_text)
            published_urls.add(vacancy["link"])
            published += 1
            logger.info(f"✅ Опубліковано: {vacancy['title']}")
            await asyncio.sleep(5)
        except TelegramError as te:
            logger.error(f"❌ Telegram помилка: {te}")
        except Exception as e:
            logger.error(f"Помилка публікації: {e}")

    logger.info(f"📢 Опубліковано {published} вакансій")


async def scheduler(bot):
    await asyncio.sleep(10)
    while True:
        await collect_and_post(bot)
        logger.info(f"⏰ Наступний пост через {POST_INTERVAL // 3600} год.")
        await asyncio.sleep(POST_INTERVAL)


# ---------- COMMANDS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔨 Привіт! Я бот підробітків у Києві\n"
        "/post — опублікувати зараз\n"
        "/status — статус"
    )

async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Шукаю вакансії...")
    await collect_and_post(context.bot)
    await update.message.reply_text("✅ Готово! Перевірте канал.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Канал: {CHANNEL_ID}\n"
        f"Час: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"Опубліковано URL: {len(published_urls)}"
    )

# ---------- MAIN ----------

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("status", status))

    async def on_start(app):
        asyncio.create_task(scheduler(app.bot))

    app.post_init = on_start

    logger.info("🚀 Бот запускається...")

    app.run_polling()

if __name__ == "__main__":
    main()
    

