"""
Хранилище истории откликов (работа с БД)
"""
from storage.database import SyncDatabase

def add_application(telegram_id: int, vacancy_id: str, title: str, url: str, status: str, letter: str = "", error: str = None):
    SyncDatabase.add_application(telegram_id, vacancy_id, title, url, status, letter, error)

def get_applied_ids(telegram_id: int) -> set:
    return SyncDatabase.get_applied_ids(telegram_id)

def get_stats(telegram_id: int):
    return SyncDatabase.get_stats(telegram_id)