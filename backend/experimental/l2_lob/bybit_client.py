"""
Bybit L2 Order Book client.

Fetches order book snapshots via Bybit REST API.
"""

import logging
from typing import Any

from backend.experimental.l2_lob.models import L2Level, L2Snapshot
from backend.services.adapters.bybit import BybitAdapter

logger = logging.getLogger(__name__)


def _parse_levels(raw: list[list[Any]]) -> list[L2Level]:
    """Parse Bybit format [[price_str, size_str], ...] to L2Level list."""
    out = []
    for row in raw or []:
        if len(row) >= 2:
            try:
                price = float(row[0])
                size = float(row[1])
                out.append(L2Level(price=price, size=size))
            except (TypeError, ValueError):
                continue
    return out


def fetch_orderbook(
    symbol: str = "BTCUSDT",
    category: str = "linear",
    limit: int = 50,
    adapter: BybitAdapter | None = None,
) -> L2Snapshot | None:
    """
    Fetch L2 order book snapshot from Bybit.

    Args:
        symbol: Trading pair
        category: spot, linear, inverse, option
        limit: Depth levels (linear: 1-500)
        adapter: BybitAdapter instance (creates default if None)

    Returns:
        L2Snapshot or None on error
    """
    adp = adapter or BybitAdapter()
    raw = adp.get_orderbook(symbol=symbol, category=category, limit=limit)
    if not raw:
        return None

    bids = _parse_levels(raw.get("b") or raw.get("bids", []))
    asks = _parse_levels(raw.get("a") or raw.get("asks", []))
    ts = int(raw.get("ts", 0) or raw.get("timestamp", 0))
    update_id = raw.get("u")
    seq = raw.get("seq")
    sym = str(raw.get("s", symbol))

    return L2Snapshot(
        timestamp=ts,
        symbol=sym,
        bids=bids,
        asks=asks,
        update_id=update_id,
        seq=seq,
    )
