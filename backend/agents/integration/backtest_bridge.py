"""
Backtest Bridge — converts LLM StrategyDefinition to BacktestEngine input.

This module bridges the gap between:
- LLM output (StrategyDefinition with signals, filters, exit conditions)
- Engine input (BacktestInput with numpy arrays of entry/exit signals)

Pipeline:
    StrategyDefinition
        → map to strategy_type + params
        → generate_signals_for_strategy()
        → BacktestInput
        → FallbackEngineV4.run()
        → metrics dict
"""

from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd
from loguru import logger

from backend.agents.prompts.response_parser import StrategyDefinition


class BacktestBridge:
    """
    Bridge between LLM-generated strategies and the backtest engine.

    Converts StrategyDefinition → BacktestInput → BacktestOutput → metrics dict.

    Uses FallbackEngineV4 (gold standard) and the universal signal dispatcher.

    Example:
        bridge = BacktestBridge()
        metrics = await bridge.run_strategy(
            strategy=strategy_def,
            symbol="BTCUSDT",
            timeframe="15",
            df=ohlcv_df,
            initial_capital=10000,
            leverage=10,
        )
        print(f"Sharpe: {metrics['sharpe_ratio']}")
    """

    # Commission rate — CRITICAL: must match TradingView parity
    COMMISSION_RATE = 0.0007

    def __init__(self) -> None:
        self._engine = None

    def _get_engine(self):
        """Lazy-load FallbackEngineV4."""
        if self._engine is None:
            from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4

            self._engine = FallbackEngineV4()
        return self._engine

    async def run_strategy(
        self,
        strategy: StrategyDefinition,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        initial_capital: float = 10000,
        leverage: int = 1,
        direction: str = "both",
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[str, Any]:
        """
        Convert StrategyDefinition to engine format, run backtest, return metrics.

        Args:
            strategy: LLM-generated StrategyDefinition
            symbol: Trading pair (e.g. "BTCUSDT")
            timeframe: Candle interval (e.g. "15", "60")
            df: OHLCV DataFrame (columns: open, high, low, close, volume)
            initial_capital: Starting capital in USDT
            leverage: Trading leverage
            direction: "long", "short", or "both"
            stop_loss: Override SL from strategy (fraction, e.g. 0.02 = 2%)
            take_profit: Override TP from strategy (fraction, e.g. 0.03 = 3%)

        Returns:
            Dict with backtest metrics (sharpe_ratio, max_drawdown, etc.)
        """
        # Map StrategyDefinition to engine params
        strategy_type = strategy.get_strategy_type_for_engine()
        strategy_params = strategy.get_engine_params()

        logger.info(
            f"🔗 BacktestBridge: running '{strategy.strategy_name}' as {strategy_type} with params={strategy_params}"
        )

        # Extract SL/TP from strategy exit conditions (if not overridden)
        if stop_loss is None:
            stop_loss = self._extract_stop_loss(strategy)
        if take_profit is None:
            take_profit = self._extract_take_profit(strategy)

        # Run in thread pool (engine is sync)
        result = await asyncio.to_thread(
            self._run_backtest_sync,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            df=df,
            symbol=symbol,
            timeframe=timeframe,
            initial_capital=initial_capital,
            leverage=leverage,
            direction=direction,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        return result

    def _run_backtest_sync(
        self,
        strategy_type: str,
        strategy_params: dict[str, Any],
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        initial_capital: float,
        leverage: int,
        direction: str,
        stop_loss: float,
        take_profit: float,
    ) -> dict[str, Any]:
        """Synchronous backtest execution."""
        from backend.backtesting.interfaces import BacktestInput, TradeDirection
        from backend.backtesting.signal_generators import generate_signals_for_strategy

        engine = self._get_engine()

        # Generate signals
        try:
            long_entries, long_exits, short_entries, short_exits = generate_signals_for_strategy(
                candles=df,
                strategy_type=strategy_type,
                params=strategy_params,
                direction=direction,
            )
        except ValueError as e:
            logger.error(f"Signal generation failed: {e}")
            return {"error": str(e), "total_trades": 0}

        # Map direction
        dir_map = {
            "long": TradeDirection.LONG_ONLY,
            "short": TradeDirection.SHORT_ONLY,
            "both": TradeDirection.BOTH,
        }
        trade_direction = dir_map.get(direction, TradeDirection.BOTH)

        # Build BacktestInput
        bt_input = BacktestInput(
            candles=df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol=symbol,
            interval=timeframe,
            initial_capital=initial_capital,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            taker_fee=self.COMMISSION_RATE,
            direction=trade_direction,
        )

        # Run engine
        output = engine.run(bt_input)

        if not output.is_valid:
            logger.warning(f"Backtest invalid: {output.validation_errors}")
            return {
                "error": "; ".join(output.validation_errors),
                "total_trades": 0,
            }

        # Extract metrics
        m = output.metrics
        return {
            "net_pnl": m.net_pnl,
            "total_return_pct": m.total_return_pct,
            "sharpe_ratio": m.sharpe_ratio,
            "max_drawdown_pct": m.max_drawdown_pct,
            "win_rate": m.win_rate,
            "profit_factor": m.profit_factor,
            "total_trades": m.total_trades,
            "winning_trades": m.winning_trades,
            "losing_trades": m.losing_trades,
            "avg_trade_pnl": m.avg_trade_pnl,
            "largest_win": m.largest_win,
            "largest_loss": m.largest_loss,
            "execution_time": output.execution_time,
            "engine_name": output.engine_name,
            "bars_processed": output.bars_processed,
            "strategy_type": strategy_type,
            "strategy_params": strategy_params,
        }

    def _extract_stop_loss(self, strategy: StrategyDefinition) -> float:
        """Extract stop loss from StrategyDefinition exit conditions."""
        if strategy.exit_conditions and strategy.exit_conditions.stop_loss:
            sl = strategy.exit_conditions.stop_loss
            value = sl.value
            if sl.type == "fixed_pct":
                return value / 100 if value > 1 else value
            if sl.type == "atr_based":
                return value  # ATR multiplier, engine handles it
            return value / 100 if value > 1 else value
        return 0.02  # Default 2%

    def _extract_take_profit(self, strategy: StrategyDefinition) -> float:
        """Extract take profit from StrategyDefinition exit conditions."""
        if strategy.exit_conditions and strategy.exit_conditions.take_profit:
            tp = strategy.exit_conditions.take_profit
            value = tp.value
            if tp.type == "fixed_pct":
                return value / 100 if value > 1 else value
            if tp.type == "atr_based":
                return value
            return value / 100 if value > 1 else value
        return 0.03  # Default 3%

    def strategy_to_config(
        self,
        strategy: StrategyDefinition,
        symbol: str = "BTCUSDT",
        timeframe: str = "15",
        start_date: str = "2025-01-01",
        end_date: str = "2025-06-01",
        initial_capital: float = 10000,
        leverage: float = 1,
    ) -> dict[str, Any]:
        """
        Convert StrategyDefinition to API-compatible BacktestConfig dict.

        Useful for submitting to /api/v1/backtests/ endpoint.

        Args:
            strategy: LLM-generated StrategyDefinition
            symbol: Trading pair
            timeframe: Candle interval
            start_date: Backtest start (YYYY-MM-DD)
            end_date: Backtest end (YYYY-MM-DD)
            initial_capital: Starting capital
            leverage: Trading leverage

        Returns:
            Dict matching BacktestConfig schema
        """
        return {
            "symbol": symbol,
            "interval": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "leverage": leverage,
            "direction": "both",
            "strategy_type": strategy.get_strategy_type_for_engine(),
            "strategy_params": strategy.get_engine_params(),
            "stop_loss": self._extract_stop_loss(strategy),
            "take_profit": self._extract_take_profit(strategy),
        }
