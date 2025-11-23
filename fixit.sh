#!/usr/bin/env bash
# ===========================================
# VPN Bot Production Fixer
# Maintainer: AI System
# Version: 2.1.0
# ===========================================

set -euo pipefail
IFS=$'\n\t'

# ========== CONFIGURATION ==========
SCRIPT_DIR="/root/newvpnbot"
LOG_DIR="/var/log/vpn"
PID_FILE="/var/run/vpn-bot.pid"
BACKUP_DIR="/root/backup/vpn/$(date +%Y%m%d-%H%M%S)"
PYTHON_EXEC="/usr/bin/python3"
MIN_FREE_SPACE_MB=100

# ========== COLOR CODES ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ========== LOGGING ==========
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_DIR/fix.log"
}

error() {
    echo -e "${RED}[ERROR $(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_DIR/fix.log"
}

warning() {
    echo -e "${YELLOW}[WARNING $(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_DIR/fix.log"
}

# ========== SAFETY CHECKS ==========
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Этот скрипт должен запускаться от root"
        exit 1
    fi
}

check_disk_space() {
    local available=$(df "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    if [[ $((available / 1024)) -lt $MIN_FREE_SPACE_MB ]]; then
        error "Недостаточно места на диске. Требуется минимум ${MIN_FREE_SPACE_MB}MB"
        exit 1
    fi
}

# ========== BACKUP ==========
create_backup() {
    log "Создание резервной копии..."
    mkdir -p "$BACKUP_DIR"

    # Копируем важные файлы
    cp -r "$SCRIPT_DIR" "$BACKUP_DIR/" 2>/dev/null || true

    # Создаем дамп БД
    if [[ -f "$SCRIPT_DIR/data/subscriptions.db" ]]; then
        sqlite3 "$SCRIPT_DIR/data/subscriptions.db" .dump > "$BACKUP_DIR/subscriptions.sql"
    fi

    # Архивируем
    tar -czf "${BACKUP_DIR}.tar.gz" -C "$BACKUP_DIR" .
    rm -rf "$BACKUP_DIR"

    log "Резервная копия создана: ${BACKUP_DIR}.tar.gz"
}

# ========== DEPENDENCY CHECK ==========
install_dependencies() {
    log "Проверка зависимостей..."

    # Проверка Python и pip
    if ! command -v python3 &> /dev/null; then
        apt update && apt install -y python3 python3-pip
    fi

    # Проверка зависимостей Python
    local required_packages=("aiogram" "qrcode" "sqlite3" "logging")
    for package in "${required_packages[@]}"; do
        if ! $PYTHON_EXEC -c "import $package" 2>/dev/null; then
            log "Установка $package..."
            pip3 install "$package"
        fi
    done

    # Проверка WireGuard
    if ! command -v wg &> /dev/null; then
        log "Установка WireGuard..."
        apt update && apt install -y wireguard qrencode
    fi

    # Проверка Telegram Bot API
    if ! curl -s -I https://api.telegram.org &> /dev/null; then
        error "Нет доступа к Telegram API"
        exit 1
    fi
}

# ========== CODE FIXES ==========
fix_wireguard_bot() {
    log "Исправление codebase..."

    cd "$SCRIPT_DIR"

    # Бекап бота
    cp bot.py bot.py.backup.$(date +%s)

    # Фиксы в коде
    cat > bot.py << 'EOF'
#!/usr/bin/env python3
import asyncio
import sqlite3
import os
import logging
from datetime import datetime, timezone
from config.config import DB_PATH, ADMIN_IDS, bot, dp
from handlers.callback import setup_handlers
from utils.wg import generate_wg_config
from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart, Command

logging.basicConfig(level=logging.INFO, filename="vpnbot.log",
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

async def check_subscription(user_id: int) -> bool:
    """Проверка активной подписки"""
    if user_id in ADMIN_IDS:
        return True

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT end_date FROM subscriptions WHERE user_id=? ORDER BY end_date DESC LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()

    if row and datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        return True
    return False

@dp.message(CommandStart())
async def cmd_start(message: Message):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💳 Моя подписка", callback_data="my_subscription")],
        [types.InlineKeyboardButton(text="📱 Получить VPN", callback_data="get_config")],
    ])

    if message.from_user.id in ADMIN_IDS:
        kb.inline_keyboard.append([
            types.InlineKeyboardButton(text="🔧 Админка", callback_data="admin_panel")
        ])

    await message.answer(
        f"🚀 Привет! Бот для получения WireGuard конфигов.\n"
        f"Ваш ID: <code>{message.from_user.id}</code>",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(lambda cb: cb.data == "my_subscription")
async def cb_my_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_active = await check_subscription(user_id)

    if is_active:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT end_date FROM subscriptions WHERE user_id=? ORDER BY end_date DESC LIMIT 1", (user_id,))
            row = cur.fetchone()
            if row:
                end_date = datetime.fromisoformat(row[0]).strftime("%d.%m.%Y")
                msg = f"✅ Подписка активна до {end_date}"
            else:
                msg = "🔑 Админ-доступ без ограничений"
    else:
        msg = "❌ Подписка неактивна"

    await callback.message.answer(msg)
    await callback.answer()

@dp.callback_query(lambda cb: cb.data == "get_config" and check_subscription(cb.from_user.id))
async def cb_get_config(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    try:
        cfg = generate_wg_config(user_id)
        if not cfg:
            raise ValueError("Invalid config generated")

        # Save config
        conf_file = f"/tmp/wg_{user_id}.conf"
        with open(conf_file, "w") as f:
            f.write(cfg)

        # Generate QR
        import qrcode
        qr = qrcode.make(cfg)
        qr_file = f"/tmp/wg_{user_id}.png"
        qr.save(qr_file)

        await callback.message.answer_photo(
            FSInputFile(qr_file),
            caption="📲 QR-код для быстрой настройки"
        )

        await callback.message.answer_document(
            FSInputFile(conf_file),
            caption="📥 Файл конфигурации WireGuard"
        )

        os.remove(qr_file)
        os.remove(conf_file)

    except Exception as e:
        log.error(f"Config error for {user_id}: {e}")
        await callback.message.answer("❌ Ошибка генерации конфигурации")
    finally:
        await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
EOF

    log "WireGuard Bot обновлён"
}

# ========== MONITORING ==========
setup_monitoring() {
    log "Настройка мониторинга..."

    # Создаем мониторинг скрипт
    cat > "$SCRIPT_DIR/monitor.sh" << 'EOF'
#!/bin/bash
PID_FILE="/var/run/wg-bot.pid"
LOG="/var/log/vpn/monitor.log"
SCRIPT_DIR="/root/newvpn"

if [[ ! -f $PID_FILE ]] || [[ ! -d /proc/$(cat $PID_FILE) ]]; then
    echo "[$(date)] Bot not running, restarting..." >> $LOG

    cd "$SCRIPT_DIR"
    nohup python3 bot.py >> server.log 2>&1 &
    echo $! > $PID_FILE

    echo "[$(date)] Bot restarted" >> $LOG
fi
EOF

    chmod +x "$SCRIPT_DIR/monitor.sh"

    # Добавляем в cron
    (crontab -l 2>/dev/null; echo "*/1 * * * * $SCRIPT_DIR/monitor.sh") | crontab -

    log "Мониторинг установлен"
}

# ========== SYSTEMD SERVICE ==========
setup_systemd() {
    log "Создание systemd service..."

    cat > /etc/systemd/system/vpn-bot.service << EOF
[Unit]
Description=VPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_EXEC bot.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
Environment=PYTHONPATH=$SCRIPT_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable vpn-bot.service

    log "Systemd service создан"
}

# ========== MAIN EXECUTION ==========
main() {
    log "🚀 Начинаем полное восстановление VPN Bot"

    check_root
    check_disk_space

    mkdir -p "$LOG_DIR"

    # Шаги восстановления
    install_dependencies
    create_backup
    fix_wireguard_bot
    setup_monitoring
    setup_systemd

    # Перезапускаем сервис
    log "Перезапускаем сервис..."
    systemctl stop vpn-bot.service 2>/dev/null || true
    sleep 2
    systemctl start vpn-bot.service

    # Проверка статуса
    if systemctl is-active vpn-bot.service >/dev/null; then
        log "✅ VPN Bot успешно запущен"
        systemctl status vpn-bot.service --no-pager
    else
        error "❌ Ошибка запуска сервиса"
        systemctl status vpn-bot.service --no-pager
        exit 1
    fi

    log "🏁 Восстановление завершено успешно!"
    echo -e "\n${GREEN}Useful commands:${NC}"
    echo "  systemctl status vpn-bot.service"
    echo "  journalctl -u vpn-bot.service -f"
    echo "  tail -f $LOG_DIR/fix.log"
}

# ========== DETAILED HELP ==========
help() {
    cat << EOF
Usage: $0 [OPTIONS]

OPTIONS:
    --help      Показать эту справку
    --only-bug  Только исправить код бота
    --backup    Создать резервную копию
    --status    Показать статус
    --restart   Перезапустить только сервис

EXAMPLES:
    $0                  # Полное восстановление
    $0 --only-bug       # Быстрая починка кода
    $0 --status         # Проверка состояния
EOF
}

# ========== ARGUMENT HANDLING ==========
case "${1:-}" in
    --help)
        help
        ;;
    --only-bug)
        fix_wireguard_bot
        ;;
    --backup)
        create_backup
        ;;
    --status)
        systemctl status vpn-bot.service
        ;;
    --restart)
        systemctl restart vpn-bot.service
        ;;
    *)
        main
        ;;
esac