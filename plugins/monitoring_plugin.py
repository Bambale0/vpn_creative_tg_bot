"""
Плагин мониторинга для VPN бота
"""

import psutil
import os
import hashlib
import logging
import time
from typing import Dict, List, Any
from pathlib import Path

log = logging.getLogger("plugins.monitoring")

class Plugin:
    """Плагин мониторинга системы"""

    version = "2.0.0"
    description = "Мониторинг системы, безопасности и метрик бота"
    author = "VPN Bot Team"

    def __init__(self):
        self.enabled = False

    async def setup(self) -> bool:
        """Инициализация плагина"""
        try:
            # Проверяем наличие psutil
            import psutil
            self.enabled = True
            log.info("Плагин мониторинга успешно инициализирован")
            return True
        except ImportError:
            log.error("psutil не установлен. Установите: pip install psutil")
            return False
        except Exception as e:
            log.error(f"Ошибка инициализации плагина мониторинга: {e}")
            return False

    def teardown(self) -> None:
        """Очистка ресурсов"""
        self.enabled = False
        log.info("Плагин мониторинга выгружен")

    def get_real_time_metrics(self) -> Dict[str, Any]:
        """Получение реальных метрик системы"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()

            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used': memory.used / 1024 / 1024,  # MB
                'memory_total': memory.total / 1024 / 1024,  # MB
                'disk_percent': disk.percent,
                'disk_used': disk.used / 1024 / 1024 / 1024,  # GB
                'disk_total': disk.total / 1024 / 1024 / 1024,  # GB
                'network_sent': network.bytes_sent / 1024 / 1024,  # MB
                'network_recv': network.bytes_recv / 1024 / 1024,  # MB
            }
        except Exception as e:
            log.error(f"Ошибка получения метрик: {e}")
            return {}

    def get_system_info(self) -> Dict[str, Any]:
        """Получение информации о системе"""
        try:
            return {
                'cpu_count': psutil.cpu_count(),
                'cpu_freq': psutil.cpu_freq().current if psutil.cpu_freq() else None,
                'load_average': psutil.getloadavg(),
                'boot_time': psutil.boot_time(),
                'processes': len(psutil.pids()),
            }
        except Exception as e:
            log.error(f"Ошибка получения системной информации: {e}")
            return {}

    def check_security(self) -> Dict[str, Any]:
        """Проверка безопасности"""
        try:
            # Проверка открытых портов
            open_ports = []
            for conn in psutil.net_connections():
                if conn.status == 'LISTEN':
                    open_ports.append({
                        'port': conn.laddr.port if conn.laddr else 'unknown',
                        'protocol': 'TCP' if conn.type == 1 else 'UDP'
                    })

            # Проверка целостности файлов
            critical_files = [
                'config/config.py',
                'main_scripts/main.py',
                'start_webhook_bot.py',
                'data/subscriptions.db'
            ]

            file_integrity = {}
            for file_path in critical_files:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        file_integrity[file_path] = hashlib.md5(f.read()).hexdigest()
                else:
                    file_integrity[file_path] = 'not_found'

            return {
                'open_ports': open_ports,
                'file_integrity': file_integrity,
                'threats_detected': len([p for p in open_ports if p['port'] in [22, 80, 443, 8000, 8001]]),
            }
        except Exception as e:
            log.error(f"Ошибка проверки безопасности: {e}")
            return {}

    def get_database_stats(self) -> Dict[str, Any]:
        """Статистика базы данных"""
        try:
            db_files = ['data/subscriptions.db', 'data/users.db', 'data/vpn_bot.db']
            stats = {}

            for db_file in db_files:
                if os.path.exists(db_file):
                    size = os.path.getsize(db_file) / 1024 / 1024  # MB
                    stats[db_file] = {
                        'size_mb': size,
                        'exists': True
                    }
                else:
                    stats[db_file] = {'size_mb': 0, 'exists': False}

            return stats
        except Exception as e:
            log.error(f"Ошибка получения статистики БД: {e}")
            return {}

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Полный отчет мониторинга"""
        return {
            'status': 'active' if self.enabled else 'inactive',
            'version': self.version,
            'system': self.get_system_info(),
            'metrics': self.get_real_time_metrics(),
            'security': self.check_security(),
            'database': self.get_database_stats(),
            'timestamp': time.time() if self.enabled else None,
        }

    def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """Получение алертов производительности"""
        alerts = []
        metrics = self.get_real_time_metrics()

        if metrics.get('cpu_percent', 0) > 90:
            alerts.append({
                'type': 'critical',
                'message': 'Высокая нагрузка CPU',
                'value': metrics['cpu_percent']
            })
        elif metrics.get('cpu_percent', 0) > 70:
            alerts.append({
                'type': 'warning',
                'message': 'Повышенная нагрузка CPU',
                'value': metrics['cpu_percent']
            })

        if metrics.get('memory_percent', 0) > 90:
            alerts.append({
                'type': 'critical',
                'message': 'Высокое использование памяти',
                'value': metrics['memory_percent']
            })

        if metrics.get('disk_percent', 0) > 90:
            alerts.append({
                'type': 'critical',
                'message': 'Мало места на диске',
                'value': metrics['disk_percent']
            })

        return alerts

    def generate_security_report(self) -> str:
        """Генерация отчета по безопасности"""
        try:
            security = self.check_security()
            report = "🔒 <b>Отчет по безопасности</b>\n\n"

            # Открытые порты
            report += f"🌐 <b>Открытые порты:</b> {len(security.get('open_ports', []))}\n"
            for port in security.get('open_ports', []):
                report += f"   • Порт {port['port']} ({port['protocol']})\n"

            # Целостность файлов
            report += f"\n📁 <b>Целостность файлов:</b>\n"
            for file_path, hash_value in security.get('file_integrity', {}).items():
                status = "✅ OK" if hash_value != 'not_found' else "❌ Не найден"
                report += f"   • {file_path}: {status}\n"

            # Угрозы
            threats = security.get('threats_detected', 0)
            report += f"\n⚠️ <b>Обнаружено угроз:</b> {threats}\n"

            if threats == 0:
                report += "✅ Система в безопасности\n"
            else:
                report += "⚠️ Рекомендуется проверить систему\n"

            return report

        except Exception as e:
            log.error(f"Ошибка генерации отчета безопасности: {e}")
            return f"❌ Ошибка при генерации отчета: {str(e)}"

# Экземпляр плагина
monitoring_plugin = Plugin()
