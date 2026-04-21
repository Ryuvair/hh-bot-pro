from telegram import Update
from telegram.ext import ContextTypes
from bot.utils.helpers import show_main_menu
import storage.database as db
from core.logger import logger


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.AsyncDatabase.get_user(user_id)
    if user and user.get('resume_text'):
        # Устанавливаем ручной режим из настроек пользователя
        if user.get('settings'):
            import bot.utils.helpers as tb_helpers
            tb_helpers.user_manual_mode[user_id] = user['settings'].get('manual_mode', False)
        await show_main_menu(update, context)
        context.user_data['state'] = None
    else:
        await update.message.reply_text(
            "👋 Привет! Я помогу тебе автоматизировать отклики на hh.ru.\n\n"
            "Для начала отправь мне текст твоего резюме (не менее 500 символов)."
        )
        context.user_data['state'] = 'awaiting_resume'


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
        "• Выберите режим: авто (бот сам решает) или ручной (вы подтверждаете каждый отклик).\n"
        "• Нажмите «Запустить отклики» — бот начнёт работу.\n\n"
        "*Команды:*\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/cancel — отменить текущую настройку\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")