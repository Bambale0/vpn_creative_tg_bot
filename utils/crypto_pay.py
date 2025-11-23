import json, hmac, hashlib, aiohttp, logging, asyncio
from config.config import CRYPTO_PAY_WEBHOOK_SECRET  # 128-битный ключ для HMAC
from .payments import finish_crypto_payment
log = logging.getLogger("cryptopay")


class CryptoPay:
    URL = "https://pay.crypt.bot/api"
    
    def __init__(self, token: str):
        self.token = token
        self.exchange_rates = {}
        self.last_update = None
        self.update_task = None

    async def start_exchange_rate_updater(self, interval_minutes: int=30):
        """Запускает автоматическое обновление курсов валют"""
        if self.update_task:
            self.update_task.cancel()
        
        async def update_rates():
            while True:
                try:
                    await self.update_exchange_rates()
                    log.info("Курсы валют Crypto Pay обновлены")
                    await asyncio.sleep(interval_minutes * 60)
                except Exception as e:
                    log.error(f"Ошибка обновления курсов: {e}")
                    await asyncio.sleep(60)  # Пауза при ошибке
        
        self.update_task = asyncio.create_task(update_rates())

    async def stop_exchange_rate_updater(self):
        """Останавливает автоматическое обновление курсов"""
        if self.update_task:
            self.update_task.cancel()
            self.update_task = None

    async def update_exchange_rates(self):
        """Обновляет курсы валют"""
        try:
            rates = await self.request("GET", "getExchangeRates")
            log.info(f"Получены курсы от API: {rates}")
            if rates:
                self.exchange_rates = {}
                for rate in rates:
                    key = f"{rate['source']}_{rate['target']}"
                    self.exchange_rates[key] = {
                        'rate': float(rate['rate']),
                        'is_valid': rate['is_valid']
                    }
                self.last_update = asyncio.get_event_loop().time()
                log.info(f"Обновлены курсы валют: {list(self.exchange_rates.keys())}")
                return True
        except Exception as e:
            log.error(f"Ошибка получения курсов валют: {e}")
        return False

    async def get_exchange_rate(self, source: str, target: str) -> float:
        """Получает текущий курс обмена"""
        # API возвращает курсы в формате USDT_RUB, BTC_RUB и т.д.
        # Это означает: 1 USDT = X RUB, 1 BTC = Y RUB и т.д.
        
        # Если запрашиваем курс RUB -> крипто, нам нужен обратный курс
        if source == "RUB" and target in ["USDT", "BTC", "ETH", "TON"]:
            # Получаем прямой курс крипто -> RUB
            key = f"{target}_RUB"
            if key in self.exchange_rates:
                direct_rate = self.exchange_rates[key]['rate']
                # Обратный курс: 1 RUB = 1 / direct_rate крипто
                return 1.0 / direct_rate
        elif source in ["USDT", "BTC", "ETH", "TON"] and target == "RUB":
            # Прямой курс крипто -> RUB
            key = f"{source}_RUB"
            return self.exchange_rates.get(key, {}).get('rate', 1.0)
        else:
            # Для других пар используем стандартный формат
            key = f"{source}_{target}"
        
        # Если курсы устарели или отсутствуют, обновляем
        if (not self.exchange_rates or 
            not self.last_update or 
            asyncio.get_event_loop().time() - self.last_update > 3600):  # 1 час
            await self.update_exchange_rates()
        
        rate = self.exchange_rates.get(key, {}).get('rate', 1.0)
        log.info(f"Курс {key}: {rate}")
        return rate

    async def convert_amount(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Конвертирует сумму между валютами"""
        if from_currency == to_currency:
            return amount
            
        rate = await self.get_exchange_rate(from_currency, to_currency)
        
        # Для конвертации из фиатной валюты (RUB) в криптовалюту нужно делить на курс
        # API возвращает курсы в формате USDT_RUB, BTC_RUB и т.д., поэтому используем обратный курс
        if from_currency == "RUB" and to_currency in ["USDT", "BTC", "ETH", "TON"]:
            result = amount / rate
            log.info(f"Конвертация: {amount} {from_currency} -> {result} {to_currency} (курс: {rate})")
            return result
        else:
            # Для других случаев (обратная конвертация) используем умножение
            result = amount * rate
            log.info(f"Конвертация: {amount} {from_currency} -> {result} {to_currency} (курс: {rate})")
            return result

    async def request(self, method: str, path: str, **body):
        async with aiohttp.ClientSession() as s:
            async with s.request(
                method,
                f"{self.URL}/{path}",
                json=body,
                headers={"Crypto-Pay-API-Token": self.token}
            ) as r:
                data = await r.json()
                if data.get("ok"):
                    return data["result"]
                raise RuntimeError(data.get("error"))

    async def create_invoice(self, amount: float, asset: str, desc: str, user_id: int):
        invoice = await self.request(
            "POST",
            "createInvoice",
            asset=asset,
            amount=str(amount),
            description=desc,
            payload=str(user_id),
            expires_in=900,
        )
        return invoice

    async def check_invoice(self, inv_id: str):
        invoices = await self.request("GET", f"getInvoices?invoice_ids={inv_id}")
        if invoices.get("items"):
            return invoices["items"][0]
        return None

    async def create_invoice_with_auto_rate(self, amount_rub: float, asset: str, description: str, user_id: int):
        """Создает инвойс с автоматическим расчетом суммы в криптовалюте"""
        try:
            # Используем исходную сумму без наценки
            log.info(f"Сумма для конвертации: {amount_rub} RUB")
            
            # Получаем текущий курс (сколько RUB за 1 единицу криптовалюты)
            exchange_rate = await self.get_exchange_rate(asset, "RUB")
            log.info(f"Курс для создания инвойса: 1 {asset} = {exchange_rate} RUB")
            
            # Рассчитываем сумму в криптовалюте: amount_rub / курс
            crypto_amount = amount_rub / exchange_rate
            
            # Округляем до нужного количества знаков в зависимости от валюты
            precision = {
                "USDT": 2,
                "BTC": 8,
                "ETH": 6,
                "TON": 2
            }.get(asset, 6)
            
            crypto_amount = round(crypto_amount, precision)
            
            log.info(f"Создание инвойса: {amount_rub:.2f} RUB -> {crypto_amount} {asset} (курс: {exchange_rate})")
            
            # Создаем инвойс
            invoice = await self.request(
                "POST",
                "createInvoice",
                asset=asset,
                amount=str(crypto_amount),
                description=description,
                payload=str(user_id),
                expires_in=900,
            )
            
            return invoice
            
        except Exception as e:
            log.error(f"Ошибка создания инвойса с авто-курсом: {e}")
            # Fallback: создаем инвойс с фиксированной суммой (старый метод)
            return await self.create_invoice(amount_rub, asset, description, user_id)


def sign_hook(body: bytes, secret: bytes) -> str:
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


async def handle_crypto_webhook(request, bot, db_path: str):
    secret = CRYPTO_PAY_WEBHOOK_SECRET.encode()
    sig_header = request.headers.get("Crypto-Pay-API-Signature")
    body = await request.read()

    if not sig_header or not hmac.compare_digest(
        sign_hook(body, secret), sig_header
    ):
        return 401, "Unauthorized"

    data = json.loads(body)
    if data.get("event") != "invoice_paid":
        return 200, "ok"

    invoice = data["payload"]["invoice"]
    user_id = int(invoice["payload"]) if invoice["payload"].isdigit() else None
    if not user_id:
        return 200, "ok"

    amount = float(invoice["amount"])
    await finish_crypto_payment(
        user_id, invoice["invoice_id"], amount, bot, db_path
    )
    return 200, "ok"
