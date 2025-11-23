"""
Пакет плагинов для VPN бота
"""

# Импортируем встроенные плагины для доступности
from .monitoring_plugin import monitoring_plugin
from .bonus_plugin import bonus_plugin

# Экспортируем функции
from .bonus_plugin import give_user_bonus, get_bonus_statistics

__all__ = [
    'monitoring_plugin',
    'bonus_plugin',
    'give_user_bonus',
    'get_bonus_statistics'
]
