from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
    AsyncSession,
)
from asyncio import current_task
from core.config import load_config

config = load_config()


class DataBaseHelper:
    def __init__(self):
        self.engine = create_async_engine(
            f"mysql+aiomysql://{config.db.user}:{config.db.password}@{config.db.hostname}:{config.db.port}/{config.db.db_name}",
            echo=config.db.db_echo,
            pool_pre_ping=True,  # проверяет соединение перед использованием
            pool_recycle=1800,  # пересоздаёт каждые 30 минут (меньше чем wait_timeout)
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    def get_scope_session(self):
        session = async_scoped_session(session_factory=self.session_factory, scopefunc=current_task)
        return session

    async def scope_session_dependency(
        self,
    ) -> AsyncGenerator[async_scoped_session[AsyncSession | Any], Any]:
        session = self.get_scope_session()
        try:
            yield session
        finally:
            await session.remove()


db_helper = DataBaseHelper()
