#!/usr/bin/env python3
"""
Модуль конфигурации для VPN Telegram Bot
Централизованное управление конфигурацией с переменными окружения
"""

import os
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# ------------------------------------------------------------------
# БАЗОВЫЕ ПУТИ И ДИРЕКТОРИИ
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent

# Переопределяем базовую директорию через переменную окружения для сервисов
SERVICE_MODE = os.getenv("SERVICE_MODE", "false").lower() == "true"

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
I18N_DIR = CONFIG_DIR / "i18n"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SSL_DIR = BASE_DIR / "ssl"
CLIENTS_DIR = BASE_DIR / "clients"
LOGS_DIR = BASE_DIR / "logs"

# Создание необходимых директорий
for directory in [DATA_DIR, STATIC_DIR, SSL_DIR, CLIENTS_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# ------------------------------------------------------------------
# КОНФИГУРАЦИЯ TELEGRAM BOT
# ------------------------------------------------------------------
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_IDS: List[int] = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")

# ------------------------------------------------------------------
# КОНФИГУРАЦИЯ СЕРВЕРА
# ------------------------------------------------------------------
SERVER_IP: str = os.getenv("SERVER_IP", "195.245.239.171")
SERVER_PUBLIC_KEY: str = os.getenv("SERVER_PUBLIC_KEY", "2+TcrDqudxEA6qFGaB9UoZ6wLxLKA0n8M/XL9fEWdR8=")
WG_PORT: int = int(os.getenv("WG_PORT", "51820"))
WG_INTERFACE: str = os.getenv("WG_INTERFACE", "wg0")

# ------------------------------------------------------------------
# КОНФИГУРАЦИЯ БАЗЫ ДАННЫХ
# ------------------------------------------------------------------
DB_PATH: str = os.getenv("DB_PATH", str(DATA_DIR / "subscriptions.db"))
DB_BACKUP_PATH: str = os.getenv("DB_BACKUP_PATH", str(DATA_DIR / "subscriptions.db.backup"))

# ------------------------------------------------------------------
# КОНФИГУРАЦИЯ WEBHOOK И WEB
# ------------------------------------------------------------------
WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "")
WEBHOOK_PATH: str = f"/webhook/{TELEGRAM_TOKEN.split(':')[1]}" if TELEGRAM_TOKEN and ':' in TELEGRAM_TOKEN else "/webhook"
WEBHOOK_URL: str = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")

# YooKassa webhook configuration
YOOKASSA_WEBHOOK_URL: str = os.getenv("YOOKASSA_WEBHOOK_URL", f"{WEBHOOK_HOST}/yookassa_webhook" if WEBHOOK_HOST else "")

WEBAPP_HOST: str = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT: int = int(os.getenv("WEBAPP_PORT", "8000"))
WEBAPP_DOMAIN: str = os.getenv("WEBAPP_DOMAIN", "")

# ------------------------------------------------------------------
# SSL/TLS КОНФИГУРАЦИЯ
# ------------------------------------------------------------------
SSL_CERT_PATH: str = os.getenv("SSL_CERT_PATH", str(SSL_DIR / "cert.pem"))
SSL_KEY_PATH: str = os.getenv("SSL_KEY_PATH", str(SSL_DIR / "key.pem"))
SSL_ENABLED: bool = os.getenv("SSL_ENABLED", "false").lower() == "true"

# ------------------------------------------------------------------
# КОНФИГУРАЦИЯ ПЛАТЕЖЕЙ
# ------------------------------------------------------------------
# Crypto Pay
CRYPTO_PAY_TOKEN: str = os.getenv("CRYPTO_PAY_TOKEN", "")
CRYPTO_PAY_API_URL: str = "https://pay.crypt.bot/api"
CRYPTO_PAY_WEBHOOK_SECRET: str = os.getenv("CRYPTO_PAY_WEBHOOK_SECRET", "")

# YooKassa
YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_API_URL: str = "https://api.yookassa.ru/v3"

# Настройки платежей
PAYMENT_CURRENCY: str = os.getenv("PAYMENT_CURRENCY", "RUB")
PAYMENT_TIMEOUT: int = int(os.getenv("PAYMENT_TIMEOUT", "900"))  # 15 минут

# ------------------------------------------------------------------
# КОНФИГУРАЦИЯ ГЕЙМИФИКАЦИИ
# ------------------------------------------------------------------
# Настройки пробного периода
TRIAL_DAYS: int = int(os.getenv("TRIAL_DAYS", "10"))
TRIAL_ENABLED: bool = os.getenv("TRIAL_ENABLED", "true").lower() == "true"

# Система рефералов
REFERRAL_BONUS_FIRST: int = int(os.getenv("REFERRAL_BONUS_FIRST", "10"))
REFERRAL_BONUS_SUBSEQUENT: int = int(os.getenv("REFERRAL_BONUS_SUBSEQUENT", "5"))
REFERRAL_ENABLED: bool = os.getenv("REFERRAL_ENABLED", "true").lower() == "true"

# Ежедневный бонус
DAILY_BONUS_MIN: int = int(os.getenv("DAILY_BONUS_MIN", "1"))
DAILY_BONUS_MAX: int = int(os.getenv("DAILY_BONUS_MAX", "3"))
DAILY_BONUS_ENABLED: bool = os.getenv("DAILY_BONUS_ENABLED", "true").lower() == "true"

# Система уровней
LEVEL_UP_POINTS: int = int(os.getenv("LEVEL_UP_POINTS", "100"))
LEVEL_REWARD_DAYS: int = int(os.getenv("LEVEL_REWARD_DAYS", "2"))

# Достижения
ACHIEVEMENTS: Dict[str, Dict[str, Any]] = {
    "first_purchase": {
        "name": "Первая покупка",
        "reward": 5,
        "description": "За первую покупку подписки"
    },
    "invite_3_friends": {
        "name": "Социальная бабочка",
        "reward": 10,
        "description": "Пригласить 3 друзей"
    },
    "year_subscription": {
        "name": "Годовой абонемент",
        "reward": 15,
        "description": "Купить годовую подписку"
    },
    "vip_member": {
        "name": "VIP-статус",
        "reward": 20,
        "description": "Достичь 5 уровня"
    },
    "daily_streak_7": {
        "name": "Недельная серия",
        "reward": 5,
        "description": "7 дней подряд заходить за бонусом"
    },
    "daily_streak_30": {
        "name": "Месячная серия",
        "reward": 15,
        "description": "30 дней подряд заходить за бонусом"
    }
}

# ------------------------------------------------------------------
# ПЛАНЫ ПОДПИСКИ
# ------------------------------------------------------------------
SUBSCRIPTION_PLANS: Dict[str, Dict[str, Any]] = {
    "1_month": {
        "duration_days": 30,
        "price_rub": 200,
        "discount_percent": 0,
        "description": "1 месяц"
    },
    "3_months": {
        "duration_days": 90,
        "price_rub": 540,
        "discount_percent": 10,
        "description": "3 месяца (скидка 10%)"
    },
    "12_months": {
        "duration_days": 360,
        "price_rub": 2000,
        "discount_percent": 17,
        "description": "12 месяцев (скидка 17%)"
    }
}

# ------------------------------------------------------------------
# КОНФИГУРАЦИЯ WIREGUARD
# ------------------------------------------------------------------
WG_EXEC: str = os.getenv("WG_EXEC", "/usr/bin/wg")
WG_QUICK_EXEC: str = os.getenv("WG_QUICK_EXEC", "/usr/bin/wg-quick")
WG_CONFIG_PATH: str = os.getenv("WG_CONFIG_PATH", f"/etc/wireguard/{WG_INTERFACE}.conf")
WG_SUBNET: str = os.getenv("WG_SUBNET", "10.13.13.0/24")
WG_DNS: str = os.getenv("WG_DNS", "1.1.1.1, 8.8.8.8")
WG_MTU: int = int(os.getenv("WG_MTU", "1420"))
WG_KEEPALIVE: int = int(os.getenv("WG_KEEPALIVE", "25"))

# ------------------------------------------------------------------
# КОНФИГУРАЦИЯ ЛОГИРОВАНИЯ
# ------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOG_FILE: str = os.getenv("LOG_FILE", str(LOGS_DIR / "bot.log"))
LOG_MAX_SIZE: int = int(os.getenv("LOG_MAX_SIZE", "10485760"))  # 10MB
LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# ------------------------------------------------------------------
# МОНИТОРИНГ И ОБСЛУЖИВАНИЕ
# ------------------------------------------------------------------
CLEANUP_INTERVAL: int = int(os.getenv("CLEANUP_INTERVAL", "3600"))  # 1 час
BACKUP_INTERVAL: int = int(os.getenv("BACKUP_INTERVAL", "86400"))  # 24 часа
MONITORING_ENABLED: bool = os.getenv("MONITORING_ENABLED", "true").lower() == "true"

# ------------------------------------------------------------------
# ВНЕШНИЕ СЕРВИСЫ
# ------------------------------------------------------------------
INSTRUCTIONS_IMAGE_URL: str = os.getenv(
    "INSTRUCTIONS_IMAGE_URL",
    "https://raw.githubusercontent.com/chiicreative/vpn-bot-ui/main/images/setup_instructions.png"
)
TELEGRAM_API_URL: str = "https://api.telegram.org"

# ------------------------------------------------------------------
# НАСТРОЙКИ БЕЗОПАСНОСТИ
# ------------------------------------------------------------------
MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOGIN_TIMEOUT: int = int(os.getenv("LOGIN_TIMEOUT", "300"))  # 5 минут
SESSION_TIMEOUT: int = int(os.getenv("SESSION_TIMEOUT", "86400"))  # 24 часа
WEBHOOK_SECRET_KEY: str = os.getenv("WEBHOOK_SECRET_KEY", "")

# ------------------------------------------------------------------
# ФЛАГИ ФУНКЦИЙ
# ------------------------------------------------------------------
FEATURES: Dict[str, bool] = {
    "webhook_mode": WEBHOOK_URL != "",
    "ssl_enabled": SSL_ENABLED,
    "trial_enabled": TRIAL_ENABLED,
    "referral_system": REFERRAL_ENABLED,
    "daily_bonus": DAILY_BONUS_ENABLED,
    "achievements": True,
    "qr_codes": True,
    "multi_language": True,
    "admin_panel": True,
    "crypto_payments": CRYPTO_PAY_TOKEN != "",
    "yookassa_payments": YOOKASSA_SHOP_ID != "",
    "monitoring": MONITORING_ENABLED,
    "backup_system": True,
    "cleanup_system": True
}


# ------------------------------------------------------------------
# ФУНКЦИИ ВАЛИДАЦИИ
# ------------------------------------------------------------------
def validate_config() -> List[str]:
    """Валидирует конфигурацию и возвращает список ошибок"""
    errors = []
    
    # Обязательные поля
    required_fields = [
        ("TELEGRAM_TOKEN", TELEGRAM_TOKEN),
        ("SERVER_IP", SERVER_IP),
        ("SERVER_PUBLIC_KEY", SERVER_PUBLIC_KEY),
    ]
    
    for field_name, field_value in required_fields:
        if not field_value:
            errors.append(f"Обязательное поле {field_name} не сконфигурировано")
    
    # Валидировать ID администраторов
    if not ADMIN_IDS:
        errors.append("Не настроены ID администраторов в ADMIN_IDS")
    
    # Валидировать токены платежей
    if not CRYPTO_PAY_TOKEN and not YOOKASSA_SHOP_ID:
        errors.append("Должен быть сконфигурирован хотя бы один метод платежа")
    
    # Валидировать конфигурацию вебхука
    if FEATURES["webhook_mode"] and not WEBHOOK_SECRET:
        errors.append("Секрет вебхука обязателен в режиме вебхука")
    
    return errors


def get_config_summary() -> Dict[str, Any]:
    """Возвращает сводку текущей конфигурации"""
    return {
        "bot_configured": bool(TELEGRAM_TOKEN),
        "webhook_mode": FEATURES["webhook_mode"],
        "payment_methods": {
            "crypto": FEATURES["crypto_payments"],
            "yookassa": FEATURES["yookassa_payments"]
        },
        "gamification": {
            "trial": FEATURES["trial_enabled"],
            "referral": FEATURES["referral_system"],
            "daily_bonus": FEATURES["daily_bonus"],
            "achievements": FEATURES["achievements"]
        },
        "subscription_plans": list(SUBSCRIPTION_PLANS.keys()),
        "admin_count": len(ADMIN_IDS),
        "features": FEATURES
    }


# ------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Валидировать конфигурацию при импорте
    config_errors = validate_config()
    if config_errors:
        print("Обнаружены ошибки конфигурации:")
        for error in config_errors:
            print(f"  - {error}")
        print("\nПожалуйста, проверьте ваш .env файл и конфигурацию.")
    else:
        print("Конфигурация успешно валидирована!")
        print(f"Сводка конфигурации: {get_config_summary()}")
