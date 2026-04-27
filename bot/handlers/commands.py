from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from bot.utils.helpers import show_main_menu
import storage.database as db
from core.logger import logger


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.AsyncDatabase.get_user(user_id)

    # Постоянное меню снизу — появляется всегда
    reply_keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("▶️ Запустить отклики"), KeyboardButton("🔄 Режим")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("📄 Резюме")],
        [KeyboardButton("📌 Должности"), KeyboardButton("🔗 По ссылке")],
        [KeyboardButton("🔐 Авторизация hh.ru")],
    ], resize_keyboard=True)

    if user and user.get('resume_text'):
        # Знакомый пользователь
        if user.get('settings'):
            import bot.utils.helpers as tb_helpers
            tb_helpers.user_manual_mode[user_id] = user['settings'].get('manual_mode', False)

        await update.message.reply_text(
            "⌨️ Панель управления",
            reply_markup=reply_keyboard
        )
        await show_main_menu(update, context)
        context.user_data['state'] = None
    else:
        # Новый пользователь — онбординг
        await update.message.reply_text(
            "⌨️ Панель управления",
            reply_markup=reply_keyboard
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Войти в hh.ru", callback_data="start_hh_login")],
            [InlineKeyboardButton("✅ Я уже авторизован", callback_data="already_authorized")],
        ])
        await update.message.reply_text(
            "👋 Привет! Я помогу тебе автоматизировать отклики на hh.ru.\n\n"
            "🔐 *Шаг 1: Авторизация*\n"
            "Для работы бота нужно войти в hh.ru через браузер на этом компьютере.\n\n"
            "Нажми кнопку ниже чтобы войти, затем нажми «Я уже авторизован».",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        context.user_data['state'] = 'awaiting_auth'


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Настройка отменена.")
    context.user_data['state'] = None


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *HH Bot Pro — Помощь*\n\n"
        "Этот бот автоматизирует отклики на hh.ru.\n\n"
        "*Основные действия:*\n"
        "• Загрузите резюме через меню «Резюме».\n"
        "• Укажите желаемую должность и количество откликов.\n"
        "• Выберите режим: авто или ручной.\n"
        "• Нажмите «Запустить отклики» — бот начнёт работу.\n\n"
        "*Команды:*\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/cancel — отменить текущую настройку\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")