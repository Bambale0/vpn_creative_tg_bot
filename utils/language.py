"""
Модуль для работы с языками
"""

import aiosqlite
from config.config import DB_PATH


async def get_user_language(user_id: int) -> str:
    """
    Получить язык пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        str: код языка (ru/en/de)
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute(
                "SELECT language FROM users_info WHERE user_id = ?",
                (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else "ru"
    except Exception:
        return "ru"
