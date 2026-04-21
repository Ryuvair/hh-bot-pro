import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import bot.utils.helpers as tb_helpers
import storage.database as db
from core.logger import logger
from bot.keyboards.main import get_analysis_keyboard
from core.async_executor import run_in_thread


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    user_id = update.effective_user.id
    text = update.message.text.strip()

    logger.info(f"📥 Получено сообщение от {user_id}, state={state}, текст: {text}")

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
    else:
        await update.message.reply_text("Используйте кнопки меню для навигации.")


async def analyze_resume_async(user_id: int, resume: str, status_message, context: ContextTypes.DEFAULT_TYPE = None):
    from services.resume_improver import ResumeImprover

    improver = ResumeImprover()
    analysis = await run_in_thread(improver.analyze, resume)

    if context:
        context.user_data['analysis'] = analysis
        context.user_data['resume_text'] = resume
        if analysis.get('improved_resume'):
            context.user_data['improved_resume'] = analysis['improved_resume']

    text = f"📊 *Оценка резюме: {analysis['score']}/10*\n\n"
    if analysis['strengths']:
        text += "*Сильные стороны:*\n" + '\n'.join(f"✅ {s}" for s in analysis['strengths']) + "\n\n"
    if analysis['weaknesses']:
        text += "*Что можно улучшить:*\n" + '\n'.join(f"⚠️ {w}" for w in analysis['weaknesses']) + "\n\n"

    from bot.keyboards.main import get_analysis_keyboard
    keyboard = get_analysis_keyboard(has_improved=bool(analysis.get('improved_resume')))

    await status_message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def process_resume(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    if len(text) < 500:
        await update.message.reply_text("❌ Резюме слишком короткое. Отправь текст от 500 символов.")
        return

    await db.AsyncDatabase.save_user(user_id, resume_text=text)
    await update.message.reply_text("✅ Резюме сохранено!")
    context.user_data['state'] = None

    msg = await update.message.reply_text("🔍 Алина анализирует резюме...")
    await analyze_resume_async(user_id, text, msg, context)


async def analyze_resume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, resume: str):
    msg = await update.callback_query.edit_message_text("🔍 Алина анализирует резюме...")
    await analyze_resume_async(user_id, resume, msg, context)


async def process_job(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, job: str):
    if not job:
        await update.message.reply_text("❌ Введите название должности.")
        return
    user = await db.AsyncDatabase.get_user(user_id)
    settings = user.get('settings', {}) if user else {}
    settings['job_title'] = job
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


async def process_custom_letter(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, new_letter: str):
    vac_id = context.user_data.get('editing_vac_id')
    if not vac_id:
        return
    if len(new_letter) < 50:
        await update.message.reply_text("❌ Слишком короткое письмо. Попробуй ещё раз.")
        return
    ctx = tb_helpers.pending_vacancies.get(vac_id)
    if ctx:
        ctx['letter'] = new_letter
        stars = "⭐" * (ctx['revaz_score'] // 2) + "☆" * (5 - ctx['revaz_score'] // 2)
        letter_preview = new_letter[:1000] + "..." if len(new_letter) > 1000 else new_letter
        text = (
            f"🎯 *{ctx['vacancy']['title'][:60]}*\n\n"
            f"🏢 {ctx['vacancy'].get('company', 'Не указана')}\n"
            f"💰 {ctx['vacancy'].get('salary', 'Не указана')}\n"
            f"📊 Релевантность: {ctx['revaz_score']}/10 {stars}\n"
            f"💡 {ctx['revaz_reason'][:100]}\n\n"
            f"📝 *Письмо (отредактировано):*\n{letter_preview}"
        )
        from bot.keyboards.main import get_vacancy_card_keyboard
        keyboard = get_vacancy_card_keyboard(vac_id)
        await tb_helpers.telegram_bot.edit_message_text(
            chat_id=ctx['chat_id'],
            message_id=ctx['message_id'],
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
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

    limit = settings.get('limit')
    if limit:
        if tb_helpers.start_session_func:
            success = tb_helpers.start_session_func(user_id, "", limit, custom_url=url)
            if success:
                tb_helpers.user_sessions_active[user_id] = True
                await update.message.reply_text("🚀 Запускаю отклики по твоей ссылке!")
                await tb_helpers.show_main_menu(update, context)
            else:
                await update.message.reply_text("⚠️ Сессия уже запущена или произошла ошибка")
        else:
            await update.message.reply_text("❌ Функция запуска не настроена")
    else:
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