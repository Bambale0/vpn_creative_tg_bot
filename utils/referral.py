"""
Модуль для работы с реферальной системой
"""

from config.dependencies import t
from config.config import BOT_USERNAME
from utils.game import get_referral_info, get_user_referral_code


async def referral_ui(user_id: int) -> str:
    """
    Получить интерфейс реферальной системы
    
    Args:
        user_id: ID пользователя
    
    Returns:
        str: текст реферального интерфейса
    """
    try:
        # Получаем информацию о рефералах
        referral_info = await get_referral_info(user_id)
        referral_code = await get_user_referral_code(user_id)
        
        # Получаем полную реферальную ссылку
        from utils.game import get_full_referral_link
        referral_link = await get_full_referral_link(user_id)
        
        # Формируем текст с данными
        return await t(user_id, "referral_ui",
                     code=referral_code,
                     link=referral_link,
                     count=referral_info["referral_count"],
                     total_days=referral_info["total_bonus"],
                     bot_username=BOT_USERNAME)
    except Exception as e:
        # В случае ошибки логируем и возвращаем базовый текст без кода
        from config.dependencies import log
        log().error(f"Error in referral_ui for user {user_id}: {e}")

        return await t(user_id, "referral_ui",
                     code="ERROR",
                     link=f"https://t.me/{BOT_USERNAME}?start=ref_ERROR",
                     count=0,
                     total_days=0,
                     bot_username=BOT_USERNAME)
