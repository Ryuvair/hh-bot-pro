from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_keyboard(start_stop_text: str, mode_text: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(start_stop_text, callback_data="toggle_session")],
        [InlineKeyboardButton(f"🔄 Режим: {mode_text}", callback_data="toggle_mode")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📄 Резюме", callback_data="resume_menu")],
        [InlineKeyboardButton("📌 Мои должности", callback_data="jobs_menu")],
        [InlineKeyboardButton("🔗 Запустить отклики по ссылке", callback_data="start_by_url")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_resume_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("👁️ Посмотреть активное резюме", callback_data="view_resume")],
        [InlineKeyboardButton("📤 Загрузить новое резюме", callback_data="upload_resume")],
        [InlineKeyboardButton("🔄 Сменить активное резюме", callback_data="switch_resume")],
        [InlineKeyboardButton("🔍 Анализировать текущее", callback_data="analyze_resume")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_analysis_keyboard(has_improved: bool = False) -> InlineKeyboardMarkup:
    keyboard = []
    if has_improved:
        keyboard.append([InlineKeyboardButton("👀 Посмотреть улучшенное", callback_data="view_improved")])
        keyboard.append([InlineKeyboardButton("✨ Применить улучшенное", callback_data="apply_improved_onboard")])
    keyboard.append([InlineKeyboardButton("⏭️ Оставить как есть", callback_data="skip_analysis")])
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔥 Автоматический", callback_data="mode_auto")],
        [InlineKeyboardButton("🎯 Ручной (подтверждение)", callback_data="mode_manual")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_job_suggestions_keyboard(jobs: list) -> InlineKeyboardMarkup:
    keyboard = []
    for job in jobs[:8]:
        keyboard.append([InlineKeyboardButton(job, callback_data=f"use_job_{job}")])
    keyboard.append([InlineKeyboardButton("✏️ Ввести свою", callback_data="new_job")])
    return InlineKeyboardMarkup(keyboard)

def get_vacancy_card_keyboard(vacancy_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Откликнуться", callback_data=f"apply_{vacancy_id}")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data=f"skip_{vacancy_id}")],
        [InlineKeyboardButton("🔄 Перегенерировать", callback_data=f"regen_{vacancy_id}")],
        [InlineKeyboardButton("📄 Полностью", callback_data=f"full_{vacancy_id}")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{vacancy_id}")],
    ])

def get_confirm_job_keyboard(job_title: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔍 Искать: {job_title}", callback_data=f"use_job_{job_title}")],
        [InlineKeyboardButton("✏️ Ввести новую", callback_data="new_job")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ])

def get_jobs_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Ввести должность вручную", callback_data="job_manual")],
        [InlineKeyboardButton("🤖 Подобрать по резюме", callback_data="job_suggest")],
        [InlineKeyboardButton("👁️ Показать текущую должность", callback_data="job_show")],
        [InlineKeyboardButton("🔗 Вставить ссылку с фильтрами", callback_data="job_url")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ])