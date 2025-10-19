"""Alembic environment configured for asyncio SQLAlchemy."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from backend.core.config import settings
from backend.database import Base

# Alembic Config object
config = context.config

# Поддерживаем переопределение URL через переменные окружения
alembic_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL")
if alembic_url:
    config.set_main_option("sqlalchemy.url", alembic_url)
else:
    config.set_main_option("sqlalchemy.url", settings.async_database_url)

# Настройка логирования
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные моделей
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запускаем миграции в оффлайн-режиме."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Запускаем миграции в онлайн-режиме с асинхронным движком."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
