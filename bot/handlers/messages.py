import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import bot.utils.helpers as tb_helpers
import storage.database as db
from core.logger import logger
from bot.keyboards.main import get_analysis_keyboard
from core.async_executor import run_in_thread

MENU_BUTTONS = {
    "📊 Статистика": "stats",
    "📄 Резюме": "resume_menu",
    "📌 Должности": "jobs_menu",
    "🔗 По ссылке": "start_by_url",
    "🔐 Авторизация hh.ru": "start_hh_login",
    "🔄 Режим": "toggle_mode",
}


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    user_id = update.effective_user.id
    text = update.message.text.strip()

    logger.info(f"📥 Получено сообщение от {user_id}, state={state}, текст: {text}")

    if state not in ('awaiting_resume', 'awaiting_job', 'awaiting_limit',
                     'awaiting_custom_letter', 'awaiting_job_url', 'awaiting_search_url',
                     'awaiting_limit_for_url', 'awaiting_phone', 'awaiting_sms'):

        if text in ("▶️ Запустить отклики", "⏸️ Остановить"):
            await handle_toggle_session(update, context, user_id)
            return

        if text in MENU_BUTTONS:
            await handle_menu_action(update, context, user_id, MENU_BUTTONS[text])
            return

    if state == 'awaiting_resume':
        await process_resume(update, context, user_id, text)
    elif state == 'awaiting_job':
        await process_job(update, context, user_id, text)
    elif state == 'awaiting_limit':
        await process_limit(update, context, user_id, text)
    elif state == 'awaiting_custom_letter':
        await process_custom_letter(update, context, user_id, text)
    elif state == 'awaiting_job_url':
        await process_job_url(update, context, user_id, text)
    elif state == 'awaiting_search_url':
        await process_search_url(update, context, user_id, text)
    elif state == 'awaiting_limit_for_url':
        await process_limit_for_url(update, context, user_id, text)
    elif state == 'awaiting_phone':
        await process_phone(update, context, user_id, text)
    elif state == 'awaiting_sms':
        await process_sms(update, context, user_id, text)
    else:
        await update.message.reply_text("Используйте кнопки меню для навигации.")


async def handle_toggle_session(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    session_active = tb_helpers.get_user_session_active(user_id)

    if session_active:
        if tb_helpers.stop_session_func:
            tb_helpers.stop_session_func(user_id)
            tb_helpers.user_sessions_active[user_id] = False
        await update.message.reply_text("🔴 Сессия остановлена.")
        await tb_helpers.show_main_menu(update, context)
    else:
        user = await db.AsyncDatabase.get_user(user_id)
        settings = user.get('settings', {}) if user else {}
        job_title = settings.get('job_title')
        limit = settings.get('limit')
        custom_url = settings.get('custom_search_url')

        if job_title:
            custom_url = None

        if not job_title and not custom_url:
            await update.message.reply_text("📝 Введите желаемую должность:")
            context.user_data['state'] = 'awaiting_job'
            return

        if not limit:
            await update.message.reply_text("📊 Сколько откликов отправить? Введи число:")
            context.user_data['state'] = 'awaiting_limit'
            return

        if tb_helpers.start_session_func:
            success = tb_helpers.start_session_func(user_id, job_title or "", limit, custom_url)
            if success:
                tb_helpers.user_sessions_active[user_id] = True
                await tb_helpers.show_main_menu(update, context)
            else:
                await update.message.reply_text("⚠️ Сессия уже запущена или произошла ошибка")


async def handle_menu_action(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, action: str):
    if action == "toggle_mode":
        manual_mode = tb_helpers.get_user_manual_mode(user_id)
        manual_mode = not manual_mode
        tb_helpers.user_manual_mode[user_id] = manual_mode
        user = await db.AsyncDatabase.get_user(user_id)
        if user:
            settings = user.get('settings', {})
            settings['manual_mode'] = manual_mode
            await db.AsyncDatabase.save_user(user_id, settings=settings)
        mode_text = "🟡 Ручной" if manual_mode else "🟢 Авто"
        await update.message.reply_text(f"✅ Режим изменён: {mode_text}")
        await tb_helpers.show_main_menu(update, context)

    elif action == "stats":
        stats = await db.AsyncDatabase.get_stats(user_id)
        text = (
            f"📊 *СТАТИСТИКА*\n\n"
            f"📬 Всего откликов: {stats['total']}\n"
            f"✅ Отправлено: {stats['sent']}\n"
            f"🛡️ Отклонено Ревазом: {stats['revaz_skip']}\n"
            f"❌ Ошибок: {stats['error']}\n\n"
            f"📅 *Сегодня:* {stats['sent_today']}"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Успешные отклики", callback_data="successful_applications")],
        ])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif action == "resume_menu":
        from bot.keyboards.main import get_resume_menu_keyboard
        await update.message.reply_text(
            "📄 *Управление резюме*\n\nВыбери действие:",
            parse_mode="Markdown",
            reply_markup=get_resume_menu_keyboard()
        )

    elif action == "analyze_resume":
        resume_text = await db.AsyncDatabase.get_active_resume(user_id)
        if not resume_text:
            await update.message.reply_text("❌ Активное резюме не найдено.")
            return
        msg = await update.message.reply_text("🔍 Алина анализирует резюме...")
        await analyze_resume_async(user_id, resume_text, msg, context)

    elif action == "jobs_menu":
        from bot.keyboards.main import get_jobs_menu_keyboard
        await update.message.reply_text(
            "📌 *Управление должностями*\n\nВыбери действие:",
            parse_mode="Markdown",
            reply_markup=get_jobs_menu_keyboard()
        )

    elif action == "start_by_url":
        await update.message.reply_text(
            "🔗 *Отправь мне готовую ссылку на поиск hh.ru*\n\n"
            "Пример: `https://hh.ru/search/vacancy?resume=...`\n\n"
            "Я запущу отклики по этой ссылке.",
            parse_mode="Markdown"
        )
        context.user_data['state'] = 'awaiting_search_url'

    elif action == "start_hh_login":
        from core.session_manager import session_manager
        success = session_manager.start_auth_session(user_id)
        if success:
            await update.message.reply_text(
                "🌐 Открываю браузер...\n\n"
                "Сейчас появится окно Chrome на компьютере!\n"
                "Жди следующего сообщения от бота 👇"
            )
            context.user_data['state'] = 'awaiting_phone'
        else:
            await update.message.reply_text("⚠️ Авторизация уже запущена.")


async def analyze_resume_async(user_id: int, resume: str, status_message, context: ContextTypes.DEFAULT_TYPE = None):
    from services.resume_improver import ResumeImprover

    improver = ResumeImprover()
    analysis = await run_in_thread(improver.analyze, resume)

    if context:
        context.user_data['analysis'] = analysis
        context.user_data['resume_text'] = resume
        if analysis.get('improved_resume'):
            context.user_data['improved_resume'] = analysis['improved_resume']

    score = analysis['score']

    text = f"📊 *Оценка резюме: {score}/10*\n\n"

    if analysis['strengths']:
        text += "*✅ Сильные стороны:*\n"
        for s in analysis['strengths'][:5]:
            text += f"• {s}\n"
        text += "\n"

    if analysis['weaknesses']:
        text += "*⚠️ Что улучшить:*\n"
        for w in analysis['weaknesses'][:5]:
            text += f"• {w}\n"
        text += "\n"

    if analysis.get('keywords'):
        text += f"*🔑 Ключевые слова для ATS:*\n{', '.join(analysis['keywords'][:8])}\n\n"

    has_improved = bool(analysis.get('improved_resume'))

    if score < 9:
        if has_improved:
            text += "💡 *Алина подготовила улучшенную версию резюме!*\nНажми кнопку чтобы посмотреть и применить."
        else:
            text += "💡 *Хочешь сделать резюме более релевантным?*\nНажми кнопку и Алина улучшит его."

    from bot.keyboards.main import get_analysis_keyboard
    keyboard = get_analysis_keyboard(has_improved=has_improved, score=score)
    # Убираем проблемные символы для Markdown
    text = text.replace('`', "'").replace('_', ' ')
    try:
        await status_message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    except Exception:
        # Fallback без форматирования
        text_plain = text.replace('*', '').replace('_', '')
        await status_message.edit_text(text_plain, reply_markup=keyboard)


async def analyze_resume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, resume: str):
    msg = await update.callback_query.edit_message_text("🔍 Алина анализирует резюме...")
    await analyze_resume_async(user_id, resume, msg, context)


async def process_resume(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    if len(text) < 500:
        await update.message.reply_text("❌ Резюме слишком короткое. Отправь текст от 500 символов.")
        return

    await db.AsyncDatabase.save_user(
        user_id,
        resume_text=text,
        resumes=[{"name": "Основное", "text": text}],
        active_resume_index=0
    )

    await update.message.reply_text(
        "✅ *Резюме сохранено!*\n\n"
        "🔍 Алина сейчас проанализирует его и предложит улучшения...",
        parse_mode="Markdown"
    )
    context.user_data['state'] = None
    context.user_data['resume_text'] = text

    msg = await update.message.reply_text("⏳ Анализирую...")
    await analyze_resume_async(user_id, text, msg, context)


async def process_job(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, job: str):
    if not job:
        await update.message.reply_text("❌ Введите название должности.")
        return
    user = await db.AsyncDatabase.get_user(user_id)
    settings = user.get('settings', {}) if user else {}
    settings['job_title'] = job
    settings.pop('custom_search_url', None)
    await db.AsyncDatabase.save_user(user_id, settings=settings)
    await update.message.reply_text(f"✅ Должность сохранена: {job}")
    context.user_data['state'] = None

    is_editing = context.user_data.pop('editing_job', False)
    limit = settings.get('limit')

    if is_editing:
        await show_summary_and_confirm(update, user_id, job, limit or 0)
    else:
        if limit:
            await show_summary_and_confirm(update, user_id, job, limit)
        else:
            await update.message.reply_text("📊 Сколько откликов отправить? Введи число:")
            context.user_data['state'] = 'awaiting_limit'


async def process_limit(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    try:
        limit = int(text)
        if limit < 1 or limit > 200:
            await update.message.reply_text("❌ Введи число от 1 до 200.")
            return
    except ValueError:
        await update.message.reply_text("❌ Введи целое число.")
        return

    user = await db.AsyncDatabase.get_user(user_id)
    settings = user.get('settings', {}) if user else {}
    settings['limit'] = limit
    await db.AsyncDatabase.save_user(user_id, settings=settings)
    await update.message.reply_text(f"✅ Лимит установлен: {limit} откликов.")
    context.user_data['state'] = None

    job_title = settings.get('job_title', 'Не указана')
    is_editing = context.user_data.pop('editing_limit', False)

    if is_editing:
        await show_summary_and_confirm(update, user_id, job_title, limit)
    else:
        if job_title and job_title != 'Не указана':
            await show_summary_and_confirm(update, user_id, job_title, limit)
        else:
            await update.message.reply_text("📝 Введите желаемую должность:")
            context.user_data['state'] = 'awaiting_job'


async def show_summary_and_confirm(update: Update, user_id: int, job_title: str, limit: int):
    text = (
        f"📋 *Проверьте настройки:*\n\n"
        f"💼 Должность: *{job_title}*\n"
        f"🔢 Откликов: *{limit}*\n\n"
        f"Всё верно?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Начать работу", callback_data="start_session_confirm")],
        [InlineKeyboardButton("✏️ Изменить", callback_data="edit_settings")],
    ])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def process_custom_letter(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, instruction: str):
    vac_id = context.user_data.get('editing_vac_id')
    if not vac_id:
        return

    ctx = tb_helpers.pending_vacancies.get(vac_id)
    if not ctx:
        await update.message.reply_text("❌ Вакансия не найдена.")
        return

    await update.message.reply_text("✏️ Редактирую письмо...")

    from core.ai_client import get_ai_client
    ai = get_ai_client()
    original_letter = ctx['letter']

    prompt = f"""Отредактируй сопроводительное письмо согласно инструкции пользователя.

Оригинальное письмо:
{original_letter}

Инструкция пользователя:
{instruction}

Правила:
- Сохрани стиль и тон оригинала
- Не добавляй обращений, подписей, контактов
- Пиши от мужского лица
- Верни ТОЛЬКО готовое письмо без пояснений

Готовое письмо:"""

    try:
        new_letter = await run_in_thread(ai.generate, prompt, max_tokens=600)
        new_letter = new_letter.strip()
    except Exception as e:
        await update.message.reply_text("❌ Ошибка при редактировании. Попробуй ещё раз.")
        return

    ctx['letter'] = new_letter

    def escape(text: str) -> str:
        for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(ch, f'\\{ch}')
        return text

    vacancy_url = ctx['vacancy'].get('url', f"https://hh.ru/vacancy/{ctx['vacancy']['id']}")
    title = escape(ctx['vacancy']['title'][:60])
    company = escape(ctx['vacancy'].get('company', 'Не указана'))
    area = escape(ctx['vacancy'].get('area', 'Не указан'))
    reason = escape(ctx['revaz_reason'][:300])
    letter_escaped = escape(new_letter[:1000])
    revaz_score = ctx['revaz_score']

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
        f"📝 Письмо \\(отредактировано\\):\n{letter_escaped}"
    )

    from bot.keyboards.main import get_vacancy_card_keyboard
    keyboard = get_vacancy_card_keyboard(vac_id)

    try:
        await tb_helpers.telegram_bot.edit_message_text(
            chat_id=ctx['chat_id'],
            message_id=ctx['message_id'],
            text=text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Ошибка обновления карточки: {e}")

    await update.message.reply_text("✅ Письмо обновлено!")
    context.user_data.pop('editing_vac_id', None)
    context.user_data['state'] = None


async def process_job_url(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, url: str):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if not parsed.netloc.endswith("hh.ru") or "/search/vacancy" not in parsed.path:
        await update.message.reply_text("❌ Некорректная ссылка. Убедись, что это ссылка на поиск вакансий hh.ru.")
        return

    user = await db.AsyncDatabase.get_user(user_id)
    settings = user.get('settings', {}) if user else {}
    settings['custom_search_url'] = url
    settings.pop('job_title', None)
    await db.AsyncDatabase.save_user(user_id, settings=settings)

    await update.message.reply_text("✅ Ссылка сохранена. Теперь поиск будет идти по ней.")
    context.user_data['state'] = None
    await tb_helpers.show_main_menu(update, context)


async def process_search_url(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, url: str):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if not parsed.netloc.endswith("hh.ru") or "/search/vacancy" not in parsed.path:
        await update.message.reply_text("❌ Некорректная ссылка. Убедись, что это ссылка на поиск вакансий hh.ru.")
        return

    user = await db.AsyncDatabase.get_user(user_id)
    settings = user.get('settings', {}) if user else {}
    settings['custom_search_url'] = url
    await db.AsyncDatabase.save_user(user_id, settings=settings)

    await update.message.reply_text("📊 Сколько откликов отправить? Введи число:")
    context.user_data['state'] = 'awaiting_limit_for_url'
    context.user_data['custom_url'] = url


async def process_limit_for_url(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    try:
        limit = int(text)
        if limit < 1 or limit > 200:
            await update.message.reply_text("❌ Введи число от 1 до 200.")
            return
    except ValueError:
        await update.message.reply_text("❌ Введи целое число.")
        return

    custom_url = context.user_data.get('custom_url')
    if not custom_url:
        await update.message.reply_text("❌ Ссылка потерялась. Попробуй снова.")
        context.user_data['state'] = None
        return

    user = await db.AsyncDatabase.get_user(user_id)
    settings = user.get('settings', {}) if user else {}
    settings['limit'] = limit
    await db.AsyncDatabase.save_user(user_id, settings=settings)

    if tb_helpers.start_session_func:
        success = tb_helpers.start_session_func(user_id, "", limit, custom_url=custom_url)
        if success:
            tb_helpers.user_sessions_active[user_id] = True
            await update.message.reply_text("🚀 Запускаю отклики по твоей ссылке!")
            await tb_helpers.show_main_menu(update, context)
        else:
            await update.message.reply_text("⚠️ Сессия уже запущена или произошла ошибка")
    else:
        await update.message.reply_text("❌ Функция запуска не настроена")

    context.user_data['state'] = None
    context.user_data.pop('custom_url', None)


async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    phone = text.strip().replace(' ', '').replace('-', '')
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text(
            "❌ Неверный формат. Введи 10 цифр без +7 и 8\n"
            "Пример: `9060295956`",
            parse_mode="Markdown"
        )
        return

    if user_id in tb_helpers.auth_events:
        tb_helpers.auth_data[user_id]['phone'] = phone
        tb_helpers.auth_events[user_id].set()
        context.user_data['state'] = 'awaiting_sms'
        await update.message.reply_text("✅ Номер принят! Жди SMS от hh.ru...")
    else:
        await update.message.reply_text("❌ Сессия авторизации не найдена. Нажми 'Войти' снова.")
        context.user_data['state'] = None


async def process_sms(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    code = text.strip()
    if not code.isdigit():
        await update.message.reply_text("❌ Код должен состоять из цифр. Попробуй ещё раз:")
        return

    if user_id in tb_helpers.auth_events:
        tb_helpers.auth_data[user_id]['sms_code'] = code
        tb_helpers.auth_events[user_id].set()
        context.user_data['state'] = None
        await update.message.reply_text("✅ Код принят! Завершаю авторизацию...")
    else:
        await update.message.reply_text("❌ Сессия авторизации не найдена.")
        context.user_data['state'] = None