"""
Утилиты для обработки callback запросов Telegram
"""

from typing import Callable, Any
import asyncio
from functools import wraps


def handle_expired_callbacks(func: Callable) -> Callable:
    """
    Декоратор для обработки истекших callback запросов
    
    Этот декоратор перехватывает ошибки истекших callback запросов Telegram
    и предотвращает появление ошибок в логах.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_str = str(e)
            # Проверяем, является ли ошибка устаревшим callback
            if ("query is too old" in error_str or 
                "Bad Request: query is too old" in error_str or
                "response timeout expired" in error_str or
                "query ID is invalid" in error_str):
                # Логируем как предупреждение, а не ошибку
                from config.dependencies import log
                log().warning(f"Expired callback ignored: {error_str}")
                return  # Игнорируем устаревшие callbacks
            raise  # Пробрасываем другие ошибки
    return wrapper


def is_callback_expired_error(error: Exception) -> bool:
    """
    Проверяет, является ли ошибка ошибкой истекшего callback запроса
    """
    error_str = str(error)
    return ("query is too old" in error_str or 
            "Bad Request: query is too old" in error_str or
            "response timeout expired" in error_str or
            "query ID is invalid" in error_str)