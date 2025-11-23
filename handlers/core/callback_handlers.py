"""
Чистые функции callback хендлеров (без декораторов)
"""
from aiogram import types, F
from aiogram.filters import Filter
from config.dependencies import t, log
from utils.menu import (
    main_menu, pricing_menu, setup_instructions_menu,
    profile_menu, daily_bonus_menu, wireguard_advantages_menu, plugins_menu,
    monitoring_menu, payment_method_menu
)
from utils.game import get_trial, activate_trial, claim_daily_bonus, check_subscription
from utils.game import show_achievements, show_leaderboard
from utils.wireguard import generate_wg_config
from utils.plugins import monitoring_plugin
from utils.referral import referral_ui
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Добавляем импорт утилит для обработки callback'ов
from utils.callback_utils import handle_expired_callbacks, is_callback_expired_error

import os
import json

async def handle_main_menu_callback(callback: types.CallbackQuery):
    """Обработчик возврата в главное меню"""
    try:
        markup = await main_menu(callback.from_user.id)
        new_text = await t(callback.from_user.id, "main_menu_full")
        await callback.message.edit_text(
            new_text,
            reply_markup=markup
        )
        await callback.answer()
    except Exception as e:
        if "message is not modified" in str(e):
            await callback.answer("ℹ️ Меню уже актуально", show_alert=False)
        elif "message to edit not found" in str(e):
            await callback.answer("📅 Сообщение устарело, используйте /start", show_alert=True)
        else:
            log().error(f"Error in main_menu callback: {e}")
            await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


@handle_expired_callbacks
async def handle_get_trial_callback(callback: types.CallbackQuery):
    """Обработчик получения trial периода"""
    try:
        success = await get_trial(callback.from_user.id, callback.message)
        if success:
            await callback.answer(await t(callback.from_user.id, "trial_activated"), show_alert=True)
        else:
            await callback.answer(await t(callback.from_user.id, "trial_already_used"), show_alert=True)
    except Exception as e:
        log().error(f"Error in get_trial callback: {e}")
        # Проверяем, является ли ошибка устаревшим callback
        if is_callback_expired_error(e):
            log().warning(f"Old callback ignored for user {callback.from_user.id}")
            return  # Игнорируем устаревшие callbacks
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_pricing_callback(callback: types.CallbackQuery):
    """Обработчик меню тарифов"""
    try:
        markup = await pricing_menu(callback.from_user.id)
        # Используем фиксированный текст вместо несуществующего ключа перевода
        pricing_text = "📦 <b>Выберите тариф</b>\n\n💎 <b>Higher-end тариф:</b> Maximum savings for heavy users\n💰 <b>Premium tariff</b> crossed by left-bottom arrow pointing right: High plan with long-term savings\n⭐ Individual tariff starts: compact plan for new users"
        await callback.message.edit_text(
            pricing_text,
            reply_markup=markup,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        log().error(f"Error in pricing callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_setup_instructions_callback(callback: types.CallbackQuery):
    """Обработчик инструкций по настройке"""
    try:
        await setup_instructions_menu(callback.from_user.id, callback.message)
        await callback.answer()
    except Exception as e:
        log().error(f"Error in setup_instructions callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_pay_callback(callback: types.CallbackQuery):
    """Обработчик выбора способа оплаты"""
    try:
        # Extract months from callback data (pay_1, pay_3, pay_12)
        months = int(callback.data.split("_")[1])
        menu_text, markup = await payment_method_menu(callback.from_user.id, months)
        await callback.message.edit_text(
            menu_text,
            reply_markup=markup,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        log().error(f"Error in pay callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_profile_menu_callback(callback: types.CallbackQuery):
    """Обработчик меню профиля"""
    try:
        profile_text, markup = await profile_menu(callback.from_user.id)
        
        try:
            await callback.message.edit_text(
                profile_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            await callback.answer()
        except Exception as edit_error:
            # Обрабатываем ошибку "message is not modified"
            if "message is not modified" in str(edit_error):
                # Просто отвечаем, что информация актуальна
                await callback.answer("ℹ️ Информация уже актуальна", show_alert=False)
            else:
                # Другие ошибки пробрасываем дальше
                raise edit_error
                
    except Exception as e:
        log().error(f"Error in profile_menu callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_referral_ui_callback(callback: types.CallbackQuery):
    """Обработчик реферального интерфейса"""
    try:
        referral_text = await referral_ui(callback.from_user.id)
        await callback.message.edit_text(
            referral_text,
            reply_markup=await main_menu(callback.from_user.id)
        )
        await callback.answer()
    except Exception as e:
        log().error(f"Error in referral_ui callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_activate_trial_callback(callback: types.CallbackQuery):
    """Обработчик активации trial"""
    try:
        success = await activate_trial(callback.from_user.id, callback.message)
        if success:
            await callback.answer(await t(callback.from_user.id, "trial_activated"), show_alert=True)
        else:
            await callback.answer(await t(callback.from_user.id, "trial_already_used"), show_alert=True)
    except Exception as e:
        log().error(f"Error in activate_trial callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


@handle_expired_callbacks
async def handle_claim_daily_bonus_callback(callback: types.CallbackQuery):
    """Обработчик получения ежедневного бонуса"""
    try:
        success = await claim_daily_bonus(callback.from_user.id, callback.message)
        if success:
            await callback.answer(await t(callback.from_user.id, "daily_bonus_claimed"), show_alert=True)
        else:
            await callback.answer(await t(callback.from_user.id, "daily_bonus_already_claimed"), show_alert=True)
    except Exception as e:
        log().error(f"Error in claim_daily_bonus callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_check_subscription_callback(callback: types.CallbackQuery):
    """Обработчик проверки подписки"""
    try:
        await check_subscription(callback.from_user.id, callback.message)
        await callback.answer()
    except Exception as e:
        log().error(f"Error in check_subscription callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_achievements_callback(callback: types.CallbackQuery):
    """Обработчик достижений"""
    try:
        await show_achievements(callback.from_user.id, callback.message)
        await callback.answer()
    except Exception as e:
        log().error(f"Error in achievements callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_leaderboard_callback(callback: types.CallbackQuery):
    """Обработчик таблицы лидеров"""
    try:
        await show_leaderboard(callback.from_user.id, callback.message)
        await callback.answer()
    except Exception as e:
        log().error(f"Error in leaderboard callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_get_config_callback(callback: types.CallbackQuery):
    """Обработчик получения конфигурации WireGuard"""
    try:
        # Проверяем наличие активной подписки
        subscription_info = await check_subscription(callback.from_user.id, callback.message)

        if not subscription_info.get("has_active"):
            await callback.answer(await t(callback.from_user.id, "config_error_no_sub"), show_alert=True)
            return

        # Генерируем конфигурацию WireGuard
        try:
            config_text = await generate_wg_config(callback.from_user.id)
        except Exception as config_error:
            if "лимита конфигураций" in str(config_error):
                await callback.answer(await t(callback.from_user.id, "config_limit_exceeded"), show_alert=True)
            else:
                await callback.answer(await t(callback.from_user.id, "config_error_creation"), show_alert=True)
            return
        
        # Создаем временный файл с конфигом
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as tmp_file:
            tmp_file.write(config_text)
            tmp_file_path = tmp_file.name
        
        try:
            # Отправляем файл пользователю
            with open(tmp_file_path, 'rb') as config_file:
                await callback.message.answer_document(
                    document=types.BufferedInputFile(
                        config_file.read(),
                        filename=f"wg_{callback.from_user.id}.conf"
                    ),
                    caption=await t(callback.from_user.id, "config_file_caption")
                )

            # Генерируем и отправляем QR-код
            from utils.wireguard import generate_qr_code
            qr_buffer = await generate_qr_code(config_text)

            await callback.message.answer_photo(
                photo=types.BufferedInputFile(
                    qr_buffer.getvalue(),
                    filename=f"wg_qr_{callback.from_user.id}.png"
                ),
                caption=await t(callback.from_user.id, "qr_code_caption")
            )
            
            await callback.answer()
            
        finally:
            # Удаляем временный файл
            os.unlink(tmp_file_path)
            
    except Exception as e:
        log().error(f"Error in get_config callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_invite_friends_callback(callback: types.CallbackQuery):
    """Обработчик реферальной системы - использует обновленную функцию"""
    try:
        # Используем новую оптимизированную функцию из menu.py
        from utils.menu import referral_menu
        await referral_menu(callback.from_user.id, callback.message)
        await callback.answer()
    except Exception as e:
        log().error(f"Error in invite_friends callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_daily_bonus_callback(callback: types.CallbackQuery):
    """Обработчик меню ежедневного бонуса"""
    try:
        from utils.menu import daily_bonus_menu
        await daily_bonus_menu(callback.from_user.id, callback.message)
        await callback.answer()
    except Exception as e:
        log().error(f"Error in daily_bonus callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_wireguard_advantages_callback(callback: types.CallbackQuery):
    """Обработчик меню преимуществ WireGuard"""
    try:
        text, markup = await wireguard_advantages_menu(callback.from_user.id)
        await callback.message.edit_text(
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        log().error(f"Error in wireguard_advantages callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_plugins_menu_callback(callback: types.CallbackQuery):
    """Обработчик меню плагинов"""
    try:
        # Проверяем права администратора
        from config.config import ADMIN_IDS
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("🚫 Доступ запрещен", show_alert=True)
            return

        markup = await plugins_menu(callback.from_user.id)
        await callback.message.edit_text(
            await t(callback.from_user.id, "plugins_menu_header"),
            reply_markup=markup,
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        log().error(f"Error in plugins_menu callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_monitoring_menu_callback(callback: types.CallbackQuery):
    """Обработчик меню мониторинга"""
    try:
        # Проверяем права администратора
        from config.config import ADMIN_IDS
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("🚫 Доступ запрещен", show_alert=True)
            return
        
        from utils.plugins import monitoring_plugin
        
        # Получаем полный отчет
        report = await monitoring_plugin.get_comprehensive_report()
        
        if 'error' in report:
            await callback.answer(f"❌ Ошибка: {report['error']}", show_alert=True)
            return
        
        # Формируем красивый отчет
        status_emoji = "✅" if report['status'] == 'healthy' else "⚠️"
        
        message_text = (
            f"{status_emoji} <b>Мониторинг системы</b>\n\n"
            f"📊 <b>Статус:</b> {report['status'].upper()}\n"
            f"⏰ <b>Время:</b> {report['timestamp']}\n"
            f"🕐 <b>Uptime:</b> {report['uptime']}\n\n"
            
            f"💻 <b>Система:</b>\n"
            f"   • CPU: {report['system']['cpu_count']} cores\n"
            f"   • Память: {report['system']['memory']['percentage']}% использовано\n"
            f"   • Платформа: {report['system']['platform']}\n\n"
            
            f"🗄️ <b>База данных:</b>\n"
            f"   • Размер: {report['database']['file_size']} bytes\n"
            f"   • Таблиц: {len(report['database']['tables'])}\n"
            f"   • Записей: {report['database']['total_records']}\n"
            f"   • Целостность: {report['database']['integrity_check']}\n\n"
            
            f"🤖 <b>Бот:</b>\n"
            f"   • Активные пользователи: {report['bot']['active_users']}\n"
            f"   • Всего пользователей: {report['bot']['total_users']}\n"
            f"   • Активные подписки: {report['bot']['active_subscriptions']}\n"
            f"   • Конверсия: {report['bot']['conversion_rate']:.2f}%\n\n"
            
            f"🔒 <b>Безопасность:</b>\n"
            f"   • Открытые порты: {len([p for p in report['security']['ports'] if p['status'] == 'open'])}\n"
            f"   • Аномалий: {len(report['security']['anomalies'])}\n"
        )
        
        # Создаем клавиатуру с действиями
        builder = InlineKeyboardBuilder()

        # Texts for buttons
        refresh_text = await t(callback.from_user.id, "monitoring_refresh_btn")
        realtime_text = await t(callback.from_user.id, "monitoring_realtime_btn")
        security_text = await t(callback.from_user.id, "monitoring_security_btn")
        detailed_text = await t(callback.from_user.id, "monitoring_detailed_btn")
        back_text = await t(callback.from_user.id, "back_to_main")

        builder.row(types.InlineKeyboardButton(
            text=refresh_text,
            callback_data="monitoring_refresh"
        ))

        builder.row(types.InlineKeyboardButton(
            text=realtime_text,
            callback_data="monitoring_realtime"
        ))

        builder.row(types.InlineKeyboardButton(
            text=security_text,
            callback_data="monitoring_security"
        ))

        builder.row(types.InlineKeyboardButton(
            text=detailed_text,
            callback_data="monitoring_detailed"
        ))

        builder.row(types.InlineKeyboardButton(
            text=back_text,
            callback_data="main_menu"
        ))
        
        await callback.message.edit_text(
            message_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        log().error(f"Error in monitoring_menu callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_monitoring_refresh_callback(callback: types.CallbackQuery):
    """Обработчик обновления мониторинга"""
    try:
        from config.config import ADMIN_IDS
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("🚫 Доступ запрещен", show_alert=True)
            return
        
        await callback.answer("🔄 Обновление данных...", show_alert=False)
        await handle_monitoring_menu_callback(callback)
        
    except Exception as e:
        log().error(f"Error in monitoring_refresh callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_monitoring_realtime_callback(callback: types.CallbackQuery):
    """Обработчик реальных метрик"""
    try:
        from config.config import ADMIN_IDS
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("🚫 Доступ запрещен", show_alert=True)
            return
        
        from utils.plugins import monitoring_plugin
        metrics = monitoring_plugin.get_real_time_metrics()
        
        message_text = (
            "⚡ <b>Реальные метрики системы</b>\n\n"
            f"💻 <b>CPU:</b> {metrics['cpu_percent']:.1f}%\n"
            f"🧠 <b>Память:</b> {metrics['memory_percent']:.1f}%\n"
            f"💾 <b>Диски:</b>\n"
        )
        
        for disk in metrics['disk_usage']:
            message_text += f"   • {disk['mountpoint']}: {disk['percent']:.1f}%\n"
        
        message_text += (
            f"🌐 <b>Сетевые соединения:</b> {metrics['network_connections']}\n"
            f"⚙️ <b>Процессы:</b> {metrics['process_count']}\n"
            f"📊 <b>Load Average:</b> {', '.join(f'{x:.2f}' for x in metrics['load_average'])}\n"
            f"⏰ <b>Время:</b> {metrics['timestamp']}\n"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="monitoring_realtime"
        ))
        builder.row(types.InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="monitoring_menu"
        ))
        
        await callback.message.edit_text(
            message_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        log().error(f"Error in monitoring_realtime callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_monitoring_security_callback(callback: types.CallbackQuery):
    """Обработчик отчета по безопасности"""
    try:
        from config.config import ADMIN_IDS
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("🚫 Доступ запрещен", show_alert=True)
            return
        
        from utils.plugins import monitoring_plugin
        security_report = monitoring_plugin.generate_security_report()
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="🔄 Проверить снова",
            callback_data="monitoring_security"
        ))
        builder.row(types.InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="monitoring_menu"
        ))
        
        await callback.message.edit_text(
            security_report,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        log().error(f"Error in monitoring_security callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_monitoring_detailed_callback(callback: types.CallbackQuery):
    """Обработчик подробного отчета"""
    try:
        from config.config import ADMIN_IDS
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("🚫 Доступ запрещен", show_alert=True)
            return

        from utils.plugins import monitoring_plugin
        report = await monitoring_plugin.get_comprehensive_report()

        if 'error' in report:
            await callback.answer(f"❌ Ошибка: {report['error']}", show_alert=True)
            return

        # Формируем JSON-отчет для администратора
        import json
        detailed_report = json.dumps(report, indent=2, ensure_ascii=False)

        # Отправляем как файл, если слишком большой
        if len(detailed_report) > 4000:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(detailed_report)
                f.flush()

                from aiogram.types import FSInputFile
                await callback.message.answer_document(
                    FSInputFile(f.name),
                    caption="📊 Подробный отчет мониторинга"
                )

                os.unlink(f.name)
        else:
            await callback.message.edit_text(
                f"📊 <b>Подробный отчет:</b>\n\n"
                f"<code>{detailed_report[:3500]}...</code>",
                parse_mode="HTML"
            )

        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="monitoring_menu"
        ))

        await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
        await callback.answer()

    except Exception as e:
        log().error(f"Error in monitoring_detailed callback: {e}")
        await callback.answer(await t(callback.from_user.id, "error_occurred"), show_alert=True)


async def handle_device_instructions_callback(callback: types.CallbackQuery):
    """Обработчик инструкций для конкретного устройства"""
    try:
        # Извлекаем тип устройства из callback_data
        device_type = callback.data.split("_")[1]  # device_android, device_ios, etc.

        from utils.menu import get_device_instructions

        # Получаем подробные инструкции для устройства
        instructions_text = await get_device_instructions(device_type, callback.from_user.id)

        # Создаем клавиатуру с кнопками для скачивания файлов и назад
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Скачать wg0.conf", callback_data="get_config")],
            [InlineKeyboardButton(text="👈 Назад к выбору", callback_data="setup_instructions"),
             InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
        ])

        await callback.message.edit_text(
            instructions_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True  # Отключаем превью ссылок
        )

        await callback.answer()

    except Exception as e:
        log().error(f"Error in device instructions callback for {callback.data}: {e}")
        await callback.answer("❌ Ошибка загрузки инструкций", show_alert=True)
