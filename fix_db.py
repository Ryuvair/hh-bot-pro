"""
Скрипт починки БД — конвертирует старые резюме в новый формат
"""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/hh_bot.db")

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    
    for user in users:
        user = dict(user)
        telegram_id = user['telegram_id']
        resume_text = user.get('resume_text', '')
        resumes_raw = user.get('resumes')
        
        # Если resumes пустой или null — конвертируем
        resumes = None
        if resumes_raw:
            try:
                resumes = json.loads(resumes_raw)
            except:
                resumes = None
        
        if not resumes and resume_text:
            # Создаём правильный формат
            resumes = [{"name": "Основное", "text": resume_text}]
            cursor.execute(
                "UPDATE users SET resumes = ?, active_resume_index = 0 WHERE telegram_id = ?",
                (json.dumps(resumes, ensure_ascii=False), telegram_id)
            )
            print(f"✅ Починил пользователя {telegram_id}")
        else:
            print(f"ℹ️ Пользователь {telegram_id} уже в порядке")
    
    conn.commit()
    print("✅ Готово!")