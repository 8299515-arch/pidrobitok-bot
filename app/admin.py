from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.config import Settings
from app.storage import SQLiteStorage


class AdminService:
    def __init__(self, settings: Settings, storage: SQLiteStorage) -> None:
        self._admin_user_ids = settings.admin_user_ids
        self._storage = storage

    def is_admin(self, user_id: int) -> bool:
        return user_id in self._admin_user_ids

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None or update.effective_user is None:
            return
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Доступ запрещён.")
            return

        stats = self._storage.get_admin_stats()
        await update.message.reply_text(
            "🛠 Админ-панель\n\n"
            f"👥 Пользователей: {stats['users']}\n"
            f"💼 Вакансий: {stats['jobs']}\n"
            f"🔔 Мониторингов: {stats['searches']}\n"
            f"📨 Доставок: {stats['deliveries']}\n"
            f"📢 Каналов: {stats['channels']}\n\n"
            f"🕐 Последняя вакансия: {stats['last_job'] or 'нет данных'}"
        )
