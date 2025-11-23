#!/bin/bash

# VPN Bot Deployment Script
# Использование: ./deploy.sh [command]
# Commands:
#   start     - Запустить все сервисы
#   stop      - Остановить все сервисы
#   restart   - Перезапустить все сервисы
#   status    - Проверить статус сервисов
#   logs      - Показать логи сервисов
#   update    - Обновить образы и перезапустить
#   cleanup   - Очистить неиспользуемые образы и контейнеры

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка наличия docker и docker-compose
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен. Установите Docker."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose не установлен. Установите docker-compose."
        exit 1
    fi
}

# Проверка наличия .env файла
check_env() {
    if [ ! -f .env ]; then
        log_warning ".env файл не найден. Создаю шаблон..."
        cat > .env << EOF
# Основные настройки
TELEGRAM_TOKEN=your_telegram_token_here
WEBHOOK_HOST=https://your-domain.com
ADMIN_IDS=123456789

# Платежные системы
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
CRYPTO_PAY_TOKEN=your_crypto_token
CRYPTO_PAY_WEBHOOK_SECRET=your_webhook_secret

# WireGuard настройки
SERVER_IP=10.0.0.1
SERVER_PUBLIC_KEY=your_public_key
WG_SERVER_PORT=51820
WG_PEERS_COUNT=100
WG_PEER_DNS=8.8.8.8
WG_INTERNAL_SUBNET=10.0.0.0/24

# Порты
WEBAPP_PORT=8000

# SSL настройки (если используете HTTPS)
SSL_CERT_PATH=/app/ssl/fullchain.pem
SSL_KEY_PATH=/app/ssl/privkey.pem
SSL_ENABLED=true
EOF
        log_error "Заполните .env файл с правильными значениями и запустите скрипт снова."
        exit 1
    fi
}

# Проверка наличия nginx.conf
check_nginx() {
    if [ ! -f nginx.conf ]; then
        log_warning "nginx.conf не найден. Создаю базовую конфигурацию..."
        cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server vpnbot:8001;
    }

    upstream webapp {
        server webapp:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;

        # Redirect to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # Yookassa webhooks
        location /yookassa_webhook {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Crypto Pay webhooks
        location /crypto_pay_webhook {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Webapp
        location / {
            proxy_pass http://webapp;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
EOF
        log_warning "Заполните nginx.conf правильными путями к SSL сертификатам."
    fi
}

# Создание необходимых директорий
create_directories() {
    log_info "Создание необходимых директорий..."
    mkdir -p data logs ssl
}

start_services() {
    log_info "Запуск сервисов..."
    docker-compose up -d --build
    log_success "Сервисы запущены"
}

stop_services() {
    log_info "Остановка сервисов..."
    docker-compose down
    log_success "Сервисы остановлены"
}

restart_services() {
    log_info "Перезапуск сервисов..."
    docker-compose restart
    log_success "Сервисы перезапущены"
}

status_services() {
    log_info "Статус сервисов:"
    docker-compose ps
}

logs_services() {
    docker-compose logs -f --tail=100
}

update_services() {
    log_info "Обновление сервисов..."
    docker-compose pull
    docker-compose up -d --build
    log_success "Сервисы обновлены"
}

cleanup() {
    log_info "Очистка неиспользуемых ресурсов..."
    docker system prune -f
    docker volume prune -f
    log_success "Очистка завершена"
}

main() {
    # Основной блок
    check_dependencies
    check_env
    check_nginx
    create_directories

    case "${1:-help}" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            status_services
            ;;
        logs)
            logs_services
            ;;
        update)
            update_services
            ;;
        cleanup)
            cleanup
            ;;
        help|*)
            echo "VPN Bot Deployment Script"
            echo ""
            echo "Использование: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  start     - Запустить все сервисы"
            echo "  stop      - Остановить все сервисы"
            echo "  restart   - Перезапустить все сервисы"
            echo "  status    - Проверить статус сервисов"
            echo "  logs      - Показать логи сервисов"
            echo "  update    - Обновить образы и перезапустить"
            echo "  cleanup   - Очистить неиспользуемые образы и контейнеры"
            echo "  help      - Показать эту справку"
            ;;
    esac
}

main "$@"
