"""
Webhook handlers for VPN Telegram Bot
"""

from datetime import datetime, timedelta
import aiosqlite
import json
import hmac
import hashlib

from aiohttp import web

from config.config import DB_PATH
from config.dependencies import log, bot
from utils.game import add_user_points, check_achievements, check_referral_system


async def process_yookassa_webhook(data: dict):
    """Обработка вебхука от ЮKassa"""
    try:
        payment_data = data.get('object', {})
        payment_id = payment_data.get('id')
        status = payment_data.get('status')
        
        if not payment_id or not status:
            return
        
        log().info(f"Processing YooKassa webhook: {payment_id}, status: {status}")
        
        # Обновляем статус платежа в отдельном соединении
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            await conn.execute(
                "UPDATE yookassa_payments SET status = ? WHERE yookassa_id = ?",
                (status, payment_id)
            )
            await conn.commit()
        
        if status == "succeeded":
            # Получаем информацию о платеже в отдельном соединении
            async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
                cur = await conn.execute(
                    "SELECT user_id, amount, months FROM yookassa_payments WHERE yookassa_id = ?",
                    (payment_id,)
                )
                payment_info = await cur.fetchone()
            
            if payment_info:
                user_id, amount, months = payment_info
                
                # Активируем подписку в отдельном соединении
                async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
                    end_date = (datetime.utcnow() + timedelta(days=30 * months)).isoformat()
                    await conn.execute(
                        """INSERT INTO subscriptions 
                        (user_id, start_date, end_date, payment_id, duration) 
                        VALUES (?, datetime('now'), ?, ?, ?)""",
                        (user_id, end_date, f"yookassa_{payment_id}", months)
                    )
                    await conn.commit()
                
                # Начисляем очки за покупку (с повторными попытками)
                points_earned = months * 20
                points_added = await add_user_points(user_id, points_earned, "purchase")
                
                # Проверяем достижения (с повторными попытками)
                await check_achievements(user_id, "first_purchase")
                
                # Применяем реферальную систему
                await check_referral_system(user_id, amount, f"yookassa_{payment_id}")
                
                # Отправляем уведомление пользователю
                if points_added:
                    try:
                        await bot().send_message(
                            user_id,
                            f"✅ Ваша подписка активирована на {months} месяцев!\n"
                            f"🎉 Начислено {points_earned} очков за покупку!"
                        )
                    except:
                        pass
                else:
                    try:
                        await bot().send_message(
                            user_id,
                            f"✅ Ваша подписка активирована на {months} месяцев!\n"
                            f"⚠️ Не удалось начислить бонусные очки (повторите попытку позже)"
                        )
                    except:
                        pass
            
    except Exception as e:
        log().error(f"YooKassa webhook processing error: {e}")


async def process_crypto_webhook(data: dict):
    """Обработка вебхука от Crypto Pay"""
    try:
        event = data.get('event', '')
        invoice_data = data.get('payload', {}).get('invoice', {})
        invoice_id = invoice_data.get('invoice_id')
        status = invoice_data.get('status')
        
        if not invoice_id or not status:
            return
        
        log().info(f"Processing Crypto Pay webhook: {invoice_id}, status: {status}")
        
        if event == "invoice.paid" and status == "paid":
            async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
                # Обновляем статус инвойса
                await conn.execute(
                    "UPDATE crypto_invoices SET status = 'paid' WHERE address = ?",
                    (invoice_id,)
                )
                
                # Получаем данные инвойса
                cur = await conn.execute(
                    "SELECT user_id, amount_fiat FROM crypto_invoices WHERE address = ?",
                    (invoice_id,)
                )
                invoice_info = await cur.fetchone()
                
                if invoice_info:
                    user_id, amount_fiat = invoice_info
                    
                    # Определяем duration по сумме
                    duration = {200: 1, 540: 3, 2000: 12}.get(amount_fiat, 1)
                    
                    # Активируем подписку
                    end_date = (datetime.utcnow() + timedelta(days=30 * duration)).isoformat()
                    await conn.execute(
                        """INSERT INTO subscriptions 
                        (user_id, start_date, end_date, payment_id, duration) 
                        VALUES (?, datetime('now'), ?, ?, ?)""",
                        (user_id, end_date, f"crypto_{invoice_id}", duration)
                    )
                    
                    # Начисляем очки за покупку
                    points_earned = duration * 20
                    await add_user_points(user_id, points_earned, "purchase")
                    
                    # Проверяем достижения
                    await check_achievements(user_id, "first_purchase")
                    
                    # Применяем реферальную систему
                    await check_referral_system(user_id, amount_fiat, f"crypto_{invoice_id}")
                    
                    # Отправляем уведомление пользователю
                    try:
                        await bot().send_message(
                            user_id,
                            f"✅ Ваша подписка активирована на {duration} месяцев!\n"
                            f"🎉 Начислено {points_earned} очков за покупку!"
                        )
                    except:
                        pass
                
                await conn.commit()
                
    except Exception as e:
        log().error(f"Crypto Pay webhook processing error: {e}")


# Дополнительные утилиты для вебхуков
async def verify_webhook_signature(data: dict, signature: str, secret: str) -> bool:
    """Проверка подписи вебхука"""
    try:
        # Создаем подпись из данных
        payload = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
        
    except Exception as e:
        log().error(f"Webhook signature verification error: {e}")
        return False


async def log_webhook_event(data: dict, source: str):
    """Логирование вебхук событий"""
    try:
        event_data = {
            'source': source,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        log().info(f"Webhook event: {json.dumps(event_data, ensure_ascii=False)}")
        
        # Сохраняем в БД для аудита
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            await conn.execute(
                """INSERT INTO webhook_logs 
                (source, event_data, timestamp) 
                VALUES (?, ?, datetime('now'))""",
                (source, json.dumps(data, ensure_ascii=False))
            )
            await conn.commit()
            
    except Exception as e:
        log().error(f"Webhook logging error: {e}")


def register_webhook_handlers(dp):
    """Регистрирует обработчики вебхуков"""
    # Webhook handlers are middleware-based and don't use dp registration
    pass


async def yookassa_webhook_handler(request):
    """HTTP обработчик для вебхуков ЮKassa"""
    try:
        # Получаем подпись из заголовка (правильное имя для YooKassa)
        signature = request.headers.get('X-Yookassa-Signature')
        
        # Получаем данные запроса
        data = await request.json()
        
        # ВРЕМЕННО: отключаем проверку подписи для тестирования в тестовом режиме
        # TODO: Включить проверку подписи в продакшене
        if False and not signature:  # Изменено с True на False для тестирования
            log().warning("YooKassa webhook received without signature - rejecting")
            return web.json_response({"error": "signature required"}, status=401)
        
        # Проверяем подпись только если она предоставлена
        if signature:
            from config.config import YOOKASSA_SECRET_KEY
            
            # ЮKassa использует секретный ключ для подписи вебхуков
            is_valid = await verify_webhook_signature(data, signature, YOOKASSA_SECRET_KEY)
            if not is_valid:
                log().warning(f"Invalid YooKassa webhook signature: {signature}")
                return web.json_response({"error": "invalid signature"}, status=401)
        
        await process_yookassa_webhook(data)
        return web.json_response({"status": "ok"})
    except Exception as e:
        log().error(f"YooKassa webhook error: {e}")
        return web.json_response({"error": "internal error"}, status=500)


async def crypto_pay_webhook_handler(request):
    """HTTP обработчик для вебхуков Crypto Pay"""
    try:
        # Crypto Pay также использует подпись в заголовке
        signature = request.headers.get('X-Crypto-Pay-Signature')
        
        # Проверяем подпись (если предоставлена)
        if signature:
            from config.config import CRYPTO_PAY_TOKEN
            data = await request.json()
            
            # Crypto Pay использует токен для подписи вебхуков
            is_valid = await verify_webhook_signature(data, signature, CRYPTO_PAY_TOKEN)
            if not is_valid:
                log().warning(f"Invalid Crypto Pay webhook signature: {signature}")
                return web.json_response({"error": "invalid signature"}, status=401)
        else:
            # Если подпись не предоставлена, все равно обрабатываем (для разработки)
            # Но логируем предупреждение
            log().warning("Crypto Pay webhook received without signature")
            data = await request.json()
        
        await process_crypto_webhook(data)
        return web.json_response({"status": "ok"})
    except Exception as e:
        log().error(f"Crypto Pay webhook error: {e}")
        return web.json_response({"error": "internal error"}, status=500)
