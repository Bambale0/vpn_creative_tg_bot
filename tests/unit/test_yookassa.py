import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from utils.yookassa_pay import YooPay


class TestYooKassaPay:

    @pytest.fixture
    def yoo_pay(self):
        """Фикстура для объекта YooPay"""
        return YooPay()

    def test_basic_auth(self):
        """Тестирование генерации basic auth заголовка"""
        with patch('config.config.YOOKASSA_SHOP_ID', 'test_shop'), \
             patch('config.config.YOOKASSA_SECRET_KEY', 'test_secret'):
            auth_header = YooPay.basic_auth()
            expected_auth = {'Authorization': 'Basic dGVzdF9zaG9wOnRlc3Rfc2VjcmV0'}
            assert auth_header == expected_auth

    @pytest.mark.asyncio
    async def test_create_payment_success(self, yoo_pay):
        """Тестирование успешного создания платежа"""
        # Mock ответ API
        mock_response_data = {
            "id": "test_payment_id_123",
            "status": "pending",
            "amount": {"value": "200.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=test_payment_id_123"
            }
        }

        # Mock aiohttp ClientSession
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.text = AsyncMock(return_value='{"success": true}')

            mock_session.post.return_value.__aenter__.return_value = mock_response

            # Вызов метода
            payment_id, confirmation_url = await yoo_pay.create(200.00, 1, 12345)

            # Проверки
            assert payment_id == "test_payment_id_123"
            assert "checkout" in confirmation_url

            # Проверка вызовов
            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert "https://api.yookassa.ru/v3/payments" in call_args[0][0]

            # Проверка JSON тела запроса
            json_body = call_args[1]['json']
            assert json_body['amount']['value'] == "200.00"
            assert json_body['amount']['currency'] == "RUB"
            assert json_body['metadata']['user_id'] == "12345"
            assert json_body['metadata']['months'] == "1"

    @pytest.mark.asyncio
    async def test_create_payment_api_error(self, yoo_pay):
        """Тестирование ошибки API при создании платежа"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value='{"error": "Invalid request"}')

            mock_session.post.return_value.__aenter__.return_value = mock_response

            # Проверка исключения
            with pytest.raises(RuntimeError, match="YooKassa API error"):
                await yoo_pay.create(200.00, 1, 12345)

    @pytest.mark.asyncio
    async def test_create_payment_incomplete_response(self, yoo_pay):
        """Тестирование неполного ответа API"""
        mock_response_data = {
            "status": "pending",
            "amount": {"value": "200.00", "currency": "RUB"}
            # отсутствует "id" и "confirmation"
        }

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)

            mock_session.post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(RuntimeError, match="Incomplete response"):
                await yoo_pay.create(200.00, 1, 12345)

    @pytest.mark.asyncio
    async def test_status_payment_success(self, yoo_pay):
        """Тестирование успешной проверки статуса платежа"""
        mock_response_data = {
            "id": "test_payment_id_123",
            "status": "succeeded",
            "amount": {"value": "200.00", "currency": "RUB"}
        }

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)

            mock_session.get.return_value.__aenter__.return_value = mock_response

            # Вызов метода
            status, amount = await yoo_pay.status("test_payment_id_123")

            # Проверки
            assert status == "succeeded"
            assert amount == 200.00

            # Проверка URL
            call_args = mock_session.get.call_args
            assert "https://api.yookassa.ru/v3/payments/test_payment_id_123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_status_payment_api_error(self, yoo_pay):
        """Тестирование ошибки API при проверке статуса"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.text = AsyncMock(return_value='{"error": "Payment not found"}')

            mock_session.get.return_value.__aenter__.return_value = mock_response

            with pytest.raises(RuntimeError, match="YooKassa API error"):
                await yoo_pay.status("test_payment_id_123")

    @pytest.mark.asyncio
    async def test_status_payment_incomplete_response(self, yoo_pay):
        """Тестирование неполного ответа при проверке статуса"""
        mock_response_data = {
            "id": "test_payment_id_123",
            "status": "succeeded"
            # отсутствует "amount"
        }

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)

            mock_session.get.return_value.__aenter__.return_value = mock_response

            with pytest.raises(RuntimeError, match="Incomplete response"):
                await yoo_pay.status("test_payment_id_123")
