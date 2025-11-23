import pytest
import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Добавляем корневую директорию в sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.game import (
    add_user_points, check_achievements, get_trial, activate_trial,
    claim_daily_bonus, check_subscription, show_achievements,
    show_leaderboard, get_referral_info
)


class TestGameFunctions:

    @pytest.mark.asyncio
    async def test_add_user_points_success(self):
        """Тестирование успешного добавления очков"""
        with patch('utils.game.aiosqlite') as mock_sqlite:
            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (100,)  # текущие очки
            mock_cursor.execute.return_value = None
            mock_conn.commit.return_value = None
            mock_sqlite.connect.return_value = mock_conn

            result = await add_user_points(12345, 50, "test_reason")

            assert result is True
            assert mock_conn.execute.call_count >= 3  # SELECT, UPDATE, INSERT log

    @pytest.mark.asyncio
    async def test_add_user_points_new_user(self):
        """Тестирование добавления очков новому пользователю"""
        with patch('utils.game.aiosqlite') as mock_sqlite:
            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None  # пользователь не существует
            mock_cursor.execute.return_value = None
            mock_conn.commit.return_value = None
            mock_sqlite.connect.return_value = mock_conn

            result = await add_user_points(99999, 100, "new_user")

            assert result is True

    @pytest.mark.asyncio
    async def test_add_user_points_database_locked_retry(self):
        """Тестирование повторных попыток при блокировке БД"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.asyncio.sleep') as mock_sleep:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor

            # Первая попытка - ошибка блокировки
            mock_cursor.fetchone.side_effect = Exception("database is locked")
            mock_sqlite.connect.return_value = mock_conn

            result = await add_user_points(12345, 50, "test")

            # Должна быть повторная попытка
            assert mock_sleep.call_count > 0
            assert result is False  # после всех попыток

    @pytest.mark.asyncio
    async def test_check_achievements_first_purchase(self):
        """Тестирование достижения первой покупки"""
        with patch('utils.game.aiosqlite') as mock_sqlite:
            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor

            # Мокируем существующие достижения (пусто)
            mock_cursor.fetchall.return_value = []
            # Мокируем количество покупок (1 - первая)
            mock_cursor.fetchone.side_effect = [1]  # одна покупка
            mock_cursor.execute.return_value = None
            mock_conn.commit.return_value = None
            mock_sqlite.connect.return_value = mock_conn

            result = await check_achievements(12345, "first_purchase")

            assert result["first_purchase"] is True

    @pytest.mark.asyncio
    async def test_get_trial_already_used(self):
        """Тестирование trial для пользователя, который уже использовал"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.translate_func') as mock_translate:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (1,)  # trial уже использован
            mock_sqlite.connect.return_value = mock_conn

            mock_message = AsyncMock()
            mock_translate.return_value = "Trial уже использован"

            result = await get_trial(12345, mock_message)

            assert result is False
            mock_message.answer.assert_called_once_with("Trial уже использован")

    @pytest.mark.asyncio
    async def test_get_trial_success(self):
        """Тестирование успешной активации trial"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.datetime') as mock_datetime, \
             patch('utils.game.add_user_points') as mock_add_points, \
             patch('utils.game.translate_func') as mock_translate:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchone.side_effect = [(0,), None, None]  # trial не использован
            mock_cursor.execute.return_value = None
            mock_conn.commit.return_value = None
            mock_sqlite.connect.return_value = mock_conn

            mock_now = MagicMock()
            mock_datetime.utcnow.return_value = mock_now
            mock_datetime.fromisoformat.return_value = mock_now
            mock_now.strftime.return_value = "01.01.2023 12:00"
            mock_now.isoformat.return_value = "2023-01-01T12:00:00"

            mock_add_points.return_value = True
            mock_translate.return_value = "Trial активирован"

            mock_message = AsyncMock()

            result = await get_trial(12345, mock_message)

            assert result is True
            mock_add_points.assert_called_once_with(12345, 50, "trial_activation")

    @pytest.mark.asyncio
    async def test_claim_daily_bonus_already_claimed(self):
        """Тестирование ежедневного бонуса, уже полученного сегодня"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.translate_func') as mock_translate:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchone.return_value = ("2023-01-01 10:00:00",)  # уже получен
            mock_sqlite.connect.return_value = mock_conn

            mock_translate.return_value = "Бонус уже получен"
            mock_message = AsyncMock()

            result = await claim_daily_bonus(12345, mock_message)

            assert result is False
            mock_message.answer.assert_called_once_with("Бонус уже получен")

    @pytest.mark.asyncio
    async def test_claim_daily_bonus_success(self):
        """Тестирование успешного получения ежедневного бонуса"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.random.randint', return_value=25), \
             patch('utils.game.add_user_points') as mock_add_points, \
             patch('utils.game.check_achievements') as mock_check_ach, \
             patch('utils.game.translate_func') as mock_translate:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchone.side_effect = [None, (1, 10)]  # не получен, streak=1
            mock_cursor.execute.return_value = None
            mock_conn.commit.return_value = None
            mock_sqlite.connect.return_value = mock_conn

            mock_add_points.return_value = True
            mock_check_ach.return_value = {"daily_streak": False}
            mock_translate.return_value = "Бонус получен: 25 очков"

            mock_message = AsyncMock()

            result = await claim_daily_bonus(12345, mock_message)

            assert result is True
            mock_add_points.assert_called_once_with(12345, 25, "daily_bonus")

    @pytest.mark.asyncio
    async def test_check_subscription_admin(self):
        """Тестирование проверки подписки для админа"""
        with patch('utils.game.ADMIN_IDS', [12345]):
            mock_message = AsyncMock()
            result = await check_subscription(12345, mock_message)

            assert result["has_active"] is True
            assert result["is_admin"] is True
            assert result["days_remaining"] == 999999

    @pytest.mark.asyncio
    async def test_check_subscription_active(self):
        """Тестирование проверки активной подписки"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.datetime') as mock_datetime:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchone.return_value = ("2023-02-01T12:00:00", 0)  # активная подписка
            mock_sqlite.connect.return_value = mock_conn

            mock_now = MagicMock()
            mock_datetime.utcnow.return_value = mock_now
            mock_datetime.fromisoformat.return_value = mock_now
            mock_now.days = 30  # 30 дней до окончания

            mock_message = AsyncMock()
            result = await check_subscription(12345, mock_message)

            assert result["has_active"] is True
            assert result["days_remaining"] == 30

    @pytest.mark.asyncio
    async def test_show_achievements_no_achievements(self):
        """Тестирование показа достижений без достижений"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.translate_func') as mock_translate:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []  # нет достижений
            mock_sqlite.connect.return_value = mock_conn

            mock_translate.return_value = "У вас нет достижений"
            mock_message = AsyncMock()

            await show_achievements(12345, mock_message)

            mock_message.answer.assert_called_once_with("У вас нет достижений")

    @pytest.mark.asyncio
    async def test_show_achievements_with_achievements(self):
        """Тестирование показа достижений с достижениями"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.datetime') as mock_datetime, \
             patch('utils.game.translate_func') as mock_translate:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [
                ("first_purchase", "2023-01-01T12:00:00"),
                ("daily_streak", "2023-01-15T12:00:00")
            ]
            mock_sqlite.connect.return_value = mock_conn

            mock_now = MagicMock()
            mock_datetime.fromisoformat.return_value = mock_now
            mock_now.strftime.return_value = "01.01.2023"

            mock_translate.side_effect = [
                "Ваши достижения:",  # header
                "Первая покупка",    # first_purchase
                "Серия дней"         # daily_streak
            ]

            mock_message = AsyncMock()

            await show_achievements(12345, mock_message)

            # Должно быть вызвано 3 раза: header + 2 достижения
            assert mock_translate.call_count == 3

    @pytest.mark.asyncio
    async def test_show_leaderboard_empty(self):
        """Тестирование таблицы лидеров без пользователей"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.translate_func') as mock_translate:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []  # нет лидеров
            mock_sqlite.connect.return_value = mock_conn

            mock_translate.return_value = "Таблица лидеров пуста"
            mock_message = AsyncMock()

            await show_leaderboard(12345, mock_message)

            mock_message.answer.assert_called_once_with("Таблица лидеров пуста")

    @pytest.mark.asyncio
    async def test_show_leaderboard_with_leaders(self):
        """Тестирование таблицы лидеров с лидерами"""
        with patch('utils.game.aiosqlite') as mock_sqlite, \
             patch('utils.game.translate_func') as mock_translate:

            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor

            # Мокируем лидеров
            mock_cursor.fetchall.side_effect = [
                [(111, 1000), (222, 800), (333, 600)],  # топ 3
                [(None, None)],  # user info для первого лидера
                [(None, None)],  # для второго
                [(None, None)],  # для третьего
                (500,),  # очки текущего пользователя
                (2,)     # позиция пользователя (3 место)
            ]
            mock_sqlite.connect.return_value = mock_conn

            mock_translate.side_effect = [
                "🏆 Таблица лидеров",  # header
                "Таблица лидеров пуста"  # не используется
            ]

            mock_message = AsyncMock()

            await show_leaderboard(12345, mock_message)

            # Должно быть отправлено сообщение с лидерами
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "🏆" in call_args
            assert "111" in call_args  # ID первого лидера

    @pytest.mark.asyncio
    async def test_get_referral_info(self):
        """Тестирование получения реферальной информации"""
        with patch('utils.game.aiosqlite') as mock_sqlite:
            mock_conn = AsyncMock()
            mock_cursor = AsyncMock()
            mock_conn.execute.return_value = mock_cursor

            mock_cursor.fetchone.side_effect = [
                (5,),   # referral_count
                (250,), # total_bonus
            ]
            mock_cursor.fetchall.return_value = [
                (111, 30, "2023-01-01"),
                (222, 20, "2023-01-02")
            ]
            mock_sqlite.connect.return_value = mock_conn

            result = await get_referral_info(12345)

            assert result["referral_count"] == 5
            assert result["total_bonus"] == 250
            assert len(result["recent_bonuses"]) == 2
