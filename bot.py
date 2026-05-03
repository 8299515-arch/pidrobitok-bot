import asyncio
import logging
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from google import genai
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = "8704316956:AAE1h8MnbwvL35GNeiLEUflTKCUIfhMIKgU"
GEMINI_API_KEY = "AIzaSyCQx8bjxFhwCVD1qBGZW3J9MMhEXk7nSnU"
CHANNEL_ID = "@PodrabotkaKiev_1"

POST_INTERVAL = 3 * 60 * 60
published_urls = set()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

RSS_FEEDS = [
    "https://www.work.ua/rss/jobs/city=kyiv/category=68/",   # різноробочі
    "https://www.work.ua/rss/jobs/city=kyiv/category=27/",   # будівництво
    "https://www.work.ua/rss/jobs/city=kyiv/category=29/",   # вантажники
]


async def fetch_rss(url: str):
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url)
            logger.info(f"RSS {url} -> {response.status_code}")
            if response.status_code == 200:
                return response.text
    except Exception as e:
        logger.error(f"RSS помилка: {e}")
    return None


async def parse_rss_feeds():
    vacancies = []
    for url in RSS_FEEDS:
        xml_text = await fetch_rss(url)
        if not xml_text:
            continue
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item")[:5]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                description = item.findtext("description", "").strip()
                if link and link not in published_urls and title:
                    vacancies.append({
                        "title": title,
                        "description": description[:200] if description else "",
                        "link": link
                    })
        except Exception as e:
            logger.error(f"XML помилка: {e}")
        await asyncio.sleep(1)
    logger.info(f"RSS знайдено: {len(vacancies)}")
    return vacancies


def format_vacancy(vacancy: dict) -> str:
    prompt = f"""Зроби короткий пост для Telegram-каналу про підробіток у Києві:
Вакансія: {vacancy['title']}
Деталі: {vacancy['description']}
Посилання: {vacancy['link']}
Стиль: дружній, українська мова, емодзі 💼🔨💰📍, до 80 слів, посилання в кінці."""
    try:
        response = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini: {e}")
        return f"💼 {vacancy['title']}\n🔗 {vacancy['link']}"


async def collect_and_post(bot: Bot):
    logger.info("🔍 Збираємо вакансії через RSS...")
    vacancies = await parse_rss_feeds()
    if not vacancies:
        logger.warning("Вакансій не знайдено")
        return
    published = 0
    for vacancy in vacancies[:3]:
        try:
            post_text = format_vacancy(vacancy)
            await bot.send_message(chat_id=CHANNEL_ID, text=post_text)
            published_urls.add(vacancy["link"])
            published += 1
            logger.info(f"✅ {vacancy['title']}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Помилка публікації: {e}")
    logger.info(f"📢 Опубліковано {published}")


async def auto_post_loop(bot: Bot):
    while True:
        await collect_and_post(bot)
        await asyncio.sleep(POST_INTERVAL)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔨 Привіт! /post — опублікувати зараз\n/status — статус")

async def manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Шукаю...")
    await collect_and_post(context.bot)
    await update.message.reply_text("✅ Готово!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 Канал: {CHANNEL_ID}\n🕐 {datetime.now().strftime('%H:%M %d.%m.%Y')}")


async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", manual_post))
    app.add_handler(CommandHandler("status", status))
    logger.info("🚀 Бот запущено!")
    async with app:
        await app.start()
        asyncio.create_task(auto_post_loop(app.bot))
        await app.updater.start_polling()
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())    
    
  
