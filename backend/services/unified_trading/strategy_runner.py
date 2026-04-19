"""
Strategy Runner — единая точка входа Backtest / Paper / Live.

Использует DataProvider и OrderExecutor для переключения режимов.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.services.unified_trading.interfaces import (
    DataProvider,
    OrderExecutorInterface,
)


@dataclass
class RunResult:
    """Результат прогона стратегии."""

    mode: str  # "backtest" | "paper" | "live"
    trades: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    final_equity: float = 0.0
    total_pnl: float = 0.0
    error: str | None = None


class StrategyRunner:
    """
    Оркестратор: DataProvider + OrderExecutor.

    Пример:
        data = HistoricalDataProvider(db)
        exec_ = SimulatedExecutor()
        runner = StrategyRunner(data, exec_)
        result = runner.run_backtest(symbol="BTCUSDT", interval="60", strategy_fn=my_strategy)
    """

    def __init__(
        self,
        data_provider: DataProvider,
        order_executor: OrderExecutorInterface,
        initial_capital: float = 10000.0,
    ):
        self.data_provider = data_provider
        self.order_executor = order_executor
        self.initial_capital = initial_capital

    def run_backtest(
        self,
        symbol: str,
        interval: str,
        limit: int,
        strategy_fn: Callable[[Any], tuple[bool, bool, float]],
        mode: str = "backtest",
    ) -> RunResult:
        """
        Прогон стратегии на исторических данных.

        strategy_fn(df) -> (long_signal, short_signal, size)
        """
        df = self.data_provider.get_klines(symbol, interval, limit)
        if df.empty or len(df) < 2:
            return RunResult(
                mode=mode,
                error="No data from provider",
            )

        # Mutable ref для цены (обновляется в цикле)
        _current_price: list[float] = [float(df["close"].iloc[0])]
        if hasattr(self.order_executor, "set_price_provider"):
            self.order_executor.set_price_provider(lambda s: _current_price[0])

        equity = self.initial_capital
        trades = []
        equity_curve = [equity]

        for i in range(1, len(df)):
            row = df.iloc[i]
            _current_price[0] = float(row["close"])
            # Упрощённо: strategy_fn получает текущий бар и историю
            try:
                long_sig, short_sig, size = strategy_fn(df.iloc[: i + 1])
            except Exception as e:
                return RunResult(mode=mode, error=str(e))

            current_price = float(row["close"])
            if size <= 0:
                size = 0.01

            if long_sig:
                res = self.order_executor.place_market_order(symbol, "buy", size)
                if res.status == "filled" and res.filled_qty > 0:
                    pnl = res.filled_qty * (current_price - res.filled_price)
                    equity += pnl
                    trades.append({"side": "long", "pnl": pnl, "price": res.filled_price})
            elif short_sig:
                res = self.order_executor.place_market_order(symbol, "sell", size)
                if res.status == "filled" and res.filled_qty > 0:
                    pnl = res.filled_qty * (res.filled_price - current_price)
                    equity += pnl
                    trades.append({"side": "short", "pnl": pnl, "price": res.filled_price})

            equity_curve.append(equity)

        return RunResult(
            mode=mode,
            trades=trades,
            equity_curve=equity_curve,
            final_equity=equity,
            total_pnl=equity - self.initial_capital,
        )
