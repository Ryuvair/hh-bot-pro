"""
Алина — анализ и улучшение резюме (двухэтапный процесс, без выдумки)
"""
import re
import json
from typing import Dict, List
from core.ai_client import get_ai_client
from core.prompts import RESUME_ANALYSIS_PROMPT, RESUME_IMPROVE_PROMPT
from core.logger import logger

class ResumeImprover:
    def __init__(self):
        self.ai = get_ai_client()
    
    def analyze(self, resume: str) -> Dict:
        """
        Анализирует резюме, получает список улучшений,
        затем генерирует улучшенную версию через отдельный промпт.
        """
        # Шаг 1: анализ
        analysis_prompt = RESUME_ANALYSIS_PROMPT.format(resume=resume)
        analysis_response = self.ai.generate(analysis_prompt, max_tokens=1200)
        
        result = self._parse_analysis(analysis_response)
        
        # Если есть инструкции по улучшению, генерируем улучшенное резюме
        improvements = result.get('improvements', [])
        if improvements:
            improve_prompt = RESUME_IMPROVE_PROMPT.format(
                original_resume=resume,
                improvements='\n'.join(f"- {imp}" for imp in improvements)
            )
            try:
                improved_resume = self.ai.generate(improve_prompt, max_tokens=1500)
                result['improved_resume'] = improved_resume.strip()
                logger.info("Алина сгенерировала улучшенное резюме по инструкциям")
            except Exception as e:
                logger.error(f"Ошибка при генерации улучшенного резюме: {e}")
                result['improved_resume'] = None
        else:
            result['improved_resume'] = None
        
        return result
    
    def _parse_analysis(self, response: str) -> Dict:
        """Парсит ответ AI из первого этапа"""
        result = {
            'score': 5,
            'strengths': [],
            'weaknesses': [],
            'keywords': [],
            'improvements': []
        }
        
        lines = response.split('\n')
        section = None
        json_str = ""
        in_json = False
        
        for line in lines:
            line = line.strip()
            if line.startswith('ОЦЕНКА:'):
                match = re.search(r'(\d+)', line)
                if match:
                    result['score'] = int(match.group(1))
            elif line.startswith('СИЛЬНЫЕ СТОРОНЫ:'):
                section = 'strengths'
                continue
            elif line.startswith('СЛАБЫЕ СТОРОНЫ') or line.startswith('СЛАБЫЕ СТОРОНЫ / РЕКОМЕНДАЦИИ:'):
                section = 'weaknesses'
                continue
            elif line.startswith('КЛЮЧЕВЫЕ СЛОВА ДЛЯ ATS:'):
                keywords_str = line.replace('КЛЮЧЕВЫЕ СЛОВА ДЛЯ ATS:', '').strip()
                keywords_str = keywords_str.strip('[]')
                result['keywords'] = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                section = None
            elif line.startswith('JSON_IMPROVEMENTS:'):
                json_str = line.replace('JSON_IMPROVEMENTS:', '').strip()
                in_json = True
                section = None
            elif in_json:
                json_str += " " + line
            elif section == 'strengths' and line.startswith('-'):
                result['strengths'].append(line[1:].strip())
            elif section == 'weaknesses' and line.startswith('-'):
                result['weaknesses'].append(line[1:].strip())
        
        # Парсим JSON с улучшениями
        if json_str:
            try:
                # Ищем JSON объект
                match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                    result['improvements'] = data.get('improvements', [])
            except Exception as e:
                logger.warning(f"Не удалось распарсить JSON улучшений: {e}")
                # Fallback: используем слабые стороны как улучшения
                result['improvements'] = result['weaknesses'].copy()
        
        return result