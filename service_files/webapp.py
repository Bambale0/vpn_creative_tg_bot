import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
import bcrypt
import subprocess

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, '/root/vpnbot')

import aiosqlite
from fastapi import FastAPI, Request, Form, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
from handlers.webhook import process_yookassa_webhook
from config.dependencies import log, set_log_instance, get_bot_instance
# from utils.crypto_pay import handle_crypto_webhook
from config.config import WEBAPP_PORT, WEBAPP_HOST  # Импортируем из конфигурации

# Добавляем импорт DatabaseManager для оптимизации работы с БД
import sys
import os
sys.path.insert(0, '/root/vpnbot_consolidated')
from utils.database import db_manager

load_dotenv()

# Настройка логирования
import logging

logger = logging.getLogger('webapp')
logger.setLevel(logging.INFO)

# Создаем форматтер для логов
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Хендлер для файла
log_path = Path('/root/vpnbot/logs/webapp.log')
log_path.parent.mkdir(exist_ok=True)
file_handler = logging.FileHandler(log_path)
file_handler.setFormatter(formatter)

# Хендлер для консоли
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Добавляем хендлеры к логгеру
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Устанавливаем экземпляр логгера
set_log_instance(logger)

# Основные хендлеры для FastAPI
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/vpnbot/logs/webapp.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("webapp")
set_log_instance(logger)

# Import configuration from config module
# Fallback to environment variables if config module is not available
DB_PATH = os.getenv("DB_PATH", "/root/vpnbot/data/subscriptions.db")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "qwerty")
# Используем конфигурацию из config.py
# WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
# WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8000"))
SECRET_KEY = os.getenv("SECRET_KEY", "change_me")
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "86400"))
SSL_ENABLED = os.getenv("SSL_ENABLED", "false").lower() == "true"

# ---------- инициализация ----------
app = FastAPI(docs_url=None, redoc_url=None)
BASE_DIR = Path('/root/vpnbot')
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
static = BASE_DIR / "static"
static.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static), name="static")


# ---------- БД ----------
# Используем DatabaseManager вместо прямых подключений
class DB:

    @staticmethod
    async def fetch(sql: str, *args, one=False):
        async with db_manager.get_connection() as conn:
            async with conn.execute(sql, args) as cur:
                rows = await cur.fetchall()
                return rows[0] if one and rows else rows

    @staticmethod
    async def execute(sql: str, *args):
        async with db_manager.get_connection() as conn:
            await conn.execute(sql, args)
            await conn.commit()


# ---------- авторизация ----------
COOKIE_NAME = "session"
SESSIONS: Dict[str, datetime] = {}  # {sid: expires}


def hash_pass(p):
    """Безопасное хеширование пароля с помощью bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(p.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password, hashed_password):
    """Проверка пароля"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def new_session() -> str:
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {
        'expires': datetime.utcnow() + timedelta(hours=24),
        'created': datetime.utcnow()
    }
    return sid


def delete_session(sid: str): SESSIONS.pop(sid, None)


async def get_admin(request: Request) -> str:
    sid = request.cookies.get(COOKIE_NAME)
    if (not sid or 
        sid not in SESSIONS or 
        SESSIONS[sid]['expires'] < datetime.utcnow()):
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return sid  # возвращаем sid – он же «user»


# ---------- страницы ----------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    # Автоматическая проверка истекших подписок при health check
    try:
        from utils.wireguard import check_expired_subscriptions_and_remove_configs, get_active_users_count
        await check_expired_subscriptions_and_remove_configs()
        active_users = await get_active_users_count()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        active_users = 0

    return {
        "status": "healthy",
        "service": "vpn_admin_panel",
        "timestamp": datetime.now().isoformat(),
        "active_users": active_users
    }


@app.get("/admin/api/metrics/system")
async def get_system_metrics(admin=Depends(get_admin)):
    metrics = await DB.fetch("""
        SELECT timestamp, cpu_usage, memory_usage, disk_usage, 
               network_in, network_out 
        FROM system_metrics 
        ORDER BY timestamp DESC LIMIT 1440
    """)
    return {"metrics": metrics}


@app.get("/admin/api/metrics/vpn")
async def get_vpn_metrics(admin=Depends(get_admin)):
    metrics = await DB.fetch("""
        SELECT timestamp, active_connections, bandwidth_usage,
               peer_id, latency 
        FROM vpn_metrics 
        ORDER BY timestamp DESC LIMIT 1440
    """)
    return {"metrics": metrics}


@app.get("/admin/api/users/stats")
async def get_user_stats(admin=Depends(get_admin)):
    stats = await DB.fetch("""
        SELECT 
            COUNT(*) as total_users,
            SUM(CASE WHEN EXISTS (
                SELECT 1 FROM subscriptions s 
                WHERE s.user_id = u.user_id 
                AND s.end_date > datetime('now')
            ) THEN 1 ELSE 0 END) as active_users,
            SUM(CASE WHEN join_date > datetime('now', '-7 days') 
                THEN 1 ELSE 0 END) as new_users_7d
        FROM users u
    """, one=True)
    return stats


# ---------- auth ----------
@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.post("/admin/login")
async def admin_login(request: Request, username: str=Form(...), password: str=Form(...)):
    """Обработка логина администратора"""
    if username == ADMIN_USER and password == ADMIN_PASS:
        response = RedirectResponse(url="/admin/dashboard", status_code=302)
        session_id = new_session()
        response.set_cookie(COOKIE_NAME, session_id, max_age=SESSION_TIMEOUT)
        return response
    else:
        return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Неверно"})


@app.post("/admin/logout")
async def logout(admin=Depends(get_admin)):
    delete_session(admin)
    response = RedirectResponse("/admin/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ---------- ADMIN JSON-API ----------
class DaysIn(BaseModel): days: int


# общая статистика
@app.get("/admin/api/stats")
async def stats(admin=Depends(get_admin)):
    try:
        total_users = await DB.fetch("SELECT COUNT(*) FROM users", one=True)
        active_subs = await DB.fetch("SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE end_date>datetime('now')", one=True)
        yookassa = await DB.fetch("SELECT COALESCE(SUM(amount),0) FROM yookassa_payments WHERE status='paid'", one=True)
        crypto = await DB.fetch("SELECT COALESCE(SUM(amount_fiat),0) FROM crypto_invoices WHERE status='paid'", one=True)
        
        return {
            "total_users": total_users[0] if total_users else 0,
            "active_subs": active_subs[0] if active_subs else 0,
            "income": {
                "yookassa": float(yookassa[0]) if yookassa else 0,
                "crypto": float(crypto[0]) if crypto else 0
            }
        }
    except Exception as e:
        log().error(f"Error getting stats: {e}")
        return {
            "total_users": 0,
            "active_subs": 0,
            "income": {"yookassa": 0, "crypto": 0}
        }


# Управление пользователями и подписками
@app.get("/admin/api/users")
async def users_list(page: int=1, per: int=50, admin=Depends(get_admin)):
    off = (page - 1) * per
    rows = await DB.fetch("""
        SELECT 
            u.user_id, u.username, u.full_name, u.join_date,
            MAX(s.end_date) as sub_end,
            COUNT(DISTINCT wc.config_id) as configs_count,
            SUM(CASE WHEN p.status = 'paid' THEN p.amount ELSE 0 END) as total_paid
        FROM users u
        LEFT JOIN subscriptions s ON u.user_id = s.user_id
        LEFT JOIN wireguard_configs wc ON u.user_id = wc.user_id
        LEFT JOIN yookassa_payments p ON u.user_id = p.user_id
        GROUP BY u.user_id
        ORDER BY u.join_date DESC
        LIMIT ? OFFSET ?
    """, (per, off))
    
    total = await DB.fetch("SELECT COUNT(*) FROM users", one=True)
    
    return {
        "users": rows,
        "total": total[0] if total else 0,
        "pages": (total[0] + per - 1) // per if total else 0
    }


@app.post("/admin/api/users/{user_id}/ban")
async def ban_user(user_id: int, admin=Depends(get_admin)):
    await DB.execute("""
        UPDATE users SET banned = 1 
        WHERE user_id = ?
    """, (user_id,))
    
    # Логируем действие админа
    await DB.execute("""
        INSERT INTO admin_actions (admin_id, action_type, target_id, details)
        VALUES (?, 'ban_user', ?, 'User banned')
    """, (admin, str(user_id)))
    
    return {"success": True}


@app.post("/admin/api/users/{user_id}/unban")
async def unban_user(user_id: int, admin=Depends(get_admin)):
    await DB.execute("""
        UPDATE users SET banned = 0 
        WHERE user_id = ?
    """, (user_id,))
    
    await DB.execute("""
        INSERT INTO admin_actions (admin_id, action_type, target_id, details)
        VALUES (?, 'unban_user', ?, 'User unbanned')
    """, (admin, str(user_id)))
    
    return {"success": True}


@app.post("/admin/api/users/{user_id}/subscription")
async def update_subscription(
    user_id: int,
    duration: int,
    admin=Depends(get_admin)
):
    # Добавляем или обновляем подписку
    await DB.execute("""
        INSERT INTO subscriptions (user_id, start_date, end_date)
        VALUES (?, datetime('now'), datetime('now', ?))
    """, (user_id, f'+{duration} months'))
    
    return {"success": True}


# удалить пользователя
@app.delete("/admin/api/users/{uid:int}")
async def user_delete(uid: int, admin=Depends(get_admin)):
    await DB.execute("DELETE FROM users WHERE user_id=?", uid)
    await DB.execute("DELETE FROM subscriptions WHERE user_id=?", uid)
    await DB.execute("DELETE FROM wireguard_configs WHERE user_id=?", uid)
    return {"ok": True}


# добавить дни подписки
@app.post("/admin/api/users/{uid:int}/add_days")
async def user_add_days(uid: int, body: DaysIn, admin=Depends(get_admin)):
    end_row = await DB.fetch("SELECT end_date FROM subscriptions WHERE user_id=? ORDER BY end_date DESC LIMIT 1", uid, one=True)
    if end_row and end_row[0]:
        new_end = datetime.fromisoformat(end_row[0]) + timedelta(days=body.days)
        await DB.execute("UPDATE subscriptions SET end_date=? WHERE user_id=? AND end_date=?", new_end.isoformat(), uid, end_row[0])
    else:
        new_end = datetime.utcnow() + timedelta(days=body.days)
        await DB.execute("""INSERT INTO subscriptions(user_id,start_date,end_date,payment_id,duration)
                            VALUES(?,datetime('now'),?,?,?)""",
                         uid, new_end.isoformat(), f"manual_{datetime.utcnow().timestamp()}", body.days)
    return {"ok": True, "new_end": new_end.isoformat()}


# ---------- System Management ----------
@app.post("/admin/api/system/restart/{service}")
async def restart_service(service: str, admin=Depends(get_admin)):
    """Restart system services (vpn or bot)"""
    try:
        if service == "vpn":
            # Restart WireGuard service
            result = subprocess.run(['systemctl', 'restart', 'wg-quick@wg0'],
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return {"success": True, "message": "WireGuard service restarted"}
            else:
                raise HTTPException(500, f"Failed to restart WireGuard: {result.stderr}")

        elif service == "bot":
            # Restart bot service
            result = subprocess.run(['systemctl', 'restart', 'vpnbot'],
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return {"success": True, "message": "Bot service restarted"}
            else:
                raise HTTPException(500, f"Failed to restart bot: {result.stderr}")
        else:
            raise HTTPException(400, "Invalid service. Use 'vpn' or 'bot'")

    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Service restart timeout")
    except Exception as e:
        log().error(f"Error restarting {service}: {e}")
        raise HTTPException(500, f"Error restarting {service}")


@app.post("/admin/api/system/cleanup_expired")
async def cleanup_expired_subscriptions(admin=Depends(get_admin)):
    """Очистка истекших подписок и конфигов вручную"""
    try:
        from utils.wireguard import check_expired_subscriptions_and_remove_configs, get_active_users_count

        await check_expired_subscriptions_and_remove_configs()
        active_users = await get_active_users_count()

        # Логируем действие админа
        await DB.execute("""
            INSERT INTO admin_actions (admin_id, action_type, target_id, details)
            VALUES (?, 'cleanup_expired', 'system', 'Cleanup expired subscriptions and configs')
        """, (admin,))

        return {
            "success": True,
            "message": "Очистка истекших подписок выполнена",
            "active_users": active_users
        }

    except Exception as e:
        logger.error(f"Error during manual cleanup: {e}")
        raise HTTPException(500, f"Ошибка очистки: {str(e)}")


# ---------- HTML-отчёты ----------
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, admin=Depends(get_admin)):
    try:
        # Получаем статистику для дашборда
        stats_data = await stats(admin)
        
        # Получаем последние активности
        try:
            recent_activities = await DB.fetch("""
                SELECT u.username, a.activity_type, a.value, a.created 
                FROM user_activities a 
                LEFT JOIN users u ON a.user_id = u.user_id 
                ORDER BY a.created DESC LIMIT 10
            """)
        except Exception as e:
            logger.error(f"Error getting activities: {e}")
            recent_activities = []
        
        total_income = float(stats_data["income"]["yookassa"]) + float(stats_data["income"]["crypto"])
        
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "total_users": int(stats_data["total_users"]),
            "paid_users": int(stats_data["active_subs"]),
            "trial_users": max(0, int(stats_data["total_users"]) - int(stats_data["active_subs"])),
            "total_income": total_income,
            "recent_activities": recent_activities
        })
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "error": "Произошла ошибка при загрузке данных",
            "total_users": 0,
            "paid_users": 0,
            "trial_users": 0,
            "total_income": 0,
            "recent_activities": []
        })


# ---------- Webhook обработчики ----------
@app.post("/yookassa_webhook")
async def yookassa_webhook(request: Request):
    """Обработчик вебхуков от ЮKassa"""
    try:
        data = await request.json()
        await process_yookassa_webhook(data)
        return {"status": "ok"}
    except Exception as e:
        log().error(f"YooKassa webhook error: {e}")
        return {"status": "error"}


@app.post("/crypto_pay_webhook")
async def crypto_pay_webhook(request: Request):
    """Обработчик вебхуков от Crypto Pay"""
    try:
        # Используем прямую обработку без зависимости от бота
        from utils.crypto_pay import sign_hook
        import json
        import hmac
        
        secret = os.getenv("CRYPTO_PAY_WEBHOOK_SECRET", "").encode()
        sig_header = request.headers.get("Crypto-Pay-API-Signature")
        body = await request.body()

        if not sig_header or not hmac.compare_digest(
            sign_hook(body, secret), sig_header
        ):
            return Response(content="Unauthorized", status_code=401)

        data = json.loads(body)
        if data.get("event") != "invoice_paid":
            return Response(content="ok", status_code=200)

        invoice = data["payload"]["invoice"]
        user_id = int(invoice["payload"]) if invoice["payload"].isdigit() else None
        if not user_id:
            return Response(content="ok", status_code=200)

        amount = float(invoice["amount"])
        
        # Обрабатываем платеж без отправки сообщений
        from utils.payments import amount_to_months
        
        months = amount_to_months(amount)
        end_date = (datetime.utcnow() + timedelta(days=30 * months)).isoformat()
        
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            # Обновляем статус инвойса
            await conn.execute(
                "UPDATE crypto_invoices SET status='paid' WHERE id=?",
                (invoice["invoice_id"],)
            )
            
            # Активируем подписку
            await conn.execute(
                """INSERT INTO subscriptions 
                (user_id, start_date, end_date, payment_id, duration) 
                VALUES (?, datetime('now'), ?, ?, ?)""",
                (user_id, end_date, f"crypto_{invoice['invoice_id']}", months)
            )
            
            await conn.commit()
        
        return Response(content="ok", status_code=200)
        
    except Exception as e:
        log().error(f"Crypto Pay webhook error: {e}")
        return {"status": "error"}


# Функция для добавления бонусных дней и отправки сообщения
async def add_bonus_days_and_send_message(uid: int, days: int, message_text: str):
    """Добавляет бонусные дни к подписке пользователя и отправляет сообщение"""
    try:
        # Отправляем сообщение
        bot = get_bot_instance()
        if bot:
            await bot.send_message(uid, message_text)
            log().info(f"Message sent to user {uid}: {message_text}")
        else:
            log().warning(f"Bot instance not available, message not sent to user {uid}")

        # Добавляем дни к подписке
        end_row = await DB.fetch("SELECT end_date FROM subscriptions WHERE user_id=? ORDER BY end_date DESC LIMIT 1", uid, one=True)
        if end_row and end_row[0]:
            new_end = datetime.fromisoformat(end_row[0]) + timedelta(days=days)
            await DB.execute("UPDATE subscriptions SET end_date=? WHERE user_id=? AND end_date=?", new_end.isoformat(), uid, end_row[0])
            log().info(f"Extended subscription for user {uid} by {days} days, new end: {new_end.isoformat()}")
        else:
            new_end = datetime.utcnow() + timedelta(days=days)
            await DB.execute("""INSERT INTO subscriptions(user_id,start_date,end_date,payment_id,duration)
                                VALUES(?,datetime('now'),?,?,?)""",
                             uid, new_end.isoformat(), f"bonus_{datetime.utcnow().timestamp()}", days)
            log().info(f"Created new subscription for user {uid} with {days} days, end: {new_end.isoformat()}")

        return {"success": True, "new_end": new_end.isoformat()}

    except Exception as e:
        log().error(f"Error adding bonus days and sending message to user {uid}: {e}")
        return {"success": False, "error": str(e)}


# API endpoints для bonus_plugin
@app.post("/admin/api/bonus/give")
async def give_bonus_endpoint(
    user_id: int,
    days: int,
    custom_message: str = "",
    admin=Depends(get_admin)
):
    """Выдача бонуса пользователю через плагин"""
    try:
        from utils.plugins import give_user_bonus

        result = await give_user_bonus(user_id, days, custom_message)

        # Логируем действие админа
        await DB.execute("""
            INSERT INTO admin_actions (admin_id, action_type, target_id, details)
            VALUES (?, 'give_bonus', ?, ?)
        """, (admin, str(user_id), f"Gave {days} bonus days"))

        return result

    except Exception as e:
        log().error(f"Error giving bonus: {e}")
        return {"success": False, "error": str(e)}


@app.get("/admin/api/bonus/stats")
async def bonus_stats_endpoint(admin=Depends(get_admin)):
    """Получение статистики бонусов"""
    try:
        from utils.plugins import get_bonus_statistics

        stats = await get_bonus_statistics()
        return stats

    except Exception as e:
        log().error(f"Error getting bonus stats: {e}")
        return {"success": False, "error": str(e)}


@app.get("/admin/api/bonus/info")
async def bonus_info_endpoint(admin=Depends(get_admin)):
    """Информация о bonus плагине"""
    try:
        from utils.plugins import get_bonus_plugin_info

        info = get_bonus_plugin_info()
        return info

    except Exception as e:
        log().error(f"Error getting bonus plugin info: {e}")
        return {"success": False, "error": str(e)}


# ---------- RUN ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webapp:app", host=WEBAPP_HOST, port=WEBAPP_PORT, reload=False)
