import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Добавляем корневую директорию в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from handlers.core.callback_handlers import (
    handle_get_trial_callback, handle_main_menu_callback,
    handle_pricing_callback, handle_plugins_menu_callback,
    handle_monitoring_menu_callback
)


class TestCallbackHandlers:

    @pytest.mark.asyncio
    async def test_handle_get_trial_callback_success(self):
        """Тестирование успешного callback trial"""
        with patch('handlers.core.callback_handlers.get_trial') as mock_get_trial, \
             patch('handlers.core.callback_handlers.t') as mock_translate:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345
            mock_callback.message = MagicMock()

            mock_get_trial.return_value = True
            mock_translate.return_value = "Trial активирован"

            await handle_get_trial_callback(mock_callback)

            mock_get_trial.assert_called_once_with(12345, mock_callback.message)
            mock_callback.answer.assert_called_once_with("Trial активирован", show_alert=True)

    @pytest.mark.asyncio
    async def test_handle_get_trial_callback_already_used(self):
        """Тестирование callback trial уже использованного"""
        with patch('handlers.core.callback_handlers.get_trial') as mock_get_trial, \
             patch('handlers.core.callback_handlers.t') as mock_translate:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345
            mock_callback.message = MagicMock()

            mock_get_trial.return_value = False
            mock_translate.return_value = "Trial уже использован"

            await handle_get_trial_callback(mock_callback)

            mock_callback.answer.assert_called_once_with("Trial уже использован", show_alert=True)

    @pytest.mark.asyncio
    async def test_handle_get_trial_callback_old_query(self):
        """Тестирование callback с устаревшим query"""
        with patch('handlers.core.callback_handlers.get_trial') as mock_get_trial, \
             patch('handlers.core.callback_handlers.t') as mock_translate, \
             patch('handlers.core.callback_handlers.log') as mock_log:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345

            # Мокируем ошибку устаревшего query
            mock_get_trial.side_effect = Exception("Bad Request: query is too old and response timeout expired or query ID is invalid")
            mock_translate.return_value = "Ошибка"

            await handle_get_trial_callback(mock_callback)

            # Должно быть логирование предупреждения
            mock_log.warning.assert_called_once()
            # Не должно быть вызова callback.answer с ошибкой
            mock_callback.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_get_trial_callback_other_error(self):
        """Тестирование callback с другой ошибкой"""
        with patch('handlers.core.callback_handlers.get_trial') as mock_get_trial, \
             patch('handlers.core.callback_handlers.t') as mock_translate:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345

            mock_get_trial.side_effect = Exception("Database error")
            mock_translate.return_value = "Произошла ошибка"

            await handle_get_trial_callback(mock_callback)

            mock_callback.answer.assert_called_once_with("Произошла ошибка", show_alert=True)

    @pytest.mark.asyncio
    async def test_handle_main_menu_callback(self):
        """Тестирование callback главного меню"""
        with patch('handlers.core.callback_handlers.main_menu') as mock_main_menu, \
             patch('handlers.core.callback_handlers.t') as mock_translate:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345
            mock_callback.message = MagicMock()

            mock_main_menu.return_value = MagicMock()
            mock_translate.return_value = "Главное меню"

            await handle_main_menu_callback(mock_callback)

            mock_callback.message.edit_text.assert_called_once()
            mock_callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_pricing_callback(self):
        """Тестирование callback меню тарифов"""
        with patch('handlers.core.callback_handlers.pricing_menu') as mock_pricing_menu, \
             patch('handlers.core.callback_handlers.t') as mock_translate:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345
            mock_callback.message = MagicMock()
            mock_callback.data = "pricing"

            mock_pricing_menu.return_value = MagicMock()
            mock_translate.return_value = "Тарифы"

            await handle_pricing_callback(mock_callback)

            mock_callback.message.edit_text.assert_called_once()
            mock_callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_plugins_menu_callback_admin(self):
        """Тестирование callback меню плагинов для админа"""
        with patch('handlers.core.callback_handlers.ADMIN_IDS', [12345]), \
             patch('handlers.core.callback_handlers.plugins_menu') as mock_plugins_menu, \
             patch('handlers.core.callback_handlers.t') as mock_translate:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345
            mock_callback.message = MagicMock()

            mock_plugins_menu.return_value = MagicMock()
            mock_translate.return_value = "Меню плагинов"

            await handle_plugins_menu_callback(mock_callback)

            mock_callback.message.edit_text.assert_called_once()
            mock_callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_plugins_menu_callback_not_admin(self):
        """Тестирование callback меню плагинов для не-админа"""
        with patch('handlers.core.callback_handlers.ADMIN_IDS', [99999]):  # другой админ

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345  # не админ

            await handle_plugins_menu_callback(mock_callback)

            mock_callback.answer.assert_called_once_with("🚫 Доступ запрещен", show_alert=True)

    @pytest.mark.asyncio
    async def test_handle_monitoring_menu_callback_admin(self):
        """Тестирование callback меню мониторинга для админа"""
        with patch('handlers.core.callback_handlers.ADMIN_IDS', [12345]), \
             patch('handlers.core.callback_handlers.monitoring_plugin') as mock_monitoring, \
             patch('handlers.core.callback_handlers.t') as mock_translate:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345
            mock_callback.message = MagicMock()

            mock_monitoring.get_comprehensive_report.return_value = {
                'status': 'active',
                'version': '2.0.0',
                'system': {'cpu_count': 4},
                'metrics': {'cpu_percent': 50.0},
                'security': {'open_ports': []},
                'database': {'file_size': 1024},
                'bot': {'active_users': 100},
                'timestamp': 1234567890
            }
            mock_translate.return_value = "Назад в главное меню"

            await handle_monitoring_menu_callback(mock_callback)

            mock_callback.message.edit_text.assert_called_once()
            mock_callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_monitoring_menu_callback_not_admin(self):
        """Тестирование callback меню мониторинга для не-админа"""
        with patch('handlers.core.callback_handlers.ADMIN_IDS', [99999]):

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345  # не админ

            await handle_monitoring_menu_callback(mock_callback)

            mock_callback.answer.assert_called_once_with("🚫 Доступ запрещен", show_alert=True)

    @pytest.mark.asyncio
    async def test_handle_monitoring_menu_callback_error(self):
        """Тестирование callback меню мониторинга с ошибкой"""
        with patch('handlers.core.callback_handlers.ADMIN_IDS', [12345]), \
             patch('handlers.core.callback_handlers.monitoring_plugin') as mock_monitoring, \
             patch('handlers.core.callback_handlers.t') as mock_translate:

            mock_callback = MagicMock()
            mock_callback.from_user.id = 12345
            mock_callback.message = MagicMock()

            mock_monitoring.get_comprehensive_report.side_effect = Exception("Plugin error")
            mock_translate.return_value = "Произошла ошибка"

            await handle_monitoring_menu_callback(mock_callback)

            mock_callback.answer.assert_called_once_with("Произошла ошибка", show_alert=True)
