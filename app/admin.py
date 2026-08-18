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

        args = [arg.strip() for arg in context.args if arg.strip()]
        if args:
            await self._handle_command(update, args)
            return

        stats = self._storage.get_admin_stats()
        await update.message.reply_text(
            "🛠 Админ-панель\n\n"
            f"👥 Пользователей: {stats['users']}\n"
            f"💼 Вакансий: {stats['jobs']}\n"
            f"🔔 Мониторингов: {stats['searches']}\n"
            f"📨 Доставок: {stats['deliveries']}\n"
            f"📢 Активных каналов: {stats['channels']}\n"
            f"⏸ Отключённых каналов: {stats['disabled_channels']}\n"
            f"🗂 Каналов с вакансиями в базе: {stats['job_channels']}\n\n"
            f"🕐 Последняя вакансия: {stats['last_job'] or 'нет данных'}\n\n"
            "📢 Каналы:\n"
            "/admin channels — список\n"
            "/admin add_channel @channel — добавить\n"
            "/admin remove_channel @channel — отключить\n"
            "/admin enable_channel @channel — включить"
        )

    async def _handle_command(self, update: Update, args: list[str]) -> None:
        if update.message is None:
            return

        command = args[0].casefold()
        if command in {"channels", "channel", "каналы"}:
            await self._reply_channels(update)
            return
        if command in {"add_channel", "add-channel", "add"}:
            await self._reply_add_channel(update, args[1:])
            return
        if command in {"remove_channel", "remove-channel", "remove", "disable_channel", "disable-channel", "disable"}:
            await self._reply_set_channel_enabled(update, args[1:], enabled=False)
            return
        if command in {"enable_channel", "enable-channel", "enable"}:
            await self._reply_set_channel_enabled(update, args[1:], enabled=True)
            return

        await update.message.reply_text(
            "Неизвестная команда админ-панели.\n\n"
            "Доступно:\n"
            "/admin channels\n"
            "/admin add_channel @channel\n"
            "/admin remove_channel @channel\n"
            "/admin enable_channel @channel"
        )

    async def _reply_channels(self, update: Update) -> None:
        if update.message is None:
            return

        channels = self._storage.list_telegram_channels()
        if not channels:
            await update.message.reply_text(
                "📢 Каналы пока не добавлены.\n\n"
                "Добавить: /admin add_channel @channel"
            )
            return

        lines = ["📢 Telegram-каналы:"]
        for index, channel in enumerate(channels, start=1):
            status = "активен" if channel["enabled"] else "отключён"
            lines.append(
                f"{index}. @{channel['username']} — {status}, вакансий в базе: {channel['jobs']}"
            )
        lines.append("")
        lines.append("Добавить: /admin add_channel @channel")
        lines.append("Отключить: /admin remove_channel @channel")
        lines.append("Включить: /admin enable_channel @channel")
        await update.message.reply_text("\n".join(lines), disable_web_page_preview=True)

    async def _reply_add_channel(self, update: Update, args: list[str]) -> None:
        if update.message is None:
            return
        if not args:
            await update.message.reply_text("Формат: /admin add_channel @channel")
            return
        try:
            username, created = self._storage.add_telegram_channel(args[0])
        except ValueError:
            await update.message.reply_text("Канал должен быть публичным username, например @channel_name.")
            return

        action = "добавлен" if created else "включён"
        await update.message.reply_text(f"✅ Канал @{username} {action}.")

    async def _reply_set_channel_enabled(self, update: Update, args: list[str], *, enabled: bool) -> None:
        if update.message is None:
            return
        if not args:
            action = "enable_channel" if enabled else "remove_channel"
            await update.message.reply_text(f"Формат: /admin {action} @channel")
            return
        try:
            updated = self._storage.set_telegram_channel_enabled(args[0], enabled)
        except ValueError:
            await update.message.reply_text("Канал должен быть публичным username, например @channel_name.")
            return

        if not updated:
            await update.message.reply_text("Канал не найден. Сначала добавь его через /admin add_channel @channel.")
            return
        username = SQLiteStorage.normalize_telegram_channel(args[0])
        status = "включён" if enabled else "отключён"
        await update.message.reply_text(f"✅ Канал @{username} {status}.")
