"""
Авторизация на hh.ru через Playwright
"""
import time
from playwright.sync_api import Page
from core.logger import logger


def login_to_hh(page: Page, phone: str, sms_code_getter) -> bool:
    try:
        logger.info("Открываю страницу авторизации hh.ru...")
        page.goto("https://hh.ru/account/login", timeout=30000)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(3)

        # Шаг 1 — кликаем "Я ищу работу"
        logger.info("Кликаю 'Я ищу работу'...")
        try:
            page.wait_for_selector('text=Я ищу работу', timeout=10000)
            page.click('text=Я ищу работу')
            logger.info("Карточка выбрана!")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Кнопка 'Я ищу работу' не найдена: {e}")

        # Шаг 1.5 — нажимаем кнопку "Войти"
        logger.info("Нажимаю кнопку 'Войти'...")
        try:
            page.wait_for_selector('button:has-text("Войти")', timeout=5000)
            page.click('button:has-text("Войти")')
            logger.info("Нажал 'Войти', жду форму с телефоном...")
            time.sleep(3)
            page.wait_for_load_state('domcontentloaded')
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Кнопка 'Войти' не найдена: {e}")

        # Шаг 2 — вводим номер телефона прямо с клавиатуры
        # Поле уже в фокусе после перехода на страницу
        logger.info(f"Ввожу номер телефона: {phone}")
        time.sleep(1)
        page.keyboard.type(phone, delay=100)
        logger.info(f"✅ Номер введён: {phone}")
        time.sleep(0.5)

        # Нажимаем Enter
        page.keyboard.press('Enter')
        logger.info("Нажал Enter, жду SMS...")
        time.sleep(3)

        # Шаг 3 — ждём SMS код от пользователя
        logger.info("Жду SMS код от пользователя...")
        sms_code = sms_code_getter()

        if not sms_code:
            logger.error("SMS код не получен")
            return False

        # Шаг 4 — вводим SMS код прямо с клавиатуры
        logger.info(f"Ввожу SMS код: {sms_code}")
        time.sleep(1)
        page.keyboard.type(sms_code, delay=100)
        logger.info(f"✅ Код введён: {sms_code}")
        time.sleep(0.5)

        # Нажимаем Enter для подтверждения
        page.keyboard.press('Enter')
        time.sleep(3)

        # Шаг 5 — проверяем авторизацию
        current_url = page.url
        if "login" not in current_url:
            logger.info("✅ Авторизация успешна!")
            return True
        else:
            page.screenshot(path="auth_debug_final.png")
            logger.error(f"❌ Авторизация не прошла, URL: {current_url}")
            return False

    except Exception as e:
        logger.exception(f"Ошибка при авторизации: {e}")
        return False