import datetime, aiosqlite, logging
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config.dependencies import t
from config.config import DB_PATH

log = logging.getLogger("payments")

DAYS = {1: 30, 3: 90, 12: 360}
AMOUNT = {1: 200, 3: 540, 12: 2000}


def amount_to_months(amount: float) -> int:
    for m, a in AMOUNT.items():
        if abs(amount - a) < 1:
            return m
    return 1


async def crypto_currency_menu(uid, months):
    """Меню выбора криптовалюты с автоматическим расчетом сумм"""
    log = logging.getLogger(__name__)
    
    from config.dependencies import get_crypto_pay_instance
    
    # Получаем экземпляр CryptoPay
    crypto_pay = get_crypto_pay_instance()
    if not crypto_pay:
        log.error("CryptoPay instance not initialized")
        # Возвращаем меню без курсов
        builder = InlineKeyboardBuilder()
        for currency in ["USDT", "BTC", "ETH", "TON"]:
            builder.row(types.InlineKeyboardButton(
                text=f"{currency} • ~ {currency}",
                callback_data=f"crypto_pay_{months}_{currency}"
            ))
        builder.row(types.InlineKeyboardButton(
            text=await t(uid, "back_button"),
            callback_data=f"pay_{months}"
        ))
        menu_text = f"₿ <b>Выберите криптовалюту для оплаты {AMOUNT.get(months, months * 200)} RUB</b>\n⚠️ <i>Курсы временно недоступны</i>"
        return menu_text, builder.as_markup()
    
    # Инициализируем rates пустым словарем
    rates = {}
    rates_info = ""
    # Используем исходную сумму без наценки
    amount_rub = AMOUNT.get(months, months * 200)  
    
    try:
        # Получаем стоимость в рублях с наценкой
        rub_amount = amount_rub
        
        # Рассчитываем суммы в криптовалюте
        for currency in ["USDT", "BTC", "ETH", "TON"]:
            try:
                crypto_amount = await crypto_pay.convert_amount(rub_amount, "RUB", currency)
                # Форматируем в зависимости от валюты
                if currency == "USDT":
                    formatted_amount = f"{crypto_amount:.2f}"
                elif currency == "TON":
                    formatted_amount = f"{crypto_amount:.2f}"
                else:
                    formatted_amount = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                rates[currency] = formatted_amount
            except Exception as e:
                log.warning(f"Ошибка конвертации {currency}: {e}")
                rates[currency] = "~"
        
        rates_info = f"\n📊 <b>Текущие курсы:</b>\n"
        rates_info += f"• 1 USDT ≈ {await crypto_pay.get_exchange_rate('USDT', 'RUB'):.2f} RUB\n"
        rates_info += f"• 1 BTC ≈ {await crypto_pay.get_exchange_rate('BTC', 'RUB'):.0f} RUB\n"
        rates_info += f"• 1 ETH ≈ {await crypto_pay.get_exchange_rate('ETH', 'RUB'):.0f} RUB\n"
        rates_info += f"• 1 TON ≈ {await crypto_pay.get_exchange_rate('TON', 'RUB'):.2f} RUB\n"
        
    except Exception as e:
        log.error(f"Ошибка получения курсов: {e}")
        rates_info = "\n⚠️ <i>Курсы обновляются...</i>"
    
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    
    # Кнопки с суммами в криптовалюте
    buttons_text = [
        (f"USDT • {rates.get('USDT', '~')} USDT", "USDT"),
        (f"BTC • {rates.get('BTC', '~')} BTC", "BTC"),
        (f"ETH • {rates.get('ETH', '~')} ETH", "ETH"),
        (f"TON • {rates.get('TON', '~')} TON", "TON")
    ]
    
    for text, currency in buttons_text:
        builder.row(types.InlineKeyboardButton(
            text=text,
            callback_data=f"crypto_pay_{months}_{currency}"
        ))
    
    builder.row(types.InlineKeyboardButton(
        text=await t(uid, "back_button"),
        callback_data=f"pay_{months}"
    ))
    
    menu_text = f"₿ <b>Выберите криптовалюту для оплаты {amount_rub} RUB</b>{rates_info}"
    
    return menu_text, builder.as_markup()


async def create_payment_ui(uid, months, amount, method, payment_url, payment_id):
    """Создает улучшенный интерфейс оплаты"""
    builder = InlineKeyboardBuilder()
    
    # Информация о заказе
    order_text = (
        f"🛒 <b>Ваш заказ</b>\n\n"
        f"📦 Тариф: {months} месяц(ев)\n"
        f"💵 Сумма: {amount} RUB\n"
        f"💳 Способ: {method}\n\n"
        f"⬇️ <b>Выберите действие:</b>"
    )
    
    # Динамические кнопки в зависимости от метода оплаты
    if method == "ЮKassa":
        builder.row(types.InlineKeyboardButton(
            text="💳 Оплатить картой",
            url=payment_url
        ))
    else:
        builder.row(types.InlineKeyboardButton(
            text="₿ Перейти к оплате",
            url=payment_url
        ))
    
    builder.row(types.InlineKeyboardButton(
        text="◀️ Назад к тарифам",
        callback_data="pricing"
    ))
    
    return order_text, builder.as_markup()


async def ensure_subscription_table(conn: aiosqlite.Connection):
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS crypto_invoices("
        "id TEXT PRIMARY KEY, user_id INT, fiat TEXT, amount_fiat REAL, amount_coin REAL, coin TEXT, address TEXT, status TEXT)"
    )
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS yookassa_payments("
        "id TEXT PRIMARY KEY, user_id INT, amount REAL, months INT, status TEXT)"
    )


async def finish_crypto_payment(
        user_id: int, inv_id: str, amount: float, bot: Bot, db: str
):
    months = amount_to_months(amount)
    end = datetime.datetime.utcnow() + datetime.timedelta(days=DAYS[months])
    
    # Обновляем статус инвойса в отдельном соединении
    async with aiosqlite.connect(db, timeout=5) as conn:
        await conn.execute(
            "UPDATE crypto_invoices SET status='paid' WHERE id=?", (inv_id,)
        )
        await conn.commit()
    
    # Активируем подписку в отдельном соединении
    async with aiosqlite.connect(db, timeout=5) as conn:
        await conn.execute(
            "INSERT INTO subscriptions(user_id,start_date,end_date,payment_id,duration) "
            "VALUES (?,datetime('now'),?,?,?)",
            (user_id, end.isoformat(), f"crypto_{inv_id}", months),
        )
        await conn.commit()

    # Начисляем очки за покупку (с повторными попытками)
    from utils.game import add_user_points, check_referral_system  # цир. импорт
    points_added = await add_user_points(user_id, months * 20, "purchase")
    await check_referral_system(user_id, amount, f"crypto_{inv_id}")
    
    message = f"✅ Платеж принят. Подписка на {months} мес. активна."
    if not points_added:
        message += "\n⚠️ Не удалось начислить бонусные очки (повторите попытку позже)"
    
    try:
        await bot.send_message(user_id, message)
    except Exception as e:
        log.warning("notify user %s: %s", user_id, e)


async def finish_yookassa_payment(
        user_id: int, pay_id: str, amount: float, bot: Bot, db: str
):
    months = amount_to_months(amount)
    end = datetime.datetime.utcnow() + datetime.timedelta(days=DAYS[months])
    async with aiosqlite.connect(db) as conn:
        await conn.execute(
            "UPDATE yookassa_payments SET status='paid' WHERE id=?", (pay_id,)
        )
        await conn.execute(
            "INSERT INTO subscriptions(user_id,start_date,end_date,payment_id,duration) "
            "VALUES (?,datetime('now'),?,?,?)",
            (user_id, end.isoformat(), f"yookassa_{pay_id}", months),
        )
        await conn.commit()

    from utils.game import add_user_points, check_referral_system
    await add_user_points(user_id, months * 20, "purchase")
    await check_referral_system(user_id, amount, f"yookassa_{pay_id}")

    try:
        await bot.send_message(
            user_id,
            f"✅ ЮKassa-оплата подтверждена. Подписка на {months} мес. активна.",
        )
    except Exception as e:
        log.warning("notify user %s: %s", user_id, e)


async def get_user_subscription(user_id: int) -> dict:
    """
    Получить информацию о подписке пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        dict: информация о подписке или None если подписки нет
    """
    try:
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute(
                """SELECT user_id, start_date, end_date, payment_id, duration, is_trial
                FROM subscriptions 
                WHERE user_id = ? AND end_date > datetime('now')
                ORDER BY end_date DESC LIMIT 1""",
                (user_id,)
            )
            subscription = await cursor.fetchone()
            
            if subscription:
                user_id, start_date, end_date, payment_id, duration, is_trial = subscription
                return {
                    "user_id": user_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "payment_id": payment_id,
                    "duration": duration,
                    "is_trial": bool(is_trial),
                    "is_active": True
                }
            else:
                # Проверяем trial активации
                cursor = await conn.execute(
                    "SELECT activated_at FROM trial_activations WHERE user_id = ?",
                    (user_id,)
                )
                trial_activation = await cursor.fetchone()
                
                if trial_activation:
                    return {
                        "user_id": user_id,
                        "is_trial_used": True,
                        "is_active": False
                    }
                
                return None
                
    except Exception as e:
        log.error(f"Error getting user subscription for {user_id}: {e}")
        return None
