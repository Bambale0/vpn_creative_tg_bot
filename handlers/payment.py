"""
Payment handlers for VPN Telegram Bot
"""

from aiogram import F, types
from datetime import datetime, timedelta
import aiosqlite
import asyncio

from config.config import DB_PATH
from config.dependencies import t, log, yookassa, crypto_pay
from utils.ui import show_loading
from utils.game import add_user_points, check_achievements, check_referral_system
from utils.payments import create_payment_ui, crypto_currency_menu


async def cb_yookassa_pay(c: types.CallbackQuery):
    """Обработчик выбора оплаты через ЮKassa"""
    uid = c.from_user.id
    months = int(c.data.split("_")[2])
    
    # Определяем сумму based on months
    amount = {1: 200, 3: 540, 12: 2000}[months]
    
    try:
        # Создаем платеж в ЮKassa
        payment_id, confirmation_url = await yookassa().create(
            amount=amount,
            months=months,
            user_id=uid
        )
        
        if not payment_id or not confirmation_url:
            await c.answer("❌ Ошибка создания платежа. Попробуйте позже.", show_alert=True)
            return
        
        # Сохраняем информацию о платеже в БД
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            await conn.execute(
                """INSERT INTO yookassa_payments 
                (user_id, amount, yookassa_id, confirmation_url, months, status) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (uid, amount, payment_id, confirmation_url, months, "pending")
            )
            await conn.commit()
        
        # Создаем улучшенный интерфейс оплаты
        order_text, keyboard = await create_payment_ui(
            uid, months, amount, "ЮKassa", confirmation_url, payment_id
        )
        
        await c.message.edit_text(order_text, parse_mode="HTML", reply_markup=keyboard)
        
    except Exception as e:
        log().error(f"Ошибка создания платежа ЮKassa: {e}")
        await c.answer("❌ Ошибка создания платежа. Попробуйте позже.", show_alert=True)


async def cb_check_yookassa(c: types.CallbackQuery):
    """Проверка статуса оплаты через ЮKassa"""
    uid = c.from_user.id
    payment_id = c.data.split("_")[2]
    
    # Показываем анимацию загрузки
    loading_msg = await show_loading(uid)
    
    try:
        # Проверяем статус платежа
        status, _ = await yookassa().status(payment_id)
        
        if status == "succeeded":
            async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
                # Обновляем статус платежа
                await conn.execute(
                    "UPDATE yookassa_payments SET status = 'paid' WHERE yookassa_id = ?",
                    (payment_id,)
                )
                
                # Получаем информацию о платеже
                cur = await conn.execute(
                    "SELECT user_id, amount, months FROM yookassa_payments WHERE yookassa_id = ?",
                    (payment_id,)
                )
                payment_info = await cur.fetchone()
                
                if not payment_info:
                    await loading_msg.edit_text("❌ Информация о платеже не найдена")
                    return
                
                user_id, amount, months = payment_info
                
                # Активируем подписку в отдельном соединении
                duration = months
                end_date = (datetime.utcnow() + timedelta(days=30 * duration)).isoformat()
                
                async with aiosqlite.connect(DB_PATH, timeout=5) as conn_sub:
                    await conn_sub.execute(
                        """INSERT INTO subscriptions 
                        (user_id, start_date, end_date, payment_id, duration) 
                        VALUES (?, datetime('now'), ?, ?, ?)""",
                        (user_id, end_date, f"yookassa_{payment_id}", duration)
                    )
                    await conn_sub.commit()
                
                # Начисляем очки за покупку (с повторными попытками)
                points_earned = duration * 20
                points_added = await add_user_points(uid, points_earned, "purchase")
                
                # Проверяем достижения (с повторными попытками)
                await check_achievements(uid, "first_purchase")
                
                await conn.commit()
            
            # Применяем реферальную систему
            await check_referral_system(uid, amount, f"yookassa_{payment_id}")
            
            success_message = await t(uid, "payment_success", points=points_earned)
            if not points_added:
                success_message += "\n⚠️ Не удалось начислить бонусные очки (повторите попытку позже)"
            
            await loading_msg.edit_text(
                success_message,
                parse_mode="HTML"
            )
        else:
            await loading_msg.edit_text("⏳ Платеж еще не получен или обрабатывается")
    except Exception as e:
        log().error(f"Ошибка проверки платежа: {e}")
        await loading_msg.edit_text("❌ Ошибка при проверке платежа")
    finally:
        await asyncio.sleep(3)
        await loading_msg.delete()


async def cb_crypto_pay(c: types.CallbackQuery):
    uid = c.from_user.id
    parts = c.data.split("_")  
    
    if len(parts) == 3:
        # Выбор криптовалюты
        months = int(parts[2])
        menu_text, keyboard = await crypto_currency_menu(uid, months)
        await c.message.edit_text(
            menu_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return
    
    # Создание инвойса
    months = int(parts[2])
    asset = parts[3]
    
    # Определяем сумму based on months
    amount = {1: 200, 3: 540, 12: 2000}[months]
    
    # Показываем анимацию загрузки
    loading_msg = await show_loading(uid)
    
    try:
        # Создаем инвойс в Crypto Pay с автоматическим расчетом курса
        invoice = await crypto_pay().create_invoice_with_auto_rate(
            amount_rub=amount,
            asset=asset,
            description=f"VPN подписка на {months} месяцев",
            user_id=uid
        )
        
        if not invoice:
            await loading_msg.edit_text("❌ Ошибка создания платежа. Попробуйте позже.")
            return
        
        # Сохраняем информацию об инвойсе в БД
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            await conn.execute(
                """INSERT INTO crypto_invoices 
                (user_id, fiat, amount_fiat, amount_coin, coin, address, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (uid, "RUB", amount, invoice["amount"], asset, invoice["invoice_id"], "pending")
            )
            await conn.commit()
        
        # Создаем улучшенный интерфейс оплаты
        order_text, keyboard = await create_payment_ui(
            uid, months, amount, "Crypto Pay", invoice['pay_url'], invoice['invoice_id']
        )
        
        await loading_msg.edit_text(order_text, parse_mode="HTML", reply_markup=keyboard)
        
    except Exception as e:
        log().error(f"Ошибка создания платежа: {e}")
        await loading_msg.edit_text("❌ Ошибка создания платежа. Попробуйте позже.")
    finally:
        await asyncio.sleep(2)


def register_payment_handlers(dp):
    """Регистрирует все payment хендлеры"""
    dp.callback_query.register(cb_yookassa_pay, F.data.startswith("yookassa_pay_"))
    dp.callback_query.register(cb_crypto_pay, F.data.startswith("crypto_pay_"))
    
    print("Payment хендлеры зарегистрированы")
