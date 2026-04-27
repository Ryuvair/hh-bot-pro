"""
Парсинг вакансий с HH.ru с пагинацией, учётом истории и статусными сообщениями
"""
import re
import time
import asyncio
from playwright.sync_api import Page
from core.logger import logger
from storage.history_repository import get_applied_ids
import bot.utils.helpers as tb


def collect_vacancies_from_url(page: Page, url: str, telegram_id: int, chat_id: int, max_pages: int = 3) -> list:
    """
    Собирает вакансии с нескольких страниц поиска.
    Возвращает список словарей с id, title, url, company, salary, area.
    """
    all_vacancies = []
    seen_ids = set()
    applied_ids = get_applied_ids(telegram_id)

    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            page_url = url
        else:
            if '?' in url:
                page_url = f"{url}&page={page_num}"
            else:
                page_url = f"{url}?page={page_num}"

        logger.info(f"Загружаю страницу поиска {page_num}: {page_url[:60]}...")

        if tb.telegram_loop and chat_id:
            asyncio.run_coroutine_threadsafe(
                tb.telegram_bot.send_message(chat_id, f"🔍 Собираю вакансии (страница {page_num})…"),
                tb.telegram_loop
            )

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

        for _ in range(3):
            page.keyboard.press("PageDown")
            time.sleep(1)

        vacancy_items = page.query_selector_all('div[data-qa="vacancy-serp__vacancy"]')
        if not vacancy_items:
            vacancy_items = page.query_selector_all('div.vacancy-serp-item__layout')

        page_vacancies = 0

        for item in vacancy_items:
            try:
                title_el = item.query_selector('a[data-qa="serp-item__title"]')
                if not title_el:
                    title_el = item.query_selector('a[href*="/vacancy/"]')
                if not title_el:
                    continue

                href = title_el.get_attribute('href')
                if not href:
                    continue

                match = re.search(r'/vacancy/(\d+)', href)
                if not match:
                    continue

                vac_id = match.group(1)
                if vac_id in applied_ids or vac_id in seen_ids:
                    continue

                title = title_el.inner_text().strip()
                if not title:
                    continue

                # Компания
                company = 'Не указана'
                company_el = item.query_selector('a[data-qa="vacancy-serp__vacancy-employer"]')
                if not company_el:
                    company_el = item.query_selector('span[data-qa="vacancy-serp__vacancy-employer"]')
                if company_el:
                    company = company_el.inner_text().strip() or 'Не указана'

                # Зарплата
                salary = 'Не указана'
                salary_selectors = [
                    'span[data-qa="vacancy-serp__vacancy-compensation"]',
                    'span[data-qa="vacancy-serp__vacancy-compensation-range"]',
                    'div[data-qa="vacancy-serp__vacancy-compensation"]',
                ]
                for sel in salary_selectors:
                    salary_el = item.query_selector(sel)
                    if salary_el:
                        text = salary_el.inner_text().strip()
                        if text:
                            salary = text
                            break

                # Город
                area = 'Не указан'
                area_el = item.query_selector('span[data-qa="vacancy-serp__vacancy-address"]')
                if not area_el:
                    area_el = item.query_selector('div[data-qa="vacancy-serp__vacancy-address"]')
                if area_el:
                    area = area_el.inner_text().strip().split(',')[0] or 'Не указан'

                seen_ids.add(vac_id)
                all_vacancies.append({
                    'id': vac_id,
                    'title': title,
                    'url': f"https://hh.ru/vacancy/{vac_id}",
                    'company': company,
                    'salary': salary,
                    'area': area,
                })
                page_vacancies += 1

            except Exception as e:
                logger.debug(f"Ошибка парсинга карточки: {e}")
                continue

        logger.info(f"Страница {page_num}: найдено новых вакансий: {page_vacancies}")

        next_button = page.query_selector('a[data-qa="pager-next"]')
        if not next_button:
            logger.info("Достигнут конец пагинации")
            break

        time.sleep(3)

    logger.info(f"Всего найдено вакансий: {len(all_vacancies)}")
    return all_vacancies


def get_vacancy_description(page: Page, url: str) -> tuple:
    """
    Загружает страницу вакансии и возвращает (описание, зарплата, компания, город).
    """
    try:
        page.goto(url, timeout=60000)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(2)

        # Описание
        description = ""
        desc_el = page.query_selector('div[data-qa="vacancy-description"]')
        if desc_el:
            description = desc_el.inner_text()

        # Зарплата через JS — склеивает все фрагменты текста
        salary = 'Не указана'
        salary_el = page.query_selector('span[data-qa="vacancy-salary-compensation-type-net"]')
        if not salary_el:
            salary_el = page.query_selector('span[data-qa="vacancy-salary-compensation-type-gross"]')
        if salary_el:
            text = page.evaluate('el => el.innerText', salary_el)
            text = text.strip().replace('\u202f', ' ').replace('\xa0', ' ')
            if text:
                salary = text
                logger.info(f"💰 Зарплата: {salary}")

        if salary == 'Не указана':
            logger.info(f"💰 Зарплата не найдена на {url}")

        # Компания
        company = 'Не указана'
        company_el = page.query_selector('a[data-qa="vacancy-company-name"]')
        if company_el:
            company = company_el.inner_text().strip()

        # Город
        area = 'Не указан'
        area_el = page.query_selector('p[data-qa="vacancy-view-location"]')
        if not area_el:
            area_el = page.query_selector('span[data-qa="vacancy-view-raw-address"]')
        if area_el:
            area = area_el.inner_text().strip().split(',')[0]

        logger.info(f"📊 Данные: зп={salary}, компания={company}, город={area}")
        return description, salary, company, area

    except Exception as e:
        logger.warning(f"Не удалось получить данные вакансии {url}: {e}")
    return "", 'Не указана', 'Не указана', 'Не указан'