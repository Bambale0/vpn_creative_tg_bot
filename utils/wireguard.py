"""
Модуль для работы с WireGuard конфигурациями
"""
import asyncio
import aiosqlite
import os
import qrcode
import io
from config.config import DB_PATH

# Константы WireGuard
WG_EXEC = "/usr/bin/wg"
WG_QUICK_EXEC = "/usr/bin/wg-quick"
SERVER_IP = os.getenv("SERVER_IP", "195.245.239.171")
SERVER_PUBLIC_KEY = os.getenv("SERVER_PUBLIC_KEY", "2+TcrDqudxEA6qFGaB9UoZ6wLxLKA0n8M/XL9fEWdR8=")
WG_PORT = int(os.getenv("WG_PORT", "51820"))
WG_DNS = os.getenv("WG_DNS", "94.140.15.15, 94.140.14.14")


async def generate_qr_code(config_text):
    """Генерация QR-кода из текста конфигурации WireGuard"""
    try:
        # Создаем QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(config_text)
        qr.make(fit=True)

        # Создаем изображение
        img = qr.make_image(fill_color="black", back_color="white")

        # Сохраняем в буфер
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        return buf
    except Exception as e:
        print(f"Ошибка генерации QR-кода: {e}")
        raise


async def run_async(cmd, input_text=None):
    """Асинхронный запуск команд"""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE if input_text else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate(
        input=input_text.encode() if input_text else None
    )

    if proc.returncode != 0:
        raise Exception(f"Command failed: {stderr.decode()}")

    return stdout.decode().strip()


async def generate_wg_config(user_id):
    """Генерация конфигурации WireGuard с лимитом 3 на пользователя"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute("BEGIN")

            # Проверяем количество существующих конфигов
            cur = await conn.execute(
                "SELECT COUNT(*) FROM wireguard_configs WHERE user_id = ?",
                (user_id,)
            )
            config_count = (await cur.fetchone())[0]

            if config_count >= 3:
                raise Exception("Превышен лимит конфигураций (максимум 3 на пользователя)")

            # Проверяем существующий конфиг для обновления
            cur = await conn.execute(
                "SELECT config_id, private_key, public_key, address FROM wireguard_configs WHERE user_id = ? LIMIT 1",
                (user_id,)
            )
            existing_config = await cur.fetchone()

            if existing_config:
                config_id, priv, pub, address = existing_config
                print(f"Обновляем конфиг для пользователя {user_id} с актуальными ключами")
                # Удаляем старый пир
                await run_async([WG_EXEC, "set", "wg0", "peer", pub, "remove"])
                # Генерируем новый приватный ключ
                priv = await run_async([WG_EXEC, "genkey"])
                pub = await run_async([WG_EXEC, "pubkey"], input_text=priv)
                # Добавляем новый пир
                await run_async([WG_EXEC, "set", "wg0", "peer", pub, "allowed-ips", address])
                await run_async([WG_QUICK_EXEC, "save", "wg0"])
                # Обновляем в базе
                await conn.execute(
                    "UPDATE wireguard_configs SET private_key = ?, public_key = ? WHERE config_id = ?",
                    (priv, pub, config_id)
                )
            else:
                # Генерируем новый конфиг
                cur = await conn.execute(
                    "SELECT COALESCE(MAX(config_id), 0) FROM wireguard_configs"
                )
                result = await cur.fetchone()
                last = result[0] if result else 0
                ip_last = (last % 250) + 2
                address = f"10.0.0.{ip_last}"

                priv = await run_async([WG_EXEC, "genkey"])
                pub = await run_async([WG_EXEC, "pubkey"], input_text=priv)

                # Добавляем пир в WireGuard
                await run_async([WG_EXEC, "set", "wg0", "peer", pub, "allowed-ips", address])
                await run_async([WG_QUICK_EXEC, "save", "wg0"])

                await conn.execute(
                    "INSERT INTO wireguard_configs (user_id, private_key, public_key, address) VALUES (?, ?, ?, ?)",
                    (user_id, priv, pub, address)
                )
                print(f"Создан новый конфиг для пользователя {user_id}")

            await conn.commit()

            # Формируем конфиг для пользователя
            config = f"""[Interface]
PrivateKey = {priv}
Address = {address}/32
DNS = {WG_DNS}

[Peer]
PublicKey = {SERVER_PUBLIC_KEY}
AllowedIPs = 0.0.0.0/0
Endpoint = {SERVER_IP}:{WG_PORT}
PersistentKeepalive = 20
"""
            return config
    except Exception as e:
        print(f"Ошибка генерации конфига: {e}")
        raise


async def remove_wg_peer(public_key):
    """Удаление WireGuard пира по публичному ключу"""
    try:
        await run_async([WG_EXEC, "set", "wg0", "peer", public_key, "remove"])
        await run_async([WG_QUICK_EXEC, "save", "wg0"])
        print(f"Удален WireGuard пир с ключом: {public_key}")
    except Exception as e:
        print(f"Ошибка удаления WireGuard пира {public_key}: {e}")


async def check_expired_subscriptions_and_remove_configs():
    """Проверка истекших подписок и удаление неактивных конфигов (кроме администраторов)"""
    try:
        from config.config import ADMIN_IDS

        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute("BEGIN")

            # Находим пользователей с истекшими подписками (включая триалы), исключая админов
            cursor = await conn.execute("""
                SELECT DISTINCT s.user_id, wc.public_key
                FROM subscriptions s
                LEFT JOIN wireguard_configs wc ON s.user_id = wc.user_id
                WHERE s.end_date < datetime('now') AND wc.public_key IS NOT NULL
                AND s.user_id NOT IN ({})
            """.format(','.join('?' * len(ADMIN_IDS))), ADMIN_IDS)

            expired_users = await cursor.fetchall()

            # Также проверяем пользователей, которые использовали trial, но у них нет активных подписок
            # Исключаем админов и тех, кто имеет активные подписки
            cursor = await conn.execute("""
                SELECT DISTINCT ta.user_id, wc.public_key
                FROM trial_activations ta
                LEFT JOIN wireguard_configs wc ON ta.user_id = wc.user_id
                LEFT JOIN subscriptions s ON ta.user_id = s.user_id AND s.end_date > datetime('now')
                WHERE wc.public_key IS NOT NULL AND s.user_id IS NULL
                AND ta.user_id NOT IN ({})
            """.format(','.join('?' * len(ADMIN_IDS))), ADMIN_IDS)

            expired_trial_users = await cursor.fetchall()

            # Объединяем списки пользователей для удаления
            users_to_remove = {user_id: pub_key for user_id, pub_key in expired_users}
            for user_id, pub_key in expired_trial_users:
                if user_id not in users_to_remove:
                    users_to_remove[user_id] = pub_key

            if not users_to_remove:
                print("Нет истекших подписок для очистки")
                return

            print(f"Найдено {len(users_to_remove)} пользователей с истекшими подписками")

            # Удаляем WireGuard пиры и конфиги из базы
            for user_id, public_key in users_to_remove.items():
                if public_key:
                    try:
                        # Удаляем пир из WireGuard
                        await remove_wg_peer(public_key)

                        # Удаляем запись из базы данных
                        await conn.execute(
                            "DELETE FROM wireguard_configs WHERE user_id = ?",
                            (user_id,)
                        )

                        print(f"Удален конфиг для пользователя {user_id}")

                    except Exception as e:
                        print(f"Ошибка удаления конфига пользователя {user_id}: {e}")
                        continue

            await conn.commit()
            print(f"Очистка завершена. Удалено конфигов: {len(users_to_remove)}")

    except Exception as e:
        print(f"Ошибка при проверке и удалении истекших подписок: {e}")
        raise


async def get_active_users_count():
    """Получить количество пользователей с активными подписками"""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute("""
                SELECT COUNT(DISTINCT user_id) FROM subscriptions
                WHERE end_date > datetime('now')
            """)
            result = await cursor.fetchone()
            return result[0] if result else 0
    except Exception as e:
        print(f"Ошибка получения количества активных пользователей: {e}")
        return 0
