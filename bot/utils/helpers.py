import os
import asyncio
import threading
from telegram import Update
from config.settings import TELEGRAM_BOT_TOKEN
from core.logger import logger

# Глобальные переменные для многопользовательской работы
user_sessions_active = {}        # telegram_id -> bool
user_stop_flags = {}             # telegram_id -> bool
user_manual_mode = {}            # telegram_id -> bool
user_decision_events = {}        # telegram_id -> threading.Event (создаётся при необходимости)

pending_vacancies = {}           # vac_id -> контекст для ручного режима
manual_decisions = {}            # vac_id -> решение (apply/skip/regen)

# Прокси
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None

# Функции запуска/остановки сессий (устанавливаются из main.py)
start_session_func = None
stop_session_func = None

# Глобальные объекты, общие для всех сессий (но используемые только внутри потоков)
current_page = None
current_ai_client = None
current_resume = None

# Telegram-специфичные
telegram_loop = None
telegram_bot = None
loop_ready = threading.Event()


def set_global_page(page):
    global current_page
    current_page = page


def set_global_ai_client(ai_client):
    global current_ai_client
    current_ai_client = ai_client


def set_global_resume(resume_text):
    global current_resume
    current_resume = resume_text


def set_session_handlers(start_func, stop_func):
    global start_session_func, stop_session_func
    start_session_func = start_func
    stop_session_func = stop_func


def get_user_manual_mode(telegram_id: int) -> bool:
    """Возвращает ручной режим для конкретного пользователя"""
    return user_manual_mode.get(telegram_id, False)


def get_user_session_active(telegram_id: int) -> bool:
    """Проверяет, активна ли сессия у пользователя"""
    return user_sessions_active.get(telegram_id, False)


def get_user_decision_event(telegram_id: int) -> threading.Event:
    """Возвращает событие для ожидания решения пользователя (создаёт при необходимости)"""
    if telegram_id not in user_decision_events:
        user_decision_events[telegram_id] = threading.Event()
    return user_decision_events[telegram_id]


async def send_message(update: Update, text: str, reply_markup=None, parse_mode="Markdown"):
    """Отправляет новое сообщение (без повторов)"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)


async def show_main_menu(update: Update, context):
    from bot.keyboards.main import get_main_keyboard
    user_id = update.effective_user.id
    manual_mode = get_user_manual_mode(user_id)
    session_active = get_user_session_active(user_id)

    mode_text = "🟢 Авто" if not manual_mode else "🟡 Ручной"
    start_stop_text = "⏸️ Остановить" if session_active else "▶️ Запустить отклики"
    keyboard = get_main_keyboard(start_stop_text, mode_text)

    text = (
        "🤖 *HH Bot Pro*\n\n"
        f"Статус: {'🟢 Запущен' if session_active else '🔴 Остановлен'}\n"
        f"Режим: {'🟢 Автоматический' if not manual_mode else '🟡 Ручной (подтверждение)'}\n\n"
        "Выбери действие:"
    )
    await send_message(update, text, keyboard)


async def send_vacancy_card(chat_id: int, vacancy: dict, letter: str, revaz_score: int, revaz_reason: str):
    if not telegram_bot:
        logger.error("telegram_bot не инициализирован")
        return None

    def escape(text: str) -> str:
        # Экранируем спецсимволы Markdown, чтобы карточки не ломались на вакансиях/компаниях с символами вроде '_' и '*'
        for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(ch, f'\\{ch}')
        return text

    stars = "⭐" * (revaz_score // 2) + "☆" * (5 - revaz_score // 2)
    letter_preview = letter[:1000] + "..." if len(letter) > 1000 else letter
    # Формируем ссылку на вакансию
    vacancy_url = vacancy.get('url', f"https://hh.ru/vacancy/{vacancy['id']}")

    # Экранируем все поля кроме ссылки
    title = escape(vacancy['title'][:60])
    company = escape(vacancy.get('company', 'Не указана'))
    area = escape(vacancy.get('area', 'Не указан'))
    salary = escape(vacancy.get('salary', 'Не указана'))
    reason = escape(revaz_reason[:100])
    letter_preview = escape(letter_preview)

    text = (
        f"🎯 *[{title}]({vacancy_url})*\n\n"
        f"🏢 {company}\n"
        f"📍 {area}\n"
        f"💰 {salary}\n"
        f"📊 Релевантность: {revaz_score}/10 {stars}\n"
        f"💡 {reason}\n\n"
        f"📝 *Письмо:*\n{letter_preview}"
    )
    from bot.keyboards.main import get_vacancy_card_keyboard
    keyboard = get_vacancy_card_keyboard(vacancy['id'])
    msg = await telegram_bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)
    pending_vacancies[vacancy['id']] = {
        'vacancy': vacancy,
        'letter': letter,
        'message_id': msg.message_id,
        'chat_id': chat_id,
        'revaz_score': revaz_score,
        'revaz_reason': revaz_reason
    }
    return msg


async def send_auto_apply_card(chat_id: int, vacancy: dict, letter: str):
    """Отправляет информационную карточку об успешном авто-отклике"""
    if not telegram_bot:
        return
    vacancy_url = vacancy.get('url', f"https://hh.ru/vacancy/{vacancy['id']}")
    def escape(text: str) -> str:
        for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(ch, f'\\{ch}')
        return text

    title = escape(vacancy['title'][:60])
    company = escape(vacancy.get('company', 'Не указана'))
    area = escape(vacancy.get('area', 'Не указан'))
    salary = escape(vacancy.get('salary', 'Не указана'))
    letter_preview = escape((letter[:1000] + "...") if len(letter) > 1000 else letter)
    text = (
        f"✅ *Отклик отправлен (авто)*\n\n"
        f"🎯 *[{title}]({vacancy_url})*\n"
        f"🏢 {company}\n"
        f"📍 {area}\n"
        f"💰 {salary}\n\n"
        f"📝 *Письмо:*\n{letter_preview}"
    )
    await telegram_bot.send_message(chat_id, text, parse_mode="Markdown", disable_web_page_preview=True)