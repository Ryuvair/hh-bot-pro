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
        # Шаг 1: анализ
        analysis_prompt = RESUME_ANALYSIS_PROMPT.format(resume=resume)
        analysis_response = self.ai.generate(analysis_prompt, max_tokens=1500)
        logger.info(f"Алина ответила: {analysis_response[:300]}")
        
        result = self._parse_analysis(analysis_response)
        result['raw_analysis'] = analysis_response  # сохраняем полный ответ
        
        # Генерируем улучшенное резюме только если оценка ниже 9
        improvements = result.get('improvements', [])
        if result.get('score', 5) < 9 and improvements:
            improve_prompt = RESUME_IMPROVE_PROMPT.format(
                original_resume=resume,
                improvements='\n'.join(f"- {imp}" for imp in improvements)
            )
            try:
                improved_resume = self.ai.generate(improve_prompt, max_tokens=1500)
                result['improved_resume'] = improved_resume.strip()
                logger.info("Алина сгенерировала улучшенное резюме")
            except Exception as e:
                logger.error(f"Ошибка при генерации улучшенного резюме: {e}")
                result['improved_resume'] = None
        else:
            result['improved_resume'] = None
        
        return result
    
    def _parse_analysis(self, response: str) -> Dict:
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
            line_stripped = line.strip()

            # Ищем оценку в разных форматах
            score_match = re.search(r'(?:оценка|общая оценка|score)[:\s*#]*(\d+)\s*(?:/\s*10)?', line_stripped.lower())
            if score_match:
                result['score'] = min(10, max(1, int(score_match.group(1))))
                continue

            if line_stripped.startswith('СИЛЬНЫЕ СТОРОНЫ') or '**Сильные стороны' in line_stripped or '### Сильные' in line_stripped:
                section = 'strengths'
                continue
            elif line_stripped.startswith('СЛАБЫЕ СТОРОНЫ') or '**Слабые стороны' in line_stripped or '### Слабые' in line_stripped or 'РЕКОМЕНДАЦИИ' in line_stripped or '### Области' in line_stripped:
                section = 'weaknesses'
                continue
            elif 'КЛЮЧЕВЫЕ СЛОВА' in line_stripped.upper():
                keywords_str = re.sub(r'.*КЛЮЧЕВЫЕ СЛОВА[^:]*:', '', line_stripped, flags=re.IGNORECASE).strip()
                keywords_str = keywords_str.strip('[]**')
                result['keywords'] = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
                section = None
            elif line_stripped.startswith('JSON_IMPROVEMENTS:'):
                json_str = line_stripped.replace('JSON_IMPROVEMENTS:', '').strip()
                in_json = True
                section = None
            elif in_json:
                json_str += " " + line_stripped
                if '}' in line_stripped:
                    in_json = False
            elif section == 'strengths':
                # Принимаем строки с - или ** или цифры с точкой
                clean = re.sub(r'^[-*\d.)\s]+\**', '', line_stripped).strip('*').strip()
                if clean and len(clean) > 5:
                    result['strengths'].append(clean)
            elif section == 'weaknesses':
                clean = re.sub(r'^[-*\d.)\s]+\**', '', line_stripped).strip('*').strip()
                if clean and len(clean) > 5:
                    result['weaknesses'].append(clean)

        # Если оценка не найдена построчно — ищем по всему тексту
        if result['score'] == 5:
            match = re.search(r'(?:оценка|общая оценка)[:\s*]*(\d+)\s*/\s*10', response.lower())
            if match:
                result['score'] = min(10, max(1, int(match.group(1))))

        # Парсим JSON с улучшениями
        if json_str:
            try:
                match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                    result['improvements'] = data.get('improvements', [])
            except Exception as e:
                logger.warning(f"Не удалось распарсить JSON улучшений: {e}")

        # Fallback — если сильные/слабые стороны не нашли через секции
        if not result['strengths'] and not result['weaknesses']:
            result['improvements'] = result['weaknesses'].copy() or [
                "Добавить конкретные метрики и результаты",
                "Улучшить формулировки опыта работы",
                "Добавить ключевые слова для ATS"
            ]

        # Если improvements пустой — берём слабые стороны
        if not result['improvements'] and result['weaknesses']:
            result['improvements'] = result['weaknesses'][:5]

        return result