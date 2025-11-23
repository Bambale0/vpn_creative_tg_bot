import pytest
import os
import sys
import aiosqlite
from pathlib import Path

# Добавляем корневую директорию в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Тестовая конфигурация
os.environ["TEST_MODE"] = "true"
os.environ["DB_PATH"] = ":memory:"
os.environ["TELEGRAM_TOKEN"] = "test_token_123"
os.environ["ADMIN_IDS"] = "123456789"
os.environ["BOT_USERNAME"] = "test_bot"
os.environ["SERVER_IP"] = "10.0.0.1"
os.environ["SERVER_PUBLIC_KEY"] = "test_key_123"
os.environ["WEBHOOK_HOST"] = "http://test.com"
os.environ["YOOKASSA_SHOP_ID"] = "test_shop"
os.environ["YOOKASSA_SECRET_KEY"] = "test_secret"
os.environ["CRYPTO_PAY_TOKEN"] = "test_crypto_token"
os.environ["CRYPTO_PAY_WEBHOOK_SECRET"] = "test_webhook_secret"

@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для асинхронных тестов"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_connection():
    """Создает аиснхронное соединение с тестовой БД"""
    conn = await aiosqlite.connect(":memory:")

    # Создаем необходимые таблицы
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            lang TEXT DEFAULT 'ru'
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            end_date TEXT,
            status TEXT
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bonus_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            days INTEGER,
            message TEXT,
            created_at TEXT
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER NOT NULL,
            invited_id INTEGER NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS referral_bonuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER NOT NULL,
            referral_id INTEGER NOT NULL,
            bonus_days INTEGER NOT NULL,
            applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS referral_codes (
            user_id INTEGER PRIMARY KEY,
            referral_code TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await conn.commit()

    yield conn
    await conn.close()
