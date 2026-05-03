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
MAX_VACANCIES = 3
published_urls = set()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


async def fetch_html(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            logger.info(f"GET {url} -> {response.status_code}")
            return response.text
    except Exception as e:
        logger.error(f"Ошибка загрузки {url}: {e}")
        return None


async def parse_work_ua():
    vacancies = []
    urls = [
        "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/",
        "https://www.work.ua/jobs-kyiv-%D0%B2%D0%B0%D0%BD%D1%82%D0%B0%D0%B6%D0%BD%D0%B8%D0%BA/",
        "https://www.work.ua/jobs-kyiv-%D0%B3%D1%80%D1%83%D0%B7%D1%87%D0%B8%D0%BA/",
    ]
    for url in urls:
        html = await fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select(".job-link")[:5]:
            try:
                title = card.select_one("h2").text.strip() if card.select_one("h2") else "Без назви"
                company = card.select_one(".add-bottom").text.strip() if card.select_one(".add-bottom") else "Не вказано"
                salary = card.select_one(".salary").text.strip() if card.select_one(".salary") else "Договірна"
                href = card.get("href")
                link = f"https://www.work.ua{href}" if href else ""
                if link and link not in published_urls:
                    vacancies.append({"title": title, "company": company, "salary": salary, "link": link})
            except:
                pass
    logger.info(f"work.ua знайдено: {len(vacancies)}")
    return vacancies


async def parse_olx_ua():
    vacancies = []
    urls = [
        "https://www.olx.ua/uk/robota/inshi-sfery-zanyatosti/",
        "https://www.olx.ua/uk/robota/budivnytstvo-remont/",
        "https://www.olx.ua/uk/robota/transport-logistyka/",
    ]
    for url in urls:
        html = await fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("[data-cy='l-card']")[:5]:
            try:
                title = card.select_one("h4, h6").text.strip() if card.select_one("h4, h6") else "Без назви"
                salary = card.select_one("[data-testid='ad-price']").text.strip() if card.select_one("[data-testid='ad-price']") else "Договірна"
                link_el = card.select_one("a")
                href = link_el.get("href", "") if link_el else ""
                link = f"https://www.olx.ua{href}" if href.startswith("/") else href
                if link and link not in published_urls:
                    vacancies.append({"title": title, "company": "OLX", "salary": salary, "link": link})
            except:
                pass
    logger.info(f"OLX знайдено: {len(vacancies)}")
    return vacancies


def format_vacancy(vacancy: dict) -> str:
    prompt = f"""Зроби пост для Telegram-каналу про підробіток у Києві:
Назва: {vacancy['title']}
Компанія: {vacancy.get('company', '')}
Зарплата: {vacancy['salary']}
Посилання: {vacancy['link']}
Використовуй емодзі 💼🔨💰📍, українська мова, до 100 слів, в кінці посилання."""
    try:
        response = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"💼 {vacancy['title']}\n💰 {vacancy['salary']}\n🔗 {vacancy['link']}"


async def collect_and_post(bot: Bot):
    logger.info("🔍 Збираємо вакансії...")
    results = await asyncio.gather(parse_work_ua(), parse_olx_ua(), return_exceptions=True)
    all_vacancies = []
    for result in results:
        if isinstance(result, list):
            all_vacancies.extend(result)
    logger.info(f"Всього знайдено: {len(all_vacancies)}")
    if not all_vacancies:
        logger.warning("Вакансій не знайдено")
        return
    published = 0
    for vacancy in all_vacancies:
        if published >= MAX_VACANCIES:
            break
        try:
            post_text = format_vacancy(vacancy)
            await bot.send_message(chat_id=CHANNEL_ID, text=post_text)
            published_urls.add(vacancy["link"])
            published += 1
            logger.info(f"✅ Опубліковано: {vacancy['title']}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Помилка публікації: {e}")
    logger.info(f"📢 Опубліковано {published} вакансій")


async def auto_post_loop(bot: Bot):
    while True:
        await collect_and_post(bot)
        logger.info(f"⏰ Наступна публікація через {POST_INTERVAL // 3600} години")
        await asyncio.sleep(POST_INTERVAL)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔨 Привіт! Я @robota_pidrobitok_bot\n/post — опублікувати зараз\n/status — статус")

async def manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Шукаю...")
    await collect_and_post(context.bot)
    await update.message.reply_text("✅ Готово!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 Канал: {CHANNEL_ID}\nЧас: {datetime.now().strftime('%H:%M %d.%m.%Y')}")


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
       
            



    
 
    



