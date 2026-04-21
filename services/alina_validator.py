"""
Алина — строгий HR, который не прощает воды
"""
from core.ai_client import get_ai_client
from core.prompts import ALINA_VALIDATE_PROMPT, ALINA_IMPROVE_PROMPT
from core.logger import logger

class AlinaValidator:
    def __init__(self):
        self.ai = get_ai_client()
    
    def validate_and_improve(self, letter: str, resume: str, vac_text: str, title: str) -> str:
        # Быстрая проверка на запрещёнку
        forbidden = ['уважаемый', 'с уважением', 'буду рад', 'желаю успехов',
                     'меня заинтересовала', 'прошу рассмотреть', 'здравствуйте', 'добрый день']
        letter_lower = letter.lower()
        if any(word in letter_lower for word in forbidden):
            return self._force_improve(letter, resume, title,
                                       "Убрать все запрещённые слова, подпись, писать от мужского лица, сразу с сути.")
        
        # Проверка на женский род
        female_indicators = ['работала', 'координировала', 'внедряла', 'сократила', 'занималась', 'была', 'стала']
        if any(word in letter_lower for word in female_indicators):
            return self._force_improve(letter, resume, title,
                                       "Писать от МУЖСКОГО лица (работал, координировал, внедрил).")

        # Проверка на наличие цифр/фактов
        if not any(char.isdigit() for char in letter) and not any(w in letter_lower for w in ['процент', 'клиент', 'проект', 'сократил', 'увеличил']):
            return self._force_improve(letter, resume, title,
                                       "Добавить конкретику: цифры, результаты, факты из резюме. Без воды.")
        
        # Проверка длины
        words = len(letter.split())
        if words < 20 or words > 100:
            return self._force_improve(letter, resume, title,
                                       f"Сделать объём 30-80 слов (сейчас {words}). Убрать воду или добавить конкретики.")
        
        # Полная проверка AI
        prompt = ALINA_VALIDATE_PROMPT.format(letter=letter, vacancy_title=title)
        verdict = self.ai.generate(prompt, max_tokens=200)
        if "SEND" in verdict.upper() and "IMPROVE" not in verdict.upper():
            return letter
        
        return self._force_improve(letter, resume, title, verdict)
    
    def _force_improve(self, letter: str, resume: str, title: str, problems: str) -> str:
        improve_prompt = ALINA_IMPROVE_PROMPT.format(
            original_letter=letter,
            problems=problems,
            resume=resume,
            vacancy_title=title
        )
        improved = self.ai.generate(improve_prompt, max_tokens=500)
        logger.info("Алина жёстко улучшила письмо")
        return improved