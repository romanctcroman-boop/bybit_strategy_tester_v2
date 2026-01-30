"""
Universal Math Engine Core - Главный оркестратор всех модулей.

Объединяет:
- SignalGenerator: Генерация сигналов
- FilterEngine: Фильтрация
- PositionManager: Управление позициями
- TradeExecutor: Исполнение сделок
- RiskManager: Управление рисками

Автор: AI Agent
Версия: 1.0.0
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from backend.backtesting.universal_engine.filter_engine import (
    FilterConfig,
    UniversalFilterEngine,
)
from backend.backtesting.universal_engine.position_manager import (
    PositionConfig,
    UniversalPositionManager,
)
from backend.backtesting.universal_engine.risk_manager import (
    RiskConfig,
    TradeResult,
    UniversalRiskManager,
)
from backend.backtesting.universal_engine.signal_generator import (
    SignalOutput,
    UniversalSignalGenerator,
)
from backend.backtesting.universal_engine.trade_executor import (
    ExecutorConfig,
    ExitReason,
    TradeRecord,
    UniversalTradeExecutor,
)

# Import interfaces for compatibility
try:
    from backend.backtesting.interfaces import (
        BacktestInput,
        BacktestMetrics,
        BacktestOutput,
        TradeDirection,
    )
except ImportError:
    # Fallback if interfaces not available
    BacktestInput = None
    BacktestOutput = None
    BacktestMetrics = None
    TradeDirection = None


@dataclass
class EngineMetrics:
    """Metrics calculated by the engine."""

    # Basic
    net_profit: float = 0.0
    total_return: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    # Drawdown
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0

    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    # Averages
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade: float = 0.0
    avg_trade_duration: float = 0.0

    # Long/Short breakdown
    long_trades: int = 0
    short_trades: int = 0
    long_win_rate: float = 0.0
    short_win_rate: float = 0.0

    # Advanced
    expectancy: float = 0.0
    payoff_ratio: float = 0.0
    recovery_factor: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "net_profit": round(self.net_profit, 2),
            "total_return": round(self.total_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate * 100, 1),
            "profit_factor": round(self.profit_factor, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "expectancy": round(self.expectancy, 2),
            "long_trades": self.long_trades,
            "short_trades": self.short_trades,
        }


@dataclass
class EngineOutput:
    """Output from Universal Math Engine."""

    metrics: EngineMetrics = field(default_factory=EngineMetrics)
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: np.ndarray = field(default_factory=lambda: np.array([]))
    timestamps: np.ndarray = field(default_factory=lambda: np.array([]))

    # Meta
    engine_name: str = "UniversalMathEngine"
    execution_time: float = 0.0
    bars_processed: int = 0

    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    # Debug info
    signals_generated: int = 0
    signals_filtered: int = 0
    filter_stats: Dict = field(default_factory=dict)


class UniversalMathEngine:
    """
    Universal Math Engine - единый вычислительный центр.

    Объединяет все компоненты в единый pipeline:
    1. Signal Generation (по типу стратегии)
    2. Signal Filtering (MTF, BTC, Volume, etc.)
    3. Position Sizing (Fixed, Risk, Kelly, etc.)
    4. Trade Execution (SL/TP/Trailing/Breakeven)
    5. Risk Management (Drawdown, Consecutive losses, etc.)
    6. Metrics Calculation
    """

    def __init__(self, use_numba: bool = True):
        """
        Initialize Universal Math Engine.

        Args:
            use_numba: Use Numba acceleration where available
        """
        self.use_numba = use_numba
        self.signal_generator = UniversalSignalGenerator(use_numba=use_numba)
        self.filter_engine = UniversalFilterEngine(use_numba=use_numba)

        # These are created per-run with specific config
        self.position_manager: Optional[UniversalPositionManager] = None
        self.trade_executor: Optional[UniversalTradeExecutor] = None
        self.risk_manager: Optional[UniversalRiskManager] = None

        logger.info("UniversalMathEngine initialized")

    def run(
        self,
        candles: pd.DataFrame,
        strategy_type: str,
        strategy_params: Dict[str, Any],
        initial_capital: float = 10000.0,
        direction: str = "both",
        stop_loss: float = 0.02,
        take_profit: float = 0.03,
        leverage: int = 10,
        position_size: float = 0.10,
        taker_fee: float = 0.001,
        slippage: float = 0.0005,
        # Advanced options
        filter_config: Optional[FilterConfig] = None,
        position_config: Optional[PositionConfig] = None,
        executor_config: Optional[ExecutorConfig] = None,
        risk_config: Optional[RiskConfig] = None,
    ) -> EngineOutput:
        """
        Run backtest with all features.

        Args:
            candles: OHLCV DataFrame
            strategy_type: Strategy type (rsi, macd, bb, etc.)
            strategy_params: Strategy parameters
            initial_capital: Starting capital
            direction: "long", "short", or "both"
            stop_loss: Stop loss percentage
            take_profit: Take profit percentage
            leverage: Leverage multiplier
            position_size: Position size as fraction of capital
            taker_fee: Taker fee
            slippage: Slippage
            filter_config: Optional filter configuration
            position_config: Optional position configuration
            executor_config: Optional executor configuration
            risk_config: Optional risk configuration

        Returns:
            EngineOutput with metrics, trades, and equity curve
        """
        start_time = time.time()
        output = EngineOutput()

        try:
            # Validate input
            if candles is None or len(candles) == 0:
                output.is_valid = False
                output.validation_errors.append("Empty candles DataFrame")
                return output

            n_bars = len(candles)
            output.bars_processed = n_bars

            # Extract OHLCV
            close = candles["close"].values.astype(np.float64)
            high = (
                candles["high"].values.astype(np.float64)
                if "high" in candles
                else close
            )
            low = (
                candles["low"].values.astype(np.float64) if "low" in candles else close
            )
            open_prices = (
                candles["open"].values.astype(np.float64)
                if "open" in candles
                else close
            )

            # Get timestamps
            if hasattr(candles.index, "to_pydatetime"):
                timestamps = candles.index.to_pydatetime()
            else:
                timestamps = [datetime.now() for _ in range(n_bars)]

            # =================================================================
            # STEP 1: Generate signals
            # =================================================================
            signal_output = self.signal_generator.generate(
                candles, strategy_type, strategy_params, direction
            )

            long_entries = signal_output.long_entries
            long_exits = signal_output.long_exits
            short_entries = signal_output.short_entries
            short_exits = signal_output.short_exits

            output.signals_generated = int(np.sum(long_entries) + np.sum(short_entries))

            # =================================================================
            # STEP 2: Apply filters
            # =================================================================
            if filter_config is not None:
                filter_output = self.filter_engine.apply_filters(
                    candles, long_entries, short_entries, filter_config
                )
                long_entries = filter_output.long_entries
                short_entries = filter_output.short_entries
                output.filter_stats = filter_output.filter_stats

            output.signals_filtered = int(np.sum(long_entries) + np.sum(short_entries))

            # =================================================================
            # STEP 3: Initialize managers
            # =================================================================
            # Position Manager
            if position_config is None:
                position_config = PositionConfig(
                    position_size=position_size,
                    leverage=leverage,
                    stop_loss=stop_loss,
                )
            self.position_manager = UniversalPositionManager(position_config)

            # Trade Executor
            if executor_config is None:
                executor_config = ExecutorConfig(
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    taker_fee=taker_fee,
                    slippage=slippage,
                    leverage=leverage,
                )
            self.trade_executor = UniversalTradeExecutor(executor_config)
            self.trade_executor.set_atr_values(high, low, close)

            # Risk Manager
            if risk_config is None:
                risk_config = RiskConfig()
            self.risk_manager = UniversalRiskManager(risk_config, initial_capital)

            # =================================================================
            # STEP 4: Main simulation loop
            # =================================================================
            equity = np.zeros(n_bars, dtype=np.float64)
            equity[0] = initial_capital
            current_capital = initial_capital

            for i in range(1, n_bars):
                bar_time = timestamps[i] if i < len(timestamps) else datetime.now()

                # Check if can trade
                can_trade, reason = self.risk_manager.can_trade(i, bar_time)

                # Process existing trades
                closed_trades = self.trade_executor.process_bar(
                    bar_index=i,
                    bar_time=bar_time,
                    open_price=open_prices[i],
                    high=high[i],
                    low=low[i],
                    close=close[i],
                    long_exit=long_exits[i],
                    short_exit=short_exits[i],
                )

                # Update capital and risk tracking
                for trade in closed_trades:
                    current_capital += trade.pnl
                    self.risk_manager.record_trade(
                        TradeResult(
                            pnl=trade.pnl,
                            pnl_pct=trade.pnl_pct,
                            exit_time=trade.exit_time,
                            exit_bar=i,
                            is_win=trade.pnl > 0,
                        ),
                        current_bar=i,
                    )

                self.risk_manager.update_equity(current_capital)

                # Check for new entries
                if can_trade and len(self.trade_executor.active_trades) == 0:
                    # Long entry
                    if long_entries[i] and direction in ["long", "both"]:
                        size = self.position_manager.calculate_position_size(
                            current_capital,
                            close[i],
                            "long",
                            self.trade_executor.atr_values[i]
                            if self.trade_executor.atr_values is not None
                            else 0,
                        )
                        if size > 0:
                            self.trade_executor.open_trade(
                                bar_index=i,
                                bar_time=bar_time,
                                price=close[i],
                                size=size,
                                direction="long",
                                atr_value=self.trade_executor.atr_values[i]
                                if self.trade_executor.atr_values is not None
                                else 0,
                            )

                    # Short entry
                    elif short_entries[i] and direction in ["short", "both"]:
                        size = self.position_manager.calculate_position_size(
                            current_capital,
                            close[i],
                            "short",
                            self.trade_executor.atr_values[i]
                            if self.trade_executor.atr_values is not None
                            else 0,
                        )
                        if size > 0:
                            self.trade_executor.open_trade(
                                bar_index=i,
                                bar_time=bar_time,
                                price=close[i],
                                size=size,
                                direction="short",
                                atr_value=self.trade_executor.atr_values[i]
                                if self.trade_executor.atr_values is not None
                                else 0,
                            )

                equity[i] = current_capital

            # =================================================================
            # STEP 5: Close remaining trades
            # =================================================================
            final_closed = self.trade_executor.close_all_trades(
                bar_index=n_bars - 1,
                bar_time=timestamps[-1] if len(timestamps) > 0 else datetime.now(),
                close_price=close[-1],
                reason=ExitReason.END_OF_DATA,
            )

            for trade in final_closed:
                current_capital += trade.pnl

            equity[-1] = current_capital

            # =================================================================
            # STEP 6: Calculate metrics
            # =================================================================
            all_trades = self.trade_executor.completed_trades
            output.trades = all_trades
            output.equity_curve = equity
            output.timestamps = np.array(timestamps)
            output.metrics = self._calculate_metrics(
                all_trades, equity, initial_capital
            )

        except Exception as e:
            logger.error(f"UniversalMathEngine error: {e}")
            output.is_valid = False
            output.validation_errors.append(str(e))

        output.execution_time = time.time() - start_time
        return output

    def run_from_backtest_input(self, input_data) -> EngineOutput:
        """
        Run backtest from BacktestInput (for compatibility with existing code).

        Args:
            input_data: BacktestInput instance

        Returns:
            EngineOutput
        """
        # Extract strategy params
        strategy_type = getattr(input_data, "strategy_type", "rsi")
        strategy_params = getattr(input_data, "strategy_params", {})

        # Create configs from input
        filter_config = FilterConfig(
            mtf_enabled=getattr(input_data, "mtf_enabled", False),
            mtf_htf_candles=getattr(input_data, "mtf_htf_candles", None),
            mtf_htf_index_map=getattr(input_data, "mtf_htf_index_map", None),
            volatility_filter_enabled=getattr(
                input_data, "volatility_filter_enabled", False
            ),
            volume_filter_enabled=getattr(input_data, "volume_filter_enabled", False),
        )

        position_config = PositionConfig(
            position_sizing_mode=getattr(input_data, "position_sizing_mode", "fixed"),
            position_size=getattr(input_data, "position_size", 0.10),
            leverage=getattr(input_data, "leverage", 10),
            dca_enabled=getattr(input_data, "dca_enabled", False),
            dca_safety_orders=getattr(input_data, "dca_safety_orders", 0),
            pyramiding=getattr(input_data, "pyramiding", 1),
        )

        # Get direction
        direction_val = getattr(input_data, "direction", "both")
        if hasattr(direction_val, "value"):
            direction = direction_val.value
        else:
            direction = str(direction_val).lower()

        return self.run(
            candles=input_data.candles,
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            initial_capital=input_data.initial_capital,
            direction=direction,
            stop_loss=input_data.stop_loss,
            take_profit=input_data.take_profit,
            leverage=input_data.leverage,
            position_size=input_data.position_size,
            taker_fee=input_data.taker_fee,
            slippage=input_data.slippage,
            filter_config=filter_config,
            position_config=position_config,
        )

    def _calculate_metrics(
        self, trades: List[TradeRecord], equity: np.ndarray, initial_capital: float
    ) -> EngineMetrics:
        """Calculate all metrics from trades and equity curve."""
        metrics = EngineMetrics()

        if not trades:
            return metrics

        # Basic stats
        pnls = np.array([t.pnl for t in trades])
        metrics.net_profit = float(np.sum(pnls))
        metrics.total_return = (equity[-1] - initial_capital) / initial_capital * 100

        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]

        metrics.gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        metrics.gross_loss = float(np.sum(losses)) if len(losses) > 0 else 0.0

        metrics.total_trades = len(trades)
        metrics.winning_trades = len(wins)
        metrics.losing_trades = len(losses)
        metrics.win_rate = (
            metrics.winning_trades / metrics.total_trades
            if metrics.total_trades > 0
            else 0.0
        )

        metrics.avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
        metrics.avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
        metrics.avg_trade = float(np.mean(pnls))

        # Profit factor
        if abs(metrics.gross_loss) > 0:
            metrics.profit_factor = abs(metrics.gross_profit / metrics.gross_loss)
        else:
            metrics.profit_factor = float("inf") if metrics.gross_profit > 0 else 0.0

        # Payoff ratio
        if abs(metrics.avg_loss) > 0:
            metrics.payoff_ratio = abs(metrics.avg_win / metrics.avg_loss)

        # Expectancy
        metrics.expectancy = (
            metrics.win_rate * metrics.avg_win
            + (1 - metrics.win_rate) * metrics.avg_loss
        )

        # Drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        metrics.max_drawdown = float(np.max(drawdown)) * 100

        # Drawdown duration
        in_drawdown = drawdown > 0
        if np.any(in_drawdown):
            dd_changes = np.diff(in_drawdown.astype(int))
            dd_starts = np.where(dd_changes == 1)[0]
            dd_ends = np.where(dd_changes == -1)[0]

            if len(dd_starts) > 0 and len(dd_ends) > 0:
                if dd_ends[0] < dd_starts[0]:
                    dd_ends = dd_ends[1:]
                if len(dd_starts) > len(dd_ends):
                    dd_ends = np.append(dd_ends, len(equity) - 1)
                if len(dd_starts) > 0 and len(dd_ends) > 0:
                    durations = dd_ends[: len(dd_starts)] - dd_starts[: len(dd_ends)]
                    if len(durations) > 0:
                        metrics.max_drawdown_duration = int(np.max(durations))

        # Sharpe ratio (annualized, assuming daily data)
        returns = np.diff(equity) / equity[:-1]
        if len(returns) > 1 and np.std(returns) > 0:
            metrics.sharpe_ratio = float(
                np.mean(returns) / np.std(returns) * np.sqrt(252)
            )

        # Sortino ratio
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0 and np.std(negative_returns) > 0:
            metrics.sortino_ratio = float(
                np.mean(returns) / np.std(negative_returns) * np.sqrt(252)
            )

        # Calmar ratio
        if metrics.max_drawdown > 0:
            annualized_return = metrics.total_return  # Simplified
            metrics.calmar_ratio = annualized_return / metrics.max_drawdown

        # Recovery factor
        if metrics.max_drawdown > 0:
            metrics.recovery_factor = metrics.net_profit / (
                metrics.max_drawdown * initial_capital / 100
            )

        # Long/Short breakdown
        long_trades = [t for t in trades if t.direction == "long"]
        short_trades = [t for t in trades if t.direction == "short"]

        metrics.long_trades = len(long_trades)
        metrics.short_trades = len(short_trades)

        if long_trades:
            long_wins = sum(1 for t in long_trades if t.pnl > 0)
            metrics.long_win_rate = long_wins / len(long_trades)

        if short_trades:
            short_wins = sum(1 for t in short_trades if t.pnl > 0)
            metrics.short_win_rate = short_wins / len(short_trades)

        # Average trade duration
        durations = [t.duration_bars for t in trades]
        metrics.avg_trade_duration = float(np.mean(durations)) if durations else 0.0

        return metrics

    @property
    def name(self) -> str:
        return "UniversalMathEngine"

    @property
    def supports_bar_magnifier(self) -> bool:
        return True

    @property
    def supports_parallel(self) -> bool:
        return True
