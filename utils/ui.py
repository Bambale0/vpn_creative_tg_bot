"""
Модуль для UI компонентов
"""

from aiogram import types
from config.dependencies import t


async def show_loading(user_id: int) -> types.Message:
    """
    Показать индикатор загрузки
    
    Args:
        user_id: ID пользователя
    
    Returns:
        types.Message: сообщение с индикатором загрузки
    """
    from config.dependencies import get_bot_instance
    bot_instance = get_bot_instance()  # Получаем экземпляр бота
    return await bot_instance.send_message(user_id, await t(user_id, "loading"))
