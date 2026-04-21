import subprocess
import time
from pathlib import Path
from contextlib import contextmanager
from playwright.sync_api import sync_playwright
from config.settings import CHROME_PATH, TIMEOUT, BASE_DIR
from core.logger import logger


def get_user_profile_path(telegram_id: int) -> str:
    """Возвращает путь к папке профиля Chrome для пользователя"""
    profile_dir = BASE_DIR / "chrome_profiles" / str(telegram_id)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return str(profile_dir)


@contextmanager
def launch_browser(telegram_id: int = None, headless: bool = False):
    """
    Запускает браузер с профилем пользователя.
    Если telegram_id не указан, используется профиль по умолчанию.
    """
    if telegram_id:
        user_data_dir = get_user_profile_path(telegram_id)
    else:
        user_data_dir = str(BASE_DIR / "chrome_profile")
        # Убедимся, что папка существует
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f"Запуск браузера с профилем: {user_data_dir}")

    # Не убиваем все Chrome, чтобы не мешать другим сессиям
    # subprocess.run("taskkill /f /im chrome.exe 2>nul", shell=True)
    # time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            slow_mo=800,
            executable_path=CHROME_PATH,
            viewport={'width': 1280, 'height': 800},
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage'
            ]
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.set_default_timeout(TIMEOUT)

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        logger.info("Браузер запущен")
        try:
            yield page
        finally:
            logger.info("Закрытие браузера...")
            try:
                browser.close()
            except Exception:
                pass