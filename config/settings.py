"""
Настройки HH Bot Pro
"""
import os
import random
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================
# ПУТИ
# ============================================
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ============================================
# ПОЛЬЗОВАТЕЛЬ
# ============================================
DEFAULT_USER_ID = "default"
USER_DATA_DIR = DATA_DIR / DEFAULT_USER_ID
USER_DATA_DIR.mkdir(exist_ok=True)

RESUME_FILE = USER_DATA_DIR / "resume.txt"
PROFILE_FILE = USER_DATA_DIR / "profile.json"
HISTORY_FILE = USER_DATA_DIR / "history.json"
SEARCHES_FILE = USER_DATA_DIR / "searches.json"
STOP_FILE = BASE_DIR / "stop_signal.txt"

# ============================================
# HH НАСТРОЙКИ
# ============================================
BOT_PROFILE = os.getenv("HH_BOT_PROFILE", str(BASE_DIR / "chrome_profile"))
CHROME_PATH = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

TIMEOUT = 60000
PAGE_LOAD_WAIT = 5
PAUSE_BETWEEN_VACANCIES = (7, 14)
PAUSE_AFTER_APPLY = (5, 10)

# ============================================
# AI НАСТРОЙКИ
# ============================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "")

AI_PRIMARY = "deepseek"
AI_FALLBACK = "gigachat"

# ============================================
# РЕЖИМЫ РАБОТЫ
# ============================================
VALIDATION_MODE = os.getenv("VALIDATION_MODE", "revaz")
SEARCH_MODE = os.getenv("SEARCH_MODE", "smart")

MAX_APPLIES_PER_SESSION = int(os.getenv("MAX_APPLIES_PER_SESSION", "18"))
MAX_APPLIES_PER_DAY = int(os.getenv("MAX_APPLIES_PER_DAY", "100"))

# ============================================
# TELEGRAM НАСТРОЙКИ
# ============================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "")

# ============================================
# ПОИСКОВАЯ ССЫЛКА
# ============================================
SEARCH_URL = "https://hh.ru/search/vacancy?text=Project+manager+it+%D1%81%D1%82%D0%B0%D0%B6%D0%B5%D1%80&excluded_text=&area=1&salary=&salary=&currency_code=RUR&experience=doesNotMatter&order_by=relevance&search_period=0&items_on_page=50&L_save_area=true&hhtmFrom=vacancy_search_filter"

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================
def get_random_pause(pause_range: tuple) -> float:
    return random.uniform(*pause_range)

def ensure_dirs():
    dirs = [DATA_DIR, LOGS_DIR, USER_DATA_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

ensure_dirs()