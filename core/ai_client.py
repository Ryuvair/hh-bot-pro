"""
AI-клиент только для DeepSeek с асинхронными обёртками
"""
import os
import asyncio
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
from config.settings import DEEPSEEK_API_KEY
from core.logger import logger, log_ai

load_dotenv()

class AIClient:
    def __init__(self):
        self.deepseek_client = None
        self._init_deepseek()
    
    def _init_deepseek(self):
        if DEEPSEEK_API_KEY:
            try:
                self.deepseek_client = OpenAI(
                    api_key=DEEPSEEK_API_KEY,
                    base_url="https://api.deepseek.com/v1"
                )
                logger.info("✅ DeepSeek подключен")
            except Exception as e:
                logger.error(f"❌ Ошибка подключения DeepSeek: {e}")
                self.deepseek_client = None
        else:
            logger.warning("⚠️ DeepSeek API ключ не найден")
    
    def generate_with_deepseek(self, prompt: str, temperature: float = 0.7, max_tokens: int = 500) -> str:
        if not self.deepseek_client:
            raise Exception("DeepSeek не настроен")
        
        response = self.deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        result = response.choices[0].message.content.strip()
        log_ai("DeepSeek", prompt[:200], result)
        return result
    
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 500) -> str:
        return self.generate_with_deepseek(prompt, temperature, max_tokens)
    
    def is_available(self) -> bool:
        return self.deepseek_client is not None

_ai_client: Optional[AIClient] = None
_init_lock = asyncio.Lock()

async def get_ai_client_async() -> AIClient:
    """Асинхронное получение AI-клиента (инициализация в отдельном потоке)"""
    global _ai_client
    if _ai_client is None:
        async with _init_lock:
            if _ai_client is None:
                from core.async_executor import run_in_thread
                _ai_client = await run_in_thread(_init_ai_client_sync)
    return _ai_client

def _init_ai_client_sync() -> AIClient:
    """Синхронная инициализация (вызывается в потоке)"""
    return AIClient()

def get_ai_client() -> AIClient:
    """Синхронное получение (для использования в потоках сессий)"""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client