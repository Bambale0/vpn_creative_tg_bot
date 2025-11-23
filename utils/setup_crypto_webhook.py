#!/usr/bin/env python3
"""
Скрипт для настройки вебхука Crypto Pay
"""

import asyncio
import aiohttp
from config.config import CRYPTO_PAY_TOKEN, WEBHOOK_HOST, CRYPTO_PAY_WEBHOOK_SECRET


async def setup_crypto_webhook():
    """Настройка вебхука для Crypto Pay"""
    
    if not CRYPTO_PAY_TOKEN or CRYPTO_PAY_TOKEN == "ваш_реальный_токен_от_crypto_bot":
        print("❌ Токен Crypto Pay не настроен. Обновите CRYPTO_PAY_TOKEN в .env файле")
        return False
    
    if not WEBHOOK_HOST:
        print("❌ WEBHOOK_HOST не настроен. Укажите ваш домен в .env файле")
        return False
    
    if not CRYPTO_PAY_WEBHOOK_SECRET or CRYPTO_PAY_WEBHOOK_SECRET == "ваш_секретный_ключ_для_вебхука":
        print("❌ Секретный ключ вебхука не настроен. Обновите CRYPTO_PAY_WEBHOOK_SECRET в .env файле")
        return False
    
    webhook_url = f"{WEBHOOK_HOST}/crypto_pay_webhook"
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN
        }
        
        # Получаем текущие вебхуки
        async with session.get(
            "https://pay.crypt.bot/api/getWebhookInfo",
            headers=headers
        ) as response:
            data = await response.json()
            
            if data.get("ok"):
                webhook_info = data.get("result", {})
                if webhook_info.get("url") == webhook_url:
                    print("✅ Вебхук уже настроен правильно")
                    return True
                
                # Удаляем старый вебхук если есть
                if webhook_info.get("url"):
                    async with session.post(
                        "https://pay.crypt.bot/api/deleteWebhook",
                        headers=headers
                    ) as delete_response:
                        delete_data = await delete_response.json()
                        if not delete_data.get("ok"):
                            print(f"❌ Ошибка удаления старого вебхука: {delete_data}")
                            return False
            
        # Устанавливаем новый вебхук
        async with session.post(
            "https://pay.crypt.bot/api/setWebhook",
            headers=headers,
            json={
                "url": webhook_url,
                "secret": CRYPTO_PAY_WEBHOOK_SECRET
            }
        ) as response:
            data = await response.json()
            
            if data.get("ok"):
                print(f"✅ Вебхук успешно настроен: {webhook_url}")
                return True
            else:
                print(f"❌ Ошибка настройки вебхука: {data}")
                return False


if __name__ == "__main__":
    result = asyncio.run(setup_crypto_webhook())
    if result:
        print("🎉 Настройка Crypto Pay завершена успешно!")
    else:
        print("⚠️ Настройка Crypto Pay завершена с ошибками")
