import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем корневую директорию в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from plugins.monitoring_plugin import Plugin as MonitoringPlugin
from plugins.bonus_plugin import Plugin as BonusPlugin


class TestMonitoringPlugin:

    @pytest.fixture
    def monitoring_plugin(self):
        """Фикстура для плагина мониторинга"""
        return MonitoringPlugin()

    def test_plugin_initialization(self, monitoring_plugin):
        """Тестирование инициализации плагина"""
        assert monitoring_plugin.version == "2.0.0"
        assert monitoring_plugin.description == "Мониторинг системы, безопасности и метрик бота"
        assert monitoring_plugin.author == "VPN Bot Team"
        assert not monitoring_plugin.enabled

    def test_setup_success(self, monitoring_plugin):
        """Тестирование успешной инициализации"""
        with patch.dict('sys.modules', {'psutil': MagicMock()}):
            result = monitoring_plugin.setup()
            assert result is True
            assert monitoring_plugin.enabled is True

    def test_setup_failure_no_psutil(self, monitoring_plugin):
        """Тестирование неудачной инициализации без psutil"""
        with patch.dict('sys.modules', {'psutil': None}):
            result = monitoring_plugin.setup()
            assert result is False
            assert monitoring_plugin.enabled is False

    def test_teardown(self, monitoring_plugin):
        """Тестирование выгрузки плагина"""
        monitoring_plugin.enabled = True
        monitoring_plugin.teardown()
        assert monitoring_plugin.enabled is False

    def test_get_real_time_metrics(self, monitoring_plugin):
        """Тестирование получения реальных метрик"""
        monitoring_plugin.enabled = True

        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value = MagicMock(percent=60.0, used=1024*1024*1024, total=2*1024*1024*1024)
        mock_psutil.disk_usage.return_value = MagicMock(percent=70.0, used=100*1024*1024*1024, total=200*1024*1024*1024)
        mock_psutil.net_io_counters.return_value = MagicMock(bytes_sent=1024*1024, bytes_recv=2*1024*1024)

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            metrics = monitoring_plugin.get_real_time_metrics()

            assert 'cpu_percent' in metrics
            assert 'memory_percent' in metrics
            assert 'disk_percent' in metrics
            assert 'network_sent' in metrics
            assert metrics['cpu_percent'] == 50.0
            assert metrics['memory_percent'] == 60.0

    def test_get_system_info(self, monitoring_plugin):
        """Тестирование получения системной информации"""
        monitoring_plugin.enabled = True

        mock_psutil = MagicMock()
        mock_psutil.cpu_count.return_value = 4
        mock_psutil.cpu_freq.return_value = MagicMock(current=2.5)
        mock_psutil.getloadavg.return_value = (1.0, 1.5, 2.0)
        mock_psutil.boot_time.return_value = 1234567890
        mock_psutil.pids.return_value = [1, 2, 3, 4, 5]

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            info = monitoring_plugin.get_system_info()

            assert info['cpu_count'] == 4
            assert info['load_average'] == (1.0, 1.5, 2.0)
            assert info['processes'] == 5

    def test_check_security(self, monitoring_plugin):
        """Тестирование проверки безопасности"""
        monitoring_plugin.enabled = True

        mock_psutil = MagicMock()
        mock_conn = MagicMock()
        mock_conn.status = 'LISTEN'
        mock_conn.laddr.port = 80
        mock_conn.type = 1
        mock_psutil.net_connections.return_value = [mock_conn]

        with patch.dict('sys.modules', {'psutil': mock_psutil}), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', MagicMock()) as mock_open:

            # Мокируем чтение файла
            mock_file = MagicMock()
            mock_file.read.return_value = b'test content'
            mock_open.return_value.__enter__.return_value = mock_file

            security = monitoring_plugin.check_security()

            assert 'open_ports' in security
            assert 'file_integrity' in security
            assert 'threats_detected' in security
            assert len(security['open_ports']) == 1
            assert security['open_ports'][0]['port'] == 80

    def test_get_performance_alerts(self, monitoring_plugin):
        """Тестирование получения алертов производительности"""
        monitoring_plugin.enabled = True

        with patch.object(monitoring_plugin, 'get_real_time_metrics') as mock_metrics:
            # Тестируем критический CPU
            mock_metrics.return_value = {'cpu_percent': 95.0, 'memory_percent': 50.0, 'disk_percent': 50.0}
            alerts = monitoring_plugin.get_performance_alerts()

            assert len(alerts) == 1
            assert alerts[0]['type'] == 'critical'
            assert 'CPU' in alerts[0]['message']

    def test_generate_security_report(self, monitoring_plugin):
        """Тестирование генерации отчета безопасности"""
        monitoring_plugin.enabled = True

        with patch.object(monitoring_plugin, 'check_security') as mock_security:
            mock_security.return_value = {
                'open_ports': [{'port': 80, 'protocol': 'TCP'}],
                'file_integrity': {'config/config.py': 'hash123'},
                'threats_detected': 1
            }

            report = monitoring_plugin.generate_security_report()

            assert '🔒' in report
            assert 'Открытые порты' in report
            assert 'Целостность файлов' in report
            assert 'Обнаружено угроз: 1' in report


class TestBonusPlugin:

    @pytest.fixture
    def bonus_plugin(self):
        """Фикстура для плагина бонусов"""
        return BonusPlugin()

    def test_plugin_initialization(self, bonus_plugin):
        """Тестирование инициализации плагина"""
        assert bonus_plugin.version == "1.0.0"
        assert bonus_plugin.description == "Система бонусов и наград для пользователей"
        assert bonus_plugin.author == "VPN Bot Team"
        assert not bonus_plugin.enabled

    def test_setup_success(self, bonus_plugin):
        """Тестирование успешной инициализации"""
        mock_sqlite = MagicMock()
        mock_conn = MagicMock()
        mock_sqlite.connect.return_value = mock_conn

        with patch.dict('sys.modules', {'sqlite3': mock_sqlite}):
            result = bonus_plugin.setup()
            assert result is True
            assert bonus_plugin.enabled is True

    def test_setup_failure(self, bonus_plugin):
        """Тестирование неудачной инициализации"""
        mock_sqlite = MagicMock()
        mock_sqlite.connect.side_effect = Exception("DB Error")

        with patch.dict('sys.modules', {'sqlite3': mock_sqlite}):
            result = bonus_plugin.setup()
            assert result is False
            assert bonus_plugin.enabled is False

    def test_teardown(self, bonus_plugin):
        """Тестирование выгрузки плагина"""
        bonus_plugin.enabled = True
        bonus_plugin.teardown()
        assert bonus_plugin.enabled is False

    @pytest.mark.asyncio
    async def test_give_bonus_success(self, bonus_plugin):
        """Тестирование успешной выдачи бонуса"""
        bonus_plugin.enabled = True

        mock_sqlite = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite.connect.return_value = mock_conn

        with patch.dict('sys.modules', {'sqlite3': mock_sqlite}), \
             patch('plugins.bonus_plugin.datetime') as mock_datetime:

            # Мокируем пользователя
            mock_cursor.fetchone.return_value = (1,)  # user exists
            mock_cursor.execute.return_value = None
            mock_conn.commit.return_value = None

            mock_now = MagicMock()
            mock_datetime.now.return_value = mock_now
            mock_datetime.utcnow.return_value = mock_now
            mock_now.strftime.return_value = "2023-01-01_12:00:00"

            result = await bonus_plugin.give_bonus(12345, 30, "Test bonus")

            assert result['success'] is True
            assert result['days'] == 30

    @pytest.mark.asyncio
    async def test_give_bonus_user_not_found(self, bonus_plugin):
        """Тестирование выдачи бонуса несуществующему пользователю"""
        bonus_plugin.enabled = True

        mock_sqlite = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite.connect.return_value = mock_conn

        with patch.dict('sys.modules', {'sqlite3': mock_sqlite}):
            # Пользователь не найден
            mock_cursor.fetchone.return_value = None

            result = await bonus_plugin.give_bonus(99999, 30, "Test bonus")

            assert result['success'] is False
            assert result['error'] == "User not found"

    @pytest.mark.asyncio
    async def test_get_stats(self, bonus_plugin):
        """Тестирование получения статистики"""
        bonus_plugin.enabled = True

        mock_sqlite = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite.connect.return_value = mock_conn

        with patch.dict('sys.modules', {'sqlite3': mock_sqlite}), \
             patch('plugins.bonus_plugin.datetime') as mock_datetime:

            # Мокируем результаты запросов
            mock_cursor.fetchone.side_effect = [
                (10,),  # total_bonuses
                (300,),  # total_days
                (5,),   # recent_bonuses
                (150,)  # recent_days
            ]

            mock_now = MagicMock()
            mock_datetime.now.return_value = mock_now
            mock_datetime.timedelta.return_value = mock_now

            result = await bonus_plugin.get_stats()

            assert result['success'] is True
            assert result['total_bonuses'] == 10
            assert result['total_days'] == 300
            assert result['recent_bonuses'] == 5

    def test_get_info(self, bonus_plugin):
        """Тестирование получения информации о плагине"""
        info = bonus_plugin.get_info()

        assert info['name'] == 'bonus_plugin'
        assert info['version'] == '1.0.0'
        assert info['description'] == 'Система бонусов и наград для пользователей'
        assert info['author'] == 'VPN Bot Team'
        assert 'enabled' in info
