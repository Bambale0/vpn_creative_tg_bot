"""
Game mechanics and user progression system
"""

import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio

from config.config import DB_PATH, TRIAL_DAYS, REFERRAL_BONUS_FIRST, REFERRAL_BONUS_SUBSEQUENT, REFERRAL_ENABLED
from config.dependencies import log, t as translate_func


async def add_user_points(user_id: int, points: int, reason: str) -> bool:
    """
    Добавить очки пользователю
    
    Args:
        user_id: ID пользователя
        points: количество очков
        reason: причина начисления
    
    Returns:
        bool: успешность операции
    """
    max_retries = 3
    retry_delay = 0.1  # 100ms
    
    for attempt in range(max_retries):
        try:
            async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
                # Получаем текущие очки
                cursor = await conn.execute(
                    "SELECT points FROM users WHERE user_id = ?",
                    (user_id,)
                )
                result = await cursor.fetchone()
                
                if result:
                    current_points = result[0] if result[0] is not None else 0
                    new_points = current_points + points
                    
                    # Обновляем очки
                    await conn.execute(
                        "UPDATE users SET points = ? WHERE user_id = ?",
                        (new_points, user_id)
                    )
                else:
                    # Создаем запись пользователя
                    await conn.execute(
                        "INSERT INTO users (user_id, points) VALUES (?, ?)",
                        (user_id, points)
                    )
                
                # Логируем начисление очков
                await conn.execute(
                    """INSERT INTO points_log 
                    (user_id, points, reason, timestamp) 
                    VALUES (?, ?, ?, datetime('now'))""",
                    (user_id, points, reason)
                )
                
                await conn.commit()
                
                logging.getLogger("game").info(f"Added {points} points to user {user_id} for {reason}")
                return True

        except Exception as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logging.getLogger("game").warning(f"Database locked, retrying ({attempt + 1}/{max_retries}) for user {user_id}")
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            logging.getLogger("game").error(f"Error adding points to user {user_id}: {e}")
            return False
    
    return False


async def check_achievements(user_id: int, achievement_type: str) -> Dict[str, bool]:
    """
    Проверить и разблокировать достижения
    
    Args:
        user_id: ID пользователя
        achievement_type: тип достижения
    
    Returns:
        Dict: информация о разблокированных достижениях
    """
    achievements = {
        "first_purchase": False,
        "daily_streak": False,
        "referral_master": False,
        "vip_status": False
    }
    
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
                # Проверяем существующие достижения
                cursor = await conn.execute(
                    "SELECT achievement_type FROM user_achievements WHERE user_id = ?",
                    (user_id,)
                )
                existing_achievements = await cursor.fetchall()
                
                # Проверяем условия для каждого типа достижения
                if achievement_type == "first_purchase":
                    # Проверяем первую покупку
                    cursor = await conn.execute(
                        "SELECT COUNT(*) FROM subscriptions WHERE user_id = ?",
                        (user_id,)
                    )
                    purchase_count = (await cursor.fetchone())[0]
                    
                    if purchase_count == 1:
                        # Разблокируем достижение
                        await conn.execute(
                            """INSERT OR IGNORE INTO user_achievements 
                            (user_id, achievement_type, unlocked_at) 
                            VALUES (?, ?, datetime('now'))""",
                            (user_id, "first_purchase")
                        )
                        achievements["first_purchase"] = True
                
                elif achievement_type == "daily_streak":
                    # Проверяем ежедневную серию
                    cursor = await conn.execute(
                        """SELECT MAX(streak_count) FROM daily_bonus 
                        WHERE user_id = ? AND last_claim >= date('now', '-7 days')""",
                        (user_id,)
                    )
                    streak = (await cursor.fetchone())[0] or 0
                    
                    if streak >= 7:
                        await conn.execute(
                            """INSERT OR IGNORE INTO user_achievements 
                            (user_id, achievement_type, unlocked_at) 
                            VALUES (?, ?, datetime('now'))""",
                            (user_id, "daily_streak")
                        )
                        achievements["daily_streak"] = True
                
                elif achievement_type == "referral_master":
                    # Проверяем реферальную систему
                    cursor = await conn.execute(
                        "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
                        (user_id,)
                    )
                    referral_count = (await cursor.fetchone())[0]
                    
                    if referral_count >= 5:
                        await conn.execute(
                            """INSERT OR IGNORE INTO user_achievements 
                            (user_id, achievement_type, unlocked_at) 
                            VALUES (?, ?, datetime('now'))""",
                            (user_id, "referral_master")
                        )
                        achievements["referral_master"] = True
                
                elif achievement_type == "vip_status":
                    # Проверяем VIP статус (очки)
                    cursor = await conn.execute(
                        "SELECT points FROM users WHERE user_id = ?",
                        (user_id,)
                    )
                    points = (await cursor.fetchone())[0] or 0
                    
                    if points >= 1000:
                        await conn.execute(
                            """INSERT OR IGNORE INTO user_achievements 
                            (user_id, achievement_type, unlocked_at) 
                            VALUES (?, ?, datetime('now'))""",
                            (user_id, "vip_status")
                        )
                        achievements["vip_status"] = True
                
                await conn.commit()
                
                # Отправляем уведомление о новых достижениях
                new_achievements = [k for k, v in achievements.items() if v and k not in [a[0] for a in existing_achievements]]
                
                if new_achievements:
                    log().info(f"User {user_id} unlocked achievements: {new_achievements}")
                
                return achievements
                
        except Exception as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                log().warning(f"Database locked in check_achievements, retrying ({attempt + 1}/{max_retries}) for user {user_id}")
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            log().error(f"Error checking achievements for user {user_id}: {e}")
            return achievements
    
    return achievements


async def check_referral_system(user_id: int, payment_amount: float, payment_id: str) -> bool:
    """
    Обработать реферальную систему после оплата
    
    Args:
        user_id: ID пользователя
        payment_amount: сумма платежа
        payment_id: ID платежа
    
    Returns:
        bool: успешность операции
    """
    # Проверяем, включена ли реферальная система
    if not REFERRAL_ENABLED:
        return False
    
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            # Проверяем, есть ли реферер у пользователя
            cursor = await conn.execute(
                "SELECT inviter_id FROM referrals WHERE invited_id = ?",
                (user_id,)
            )
            referral = await cursor.fetchone()
            
            if referral:
                referrer_id = referral[0]
                
                # Проверяем, первая ли это покупка реферала
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM referral_bonuses WHERE referral_id = ?",
                    (user_id,)
                )
                referral_count = (await cursor.fetchone())[0]
                
                # Определяем размер бонуса: за первую покупку больше, за последующие - меньше
                if referral_count == 0:
                    bonus_amount = REFERRAL_BONUS_FIRST
                else:
                    bonus_amount = REFERRAL_BONUS_SUBSEQUENT
                
                # Добавляем очки рефереру
                await add_user_points(referrer_id, bonus_amount, "referral_bonus")
                
                # Логируем реферальный бонус
                await conn.execute(
                    """INSERT INTO referral_bonuses 
                    (inviter_id, referral_id, bonus_days, applied_date) 
                    VALUES (?, ?, ?, datetime('now'))""",
                    (referrer_id, user_id, bonus_amount)
                )
                
                await conn.commit()
                
                log().info(f"Referral bonus {bonus_amount} awarded to {referrer_id} for referral {user_id}")
                return True
            
        return False
        
    except Exception as e:
        log().error(f"Error processing referral system for user {user_id}: {e}")
        return False


async def get_trial(user_id: int, message) -> bool:
    """
    Активировать trial период для пользователя
    
    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа
    
    Returns:
        bool: успешность активации
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            # Проверяем, не активировал ли уже пользователь trial
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM trial_activations WHERE user_id = ?",
                (user_id,)
            )
            trial_count_result = await cursor.fetchone()
            trial_count = trial_count_result[0] if trial_count_result else 0
            
            if trial_count > 0:
                # Пользователь уже активировал trial
                await message.answer(await translate_func(user_id, "trial_already_used"))
                return False
            
            # Активируем trial на количество дней из конфига
            end_date = (datetime.utcnow() + timedelta(days=TRIAL_DAYS)).isoformat()
            
            await conn.execute(
                """INSERT INTO subscriptions 
                (user_id, start_date, end_date, payment_id, duration, is_trial) 
                VALUES (?, datetime('now'), ?, ?, 0, 1)""",
                (user_id, end_date, f"trial_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
            )
            
            # Записываем активацию trial
            await conn.execute(
                "INSERT OR IGNORE INTO trial_activations (user_id, activated_at) VALUES (?, datetime('now'))",
                (user_id,)
            )
            
            # Начисляем бонусные очки за активацию trial
            await add_user_points(user_id, 50, "trial_activation")
            
            await conn.commit()
            
            # Отправляем сообщение об успешной активации trial
            end_date_formatted = datetime.fromisoformat(end_date).strftime('%d.%m.%Y %H:%M')
            await message.answer(await translate_func(user_id, "trial_activated", end_date=end_date_formatted))
            
            log().info(f"Trial activated for user {user_id}")
            return True
            
    except Exception as e:
        log().error(f"Error activating trial for user {user_id}: {e}")
        return False


async def activate_trial(user_id: int, message) -> bool:
    """Алиас для get_trial"""
    return await get_trial(user_id, message)


async def claim_daily_bonus(user_id: int, message) -> bool:
    """
    Забрать ежедневный бонус
    
    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа
    
    Returns:
        bool: успешность операции
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            # Проверяем, получал ли уже пользователь бонус сегодня
            cursor = await conn.execute(
                "SELECT last_claim FROM daily_bonus WHERE user_id = ? AND date(last_claim) = date('now')",
                (user_id,)
            )
            already_claimed = await cursor.fetchone()
            
            if already_claimed:
                await message.answer(await translate_func(user_id, "daily_bonus_already_claimed"))
                return False
            
            # Начисляем бонусные очки (10-50 случайных)
            import random
            bonus_points = random.randint(10, 50)
            
            await add_user_points(user_id, bonus_points, "daily_bonus")
            
            # Обновляем запись ежедневного бонуса
            cursor = await conn.execute(
                "SELECT streak_count, total_claimed FROM daily_bonus WHERE user_id = ?",
                (user_id,)
            )
            existing_record = await cursor.fetchone()
            
            if existing_record:
                current_streak = existing_record[0] or 0
                total_claimed = existing_record[1] or 0
                new_streak = current_streak + 1
                
                await conn.execute(
                    "UPDATE daily_bonus SET last_claim = datetime('now'), streak_count = ?, total_claimed = ? WHERE user_id = ?",
                    (new_streak, total_claimed + 1, user_id)
                )
            else:
                # Создаем новую запись
                new_streak = 1
                await conn.execute(
                    "INSERT INTO daily_bonus (user_id, last_claim, streak_count, total_claimed) VALUES (?, datetime('now'), 1, 1)",
                    (user_id,)
                )
            
            await conn.commit()
            
            # Проверяем достижения
            await check_achievements(user_id, "daily_streak")
            
            await message.answer(await translate_func(user_id, "daily_bonus_claimed", points=bonus_points, streak=new_streak))
            
            log().info(f"Daily bonus {bonus_points} points claimed by user {user_id}, streak: {new_streak}")
            return True
            
    except Exception as e:
        log().error(f"Error claiming daily bonus for user {user_id}: {e}")
        return False


async def check_subscription(user_id: int, message) -> Dict[str, any]:
    """
    Проверить статус подписки пользователя

    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа

    Returns:
        Dict: информация о подписке
    """
    try:
        # Админы всегда имеют премиум подписку
        from config.config import ADMIN_IDS
        if user_id in ADMIN_IDS:
            return {
                "has_active": True,
                "is_trial": False,
                "end_date": None,
                "days_remaining": 999999,  # Бесконечная подписка для админов
                "is_admin": True
            }

        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute(
                """SELECT end_date, is_trial
                FROM subscriptions
                WHERE user_id = ? AND end_date > datetime('now')
                ORDER BY end_date DESC LIMIT 1""",
                (user_id,)
            )
            subscription = await cursor.fetchone()

            result = {
                "has_active": subscription is not None,
                "is_trial": False,
                "end_date": None,
                "days_remaining": 0
            }

            if subscription:
                end_date_str, is_trial = subscription
                end_date = datetime.fromisoformat(end_date_str)
                days_remaining = (end_date - datetime.utcnow()).days

                result.update({
                    "is_trial": bool(is_trial),
                    "end_date": end_date,
                    "days_remaining": max(0, days_remaining)
                })

            return result

    except Exception as e:
        log().error(f"Error checking subscription for user {user_id}: {e}")
        return {"has_active": False, "error": str(e)}


async def show_achievements(user_id: int, message) -> None:
    """
    Показать достижения пользователя
    
    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute(
                "SELECT achievement_type, unlocked_at FROM user_achievements WHERE user_id = ?",
                (user_id,)
            )
            achievements = await cursor.fetchall()
            
            if not achievements:
                await message.answer(await translate_func(user_id, "no_achievements"))
                return
            
            # Форматируем список достижений
            achievements_text = await translate_func(user_id, "achievements_header")
            
            for achievement_type, unlocked_at in achievements:
                achievement_name = await translate_func(user_id, f"achievement_{achievement_type}")
                unlocked_date = datetime.fromisoformat(unlocked_at).strftime("%d.%m.%Y")
                achievements_text += f"\n🏆 {achievement_name} - {unlocked_date}"
            
            await message.answer(achievements_text)
            
    except Exception as e:
        log().error(f"Error showing achievements for user {user_id}: {e}")
        await message.answer(await translate_func(user_id, "achievements_error"))


async def show_leaderboard(user_id: int, message) -> None:
    """
    Показать таблицу лидеров
    
    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа
    
    Returns:
        bool: успешность операции
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute(
                """SELECT user_id, points FROM users 
                WHERE points > 0 
                ORDER BY points DESC 
                LIMIT 10"""
            )
            leaders = await cursor.fetchall()
            
            if not leaders:
                await message.answer(await translate_func(user_id, "leaderboard_empty"))
                return
            
            leaderboard_text = await translate_func(user_id, "leaderboard_header")
            
            for i, (leader_id, points) in enumerate(leaders, 1):
                # Получаем имя пользователя (если есть)
                cursor = await conn.execute(
                    "SELECT first_name, username FROM users_info WHERE user_id = ?",
                    (leader_id,)
                )
                user_info = await cursor.fetchone()
                
                if user_info:
                    first_name, username = user_info
                    display_name = f"@{username}" if username else first_name
                else:
                    display_name = f"User {leader_id}"
                
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
                leaderboard_text += f"\n{medal} {i}. {display_name} - {points} pts"
            
            # Добавляем позицию текущего пользователя
            cursor = await conn.execute(
                "SELECT points FROM users WHERE user_id = ?",
                (user_id,)
            )
            user_points = (await cursor.fetchone())[0] or 0
            
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM users WHERE points > ?",
                (user_points,)
            )
            user_rank = (await cursor.fetchone())[0] + 1
            
            leaderboard_text += f"\n\n📊 Ваше место: {user_rank} ({user_points} pts)"
            
            await message.answer(leaderboard_text)
            
    except Exception as e:
        log().error(f"Error showing leaderboard for user {user_id}: {e}")
        await message.answer(await translate_func(user_id, "leaderboard_error"))


async def get_referral_info(user_id: int) -> dict:
    """
    Получить информацию о реферальной системе пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        dict: информация о рефералах и бонусах
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            # Получаем количество рефералов
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM referrals WHERE inviter_id = ?",
                (user_id,)
            )
            referral_count = (await cursor.fetchone())[0]
            
            # Получаем общую сумму реферальных бонусов
            cursor = await conn.execute(
                "SELECT COALESCE(SUM(bonus_days), 0) FROM referral_bonuses WHERE inviter_id = ?",
                (user_id,)
            )
            total_bonus = (await cursor.fetchone())[0]
            
            # Получаем последние 5 реферальных бонусов
            cursor = await conn.execute(
                """SELECT referral_id, bonus_days, applied_date 
                FROM referral_bonuses 
                WHERE inviter_id = ? 
                ORDER BY applied_date DESC LIMIT 5""",
                (user_id,)
            )
            recent_bonuses = await cursor.fetchall()
            
            return {
                "referral_count": referral_count,
                "total_bonus": total_bonus,
                "recent_bonuses": recent_bonuses
            }
            
    except Exception as e:
        log().error(f"Error getting referral info for user {user_id}: {e}")
        return {"referral_count": 0, "total_bonus": 0, "recent_bonuses": []}


async def get_user_id_from_referral_code(referral_code: str) -> Optional[int]:
    """
    Получить user_id из реферального кода (упрощенная генерация)

    Args:
        referral_code: реферальный код (6-значный, без префиксов)

    Returns:
        Optional[int]: user_id или None если код не найден
    """
    try:
        # Валидация входных данных
        if not referral_code or not isinstance(referral_code, str):
            return None

        # Для обратной совместимости: убираем префиксы REF или ref_ если есть
        clean_code = referral_code
        if clean_code.startswith('REF'):
            clean_code = clean_code[3:]
        elif clean_code.startswith('ref_'):
            clean_code = clean_code[4:]

        # Проверяем длину кода (должна быть ровно 6 символов)
        if len(clean_code) != 6:
            return None

        # Проверяем, что код состоит только из букв и цифр
        import string
        allowed_chars = string.ascii_uppercase + string.digits
        if not all(c in allowed_chars for c in clean_code):
            return None

        # Ищем user_id по коду
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute(
                "SELECT user_id FROM referral_codes WHERE referral_code = ?",
                (clean_code,)
            )
            result = await cursor.fetchone()

            if result:
                return result[0]
            else:
                return None

    except Exception as e:
        log().error(f"Error getting user_id from referral code '{referral_code}': {e}")
        return None


async def get_user_referral_code(user_id: int) -> str:
    """
    Получить реферальный код пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        str: реферальный код (6 символов)
    """
    # Валидация входных данных
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Invalid user_id")
    
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            # Проверяем, есть ли уже код для пользователя
            cursor = await conn.execute(
                "SELECT referral_code FROM referral_codes WHERE user_id = ?",
                (user_id,)
            )
            existing_code = await cursor.fetchone()
            
            if existing_code:
                return existing_code[0]
            
            # Генерируем новый короткий код (6 символов)
            import random
            import string
            
            # Генерируем уникальный код
            while True:
                # Используем буквы и цифры для кода
                code_chars = string.ascii_uppercase + string.digits
                short_code = ''.join(random.choices(code_chars, k=6))
                
                # Проверяем уникальность
                cursor = await conn.execute(
                    "SELECT user_id FROM referral_codes WHERE referral_code = ?",
                    (short_code,)
                )
                existing_user = await cursor.fetchone()
                
                if not existing_user:
                    break
            
            # Сохраняем код в базу
            await conn.execute(
                "INSERT INTO referral_codes (user_id, referral_code) VALUES (?, ?)",
                (user_id, short_code)
            )
            await conn.commit()
            
            return short_code
            
    except Exception as e:
        log().error(f"Error generating referral code for user {user_id}: {e}")
        # Запасной вариант - короткий хэш
        import hashlib
        hash_obj = hashlib.md5(str(user_id).encode())
        return hash_obj.hexdigest()[:6].upper()


async def get_referral_stats() -> dict:
    """
    Получить общую статистику реферальной системы
    
    Returns:
        dict: общая статистика
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            # Общее количество рефералов
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM referrals"
            )
            total_referrals = (await cursor.fetchone())[0]
            
            # Общая сумма выплаченных бонусов
            cursor = await conn.execute(
                "SELECT COALESCE(SUM(bonus_days), 0) FROM referral_bonuses"
            )
            total_bonus_paid = (await cursor.fetchone())[0]
            
            # Топ 5 рефереров
            cursor = await conn.execute(
                """SELECT r.inviter_id, COUNT(*) as count, COALESCE(SUM(rb.bonus_days), 0) as total_bonus
                FROM referrals r
                LEFT JOIN referral_bonuses rb ON r.inviter_id = rb.inviter_id
                GROUP BY r.inviter_id
                ORDER BY count DESC LIMIT 5"""
            )
            top_referrers = await cursor.fetchall()
            
            return {
                "total_referrals": total_referrals,
                "total_bonus_paid": total_bonus_paid,
                "top_referrers": top_referrers
            }
            
    except Exception as e:
        log().error(f"Error getting referral stats: {e}")
        return {"total_referrals": 0, "total_bonus_paid": 0, "top_referrers": []}


async def get_daily_bonus_info(user_id: int) -> dict:
    """
    Получить информацию о ежедневном бонусе пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        dict: информация о бонусе
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            # Проверяем, когда пользователь последний раз получал бонус
            cursor = await conn.execute(
                "SELECT last_claim FROM daily_bonus WHERE user_id = ?",
                (user_id,)
            )
            result = await cursor.fetchone()
            
            if result and result[0]:
                last_claim = datetime.fromisoformat(result[0])
                next_claim_time = last_claim + timedelta(hours=24)
                can_claim = datetime.utcnow() >= next_claim_time
                
                # Определяем сумму бонуса (базовая сумма + бонус за последовательные дни)
                cursor = await conn.execute(
                    "SELECT streak_count FROM daily_bonus WHERE user_id = ?",
                    (user_id,)
                )
                streak_result = await cursor.fetchone()
                streak = streak_result[0] if streak_result else 0
                
                # Базовая сумма + дополнительный бонус за streak
                base_amount = 10
                bonus_amount = base_amount + min(streak * 2, 20)  # Максимум +20 за streak
                
                return {
                    "can_claim": can_claim,
                    "next_claim_time": next_claim_time,
                    "last_claim": last_claim,
                    "streak": streak,
                    "amount": bonus_amount
                }
            else:
                # Пользователь никогда не получал бонус
                return {
                    "can_claim": True,
                    "next_claim_time": datetime.utcnow(),
                    "last_claim": None,
                    "streak": 0,
                    "amount": 10  # Базовая сумма
                }
                
    except Exception as e:
        log().error(f"Error getting daily bonus info for user {user_id}: {e}")
        return {
            "can_claim": False,
            "next_claim_time": datetime.utcnow(),
            "last_claim": None,
            "streak": 0,
            "amount": 10
        }


async def get_full_referral_link(user_id: int) -> str:
    """
    Получить полную реферальную ссылку (упрощенная генерация)

    Args:
        user_id: ID пользователя

    Returns:
        str: полная реферальная ссылка без префикса
    """
    try:
        from config.config import BOT_USERNAME

        # Валидация входных данных
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")

        # Получаем реферальный код
        referral_code = await get_user_referral_code(user_id)

        # Упрощенный формат: убираем префикс ref_ для более короткой ссылки
        return f"https://t.me/{BOT_USERNAME}?start={referral_code}"

    except Exception as e:
        log().error(f"Error generating referral link for user {user_id}: {e}")
        # Возвращаем запасной вариант с коротким хэшем
        import hashlib
        hash_obj = hashlib.md5(str(user_id).encode())
        short_code = hash_obj.hexdigest()[:6].upper()
        return f"https://t.me/{BOT_USERNAME}?start={short_code}"


async def init_referral_codes_table():
    """Инициализация таблицы для маппинга реферальных кодов"""
    import logging
    logger = logging.getLogger("referral_init")
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS referral_codes (
                    user_id INTEGER PRIMARY KEY,
                    referral_code TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.commit()
        logger.info("Referral codes table initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing referral codes table: {e}")


async def init_referral_system():
    """Инициализация реферальной системы"""
    import logging
    logger = logging.getLogger("referral_init")
    try:
        await init_referral_codes_table()
        logger.info("Referral system initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing referral system: {e}")
