"""
Модуль для работы с поддержкой
"""

from config.dependencies import t


async def support_menu(user_id: int) -> str:
    """
    Получить меню поддержки
    
    Args:
        user_id: ID пользователя
    
    Returns:
        str: текст меню поддержки
    """
    return await t(user_id, "support_menu")
