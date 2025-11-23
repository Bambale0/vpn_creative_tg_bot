import pytest
import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Добавляем корневую директорию в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.plugins import PluginManager, setup_plugins, get_plugins_stats
from plugins.monitoring_plugin import monitoring_plugin
from plugins.bonus_plugin import bonus_plugin


class TestPluginsIntegration:

    @pytest.mark.asyncio
    async def test_plugin_manager_discover_plugins(self):
        """Тестирование обнаружения плагинов"""
        plugin_manager = PluginManager()

        # Создаем тестовые файлы плагинов
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_manager.plugins_dir = Path(temp_dir)

            # Создаем тестовый плагин
            test_plugin_path = Path(temp_dir) / "test_plugin.py"
            test_plugin_path.write_text("""
class Plugin:
    def setup(self):
        return True
    def teardown(self):
        pass
""")

            plugins = plugin_manager.discover_plugins()
            assert "test_plugin" in plugins

    @pytest.mark.asyncio
    async def test_plugin_manager_load_monitoring_plugin(self):
        """Тестирование загрузки плагина мониторинга"""
        plugin_manager = PluginManager()

        # Мокируем импорт
        with patch.dict('sys.modules', {
            'plugins.monitoring_plugin': MagicMock(),
            'psutil': MagicMock()
        }):
            with patch('plugins.monitoring_plugin.monitoring_plugin') as mock_plugin:
                mock_plugin.setup.return_value = True

                result = plugin_manager.load_plugin("monitoring_plugin")

                assert result is True
                assert "monitoring_plugin" in plugin_manager.loaded_plugins

    @pytest.mark.asyncio
    async def test_plugin_manager_load_bonus_plugin(self):
        """Тестирование загрузки плагина бонусов"""
        plugin_manager = PluginManager()

        # Мокируем импорт и БД
        with patch.dict('sys.modules', {
            'plugins.bonus_plugin': MagicMock(),
        }):
            with patch('plugins.bonus_plugin.sqlite3') as mock_sqlite:
                mock_conn = MagicMock()
                mock_sqlite.connect.return_value = mock_conn

                with patch('plugins.bonus_plugin.bonus_plugin') as mock_plugin:
                    mock_plugin.setup.return_value = True

                    result = plugin_manager.load_plugin("bonus_plugin")

                    assert result is True
                    assert "bonus_plugin" in plugin_manager.loaded_plugins

    @pytest.mark.asyncio
    async def test_setup_plugins_function(self):
        """Тестирование функции setup_plugins"""
        with patch('utils.plugins.plugin_manager') as mock_manager:
            mock_manager.load_all_plugins.return_value = 2

            result = setup_plugins()

            assert result == 2
            mock_manager.load_all_plugins.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_plugins_stats_function(self):
        """Тестирование функции get_plugins_stats"""
        with patch('utils.plugins.plugin_manager') as mock_manager:
            mock_manager.get_stats.return_value = {
                'total_available': 3,
                'total_loaded': 2,
                'available_plugins': ['plugin1', 'plugin2', 'plugin3'],
                'loaded_plugins': ['plugin1', 'plugin2']
            }

            result = get_plugins_stats()

            assert result['total_available'] == 3
            assert result['total_loaded'] == 2

    @pytest.mark.asyncio
    async def test_monitoring_plugin_integration(self):
        """Интеграционное тестирование плагина мониторинга"""
        # Тестируем в изоляции
        with patch('plugins.monitoring_plugin.psutil') as mock_psutil:
            # Настраиваем моки
            mock_psutil.cpu_percent.return_value = 45.0
            mock_psutil.virtual_memory.return_value = MagicMock(percent=60.0)
            mock_psutil.disk_usage.return_value = MagicMock(percent=70.0)
            mock_psutil.net_io_counters.return_value = MagicMock(bytes_sent=1024, bytes_recv=2048)
            mock_psutil.cpu_count.return_value = 4
            mock_psutil.getloadavg.return_value = (1.0, 1.5, 2.0)

            # Инициализируем плагин
            success = monitoring_plugin.setup()
            assert success is True

            # Тестируем получение метрик
            metrics = monitoring_plugin.get_real_time_metrics()
            assert metrics['cpu_percent'] == 45.0
            assert metrics['memory_percent'] == 60.0

            # Тестируем системную информацию
            info = monitoring_plugin.get_system_info()
            assert info['cpu_count'] == 4
            assert info['load_average'] == (1.0, 1.5, 2.0)

            # Тестируем алерты
            alerts = monitoring_plugin.get_performance_alerts()
            # CPU 45% не должен вызывать алерты
            assert len(alerts) == 0

            # Тестируем критический CPU
            mock_psutil.cpu_percent.return_value = 95.0
            alerts = monitoring_plugin.get_performance_alerts()
            assert len(alerts) == 1
            assert alerts[0]['type'] == 'critical'
            assert 'CPU' in alerts[0]['message']

    @pytest.mark.asyncio
    async def test_bonus_plugin_integration(self):
        """Интеграционное тестирование плагина бонусов"""
        with patch('plugins.bonus_plugin.sqlite3') as mock_sqlite:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_sqlite.connect.return_value = mock_conn

            # Настраиваем моки для БД
            mock_cursor.fetchone.side_effect = [(1,), None, None]  # user exists
            mock_cursor.execute.return_value = None
            mock_conn.commit.return_value = None

            # Инициализируем плагин
            success = await bonus_plugin.setup()
            assert success is True

            # Тестируем выдачу бонуса
            result = await bonus_plugin.give_bonus(12345, 30, "Test bonus")
            assert result['success'] is True
            assert result['days'] == 30

            # Тестируем статистику
            mock_cursor.fetchone.side_effect = [(5,), (150,), (3,), (90,)]
            result = await bonus_plugin.get_stats()
            assert result['success'] is True
            assert result['total_bonuses'] == 5
            assert result['total_days'] == 150

    @pytest.mark.asyncio
    async def test_plugins_import_integration(self):
        """Тестирование импорта плагинов из __init__.py"""
        # Проверяем, что плагины доступны для импорта
        from plugins import monitoring_plugin, bonus_plugin, give_user_bonus, get_bonus_statistics

        assert monitoring_plugin is not None
        assert bonus_plugin is not None
        assert callable(give_user_bonus)
        assert callable(get_bonus_statistics)

        # Тестируем глобальные функции
        with patch.object(bonus_plugin, 'give_bonus') as mock_give_bonus:
            mock_give_bonus.return_value = {"success": True, "days": 30}

            result = await give_user_bonus(12345, 30, "Test")
            assert result['success'] is True

        with patch.object(bonus_plugin, 'get_stats') as mock_get_stats:
            mock_get_stats.return_value = {"success": True, "total_bonuses": 10}

            result = await get_bonus_statistics()
            assert result['success'] is True

    @pytest.mark.asyncio
    async def test_plugin_error_handling(self):
        """Тестирование обработки ошибок в плагинах"""
        plugin_manager = PluginManager()

        # Тестируем загрузку несуществующего плагина
        result = plugin_manager.load_plugin("nonexistent_plugin")
        assert result is False

        # Тестируем плагин с ошибкой в setup
        with patch.dict('sys.modules', {
            'plugins.error_plugin': MagicMock(),
        }):
            with patch('plugins.error_plugin.Plugin') as mock_plugin_class:
                mock_instance = MagicMock()
                mock_instance.setup.side_effect = Exception("Setup failed")
                mock_plugin_class.return_value = mock_instance

                result = plugin_manager.load_plugin("error_plugin")
                assert result is False

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """Тестирование жизненного цикла плагинов"""
        plugin_manager = PluginManager()

        # Загружаем плагин
        with patch.dict('sys.modules', {
            'plugins.test_plugin': MagicMock(),
        }):
            with patch('plugins.test_plugin.Plugin') as mock_plugin_class:
                mock_instance = MagicMock()
                mock_instance.setup.return_value = True
                mock_instance.teardown.return_value = None
                mock_plugin_class.return_value = mock_instance

                # Загрузка
                result = plugin_manager.load_plugin("test_plugin")
                assert result is True
                assert "test_plugin" in plugin_manager.loaded_plugins

                # Выгрузка
                result = plugin_manager.unload_plugin("test_plugin")
                assert result is True
                assert "test_plugin" not in plugin_manager.loaded_plugins

                # Проверяем вызов teardown
                mock_instance.teardown.assert_called_once()
