import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import bot.utils.helpers as tb_helpers
from bot.keyboards.main import (
    get_resume_menu_keyboard, get_job_suggestions_keyboard,
    get_confirm_job_keyboard, get_main_keyboard, get_jobs_menu_keyboard
)
import storage.database as db
from core.logger import logger
from core.ai_client import get_ai_client_async
from core.prompts import JOB_SUGGESTIONS_PROMPT
from bot.handlers.messages import analyze_resume_handler
from core.async_executor import run_in_thread


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = update.effective_user.id
    user = await db.AsyncDatabase.get_user(user_id)
    settings = user.get('settings', {}) if user else {}

    session_active = tb_helpers.get_user_session_active(user_id)
    manual_mode = tb_helpers.get_user_manual_mode(user_id)

    if data == "toggle_session":
        if not session_active:
            job_title = settings.get('job_title')
            limit = settings.get('limit')

            if job_title:
                keyboard = get_confirm_job_keyboard(job_title)
                await query.edit_message_text(
                    f"Желаемая должность: *{job_title}*\n\nХотите искать по ней или ввести новую?",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                context.user_data['state'] = None
                return
            else:
                await query.edit_message_text("📝 Введите желаемую должность:")
                context.user_data['state'] = 'awaiting_job'
                return
        else:
            if tb_helpers.stop_session_func:
                tb_helpers.stop_session_func(user_id)
                session_active = False
                mode_text = "🟢 Авто" if not manual_mode else "🟡 Ручной"
                start_stop_text = "▶️ Запустить отклики"
                keyboard = get_main_keyboard(start_stop_text, mode_text)
                text = (
                    "🤖 *HH Bot Pro*\n\n"
                    f"Статус: 🔴 Остановлен\n"
                    f"Режим: {'🟢 Автоматический' if not manual_mode else '🟡 Ручной (подтверждение)'}\n\n"
                    "Выбери действие:"
                )
                await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")
                logger.info(f"Сессия пользователя {user_id} остановлена через Telegram")
                context.user_data['state'] = None

    elif data == "toggle_mode":
        manual_mode = not manual_mode
        tb_helpers.user_manual_mode[user_id] = manual_mode
        if user:
            settings['manual_mode'] = manual_mode
            await db.AsyncDatabase.save_user(user_id, settings=settings)
        session_active = tb_helpers.get_user_session_active(user_id)
        mode_text = "🟢 Авто" if not manual_mode else "🟡 Ручной"
        start_stop_text = "⏸️ Остановить" if session_active else "▶️ Запустить отклики"
        keyboard = get_main_keyboard(start_stop_text, mode_text)
        text = (
            "🤖 *HH Bot Pro*\n\n"
            f"Статус: {'🟢 Запущен' if session_active else '🔴 Остановлен'}\n"
            f"Режим: {'🟢 Автоматический' if not manual_mode else '🟡 Ручной (подтверждение)'}\n\n"
            "Выбери действие:"
        )
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif data == "stats":
        stats = await db.AsyncDatabase.get_stats(user_id)
        text = (
            f"📊 *СТАТИСТИКА*\n\n"
            f"📬 Всего откликов: {stats['total']}\n"
            f"✅ Отправлено: {stats['sent']}\n"
            f"🛡️ Отклонено Ревазом: {stats['revaz_skip']}\n"
            f"❌ Ошибок: {stats['error']}\n"
            f"🤖 AI-ошибок: {stats['ai_error']}\n\n"
            f"📅 *Сегодня отправлено:* {stats['sent_today']}"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Успешные отклики", callback_data="successful_applications")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ])
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")

    elif data == "successful_applications":
        apps = await db.AsyncDatabase.get_recent_applications(user_id, limit=10, status='sent')
        if not apps:
            await query.edit_message_text("Пока нет успешных откликов.")
            return
        text = "*Последние отправленные отклики:*\n\n"
        keyboard = []
        for app in apps:
            short_title = app['title'][:40] + "..." if len(app['title']) > 40 else app['title']
            keyboard.append([InlineKeyboardButton(short_title, url=app['url'])])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="stats")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "back_to_main":
        await tb_helpers.show_main_menu(update, context)
        context.user_data['state'] = None

    elif data == "resume_menu":
        await query.edit_message_text(
            "📄 *Управление резюме*\n\nВыбери действие:",
            parse_mode="Markdown",
            reply_markup=get_resume_menu_keyboard()
        )

    elif data == "view_resume":
        resume_text = await db.AsyncDatabase.get_active_resume(user_id)
        if not resume_text:
            await query.answer("Активное резюме не найдено", show_alert=True)
            return
        await query.edit_message_text(
            f"📄 *Ваше активное резюме:*\n\n{resume_text[:3500]}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="resume_menu")]])
        )

    elif data == "upload_resume":
        await query.edit_message_text("📤 Отправь мне текст твоего резюме (более 500 символов).")
        context.user_data['state'] = 'awaiting_resume'

    elif data == "switch_resume":
        resumes = user.get('resumes', []) if user else []
        if not resumes:
            await query.answer("У вас нет сохранённых резюме", show_alert=True)
            return
        keyboard = []
        for i, r in enumerate(resumes):
            name = r.get('name', f'Резюме {i+1}')
            active_mark = " ✅" if i == user.get('active_resume_index', 0) else ""
            keyboard.append([InlineKeyboardButton(f"{name}{active_mark}", callback_data=f"set_active_resume_{i}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="resume_menu")])
        await query.edit_message_text(
            "🔄 *Выберите активное резюме:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("set_active_resume_"):
        idx = int(data.replace("set_active_resume_", ""))
        if user and user.get('resumes'):
            await db.AsyncDatabase.save_user(user_id, active_resume_index=idx)
            await query.edit_message_text("✅ Активное резюме изменено.")
            await tb_helpers.show_main_menu(update, context)
        else:
            await query.answer("Ошибка", show_alert=True)

    elif data == "analyze_resume":
        resume_text = await db.AsyncDatabase.get_active_resume(user_id)
        if not resume_text:
            await query.edit_message_text("❌ Активное резюме не найдено.")
            return
        await query.edit_message_text("🔍 Алина анализирует...")
        await analyze_resume_handler(update, context, user_id, resume_text)

    elif data == "view_improved":
        analysis = context.user_data.get('analysis', {})
        improved = analysis.get('improved_resume')
        if not improved:
            await query.answer("Нет улучшенной версии", show_alert=True)
            return
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Применить улучшенное", callback_data="apply_improved_resume")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_analysis")],
        ])
        await query.edit_message_text(
            f"📄 *Улучшенная версия резюме:*\n\n{improved[:3500]}",
            reply_markup=keyboard
        )

    elif data == "skip_analysis":
        await suggest_jobs(update, context, user_id)
        context.user_data['state'] = None

    elif data == "back_to_analysis":
        analysis = context.user_data.get('analysis')
        resume_text = context.user_data.get('resume_text') or await db.AsyncDatabase.get_active_resume(user_id)
        if analysis and resume_text:
            await analyze_resume_handler(update, context, user_id, resume_text)
        else:
            await query.edit_message_text("Данные анализа не найдены.")

    elif data == "apply_improved_onboard":
        analysis = context.user_data.get('analysis', {})
        improved = analysis.get('improved_resume')
        if not improved:
            await query.answer("Нет улучшенной версии", show_alert=True)
            return
        await db.AsyncDatabase.save_user(user_id, resume_text=improved)
        context.user_data['improved_resume'] = improved
        await query.edit_message_text("✅ Улучшенное резюме сохранено!")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Подобрать должность", callback_data="update_job")],
            [InlineKeyboardButton("◀️ В меню", callback_data="back_to_main")],
        ])
        await query.message.reply_text("Хочешь подобрать должность под новое резюме?", reply_markup=keyboard)

    elif data == "apply_improved_resume":
        analysis = context.user_data.get('analysis', {})
        improved = analysis.get('improved_resume')
        if not improved:
            await query.edit_message_text("❌ Нет улучшенного резюме.")
            return
        await db.AsyncDatabase.save_user(user_id, resume_text=improved)
        context.user_data['improved_resume'] = improved
        await query.edit_message_text("✅ Улучшенное резюме сохранено!")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить должность", callback_data="update_job")],
            [InlineKeyboardButton("◀️ В меню", callback_data="back_to_main")],
        ])
        await query.message.reply_text("Хочешь заново подобрать должность под новое резюме?", reply_markup=keyboard)

    elif data == "update_job":
        await suggest_jobs(update, context, user_id)

    elif data == "jobs_menu":
        await query.edit_message_text(
            "📌 *Управление должностями*\n\nВыбери действие:",
            parse_mode="Markdown",
            reply_markup=get_jobs_menu_keyboard()
        )

    elif data == "job_manual":
        await query.edit_message_text("📝 Введите желаемую должность:")
        context.user_data['state'] = 'awaiting_job'

    elif data == "job_suggest":
        await suggest_jobs(update, context, user_id)

    elif data == "job_show":
        job_title = settings.get('job_title', 'Не указана')
        await query.edit_message_text(
            f"📌 *Текущая должность для поиска:*\n\n{job_title}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="jobs_menu")]
            ])
        )

    elif data == "job_url":
        await query.edit_message_text(
            "🔗 *Отправь мне готовую ссылку на поиск hh.ru*\n\n"
            "Пример: `https://hh.ru/search/vacancy?resume=...&experience=noExperience`\n\n"
            "Я сохраню эту ссылку и буду использовать её для поиска вместо должности.",
            parse_mode="Markdown"
        )
        context.user_data['state'] = 'awaiting_job_url'

    elif data.startswith("use_job_"):
        job = data.replace("use_job_", "")
        settings['job_title'] = job
        await db.AsyncDatabase.save_user(user_id, settings=settings)
        await query.edit_message_text(f"✅ Будем искать: {job}")
        limit = settings.get('limit')
        if not limit:
            await query.edit_message_text("📊 Сколько откликов отправить? Введи число:")
            context.user_data['state'] = 'awaiting_limit'
            return
        from bot.handlers.messages import show_summary_and_confirm
        await show_summary_and_confirm(update, user_id, job, limit)

    elif data == "new_job":
        await query.edit_message_text("📝 Введите желаемую должность:")
        context.user_data['state'] = 'awaiting_job'
        logger.info(f"Установлено состояние awaiting_job для {user_id}")

    elif data == "start_session_confirm":
        job_title = settings.get('job_title')
        limit = settings.get('limit')
        custom_url = settings.get('custom_search_url')
        if not job_title and not custom_url:
            await query.edit_message_text("❌ Не задана ни должность, ни ссылка для поиска.")
            return
        if not limit:
            await query.edit_message_text("📊 Сколько откликов отправить? Введи число:")
            context.user_data['state'] = 'awaiting_limit'
            return
        if tb_helpers.start_session_func:
            success = tb_helpers.start_session_func(user_id, job_title or "", limit, custom_url)
            if success:
                tb_helpers.user_sessions_active[user_id] = True
                await tb_helpers.show_main_menu(update, context)
                logger.info(f"Сессия пользователя {user_id} запущена через Telegram")
            else:
                await query.edit_message_text("⚠️ Сессия уже запущена или произошла ошибка")
        else:
            await query.edit_message_text("❌ Функция запуска не настроена")
        context.user_data['state'] = None

    elif data == "edit_settings":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💼 Изменить должность", callback_data="edit_job")],
            [InlineKeyboardButton("🔢 Изменить лимит", callback_data="edit_limit")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
        ])
        await query.edit_message_text("Что хотите изменить?", reply_markup=keyboard)

    elif data == "edit_job":
        await query.edit_message_text("📝 Введите новую должность:")
        context.user_data['state'] = 'awaiting_job'
        context.user_data['editing_job'] = True

    elif data == "edit_limit":
        await query.edit_message_text("📊 Введите новое количество откликов (1-200):")
        context.user_data['state'] = 'awaiting_limit'
        context.user_data['editing_limit'] = True

    elif data == "start_by_url":
        await query.edit_message_text(
            "🔗 *Отправь мне готовую ссылку на поиск hh.ru*\n\n"
            "Пример: `https://hh.ru/search/vacancy?resume=...&experience=noExperience`\n\n"
            "Я запущу отклики по этой ссылке, используя твоё активное резюме.",
            parse_mode="Markdown"
        )
        context.user_data['state'] = 'awaiting_search_url'

    elif data.startswith("apply_"):
        vac_id = data.replace("apply_", "")
        tb_helpers.manual_decisions[vac_id] = "apply"
        event = tb_helpers.get_user_decision_event(user_id)
        event.set()
        await query.edit_message_text(f"✅ Отклик на вакансию отправлен!")

    elif data.startswith("skip_"):
        vac_id = data.replace("skip_", "")
        tb_helpers.manual_decisions[vac_id] = "skip"
        event = tb_helpers.get_user_decision_event(user_id)
        event.set()
        await query.edit_message_text(f"⏭️ Вакансия пропущена.")

    elif data.startswith("regen_"):
        vac_id = data.replace("regen_", "")
        tb_helpers.manual_decisions[vac_id] = "regen"
        event = tb_helpers.get_user_decision_event(user_id)
        event.set()
        await query.edit_message_text(f"🔄 Письмо перегенерировано")

    elif data.startswith("full_"):
        vac_id = data.replace("full_", "")
        ctx = tb_helpers.pending_vacancies.get(vac_id)
        if ctx:
            await query.message.reply_text(f"📄 *Полный текст письма:*\n\n{ctx['letter']}", parse_mode="Markdown")
        else:
            await query.answer("Вакансия не найдена", show_alert=True)

    elif data.startswith("edit_"):
        vac_id = data.replace("edit_", "")
        ctx = tb_helpers.pending_vacancies.get(vac_id)
        if not ctx:
            await query.answer("Вакансия не найдена", show_alert=True)
            return
        await query.edit_message_text("✏️ Отправь новый текст сопроводительного письма:")
        context.user_data['state'] = 'awaiting_custom_letter'
        context.user_data['editing_vac_id'] = vac_id


async def suggest_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user = await db.AsyncDatabase.get_user(user_id)
    resume_text = user['resume_text'] if user else context.user_data.get('resume_text', '')
    active_resume = await db.AsyncDatabase.get_active_resume(user_id)
    if active_resume:
        resume_text = active_resume
    ai = await get_ai_client_async()
    prompt = JOB_SUGGESTIONS_PROMPT.format(resume=resume_text[:2000])

    try:
        import json
        jobs_str = await run_in_thread(ai.generate, prompt, max_tokens=300)
        jobs_str = jobs_str.strip()
        if jobs_str.startswith('```json'):
            jobs_str = jobs_str[7:]
        if jobs_str.startswith('```'):
            jobs_str = jobs_str[3:]
        if jobs_str.endswith('```'):
            jobs_str = jobs_str[:-3]
        jobs = json.loads(jobs_str)
        if not isinstance(jobs, list) or len(jobs) == 0:
            raise ValueError("Пустой список")
    except Exception as e:
        logger.warning(f"Не удалось распарсить JSON с должностями: {e}")
        jobs = ["Менеджер проектов", "Менеджер по продажам", "Аналитик", "Продакт-менеджер", "Ассистент руководителя"]

    context.user_data['suggested_jobs'] = jobs
    keyboard = get_job_suggestions_keyboard(jobs)
    text = "📋 Я подобрал для тебя подходящие должности. Выбери или введи свою:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)