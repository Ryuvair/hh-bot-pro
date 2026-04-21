"""
Модуль для работы с базой данных SQLite (синхронный + асинхронный)
Поддержка нескольких резюме и активного резюме.
"""
import sqlite3
import json
import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from config.settings import DATA_DIR
from core.logger import logger

DB_PATH = DATA_DIR / "hh_bot.db"

def init_db():
    """Создаёт таблицы, если их нет, и обновляет схему"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                resume_text TEXT,
                settings TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                resumes TEXT,
                active_resume_index INTEGER DEFAULT 0
            )
        ''')
        # Добавляем новые колонки для старых баз
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN resumes TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN active_resume_index INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                vacancy_id TEXT NOT NULL,
                title TEXT,
                url TEXT,
                status TEXT,
                letter TEXT,
                error TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id)
            )
        ''')
        conn.commit()
    logger.info(f"База данных инициализирована: {DB_PATH}")

init_db()

# ============================================
# СИНХРОННЫЙ КЛАСС
# ============================================
class SyncDatabase:
    @staticmethod
    def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            if row:
                user = dict(row)
                if user.get('settings'):
                    user['settings'] = json.loads(user['settings'])
                if user.get('resumes'):
                    user['resumes'] = json.loads(user['resumes'])
                else:
                    # Миграция старых данных: одиночное резюме -> список
                    if user.get('resume_text'):
                        user['resumes'] = [{"name": "Основное", "text": user['resume_text']}]
                        user['active_resume_index'] = 0
                    else:
                        user['resumes'] = []
                        user['active_resume_index'] = 0
                return user
            return None

    @staticmethod
    def save_user(telegram_id: int, resume_text: str = None, settings: Dict = None,
                  resumes: List[Dict] = None, active_resume_index: int = None) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,))
            exists = cursor.fetchone()
            if exists:
                updates = []
                params = []
                if resume_text is not None:
                    updates.append("resume_text = ?")
                    params.append(resume_text)
                if settings is not None:
                    updates.append("settings = ?")
                    params.append(json.dumps(settings, ensure_ascii=False))
                if resumes is not None:
                    updates.append("resumes = ?")
                    params.append(json.dumps(resumes, ensure_ascii=False))
                if active_resume_index is not None:
                    updates.append("active_resume_index = ?")
                    params.append(active_resume_index)
                if updates:
                    updates.append("updated_at = ?")
                    params.append(now)
                    params.append(telegram_id)
                    cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?", params)
            else:
                # Для нового пользователя
                resumes_json = json.dumps(resumes, ensure_ascii=False) if resumes else "[]"
                cursor.execute(
                    """INSERT INTO users (telegram_id, resume_text, settings, created_at, updated_at, resumes, active_resume_index)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (telegram_id, resume_text or "", json.dumps(settings or {}, ensure_ascii=False), now, now,
                     resumes_json, active_resume_index or 0)
                )
            conn.commit()

    @staticmethod
    def get_active_resume(telegram_id: int) -> Optional[str]:
        user = SyncDatabase.get_user(telegram_id)
        if not user:
            return None
        resumes = user.get('resumes', [])
        idx = user.get('active_resume_index', 0)
        if 0 <= idx < len(resumes):
            return resumes[idx].get('text', '')
        return None

    @staticmethod
    def add_application(telegram_id: int, vacancy_id: str, title: str, url: str, status: str, letter: str = "", error: str = None):
        now = datetime.now().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO applications (telegram_id, vacancy_id, title, url, status, letter, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, vacancy_id, title, url, status, letter, error, now)
            )
            conn.commit()

    @staticmethod
    def get_applied_ids(telegram_id: int) -> set:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT vacancy_id FROM applications WHERE telegram_id = ? AND status = 'sent'", (telegram_id,))
            return {row[0] for row in cursor.fetchall()}

    @staticmethod
    def get_stats(telegram_id: int) -> Dict[str, int]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM applications WHERE telegram_id = ?", (telegram_id,))
            total = cursor.fetchone()[0]
            cursor.execute(
                "SELECT status, COUNT(*) FROM applications WHERE telegram_id = ? GROUP BY status",
                (telegram_id,)
            )
            stats = {row[0]: row[1] for row in cursor.fetchall()}
            today = datetime.now().date().isoformat()
            cursor.execute(
                "SELECT COUNT(*) FROM applications WHERE telegram_id = ? AND status = 'sent' AND date(created_at) = ?",
                (telegram_id, today)
            )
            sent_today = cursor.fetchone()[0]
            return {
                'total': total,
                'sent': stats.get('sent', 0),
                'revaz_skip': stats.get('revaz_skip', 0),
                'error': stats.get('error', 0),
                'ai_error': stats.get('ai_error', 0),
                'sent_today': sent_today
            }

    @staticmethod
    def get_recent_applications(telegram_id: int, limit: int = 10, status: str = None) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM applications WHERE telegram_id = ?"
            params = [telegram_id]
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

# ============================================
# АСИНХРОННЫЙ КЛАСС
# ============================================
class AsyncDatabase:
    @staticmethod
    async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    user = dict(row)
                    if user.get('settings'):
                        user['settings'] = json.loads(user['settings'])
                    if user.get('resumes'):
                        user['resumes'] = json.loads(user['resumes'])
                    else:
                        if user.get('resume_text'):
                            user['resumes'] = [{"name": "Основное", "text": user['resume_text']}]
                            user['active_resume_index'] = 0
                        else:
                            user['resumes'] = []
                            user['active_resume_index'] = 0
                    return user
                return None

    @staticmethod
    async def save_user(telegram_id: int, resume_text: str = None, settings: Dict = None,
                        resumes: List[Dict] = None, active_resume_index: int = None) -> None:
        now = datetime.now().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
                exists = await cursor.fetchone()
            if exists:
                updates = []
                params = []
                if resume_text is not None:
                    updates.append("resume_text = ?")
                    params.append(resume_text)
                if settings is not None:
                    updates.append("settings = ?")
                    params.append(json.dumps(settings, ensure_ascii=False))
                if resumes is not None:
                    updates.append("resumes = ?")
                    params.append(json.dumps(resumes, ensure_ascii=False))
                if active_resume_index is not None:
                    updates.append("active_resume_index = ?")
                    params.append(active_resume_index)
                if updates:
                    updates.append("updated_at = ?")
                    params.append(now)
                    params.append(telegram_id)
                    await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?", params)
            else:
                resumes_json = json.dumps(resumes, ensure_ascii=False) if resumes else "[]"
                await db.execute(
                    """INSERT INTO users (telegram_id, resume_text, settings, created_at, updated_at, resumes, active_resume_index)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (telegram_id, resume_text or "", json.dumps(settings or {}, ensure_ascii=False), now, now,
                     resumes_json, active_resume_index or 0)
                )
            await db.commit()

    @staticmethod
    async def get_active_resume(telegram_id: int) -> Optional[str]:
        user = await AsyncDatabase.get_user(telegram_id)
        if not user:
            return None
        resumes = user.get('resumes', [])
        idx = user.get('active_resume_index', 0)
        if 0 <= idx < len(resumes):
            return resumes[idx].get('text', '')
        return None

    @staticmethod
    async def add_application(telegram_id: int, vacancy_id: str, title: str, url: str, status: str, letter: str = "", error: str = None):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO applications (telegram_id, vacancy_id, title, url, status, letter, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, vacancy_id, title, url, status, letter, error, now)
            )
            await db.commit()

    @staticmethod
    async def get_applied_ids(telegram_id: int) -> set:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT vacancy_id FROM applications WHERE telegram_id = ? AND status = 'sent'", (telegram_id,)) as cursor:
                rows = await cursor.fetchall()
                return {row[0] for row in rows}

    @staticmethod
    async def get_stats(telegram_id: int) -> Dict[str, int]:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM applications WHERE telegram_id = ?", (telegram_id,)) as cursor:
                total = (await cursor.fetchone())[0]
            async with db.execute(
                "SELECT status, COUNT(*) FROM applications WHERE telegram_id = ? GROUP BY status",
                (telegram_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                stats = {row[0]: row[1] for row in rows}
            today = datetime.now().date().isoformat()
            async with db.execute(
                "SELECT COUNT(*) FROM applications WHERE telegram_id = ? AND status = 'sent' AND date(created_at) = ?",
                (telegram_id, today)
            ) as cursor:
                sent_today = (await cursor.fetchone())[0]
            return {
                'total': total,
                'sent': stats.get('sent', 0),
                'revaz_skip': stats.get('revaz_skip', 0),
                'error': stats.get('error', 0),
                'ai_error': stats.get('ai_error', 0),
                'sent_today': sent_today
            }

    @staticmethod
    async def get_recent_applications(telegram_id: int, limit: int = 10, status: str = None) -> List[Dict]:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM applications WHERE telegram_id = ?"
            params = [telegram_id]
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]