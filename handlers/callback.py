"""
Модуль обработки callback запросов
"""

from aiogram import F
from handlers.core.callback_handlers import (
    handle_main_menu_callback,
    handle_get_trial_callback,
    handle_pricing_callback,
    handle_setup_instructions_callback,
    handle_pay_callback,
    handle_profile_menu_callback,
    handle_referral_ui_callback,
    handle_activate_trial_callback,
    handle_claim_daily_bonus_callback,
    handle_check_subscription_callback,
    handle_achievements_callback,
    handle_leaderboard_callback,
    handle_get_config_callback,
    handle_invite_friends_callback,
    handle_daily_bonus_callback,
    handle_wireguard_advantages_callback,
    handle_plugins_menu_callback,
    handle_monitoring_menu_callback,
    handle_monitoring_refresh_callback,
    handle_monitoring_realtime_callback,
    handle_monitoring_security_callback,
    handle_monitoring_detailed_callback
)


def register_callback_handlers(dp):
    """Регистрирует все callback хендлеры"""
    dp.callback_query.register(handle_main_menu_callback, F.data == "main_menu")
    dp.callback_query.register(handle_get_trial_callback, F.data == "get_trial")
    dp.callback_query.register(handle_pricing_callback, F.data == "pricing")
    dp.callback_query.register(handle_setup_instructions_callback, F.data == "setup_instructions")
    dp.callback_query.register(handle_pay_callback, F.data.startswith("pay_"))
    dp.callback_query.register(handle_profile_menu_callback, F.data == "my_profile")
    dp.callback_query.register(handle_referral_ui_callback, F.data == "referral_ui")
    dp.callback_query.register(handle_activate_trial_callback, F.data == "activate_trial")
    dp.callback_query.register(handle_claim_daily_bonus_callback, F.data == "claim_daily_bonus")
    dp.callback_query.register(handle_check_subscription_callback, F.data == "check_subscription")
    dp.callback_query.register(handle_achievements_callback, F.data == "achievements")
    dp.callback_query.register(handle_leaderboard_callback, F.data == "leaderboard")
    dp.callback_query.register(handle_get_config_callback, F.data == "get_config")
    dp.callback_query.register(handle_invite_friends_callback, F.data == "invite_friends")
    dp.callback_query.register(handle_daily_bonus_callback, F.data == "daily_bonus")
    dp.callback_query.register(handle_wireguard_advantages_callback, F.data == "wireguard_advantages")
    dp.callback_query.register(handle_plugins_menu_callback, F.data == "plugins_menu")
    dp.callback_query.register(handle_monitoring_menu_callback, F.data == "monitoring_menu")
    dp.callback_query.register(handle_monitoring_refresh_callback, F.data == "monitoring_refresh")
    dp.callback_query.register(handle_monitoring_realtime_callback, F.data == "monitoring_realtime")
    dp.callback_query.register(handle_monitoring_security_callback, F.data == "monitoring_security")
    dp.callback_query.register(handle_monitoring_detailed_callback, F.data == "monitoring_detailed")
    
    print("Callback хендлеры зарегистрированы")
