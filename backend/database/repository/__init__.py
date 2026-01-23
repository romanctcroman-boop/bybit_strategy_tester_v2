"""
Repository Pattern - Package exports

Usage:
    from backend.database.repository import KlineRepository, UnitOfWork

    with UnitOfWork() as uow:
        repo = KlineRepository(uow.session)
        repo.bulk_upsert('BTCUSDT', '15', candles)
"""

from .base_repository import BaseRepository
from .kline_repository import KlineRepository

__all__ = [
    "BaseRepository",
    "KlineRepository",
]
