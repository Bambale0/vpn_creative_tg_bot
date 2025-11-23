import pytest
import json
import hmac
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from utils.crypto_pay import CryptoPay, sign_hook, handle_crypto_webhook


class TestCryptoPay:

    @pytest.fixture
    def crypto_pay(self):
        """Фикстура для объекта CryptoPay"""
        return CryptoPay("test_token_123")

    @pytest.mark.asyncio
    async def test_update_exchange_rates_success(self, crypto_pay):
        """Тестирование успешного обновления курсов валют"""
        mock_rates = [
            {"source": "USDT", "target": "RUB", "rate": "90.5", "is_valid": True},
            {"source": "BTC", "target": "RUB", "rate": "5000000", "is_valid": True}
        ]

        mock_response = {"ok": True, "result": mock_rates}

        with patch.object(crypto_pay, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_rates

            result = await crypto_pay.update_exchange_rates()

            assert result is True
            assert "USDT_RUB" in crypto_pay.exchange_rates
            assert "BTC_RUB" in crypto_pay.exchange_rates
            assert crypto_pay.exchange_rates["USDT_RUB"]["rate"] == 90.5
            assert crypto_pay.last_update is not None

    @pytest.mark.asyncio
    async def test_update_exchange_rates_failure(self, crypto_pay):
        """Тестирование неудачного обновления курсов"""
        with patch.object(crypto_pay, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("API Error")

            result = await crypto_pay.update_exchange_rates()

            assert result is False
            assert crypto_pay.exchange_rates == {}

    def test_get_exchange_rate_direct(self, crypto_pay):
        """Тестирование получения прямого курса"""
        crypto_pay.exchange_rates = {
            "USDT_RUB": {"rate": 90.5, "is_valid": True}
        }

        rate = crypto_pay.get_exchange_rate("USDT", "RUB")
        assert rate == 90.5

    def test_get_exchange_rate_reverse(self, crypto_pay):
        """Тестирование получения обратного курса"""
        crypto_pay.exchange_rates = {
            "USDT_RUB": {"rate": 90.5, "is_valid": True}
        }

        # Обратный курс RUB -> USDT должен быть 1/90.5
        rate = crypto_pay.get_exchange_rate("RUB", "USDT")
        assert abs(rate - (1/90.5)) < 0.0001

    @pytest.mark.asyncio
    async def test_convert_amount_same_currency(self, crypto_pay):
        """Тестирование конвертации одной валюты"""
        result = await crypto_pay.convert_amount(100, "RUB", "RUB")
        assert result == 100

    @pytest.mark.asyncio
    async def test_convert_amount_with_rate(self, crypto_pay):
        """Тестирование конвертации с курсом"""
        crypto_pay.exchange_rates = {
            "USDT_RUB": {"rate": 90.5, "is_valid": True}
        }

        result = await crypto_pay.convert_amount(100, "RUB", "USDT")
        expected = 100 / 90.5  # обратный курс
        assert abs(result - expected) < 0.0001

    @pytest.mark.asyncio
    async def test_create_invoice_success(self, crypto_pay):
        """Тестирование успешного создания инвойса"""
        mock_invoice = {
            "invoice_id": "test_invoice_123",
            "pay_url": "https://pay.crypt.bot/test",
            "amount": "1.5",
            "currency": "USDT",
            "status": "active"
        }

        with patch.object(crypto_pay, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_invoice

            result = await crypto_pay.create_invoice(1.5, "USDT", "Test payment", 12345)

            assert result == mock_invoice
            mock_request.assert_called_once_with(
                "POST",
                "createInvoice",
                asset="USDT",
                amount="1.5",
                description="Test payment",
                payload="12345",
                expires_in=900
            )

    @pytest.mark.asyncio
    async def test_check_invoice_success(self, crypto_pay):
        """Тестирование успешной проверки инвойса"""
        mock_invoices = {
            "items": [{
                "invoice_id": "test_invoice_123",
                "status": "paid",
                "amount": "1.5"
            }]
        }

        with patch.object(crypto_pay, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_invoices

            result = await crypto_pay.check_invoice("test_invoice_123")

            assert result["invoice_id"] == "test_invoice_123"
            assert result["status"] == "paid"

    @pytest.mark.asyncio
    async def test_check_invoice_not_found(self, crypto_pay):
        """Тестирование проверки несуществующего инвойса"""
        mock_invoices = {"items": []}

        with patch.object(crypto_pay, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_invoices

            result = await crypto_pay.check_invoice("nonexistent_invoice")

            assert result is None

    @pytest.mark.asyncio
    async def test_create_invoice_with_auto_rate_success(self, crypto_pay):
        """Тестирование создания инвойса с авто-курсом"""
        crypto_pay.exchange_rates = {
            "USDT_RUB": {"rate": 90.5, "is_valid": True}
        }

        mock_invoice = {
            "invoice_id": "auto_invoice_123",
            "pay_url": "https://pay.crypt.bot/auto",
            "amount": "2.21",  # 200 / 90.5 ≈ 2.2099, округлено до 2.21
            "status": "active"
        }

        with patch.object(crypto_pay, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_invoice

            result = await crypto_pay.create_invoice_with_auto_rate(
                200.0, "USDT", "VPN 1 month", 12345
            )

            assert result == mock_invoice

            # Проверяем вызов createInvoice с рассчитанной суммой
            call_kwargs = mock_request.call_args[1]
            calculated_amount = float(call_kwargs["amount"])
            expected_amount = 200.0 / 90.5  # ≈ 2.2099
            assert abs(calculated_amount - expected_amount) < 0.01

    @pytest.mark.asyncio
    async def test_create_invoice_with_auto_rate_fallback(self, crypto_pay):
        """Тестирование fallback при ошибке авто-курса"""
        # Оставляем пустые exchange_rates
        crypto_pay.exchange_rates = {}

        mock_invoice = {
            "invoice_id": "fallback_invoice_123",
            "status": "active"
        }

        with patch.object(crypto_pay, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_invoice

            result = await crypto_pay.create_invoice_with_auto_rate(
                200.0, "USDT", "VPN 1 month", 12345
            )

            assert result == mock_invoice

            # При fallback должна вызваться обычная create_invoice с исходной суммой
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["amount"] == "200.0"  # fallback к исходной сумме

    def test_sign_hook_valid(self):
        """Тестирование валидной HMAC подписи"""
        body = b'{"test": "data"}'
        secret = b'test_secret_key'
        expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

        result = sign_hook(body, secret)
        assert result == expected_signature

    @pytest.mark.asyncio
    async def test_handle_crypto_webhook_success(self):
        """Тестирование успешной обработки вебхука"""
        # Создаем моковый request
        mock_request = MagicMock()
        mock_request.headers = {
            "Crypto-Pay-API-Signature": "valid_signature"
        }
        body_data = {
            "event": "invoice_paid",
            "payload": {
                "invoice": {
                    "payload": "12345",
                    "invoice_id": "inv_123",
                    "amount": "1.5"
                }
            }
        }
        mock_request.read = AsyncMock(return_value=json.dumps(body_data).encode())

        # Мокируем finish_crypto_payment
        with patch('utils.crypto_pay.finish_crypto_payment', new_callable=AsyncMock) as mock_finish, \
             patch('utils.crypto_pay.hmac.compare_digest', return_value=True), \
             patch('json.loads', return_value=body_data):

            mock_bot = MagicMock()
            status, response = await handle_crypto_webhook(mock_request, mock_bot, ":memory:")

            assert status == 200
            assert response == "ok"
            mock_finish.assert_called_once_with(12345, "inv_123", 1.5, mock_bot, ":memory:")

    @pytest.mark.asyncio
    async def test_handle_crypto_webhook_invalid_signature(self):
        """Тестирование вебхука с неверной подписью"""
        mock_request = MagicMock()
        mock_request.headers = {
            "Crypto-Pay-API-Signature": "invalid_signature"
        }
        mock_request.read = AsyncMock(return_value=b'{"test": "data"}')

        mock_bot = MagicMock()

        status, response = await handle_crypto_webhook(mock_request, mock_bot, ":memory:")

        assert status == 401
        assert response == "Unauthorized"

    @pytest.mark.asyncio
    async def test_handle_crypto_webhook_wrong_event(self):
        """Тестирование вебхука с неподдерживаемым событием"""
        mock_request = MagicMock()
        mock_request.headers = {
            "Crypto-Pay-API-Signature": "valid_signature"
        }
        body_data = {"event": "invoice_created"}  # не invoice_paid
        mock_request.read = AsyncMock(return_value=json.dumps(body_data).encode())

        with patch('utils.crypto_pay.hmac.compare_digest', return_value=True), \
             patch('json.loads', return_value=body_data):

            mock_bot = MagicMock()
            status, response = await handle_crypto_webhook(mock_request, mock_bot, ":memory:")

            assert status == 200
            assert response == "ok"
