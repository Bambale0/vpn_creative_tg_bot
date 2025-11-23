#!/usr/bin/env python3
"""
Скрипт для запуска Telegram бота на вебхуках
"""

import asyncio
import ssl
import logging
import os
import sys
import time

# Добавляем корневую директорию проекта в путь Python
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from datetime import datetime

# Импорт функций перевода и зависимостей
import aiosqlite

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/webhook-service.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("webhook_bot")

# Импорт зависимостей
from utils.yookassa_pay import YooPay
from utils.crypto_pay import CryptoPay
from config.dependencies import (
    set_bot_instance, set_log_instance, set_t_instance,
    set_dp_instance, set_yookassa_instance, set_crypto_pay_instance
)


# Функции перевода и логирования
async def get_user_lang(uid: int) -> str:
    """Получает язык пользователя из БД"""
    from config.config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute("SELECT lang FROM users WHERE user_id=?", (uid,))
        row = await cur.fetchone()
        return row[0] if row else "ru"


async def t(uid: int, key: str, **kwargs) -> str:
    """Возвращает переведённую строку"""
    from config.config import I18N_DIR
    import yaml
    
    # Загружаем языковые файлы
    langs = {}
    for lang_file in os.listdir(I18N_DIR):
        if lang_file.endswith('.yaml'):
            lang_code = lang_file.split('.')[0]
            with open(os.path.join(I18N_DIR, lang_file), 'r', encoding='utf-8') as f:
                langs[lang_code] = yaml.safe_load(f)
    
    lang = await get_user_lang(uid)
    text = langs.get(lang, langs.get("en", {})).get(key, key)
    
    if kwargs:
        try:
            text = text.format(**{k: str(v) for k, v in kwargs.items()})
        except (KeyError, ValueError):
            logger.warning(f"Ошибка форматирования для ключа '{key}' на языке '{lang}'")
    
    return text


# Функция логирования
log = logger


async def on_startup(bot: Bot, base_url: str):
    """Действия при запуске бота"""
    logger.info("Бот запускается на вебхуках...")
    
    # Настраиваем вебхук URL
    webhook_path = f"/webhook/{os.getenv('WEBHOOK_SECRET')}"
    webhook_url = f"{base_url}{webhook_path}"
    
    # Установка вебхука
    await bot.set_webhook(
        url=webhook_url,
        certificate=FSInputFile("fullchain.pem") if base_url.startswith("https") else None
    )
    logger.info(f"Вебхук установлен: {webhook_url}")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Бот останавливается...")

    # Останавливаем автоматическое обновление курсов
    from config.dependencies import get_crypto_pay_instance
    crypto_pay = get_crypto_pay_instance()
    if crypto_pay:
        # await crypto_pay.stop_exchange_rate_updater()
        logger.info("Автоматическое обновление курсов остановлено (метод недоступен)")

    # Закрываем соединения БД
    try:
        from utils.db_pool import close_db_connections
        await close_db_connections()
        logger.info("Соединения БД закрыты")
    except Exception as e:
        logger.error(f"Ошибка при закрытии соединений БД: {e}")

    # Удаление вебхука
    await bot.delete_webhook()
    logger.info("Вебхук удален")


async def cleanup_expired_subscriptions():
    """Фоновая задача для очистки истекших подписок"""
    from config.config import DB_PATH
    while True:
        try:
            async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
                # Помечаем истекшие подписки как неактивные
                await conn.execute(
                    "UPDATE subscriptions SET active = 0 WHERE end_date < datetime('now') AND active = 1"
                )
                await conn.commit()
                
                # Логируем количество очищенных подписок
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM subscriptions WHERE end_date < datetime('now') AND active = 0"
                )
                expired_count = (await cursor.fetchone())[0]
                
                if expired_count > 0:
                    logger.info(f"Очищено {expired_count} истекших подписок")
                    
        except Exception as e:
            logger.error(f"Ошибка при очистке истекших подписок: {e}")
        
        # Запускаем каждые 6 часов
        await asyncio.sleep(6 * 60 * 60)


async def cleanup_old_logs():
    """Фоновая задача для очистки старых логов"""
    while True:
        try:
            # Удаляем логи старше 30 дней
            import glob
            
            log_dir = "logs"
            if os.path.exists(log_dir):
                for log_file in glob.glob(os.path.join(log_dir, "*.log")):
                    if os.path.getmtime(log_file) < time.time() - 30 * 24 * 60 * 60:
                        os.remove(log_file)
                        logger.info(f"Удален старый лог файл: {log_file}")
                        
        except Exception as e:
            logger.error(f"Ошибка при очистке старых логов: {e}")
        
        # Запускаем раз в сутки
        await asyncio.sleep(24 * 60 * 60)


async def main():
    """Основная функция запуска вебхук бота"""
    try:
        # Инициализация зависимостей
        from config.config import CRYPTO_PAY_TOKEN
        
        # Инициализируем платежные системы
        yookassa = YooPay()
        set_yookassa_instance(yookassa)
        
        crypto_pay = CryptoPay(CRYPTO_PAY_TOKEN)
        set_crypto_pay_instance(crypto_pay)
        
        # Запускаем автоматическое обновление курсов валют
        # await crypto_pay.start_exchange_rate_updater(interval_minutes=30)
        logger.info("Автоматическое обновление курсов Crypto Pay пропущено (метод недоступен)")

        # Импортируем конфигурацию
        from config.config import TELEGRAM_TOKEN, WEBHOOK_HOST
        from config.config import SSL_CERT_PATH, SSL_KEY_PATH, SSL_ENABLED
        from config.config import WEBHOOK_SECRET, WEBAPP_PORT  # Добавляем недостающие импорты

        # Используем порт 8001 для вебхук бота (nginx проксирует сюда)
        WEBHOOK_BOT_PORT = 8001

        # Проверяем обязательные переменные
        if not TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN не установлен")
        
        # Создаем бота и диспетчер
        bot = Bot(token=TELEGRAM_TOKEN)
        dp = Dispatcher()
        
        # Устанавливаем глобальные зависимости
        set_bot_instance(bot)
        set_log_instance(logger)
        set_dp_instance(dp)
        set_t_instance(t)
        
        # Базовая проверка доступности сервера
        try:
            bot_info = await bot.get_me()
            logger.info(f"Бот @{bot_info.username} готов к работе")
        except Exception as e:
            logger.error(f"Ошибка подключения к Telegram: {e}")
            return
        
        # Настраиваем вебхук URL
        base_url = WEBHOOK_HOST.rstrip('/')
        webhook_path = f"/webhook/{WEBHOOK_SECRET}"
        webhook_url = f"{base_url}{webhook_path}"
        
        logger.info(f"Webhook URL: {webhook_url}")
        logger.info(f"Webapp порт: {WEBAPP_PORT}")
        logger.info(f"Webhook bot порт: {WEBHOOK_BOT_PORT}")
        
        # Инициализация плагинов
        try:
            from utils.plugins import aasetup_plugins
            loaded_plugins = await aasetup_plugins()
            logger.info(f"✅ Загружено {loaded_plugins} плагинов")
        except ImportError:
            logger.info("Плагины не найдены, пропускаем инициализацию плагинов")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки плагинов: {e}")

        # Инициализация реферальной системы
        try:
            from utils.game import init_referral_system
            await init_referral_system()
            logger.info("✅ Реферальная система инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации реферальной системы: {e}")

        # Регистрируем обработчики
        # Импорты нужны для регистрации хендлеров
        import handlers.command  # noqa: F401
        import handlers.callback  # noqa: F401
        import handlers.payment  # noqa: F401
        import handlers.registration  # noqa: F401
        import handlers.webhook  # noqa: F401
        
        # Вызываем функции регистрации обработчиков
        from handlers.command import register_command_handlers
        from handlers.callback import register_callback_handlers
        from handlers.payment import register_payment_handlers
        from handlers.registration import register_all_handlers
        from handlers.webhook import register_webhook_handlers
        
        register_command_handlers(dp)
        register_callback_handlers(dp)
        register_payment_handlers(dp)
        register_all_handlers(dp)
        register_webhook_handlers(dp)
        
        # Регистрируем обработчики вебхуков
        from handlers.webhook import (
            yookassa_webhook_handler,
            crypto_pay_webhook_handler
        )
        
        # Создаем HTTP сервер
        app = web.Application()
        
        # Добавляем маршруты для вебхуков
        app.router.add_post('/yookassa_webhook', yookassa_webhook_handler)
        app.router.add_post('/crypto_pay_webhook', crypto_pay_webhook_handler)
        
        # Добавляем health check
        async def health_handler(request):
            return web.json_response({
                "status": "healthy",
                "service": "telegram_webhook_bot",
                "timestamp": datetime.now().isoformat()
            })
        
        app.router.add_get('/health', health_handler)
        app.router.add_get('/', health_handler)
        
        # Настраиваем обработчик вебхуков
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        
        webhook_requests_handler.register(app, path=webhook_path)
        
        # Настраиваем приложение
        setup_application(app, dp, bot=bot)

        # Пытемся установить webhook
        webhook_mode = False
        try:
            await on_startup(bot, base_url)
            webhook_mode = True
            logger.info("Webhook успешно установлен - режим вебхуков активен.")
        except Exception as e:
            logger.error(f"Не удалось установить webhook: {e}. Запуск в гибридном режиме.")

        # Настраиваем SSL если нужно
        ssl_context = None
        if base_url.startswith("https") and SSL_CERT_PATH and SSL_KEY_PATH and SSL_ENABLED:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(SSL_CERT_PATH, SSL_KEY_PATH)
            logger.info("SSL контекст создан")
        elif base_url.startswith("https") and not SSL_ENABLED:
            logger.warning("HTTPS URL указан, но SSL отключен в конфигурации")

        # Запускаем HTTP сервер всегда для вебхуков
        logger.info("Запуск HTTP сервера для обработки вебхуков...")

        # Если webhook не установлен, стартуем polling параллельно
        if not webhook_mode:
            logger.info("Запуск polling mode параллельно с HTTP сервером...")
            polling_task = asyncio.create_task(dp.start_polling(bot))

        # Запускаем HTTP сервер
        await web._run_app(
            app,
            host="0.0.0.0",
            port=WEBHOOK_BOT_PORT,  # Используем отдельный порт для вебхук бота
            ssl_context=ssl_context,
            print=lambda x: logger.info(f"HTTP: {x}")
        )
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        exit(1)
