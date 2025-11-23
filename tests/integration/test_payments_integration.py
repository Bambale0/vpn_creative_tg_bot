import pytest
import aiosqlite
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types

from utils.payments import finish_crypto_payment, finish_yookassa_payment, create_payment_ui, crypto_currency_menu
from utils.crypto_pay import handle_crypto_webhook


class TestPaymentIntegration:

    @pytest.fixture
    async def db_conn(self, tmp_path):
        """Создает тестовую базу данных"""
        db_path = tmp_path / "test.db"
        conn = await aiosqlite.connect(db_path)

        # Создаем необходимые таблицы
        await conn.execute("""
            CREATE TABLE subscriptions (
                user_id INTEGER,
                start_date TEXT,
                end_date TEXT,
                payment_id TEXT,
                duration INTEGER,
                is_trial INTEGER DEFAULT 0
            )
        """)

        await conn.execute("""
            CREATE TABLE crypto_invoices (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                fiat TEXT,
                amount_fiat REAL,
                amount_coin REAL,
                coin TEXT,
                address TEXT,
                status TEXT
            )
        """)

        await conn.execute("""
            CREATE TABLE yookassa_payments (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                yookassa_id TEXT,
                confirmation_url TEXT,
                months INTEGER,
                status TEXT
            )
        """)

        await conn.commit()
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_finish_crypto_payment_integration(self, db_conn):
        """Интеграционный тест завершения крипто-платежа"""
        user_id = 12345
        inv_id = "test_invoice_123"
        amount = 200.0  # соответствует 1 месяцу

        # Создаем запись об инвойсе
        await db_conn.execute("""
            INSERT INTO crypto_invoices (id, user_id, fiat, amount_fiat, amount_coin, coin, address, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (inv_id, user_id, "RUB", amount, 2.21, "USDT", inv_id, "pending"))
        await db_conn.commit()

        # Мокаем бота
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        # Мокируем игровые функции
        with patch('utils.payments.add_user_points', new_callable=AsyncMock) as mock_add_points, \
             patch('utils.payments.check_referral_system', new_callable=AsyncMock) as mock_check_referral:

            mock_add_points.return_value = True

            # Выполняем завершение платежа
            await finish_crypto_payment(user_id, inv_id, amount, mock_bot, ":memory:")

            # Проверяем, что подписка создана
            cursor = await db_conn.execute(
                "SELECT user_id, payment_id, duration FROM subscriptions WHERE user_id = ?",
                (user_id,)
            )
            subscription = await cursor.fetchone()

            assert subscription is not None
            assert subscription[0] == user_id
            assert subscription[1] == f"crypto_{inv_id}"
            assert subscription[2] == 1  # 1 месяц для 200 RUB

            # Проверяем, что статус инвойса обновлен
            cursor = await db_conn.execute(
                "SELECT status FROM crypto_invoices WHERE id = ?",
                (inv_id,)
            )
            invoice_status = await cursor.fetchone()
            assert invoice_status[0] == "paid"

            # Проверяем вызовы бота и игровых функций
            mock_bot.send_message.assert_called_once()
            message_sent = mock_bot.send_message.call_args[0][1]
            assert "✅ Платеж принят" in message_sent
            assert "1 мес" in message_sent

            mock_add_points.assert_called_once_with(user_id, 20, "purchase")  # 1 * 20
            mock_check_referral.assert_called_once()

    @pytest.mark.asyncio
    async def test_finish_yookassa_payment_integration(self, db_conn):
        """Интеграционный тест завершения Yookassa платежа"""
        user_id = 12345
        pay_id = "test_payment_123"
        amount = 540.0  # соответствует 3 месяцам

        # Создаем запись о платеже
        await db_conn.execute("""
            INSERT INTO yookassa_payments (id, user_id, amount, yookassa_id, months, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pay_id, user_id, amount, pay_id, 3, "pending"))
        await db_conn.commit()

        # Мокаем бота
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        # Мокируем игровые функции
        with patch('utils.payments.add_user_points', new_callable=AsyncMock) as mock_add_points, \
             patch('utils.payments.check_referral_system', new_callable=AsyncMock) as mock_check_referral:

            mock_add_points.return_value = True

            # Выполняем завершение платежа
            await finish_yookassa_payment(user_id, pay_id, amount, mock_bot, ":memory:")

            # Проверяем, что подписка создана
            cursor = await db_conn.execute(
                "SELECT user_id, payment_id, duration FROM subscriptions WHERE user_id = ?",
                (user_id,)
            )
            subscription = await cursor.fetchone()

            assert subscription is not None
            assert subscription[0] == user_id
            assert subscription[1] == f"yookassa_{pay_id}"
            assert subscription[2] == 3  # 3 месяца для 540 RUB

            # Проверяем, что статус платежа обновлен
            cursor = await db_conn.execute(
                "SELECT status FROM yookassa_payments WHERE id = ?",
                (pay_id,)
            )
            payment_status = await cursor.fetchone()
            assert payment_status[0] == "paid"

            # Проверяем вызовы бота
            mock_bot.send_message.assert_called_once()
            message_sent = mock_bot.send_message.call_args[0][1]
            assert "✅ ЮKassa-оплата подтверждена" in message_sent
            assert "3 мес" in message_sent

            mock_add_points.assert_called_once_with(user_id, 60, "purchase")  # 3 * 20
            mock_check_referral.assert_called_once()

    @pytest.mark.asyncio
    async def test_crypto_webhook_full_flow(self, db_conn):
        """Тестирование полного потока обработки крипто-вебхука"""
        user_id = 12345
        inv_id = "webhook_invoice_123"
        amount = 200.0

        # Создаем запись об инвойсе
        await db_conn.execute("""
            INSERT INTO crypto_invoices (id, user_id, fiat, amount_fiat, amount_coin, coin, address, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (inv_id, user_id, "RUB", amount, 2.21, "USDT", inv_id, "pending"))
        await db_conn.commit()

        # Создаем моковый request
        mock_request = MagicMock()
        mock_request.headers = {
            "Crypto-Pay-API-Signature": "test_signature"
        }

        body_data = {
            "event": "invoice_paid",
            "payload": {
                "invoice": {
                    "payload": str(user_id),
                    "invoice_id": inv_id,
                    "amount": str(amount)
                }
            }
        }

        mock_request.read = AsyncMock(return_value=json.dumps(body_data).encode())

        # Мокаем валидацию подписи и бота
        mock_bot = MagicMock()

        with patch('utils.crypto_pay.hmac.compare_digest', return_value=True), \
             patch('utils.crypto_pay.finish_crypto_payment', new_callable=AsyncMock) as mock_finish, \
             patch('json.loads', return_value=body_data):

            # Обрабатываем вебхук
            status, response = await handle_crypto_webhook(mock_request, mock_bot, ":memory:")

            # Проверяем успешный ответ
            assert status == 200
            assert response == "ok"

            # Проверяем вызов завершения платежа
            mock_finish.assert_called_once_with(user_id, inv_id, amount, mock_bot, ":memory:")

    @pytest.mark.asyncio
    async def test_create_payment_ui_structure(self):
        """Тестирование создания UI платежа"""
        uid = 12345
        months = 1
        amount = 200
        method = "ЮKassa"
        payment_url = "https://example.com/pay"
        payment_id = "test_payment_123"

        order_text, keyboard = await create_payment_ui(uid, months, amount, method, payment_url, payment_id)

        # Проверяем текст заказа
        assert "🛒 <b>Ваш заказ</b>" in order_text
        assert f"{months} месяц(ев)" in order_text
        assert f"{amount} RUB" in order_text
        assert method in order_text

        # Проверяем клавиатуру (inline клавиатура)
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

        # Проверяем кнопку оплаты
        pay_button = keyboard.inline_keyboard[0][0]
        assert pay_button.url == payment_url

        # Проверяем кнопку "Назад"
        back_button = keyboard.inline_keyboard[1][0]
        assert back_button.callback_data == "pricing"

    @pytest.mark.asyncio
    async def test_crypto_currency_menu_with_rates(self):
        """Тестирование меню выбора криптовалюты с курсами"""
        uid = 12345
        months = 1

        # Мокаем крипто-пей
        mock_crypto_pay = MagicMock()
        mock_crypto_pay.convert_amount = AsyncMock(side_effect=lambda rub, from_curr, to_curr: {
            ("RUB", "USDT"): 2.0,
            ("RUB", "BTC"): 0.00005,
            ("RUB", "ETH"): 0.0005,
            ("RUB", "TON"): 2.5
        }.get((from_curr, to_curr), 1.0))

        mock_crypto_pay.get_exchange_rate = AsyncMock(side_effect=lambda from_curr, to_curr: {
            ("USDT", "RUB"): 100.0,
            ("BTC", "RUB"): 2000000.0,
            ("ETH", "RUB"): 200000.0,
            ("TON", "RUB"): 80.0
        }.get((from_curr, to_curr), 1.0))

        with patch('utils.payments.get_crypto_pay_instance', return_value=mock_crypto_pay), \
             patch('utils.payments.t', new_callable=AsyncMock) as mock_t:

            mock_t.return_value = "Назад"

            menu_text, keyboard = await crypto_currency_menu(uid, months)

            # Проверяем текст меню
            assert "₿ <b>Выберите криптовалюту для оплаты 200 RUB</b>" in menu_text
            assert "Текущие курсы:" in menu_text

            # Проверяем кнопки валют
            assert len(keyboard.inline_keyboard) > 0

            # Проверяем callback_data для кнопок
            button_texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
            assert any("USDT" in text for text in button_texts)
            assert any("BTC" in text for text in button_texts)
            assert any("ETH" in text for text in button_texts)
            assert any("TON" in text for text in button_texts)

    @pytest.mark.asyncio
    async def test_crypto_currency_menu_without_rates(self):
        """Тестирование меню выбора криптовалюты без курсов"""
        uid = 12345
        months = 1

        with patch('utils.payments.get_crypto_pay_instance', return_value=None), \
             patch('utils.payments.t', new_callable=AsyncMock) as mock_t:

            mock_t.return_value = "Назад"

            menu_text, keyboard = await crypto_currency_menu(uid, months)

            # Проверяем текст меню
            assert "Курсы временно недоступны" in menu_text
            assert "200 RUB" in menu_text

            # Проверяем кнопки (должны быть без сумм)
            assert len(keyboard.inline_keyboard) > 0
