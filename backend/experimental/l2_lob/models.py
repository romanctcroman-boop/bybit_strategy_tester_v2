"""
L2 Order Book data models.

Compatible with backend.backtesting.universal_engine.order_book.OrderBookLevel.
"""

from dataclasses import dataclass, field


@dataclass
class L2Level:
    """Single price level (bid or ask)."""

    price: float
    size: float
    order_count: int = 1


@dataclass
class L2Snapshot:
    """
    Order book snapshot — bids (desc by price), asks (asc by price).

    Timestamp in milliseconds (Unix ms).
    """

    timestamp: int
    symbol: str
    bids: list[L2Level] = field(default_factory=list)
    asks: list[L2Level] = field(default_factory=list)
    update_id: int | None = None
    seq: int | None = None

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> float | None:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> float | None:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_bps(self) -> float | None:
        if self.spread and self.mid_price and self.mid_price > 0:
            return (self.spread / self.mid_price) * 10_000
        return None

    def to_order_book_levels(self) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        """Convert to (bids, asks) as list of (price, size) for OrderBookSimulator."""
        bids = [(l.price, l.size) for l in self.bids]
        asks = [(l.price, l.size) for l in self.asks]
        return bids, asks
