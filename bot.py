import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


async def fetch_html(url: str):
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=HEADERS) as client:
            response = await client.get(url)
            logger.info(f"GET {url} -> {response.status_code}")
            if response.status_code == 200:
                return response.text
    except Exception as e:
        logger.error(f"Помилка: {url}: {e}")
    return None


async def parse_work_ua():
    vacancies = []
    keywords = ["різнорабочий", "вантажник", "підсобний+робітник", "прибиральник"]
    for kw in keywords:
        html = await fetch_html(f"https://www.work.ua/jobs-kyiv-{kw}/?page=1")
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("h2 a[href^='/jobs/']")[:3]:
            try:
                title = card.text.strip()
                href = card.get("href", "")
                link = f"https://www.work.ua{href}"
                parent = card.find_parent("div", class_=lambda x: x and "job-link" in x)
                salary = ""
                if parent:
                    sal = parent.select_one(".salary")
                    salary = sal.text.strip() if sal else "Договірна"
                if link and link not in published_urls:
                    vacancies.append({"title": title, "salary": salary or "Договірна", "link": link})
            except:
                pass
        await asyncio.sleep(1)
    logger.info(f"work.ua: {len(vacancies)}")
    return vacancies


def format_vacancy(vacancy: dict) -> str:
    prompt = f"""Зроби короткий пост для Telegram-каналу про підробіток у Києві:
Вакансія: {vacancy['title']}
Зарплата: {vacancy['salary']}
Посилання: {vacancy['link']}
Стиль: дружній, українська мова, емодзі 💼🔨💰, до 80 слів, посилання в кінці."""
    try:
        response = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini: {e}")
        return f"💼 {vacancy['title']}\n💰 {vacancy['salary']}\n🔗 {vacancy['link']}"


async def collect_and_post(bot: Bot):
    logger.info("🔍 Збираємо вакансії...")
    vacancies = await parse_work_ua()
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
    await update.message.reply_text("🔨 Привіт! /post — опублікувати зараз")

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
