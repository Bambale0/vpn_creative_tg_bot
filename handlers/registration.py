"""
Модуль для регистрации хендлеров.
Вызывается только при запуске приложения.
"""

from .command import register_command_handlers
from .callback import register_callback_handlers
from .payment import register_payment_handlers


def register_all_handlers(dp):
    """Зарегистрировать все хендлеры"""
    register_command_handlers(dp)
    register_callback_handlers(dp)
    register_payment_handlers(dp)
    print("Все хендлеры успешно зарегистрированы")
