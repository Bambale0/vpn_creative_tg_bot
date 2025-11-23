"""
Модуль алертов для системы мониторинга
"""
import logging
import asyncio
from typing import Optional
from config.config import ADMIN_IDS
from config.dependencies import get_bot_instance

log = logging.getLogger("alerts")

async def send_alert_to_admins(message: str, level: str = "CRITICAL"):
    """
    Отправка алерта администраторам

    Args:
        message: сообщение алерта
        level: уровень важности (CRITICAL, WARNING, INFO)
    """
    try:
        bot = get_bot_instance()
        if not bot:
            log.error("Bot instance not available for alerts")
            return

        emoji_map = {
            "CRITICAL": "🚨",
            "WARNING": "⚠️",
            "INFO": "ℹ️"
        }

        emoji = emoji_map.get(level, "🔔")
        alert_message = f"{emoji} <b>Система алертов</b>\n\n{message}"

        sent_count = 0
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    alert_message,
                    parse_mode="HTML"
                )
                sent_count += 1
                await asyncio.sleep(0.1)  # Небольшая задержка между сообщениями
            except Exception as e:
                log.error(f"Failed to send alert to admin {admin_id}: {e}")

        log.info(f"Alert sent to {sent_count}/{len(ADMIN_IDS)} admins")

    except Exception as e:
        log.error(f"Error sending alert: {e}")

async def alert_critical_error(error_message: str):
    """Отправка критического алерта"""
    await send_alert_to_admins(
        f"❌ <b>Критическая ошибка!</b>\n\n{error_message}",
        "CRITICAL"
    )

async def alert_security_issue(issue_message: str):
    """Отправка алерта по безопасности"""
    await send_alert_to_admins(
        f"🔒 <b>Проблема безопасности!</b>\n\n{issue_message}",
        "CRITICAL"
    )

async def alert_performance_warning(metric_name: str, value: float, threshold: float):
    """Отправка алерта о производительности"""
    await send_alert_to_admins(
        f"📊 <b>Алерт производительности</b>\n\n"
        f"Метрика: {metric_name}\n"
        f"Значение: {value}\n"
        f"Порог: {threshold}",
        "WARNING"
    )

async def alert_database_error(error_message: str):
    """Отправка алерта об ошибке БД"""
    await send_alert_to_admins(
        f"🗄️ <b>Ошибка базы данных</b>\n\n{error_message}",
        "CRITICAL"
    )

# Глобальные функции для удобства использования
critical_alert = alert_critical_error
security_alert = alert_security_issue
performance_alert = alert_performance_warning
database_alert = alert_database_error
