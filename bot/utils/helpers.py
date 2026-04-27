import asyncio
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from config.settings import TELEGRAM_BOT_TOKEN
from core.logger import logger

user_sessions_active = {}
user_stop_flags = {}
user_manual_mode = {}
user_decision_events = {}

pending_vacancies = {}
manual_decisions = {}

PROXY_URL = "socks5://qWshEM:9qau5X@85.195.81.131:11412"

start_session_func = None
stop_session_func = None

auth_events = {}
auth_data = {}

current_page = None
current_ai_client = None
current_resume = None

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
    return user_manual_mode.get(telegram_id, False)


def get_user_session_active(telegram_id: int) -> bool:
    return user_sessions_active.get(telegram_id, False)


def get_user_decision_event(telegram_id: int) -> threading.Event:
    if telegram_id not in user_decision_events:
        user_decision_events[telegram_id] = threading.Event()
    return user_decision_events[telegram_id]


async def send_message(update: Update, text: str, reply_markup=None, parse_mode="Markdown"):
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

    mode_text = "🟡 Ручной" if manual_mode else "🟢 Авто"
    start_stop_text = "⏸️ Остановить" if session_active else "▶️ Запустить отклики"
    keyboard = get_main_keyboard(start_stop_text, mode_text)

    text = (
        "🤖 *HH Bot Pro*\n\n"
        f"Статус: {'🟢 Запущен' if session_active else '🔴 Остановлен'}\n"
        f"Режим: {'🟡 Ручной' if manual_mode else '🟢 Авто'}\n\n"
        "Выбери действие:"
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def send_vacancy_card(chat_id: int, vacancy: dict, letter: str, revaz_score: int, revaz_reason: str):
    if not telegram_bot:
        logger.error("telegram_bot не инициализирован")
        return None

    def escape(text: str) -> str:
        for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(ch, f'\\{ch}')
        return text

    letter_preview = letter[:1000] + "..." if len(letter) > 1000 else letter
    vacancy_url = vacancy.get('url', f"https://hh.ru/vacancy/{vacancy['id']}")

    title = escape(vacancy['title'][:60])
    company = escape(vacancy.get('company', 'Не указана'))
    area = escape(vacancy.get('area', 'Не указан'))
    reason = escape(revaz_reason[:250])
    letter_escaped = escape(letter_preview)

    if revaz_score >= 70:
        match_emoji = "🟢"
    elif revaz_score >= 40:
        match_emoji = "🟡"
    else:
        match_emoji = "🔴"

    text = (
        f"🎯 [{title}]({vacancy_url})\n\n"
        f"🏢 {company}\n"
        f"📍 {area}\n"
        f"📊 Вероятность матча: {match_emoji} {revaz_score}%\n"
        f"💡 {reason}\n\n"
        f"📝 Письмо:\n{letter_escaped}"
    )

    from bot.keyboards.main import get_vacancy_card_keyboard
    keyboard = get_vacancy_card_keyboard(vacancy['id'])

    try:
        msg = await telegram_bot.send_message(
            chat_id, text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Ошибка отправки карточки: {e}")
        msg = await telegram_bot.send_message(
            chat_id,
            f"🎯 {vacancy['title'][:60]}\n"
            f"🏢 {vacancy.get('company','Не указана')}\n"
            f"📍 {vacancy.get('area','Не указан')}\n"
            f"📊 Вероятность матча: {revaz_score}%\n"
            f"💡 {revaz_reason[:150]}\n\n"
            f"📝 Письмо:\n{letter[:500]}",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    pending_vacancies[vacancy['id']] = {
        'vacancy': vacancy,
        'letter': letter,
        'message_id': msg.message_id,
        'chat_id': chat_id,
        'revaz_score': revaz_score,
        'revaz_reason': revaz_reason
    }
    return msg


async def send_auto_apply_card(chat_id: int, vacancy: dict, letter: str, revaz_score: int = 0, revaz_reason: str = ""):
    """Отправляет карточку об успешном авто-отклике с вероятностью матча"""
    if not telegram_bot:
        return
    vacancy_url = vacancy.get('url', f"https://hh.ru/vacancy/{vacancy['id']}")

    if revaz_score >= 70:
        match_emoji = "🟢"
    elif revaz_score >= 40:
        match_emoji = "🟡"
    else:
        match_emoji = "🔴"

    text = (
        f"✅ Отклик отправлен (авто)\n\n"
        f"🎯 {vacancy['title'][:60]}\n"
        f"🏢 {vacancy.get('company', 'Не указана')}\n"
        f"📍 {vacancy.get('area', 'Не указан')}\n"
        f"📊 Вероятность матча: {match_emoji} {revaz_score}%\n"
        f"💡 {revaz_reason[:150]}\n\n"
        f"📝 Письмо:\n{letter[:500]}"
    )
    await telegram_bot.send_message(chat_id, text, disable_web_page_preview=True)