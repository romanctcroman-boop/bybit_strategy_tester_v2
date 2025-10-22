from typing import Any, Dict, Protocol, TypedDict

from backend.core.backtest_engine import BacktestEngine


class EngineResult(TypedDict, total=False):
    final_capital: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    trades: list
    metrics: Dict[str, Any]
    error: str


class IBacktestEngine(Protocol):
    def run(self, data: Any, strategy_config: dict) -> EngineResult: ...


def get_engine(name: str | None = None, **kwargs) -> IBacktestEngine:
    """Return an engine instance by name. For now return BacktestEngine.

    Extendable: map names to different engine implementations.
    """
    # future: lookup table
    return BacktestEngine(**kwargs)
