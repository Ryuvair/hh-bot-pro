"""
Генерация сопроводительных писем (без валидаторов)
"""
import re
from core.ai_client import get_ai_client
from core.prompts import COVER_LETTER_STRUCTURED
from core.logger import logger, log_ai

class LetterGenerator:
    def __init__(self):
        self.ai = get_ai_client()
    
    def _clean_letter(self, letter: str) -> str:
        """Вырезает любой мусор: валидаторские блоки, женский род, подписи"""
        lines = letter.split('\n')
        cleaned = []
        for line in lines:
            low = line.lower()
            # Пропускаем строки с мусором
            if any(x in low for x in [
                'уважаемый', 'с уважением', 'буду рад', 'желаю успехов',
                'меня заинтересовала', 'прошу рассмотреть', 'здравствуйте',
                'благодарю за внимание', 'добрый день',
                'основные правки', 'исправленное письмо', 'ошибки:',
                'согласование по роду', 'лексика и стиль', 'грамматика',
                'координировала', 'работала', 'готова', 'занималась'
            ]):
                continue
            cleaned.append(line)
        letter = '\n'.join(cleaned).strip()
        
        # Убираем префиксы от валидаторов
        letter = re.sub(r'(?i)^.*исправленное письмо:\s*', '', letter)
        letter = re.sub(r'(?i)^.*основные правки:.*$', '', letter, flags=re.MULTILINE)
        letter = re.sub(r'(?i)\s*с уважением,?\s*', '', letter)
        letter = re.sub(r'(?i)\s*благодарю за внимание,?\s*', '', letter)
        letter = re.sub(r'\n[А-Я][а-я]+(?:\s+[А-Я][а-я]+)?\s*$', '', letter)
        
        if len(letter.split()) < 15:
            letter = "Вижу, нужен специалист с опытом в вашей сфере. Мой опыт соответствует требованиям. Готов обсудить детали."
        return letter.strip()
    
    def generate(self, resume: str, vac_text: str, title: str) -> str:
        prompt = COVER_LETTER_STRUCTURED.format(
            resume=resume,
            title=title,
            description=vac_text
        )
        try:
            letter = self.ai.generate(prompt, max_tokens=800)
            log_ai("COVER_LETTER_STRUCTURED", prompt[:200], letter)
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return "Вижу, нужен специалист с опытом в вашей сфере. Мой опыт соответствует требованиям. Готов обсудить детали."
        
        letter = self._clean_letter(letter)
        return letter