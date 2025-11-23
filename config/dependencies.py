"""
Dependency injection and circular import resolution
"""

from typing import Optional
import logging
from aiogram import Dispatcher

# Global instances that will be set during initialization
_bot_instance = None
_log_instance = None
_t_instance = None
_yookassa_instance = None
_crypto_pay_instance = None
_dp_instance = None


def set_bot_instance(bot):
    """Set the bot instance globally"""
    global _bot_instance
    _bot_instance = bot


def get_bot_instance():
    """Get the bot instance"""
    return _bot_instance


def set_log_instance(log):
    """Set the log instance globally"""
    global _log_instance
    _log_instance = log


def get_log_instance():
    """Get the log instance"""
    return _log_instance


def set_t_instance(t_func):
    """Set the translation function instance globally"""
    global _t_instance
    _t_instance = t_func


def get_t_instance():
    """Get the translation function instance"""
    return _t_instance


def set_yookassa_instance(yookassa):
    """Set the YooKassa instance globally"""
    global _yookassa_instance
    _yookassa_instance = yookassa


def get_yookassa_instance():
    """Get the YooKassa instance"""
    return _yookassa_instance


def set_crypto_pay_instance(crypto_pay):
    """Set the Crypto Pay instance globally"""
    global _crypto_pay_instance
    _crypto_pay_instance = crypto_pay


def get_crypto_pay_instance():
    """Get the Crypto Pay instance"""
    return _crypto_pay_instance


def set_dp_instance(dp):
    """Set the Dispatcher instance globally"""
    global _dp_instance
    _dp_instance = dp


def dp():
    """Get the Dispatcher instance"""
    if _dp_instance is None:
        raise RuntimeError("Dispatcher instance not initialized")
    return _dp_instance


def bot():
    """Get the bot instance"""
    if _bot_instance is None:
        raise RuntimeError("Bot instance not initialized")
    return _bot_instance


def log():
    """Get the log instance"""
    if _log_instance is None:
        raise RuntimeError("Log instance not initialized")
    return _log_instance


def t(user_id: int, key: str, **kwargs):
    """Get the translation function"""
    if _t_instance is None:
        raise RuntimeError("Translation instance not initialized")
    return _t_instance(user_id, key, **kwargs)


def yookassa():
    """Get the YooKassa instance"""
    if _yookassa_instance is None:
        raise RuntimeError("YooKassa instance not initialized")
    return _yookassa_instance


def crypto_pay():
    """Get the Crypto Pay instance"""
    if _crypto_pay_instance is None:
        raise RuntimeError("Crypto Pay instance not initialized")
    return _crypto_pay_instance
