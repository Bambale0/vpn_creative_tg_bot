"""
Command handlers for VPN Telegram Bot
"""

import aiosqlite
from config.config import DB_PATH

"""
Чистые функции для обработки команд
"""
from utils.menu import main_menu, profile_menu, referral_menu, setup_instructions_menu


def get_user_id_from_message(message):
    """Безопасное получение user_id из сообщения"""
    if hasattr(message, 'from_user') and message.from_user is not None:
        return message.from_user.id
    elif hasattr(message, 'chat') and message.chat is not None:
        return message.chat.id
    else:
        # Fallback - используем 0 или генерируем ошибку
        return 0


async def process_referral_link(user_id: int, referral_code: str, message):
    """Обработка реферальной ссылки"""
    try:
        from utils.game import get_user_id_from_referral_code
        from config.dependencies import log, t as translate_func

        # Валидация входных данных
        if not referral_code or not isinstance(referral_code, str):
            await message.answer(await translate_func(user_id, "invalid_referral_code"))
            return

        # Убираем префикс REF если есть (для совместимости)
        clean_code = referral_code
        if clean_code.startswith('REF'):
            clean_code = clean_code[3:]

        # Проверяем минимальную длину кода (минимум 6 символов для кода)
        if len(clean_code) < 6:
            await message.answer(await translate_func(user_id, "invalid_referral_code"))
            return
        
        # Проверяем, не является ли пользователь уже рефералом
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute(
                "SELECT inviter_id FROM referrals WHERE invited_id = ?",
                (user_id,)
            )
            existing_referral = await cursor.fetchone()
            
            if existing_referral:
                await message.answer(await translate_func(user_id, "already_referred"))
                return
        
        # Получаем ID реферера из кода
        inviter_id = await get_user_id_from_referral_code(clean_code)
        
        if not inviter_id:
            await message.answer(await translate_func(user_id, "invalid_referral_code"))
            return
        
        # Проверяем, не пытается ли пользователь пригласить сам себя
        if inviter_id == user_id:
            await message.answer(await translate_func(user_id, "cannot_refer_self"))
            return
        
        # Проверяем, существует ли реферер в базе
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?",
                (inviter_id,)
            )
            referrer_exists = await cursor.fetchone()
            
            if not referrer_exists:
                await message.answer(await translate_func(user_id, "invalid_referral_code"))
                return
        
        # Сохраняем реферальную связь
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            await conn.execute(
                "INSERT INTO referrals (inviter_id, invited_id, referral_date) VALUES (?, ?, datetime('now'))",
                (inviter_id, user_id)
            )
            await conn.commit()
        
        # Отправляем уведомления
        await message.answer(await translate_func(user_id, "referral_joined", inviter_code=referral_code))

        # Уведомляем реферера
        try:
            from config.dependencies import get_bot_instance
            bot = get_bot_instance()
            if bot:
                await bot.send_message(
                    inviter_id,
                    await translate_func(inviter_id, "new_referral_joined", referral_code=referral_code)
                )
        except Exception as e:
            from config.dependencies import log
            log().error(f"Failed to notify referrer {inviter_id}: {e}")

        log().info(f"Successfully processed referral link for user {user_id} with code {referral_code}")

    except Exception as e:
        from config.dependencies import log
        log().error(f"Error processing referral link for user {user_id}: {e}")
        await message.answer("❌ Произошла ошибка при обработке реферальной ссылки.")


async def handle_start_command(message):
    """Обработка команды /start"""
    from config.dependencies import get_bot_instance
    bot = get_bot_instance()
    
    user_id = get_user_id_from_message(message)
    
    # Обработка реферальных ссылок
    args = message.text.split()
    if len(args) > 1:
        start_arg = args[1]
        if start_arg.startswith('ref_'):
            # Реферальная ссылка
            referral_code = start_arg[4:]  # Убираем 'ref_' префикс
            await process_referral_link(user_id, referral_code, message)
            return
    
    keyboard = await main_menu(user_id)
    
    # Оптимизированный текст приветствия
    welcome_text = """🌟 <b>Chill Creative VPN</b>

🔒 <b>Ваша свобода в интернете</b>

🚀 <b>Что я умею:</b>
• 🎁 Бесплатный тест на 10 дней
• 🛡️ Настройка VPN за 1 минуту
• 📊 Ваш персональный профиль
• 💎 Лучшие тарифы с выгодой -17%
• 🎯 Бонусы за ежедневные визиты
• 👥 Приглашай друзей → получай дни
• 📋 Полные инструкции по настройке
• ⚡ Преимущества WireGuard технологии

<i>👇 Выберите действие:</i>"""

    # Используем message.answer если bot не доступен (polling режим)
    if bot is not None:
        await bot.send_message(
            chat_id=message.chat.id,
            text=welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            text=welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


async def handle_menu_command(message):
    """Обработка команды /menu"""
    user_id = get_user_id_from_message(message)
    keyboard = await main_menu(user_id)

    # Оптимизированный текст приветствия
    welcome_text = """� <b>Chill Creative VPN</b>

🔒 <b>Ваша свобода в интернете</b>

🚀 <b>Что я умею:</b>
• 🎁 Бесплатный тест на 10 дней
• 🛡️ Настройка VPN за 1 минуту
• 📊 Ваш персональный профиль
• 💎 Лучшие тарифы с выгодой -17%
• 🎯 Бонусы за ежедневные визиты
• 👥 Приглашай друзей → получай дни
• � Полные инструкции по настройке
• ⚡ Преимущества WireGuard технологии

<i>👇 Выберите действие:</i>"""

    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def handle_profile_command(message):
    """Обработка команды /profile"""
    user_id = get_user_id_from_message(message)
    profile_text, markup = await profile_menu(user_id)
    await message.answer(profile_text, reply_markup=markup)


async def handle_daily_command(message):
    """Обработка команды /daily"""
    from utils.menu import daily_bonus_menu
    user_id = get_user_id_from_message(message)
    await daily_bonus_menu(user_id, message)


async def handle_referral_command(message):
    """Обработка команды /referral"""
    user_id = get_user_id_from_message(message)
    await referral_menu(user_id, message)


async def handle_setup_command(message):
    """Обработка команды /setup"""
    user_id = get_user_id_from_message(message)
    await setup_instructions_menu(user_id, message)


async def handle_welcome_command(message):
    """Обработка команды /welcome с кратким описанием"""
    user_id = get_user_id_from_message(message)
    keyboard = await main_menu(user_id)

    welcome_text = """🌟 <b>Chill Creative VPN</b>

🔒 <b>Свобода в интернете:</b>
• 🚀 Быстрый VPN WireGuard
• 🌍 Нет блокировок
• � Полная конфиденциальность
• 🎁 Бесплатный тест
• ⚡ 1 минута настройки

<i>👇 Выберите действие:</i>"""

    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
