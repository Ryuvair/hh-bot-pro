"""Проверка работоспособности модулей"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import BASE_DIR, LOGS_DIR
from core.logger import logger, log_startup
from core.ai_client import get_ai_client
from core.browser import launch_browser

log_startup()

# Проверяем AI
try:
    ai = get_ai_client()
    if ai.is_available():
        response = ai.generate("Скажи 'Привет, мир!' одним словом", max_tokens=20)
        logger.info(f"✅ AI тест пройден: {response}")
    else:
        logger.error("❌ AI не настроен")
except Exception as e:
    logger.error(f"❌ AI ошибка: {e}")

# Проверяем браузер
try:
    with launch_browser() as page:
        page.goto("https://hh.ru")
        logger.info(f"✅ Браузер открыл HH: {page.title()}")
except Exception as e:
    logger.error(f"❌ Ошибка браузера: {e}")

logger.info("Тест завершён")