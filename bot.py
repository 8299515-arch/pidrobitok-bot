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


async def fetch_html(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            return response.text
    except Exception as e:
        logger.error(f"Ошибка загрузки {url}: {e}")
        return None


async def parse_work_ua():
    vacancies = []
    html = await fetch_html("https://www.work.ua/jobs-%D1%80%D1%96%D0%B7%D0%BD%D0%BE%D1%80%D0%B0%D0%B1%D0%BE%D1%87%D0%B8%D0%B9/")
    if not html:
        return vacancies
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select(".job-link")[:10]:
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
    return vacancies


async def parse_olx_ua():
    vacancies = []
    html = await fetch_html("https://www.olx.ua/uk/rabota/raznorabochie/")
    if not html:
        return vacancies
    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select("[data-cy='l-card']")[:10]:
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
    return vacancies


# ✅ ВИПРАВЛЕНО: обгорнуто в asyncio.to_thread щоб не блокувати event loop
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


async def collect_and_post(context: ContextTypes.DEFAULT_TYPE):
    logger.info("🔍 Збираємо вакансії...")
    results = await asyncio.gather(parse_work_ua(), parse_olx_ua(), return_exceptions=True)
    all_vacancies = []
    for result in results:
        if isinstance(result, list):
            all_vacancies.extend(result)
    if not all_vacancies:
        logger.warning("Вакансій не знайдено")
        return
    published = 0
    for vacancy in all_vacancies:
        if published >= MAX_VACANCIES:
            break
        try:
            post_text = await format_vacancy(vacancy)  # ✅ ВИПРАВЛЕНО: тепер await

            # ✅ ВИПРАВЛЕНО: явна обробка помилок Telegram з детальним логуванням
            try:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=post_text)
            except TelegramError as te:
                logger.error(f"❌ Telegram не може надіслати повідомлення в {CHANNEL_ID}: {te}")
                logger.error("Перевірте: 1) Бот є адміном каналу, 2) CHANNEL_ID правильний (формат @username або -100...)")
                continue

            published_urls.add(vacancy["link"])
            published += 1
            logger.info(f"✅ Опубліковано: {vacancy['title']}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Помилка публікації: {e}")
    logger.info(f"📢 Опубліковано {published} вакансій")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔨 Привіт! Я @robota_pidrobitok_bot\n"
        "/post — опублікувати зараз\n"
        "/status — статус\n"
        "/check — перевірити доступ до каналу"
    )


async def manual_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Шукаю...")
    await collect_and_post(context)
    await update.message.reply_text("✅ Готово!")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Канал: {CHANNEL_ID}\n"
        f"Час: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"Опубліковано URL: {len(published_urls)}"
    )


# ✅ НОВА КОМАНДА: перевірити чи бот має доступ до каналу
async def check_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = await context.bot.get_chat(CHANNEL_ID)
        member = await context.bot.get_chat_member(CHANNEL_ID, context.bot.id)
        await update.message.reply_text(
            f"✅ Канал знайдено: {chat.title}\n"
            f"👤 Статус бота: {member.status}\n"
            f"{'✅ Бот є адміном' if member.status == 'administrator' else '❌ Бот НЕ є адміном — додайте як адміністратора!'}"
        )
    except TelegramError as e:
        await update.message.reply_text(
            f"❌ Помилка доступу до каналу: {e}\n\n"
            f"Перевірте:\n"
            f"1. Бот доданий в канал\n"
            f"2. Бот має права адміністратора\n"
            f"3. CHANNEL_ID правильний: {CHANNEL_ID}"
        )


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # ✅ ВИПРАВЛЕНО: job_queue потребує пакет python-telegram-bot[job-queue]
    if app.job_queue:
        app.job_queue.run_repeating(collect_and_post, interval=POST_INTERVAL, first=30)
        logger.info(f"⏰ Авто-постинг кожні {POST_INTERVAL // 3600} год.")
    else:
        logger.warning("⚠️ job_queue недоступний! Встановіть: pip install 'python-telegram-bot[job-queue]'")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("post", manual_post))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("check", check_channel))  # ✅ НОВА КОМАНДА

    logger.info("🚀 Бот запущено!")
    app.run_polling()


if __name__ == "__main__":
    main()
   
  
