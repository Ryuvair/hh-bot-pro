"""
HH Bot Pro — многопользовательский с динамическим поиском и ручным режимом
"""
import time
import threading
from dotenv import load_dotenv
load_dotenv()

from core.logger import logger, log_startup, log_shutdown
from core.session_manager import session_manager
from config.settings import TELEGRAM_BOT_TOKEN
from bot.bot import run_telegram_bot
import bot.utils.helpers as tb_helpers


def start_session(telegram_id: int, job_title: str, limit: int, custom_url: str = None) -> bool:
    """Функция для вызова из Telegram бота"""
    return session_manager.start_session(telegram_id, job_title, limit, custom_url)


def stop_session(telegram_id: int):
    """Функция для вызова из Telegram бота"""
    session_manager.stop_session(telegram_id)


def main():
    log_startup()
    # Передаём функции в хелперы, чтобы бот мог их вызывать
    tb_helpers.set_session_handlers(start_session, stop_session)

    if TELEGRAM_BOT_TOKEN:
        telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        telegram_thread.start()
        logger.info("Telegram бот запущен в фоне")

    if not tb_helpers.loop_ready.wait(timeout=10):
        logger.error("Таймаут ожидания готовности Telegram loop")
        return

    if not tb_helpers.telegram_loop:
        logger.error("telegram_loop всё ещё None после loop_ready!")
        return

    logger.info(f"Telegram loop готов: {id(tb_helpers.telegram_loop)}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Завершение работы")
    finally:
        log_shutdown(0)


if __name__ == "__main__":
    main()