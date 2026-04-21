import asyncio
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config.settings import TELEGRAM_BOT_TOKEN
from core.logger import logger
import bot.utils.helpers as tb_helpers
from bot.handlers.commands import start, cancel, help_command
from bot.handlers.callbacks import button_handler
from bot.handlers.messages import handle_all_text


def run_telegram_bot():
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram токен не настроен.")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tb_helpers.telegram_loop = loop

    try:
        application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .proxy_url(tb_helpers.PROXY_URL)
            .get_updates_proxy_url(tb_helpers.PROXY_URL)
            .build()
        )
        tb_helpers.telegram_bot = application.bot
        tb_helpers.loop_ready.set()
    except Exception as e:
        logger.error(f"Не удалось создать Application: {e}")
        return

    # Установка команд для нативного меню
    loop.run_until_complete(
        application.bot.set_my_commands([
            ("start", "Главное меню"),
            ("help", "Помощь и инструкция"),
            ("cancel", "Отменить действие"),
        ])
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_text))

    logger.info(f"✅ Telegram бот запущен через прокси {tb_helpers.PROXY_URL}")
    loop.run_until_complete(application.run_polling(drop_pending_updates=True))