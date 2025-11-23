"""
Модуль управления плагинами для VPN бота
"""

import importlib
import inspect
import os
import sys
import asyncio
import logging
from typing import Dict, List, Any
from pathlib import Path

log = logging.getLogger("plugins")

# Импортируем плагины
from plugins.monitoring_plugin import monitoring_plugin
from plugins.bonus_plugin import bonus_plugin, give_user_bonus, get_bonus_statistics


class PluginManager:
    """Менеджер плагинов для загрузки и управления расширениями"""
    
    def __init__(self, plugins_dir: str="plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins: Dict[str, Any] = {}
        self.loaded_plugins: List[str] = []
        
    def discover_plugins(self) -> List[str]:
        """Обнаруживает все доступные плагины в директории"""
        plugins = []
        if self.plugins_dir.exists():
            for file in self.plugins_dir.glob("*.py"):
                if file.name != "__init__.py" and not file.name.startswith("_"):
                    plugins.append(file.stem)
        return plugins
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Загружает конкретный плагин"""
        try:
            # Специальная обработка для встроенных плагинов
            if plugin_name == "monitoring_plugin":
                if inspect.iscoroutinefunction(monitoring_plugin.setup):
                    result = asyncio.run(monitoring_plugin.setup())
                else:
                    result = monitoring_plugin.setup()
                if result:
                    self.plugins[plugin_name] = monitoring_plugin
                    self.loaded_plugins.append(plugin_name)
                    log.info(f"Плагин '{plugin_name}' успешно загружен")
                    return True
                return False

            elif plugin_name == "bonus_plugin":
                if inspect.iscoroutinefunction(bonus_plugin.setup):
                    result = asyncio.run(bonus_plugin.setup())
                else:
                    result = bonus_plugin.setup()
                if result:
                    self.plugins[plugin_name] = bonus_plugin
                    self.loaded_plugins.append(plugin_name)
                    log.info(f"Плагин '{plugin_name}' успешно загружен")
                    return True
                return False

            # Стандартная загрузка для других плагинов
            module_name = f"plugins.{plugin_name}"
            module = importlib.import_module(module_name)

            if hasattr(module, 'Plugin') and inspect.isclass(module.Plugin):
                plugin_class = module.Plugin
                plugin_instance = plugin_class()

                if hasattr(plugin_instance, 'setup') and callable(plugin_instance.setup):
                    if inspect.iscoroutinefunction(plugin_instance.setup):
                        result = asyncio.run(plugin_instance.setup())
                    else:
                        result = plugin_instance.setup()
                    if result:
                        self.plugins[plugin_name] = plugin_instance
                        self.loaded_plugins.append(plugin_name)
                        log.info(f"Плагин '{plugin_name}' успешно загружен")
                        return True
                    else:
                        log.warning(f"Плагин '{plugin_name}' не удалось инициализировать")
                else:
                    log.warning(f"Плагин '{plugin_name}' не имеет метода setup")
            else:
                log.warning(f"Плагин '{plugin_name}' не содержит класс Plugin")

        except ImportError as e:
            log.error(f"Ошибка импорта плагина '{plugin_name}': {e}")
        except Exception as e:
            log.error(f"Ошибка загрузки плагина '{plugin_name}': {e}")

        return False

    async def aload_plugin(self, plugin_name: str) -> bool:
        """Асинхронная загрузка плагина"""
        try:
            # Специальная обработка для встроенных плагинов
            if plugin_name == "monitoring_plugin":
                if inspect.iscoroutinefunction(monitoring_plugin.setup):
                    result = await monitoring_plugin.setup()
                else:
                    result = monitoring_plugin.setup()
                if result:
                    self.plugins[plugin_name] = monitoring_plugin
                    self.loaded_plugins.append(plugin_name)
                    log.info(f"Плагин '{plugin_name}' успешно загружен")
                    return True
                return False

            elif plugin_name == "bonus_plugin":
                if inspect.iscoroutinefunction(bonus_plugin.setup):
                    result = await bonus_plugin.setup()
                else:
                    result = bonus_plugin.setup()
                if result:
                    self.plugins[plugin_name] = bonus_plugin
                    self.loaded_plugins.append(plugin_name)
                    log.info(f"Плагин '{plugin_name}' успешно загружен")
                    return True
                return False

            # Стандартная загрузка для других плагинов
            module_name = f"plugins.{plugin_name}"
            module = importlib.import_module(module_name)

            if hasattr(module, 'Plugin') and inspect.isclass(module.Plugin):
                plugin_class = module.Plugin
                plugin_instance = plugin_class()

                if hasattr(plugin_instance, 'setup') and callable(plugin_instance.setup):
                    if inspect.iscoroutinefunction(plugin_instance.setup):
                        result = await plugin_instance.setup()
                    else:
                        result = plugin_instance.setup()
                    if result:
                        self.plugins[plugin_name] = plugin_instance
                        self.loaded_plugins.append(plugin_name)
                        log.info(f"Плагин '{plugin_name}' успешно загружен")
                        return True
                    else:
                        log.warning(f"Плагин '{plugin_name}' не удалось инициализировать")
                else:
                    log.warning(f"Плагин '{plugin_name}' не имеет метода setup")
            else:
                log.warning(f"Плагин '{plugin_name}' не содержит класс Plugin")

        except ImportError as e:
            log.error(f"Ошибка импорта плагина '{plugin_name}': {e}")
        except Exception as e:
            log.error(f"Ошибка загрузки плагина '{plugin_name}': {e}")

        return False
    
    def load_all_plugins(self) -> int:
        """Загружает все доступные плагины"""
        plugins = self.discover_plugins()
        loaded_count = 0

        # Всегда загружаем встроенные плагины первыми
        builtin_plugins = ["monitoring_plugin", "bonus_plugin"]

        for builtin in builtin_plugins:
            if hasattr(sys.modules.get(f'plugins.{builtin}'), builtin):
                if self.load_plugin(builtin):
                    loaded_count += 1

        # Загружаем остальные плагины
        for plugin in plugins:
            if plugin not in builtin_plugins and self.load_plugin(plugin):
                loaded_count += 1

        log.info(f"Загружено {loaded_count} из {len(plugins) + len(builtin_plugins)} плагинов")
        return loaded_count

    async def aaload_all_plugins(self) -> int:
        """Асинхронно загружает все доступные плагины"""
        plugins = self.discover_plugins()
        loaded_count = 0

        # Всегда загружаем встроенные плагины первыми
        builtin_plugins = ["monitoring_plugin", "bonus_plugin"]

        for builtin in builtin_plugins:
            if hasattr(sys.modules.get(f'plugins.{builtin}'), builtin):
                if await self.aload_plugin(builtin):
                    loaded_count += 1

        # Загружаем остальные плагины
        for plugin in plugins:
            if plugin not in builtin_plugins and await self.aload_plugin(plugin):
                loaded_count += 1

        log.info(f"Загружено {loaded_count} из {len(plugins) + len(builtin_plugins)} плагинов")
        return loaded_count

    def unload_plugin(self, plugin_name: str) -> bool:
        """Выгружает плагин"""
        if plugin_name in self.plugins:
            try:
                plugin = self.plugins[plugin_name]
                if hasattr(plugin, 'teardown') and callable(plugin.teardown):
                    plugin.teardown()
                
                del self.plugins[plugin_name]
                self.loaded_plugins.remove(plugin_name)
                
                # Выгружаем модуль
                module_name = f"plugins.{plugin_name}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                log.info(f"Плагин '{plugin_name}' успешно выгружен")
                return True
                
            except Exception as e:
                log.error(f"Ошибка выгрузки плагина '{plugin_name}': {e}")
        
        return False
    
    def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """Возвращает информацию о плагине"""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            info = {
                'name': plugin_name,
                'loaded': True,
                'version': getattr(plugin, 'version', '1.0.0'),
                'description': getattr(plugin, 'description', 'Без описания'),
                'author': getattr(plugin, 'author', 'Неизвестный автор'),
            }
            return info
        
        # Информация о не загруженном плагине
        return {
            'name': plugin_name,
            'loaded': False,
            'version': 'Неизвестно',
            'description': 'Плагин не загружен',
            'author': 'Неизвестно'
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по плагинам"""
        available = self.discover_plugins()
        return {
            'total_available': len(available),
            'total_loaded': len(self.loaded_plugins),
            'available_plugins': available,
            'loaded_plugins': self.loaded_plugins,
        }


# Глобальный экземпляр менеджера плагинов
plugin_manager = PluginManager()


def setup_plugins() -> int:
    """Инициализирует и загружает все плагины"""
    return plugin_manager.load_all_plugins()


async def aasetup_plugins() -> int:
    """Асинхронно инициализирует и загружает все плагины"""
    return await plugin_manager.aaload_all_plugins()


def get_plugins_stats() -> Dict[str, Any]:
    """Возвращает статистику плагинов"""
    return plugin_manager.get_stats()


def get_plugin_info(plugin_name: str) -> Dict[str, Any]:
    """Возвращает информацию о конкретном плагине"""
    return plugin_manager.get_plugin_info(plugin_name)


def unload_plugin(plugin_name: str) -> bool:
    """Выгружает плагин"""
    return plugin_manager.unload_plugin(plugin_name)


def load_plugin(plugin_name: str) -> bool:
    """Загружает плагин"""
    return plugin_manager.load_plugin(plugin_name)


# API функции для bonus_plugin
def get_bonus_plugin_info() -> Dict[str, Any]:
    """Информация о bonus плагине"""
    if "bonus_plugin" in plugin_manager.plugins:
        return plugin_manager.plugins["bonus_plugin"].get_info()
    else:
        return {"name": "bonus_plugin", "loaded": False}
