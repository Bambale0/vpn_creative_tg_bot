#!/usr/bin/env python3
"""
WireGuard VPN Bot (aiogram 3.x)
Вся работа ведётся из каталога /root/newvpn
"""
import os
import ssl
import sqlite3
import asyncio
import logging
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web
from yookassa import Configuration, Payment
import qrcode  # ← теперь точно импортирован

# ------------------------------------------------------------------
# 0. Пути относительно каталога скрипта
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "data", "subscriptions.db")
SSL_CERT = os.path.join(BASE_DIR, "ssl", "cert.pem")
SSL_KEY  = os.path.join(BASE_DIR, "ssl", "key.pem")

# ------------------------------------------------------------------
# 1. Конфигурация
# ------------------------------------------------------------------
try:
    from config.config import *
except ImportError as e:
    raise SystemExit("config/config.py не найден!") from e

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("vpnbot")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ------------------------------------------------------------------
# 2. База данных
# ------------------------------------------------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS subscriptions(
                sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                payment_id TEXT UNIQUE,
                duration INTEGER
            );
            CREATE TABLE IF NOT EXISTS wireguard_configs(
                config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                private_key TEXT,
                public_key TEXT,
                address TEXT
            );
        """)
init_db()

# ------------------------------------------------------------------
# 3. WireGuard helpers
# ------------------------------------------------------------------
WG_EXEC = "/usr/bin/wg"
WG_QUICK_EXEC = "/usr/bin/wg-quick"

def run(cmd, input_text=None):
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()

def register_peer(pubkey, ip):
    try:
        subprocess.run([WG_EXEC, "set", "wg0", "peer", pubkey, "allowed-ips", ip], check=True)
        subprocess.run([WG_QUICK_EXEC, "save", "wg0"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        log.error("WG error: %s", e)
        return False

def generate_wg_config(user_id):
    priv = run([WG_EXEC, "genkey"])
    pub = run([WG_EXEC, "pubkey"], input_text=priv)

    # Синхронизируем настройки с остальным кодом
    server_ip = os.getenv("SERVER_IP", "195.245.239.171")
    server_public_key = os.getenv("SERVER_PUBLIC_KEY", "2+TcrDqudxEA6qFGaB9UoZ6wLxLKA0n8M/XL9fEWdR8=")
    wg_port = int(os.getenv("WG_PORT", "51820"))
    wg_dns = os.getenv("WG_DNS", "94.140.15.15, 94.140.14.14")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(config_id),0) FROM wireguard_configs")
        last = cur.fetchone()[0]
        ip_last = (last % 250) + 2
        address = f"10.0.0.{ip_last}"

        config = f"""[Interface]
PrivateKey = {priv}
Address = {address}/32
DNS = {wg_dns}

[Peer]
PublicKey = {server_public_key}
AllowedIPs = 0.0.0.0/0
Endpoint = {server_ip}:{wg_port}
PersistentKeepalive = 20
"""

        if not register_peer(pub, address):
            raise RuntimeError("failed to add peer")

        conn.execute(
            "INSERT OR REPLACE INTO wireguard_configs(user_id,private_key,public_key,address) "
            "VALUES(?,?,?,?)",
            (user_id, priv, pub, address)
        )
        conn.commit()
    return config

# ------------------------------------------------------------------
# 4. Утилиты
# ------------------------------------------------------------------
def check_subscription(uid):
    """Проверка подписки с учетом администраторов (у них вечная подписка)"""
    # Администраторы всегда имеют премиум подписку
    if uid in ADMIN_IDS:
        return True

    # Для обычных пользователей проверяем только активные подписки
    # (истекшие подписки не считаются)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT end_date FROM subscriptions WHERE user_id=? AND end_date > datetime('now') ORDER BY end_date DESC LIMIT 1",
            (uid,)
        )
        row = cur.fetchone()
    return bool(row)
def main_menu():
    b = InlineKeyboardBuilder()
    b.row(types.InlineKeyboardButton(text="📅 1 мес – 200₽", callback_data="pay_1"))
    b.row(types.InlineKeyboardButton(text="📅 3 мес – 540₽", callback_data="pay_3"))
    b.row(types.InlineKeyboardButton(text="📅 12 мес – 2000₽", callback_data="pay_12"))
    b.row(
        types.InlineKeyboardButton(text="📊 Моя подписка", callback_data="my_subscription"),
        types.InlineKeyboardButton(text="⚡ Получить конфиг", callback_data="get_config")
    )
    b.row(types.InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"))
    return b.as_markup()

def payment_menu(url):
    b = InlineKeyboardBuilder()
    b.row(types.InlineKeyboardButton(text="💳 Перейти к оплате", url=url))
    b.row(types.InlineKeyboardButton(text="✅ Я оплатил", callback_data="check_payment"))
    return b.as_markup()

def admin_kb():
    b = InlineKeyboardBuilder()
    b.row(
        types.InlineKeyboardButton(text="🔑 Получить VPN", callback_data="admin_getvpn"),
        types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
    )
    return b.as_markup()

# ------------------------------------------------------------------
# 6. Хэндлеры
# ------------------------------------------------------------------
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id,username,full_name) VALUES(?,?,?)",
            (uid, message.from_user.username, message.from_user.full_name)
        )
    if uid in ADMIN_IDS:
        await message.answer("⚡ Админ-панель активна", reply_markup=types.ReplyKeyboardRemove())
        await message.answer("👑 Выберите действие:", reply_markup=admin_kb())
    else:
        await message.answer("🔒 Добро пожаловать!\n👇 Выберите действие:", reply_markup=main_menu())

@dp.callback_query(F.data.in_({"pay_1", "pay_3", "pay_12"}))
async def cb_pay(callback: types.CallbackQuery):
    duration = int(callback.data.split("_")[1])
    price = {1: 150, 3: 400, 12: 1500}[duration]
    desc = f"VPN {duration} мес"
    payment = Payment.create({
        "amount": {"value": f"{price}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": f"https://t.me/{(await bot.me()).username}"},
        "capture": True,
        "description": desc,
        "metadata": {"user_id": callback.from_user.id, "duration": duration}
    })
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO subscriptions(user_id,payment_id,duration) VALUES(?,?,?)",
            (callback.from_user.id, payment.id, duration)
        )
    await callback.message.edit_text(
        f"💳 Оплатите {price}₽",
        reply_markup=payment_menu(payment.confirmation.confirmation_url)
    )

@dp.callback_query(F.data == "check_payment")
async def cb_check_payment(callback: types.CallbackQuery):
    uid = callback.from_user.id
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT payment_id FROM subscriptions WHERE user_id=? ORDER BY sub_id DESC LIMIT 1",
            (uid,)
        )
        row = cur.fetchone()
    if not row:
        return await callback.answer("❌ Платёж не найден", show_alert=True)
    payment = Payment.find_one(row[0])
    if payment.status == "succeeded":
        await callback.message.edit_text("🎉 Платёж подтверждён! Подписка активирована.")
    else:
        await callback.answer("⏳ Платёж обрабатывается", show_alert=True)

# Обработчик get_config теперь в handlers/core/callback_handlers.py
# Здесь он закомментирован, чтобы избежать конфликта
# @dp.callback_query(F.data == "get_config")
# async def cb_get_config(callback: types.CallbackQuery):
#     # Логика перенесена в handlers/core/callback_handlers.py
#     pass

@dp.callback_query(F.data == "my_subscription")
async def cb_my_sub(callback: types.CallbackQuery):
    uid = callback.from_user.id
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT end_date FROM subscriptions WHERE user_id=? ORDER BY end_date DESC LIMIT 1",
            (uid,)
        )
        row = cur.fetchone()
    if row and datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        txt = f"✅ Подписка активна до {row[0].split('.')[0]} (UTC)"
    else:
        txt = "❌ Подписка неактивна"

    # Избегаем "message is not modified"
    try:
        await callback.message.edit_text(txt, reply_markup=main_menu())
    except TelegramBadRequest:
        await callback.answer("ℹ️ Информация не изменилась", show_alert=True)

@dp.callback_query(F.data == "admin_getvpn")
async def cb_admin_getvpn(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("🚫", show_alert=True)

    cfg = generate_wg_config(callback.from_user.id)
    if not cfg:
        return await callback.answer("❌ Ошибка генерации", show_alert=True)

    uid = callback.from_user.id

    # QR-код
    qr_path = f"/tmp/{uid}_vpn_{int(datetime.now().timestamp())}.png"
    qrcode.make(cfg).save(qr_path)
    await callback.message.answer_photo(
        FSInputFile(qr_path),
        caption="📲 Админ QR"
    )
    os.remove(qr_path)

    # .conf-файл
    conf_path = f"/tmp/{uid}_{int(datetime.now().timestamp())}.conf"
    with open(conf_path, "w") as f:
        f.write(cfg)
    await callback.message.answer_document(
        FSInputFile(conf_path),
        caption="🔑 Админ-конфиг"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("🚫", show_alert=True)
    await callback.answer("📊 Статистика – позже", show_alert=True)

@dp.callback_query(F.data == "support")
async def cb_support(callback: types.CallbackQuery):
    await callback.answer("🆘 Напишите @Chill_creative", show_alert=True)

# ------------------------------------------------------------------
# 7. Автоматическая очистка истекших подписок и отправка напоминаний
# ------------------------------------------------------------------
async def cleanup_expired_subscriptions():
    """Фоновая задача для автоматической очистки истекших подписок"""
    reminder_counter = 0  # Счетчик для отправки напоминаний реже очистки

    while True:
        try:
            # Импортируем функции
            from utils.wireguard import check_expired_subscriptions_and_remove_configs, send_subscription_reminders

            # Очистка всегда выполняется каждые 30 минут
            await check_expired_subscriptions_and_remove_configs()
            log.info("Automatic cleanup of expired subscriptions completed")

            # Напоминания отправляются каждые 2 часа (каждые 4 цикла по 30 минут)
            reminder_counter += 1
            if reminder_counter >= 4:
                await send_subscription_reminders()
                log.info("Subscription reminders sent")
                reminder_counter = 0

        except Exception as e:
            log.error(f"Error during automatic cleanup: {e}")

        # Запускаем цикл каждые 30 минут (1800 секунд)
        await asyncio.sleep(1800)

# ------------------------------------------------------------------
# 8. Webhook ЮKassa
# ------------------------------------------------------------------
async def start_webhook():
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(SSL_CERT, SSL_KEY)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8443, ssl_context=ssl_ctx)
    await site.start()
    log.info("Webhook started on 0.0.0.0:8443")

# ------------------------------------------------------------------
# 8. Zapusk
# ------------------------------------------------------------------
async def main():
    # Запускаем фоновую задачу очистки истекших подписок
    cleanup_task = asyncio.create_task(cleanup_expired_subscriptions())
    log.info("Background cleanup task started")

    await bot.delete_webhook()
    await start_webhook()
    await dp.start_polling(bot)

    # Останавливаем фоновую задачу при выходе
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        log.info("Background cleanup task stopped")

if __name__ == "__main__":
    asyncio.run(main())
