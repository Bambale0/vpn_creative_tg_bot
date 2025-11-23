# 🛡️ VPN Telegram Bot - Производственная версия

**Современный Telegram бот для управления VPN-подписками с геймификацией, реферальной системой и мониторингом**

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-orange.svg)](https://github.com/aiogram/aiogram)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ Особенности

### 🔐 Безопасность и производительность
- **Rate Limiting**: Защита от спама и DDoS (макс. 10 callback/sec на пользователя)
- **Connection Pooling**: Оптимизированное управление БД соединениями
- **SSL/TLS**: Полная защита вебхуков и веб-интерфейса

### 🎮 Геймификация
- Уровни и достижений системы
- Бонусные награды за активность
- Ежедневные бонусы Metro stations
- Таблица лидеров

### 💰 Платежные системы
- **YooKassa**: Банковские карты с PCI DSS защитой
- **CryptoPay**: Анонимная оплата криптовалютой
- Реферальная программа с бонусами

### 📊 Мониторинг и администрирование
- **Real-time мониторинг**: CPU, RAM, сеть, БД
- **Алерты**: Автоматические уведомления об ошибках
- **Веб-админка**: Полный контроль через REST API UI
- **Плагины**: Расширяемая архитектура с плагинами

### 🎯 WireGuard VPN
- **Быстрая настройка**: QR-коды и конфигурационные файлы
- **Преимущества WG**: Скорость, безопасность, энергоэффективность
- **Управление пользователями**: Создание/удаление профилей

## 📁 Структура проекта

```
vpnbot_consolidated/
├── handlers/              # Обработчики Telegram API
│   └── core/              # Чистые функции хендлеров
├── utils/                 # Вспомогательные модули
│   ├── plugins.py         # 🎯 Плагинная система с async поддержкой
│   ├── db_pool.py         # 🗄️ Пул соединений БД
│   ├── alerts.py          # 🚨 Система алертов
│   ├── menu.py            # 🎨 Генератор меню
│   └── game.py            # 🎮 game механики
├── plugins/               # 🔌 Плагины
│   ├── monitoring_plugin.py  # 📊 Системный мониторинг
│   └── bonus_plugin.py       # 🎁 Бонусная система
├── config/                # ⚙️ Конфигурация
│   ├── config.py          # Основные настройки
│   ├── dependencies.py    # Dependency injection
│   └── i18n/              # 🌍 i18n файлы
├── service_files/         # 🚀 Deployment
│   ├── vpnbot.service     # Systemd сервис
│   ├── start_webhook_bot.py  # Точка входа
│   └── webapp.py          # FastAPI веб-приложение
├── tests/                 # 🧪 Тесты
│   ├── unit/              # Юнит-тесты
│   ├── integration/       # Интеграционные тесты
│   └── conftest.py        # Текстовая конфигурация
├── docs/                  # 📖 Документация
├── static/                # 🎨 Static файлы
├── templates/             # 🎭 HTML templates
├── data/                  # 🗃️ Базы данных
├── logs/                  # 📝 Логи
├── ssl/                   # 🔐 SSL сертификаты
├── docker-compose.yml     # 🐳 Docker Compose
├── deploy.sh             # 🔧 Deployment скрипт
├── requirements.txt      # 📦 Python зависимости
└── .env                  # 🔑 Секреты (не коммитить)
```

## 🚀 Быстрый запуск

### 🐳 Docker Deployment (Рекомендуемый)

```bash
# Клонирование проекта
git clone <repo> && cd vpnbot_consolidated

# Настройка переменных
cp .env.example .env
nano .env  # Введите свои настройки

# Запуск всех сервисов
./deploy.sh start

# Проверка статуса
./deploy.sh status

# Просмотр логов
./deploy.sh logs
```

### 🈸 Ручное развертывание

```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Настройка окружения
cp .env.example .env
nano .env

# 3. Установка сервиса
sudo cp service_files/vpnbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vpnbot.service
sudo systemctl start vpnbot.service
```

## 🔧 Конфигурация

### Основные переменные окружения (.env)

```bash
# Бот
TELEGRAM_TOKEN=your_bot_token
BOT_USERNAME=your_bot_username

# Базы данных
DB_PATH=data/vpn_bot.db

# Платежные системы
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret
CRYPTO_PAY_TOKEN=your_crypto_token

# Серверные настройки
WEBHOOK_HOST=https://your-domain.com
WEBAPP_PORT=8000

# Администраторы (Telegram user IDs)
ADMIN_IDS=123456789,987654321

# WireGuard
SERVER_IP=10.0.0.1
SERVER_PUBLIC_KEY=your_wg_public_key
```

### Nginx Proxy (рекомендуемый)

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # Webhook endpoints
    location /yookassa_webhook { proxy_pass http://backend; }
    location /crypto_pay_webhook { proxy_pass http://backend; }

    # Webapp
    location / { proxy_pass http://webapp; }
}
```

## 📊 Использование

### Пользователи
- `/start` - Начало работы с ботом
- Интуитивное меню с inline кнопками
- Поддержка триал-периода
- Автоматическое продление подписки

### Администраторы
- Веб-админка: `http://your-domain.com/admin/dashboard`
- Мониторинг системы в реальном времени
- Управление пользователями и подписками
- Просмотр статистики и алертов

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# Интеграционные тесты
pytest tests/integration/

# Тесты с покрытием
pytest --cov=utils --cov=plugins --cov-report=html
```

## 🔌 Разработка плагинов

Создание кастомного плагина:

```python
# plugins/custom_plugin.py
class Plugin:
    async def setup(self) -> bool:
        # Инициализация
        return True

    def teardown(self) -> None:
        # Cleanup
        pass

    # Ваша логика...
```

## 🔒 Безопасность

- **Input validation**: Все входные данные проверяются
- **SQL инъекции**: Использование parametrized queries
- **Rate limiting**: Защита от злоупотреблений
- **SSL/TLS**: Защищенные соединения
- **Secret management**: Переменные окружения

## 📈 Производительность

- **Async/await**: Полностью асинхронная архитектура
- **Connection pooling**: Оптимизация БД соединений
- **Caching**: Кэширование частых запросов
- **Monitoring**: Реальный мониторинг ресурсов

## 📞 Поддержка

### Документация
- `SERVICE_SETUP.md` - Детальные инструкции по настройке
- `docs/` - Техническая документация

### Алерты и логгирование
- **Логи**: `logs/` директория
- **Алерты**: Автоматические Telegram уведомления админам
- **Мониторинг**: Веб-интерфейс с реальными метриками

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE) файл.

## 🤝 contributing

1. Fork проект
2. Создать feature branch (`git checkout -b feature/amazing`)
3. Commit изменений (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing`)
5. Создать Pull Request

---

**Проект готов к продакшн использованию с полной системой алертов, мониторинга и автоматизированного развертывания.**
