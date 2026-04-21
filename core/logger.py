"""
Расширенное логирование для HH Bot Pro с общим логом all.log
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

from config.settings import LOGS_DIR

# Форматы
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%H:%M:%S"
FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class HHLogger:
    _instance: Optional['HHLogger'] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self):
        self._logger = logging.getLogger("HHBot")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()

        # Консоль (INFO и выше)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(CONSOLE_FORMAT, DATE_FORMAT))
        self._logger.addHandler(console)

        # Основной файл (DEBUG и выше)
        debug = RotatingFileHandler(LOGS_DIR / "debug.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        debug.setLevel(logging.DEBUG)
        debug.setFormatter(logging.Formatter(FILE_FORMAT, FILE_DATE_FORMAT))
        self._logger.addHandler(debug)

        # Ошибки (ERROR и выше)
        error = RotatingFileHandler(LOGS_DIR / "error.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        error.setLevel(logging.ERROR)
        error.setFormatter(logging.Formatter(FILE_FORMAT, FILE_DATE_FORMAT))
        self._logger.addHandler(error)

        # ========== ОБЩИЙ ЛОГ ДЛЯ GITHUB (INFO и выше) ==========
        all_handler = RotatingFileHandler(LOGS_DIR / "all.log", maxBytes=10*1024*1024, backupCount=3, encoding='utf-8')
        all_handler.setLevel(logging.INFO)
        all_handler.setFormatter(logging.Formatter(FILE_FORMAT, FILE_DATE_FORMAT))
        self._logger.addHandler(all_handler)

        # Логгер откликов
        self._apply_logger = logging.getLogger("HHBot.Applies")
        self._apply_logger.setLevel(logging.INFO)
        apply_handler = RotatingFileHandler(LOGS_DIR / "applies.log", maxBytes=10*1024*1024, backupCount=10, encoding='utf-8')
        apply_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", FILE_DATE_FORMAT))
        self._apply_logger.addHandler(apply_handler)
        self._apply_logger.propagate = False

        # Логгер AI
        self._ai_logger = logging.getLogger("HHBot.AI")
        self._ai_logger.setLevel(logging.DEBUG)
        ai_handler = RotatingFileHandler(LOGS_DIR / "ai.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        ai_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", FILE_DATE_FORMAT))
        self._ai_logger.addHandler(ai_handler)
        self._ai_logger.propagate = False

        # Логгер HTTP (Telegram API)
        self._http_logger = logging.getLogger("HHBot.HTTP")
        self._http_logger.setLevel(logging.DEBUG)
        http_handler = RotatingFileHandler(LOGS_DIR / "http.log", maxBytes=10*1024*1024, backupCount=3, encoding='utf-8')
        http_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", FILE_DATE_FORMAT))
        self._http_logger.addHandler(http_handler)
        self._http_logger.propagate = False

        # Логгер браузера
        self._browser_logger = logging.getLogger("HHBot.Browser")
        self._browser_logger.setLevel(logging.DEBUG)
        browser_handler = RotatingFileHandler(LOGS_DIR / "browser.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        browser_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", FILE_DATE_FORMAT))
        self._browser_logger.addHandler(browser_handler)
        self._browser_logger.propagate = False

    def get_logger(self): return self._logger
    def get_apply_logger(self): return self._apply_logger
    def get_ai_logger(self): return self._ai_logger
    def get_http_logger(self): return self._http_logger
    def get_browser_logger(self): return self._browser_logger

_logger_instance = HHLogger()
logger = _logger_instance.get_logger()
apply_logger = _logger_instance.get_apply_logger()
ai_logger = _logger_instance.get_ai_logger()
http_logger = _logger_instance.get_http_logger()
browser_logger = _logger_instance.get_browser_logger()

def log_startup():
    logger.info("=" * 60)
    logger.info(f"🚀 HH BOT PRO STARTED | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

def log_shutdown(total_applies: int = 0):
    logger.info("=" * 60)
    logger.info(f"🏁 HH BOT PRO FINISHED | Откликов: {total_applies}")
    logger.info("=" * 60)

def log_apply(vacancy_id: str, title: str, status: str, letter_preview: str = "", error: str = ""):
    if status == "sent":
        msg = f"✅ SENT | {vacancy_id} | {title[:50]}"
        if letter_preview: msg += f"\n   📝 {letter_preview[:100]}..."
    elif status == "error":
        msg = f"❌ ERROR | {vacancy_id} | {title[:50]} | {error}"
    elif status == "skip":
        msg = f"⏭️ SKIP | {vacancy_id} | {title[:50]}"
    elif status == "revaz_skip":
        msg = f"🛡️ REVAZ SKIP | {vacancy_id} | {title[:50]} | {error}"
    else:
        msg = f"ℹ️ {status} | {vacancy_id} | {title[:50]}"
    apply_logger.info(msg)

def log_ai(prompt_type: str, input_data: str, output: str, error: str = None):
    sep = "-" * 50
    if error:
        ai_logger.error(f"{sep}\n🔴 ERROR | {prompt_type}\nInput: {input_data[:200]}...\nError: {error}\n{sep}")
    else:
        ai_logger.debug(f"{sep}\n🟢 {prompt_type}\nInput: {input_data[:500]}...\nOutput: {output[:500]}...\n{sep}")

def log_http(method: str, url: str, status: int = None, error: str = None):
    if error:
        http_logger.error(f"{method} {url} | ERROR: {error}")
    else:
        http_logger.debug(f"{method} {url} | Status: {status}")

def log_browser(action: str, url: str = "", details: str = ""):
    browser_logger.debug(f"🌐 {action} | {url} | {details}")