#!/usr/bin/env python3
"""
Симуляция запросов к VPN боту для тестирования функциональности
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot_simulation")

BOT_TOKEN = ""  # Устанавливается из .env
CHAT_ID = "339795159"  # Тестовый ID пользователя

WEBHOOK_URL = "http://127.0.0.1:8001/webhook/57f512916856b553a9c060b707c84c8931c2da1b31344d17f07670b31bbd379f"  # Это должен быть корректный токен

def load_config():
    """Загрузка конфигурации из .env файла"""
    global BOT_TOKEN, CHAT_ID, WEBHOOK_URL

    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('TELEGRAM_TOKEN='):
                    BOT_TOKEN = line.split('=', 1)[1].strip()
                elif line.startswith('ADMIN_IDS='):
                    # Используем первый ADMIN ID как тестовый
                    admin_ids = line.split('=', 1)[1].strip()
                    if admin_ids:
                        CHAT_ID = admin_ids.strip('[]').split(',')[0].strip()
                        break
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")


def generate_update(update_id: int, command: str = None, callback_data: str = None, user_id: int = None):
    """Генерация webhook update для симуляции"""
    base_update = {
        "update_id": update_id,
        "message": {
            "message_id": update_id * 10,
            "from": {
                "id": user_id or int(CHAT_ID),
                "is_bot": False,
                "first_name": "TestUser",
                "language_code": "ru"
            },
            "chat": {
                "id": user_id or int(CHAT_ID),
                "type": "private"
            },
            "date": int(datetime.now().timestamp())
        }
    }

    if command:
        base_update["message"]["text"] = command
        base_update["message"]["entities"] = [{
            "offset": 0,
            "length": len(command),
            "type": "bot_command"
        }]
    elif callback_data:
        base_update.pop("message")
        base_update["callback_query"] = {
            "id": f"cb_{update_id}",
            "from": {
                "id": user_id or int(CHAT_ID),
                "is_bot": False,
                "first_name": "TestUser",
                "language_code": "ru"
            },
            "message": {
                "message_id": update_id * 9,
                "from": {
                    "id": int(CHAT_ID),
                    "is_bot": True,
                    "first_name": "VPN Bot",
                    "username": "vpn_creative_bot"
                },
                "chat": {
                    "id": user_id or int(CHAT_ID),
                    "type": "private"
                },
                "date": int(datetime.now().timestamp()),
                "text": "Главное меню",
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "Тест", "callback_data": callback_data}]
                    ]
                }
            },
            "chat_instance": f"ci_{update_id}",
            "data": callback_data
        }

    return base_update


async def send_webhook_update(update):
    """Отправка webhook update"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                WEBHOOK_URL,
                json=update,
                headers={"Content-Type": "application/json"}
            ) as response:
                logger.info(f"Update {update['update_id']} отправлен: {response.status}")
                if response.status != 200:
                    logger.error(f"Ошибка отправки: {await response.text()}")
                return response.status == 200
    except Exception as e:
        logger.error(f"Ошибка подключения к webhook: {e}")
        return False


async def simulate_commands():
    """Симуляция команд бота"""
    logger.info("🚀 Начинаем симуляцию команд бота")

    # Тестовые команды и callback data
    test_cases = [
        ("Команда /start", "/start"),
        ("Команда /menu", "/menu"),
        ("Команда /profile", "/profile"),
        ("Команда /daily", "/daily"),
        ("Callback main_menu", "main_menu", True),
        ("Callback pricing", "pricing", True),
        ("Callback my_profile", "my_profile", True),
        ("Callback daily_bonus", "daily_bonus", True),
        ("Callback invite_friends", "invite_friends", True),
        ("Callback wireguard_advantages", "wireguard_advantages", True),
    ]

    for i, test_case in enumerate(test_cases, 1):
        if len(test_case) == 3 and test_case[2]:  # callback
            description, callback_data, _ = test_case
            update = generate_update(i, callback_data=callback_data)
        else:  # command
            description, command = test_case
            update = generate_update(i, command=command)

        logger.info(f"📨 Отправка: {description}")
        success = await send_webhook_update(update)

        if success:
            logger.info(f"✅ {description} - успешно")
        else:
            logger.error(f"❌ {description} - ошибка")

        # Небольшая задержка между запросами
        await asyncio.sleep(2)

    logger.info("🎉 Симуляция завершена!")


async def check_logs():
    """Проверка логов после симуляции"""
    logger.info("📊 Проверка логов после симуляции")

    try:
        with open("logs/webhook-service.log", "r", encoding="utf-8") as f:
            lines = f.readlines()[-50:]  # Последние 50 строк

        logger.info("📋 Последние записи вебхук логов:")
        for line in lines:
            if any(keyword in line.lower() for keyword in ["error", "warning", "exception", "ошибка", "предупреждение"]):
                logger.warning(f"⚠️  {line.strip()}")
            elif any(keyword in line.lower() for keyword in ["handled", "обработан"]):
                logger.info(f"✅ {line.strip()}")

    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")


if __name__ == "__main__":
    load_config()

    if not BOT_TOKEN:
        logger.error("Ошибка: TELEGRAM_BOT_TOKEN не найден в .env файле")
        exit(1)

    logger.info(f"🔧 Конфигурация загружена: TOKEN=****{BOT_TOKEN[-10:]}")
    logger.info(f"👤 Тестовый чат ID: {CHAT_ID}")

    async def main():
        # Запуск симуляции
        await simulate_commands()

        # Небольшая задержка для обработки
        await asyncio.sleep(5)

        # Проверка логов
        await check_logs()

    asyncio.run(main())
