"""
Отправка откликов на HH с обработкой тестовых вопросов (улучшенная)
"""
import re
import time
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from core.logger import logger
from core.prompts import TEST_ANSWER_PROMPT


def apply_to_vacancy(page: Page, vacancy: dict, cover_letter: str, resume: str, ai_client) -> bool:
    logger.info(f"Открываю вакансию: {vacancy['title'][:50]}...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            page.goto(vacancy['url'], timeout=60000)
            page.wait_for_load_state('domcontentloaded')
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning(f"Не смог загрузить вакансию после {max_retries} попыток: {e}")
                return False
            logger.debug(f"Повторная загрузка страницы (попытка {attempt + 2})...")
            time.sleep(5)
    
    time.sleep(3)
    
    btn = None
    selectors = [
        'a[data-qa="vacancy-response-link-top"]',
        'a[data-qa="vacancy-response-link"]',
        'button[data-qa="vacancy-response-button"]',
        'button:has-text("Откликнуться")',
        'button:has-text("Отклик")',
        'a:has-text("Откликнуться")',
        'span:has-text("Откликнуться")'
    ]
    for sel in selectors:
        try:
            btn = page.wait_for_selector(sel, timeout=5000)
            if btn:
                logger.debug(f"Найдена кнопка отклика: {sel}")
                break
        except PlaywrightTimeoutError:
            continue
    
    if not btn:
        logger.warning("Кнопка 'Откликнуться' не найдена")
        return False
    
    try:
        btn.scroll_into_view_if_needed()
        btn.click()
        logger.debug("Кнопка отклика нажата")
        time.sleep(5)   # увеличенная пауза
    except Exception as e:
        logger.warning(f"Не удалось нажать кнопку: {e}")
        return False
    
    # Ждем появления модального окна
    try:
        page.wait_for_selector('div[data-qa="vacancy-response-popup"]', timeout=7000)
        logger.debug("Модальное окно появилось")
    except PlaywrightTimeoutError:
        logger.warning("Модальное окно не появилось, продолжаем...")
    
    try:
        add_letter_btn = page.query_selector('button:has-text("Добавить сопроводительное")')
        if add_letter_btn:
            add_letter_btn.click()
            logger.debug("Нажата кнопка 'Добавить сопроводительное'")
            time.sleep(2)
    except Exception:
        pass

    input_fields = page.query_selector_all('input[type="text"], input[type="textarea"], textarea')
    for field in input_fields:
        try:
            placeholder = field.get_attribute('placeholder') or ''
            label = field.get_attribute('aria-label') or ''
            name = field.get_attribute('name') or ''
            
            current_value = field.input_value() if field.evaluate('el => el.value') else ''
            if current_value:
                continue
            
            combined = (placeholder + label + name).lower()
            question_keywords = ['почему', 'тест', 'задание', 'вопрос', 'ответ', 'why', 'test', 'задача']
            if any(kw in combined for kw in question_keywords):
                prompt = TEST_ANSWER_PROMPT.format(
                    question=placeholder or label or "Почему вы хотите работать у нас?",
                    resume=resume
                )
                answer = ai_client.generate(prompt, max_tokens=150)
                field.fill(answer)
                logger.debug(f"Заполнен тестовый вопрос: {placeholder[:30]}...")
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Не удалось обработать поле вопроса: {e}")
            continue

    textarea = None
    textarea_selectors = [
        'textarea[data-qa="vacancy-response-popup-form-letter-input"]',
        'textarea[data-qa="vacancy-response-letter"]',
        'div[data-qa="vacancy-response-letter"] textarea',
        'form[action*="vacancy_response"] textarea',
        'textarea'
    ]
    for sel in textarea_selectors:
        try:
            textarea = page.wait_for_selector(sel, timeout=5000)
            if textarea:
                logger.debug(f"Найдено поле письма: {sel}")
                break
        except PlaywrightTimeoutError:
            continue
    
    if textarea:
        try:
            textarea.scroll_into_view_if_needed()
            textarea.fill(cover_letter)
            logger.debug("Письмо вставлено")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Не удалось заполнить поле письма: {e}")
    else:
        logger.info("Поле для письма не найдено (возможно, не требуется)")
    
    submit = None
    submit_selectors = [
        'button[data-qa="vacancy-response-submit-popup"]',
        'button:has-text("Отправить")',
        'button:has-text("Откликнуться")',
        'form[action*="vacancy_response"] button[type="submit"]',
        'button[data-qa="vacancy-response-submit"]'
    ]
    for sel in submit_selectors:
        try:
            submit = page.wait_for_selector(sel, timeout=5000)
            if submit:
                logger.debug(f"Найдена кнопка отправки: {sel}")
                break
        except PlaywrightTimeoutError:
            continue
    
    if submit:
        try:
            submit.scroll_into_view_if_needed()
            submit.click()
            logger.debug("Кнопка отправки нажата")
            time.sleep(4)
            
            try:
                page.wait_for_selector('button[data-qa="vacancy-response-submit-popup"]', state='detached', timeout=10000)
                logger.info("✅ Отклик отправлен (модальное окно закрылось)")
                return True
            except PlaywrightTimeoutError:
                success_msg = page.query_selector('div[data-qa="vacancy-response-success"]')
                if success_msg:
                    logger.info("✅ Отклик отправлен (сообщение об успехе)")
                    return True
                error_msg = page.query_selector('div[data-qa="vacancy-response-error"]')
                if error_msg:
                    logger.error(f"Ошибка отправки: {error_msg.inner_text()}")
                    return False
                if not page.query_selector('button[data-qa="vacancy-response-submit-popup"]'):
                    logger.info("✅ Отклик отправлен (кнопка отправки исчезла)")
                    return True
                logger.warning("⚠️ Не удалось подтвердить отправку, считаем неудачей")
                return False
        except Exception as e:
            logger.warning(f"Ошибка при отправке: {e}")
            return False
    else:
        logger.warning("Кнопка 'Отправить' не найдена")
        return False