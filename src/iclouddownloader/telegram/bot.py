from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from iclouddownloader.services.runtime_settings_service import get_effective_settings
from iclouddownloader.db.session import get_session_factory
from iclouddownloader.telegram.twofa_handler import TwoFAHandler

logger = logging.getLogger(__name__)


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    text = update.message.text or ""
    db = get_session_factory()()
    try:
        handler = TwoFAHandler(db)
        reply = handler.handle_message(
            update.effective_chat.id,
            text,
            update.effective_user.id if update.effective_user else None,
        )
        if reply:
            await update.message.reply_text(reply)
    finally:
        db.close()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("iCloud Photo Downloader bot. Use /code 123456 for 2FA.")


def build_telegram_app() -> Application | None:
    settings = get_effective_settings()
    if not settings.telegram_enabled or not settings.telegram_bot_token:
        return None
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("code", handle_code))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))
    return app


def run_telegram_bot() -> None:
    app = build_telegram_app()
    if not app:
        logger.info("Telegram bot disabled")
        return
    logger.info("Starting Telegram bot polling")
    app.run_polling(drop_pending_updates=True)


async def run_telegram_bot_async() -> None:
    app = build_telegram_app()
    if not app:
        return
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)  # type: ignore[union-attr]
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await app.updater.stop()  # type: ignore[union-attr]
        await app.stop()
        await app.shutdown()
