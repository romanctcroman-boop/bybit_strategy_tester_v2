"""
L2 Order Book — экспериментальный модуль.

- Загрузка L2 снимков через Bybit API
- Хранение и replay для бэктеста
- Заготовка под Generative LOB (CGAN)
"""

from backend.experimental.l2_lob.bybit_client import fetch_orderbook
from backend.experimental.l2_lob.models import L2Level, L2Snapshot

__all__ = [
    "L2Level",
    "L2Snapshot",
    "fetch_orderbook",
]
