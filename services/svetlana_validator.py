"""
Светлана Викторовна — проверка русского языка
"""
from core.ai_client import get_ai_client
from core.prompts import SVETLANA_VALIDATE_PROMPT
from core.logger import logger

class SvetlanaValidator:
    def __init__(self):
        self.ai = get_ai_client()
    
    def validate_and_fix(self, letter: str) -> str:
        """Проверяет письмо и возвращает исправленную версию"""
        prompt = SVETLANA_VALIDATE_PROMPT.format(letter=letter)
        try:
            response = self.ai.generate(prompt, max_tokens=600)
            
            if "ИСПРАВЛЕННОЕ ПИСЬМО:" in response:
                parts = response.split("ИСПРАВЛЕННОЕ ПИСЬМО:")
                if len(parts) > 1:
                    fixed = parts[1].strip()
                    logger.info("Светлана Викторовна внесла правки")
                    return fixed
            
            if "ОШИБОК НЕТ" in response.upper():
                logger.info("Светлана Викторовна: ошибок нет")
            else:
                logger.warning("Светлана Викторовна: не удалось распарсить ответ")
            
            return letter
        except Exception as e:
            logger.error(f"Ошибка при проверке Светланой Викторовной: {e}")
            return letter