"""
Асинхронный исполнитель для CPU/IO-bound задач в Telegram-боте.
Использует ThreadPoolExecutor для неблокирующего выполнения синхронных функций.
"""
import asyncio
import concurrent.futures
from core.logger import logger

# Пул из 10 потоков (можно увеличить при необходимости)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="tg_worker")

async def run_in_thread(func, *args, **kwargs):
    """
    Выполняет синхронную функцию func(*args, **kwargs) в отдельном потоке,
    не блокируя event loop.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(_executor, lambda: func(*args, **kwargs))
    except Exception as e:
        logger.error(f"Ошибка в потоке {func.__name__}: {e}")
        raise