"""Полный тест всех систем HH Bot Pro с записью результатов"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.logger import logger, log_startup, log_shutdown
from core.ai_client import get_ai_client
from core.browser import launch_browser
from config.settings import RESUME_FILE, BASE_DIR

REPORT_FILE = BASE_DIR / "test_report.txt"

def write_report(content: str):
    """Дописывает строку в отчёт"""
    with open(REPORT_FILE, 'a', encoding='utf-8') as f:
        f.write(content + '\n')

# Очищаем старый отчёт
with open(REPORT_FILE, 'w', encoding='utf-8') as f:
    f.write(f"HH BOT PRO - ТЕСТОВЫЙ ОТЧЁТ\n{'='*50}\n")
    f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

log_startup()
write_report(f"Тест запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ===== 1. ТЕСТ AI =====
print("\n🧠 ТЕСТ AI...")
write_report("\n--- ТЕСТ AI ---")
try:
    ai = get_ai_client()
    if ai.is_available():
        response = ai.generate("Скажи 'Привет, мир!'", max_tokens=30)
        logger.info(f"✅ AI отвечает: {response}")
        write_report(f"✅ AI отвечает: {response}")
    else:
        msg = "❌ AI не настроен"
        logger.error(msg)
        write_report(msg)
        sys.exit(1)
except Exception as e:
    msg = f"❌ AI ошибка: {e}"
    logger.error(msg)
    write_report(msg)
    sys.exit(1)

# ===== 2. ТЕСТ БРАУЗЕРА =====
print("\n🌐 ТЕСТ БРАУЗЕРА...")
write_report("\n--- ТЕСТ БРАУЗЕРА ---")
try:
    with launch_browser() as page:
        page.goto("https://hh.ru", timeout=30000)
        title = page.title()
        logger.info(f"✅ HH открыт: {title}")
        write_report(f"✅ HH открыт: {title}")
        
        if page.query_selector('a[data-qa="mainmenu_applicantResumes"]'):
            logger.info("✅ Пользователь авторизован на HH")
            write_report("✅ Пользователь авторизован на HH")
        else:
            logger.warning("⚠️ Не удалось подтвердить авторизацию")
            write_report("⚠️ Не удалось подтвердить авторизацию")
except Exception as e:
    msg = f"❌ Ошибка браузера: {e}"
    logger.error(msg)
    write_report(msg)
    sys.exit(1)

# ===== 3. ТЕСТ ГЕНЕРАЦИИ ПИСЬМА =====
print("\n📝 ТЕСТ ГЕНЕРАЦИИ ПИСЬМА...")
write_report("\n--- ТЕСТ ГЕНЕРАЦИИ ПИСЬМА ---")
try:
    if RESUME_FILE.exists():
        with open(RESUME_FILE, 'r', encoding='utf-8') as f:
            resume = f.read()[:500]
    else:
        resume = "Опыт управления точками продаж, ведения клиентов, Excel, Python."
        logger.warning("⚠️ Файл резюме не найден, используется тестовое")
        write_report("⚠️ Использовано тестовое резюме")
    
    vac_text = "Требуется менеджер проектов. Знание Excel, английский язык."
    title = "Менеджер проектов"
    
    prompt = f"""
Ты — ассистент. Напиши короткое сопроводительное письмо.
Резюме: {resume}
Вакансия: {title}
Требования: {vac_text}
Без воды, 5-7 предложений.
"""
    letter = ai.generate(prompt, max_tokens=200)
    logger.info(f"✅ Письмо сгенерировано:\n{letter}")
    write_report(f"✅ Письмо сгенерировано:\n{letter}\n")
except Exception as e:
    msg = f"❌ Ошибка генерации письма: {e}"
    logger.error(msg)
    write_report(msg)
    sys.exit(1)

print("\n" + "="*50)
print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
print("="*50)
write_report("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
write_report(f"Завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

log_shutdown()