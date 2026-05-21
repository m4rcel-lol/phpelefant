from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from phpelefant_discord.db.base import Base
from phpelefant_discord.db import models  # noqa: F401


def make_engine(database_url: str) -> AsyncEngine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_async_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_database(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(ensure_compatibility_columns)


def ensure_compatibility_columns(connection) -> None:
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    if "guild_settings" in table_names:
        existing = {column["name"] for column in inspector.get_columns("guild_settings")}
        if "welcome_dm_enabled" not in existing:
            connection.execute(
                text("ALTER TABLE guild_settings ADD COLUMN welcome_dm_enabled BOOLEAN DEFAULT false NOT NULL")
            )
    if "ticket_configs" in table_names:
        existing = {column["name"] for column in inspector.get_columns("ticket_configs")}
        if "ticket_categories" not in existing:
            connection.execute(
                text(
                    "ALTER TABLE ticket_configs "
                    "ADD COLUMN ticket_categories TEXT DEFAULT 'General Support|Billing|Bug Report|Staff Report|Appeal' NOT NULL"
                )
            )
    if "tickets" in table_names:
        existing = {column["name"] for column in inspector.get_columns("tickets")}
        if "category" not in existing:
            connection.execute(
                text("ALTER TABLE tickets ADD COLUMN category VARCHAR(64) DEFAULT 'General Support' NOT NULL")
            )


@asynccontextmanager
async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
