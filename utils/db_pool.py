"""
Модуль пула соединений для базы данных
"""
import asyncio
import aiosqlite
from typing import Optional, List
from config.config import DB_PATH


class DatabasePool:
    """Простой пул соединений для SQLite"""

    def __init__(self, pool_size: int = 10):
        self.pool_size = pool_size
        self.connections: List[aiosqlite.Connection] = []
        self.available: List[aiosqlite.Connection] = []
        self.lock = asyncio.Lock()
        self.initialized = False

    async def initialize(self):
        """Инициализация пула соединений"""
        if self.initialized:
            return

        for _ in range(self.pool_size):
            conn = await aiosqlite.connect(DB_PATH, timeout=5)
            self.connections.append(conn)
            self.available.append(conn)

        self.initialized = True

    async def get_connection(self) -> aiosqlite.Connection:
        """Получить соединение из пула"""
        await self.initialize()

        async with self.lock:
            if self.available:
                conn = self.available.pop()
                return conn
            else:
                # Если пул пуст, создаем временное соединение
                return await aiosqlite.connect(DB_PATH, timeout=5)

    async def return_connection(self, conn: aiosqlite.Connection):
        """Вернуть соединение в пул"""
        async with self.lock:
            if conn in self.connections:
                self.available.append(conn)
            else:
                # Временное соединение - закрываем
                await conn.close()

    async def close_all(self):
        """Закрыть все соединения пула"""
        async with self.lock:
            for conn in self.connections:
                await conn.close()
            self.connections.clear()
            self.available.clear()

# Глобальный пул соединений
db_pool = DatabasePool(pool_size=5)

async def get_db_connection() -> aiosqlite.Connection:
    """Получить соединение из пула"""
    return await db_pool.get_connection()

async def return_db_connection(conn: aiosqlite.Connection):
    """Вернуть соединение в пул"""
    await db_pool.return_connection(conn)

async def close_db_connections():
    """Закрыть все соединения пула"""
    await db_pool.close_all()
