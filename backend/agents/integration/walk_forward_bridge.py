"""
Walk-Forward Bridge — connects WalkForwardOptimizer to AI pipeline.

Converts LLM StrategyDefinition into:
1. strategy_runner callable compatible with WalkForwardOptimizer.optimize()
2. param_grid from OptimizationHints

Pipeline:
    StrategyDefinition
        → build_strategy_runner() → Callable[[list[dict], dict, float], dict]
        → build_param_grid() → dict[str, list[Any]]
        → WalkForwardOptimizer.optimize()
        → WalkForwardResult
"""

from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd
from loguru import logger

from backend.agents.prompts.response_parser import StrategyDefinition
from backend.services.walk_forward import (
    WalkForwardOptimizer,
    WalkForwardResult,
)


class WalkForwardBridge:
    """
    Bridge between LLM StrategyDefinition and WalkForwardOptimizer.

    Provides:
    - build_strategy_runner(): creates callable for WF optimizer
    - build_param_grid(): extracts param grid from OptimizationHints
    - run_walk_forward(): end-to-end WF validation of a strategy
    - run_walk_forward_async(): async wrapper for pipeline integration

    Example:
        bridge = WalkForwardBridge()
        wf_result = await bridge.run_walk_forward_async(
            strategy=strategy_def,
            df=ohlcv_df,
            symbol="BTCUSDT",
            timeframe="15",
        )
        print(f"Overfit: {wf_result.overfit_score:.2%}")
        print(f"Confidence: {wf_result.confidence_level}")
    """

    # Commission rate — must match TradingView parity (0.07%)
    COMMISSION_RATE = 0.0007

    # Default param ranges when OptimizationHints lacks specific ranges
    DEFAULT_PARAM_RANGES: dict[str, dict[str, list[Any]]] = {
        "rsi": {
            "period": [7, 14, 21, 28],
            "overbought": [65, 70, 75, 80],
            "oversold": [20, 25, 30, 35],
        },
        "macd": {
            "fast_period": [8, 10, 12, 14],
            "slow_period": [21, 26, 30],
            "signal_period": [7, 9, 11],
        },
        "ema_crossover": {
            "fast_period": [5, 9, 12, 15],
            "slow_period": [18, 21, 26, 30],
        },
        "sma_crossover": {
            "fast_period": [5, 10, 15, 20],
            "slow_period": [25, 30, 40, 50],
        },
        "bollinger": {
            "period": [15, 20, 25, 30],
            "std_dev": [1.5, 2.0, 2.5, 3.0],
        },
        "supertrend": {
            "period": [7, 10, 14, 20],
            "multiplier": [2.0, 2.5, 3.0, 3.5],
        },
        "stochastic": {
            "k_period": [9, 14, 21],
            "d_period": [3, 5, 7],
            "overbought": [75, 80, 85],
            "oversold": [15, 20, 25],
        },
    }

    def __init__(
        self,
        n_splits: int = 5,
        train_ratio: float = 0.7,
        gap_periods: int = 0,
        optimizer: WalkForwardOptimizer | None = None,
    ) -> None:
        """
        Initialize WalkForwardBridge.

        Args:
            n_splits: Number of walk-forward windows
            train_ratio: Ratio of data for training vs testing
            gap_periods: Periods to skip between train/test (avoid lookahead)
            optimizer: Custom WalkForwardOptimizer (default: global singleton)
        """
        if optimizer is not None:
            self._optimizer = optimizer
        else:
            self._optimizer = WalkForwardOptimizer(
                n_splits=n_splits,
                train_ratio=train_ratio,
                gap_periods=gap_periods,
            )

    def build_strategy_runner(
        self,
        strategy: StrategyDefinition,
        symbol: str = "BTCUSDT",
        timeframe: str = "15",
        direction: str = "both",
    ):
        """
        Build a strategy_runner callable compatible with WalkForwardOptimizer.

        The returned function has signature:
            (data: list[dict], params: dict, capital: float) -> dict

        It converts candle dicts to DataFrame, generates signals with the
        strategy type from StrategyDefinition, and runs FallbackEngineV4.

        Args:
            strategy: LLM-generated StrategyDefinition (used for type/SL/TP)
            symbol: Trading pair
            timeframe: Candle interval
            direction: Trade direction (long, short, both)

        Returns:
            Callable[[list[dict], dict, float], dict] for WF optimizer
        """
        strategy_type = strategy.get_strategy_type_for_engine()
        stop_loss = self._extract_stop_loss(strategy)
        take_profit = self._extract_take_profit(strategy)

        def runner(data: list[dict], params: dict, capital: float) -> dict:
            """Run strategy on candle data with given params."""
            return self._execute_backtest(
                data=data,
                strategy_type=strategy_type,
                strategy_params=params,
                symbol=symbol,
                timeframe=timeframe,
                initial_capital=capital,
                direction=direction,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        return runner

    def build_param_grid(
        self,
        strategy: StrategyDefinition,
    ) -> dict[str, list[Any]]:
        """
        Build parameter grid for walk-forward optimization.

        Priority:
        1. OptimizationHints.ranges from the StrategyDefinition
        2. Default ranges for the strategy type
        3. Variations around current engine params (fallback)

        Args:
            strategy: LLM-generated StrategyDefinition

        Returns:
            Dict mapping param names to lists of values to try
        """
        strategy_type = strategy.get_strategy_type_for_engine()
        current_params = strategy.get_engine_params()

        # 1. Try OptimizationHints
        if strategy.optimization_hints and strategy.optimization_hints.ranges:
            grid = self._grid_from_hints(
                strategy.optimization_hints,
                current_params,
            )
            if grid:
                logger.info(f"WF param grid from OptimizationHints: {list(grid.keys())}")
                return grid

        # 2. Try default ranges for this strategy type
        if strategy_type in self.DEFAULT_PARAM_RANGES:
            grid = self.DEFAULT_PARAM_RANGES[strategy_type].copy()
            # Ensure current param values are included
            for key, values in grid.items():
                if key in current_params and current_params[key] not in values:
                    values = sorted([*values, current_params[key]])
                    grid[key] = values
            logger.info(f"WF param grid from defaults ({strategy_type}): {list(grid.keys())}")
            return grid

        # 3. Fallback: generate grid from current params
        grid = self._grid_from_current_params(current_params)
        logger.info(f"WF param grid from current params: {list(grid.keys())}")
        return grid

    def run_walk_forward(
        self,
        strategy: StrategyDefinition,
        df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframe: str = "15",
        initial_capital: float = 10000,
        direction: str = "both",
        metric: str = "sharpe",
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization on a strategy (synchronous).

        Args:
            strategy: LLM-generated StrategyDefinition
            df: OHLCV DataFrame
            symbol: Trading pair
            timeframe: Candle interval
            initial_capital: Starting capital
            direction: Trade direction
            metric: Metric to optimize (sharpe, return, calmar)

        Returns:
            WalkForwardResult with robustness assessment
        """
        # Convert DataFrame to list[dict] for WF optimizer
        candle_data = self._df_to_candles(df)

        # Build runner and param grid
        runner = self.build_strategy_runner(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
        )
        param_grid = self.build_param_grid(strategy)

        if not param_grid:
            raise ValueError(f"Cannot build param grid for strategy type '{strategy.get_strategy_type_for_engine()}'")

        logger.info(
            f"🔄 Walk-forward: {self._optimizer.n_splits} splits, {len(param_grid)} params, {len(candle_data)} candles"
        )

        result = self._optimizer.optimize(
            data=candle_data,
            strategy_runner=runner,
            param_grid=param_grid,
            initial_capital=initial_capital,
            metric=metric,
        )

        logger.info(
            f"✅ Walk-forward done: overfit={result.overfit_score:.2%}, "
            f"consistency={result.consistency_ratio:.0%}, "
            f"confidence={result.confidence_level}"
        )
        return result

    async def run_walk_forward_async(
        self,
        strategy: StrategyDefinition,
        df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframe: str = "15",
        initial_capital: float = 10000,
        direction: str = "both",
        metric: str = "sharpe",
    ) -> WalkForwardResult:
        """
        Async wrapper for walk-forward optimization.

        Runs the sync optimizer in a thread pool to avoid blocking
        the event loop.

        Args:
            strategy: LLM-generated StrategyDefinition
            df: OHLCV DataFrame
            symbol: Trading pair
            timeframe: Candle interval
            initial_capital: Starting capital
            direction: Trade direction
            metric: Metric to optimize

        Returns:
            WalkForwardResult with robustness assessment
        """
        return await asyncio.to_thread(
            self.run_walk_forward,
            strategy=strategy,
            df=df,
            symbol=symbol,
            timeframe=timeframe,
            initial_capital=initial_capital,
            direction=direction,
            metric=metric,
        )

    # ─────────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────────────

    def _execute_backtest(
        self,
        data: list[dict],
        strategy_type: str,
        strategy_params: dict[str, Any],
        symbol: str,
        timeframe: str,
        initial_capital: float,
        direction: str,
        stop_loss: float,
        take_profit: float,
    ) -> dict[str, Any]:
        """
        Execute a single backtest run for the WF optimizer.

        Converts candle list → DataFrame → signals → engine → metrics dict.

        Returns:
            Dict with keys: return, sharpe, max_drawdown, trades
        """
        from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
        from backend.backtesting.interfaces import BacktestInput, TradeDirection
        from backend.backtesting.signal_generators import generate_signals_for_strategy

        # Convert list[dict] → DataFrame
        df = pd.DataFrame(data)
        if df.empty:
            return {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}

        # Ensure column names are lowercase
        df.columns = [c.lower() for c in df.columns]

        # Generate signals
        try:
            long_entries, long_exits, short_entries, short_exits = generate_signals_for_strategy(
                candles=df,
                strategy_type=strategy_type,
                params=strategy_params,
                direction=direction,
            )
        except (ValueError, KeyError) as e:
            logger.debug(f"Signal generation failed: {e}")
            return {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}

        # Map direction
        dir_map = {
            "long": TradeDirection.LONG,
            "short": TradeDirection.SHORT,
            "both": TradeDirection.BOTH,
        }
        trade_direction = dir_map.get(direction, TradeDirection.BOTH)

        # Build input
        bt_input = BacktestInput(
            candles=df,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol=symbol,
            interval=timeframe,
            initial_capital=initial_capital,
            leverage=1,
            stop_loss=stop_loss,
            take_profit=take_profit,
            taker_fee=self.COMMISSION_RATE,
            direction=trade_direction,
        )

        # Run engine
        engine = FallbackEngineV4()
        output = engine.run(bt_input)

        if not output.is_valid:
            return {"return": 0, "sharpe": 0, "max_drawdown": 0, "trades": 0}

        m = output.metrics
        return {
            "return": m.total_return_pct / 100 if m.total_return_pct else 0,
            "sharpe": m.sharpe_ratio or 0,
            "max_drawdown": m.max_drawdown_pct / 100 if m.max_drawdown_pct else 0,
            "trades": m.total_trades or 0,
        }

    @staticmethod
    def _df_to_candles(df: pd.DataFrame) -> list[dict]:
        """
        Convert OHLCV DataFrame to list of candle dicts.

        WalkForwardOptimizer expects list[dict] with 'open_time' key.
        """
        records = df.to_dict("records")
        result = []
        for rec in records:
            candle: dict[str, Any] = {}
            # Map standard OHLCV columns
            for col in ("open", "high", "low", "close", "volume"):
                candle[col] = rec.get(col, rec.get(col.capitalize(), 0))

            # Map timestamp — try common column names
            ts = rec.get("open_time", rec.get("timestamp", rec.get("date", None)))
            if ts is not None:
                candle["open_time"] = ts
            elif "index" in rec:
                candle["open_time"] = rec["index"]
            else:
                # Use row position as fallback
                candle["open_time"] = len(result)

            result.append(candle)
        return result

    @staticmethod
    def _extract_stop_loss(strategy: StrategyDefinition) -> float:
        """Extract stop loss fraction from StrategyDefinition."""
        if strategy.exit_conditions and strategy.exit_conditions.stop_loss:
            sl = strategy.exit_conditions.stop_loss
            value = sl.value
            if sl.type == "fixed_pct":
                return value / 100 if value > 1 else value
            if sl.type == "atr_based":
                return value
            return value / 100 if value > 1 else value
        return 0.02  # Default 2%

    @staticmethod
    def _extract_take_profit(strategy: StrategyDefinition) -> float:
        """Extract take profit fraction from StrategyDefinition."""
        if strategy.exit_conditions and strategy.exit_conditions.take_profit:
            tp = strategy.exit_conditions.take_profit
            value = tp.value
            if tp.type == "fixed_pct":
                return value / 100 if value > 1 else value
            if tp.type == "atr_based":
                return value
            return value / 100 if value > 1 else value
        return 0.03  # Default 3%

    @staticmethod
    def _grid_from_hints(
        hints,
        current_params: dict[str, Any],
    ) -> dict[str, list[Any]]:
        """
        Build param grid from OptimizationHints.

        Uses ranges directly. If a param is in parameters_to_optimize but
        has no range, generates variations around the current value.
        """
        grid: dict[str, list[Any]] = {}

        # Direct ranges from hints
        for param_name, values in hints.ranges.items():
            if values and len(values) >= 2:
                grid[param_name] = values

        # Parameters to optimize without explicit ranges
        for param_name in hints.parameters_to_optimize:
            if param_name not in grid and param_name in current_params:
                current_val = current_params[param_name]
                grid[param_name] = _generate_variations(current_val)

        return grid

    @staticmethod
    def _grid_from_current_params(
        current_params: dict[str, Any],
    ) -> dict[str, list[Any]]:
        """Generate param grid by varying current params by +/- 30%."""
        grid: dict[str, list[Any]] = {}
        for key, value in current_params.items():
            grid[key] = _generate_variations(value)
        return grid


def _generate_variations(value: Any, n_steps: int = 5) -> list[Any]:
    """
    Generate n_steps variations around a value.

    For int: +/- 40% range with integer steps
    For float: +/- 40% range with float steps
    Otherwise: return [value]
    """
    if isinstance(value, int):
        low = max(1, int(value * 0.6))
        high = int(value * 1.4) + 1
        step = max(1, (high - low) // (n_steps - 1)) if n_steps > 1 else 1
        return sorted(set(range(low, high + 1, step)))
    if isinstance(value, float):
        import numpy as np

        low = value * 0.6
        high = value * 1.4
        return [round(float(v), 4) for v in np.linspace(low, high, n_steps)]
    return [value]
