"""
Модуль для работы с меню бота
"""

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config.dependencies import t
import aiosqlite
from config.config import DB_PATH, ADMIN_IDS
from datetime import datetime
import logging
from utils.game import check_subscription as check_subscription_full

log = logging.getLogger("menu")


async def translate_func(user_id, key, **kwargs):
    """Функция перевода для совместимости"""
    try:
        return await t(user_id, key, **kwargs)
    except RuntimeError:
        # Для тестовых целей возвращаем ключ
        return key


def get_db():
    """Получить экземпляр базы данных"""
    # В новой архитектуре мы используем прямое подключение к БД
    return DB_PATH


async def check_subscription(uid):
    """Проверить активную подписку пользователя"""
    # Админы всегда имеют премиум подписку
    from config.config import ADMIN_IDS
    if uid in ADMIN_IDS:
        return True

    async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
        async with conn.execute(
            "SELECT end_date FROM subscriptions WHERE user_id = ? AND end_date > datetime('now')",
            (uid,)
        ) as cursor:
            result = await cursor.fetchone()
            return result is not None


async def main_menu(uid):
    """
    🎯 Добро пожаловать в главное меню! Здесь вы найдете все возможности нашего VPN сервиса:
    
    • 🎁 Бесплатный Trial - Попробуйте наш сервис бесплатно
    • 🛡️ Получить конфиг - Настройте VPN на ваших устройствах
    • 📊 Мой профиль - Посмотрите статистику и достижения
    • 💳 Тарифы - Выберите подходящий план подписки
    • 🎯 Ежедневный бонус - Получайте награды за ежедневные посещения
    • 👥 Пригласить друзей - Приглашайте друзей и получайте бонусы
    • 📚 Инструкция - Подробные инструкции по настройке
    • 🌟 Преимущества WireGuard - Узнайте почему мы выбрали лучшую технологию
    
    Мы всегда готовы помочь вам с настройкой и ответить на любые вопросы! 😊
    """
    subscription_info = await check_subscription(uid)
    has_active_sub = subscription_info
    
    builder = InlineKeyboardBuilder()
    
    # Группируем кнопки по смыслу
    if not has_active_sub:
        builder.row(types.InlineKeyboardButton(
            text=await translate_func(uid, "get_trial_btn"),
            callback_data="get_trial"
        ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(uid, "get_config_btn"),
        callback_data="get_config"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(uid, "my_subscription_btn"),
        callback_data="my_profile"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(uid, "pricing_btn"),
        callback_data="pricing"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(uid, "daily_bonus_btn"),
        callback_data="daily_bonus"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(uid, "invite_friends_btn"),
        callback_data="invite_friends"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(uid, "setup_instructions_btn"),
        callback_data="setup_instructions"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(uid, "wireguard_advantages_btn"),
        callback_data="wireguard_advantages"
    ))

    builder.row(types.InlineKeyboardButton(
        text=await translate_func(uid, "support_btn"),
        callback_data="support_btn"
    ))
    
    # Добавляем кнопку плагинов только для администраторов
    if uid in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(
            text="🛠️ Плагины",
            callback_data="plugins_menu"
        ))
    
    return builder.as_markup()


async def pricing_menu(uid):
    """Оптимизированное многоязычное меню тарифов с четкими преимуществами"""
    builder = InlineKeyboardBuilder()

    # Получаем язык пользователя для правильного отображения цен
    from config.dependencies import t

    # Многоязычное меню тарифов в зависимости от языка пользователя
    month_text = await translate_func(uid, "month")
    months_text = await translate_func(uid, "months")

    # Привлекательные кнопки тарифов с выгодными предложениями на разных языках
    builder.row(types.InlineKeyboardButton(
        text=f"⭐ 1 {month_text}\n💰 200₽ → 6.7₽/day",
        callback_data="pay_1"
    ))

    builder.row(types.InlineKeyboardButton(
        text=f"🎯 3 {months_text}\n💰 540₽ → 6₽/day • Discount 10%",
        callback_data="pay_3"
    ))

    builder.row(types.InlineKeyboardButton(
        text=f"🌟 12 {months_text}\n💰 2000₽ → 5.5₽/day • Best -17%",
        callback_data="pay_12"
    ))

    # Многоязычная кнопка назад
    back_text = await translate_func(uid, "back_to_main")
    builder.row(types.InlineKeyboardButton(
        text=f"👈 {back_text}",
        callback_data="main_menu"
    ))

    return builder.as_markup()


async def payment_method_menu(uid, months):
    """Лаконичное меню способов оплаты"""
    builder = InlineKeyboardBuilder()

    # Простые и ясные кнопки оплаты
    builder.row(types.InlineKeyboardButton(
        text="💳 Карта → Мгновенная активация",
        callback_data=f"yookassa_pay_{months}"
    ))

    builder.row(types.InlineKeyboardButton(
        text="₿ Крипта → Полная анонимность",
        callback_data=f"crypto_pay_{months}"
    ))

    builder.row(types.InlineKeyboardButton(
        text="👈 К тарифам",
        callback_data="pricing"
    ))

    return "🔒 Безопасная оплата", builder.as_markup()


async def profile_menu(user_id: int) -> tuple[str, types.InlineKeyboardMarkup]:
    """Компактное отображение профиля пользователя"""
    try:
        from utils.game import check_subscription as check_subscription_full

        builder = InlineKeyboardBuilder()

        # Получаем данные о пользователе
        async with aiosqlite.connect(DB_PATH, timeout=5) as conn:
            cursor = await conn.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
            points = (await cursor.fetchone() or [0])[0]

            cursor = await conn.execute("SELECT COUNT(*) FROM referrals WHERE inviter_id = ?", (user_id,))
            referrals_count = (await cursor.fetchone())[0]

            cursor = await conn.execute("SELECT COUNT(*) FROM user_achievements WHERE user_id = ?", (user_id,))
            achievements_count = (await cursor.fetchone())[0]

            cursor = await conn.execute("SELECT streak_count FROM daily_bonus WHERE user_id = ?", (user_id,))
            streak = (await cursor.fetchone() or [0])[0]

        # Рассчитываем уровень
        level = (points // 100) + 1

        # Получаем статус подписки
        sub_info = await check_subscription_full(user_id, None)
        has_active_sub = sub_info.get("has_active", False)
        is_admin = sub_info.get("is_admin", False)
        sub_status = "✅ Админ" if is_admin else ("✅ Активна" if has_active_sub else "❌ Не активна")

        # Прогресс-бар уровня
        progress = points % 100 if points < (level * 100) else 100
        progress_bar = "▰" * (progress // 10) + "▱" * (10 - progress // 10)

        timestamp = datetime.now().strftime("%H:%M")

        profile_text = f"""👤 <b>Профиль</b> ({timestamp})

⭐ Уровень {level}: {progress_bar} {points % 100}/100
🛡️ Подписка: {sub_status}
🔥 Серия: {streak} дней
👥 Рефералов: {referrals_count}
🏆 Достижений: {achievements_count}"""

        builder.row(types.InlineKeyboardButton(text="🔄 Обновить", callback_data="my_profile"))
        builder.row(types.InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

        return profile_text, builder.as_markup()

    except Exception as e:
        log.error(f"Error in profile_menu for user {user_id}: {e}")
        error_text = "👤 <b>Профиль</b>\n\n❌ Ошибка загрузки данных"

        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔄 Повторить", callback_data="my_profile"))
        builder.row(types.InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))

        return error_text, builder.as_markup()


async def daily_bonus_menu(user_id: int, message) -> None:
    """Компактное меню ежедневного бонуса"""
    try:
        from utils.game import get_daily_bonus_info

        bonus_info = await get_daily_bonus_info(user_id)

        if bonus_info["can_claim"]:
            # Доступен бонус
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"🎁 Получить {bonus_info['amount']} дней",
                    callback_data="claim_daily_bonus"
                )],
                [InlineKeyboardButton(
                    text="👈 Назад",
                    callback_data="main_menu"
                )]
            ])

            await message.answer(
                f"🎯 <b>Ежедневный бонус</b>\n\nВы получили: <b>{bonus_info['amount']} дней</b> подписки!\n🔥 Серия: <b>{bonus_info['streak']} дней</b>\n\nПолучайте бонусы регулярно 😊",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Следующий бонус позже
            next_claim_time = bonus_info["next_claim_time"]
            time_left = next_claim_time - datetime.utcnow()
            hours_left = int(time_left.total_seconds() // 3600)

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="👈 Назад",
                    callback_data="main_menu"
                )]
            ])

            await message.answer(
                f"🎯 <b>Следующий бонус через:</b>\n\n⏰ <b>{hours_left} часов</b>\n\nВозвращайтесь ежедневно!",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    except Exception as e:
        log.error(f"Error showing daily bonus menu for user {user_id}: {e}")
        await message.answer("❌ Ошибка загрузки бонуса")


async def referral_menu(user_id: int, message) -> None:
    """Лаконичное меню реферальной программы"""
    try:
        from utils.game import get_referral_info, get_user_referral_code

        # Получаем данные
        referral_info = await get_referral_info(user_id)
        referral_code = await get_user_referral_code(user_id)

        # Компактное сообщение
        message_text = f"""👥 <b>Реферальная программа</b>

📋 Ваш код: <code>{referral_code}</code>
👥 Рефералов: {referral_info["referral_count"]}
🎁 Сумма бонусов: {referral_info["total_bonus"]} дней

<i>Приглашайте друзей → получайте дни подписки!</i>"""

        # Создаем клавиатуру с кнопкой поделиться и назад
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔗 Поделиться",
                switch_inline_query=f"ref_{referral_code}"
            )],
            [InlineKeyboardButton(
                text="👈 Назад",
                callback_data="main_menu"
            )]
        ])

        await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        log.error(f"Error showing referral menu for user {user_id}: {e}")
        await message.answer("❌ Ошибка загрузки реферальной информации")


async def get_device_instructions(device_type: str, user_id: int) -> str:
    """Получить инструкции для конкретного устройства"""
    if device_type == "android":
        return """📱 <b>Настройка на Android</b>

📱 Скачайте приложение WireGuard из Google Play Store
   🔍 Поиск: "WireGuard"

🚀 <b>Подробная установка:</b>
1️⃣ Откройте WireGuard после установки
2️⃣ Нажмите "+" для добавления туннеля
3️⃣ Выберите "Импорт из файла"
4️⃣ Найдите и выберите файл wg0.conf
5️⃣ Задайте имя туннелю (например, "VPN Chill")
6️⃣ Нажмите "Создать" (Create)

🎯 <b>Подключение:</b>
   • Переключите тумблер вправо чтоь включить
   • Переключите влево чтобы отключить

⚡ <b>Использование:</b>
   • Подключитесь в любой момент
   • Уведомление в статусную строку
   • Активность видна в приложении WireGuard

🔋 <b>Экономия батареи:</b>
   • Наш сервер оптимизирован для мобильных
   • Низкое потребление трафика
   • Умное управление соединением

🆘 <b>Проблемы?</b> Напишите нами support@chillcreative.ru"""

    elif device_type == "ios":
        return """📱 <b>Настройка на iPhone/iPad</b>

📱 Скачайте WireGuard из App Store
   🔍 Поиск: "WireGuard"

🚀 <b>Подробная установка:</b>
1️⃣ Запустите WireGuard после установки
2️⃣ Коснитесь "+" в правом верхнем углу
3️⃣ Выберите "Импорт с файла"
4️⃣ Выберите скачать файл wg0.conf
5️⃣ Задайте имя туннелю (например, "VPN Chill")
6️⃣ Нажмите "Сохранить" (Save)

🎯 <b>Подключение:</b>
   • Переключите тумблер ON/OFF
   • статус вверху приложения

⚡ <b>Советы:</b>
   • Используйте на ходу
   • Полная совместимость с iOS
   • Защита всех приложений

🔋 <b>Оптимизация:</b>
   • Низкое потребление батареи
   • Сохранение зарядки устройства
   • Умное управление данными

🆘 <b>Нужна помощь?</b> support@chillcreative.ru"""

    elif device_type == "windows":
        return """💻 <b>Настройка на Windows</b>

📥 Скачайте WireGuard для Windows:
   🌐 https://download.wireguard.com/windows-client/

🚀 <b>Пошаговая установка:</b>
1️⃣ Запустите установщик .msi
2️⃣ Следуйте указаниям мастера установки
3️⃣ Запустите WireGuard после установки
4️⃣ Щелкните правой кнопкой на трее (панели задач)
5️⃣ Выберите "Import tunnel(s) from file"
6️⃣ Найдите файл wg0.conf
7️⃣ Двойной клик по туннелю чтоь активировать

🎯 <b>Управление:</b>
   • Правый клик по значку в трее
   • Активация/деактивация туннелей
   • Просмотр состояния подключения

⚡ <b>Преимущества:</b>
   • Полная защита всего трафика
   • Быстрое переключение
   • Минимум системных ресурсов
   • Автоматическое обновление

🔋 <b>Производительность:</b>
   • Не замедляет систему
   • Низкое потребление ресурсов
   • Стабильная работа в фоне

🆘 <b>Техподдержка:</b> support@chillcreative.ru"""

    elif device_type == "macos":
        return """🍎 <b>Настройка на MacOS</b>

📥 Скачайте WireGuard для macOS:
   🌐 https://apps.apple.com/app/wireguard/id1451685025

   Или через Homebrew:
   brew install --cask wireguard

🚀 <b>Установка шаг за шагом:</b>
1️⃣ Запустите приложение WireGuard
2️⃣ Щелкните "+" для нового туннеля
3️⃣ Выберите "Import tunnel(s) from file"
4️⃣ Найдите скачайте wg0.conf
5️⃣ Назовите туннель (например, "VPN Chill")
6️⃣ "Activate" или двойной клик для подключения

🎯 <b>Использование:</b>
   • Переключение с помощью значка в меню
   • Виджет Touch Bar (на новых MacBook)
   • Горячие клавиши для быстрого доступа

⚡ <b>Особенности macOS:</b>
   • Полная интеграция с системой
   • Защита от утечек DNS
   • Оптимизация под Apple Silicon

🔋 <b>Эффективность:</b>
   • Низкое потребление энергии
   • Умное управление сетью
   • Высокая стабильность

🆘 <b>Поддержка:</b> support@chillcreative.ru"""

    else:
        return """📚 <b>Выберите ваше устройство для детальных инструкций:</b>

📱 <b>Мобильные устройства:</b>
   • Android - простая установка из Google Play
   • iPhone/iPad - App Store приложение

💻 <b>Компьютеры:</b>
   • Windows 10/11 - официальный клиент
   • macOS - App Store или Homebrew

🖥️ <b>Другие платформы:</b>
   • Linux - WireGuard встроен в ядро
   • Роутеры - DD-WRT/OpenWRT
   • Smart TV, консоли - специальные конфиги

⚡ <b>Все инструкции адаптированы под ваше устройство с подробными скриншотами и видео-гайдами</b>

🆘 <b>Вопросы?</b> support@chillcreative.ru"""


async def setup_instructions_menu(user_id: int, message) -> None:
    """Расширенное меню инструкций с отдельными страницами для каждого устройства"""
    try:
        # Проверяем подписку пользователя
        subscription_info = await check_subscription(user_id)

        if not subscription_info:
            # Даже без подписки показываем общие инструкции
            welcome_text = """🔒 <b>Добро пожаловать в VPN!</b>

🔥 Активируйте подписку чтобы получить доступ к полным инструкциям и настройке

❤️ Выберите ваше устройство:"""
        else:
            welcome_text = """🔥 <b>VPN Setup - Выберите устройство</b>

⚡ Детальные инструкции с фото и видео для каждого устройства
📱 Все платформы поддерживаются
🔐 Защищенные подключения"""

        # Создаем клавиатуру с кнопками основных устройств
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            # Мобильные
            [
                InlineKeyboardButton(text="🤖 Android", callback_data="device_android"),
                InlineKeyboardButton(text="📱 iPhone", callback_data="device_ios"),
            ],
            # Компьютеры
            [
                InlineKeyboardButton(text="💻 Windows", callback_data="device_windows"),
                InlineKeyboardButton(text="🍎 macOS", callback_data="device_macos"),
            ],
            # Другие платформы
            [
                InlineKeyboardButton(text="🖥️ Linux", callback_data="device_linux"),
            ],
            [
                InlineKeyboardButton(text="👈 Назад", callback_data="main_menu"),
            ]
        ])

        await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        log.error(f"Error showing setup instructions for user {user_id}: {e}")
        await message.answer("❌ Ошибка загрузки инструкций")


async def wireguard_advantages_menu(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Итоговое меню преимуществ WireGuard"""
    # Создаем описание преимуществ WireGuard
    advantages_text = """🌟 <b>Почему мы выбрали WireGuard?</b>

⚡ <b>Молниеносная скорость</b>
   • Быстрее OpenVPN в 3-5 раз
   • Нижняя задержка (ping)
   • Оптимизирован для мобильного интернета

🔋 <b>Экономия батареи</b>
   • Низкое потребление энергии на мобильных
   • Умное управление соединением
   • Не "кушает" зарядку телефона

🔐 <b>Современная защита</b>
   • Криптография с доказанной безопасностью
   • Постоянная ротация ключей
   • Защита от утечек DNS и IPv6

🌐 <b>Надежная работа</b>
   • Стабильное подключение везде
   • Легко обходит блокировки
   • Автоматическое восстановление соединения

📱 <b>Простая настройка</b>
   • Работает на всех устройствах
   • Минимум настроек
   • QR-код для мобильных

⚙️ <b>Открытый код</b>
   • Аудиторированный исходный код
   • Сообщество разработчиков
   • Регулярные обновления безопасности

<i>WireGuard - это будущее VPN технологий! 🚀</i>"""

    # Создаем клавиатуру
    try:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="👆 Настройка VPN",
            callback_data="setup_instructions"
        ))
        builder.row(types.InlineKeyboardButton(
            text="◀️ Назад в меню",
            callback_data="main_menu"
        ))

        return advantages_text, builder.as_markup()

    except Exception as e:
        log.error(f"Error creating WireGuard advantages menu for user {user_id}: {e}")
        # Возвращаем минимальную клавиатуру в случае ошибки
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="main_menu"
        ))

        return advantages_text, builder.as_markup()





async def plugins_menu(user_id: int) -> InlineKeyboardMarkup:
    """
    🛠️ Менеджер плагинов - управление расширениями бота
    
    Доступные функции:
    • 📊 Статистика плагинов - информация о загруженных модулях
    • � Управление плагинами - включение/выключение модулей
    • 📦 Установка новых - добавление новых расширений
    • �️ Удаление плагинов - удаление ненужных модулей
    • � Обновление - проверка обновлений для плагинов
    
    💡 Плагины расширяют функциональность бота без изменения основного кода!
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки управления плагинами
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "plugins_stats_btn"),
        callback_data="plugins_stats"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "plugins_manage_btn"),
        callback_data="plugins_manage"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "plugins_install_btn"),
        callback_data="plugins_install"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "plugins_remove_btn"),
        callback_data="plugins_remove"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "plugins_update_btn"),
        callback_data="plugins_update"
    ))
    
    # Добавляем кнопку мониторинга системы
    builder.row(types.InlineKeyboardButton(
        text="� Мониторинг системы",
        callback_data="monitoring_menu"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "back_to_main"),
        callback_data="main_menu"
    ))
    
    return builder.as_markup()


async def monitoring_menu(user_id: int) -> InlineKeyboardMarkup:
    """
    🔍 Меню мониторинга - полный контроль над состоянием системы
    
    Доступные функции:
    • � Общий статус - сводка состояния системы
    • ⚡ Реальные метрики - текущие показатели в реальном времени
    • 🔒 Безопасность - анализ угроз и уязвимостей
    • 📈 Подробный отчет - детальная аналитика
    • 🚨 Алерты - уведомления о проблемах
    • ⚙️ Настройки - конфигурация мониторинга
    
    💡 Система мониторинга отслеживает все аспекты работы бота!
    """
    builder = InlineKeyboardBuilder()
    
    # Основные функции мониторинга
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "monitoring_status_btn"),
        callback_data="monitoring_menu"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "monitoring_realtime_btn"),
        callback_data="monitoring_realtime"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "monitoring_security_btn"),
        callback_data="monitoring_security"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "monitoring_detailed_btn"),
        callback_data="monitoring_detailed"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "monitoring_alerts_btn"),
        callback_data="monitoring_alerts"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "monitoring_settings_btn"),
        callback_data="monitoring_settings"
    ))
    
    builder.row(types.InlineKeyboardButton(
        text=await translate_func(user_id, "monitoring_back_btn"),
        callback_data="plugins_menu"
    ))
    
    return builder.as_markup()
