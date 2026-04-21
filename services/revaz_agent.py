"""
Реваз - технический скрининг вакансий (смягчённая версия)
"""
from core.ai_client import get_ai_client
from core.prompts import REVAZ_CHECKLIST_PROMPT, REVAZ_VERDICT_PROMPT
from core.logger import logger
import json

class RevazAgent:
    def __init__(self, resume: str):
        self.ai = get_ai_client()
        self.resume = resume if resume else "Резюме не загружено."
        self.strict_mode = False  # можно переключить в настройках позже
    
    def check(self, vacancy: dict, vac_text: str) -> tuple[bool, str]:
        """
        Возвращает (подходит, причина).
        В нестрогом режиме всегда возвращает True, но пишет предупреждение.
        """
        # Если нет описания вакансии — пропускаем
        if not vac_text:
            logger.debug("Реваз: нет описания вакансии, пропускаем")
            return True, "no_description"
        
        # Формируем чек-лист
        checklist_prompt = REVAZ_CHECKLIST_PROMPT.format(
            vacancy_title=vacancy['title'],
            vacancy_description=vac_text,
            resume=self.resume
        )
        try:
            checklist_str = self.ai.generate(checklist_prompt, max_tokens=500)
            checklist = json.loads(checklist_str)
        except Exception as e:
            logger.debug(f"Реваз не смог сформировать чек-лист: {e}")
            return True, "checklist_parse_error"
        
        if not checklist:
            logger.debug("Реваз: чек-лист пуст, пропускаем")
            return True, "empty_checklist"
        
        # Проверяем резюме по чек-листу
        verdict_prompt = REVAZ_VERDICT_PROMPT.format(
            vacancy_title=vacancy['title'],
            vacancy_description=vac_text,
            checklist=json.dumps(checklist, ensure_ascii=False),
            resume=self.resume
        )
        try:
            verdict_str = self.ai.generate(verdict_prompt, max_tokens=300)
        except Exception as e:
            logger.debug(f"Реваз: ошибка при проверке чек-листа: {e}")
            return True, "verdict_error"
        
        # Анализируем вердикт
        verdict_upper = verdict_str.upper()
        if "PASS" in verdict_upper:
            logger.debug(f"Реваз одобрил: {verdict_str[:80]}")
            return True, "passed"
        
        # В строгом режиме отклоняем, иначе просто предупреждаем
        if self.strict_mode:
            logger.info(f"🛡️ Реваз строго отклонил: {verdict_str[:80]}")
            return False, verdict_str[:100]
        else:
            logger.warning(f"⚠️ Реваз рекомендует пропустить, но продолжаем: {verdict_str[:80]}")
            return True, f"warning: {verdict_str[:100]}"