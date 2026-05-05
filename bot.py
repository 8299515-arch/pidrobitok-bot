import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from google import genai
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from telegram.error import TelegramError
import os
from dotenv import load_dotenv
import random

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8704316956:AAE1h8MnbwvL35GNeiLEUflTKCUIfhMIKgU")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCQx8bjxFhwCVD1qBGZW3J9MMhEXk7nSnU")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@PodrabotkaKiev_1")

POST_INTERVAL = 3 * 60 * 60
MAX_VACANCIES = 3
published_urls = set()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def get_headers(referer: str = "https://www.google.com/"):
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en-US;q=0.7,en;q=0.6",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Cache-Control": "max-age=0",
    }


async def fetch_html(url: str, referer: str = "https://www.google.com/"):
    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers=get_headers(referer),
        ) as client:
            # Невелика затримка щоб не виглядати як бот
            await asyncio.sleep(random.uniform(1, 3))
            response = await client.get(url)
            logger.info(f"GET {url} -> {response.status_code}")
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"Статус {response.status_code} для {url}")
                return None
    except Exception as e:
        logger.error(f"Помилка завантаження {url}: {e}")
        return None


async def parse_work_ua():
    vacancies = []
    url = "https://www.work.ua/jobs-kyiv-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/"
    html = await fetch_html(url, referer="https://www.work.ua/")
    if not html:
        return vacancies
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".job-link")
    logger.info(f"work.ua: знайдено {len(cards)} карток")
    for card in cards[:10]:
        try:
            title = card.select_one("h2").text.strip() if card.select_one("h2") else "Без назви"
            company = card.select_one(".add-bottom").text.strip() if card.select_one(".add-bottom") else "Не вказано"
            salary = card.select_one(".salary").text.strip() if card.select_one(".salary") else "Договірна"
            href = card.get("href")
            link = f"https://www.work.ua{href}" if href else ""
            if link and link not in published_urls:
                vacancies.append({"title": title, "company": company, "salary": salary, "link": link})
        except Exception:
            pass
    logger.info(f"work.ua: {len(vacancies)} нових вакансій")
    return vacancies


async def parse_olx_ua():
    vacancies = []
    url = "https://www.olx.ua/uk/rabota/stroitelstvo/raznorabochiy/kiev/"
    html = await fetch_html(url, referer="https://www.olx.ua/")
    if not html:
        return vacancies
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("[data-cy='l-card']")
    logger.info(f"olx.ua: знайдено {len(cards)} карток")
    for card in cards[:10]:
        try:
            title = card.select_one("h6").text.strip() if card.select_one("h6") else "Без назви"
            salary = card.select_one("[data-testid='ad-price']").text.strip() if card.select_one("[data-testid='ad-price']") else "Договірна"
            link_el = card.select_one("a")
            href = link_el.get("href", "") if link_el else ""
            link = f"https://www.olx.ua{href}" if href.startswith("/") else href
            if link and link not in published_urls:
                vacancies.append({"title": title, "company": "OLX", "salary": salary, "link": link})
        except Exception:
            pass
    logger.info(f"olx.ua: {len(vacancies)} нових вакансій")
    return vacancies


async def parse_robota_ua():
    """Додаткове джерело - robota.ua"""
    vacancies = []
    url = "https://robota.ua/zapros/%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%BE%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/kyiv"
    html = await fetch_html(url, referer="https://robota.ua/")
    if not html:
        return vacancies
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("alliance-employer-vacancy-short-card")
    logger.info(f"robota.ua: знайдено {len(cards)} карток")
    for card in cards[:10]:
        try:
            title = card.select_one("h2").text.strip() if card.select_one("h2") else "Без назви"
            salary = card.select_one(".salary").text.strip() if card.select_one(".salary") else "Договірна"
            link_el = card.select_one("a")
            href = link_el.get("href", "") if link_el else ""
            link = f"https://robota.ua{href}" if href.startswith("/") else href
            if link and link not in published_urls:
                vacancies.append({"title": title, "company": "Robota.ua", "salary": salary, "link": link})
        except Exception:
            pass
    logger.info(f"robota.ua: {len(vacancies)} нових вакансій")
    return vacancies


def _format_vacancy_sync(vacancy: dict) -> str:
    prompt = f"""Зроби пост для Telegram-каналу про підробіток:
Назва: {vacancy['title']}
Зарплата: {vacancy['salary']}
Посилання: {vacancy['link']}
Використовуй емодзі 💼🔨💰, українська мова, до 100 слів, в кінці посилання."""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"💼 {vacancy['title']}\n💰 {vacancy['salary']}\n🔗 {vacancy['link']}"


async def format_vacancy(vacancy: dict) -> str:
    return await asyncio.to_thread(_format_vacancy_sync, vacancy)


async def collect_and_post_direct(bot):
    logger.info("🔍 Збираємо вакансії...")
    results = await asyncio.gather(
        parse_work_ua(),
        parse_olx_ua(),
        parse_robota_ua(),
        return_exceptions=True
    )
    all_vacancies = []
    for result in results:
        if isinstance(result, list):
            all_vacancies.extend(result)

    logger.info(f"Всього знайдено: {len(all_vacancies)} вакансій")

    if not all_vacancies:
        logger.warning("⚠️ Вакансій не знайдено — всі сайти заблоковані або змінили структуру")
        return

    published = 0
    for vacancy in all_vacancies:
        if published >= MAX_VACANCIES:
            break
        try:
            post_text = await format_vacancy(vacancy)
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=post_text)
            except TelegramError as te:
                logger.error(f"❌ Telegram помилка: {te}")
                continue
            published_urls.add(vacancy["link"])
            published += 1
            logger.info(f"✅ Опубліковано: {vacancy['title']}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Помилка публікації: {e}")
    logger.info(f"📢 Опубліковано {published} вакансій")


async def scheduler(bot):
    await asyncio.sleep(30)
    while True:
        await collect_and_post_direct(bot)
        logger.info(f"⏰ Наступний пост через {POST_INTERVAL // 3600} год.")
        await asyncio.sleep(POST_INTERVAL)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔨 Привіт! Я @robota_pidrobitok_bot\n"
        "/post — опублікувати зараз\n"
        "/status — статус\n"
        "/check — перевірити доступ до каналу"
    )


async def manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Шукаю...")
    await collect_and_post_direct(context.bot)
    await update.message.reply_text("✅ Готово!")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Канал: {CHANNEL_ID}\n"
        f"Час: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"Опубліковано URL: {len(published_urls)}"
    )


async def check_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = await context.bot.get_chat(CHANNEL_ID)
        member = await context.bot.get_chat_member(CHANNEL_ID, context.bot.id)
        await update.message.reply_text(
            f"✅ Канал знайдено: {chat.title}\n"
            f"👤 Статус бота: {member.status}\n"
            f"{'✅ Бот є адміном' if member.status == 'administrator' else '❌ Бот НЕ є адміном!'}"
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ Помилка доступу до каналу: {e}")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", manual_post))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("check", check_channel))

    logger.info("🚀 Бот запущено!")

    async def run():
        async with app:
            await app.start()
            await app.updater.start_polling()
            logger.info("✅ Application running, starting scheduler...")
            await scheduler(app.bot)

    asyncio.run(run())


if __name__ == "__main__":
    main()
