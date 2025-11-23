"""
Система уведомлений и напоминаний для VPN бота
"""
import asyncio
import aiosqlite
from config.config import DB_PATH, ADMIN_IDS
from config.dependencies import log, get_bot_instance


async def send_subscription_reminders():
    """Отправка напоминаний пользователям об истечении подписки"""
    try:
        from datetime import datetime

        # Получаем бота для отправки сообщений
        bot = get_bot_instance()
        if not bot:
            print("Бот не инициализирован, пропускаем отправку напоминаний")
            return

        async with aiosqlite.connect(DB_PATH) as conn:
            # Находим пользователей, у которых подписка истечет через 1-7 дней
            cursor = await conn.execute("""
                SELECT DISTINCT s.user_id, s.end_date, s.is_trial,
                       JULIANDAY(s.end_date) - JULIANDAY('now') as days_remaining
                FROM subscriptions s
                WHERE s.end_date > datetime('now')
                AND s.end_date <= datetime('now', '+7 days')
                AND s.user_id NOT IN ({})
                ORDER BY days_remaining ASC
            """.format(','.join('?' * len(ADMIN_IDS))), ADMIN_IDS)

            expiring_subscriptions = await cursor.fetchall()

            sent_reminders = 0

            for user_id, end_date, is_trial, days_remaining in expiring_subscriptions:
                try:
                    days = int(days_remaining)
                    subscription_type = "Trial" if is_trial else "платная подписка"

                    # Настраиваем сообщение в зависимости от оставшихся дней
                    if days == 0:
                        # Истечение сегодня
                        message = f"⏰ <b>ВНИМАНИЕ!</b>\n\nВаша {subscription_type} истекает <b>СЕГОДНЯ</b>!\n\n❗ После истечения доступ к VPN будет заблокирован.\n\n🔄 <b>Рекомендуем продлить подписку заранее!</b>"
                    elif days == 1:
                        # Истечение завтра
                        message = f"⏰ <b>Напоминание</b>\n\nВаша {subscription_type} истечет <b>ЗАВТРА</b>!\n\n❗ Не забудьте продлить подписку, чтобы сохранить доступ к VPN."
                    elif days <= 3:
                        # Истечение через 2-3 дня
                        message = f"⏰ <b>Напоминание</b>\n\nВаша {subscription_type} истечет через <b>{days} дня</b>.\n\n💡 Рекомендуем продлить подписку заранее."
                    else:
                        # Истечение через 4-7 дней
                        message = f"ℹ️ <b>Информация</b>\n\nВаша {subscription_type} истечет через <b>{days} дней</b>.\n\n📅 Не забудьте вовремя продлить подписку."

                    # Добавляем призыв к действию
                    if is_trial:
                        message += "\n\n💳 Перейдите к платной подписке в главном меню!"
                    else:
                        message += "\n\n💳 Продлить подписку можно в главном меню!"

                    # Отправляем сообщение
                    await bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="HTML"
                    )

                    print(f"Отправлено напоминание пользователю {user_id}: подписка истечет через {days} дней")
                    sent_reminders += 1

                    # Небольшая задержка между сообщениями
                    await asyncio.sleep(0.1)

                except Exception as user_error:
                    print(f"Ошибка отправки напоминания пользователю {user_id}: {user_error}")
                    continue

            # Находим пользователей с уже истекшими подписками (для экстренных уведомлений)
            cursor = await conn.execute("""
                SELECT DISTINCT ta.user_id
                FROM trial_activations ta
                LEFT JOIN subscriptions s ON ta.user_id = s.user_id AND s.end_date > datetime('now')
                WHERE s.user_id IS NULL
                AND ta.user_id NOT IN ({})
                AND ta.user_id NOT IN (
                    SELECT user_id FROM wireguard_configs
                )
            """.format(','.join('?' * len(ADMIN_IDS))), ADMIN_IDS)

            expired_trial_users = await cursor.fetchall()

            for (user_id,) in expired_trial_users:
                try:
                    message = """❌ <b>Ваша trial подписка истекла!</b>

🚫 Доступ к VPN заблокирован.
🔒 Ваши конфигурации удалены.

💳 Для возобновления доступа приобретите платную подписку в главном меню!

🆘 Если у вас возникли вопросы - обращайтесь в поддержку."""

                    await bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="HTML"
                    )

                    print(f"Отправлено уведомление об истечении trial пользователю {user_id}")
                    sent_reminders += 1

                    await asyncio.sleep(0.1)

                except Exception as user_error:
                    print(f"Ошибка отправки уведомления пользователю {user_id}: {user_error}")
                    continue

            print(f"Отправка напоминаний завершена. Отправлено: {sent_reminders} уведомлений")

    except Exception as e:
        print(f"Ошибка при отправке напоминаний: {e}")
        raise
