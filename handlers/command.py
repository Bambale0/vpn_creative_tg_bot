"""
Command handlers for VPN Telegram Bot
"""

from aiogram.filters import Command
from handlers.core.command_handlers import (
    handle_start_command,
    handle_menu_command,
    handle_profile_command,
    handle_daily_command,
    handle_referral_command,
    handle_setup_command,
    handle_welcome_command
)


def register_command_handlers(dp):
    """Регистрирует все командные хендлеры"""
    dp.message.register(handle_start_command, Command("start"))
    dp.message.register(handle_menu_command, Command("menu"))
    dp.message.register(handle_profile_command, Command("profile"))
    dp.message.register(handle_daily_command, Command("daily"))
    dp.message.register(handle_referral_command, Command("referral"))
    dp.message.register(handle_setup_command, Command("setup"))
    dp.message.register(handle_welcome_command, Command("welcome"))
    
    print("Командные хендлеры зарегистрированы")
