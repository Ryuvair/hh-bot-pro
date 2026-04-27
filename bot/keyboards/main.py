from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard(start_stop_text: str, mode_text: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(start_stop_text), KeyboardButton(f"🔄 Режим")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📄 Резюме")],
        [KeyboardButton("📌 Должности"), KeyboardButton("🔗 По ссылке")],
        [KeyboardButton("🔐 Авторизация hh.ru")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_resume_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("👁️ Посмотреть активное резюме", callback_data="view_resume")],
        [InlineKeyboardButton("📤 Загрузить новое резюме", callback_data="upload_resume")],
        [InlineKeyboardButton("🔄 Сменить активное резюме", callback_data="switch_resume")],
        [InlineKeyboardButton("🔍 Анализировать текущее", callback_data="analyze_resume")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_analysis_keyboard(has_improved: bool = False, score: int = 5) -> InlineKeyboardMarkup:
    keyboard = []
    if has_improved:
        keyboard.append([InlineKeyboardButton("👀 Посмотреть улучшенное резюме", callback_data="view_improved")])
        keyboard.append([InlineKeyboardButton("✨ Применить улучшенное", callback_data="apply_improved_onboard")])
    elif score < 9:
        keyboard.append([InlineKeyboardButton("✨ Улучшить резюме с Алиной", callback_data="analyze_resume")])
    keyboard.append([InlineKeyboardButton("⏭️ Оставить как есть и продолжить", callback_data="skip_analysis")])
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔥 Автоматический", callback_data="mode_auto")],
        [InlineKeyboardButton("🎯 Ручной (подтверждение)", callback_data="mode_manual")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_job_suggestions_keyboard(jobs: list) -> InlineKeyboardMarkup:
    keyboard = []
    for i, job in enumerate(jobs[:8]):
        keyboard.append([InlineKeyboardButton(job, callback_data=f"use_job_idx_{i}")])
    keyboard.append([InlineKeyboardButton("✏️ Ввести свою", callback_data="new_job")])
    return InlineKeyboardMarkup(keyboard)

def get_vacancy_card_keyboard(vacancy_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Откликнуться", callback_data=f"apply_{vacancy_id}")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data=f"skip_{vacancy_id}")],
        [InlineKeyboardButton("📄 Полностью", callback_data=f"full_{vacancy_id}")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{vacancy_id}")],
    ])

def get_confirm_job_keyboard(job_title: str) -> InlineKeyboardMarkup:
    safe_title = job_title[:50]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔍 Искать: {safe_title}", callback_data=f"use_job_{safe_title}")],
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