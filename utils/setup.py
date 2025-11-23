"""
Модуль для инструкций по настройке
"""

from config.dependencies import t


async def setup_instructions(user_id: int) -> str:
    """
    Получить инструкции по настройке
    
    Args:
        user_id: ID пользователя
    
    Returns:
        str: текст инструкций
    """
    return await t(user_id, "setup_instructions")
