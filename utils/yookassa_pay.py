import aiohttp, base64, logging
from config.config import YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID

log = logging.getLogger("yookassa")
YOOKASSA_API_URL = "https://api.yookassa.ru/v3"


class YooPay:

    @staticmethod
    def basic_auth():
        token = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    async def create(self, amount: float, months: int, user_id: int):
        import uuid
        uid = uuid.uuid4()
        body = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "description": f"VPN {months} мес.",
            "confirmation": {"type": "redirect", "return_url": "tg://resolve"},
            "metadata": {"user_id": str(user_id), "months": str(months)},
            "capture": True,
            "receipt": {
                "customer": {"email": f"user{user_id}@temp.com"},
                "items": [{
                    "description": f"VPN подписка на {months} месяцев",
                    "quantity": "1.00",
                    "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                    "vat_code": "2",
                    "payment_mode": "full_prepayment",
                    "payment_subject": "service"
                }]
            },
            "receipt_registration": "succeeded"
        }
        
        headers = self.basic_auth()
        headers["Idempotence-Key"] = str(uid)
        
        log.info(f"Создание платежа ЮKassa: {amount} RUB, {months} мес., user_id: {user_id}")
        
        try:
            async with aiohttp.ClientSession(headers=headers) as s:
                async with s.post(f"{YOOKASSA_API_URL}/payments", json=body) as r:
                    response_text = await r.text()
                    
                    if r.status != 200:
                        log.error(f"Ошибка создания платежа ЮKassa: статус {r.status}, ответ: {response_text}")
                        raise RuntimeError(f"YooKassa API error: {r.status} - {response_text}")
                    
                    j = await r.json()
                    
                    if "id" not in j or "confirmation" not in j:
                        log.error(f"Неполный ответ от ЮKassa: {j}")
                        raise RuntimeError("Incomplete response from YooKassa")
                    
                    payment_id = j["id"]
                    confirmation_url = j["confirmation"]["confirmation_url"]
                    
                    log.info(f"Платеж создан успешно: {payment_id}")
                    return payment_id, confirmation_url
                    
        except aiohttp.ClientError as e:
            log.error(f"Сетевая ошибка при создании платежа ЮKassa: {e}")
            raise RuntimeError(f"Network error: {e}")
        except Exception as e:
            log.error(f"Неожиданная ошибка при создании платежа ЮKassa: {e}")
            raise

    async def status(self, payment_id: str):
        log.info(f"Проверка статуса платежа: {payment_id}")
        
        try:
            async with aiohttp.ClientSession(headers=self.basic_auth()) as s:
                async with s.get(f"{YOOKASSA_API_URL}/payments/{payment_id}") as r:
                    response_text = await r.text()
                    
                    if r.status != 200:
                        log.error(f"Ошибка проверки статуса платежа: статус {r.status}, ответ: {response_text}")
                        raise RuntimeError(f"YooKassa API error: {r.status} - {response_text}")
                    
                    j = await r.json()
                    
                    if "status" not in j or "amount" not in j:
                        log.error(f"Неполный ответ от ЮKassa при проверке статуса: {j}")
                        raise RuntimeError("Incomplete response from YooKassa")
                    
                    status = j["status"]
                    amount = float(j["amount"]["value"])
                    
                    log.info(f"Статус платежа {payment_id}: {status}, сумма: {amount}")
                    return status, amount
                    
        except aiohttp.ClientError as e:
            log.error(f"Сетевая ошибка при проверке статуса платежа: {e}")
            raise RuntimeError(f"Network error: {e}")
        except Exception as e:
            log.error(f"Неожиданная ошибка при проверке статуса платежа: {e}")
            raise
