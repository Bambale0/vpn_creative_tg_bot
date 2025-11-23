"""
Плагин бонусов для VPN бота
"""

import logging
import sqlite3
import aiosqlite
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# Добавляем импорт DatabaseManager
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.database import db_manager

log = logging.getLogger("plugins.bonus")

class Plugin:
    """Плагин системы бонусов"""

    version = "1.0.0"
    description = "Система бонусов и наград для пользователей"
    author = "VPN Bot Team"

    def __init__(self):
        self.enabled = False
        self.db_path = "data/subscriptions.db"

    async def setup(self) -> bool:
        """Инициализация плагина"""
        try:
            # Проверяем подключение к БД
            conn = sqlite3.connect(self.db_path)
            conn.close()
            self.enabled = True
            log.info("Плагин бонусов успешно инициализирован")
            return True
        except Exception as e:
            log.error(f"Ошибка инициализации плагина бонусов: {e}")
            return False

    def teardown(self) -> None:
        """Очистка ресурсов"""
        self.enabled = False
        log.info("Плагин бонусов выгружен")

    async def give_bonus(self, user_id: int, days: int, message: str = None) -> Dict[str, Any]:
        """Выдача бонуса пользователю"""
        try:
            if not self.enabled:
                return {"success": False, "error": "Plugin not enabled"}

            # Используем DatabaseManager вместо прямого подключения
            async with db_manager.get_connection() as conn:
                cursor = await conn.cursor()

                # Проверяем, есть ли пользователь
                await cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
                user = await cursor.fetchone()

                if not user:
                    return {"success": False, "error": "User not found"}

                # Добавляем бонус в таблицу subscriptions
                end_date = datetime.now() + timedelta(days=days)
                await cursor.execute("""
                    INSERT OR REPLACE INTO subscriptions (user_id, end_date, status)
                    VALUES (?, ?, 'active')
                """, (user[0], end_date))

                # Логируем бонус
                await cursor.execute("""
                    INSERT INTO bonus_log (user_id, days, message, created_at)
                    VALUES (?, ?, ?, ?)
                """, (user[0], days, message or "", datetime.now()))

                await conn.commit()

            log.info(f"Бонус выдан пользователю {user_id}: {days} дней")
            return {"success": True, "days": days, "end_date": end_date.isoformat()}

        except Exception as e:
            log.error(f"Ошибка выдачи бонуса: {e}")
            return {"success": False, "error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """Получение статистики бонусов"""
        try:
            if not self.enabled:
                return {"success": False, "error": "Plugin not enabled"}

            # Используем DatabaseManager вместо прямого подключения
            async with db_manager.get_connection() as conn:
                cursor = await conn.cursor()

                # Общая статистика
                await cursor.execute("SELECT COUNT(*) FROM bonus_log")
                total_bonuses_result = await cursor.fetchone()
                total_bonuses = total_bonuses_result[0] if total_bonuses_result else 0

                await cursor.execute("SELECT SUM(days) FROM bonus_log")
                result = await cursor.fetchone()
                total_days = result[0] if result and result[0] else 0

                # Статистика за последние 30 дней
                thirty_days_ago = datetime.now() - timedelta(days=30)
                await cursor.execute("SELECT COUNT(*) FROM bonus_log WHERE created_at > ?", (thirty_days_ago,))
                recent_bonuses_result = await cursor.fetchone()
                recent_bonuses = recent_bonuses_result[0] if recent_bonuses_result else 0

                await cursor.execute("SELECT SUM(days) FROM bonus_log WHERE created_at > ?", (thirty_days_ago,))
                result = await cursor.fetchone()
                recent_days = result[0] if result and result[0] else 0

                return {
                    "success": True,
                    "total_bonuses": total_bonuses,
                    "total_days": total_days,
                    "recent_bonuses": recent_bonuses,
                    "recent_days": recent_days,
                    "average_days_per_bonus": total_days / total_bonuses if total_bonuses > 0 else 0
                }

        except Exception as e:
            log.error(f"Ошибка получения статистики: {e}")
            return {"success": False, "error": str(e)}

    def get_info(self) -> Dict[str, Any]:
        """Информация о плагине"""
        return {
            "name": "bonus_plugin",
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled
        }

# Экземпляр плагина
bonus_plugin = Plugin()

# Глобальные функции для совместимости
async def give_user_bonus(user_id: int, days: int, message: str = "") -> Dict[str, Any]:
    """Выдача бонуса пользователю"""
    return await bonus_plugin.give_bonus(user_id, days, message)

async def get_bonus_statistics() -> Dict[str, Any]:
    """Получение статистики бонусов"""
    return await bonus_plugin.get_stats()
