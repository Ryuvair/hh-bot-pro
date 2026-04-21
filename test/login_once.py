"""Одноразовый запуск для ручной авторизации в HH"""
from core.browser import launch_browser
from config.settings import SEARCH_MODE  # не важно, просто импорт

print("🟢 Открываю браузер. Войди в hh.ru вручную, затем закрой окно.")
with launch_browser() as page:
    page.goto("https://hh.ru")
    input("⏳ После входа в аккаунт нажми Enter здесь, чтобы закрыть браузер...")
print("✅ Профиль сохранён. Теперь бот будет использовать эту сессию.")