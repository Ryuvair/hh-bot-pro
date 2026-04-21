"""
Парсинг вакансий с HH.ru с пагинацией, учётом истории и статусными сообщениями
"""
import re
import time
import asyncio
from playwright.sync_api import Page
from core.logger import logger
from storage.history_repository import get_applied_ids
import bot.utils.helpers as tb   # <-- ИЗМЕНЁН ИМПОРТ


def collect_vacancies_from_url(page: Page, url: str, telegram_id: int, chat_id: int, max_pages: int = 3) -> list:
    """
    Собирает вакансии с нескольких страниц поиска.
    Возвращает список словарей с id, title, url.
    max_pages — сколько страниц просмотреть.
    """
    all_vacancies = []
    seen_ids = set()
    applied_ids = get_applied_ids(telegram_id)

    for page_num in range(1, max_pages + 1):
        # Формируем URL с номером страницы
        if page_num == 1:
            page_url = url
        else:
            if '?' in url:
                page_url = f"{url}&page={page_num}"
            else:
                page_url = f"{url}?page={page_num}"

        logger.info(f"Загружаю страницу поиска {page_num}: {page_url[:60]}...")

        # Отправляем статус в Telegram
        if tb.telegram_loop and chat_id:
            asyncio.run_coroutine_threadsafe(
                tb.telegram_bot.send_message(chat_id, f"🔍 Собираю вакансии (страница {page_num})…"),
                tb.telegram_loop
            )

        # Повторные попытки загрузки
        max_retries = 3
        for attempt in range(max_retries):
            try:
                page.goto(page_url, timeout=90000)
                page.wait_for_load_state('domcontentloaded')
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.warning(f"Не смог загрузить страницу {page_num} после {max_retries} попыток: {e}")
                    return all_vacancies
                logger.debug(f"Повторная загрузка страницы {page_num} (попытка {attempt+2})...")
                time.sleep(5)

        time.sleep(3)

        # Скроллим для подгрузки
        for _ in range(3):
            page.keyboard.press("PageDown")
            time.sleep(1)

        # Ищем карточки вакансий
        cards = page.query_selector_all('a[data-qa="serp-item__title"]')
        if not cards:
            cards = page.query_selector_all('a.bloko-link[href*="/vacancy/"]')
        if not cards:
            cards = page.query_selector_all('div.vacancy-serp-item a[href*="/vacancy/"]')

        page_vacancies = 0
        for card in cards:
            href = card.get_attribute('href')
            if not href:
                continue
            match = re.search(r'/vacancy/(\d+)', href)
            if match:
                vac_id = match.group(1)
                if vac_id in applied_ids:
                    continue
                if vac_id not in seen_ids:
                    seen_ids.add(vac_id)
                    title = card.inner_text().strip()
                    if title:
                        all_vacancies.append({
                            'id': vac_id,
                            'title': title,
                            'url': f"https://hh.ru/vacancy/{vac_id}"
                        })
                        page_vacancies += 1

        logger.info(f"Страница {page_num}: найдено новых вакансий: {page_vacancies}")

        # Проверяем, есть ли следующая страница
        next_button = page.query_selector('a[data-qa="pager-next"]')
        if not next_button:
            logger.info("Достигнут конец пагинации")
            break

        time.sleep(3)

    logger.info(f"Всего найдено вакансий: {len(all_vacancies)}")
    return all_vacancies


def get_vacancy_description(page: Page, url: str) -> str:
    """
    Загружает страницу вакансии и возвращает текст описания.
    """
    try:
        page.goto(url, timeout=60000)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(2)
        desc = page.query_selector('div[data-qa="vacancy-description"]')
        if desc:
            return desc.inner_text()
    except Exception as e:
        logger.warning(f"Не удалось получить описание вакансии {url}: {e}")
    return ""