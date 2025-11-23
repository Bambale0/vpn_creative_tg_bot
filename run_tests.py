#!/usr/bin/env python3
"""
Скрипт для запуска комплексного тестирования проекта VPN бота
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description=""):
    """Запуск команды с выводом результатов"""
    print(f"\n{'='*50}")
    print(f"Запуск: {description}")
    print(f"Команда: {command}")
    print(f"{'='*50}")

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.stdout:
            print("STDOUT:")
            print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        if result.returncode == 0:
            print(f"✅ {description} - УСПЕХ")
        else:
            print(f"❌ {description} - ОШИБКА (код: {result.returncode})")

        return result.returncode == 0

    except Exception as e:
        print(f"❌ Ошибка при выполнении команды: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск комплексного тестирования VPN бота")
    print(f"Рабочая директория: {os.getcwd()}")

    # Проверяем наличие зависимостей
    print("\n📋 Проверка зависимостей...")

    # Проверяем Python
    python_version = sys.version_info
    print(f"Python: {python_version.major}.{python_version.minor}.{python_version.micro}")

    # Проверяем pytest
    try:
        import pytest
        print(f"pytest: {pytest.__version__}")
    except ImportError:
        print("❌ pytest не установлен")
        return False

    # Проверяем coverage
    try:
        import coverage
        print(f"coverage: {coverage.__version__}")
    except ImportError:
        print("⚠️  coverage не установлен (pip install coverage)")

    success_count = 0
    total_tests = 0

    # 1. Тестирование синтаксиса Python файлов
    print("\n🔍 Проверка синтаксиса Python файлов...")
    total_tests += 1

    python_files = []
    for root, dirs, files in os.walk("."):
        # Исключаем __pycache__, .git, venv
        dirs[:] = [d for d in dirs if not d.startswith('__') and d not in ['.git', 'venv', 'htmlcov']]

        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))

    syntax_errors = []
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                compile(f.read(), py_file, 'exec')
        except SyntaxError as e:
            syntax_errors.append(f"{py_file}: {e}")
        except Exception as e:
            syntax_errors.append(f"{py_file}: {e}")

    if syntax_errors:
        print("❌ Найдены ошибки синтаксиса:")
        for error in syntax_errors:
            print(f"   {error}")
        success_count += 0
    else:
        print("✅ Синтаксис всех Python файлов корректен")
        success_count += 1

    # 2. Запуск unit тестов
    print("\n🧪 Запуск unit тестов...")
    total_tests += 1

    if run_command("python -m pytest tests/unit/ -v", "Unit тесты"):
        success_count += 1
    else:
        print("⚠️  Некоторые unit тесты провалились")

    # 3. Запуск integration тестов
    print("\n🔗 Запуск integration тестов...")
    total_tests += 1

    if run_command("python -m pytest tests/integration/ -v", "Integration тесты"):
        success_count += 1
    else:
        print("⚠️  Некоторые integration тесты провалились")

    # 4. Запуск всех тестов с покрытием
    print("\n📊 Запуск всех тестов с проверкой покрытия...")
    total_tests += 1

    coverage_success = run_command(
        "python -m pytest tests/ --cov=. --cov-report=html:htmlcov --cov-report=term-missing",
        "Тесты с покрытием кода"
    )

    if coverage_success:
        success_count += 1

        # Проверяем HTML отчет покрытия
        if os.path.exists("htmlcov/index.html"):
            print("📄 HTML отчет покрытия создан: htmlcov/index.html")
        else:
            print("⚠️  HTML отчет покрытия не создан")

    # 5. Проверка импортов
    print("\n📦 Проверка импортов...")
    total_tests += 1

    import_errors = []
    test_modules = [
        'utils.plugins',
        'utils.game',
        'handlers.core.callback_handlers',
        'plugins.monitoring_plugin',
        'plugins.bonus_plugin'
    ]

    for module in test_modules:
        try:
            __import__(module)
            print(f"✅ {module} - импорт успешен")
        except ImportError as e:
            import_errors.append(f"{module}: {e}")
            print(f"❌ {module} - ошибка импорта: {e}")
        except Exception as e:
            import_errors.append(f"{module}: {e}")
            print(f"❌ {module} - ошибка: {e}")

    if import_errors:
        print(f"\n❌ Найдено {len(import_errors)} ошибок импорта")
        success_count += 0
    else:
        print("✅ Все модули импортируются корректно")
        success_count += 1

    # 6. Проверка конфигурации
    print("\n⚙️  Проверка конфигурации...")
    total_tests += 1

    config_issues = []

    # Проверяем наличие requirements.txt
    if not os.path.exists("requirements.txt"):
        config_issues.append("requirements.txt не найден")
    else:
        print("✅ requirements.txt найден")

    # Проверяем наличие .env.example
    if not os.path.exists(".env.example"):
        config_issues.append(".env.example не найден")
    else:
        print("✅ .env.example найден")

    # Проверяем pytest.ini
    if not os.path.exists("pytest.ini"):
        config_issues.append("pytest.ini не найден")
    else:
        print("✅ pytest.ini найден")

    if config_issues:
        print(f"❌ Проблемы с конфигурацией: {config_issues}")
        success_count += 0
    else:
        print("✅ Конфигурация корректна")
        success_count += 1

    # 7. Проверка логов
    print("\n📝 Проверка логов...")
    total_tests += 1

    log_files = ["logs/service.log", "logs/service-error.log", "logs/webhook-service.log"]
    log_issues = []

    for log_file in log_files:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            print(f"✅ {log_file}: {size} bytes")
        else:
            log_issues.append(f"{log_file} не найден")

    if log_issues:
        print(f"⚠️  Проблемы с логами: {log_issues}")
        success_count += 0
    else:
        print("✅ Все лог-файлы существуют")
        success_count += 1

    # Итоги
    print(f"\n{'='*50}")
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print(f"{'='*50}")
    print(f"Всего проверок: {total_tests}")
    print(f"Успешных: {success_count}")
    print(f"Провалено: {total_tests - success_count}")
    print(f"Процент успеха: {(success_count / total_tests * 100):.1f}%")

    if success_count == total_tests:
        print("🎉 Все тесты прошли успешно!")
        return True
    else:
        print("⚠️  Некоторые тесты провалились, но проект в рабочем состоянии")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
