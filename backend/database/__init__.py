"""Асинхронное управление подключением к базе данных."""

from collections.abc import AsyncGenerator, Generator

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.core.config import settings

# Базовый класс моделей SQLAlchemy (используется ORM в backend.models)
Base = declarative_base()

# Асинхронный движок SQLAlchemy
engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# Фабрика асинхронных сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)

# Временная синхронная фабрика (legacy сервисы)
_sync_url = settings.database_url
if _sync_url.startswith("postgresql://"):
    _sync_url = _sync_url.replace("postgresql://", "postgresql+psycopg://", 1)

_sync_engine = create_engine(
    _sync_url,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_sync_engine,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость FastAPI для получения асинхронной сессии БД."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Создание схемы БД при первом запуске."""
    try:
        logger.info("🗄️  Инициализация базы данных...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.success("✅ База данных инициализирована")
    except Exception as exc:
        logger.error(f"❌ Ошибка инициализации базы данных: {exc}")
        raise


async def check_db_connection() -> bool:
    """Проверяем доступность БД."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Подключение к базе данных активно")
        return True
    except Exception as exc:
        logger.error(f"❌ Подключение к базе данных не удалось: {exc}")
        return False


__all__ = [
    "Base",
    "engine",
    "AsyncSessionLocal",
    "SessionLocal",
    "get_async_session",
    "get_db",
    "init_db",
    "check_db_connection",
]


# Переэкспорт Pydantic-схем и CRUD-операций
try:  # pragma: no cover - импорт для удобства использования
    from backend.database.async_crud import (
        create_backtest,
        create_strategy,
        create_trade,
        delete_strategy,
        get_backtest,
        get_backtests,
        get_recent_backtests,
        get_results_summary,
        get_strategies,
        get_strategy,
        get_strategy_performance,
        get_top_strategies,
        get_trades,
        update_backtest,
        update_strategy,
        update_trade,
    )
    from backend.database.models import (
        Backtest,
        BacktestCreate,
        BacktestStatus,
        BacktestUpdate,
        Optimization,
        OptimizationCreate,
        Strategy,
        StrategyCreate,
        StrategyUpdate,
        Trade,
        TradeCreate,
        TradeSide,
        TradeStatus,
        TradeUpdate,
    )

    __all__.extend(
        [
            # Pydantic-схемы
            "Strategy",
            "StrategyCreate",
            "StrategyUpdate",
            "Backtest",
            "BacktestCreate",
            "BacktestUpdate",
            "BacktestStatus",
            "Trade",
            "TradeCreate",
            "TradeUpdate",
            "TradeStatus",
            "TradeSide",
            "Optimization",
            "OptimizationCreate",
            # CRUD
            "create_strategy",
            "get_strategy",
            "get_strategies",
            "update_strategy",
            "delete_strategy",
            "create_backtest",
            "get_backtest",
            "get_backtests",
            "update_backtest",
            "create_trade",
            "get_trades",
            "update_trade",
            "get_strategy_performance",
            "get_top_strategies",
            "get_recent_backtests",
            "get_results_summary",
        ]
    )

    logger.info("✅ Асинхронные модули работы с PostgreSQL загружены")
except ImportError as exc:  # pragma: no cover
    logger.warning(f"⚠️  Не удалось загрузить PostgreSQL-модули: {exc}")


def get_db() -> Generator[Session, None, None]:
    """Legacy зависимость FastAPI для синхронных сервисов."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
