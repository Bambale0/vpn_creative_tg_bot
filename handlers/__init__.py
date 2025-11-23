"""
Handlers package for VPN Telegram Bot
"""

from .callback import register_callback_handlers
from .command import register_command_handlers
from .payment import register_payment_handlers
from .webhook import register_webhook_handlers

__all__ = [
    "register_callback_handlers",
    "register_command_handlers",
    "register_payment_handlers",
    "register_webhook_handlers"
]
