"""
Оптимизированная версия игровых функций с использованием DatabaseManager
"""

import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio

from config.config import DB_PATH, TRIAL_DAYS, REFERRAL_BONUS_FIRST, REFERRAL_BONUS_SUBSEQUENT, REFERRAL_ENABLED
from config.dependencies import log, t as translate_func
from utils.database import db_manager


async def add_user_points_optimized(user_id: int, points: int, reason: str) -> bool:
    """
    Оптимизированная версия добавления очков пользователю

    Args:
        user_id: ID пользователя
        points: количество очков
        reason: причина начисления

    Returns:
        bool: успешность операции
    """
    try:
        # Получаем текущие очки
        current_points_result = await db_manager.fetch_one(
            "SELECT points FROM users WHERE user_id = ?",
            (user_id,)
        )

        if current_points_result:
            current_points = current_points_result[0] if current_points_result[0] is not None else 0
            new_points = current_points + points

            # Обновляем очки
            await db_manager.execute(
                "UPDATE users SET points = ? WHERE user_id = ?",
                (new_points, user_id)
            )
        else:
            # Создаем запись пользователя
            await db_manager.execute(
                "INSERT INTO users (user_id, points) VALUES (?, ?)",
                (user_id, points)
            )

        # Логируем начисление очков
        await db_manager.execute(
            """INSERT INTO points_log
            (user_id, points, reason, timestamp)
            VALUES (?, ?, ?, datetime('now'))""",
            (user_id, points, reason)
        )

        log().info(f"Added {points} points to user {user_id} for {reason}")
        return True

    except Exception as e:
        log().error(f"Error adding points to user {user_id}: {e}")
        return False


async def get_trial_optimized(user_id: int, message) -> bool:
    """
    Оптимизированная версия активации trial периода

    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа

    Returns:
        bool: успешность активации
    """
    try:
        # Проверяем, не активировал ли уже пользователь trial
        trial_count_result = await db_manager.fetch_one(
            "SELECT COUNT(*) FROM trial_activations WHERE user_id = ?",
            (user_id,)
        )
        trial_count = trial_count_result[0] if trial_count_result else 0

        if trial_count > 0:
            # Пользователь уже активировал trial
            await message.answer(await translate_func(user_id, "trial_already_used"))
            return False

        # Активируем trial на количество дней из конфига
        end_date = (datetime.utcnow() + timedelta(days=TRIAL_DAYS)).isoformat()

        await db_manager.execute(
            """INSERT INTO subscriptions
            (user_id, start_date, end_date, payment_id, duration, is_trial)
            VALUES (?, datetime('now'), ?, ?, 0, 1)""",
            (user_id, end_date, f"trial_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        )

        # Записываем активацию trial
        await db_manager.execute(
            "INSERT OR IGNORE INTO trial_activations (user_id, activated_at) VALUES (?, datetime('now'))",
            (user_id,)
        )

        # Начисляем бонусные очки за активацию trial
        await add_user_points_optimized(user_id, 50, "trial_activation")

        # Отправляем сообщение об успешной активации trial
        end_date_formatted = datetime.fromisoformat(end_date).strftime('%d.%m.%Y %H:%M')
        await message.answer(await translate_func(user_id, "trial_activated", end_date=end_date_formatted))

        log().info(f"Trial activated for user {user_id}")
        return True

    except Exception as e:
        log().error(f"Error activating trial for user {user_id}: {e}")
        return False


async def check_subscription_optimized(user_id: int, message) -> Dict[str, any]:
    """
    Оптимизированная версия проверки подписки

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
                "days_remaining": 999999,
                "is_admin": True
            }

        # Получаем активную подписку
        subscription_result = await db_manager.fetch_one(
            """SELECT end_date, is_trial
            FROM subscriptions
            WHERE user_id = ? AND end_date > datetime('now')
            ORDER BY end_date DESC LIMIT 1""",
            (user_id,)
        )

        result = {
            "has_active": subscription_result is not None,
            "is_trial": False,
            "end_date": None,
            "days_remaining": 0
        }

        if subscription_result:
            end_date_str, is_trial = subscription_result
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


async def claim_daily_bonus_optimized(user_id: int, message) -> bool:
    """
    Оптимизированная версия получения ежедневного бонуса

    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа

    Returns:
        bool: успешность операции
    """
    try:
        # Проверяем, получал ли уже пользователь бонус сегодня
        already_claimed_result = await db_manager.fetch_one(
            "SELECT last_claim FROM daily_bonus WHERE user_id = ? AND date(last_claim) = date('now')",
            (user_id,)
        )

        if already_claimed_result:
            await message.answer(await translate_func(user_id, "daily_bonus_already_claimed"))
            return False

        # Начисляем бонусные очки (10-50 случайных)
        import random
        bonus_points = random.randint(10, 50)

        await add_user_points_optimized(user_id, bonus_points, "daily_bonus")

        # Обновляем запись ежедневного бонуса
        existing_record_result = await db_manager.fetch_one(
            "SELECT streak_count, total_claimed FROM daily_bonus WHERE user_id = ?",
            (user_id,)
        )

        if existing_record_result:
            current_streak = existing_record_result[0] or 0
            total_claimed = existing_record_result[1] or 0
            new_streak = current_streak + 1

            await db_manager.execute(
                "UPDATE daily_bonus SET last_claim = datetime('now'), streak_count = ?, total_claimed = ? WHERE user_id = ?",
                (new_streak, total_claimed + 1, user_id)
            )
        else:
            # Создаем новую запись
            new_streak = 1
            await db_manager.execute(
                "INSERT INTO daily_bonus (user_id, last_claim, streak_count, total_claimed) VALUES (?, datetime('now'), 1, 1)",
                (user_id,)
            )

        # Проверяем достижения
        await check_achievements_optimized(user_id, "daily_streak")

        await message.answer(await translate_func(user_id, "daily_bonus_claimed", points=bonus_points, streak=new_streak))

        log().info(f"Daily bonus {bonus_points} points claimed by user {user_id}, streak: {new_streak}")
        return True

    except Exception as e:
        log().error(f"Error claiming daily bonus for user {user_id}: {e}")
        return False


async def check_achievements_optimized(user_id: int, achievement_type: str) -> Dict[str, bool]:
    """
    Оптимизированная версия проверки достижений

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

    try:
        # Проверяем существующие достижения
        existing_achievements_result = await db_manager.fetch_all(
            "SELECT achievement_type FROM user_achievements WHERE user_id = ?",
            (user_id,)
        )
        existing_achievements = [row[0] for row in existing_achievements_result]

        # Проверяем условия для каждого типа достижения
        if achievement_type == "first_purchase":
            # Проверяем первую покупку
            purchase_count_result = await db_manager.fetch_one(
                "SELECT COUNT(*) FROM subscriptions WHERE user_id = ?",
                (user_id,)
            )
            purchase_count = purchase_count_result[0] if purchase_count_result else 0

            if purchase_count == 1:
                # Разблокируем достижение
                await db_manager.execute(
                    """INSERT OR IGNORE INTO user_achievements
                    (user_id, achievement_type, unlocked_at)
                    VALUES (?, ?, datetime('now'))""",
                    (user_id, "first_purchase")
                )
                achievements["first_purchase"] = True

        elif achievement_type == "daily_streak":
            # Проверяем ежедневную серию
            streak_result = await db_manager.fetch_one(
                """SELECT MAX(streak_count) FROM daily_bonus
                WHERE user_id = ? AND last_claim >= date('now', '-7 days')""",
                (user_id,)
            )
            streak = streak_result[0] if streak_result else 0

            if streak >= 7:
                await db_manager.execute(
                    """INSERT OR IGNORE INTO user_achievements
                    (user_id, achievement_type, unlocked_at)
                    VALUES (?, ?, datetime('now'))""",
                    (user_id, "daily_streak")
                )
                achievements["daily_streak"] = True

        elif achievement_type == "referral_master":
            # Проверяем реферальную систему
            referral_count_result = await db_manager.fetch_one(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
                (user_id,)
            )
            referral_count = referral_count_result[0] if referral_count_result else 0

            if referral_count >= 5:
                await db_manager.execute(
                    """INSERT OR IGNORE INTO user_achievements
                    (user_id, achievement_type, unlocked_at)
                    VALUES (?, ?, datetime('now'))""",
                    (user_id, "referral_master")
                )
                achievements["referral_master"] = True

        elif achievement_type == "vip_status":
            # Проверяем VIP статус (очки)
            points_result = await db_manager.fetch_one(
                "SELECT points FROM users WHERE user_id = ?",
                (user_id,)
            )
            points = points_result[0] if points_result else 0

            if points >= 1000:
                await db_manager.execute(
                    """INSERT OR IGNORE INTO user_achievements
                    (user_id, achievement_type, unlocked_at)
                    VALUES (?, ?, datetime('now'))""",
                    (user_id, "vip_status")
                )
                achievements["vip_status"] = True

        # Отправляем уведомление о новых достижениях
        new_achievements = [k for k, v in achievements.items() if v and k not in existing_achievements]

        if new_achievements:
            log().info(f"User {user_id} unlocked achievements: {new_achievements}")

        return achievements

    except Exception as e:
        log().error(f"Error checking achievements for user {user_id}: {e}")
        return achievements


async def show_achievements_optimized(user_id: int, message) -> None:
    """
    Оптимизированная версия показа достижений

    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа
    """
    try:
        achievements_result = await db_manager.fetch_all(
            "SELECT achievement_type, unlocked_at FROM user_achievements WHERE user_id = ?",
            (user_id,)
        )

        if not achievements_result:
            await message.answer(await translate_func(user_id, "no_achievements"))
            return

        # Форматируем список достижений
        achievements_text = await translate_func(user_id, "achievements_header")

        for achievement_row in achievements_result:
            achievement_type, unlocked_at = achievement_row
            achievement_name = await translate_func(user_id, f"achievement_{achievement_type}")
            unlocked_date = datetime.fromisoformat(unlocked_at).strftime("%d.%m.%Y")
            achievements_text += f"\n🏆 {achievement_name} - {unlocked_date}"

        await message.answer(achievements_text)

    except Exception as e:
        log().error(f"Error showing achievements for user {user_id}: {e}")
        await message.answer(await translate_func(user_id, "achievements_error"))


async def show_leaderboard_optimized(user_id: int, message) -> None:
    """
    Оптимизированная версия таблицы лидеров

    Args:
        user_id: ID пользователя
        message: объект сообщения для ответа
    """
    try:
        leaders_result = await db_manager.fetch_all(
            """SELECT user_id, points FROM users
            WHERE points > 0
            ORDER BY points DESC
            LIMIT 10"""
        )

        if not leaders_result:
            await message.answer(await translate_func(user_id, "leaderboard_empty"))
            return

        leaderboard_text = await translate_func(user_id, "leaderboard_header")

        for i, leader_row in enumerate(leaders_result, 1):
            leader_id, points = leader_row

            # Получаем имя пользователя
            user_info_result = await db_manager.fetch_one(
                "SELECT first_name, username FROM users_info WHERE user_id = ?",
                (leader_id,)
            )

            if user_info_result:
                first_name, username = user_info_result
                display_name = f"@{username}" if username else first_name
            else:
                display_name = f"User {leader_id}"

            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
            leaderboard_text += f"\n{medal} {i}. {display_name} - {points} pts"

        # Добавляем позицию текущего пользователя
        user_points_result = await db_manager.fetch_one(
            "SELECT points FROM users WHERE user_id = ?",
            (user_id,)
        )
        user_points = user_points_result[0] if user_points_result else 0

        user_rank_result = await db_manager.fetch_one(
            "SELECT COUNT(*) FROM users WHERE points > ?",
            (user_points,)
        )
        user_rank = (user_rank_result[0] if user_rank_result else 0) + 1

        leaderboard_text += f"\n\n📊 Ваше место: {user_rank} ({user_points} pts)"

        await message.answer(leaderboard_text)

    except Exception as e:
        log().error(f"Error showing leaderboard for user {user_id}: {e}")
        await message.answer(await translate_func(user_id, "leaderboard_error"))


async def get_referral_info_optimized(user_id: int) -> dict:
    """
    Оптимизированная версия получения реферальной информации

    Args:
        user_id: ID пользователя

    Returns:
        dict: информация о рефералах и бонусах
    """
    try:
        # Получаем количество рефералов
        referral_count_result = await db_manager.fetch_one(
            "SELECT COUNT(*) FROM referrals WHERE inviter_id = ?",
            (user_id,)
        )
        referral_count = referral_count_result[0] if referral_count_result else 0

        # Получаем общую сумму реферальных бонусов
        total_bonus_result = await db_manager.fetch_one(
            "SELECT COALESCE(SUM(bonus_days), 0) FROM referral_bonuses WHERE inviter_id = ?",
            (user_id,)
        )
        total_bonus = total_bonus_result[0] if total_bonus_result else 0

        # Получаем последние 5 реферальных бонусов
        recent_bonuses_result = await db_manager.fetch_all(
            """SELECT referral_id, bonus_days, applied_date
            FROM referral_bonuses
            WHERE inviter_id = ?
            ORDER BY applied_date DESC LIMIT 5""",
            (user_id,)
        )

        return {
            "referral_count": referral_count,
            "total_bonus": total_bonus,
            "recent_bonuses": recent_bonuses_result
        }

    except Exception as e:
        log().error(f"Error getting referral info for user {user_id}: {e}")
        return {"referral_count": 0, "total_bonus": 0, "recent_bonuses": []}


async def get_user_referral_code_optimized(user_id: int) -> str:
    """
    Оптимизированная версия получения реферальных кодов

    Args:
        user_id: ID пользователя

    Returns:
        str: реферальный код (6 символов)
    """
    try:
        # Проверяем, есть ли уже код для пользователя
        existing_code_result = await db_manager.fetch_one(
            "SELECT referral_code FROM referral_codes WHERE user_id = ?",
            (user_id,)
        )

        if existing_code_result:
            return existing_code_result[0]

        # Генерируем новый короткий код (6 символов)
        import random
        import string

        # Генерируем уникальный код
        while True:
            code_chars = string.ascii_uppercase + string.digits
            short_code = ''.join(random.choices(code_chars, k=6))

            # Проверяем уникальность
            existing_user_result = await db_manager.fetch_one(
                "SELECT user_id FROM referral_codes WHERE referral_code = ?",
                (short_code,)
            )

            if not existing_user_result:
                break

        # Сохраняем код в базу
        await db_manager.execute(
            "INSERT INTO referral_codes (user_id, referral_code) VALUES (?, ?)",
            (user_id, short_code)
        )

        return short_code

    except Exception as e:
        log().error(f"Error generating referral code for user {user_id}: {e}")
        # Запасной вариант - короткий хэш
        import hashlib
        hash_obj = hashlib.md5(str(user_id).encode())
        return hash_obj.hexdigest()[:6].upper()


async def get_daily_bonus_info_optimized(user_id: int) -> dict:
    """
    Оптимизированная версия получения информации о ежедневном бонусе

    Args:
        user_id: ID пользователя

    Returns:
        dict: информация о бонусе
    """
    try:
        # Проверяем, когда пользователь последний раз получал бонус
        last_claim_result = await db_manager.fetch_one(
            "SELECT last_claim FROM daily_bonus WHERE user_id = ?",
            (user_id,)
        )

        if last_claim_result and last_claim_result[0]:
            last_claim = datetime.fromisoformat(last_claim_result[0])
            next_claim_time = last_claim + timedelta(hours=24)
            can_claim = datetime.utcnow() >= next_claim_time

            # Определяем сумму бонуса
            streak_result = await db_manager.fetch_one(
                "SELECT streak_count FROM daily_bonus WHERE user_id = ?",
                (user_id,)
            )
            streak = streak_result[0] if streak_result else 0

            # Базовая сумма + дополнительный бонус за streak
            base_amount = 10
            bonus_amount = base_amount + min(streak * 2, 20)

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
                "amount": 10
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


# Пример использования в основном коде
async def example_usage():
    """Пример использования оптимизированных функций"""
    from utils.database import init_database

    # Инициализируем БД
    await init_database()

    # Используем оптимизированные функции
    user_id = 12345

    # Проверяем подписку
    subscription_info = await check_subscription_optimized(user_id, None)
    print(f"Subscription: {subscription_info}")

    # Получаем реферальную информацию
    referral_info = await get_referral_info_optimized(user_id)
    print(f"Referral: {referral_info}")

    # Получаем информацию о бонусах
    bonus_info = await get_daily_bonus_info_optimized(user_id)
    print(f"Bonus: {bonus_info}")

    # Закрываем соединение
    await db_manager.close()
