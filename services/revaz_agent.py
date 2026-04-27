"""
Реваз - технический скрининг вакансий
"""
from core.ai_client import get_ai_client
from core.prompts import REVAZ_CHECKLIST_PROMPT, REVAZ_VERDICT_PROMPT
from core.logger import logger
import json
import re

class RevazAgent:
    def __init__(self, resume: str):
        self.ai = get_ai_client()
        self.resume = resume if resume else "Резюме не загружено."
        self.strict_mode = False

    def _parse_json(self, text: str):
        """Вытаскивает JSON даже если AI добавил лишний текст вокруг"""
        try:
            return json.loads(text)
        except:
            pass
        match = re.search(r'(\[.*?\]|\{.*?\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        return None

    def _extract_score(self, verdict_str: str) -> int:
        """Вытаскивает процент матча"""
        match = re.search(r'СКОР:\s*(\d+)%?', verdict_str)
        if match:
            return min(100, max(1, int(match.group(1))))
        match = re.search(r'(\d+)%', verdict_str)
        if match:
            return min(100, max(1, int(match.group(1))))
        if 'PASS' in verdict_str.upper():
            return 70
        return 30

    def _extract_reason(self, verdict_str: str) -> str:
        """Вытаскивает причину из вердикта — несколько вариантов парсинга"""
        # Вариант 1: ПРИЧИНА: текст
        match = re.search(r'ПРИЧИНА:\s*(.+?)(?=\nДЕТАЛИ:|$)', verdict_str, re.DOTALL)
        if match:
            return match.group(1).strip()[:200]

        # Вариант 2: берём строку после ВЕРДИКТА и СКОРА
        lines = verdict_str.strip().split('\n')
        for i, line in enumerate(lines):
            if 'ПРИЧИНА' in line.upper():
                # Берём текст после двоеточия на этой же строке
                parts = line.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()[:200]
                # Или следующую строку
                if i + 1 < len(lines) and lines[i + 1].strip():
                    return lines[i + 1].strip()[:200]

        # Вариант 3: берём любую содержательную строку после вердикта
        for line in lines:
            line = line.strip()
            if (line and
                'ВЕРДИКТ' not in line.upper() and
                'СКОР' not in line.upper() and
                'ДЕТАЛИ' not in line.upper() and
                len(line) > 20):
                return line[:200]

        return "Комментарий недоступен"

    def check(self, vacancy: dict, vac_text: str) -> tuple[bool, str, int]:
        """Возвращает (подходит, причина, скор)."""
        if not vac_text:
            return True, "Описание вакансии отсутствует", 50

        # Формируем чек-лист
        checklist_prompt = REVAZ_CHECKLIST_PROMPT.format(
            vacancy_title=vacancy['title'],
            vacancy_description=vac_text,
            resume=self.resume
        )
        try:
            checklist_str = self.ai.generate(checklist_prompt, max_tokens=500)
            checklist = self._parse_json(checklist_str)
            if not checklist:
                raise ValueError("Пустой чек-лист")
        except Exception as e:
            logger.debug(f"Реваз не смог сформировать чек-лист: {e}")
            return True, "Скрининг недоступен", 50

        # Проверяем резюме по чек-листу
        verdict_prompt = REVAZ_VERDICT_PROMPT.format(
            vacancy_title=vacancy['title'],
            vacancy_description=vac_text,
            checklist=json.dumps(checklist, ensure_ascii=False),
            resume=self.resume
        )
        try:
            verdict_str = self.ai.generate(verdict_prompt, max_tokens=400)
            logger.debug(f"Реваз вердикт: {verdict_str[:300]}")
        except Exception as e:
            logger.debug(f"Реваз: ошибка вердикта: {e}")
            return True, "Скрининг недоступен", 50

        score = self._extract_score(verdict_str)
        passed = 'PASS' in verdict_str.upper()
        reason = self._extract_reason(verdict_str)

        if passed:
            logger.debug(f"✅ Реваз одобрил ({score}%): {reason[:80]}")
        else:
            logger.warning(f"⚠️ Реваз сомневается ({score}%): {reason[:80]}")
            passed = True  # в нестрогом режиме всё равно показываем

        return passed, reason, score