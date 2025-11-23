"""
Модуль для работы с базой данных с оптимизациями для избежания блокировок
"""

import aiosqlite
import asyncio
import logging
from typing import Optional, Any, List, Tuple, Union
from contextlib import asynccontextmanager
from config.config import DB_PATH

log = logging.getLogger("database")

class DatabaseManager:
    """Менеджер базы данных с оптимизациями"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._pool: Optional[aiosqlite.Connection] = None
        self._pool_lock = asyncio.Lock()

    async def _get_connection(self) -> aiosqlite.Connection:
        """Получить соединение с оптимизациями"""
        async with self._pool_lock:
            if self._pool is None:
                self._pool = await aiosqlite.connect(
                    self.db_path,
                    timeout=30.0,  # Увеличенный timeout
                    isolation_level=None  # Автоматический commit
                )
                await self._setup_optimizations(self._pool)

        return self._pool

    async def _setup_optimizations(self, conn: aiosqlite.Connection):
        """Настройка оптимизаций SQLite"""
        try:
            # Включаем WAL mode для лучшей параллельности
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            await conn.execute("PRAGMA temp_store=MEMORY")
            await conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
            await conn.execute("PRAGMA foreign_keys=ON")

            # Проверяем, что WAL mode включен
            cursor = await conn.execute("PRAGMA journal_mode")
            result = await cursor.fetchone()
            if result and result[0] == 'wal':
                log.info("WAL mode enabled successfully")
            else:
                log.warning(f"WAL mode not enabled, current mode: {result}")

        except Exception as e:
            log.error(f"Error setting up database optimizations: {e}")

    @asynccontextmanager
    async def get_connection(self):
        """Context manager для получения соединения"""
        conn = await self._get_connection()
        try:
            yield conn
        except Exception as e:
            log.error(f"Database connection error: {e}")
            raise
        finally:
            # Не закрываем соединение, переиспользуем
            pass

    async def execute(self, query: str, parameters: tuple = ()) -> aiosqlite.Cursor:
        """Выполнить запрос с автоматической обработкой блокировок"""
        max_retries = 5
        retry_delay = 0.2

        for attempt in range(max_retries):
            try:
                async with self.get_connection() as conn:
                    cursor = await conn.execute(query, parameters)
                    await conn.commit()
                    return cursor

            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    log.warning(f"Database locked, retrying ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                elif "no such column" in str(e) or "no such table" in str(e):
                    # Это ошибка схемы, не повторяем
                    log.error(f"Database schema error: {e}")
                    raise
                else:
                    log.error(f"Database error: {e}")
                    raise

        raise Exception(f"Database operation failed after {max_retries} attempts")

    async def execute_many(self, query: str, parameters_list: list) -> None:
        """Выполнить несколько запросов"""
        max_retries = 3
        retry_delay = 0.2

        for attempt in range(max_retries):
            try:
                async with self.get_connection() as conn:
                    await conn.executemany(query, parameters_list)
                    await conn.commit()
                    return

            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    log.warning(f"Database locked in execute_many, retrying ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    log.error(f"Database execute_many error: {e}")
                    raise

        raise Exception(f"Database execute_many failed after {max_retries} attempts")

    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[Any]:
        """Получить одну запись"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                async with self.get_connection() as conn:
                    cursor = await conn.execute(query, parameters)
                    return await cursor.fetchone()

            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    log.warning(f"Database locked in fetch_one, retrying ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    log.error(f"Database fetch_one error: {e}")
                    raise

        return None

    async def fetch_all(self, query: str, parameters: tuple = ()) -> List[Any]:
        """Получить все записи"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                async with self.get_connection() as conn:
                    cursor = await conn.execute(query, parameters)
                    result = await cursor.fetchall()
                    return list(result)  # Конвертируем в list

            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    log.warning(f"Database locked in fetch_all, retrying ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    log.error(f"Database fetch_all error: {e}")
                    raise

        return []

    async def close(self):
        """Закрыть соединение"""
        async with self._pool_lock:
            if self._pool:
                await self._pool.close()
                self._pool = None
                log.info("Database connection closed")

# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()

async def init_database():
    """Инициализация базы данных с оптимизациями"""
    try:
        # Создаем соединение для инициализации
        async with aiosqlite.connect(DB_PATH, timeout=30.0) as conn:
            # Включаем WAL mode
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA foreign_keys=ON")

            # Проверяем статус
            cursor = await conn.execute("PRAGMA journal_mode")
            result = await cursor.fetchone()
            log.info(f"Database initialized with journal mode: {result[0] if result else 'unknown'}")

        log.info("Database initialization completed successfully")
        return True

    except Exception as e:
        log.error(f"Database initialization failed: {e}")
        return False

async def get_db_stats():
    """Получить статистику базы данных"""
    try:
        async with aiosqlite.connect(DB_PATH, timeout=10.0) as conn:
            # Получаем размер файла
            import os
            file_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

            # Получаем статистику таблиц
            cursor = await conn.execute("""
                SELECT name, COUNT(*) as count
                FROM sqlite_master
                WHERE type='table'
                GROUP BY name
            """)
            tables = await cursor.fetchall()

            stats = {
                "file_size_bytes": file_size,
                "file_size_mb": file_size / 1024 / 1024,
                "tables": {table[0]: table[1] for table in tables},
                "journal_mode": "unknown"
            }

            # Получаем journal mode
            cursor = await conn.execute("PRAGMA journal_mode")
            result = await cursor.fetchone()
            if result:
                stats["journal_mode"] = result[0]

            return stats

    except Exception as e:
        log.error(f"Error getting database stats: {e}")
        return {"error": str(e)}
