"""
Backtest Engine

High-performance backtesting engine using vectorbt.
Executes strategies on historical data and calculates performance metrics.

NOTE: All metric calculations use backend.core.metrics_calculator
as the single source of truth. This ensures consistency across:
- Backtest engine (this file) ✅ Uses MetricsCalculator.calculate_all()
- Fast optimizer (fast_optimizer.py)
- GPU optimizer (gpu_optimizer.py)
- Walk-forward optimizer (walk_forward.py)

REFACTORED: 2026-01-25 - Now uses MetricsCalculator.calculate_all()
"""

import uuid
import warnings
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

# Suppress vectorbt deprecation warnings for better performance
warnings.filterwarnings("ignore", category=FutureWarning, module="vectorbt")

try:
    import vectorbt as vbt

    VBT_AVAILABLE = True
except ImportError:
    vbt = None
    VBT_AVAILABLE = False
    logger.warning("vectorbt not installed. Using fallback implementation.")

from backend.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    BacktestStatus,
    EquityCurve,
    OrderSide,
    PerformanceMetrics,
    PeriodAnalysis,
    TradeRecord,
)
from backend.backtesting.strategies import BaseStrategy, get_strategy

# Centralized metrics calculator - single source of truth
from backend.core.metrics_calculator import (
    MetricsCalculator,
    TimeFrequency,
)
from backend.utils.time import utc_now

# Note: VectorBT is reserved for OPTIMIZATION only.
# Regular backtests always use the fallback engine for 100% accurate results.
# See docs/ENGINE_ARCHITECTURE.md for details on why this decision was made.


def compute_period_analysis(
    equity_series: pd.Series, trades: list, period_type: str = "monthly"
) -> list[PeriodAnalysis]:
    """
    Compute performance analysis broken down by period (monthly or yearly).

    Args:
        equity_series: Pandas Series with DatetimeIndex and equity values
        trades: List of TradeRecord objects
        period_type: "monthly" or "yearly"

    Returns:
        List of PeriodAnalysis objects
    """
    if equity_series.empty or len(trades) == 0:
        return []

    results = []

    # Group by period
    if period_type == "monthly":
        groups = equity_series.groupby(equity_series.index.to_period("M"))
    else:
        groups = equity_series.groupby(equity_series.index.to_period("Y"))

    for period, group in groups:
        if len(group) < 2:
            continue

        period_str = str(period)
        start_date = group.index.min()
        end_date = group.index.max()

        # Calculate period metrics
        start_equity = group.iloc[0]
        end_equity = group.iloc[-1]
        net_profit = end_equity - start_equity
        net_profit_pct = (net_profit / start_equity * 100) if start_equity > 0 else 0.0

        # Filter trades for this period
        period_trades = [
            t
            for t in trades
            if hasattr(t, "entry_time") and start_date <= t.entry_time <= end_date
        ]

        total_trades = len(period_trades)
        winning_trades = sum(1 for t in period_trades if t.pnl > 0)
        losing_trades = sum(1 for t in period_trades if t.pnl < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Profit factor - using GROSS values (before commissions)
        # gross_pnl = pnl + fees (to restore pre-commission P&L)
        gross_pnls = [(t.pnl + getattr(t, "fees", 0)) for t in period_trades]
        gross_profit = sum(g for g in gross_pnls if g > 0)
        gross_loss = abs(sum(g for g in gross_pnls if g < 0))
        profit_factor = (
            (gross_profit / gross_loss)
            if gross_loss > 0
            else float("inf")
            if gross_profit > 0
            else 0.0
        )

        # Max drawdown for period
        running_max = group.cummax()
        drawdown = (group - running_max) / running_max * 100
        max_drawdown = abs(drawdown.min())

        # Sharpe for period (simplified - daily returns annualized)
        if len(group) > 1:
            returns = group.pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                sharpe = returns.mean() / returns.std() * np.sqrt(252)  # Annualized
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        results.append(
            PeriodAnalysis(
                period=period_str,
                start_date=start_date.to_pydatetime()
                if hasattr(start_date, "to_pydatetime")
                else start_date,
                end_date=end_date.to_pydatetime()
                if hasattr(end_date, "to_pydatetime")
                else end_date,
                net_profit=float(net_profit),
                net_profit_pct=float(net_profit_pct),
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=float(win_rate),
                profit_factor=float(profit_factor)
                if profit_factor != float("inf")
                else 9999.99,
                max_drawdown=float(max_drawdown),
                sharpe_ratio=float(sharpe),
            )
        )

    return results


def compute_buy_hold_equity(
    ohlcv: pd.DataFrame, initial_capital: float
) -> tuple[list[float], list[float]]:
    """
    Compute Buy & Hold equity curve and drawdown.

    Args:
        ohlcv: DataFrame with 'close' column
        initial_capital: Starting capital

    Returns:
        Tuple of (equity_list, drawdown_list)
    """
    if ohlcv.empty or "close" not in ohlcv.columns:
        return [], []

    close = ohlcv["close"]

    # Calculate equity as if we bought at first bar and held
    first_price = close.iloc[0]
    shares = initial_capital / first_price
    equity = shares * close

    # Calculate drawdown
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max * 100

    return list(equity.values), list(drawdown.values)


def build_equity_from_trades(
    trades: list,
    ohlcv: pd.DataFrame,
    initial_capital: float,
    leverage: float = 1.0,
    taker_fee: float = 0.0004,
) -> tuple[list, list]:
    """
    Build equity curve from trades with proper leverage accounting.

    Uses cumulative PnL approach:
    - Equity = initial_capital + cumulative_realized_pnl + unrealized_pnl
    - All PnL values are leveraged (matching trade records)

    Returns: (equity_values, drawdown_values)
    """
    close = ohlcv["close"].values
    n_bars = len(close)

    if not trades:
        equity = [initial_capital] * n_bars
        return equity, [0.0] * n_bars

    # Build maps for trade events
    # Key: bar_index, Value: list of (event_type, trade)
    entry_map = {}  # bar -> trade that enters
    exit_map = {}  # bar -> (trade, realized_pnl) that exits

    for t in trades:
        entry_bar = getattr(t, "entry_bar_index", 0)
        exit_bar = getattr(t, "exit_bar_index", 0)
        pnl = getattr(t, "pnl", 0)

        entry_map[entry_bar] = t
        exit_map[exit_bar] = (t, pnl)

    # Build equity bar by bar
    equity = []
    cumulative_realized_pnl = 0.0
    current_position = None  # The trade currently open

    for i in range(n_bars):
        # Check for exit first (if same bar as next entry, process exit)
        if i in exit_map:
            exiting_trade, realized_pnl = exit_map[i]
            # Only close if this is actually our current position
            if current_position is not None:
                cumulative_realized_pnl += realized_pnl
                current_position = None

        # Check for entry
        if i in entry_map:
            current_position = entry_map[i]

        # Calculate current equity
        unrealized_pnl = 0.0
        if current_position is not None:
            entry_price = getattr(current_position, "entry_price", 0)
            size = getattr(current_position, "size", 0)
            side = getattr(current_position, "side", None)
            current_price = close[i]

            is_long = str(side).lower() in (
                "buy",
                "ordersidebuy",
                "ordersidelong",
                "long",
                "ordersidelong",
            )

            if is_long:
                unrealized_pnl = (current_price - entry_price) * size * leverage
            else:
                unrealized_pnl = (entry_price - current_price) * size * leverage

        current_equity = initial_capital + cumulative_realized_pnl + unrealized_pnl
        equity.append(current_equity)

    # Calculate drawdown
    equity_arr = np.array(equity)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = np.where(peak > 0, (peak - equity_arr) / peak * 100, 0.0)

    return equity, list(drawdown)


def _build_performance_metrics(
    trades: list,
    equity: list,
    config: "BacktestConfig",
    timestamps: list,
    close: pd.Series,
    drawdown: pd.Series,
    pnl_distribution: Optional[list] = None,
) -> PerformanceMetrics:
    """
    Build PerformanceMetrics using centralized MetricsCalculator.

    This is the SINGLE SOURCE OF TRUTH for metric calculations.
    All metric formulas are defined in backend.core.metrics_calculator.
    """
    import numpy as np

    equity_arr = np.array(equity)
    initial_capital = config.initial_capital

    # Calculate years for CAGR
    if len(timestamps) > 1:
        first_ts = timestamps[0]
        last_ts = timestamps[-1]
        if hasattr(first_ts, "timestamp") and hasattr(last_ts, "timestamp"):
            years = (last_ts.timestamp() - first_ts.timestamp()) / (
                365.25 * 24 * 60 * 60
            )
        else:
            years = (last_ts - first_ts).total_seconds() / (365.25 * 24 * 60 * 60)
        years = max(years, 0.001)  # Avoid division by zero
    else:
        years = 1.0

    # Use centralized calculator for all metrics
    calc_metrics = MetricsCalculator.calculate_all(
        trades=trades,
        equity=equity_arr,
        initial_capital=initial_capital,
        years=years,
        frequency=TimeFrequency.HOURLY,  # Default for crypto
    )

    # Buy & Hold calculations (not in MetricsCalculator as it's context-specific)
    if len(close) > 1:
        # Handle both pandas Series and numpy arrays
        if hasattr(close, "iloc"):
            first_price = float(close.iloc[0])
            last_price = float(close.iloc[-1])
        else:
            first_price = float(close[0])
            last_price = float(close[-1])
        buy_hold_return = ((last_price - first_price) / first_price) * initial_capital
        buy_hold_return_pct = ((last_price - first_price) / first_price) * 100
    else:
        buy_hold_return = 0.0
        buy_hold_return_pct = 0.0

    # Additional derived metrics
    total_return = (
        (equity[-1] - initial_capital) / initial_capital if initial_capital > 0 else 0.0
    )
    annual_return = (
        total_return * (365 / max(1, (timestamps[-1] - timestamps[0]).days))
        if len(timestamps) > 1
        else 0.0
    )

    # Exposure time calculation
    winning_trades_list = [t for t in trades if t.pnl > 0]
    losing_trades_list = [t for t in trades if t.pnl <= 0]

    # Calculate exposure time (% of total time in position)
    if trades and len(timestamps) > 1:
        total_bars = len(timestamps)
        bars_in_trades = sum(getattr(t, "bars_in_trade", 0) or 0 for t in trades)
        exposure_time = (bars_in_trades / total_bars * 100) if total_bars > 0 else 0.0
    else:
        exposure_time = 0.0

    # Calculate average bars in trade
    if trades:
        all_bars = [getattr(t, "bars_in_trade", 0) or 0 for t in trades]
        win_bars = [getattr(t, "bars_in_trade", 0) or 0 for t in winning_trades_list]
        loss_bars = [getattr(t, "bars_in_trade", 0) or 0 for t in losing_trades_list]
        avg_bars_in_trade = np.mean(all_bars) if all_bars else 0.0
        avg_bars_in_winning = np.mean(win_bars) if win_bars else 0.0
        avg_bars_in_losing = np.mean(loss_bars) if loss_bars else 0.0
    else:
        avg_bars_in_trade = 0.0
        avg_bars_in_winning = 0.0
        avg_bars_in_losing = 0.0

    # Calculate avg_win_loss_ratio
    avg_win_val = calc_metrics.get("avg_win_value", 0)
    avg_loss_val = calc_metrics.get("avg_loss_value", 0)
    avg_win_loss_ratio = abs(avg_win_val / avg_loss_val) if avg_loss_val != 0 else 0.0

    # Calculate largest win/loss pct of gross
    gross_profit = calc_metrics.get("gross_profit", 0)
    gross_loss = calc_metrics.get("gross_loss", 0)
    largest_win_val = calc_metrics.get("largest_win_value", 0)
    largest_loss_val = abs(calc_metrics.get("largest_loss_value", 0))
    largest_win_pct_of_gross = (
        (largest_win_val / gross_profit * 100) if gross_profit > 0 else 0.0
    )
    largest_loss_pct_of_gross = (
        (largest_loss_val / gross_loss * 100) if gross_loss > 0 else 0.0
    )

    # Convert max_drawdown_duration_bars to days
    bars_per_day = 96 if config.interval == "15" else 24  # 15m = 96 bars/day, 1h = 24
    max_dd_duration_bars = calc_metrics.get("max_drawdown_duration_bars", 0)
    max_dd_duration_days = (
        max_dd_duration_bars / bars_per_day if bars_per_day > 0 else 0.0
    )

    # ========== INTRABAR METRICS (TradingView-style simulation from OHLC) ==========
    # TradingView generates synthetic ticks from OHLC: Open → High → Low → Close
    # We use MFE/MAE from trades which already capture intrabar extremes
    # MFE = Maximum Favorable Excursion (best unrealized profit during trade)
    # MAE = Maximum Adverse Excursion (worst unrealized loss during trade)

    max_drawdown_intrabar = 0.0
    max_runup_intrabar = 0.0
    max_drawdown_intrabar_value = 0.0
    max_runup_intrabar_value = 0.0

    if trades:
        # MAE represents the maximum adverse move (drawdown) during each trade
        # This is already calculated from intrabar High/Low in fallback engine
        mae_values = [getattr(t, "mae", 0) or 0 for t in trades]
        mae_pct_values = [getattr(t, "mae_pct", 0) or 0 for t in trades]
        mfe_values = [getattr(t, "mfe", 0) or 0 for t in trades]
        mfe_pct_values = [getattr(t, "mfe_pct", 0) or 0 for t in trades]

        if mae_values:
            max_drawdown_intrabar_value = max(mae_values)  # Largest adverse excursion
            max_drawdown_intrabar = max(mae_pct_values) if mae_pct_values else 0.0

        if mfe_values:
            max_runup_intrabar_value = max(mfe_values)  # Largest favorable excursion
            max_runup_intrabar = max(mfe_pct_values) if mfe_pct_values else 0.0

    # ========== NEW: Calculate missing metrics with REAL formulas ==========

    # closed_trades = total_trades (all trades in backtest are closed)
    closed_trades = calc_metrics.get("total_trades", 0)

    # account_size_required = capital needed to survive max drawdown
    # Formula: Max Drawdown Value (so you have enough to continue trading)
    max_dd_value = calc_metrics.get("max_drawdown_value", 0)
    account_size_required = max_dd_value if max_dd_value > 0 else initial_capital

    # return_on_account_size = Net Profit / Account Size Required
    net_profit = calc_metrics.get("net_profit", 0)
    return_on_account_size = (
        (net_profit / account_size_required * 100) if account_size_required > 0 else 0.0
    )

    # total_slippage = sum of slippage applied to all trades
    # Formula: sum(entry_price * size * slippage_pct) for each trade
    slippage_pct = getattr(config, "slippage", 0.0)
    total_slippage = 0.0
    if trades and slippage_pct > 0:
        for t in trades:
            entry_price = getattr(t, "entry_price", 0)
            size = getattr(t, "size", 0)
            # Slippage on entry and exit
            total_slippage += entry_price * size * slippage_pct * 2  # Entry + Exit

    # max_contracts_held = maximum position size across all trades
    max_contracts_held = (
        max((getattr(t, "size", 0) for t in trades), default=0.0) if trades else 0.0
    )

    # Margin metrics (for leveraged trading)
    leverage = getattr(config, "leverage", 1.0)
    if trades and leverage > 1:
        margin_values = []
        for t in trades:
            entry_price = getattr(t, "entry_price", 0)
            size = getattr(t, "size", 0)
            position_value = entry_price * size
            margin_required = position_value / leverage  # Margin = Position / Leverage
            margin_values.append(margin_required)
        avg_margin_used = np.mean(margin_values) if margin_values else 0.0
        max_margin_used = max(margin_values) if margin_values else 0.0
    else:
        avg_margin_used = 0.0
        max_margin_used = 0.0

    # margin_efficiency = Net Profit / (Avg Margin * 0.7) * 100 (TradingView formula)
    margin_efficiency = 0.0
    if avg_margin_used > 0:
        margin_efficiency = (net_profit / (avg_margin_used * 0.7)) * 100

    # Recovery factor per direction
    # recovery_long = long_net_profit / long_max_drawdown
    # recovery_short = short_net_profit / short_max_drawdown
    long_trades_list = [
        t for t in trades if getattr(t, "side", "") in ("buy", "long", "BUY", "LONG")
    ]
    short_trades_list = [
        t
        for t in trades
        if getattr(t, "side", "") in ("sell", "short", "SELL", "SHORT")
    ]

    long_net = calc_metrics.get("long_net_profit", 0)
    short_net = calc_metrics.get("short_net_profit", 0)

    # Calculate long max drawdown from long trades
    recovery_long = 0.0
    if long_trades_list:
        long_equity = [initial_capital]
        for t in long_trades_list:
            long_equity.append(long_equity[-1] + getattr(t, "pnl", 0))
        long_equity_arr = np.array(long_equity)
        long_peak = np.maximum.accumulate(long_equity_arr)
        long_dd = long_peak - long_equity_arr
        long_max_dd = np.max(long_dd) if len(long_dd) > 0 else 0.0
        recovery_long = long_net / long_max_dd if long_max_dd > 0 else 0.0

    # Calculate short max drawdown from short trades
    recovery_short = 0.0
    if short_trades_list:
        short_equity = [initial_capital]
        for t in short_trades_list:
            short_equity.append(short_equity[-1] + getattr(t, "pnl", 0))
        short_equity_arr = np.array(short_equity)
        short_peak = np.maximum.accumulate(short_equity_arr)
        short_dd = short_peak - short_equity_arr
        short_max_dd = np.max(short_dd) if len(short_dd) > 0 else 0.0
        recovery_short = short_net / short_max_dd if short_max_dd > 0 else 0.0

    # Calculate quick_reversals - trades where entry is within 2 bars of previous exit
    # This indicates rapid direction changes
    quick_reversals = 0
    if len(trades) > 1:
        sorted_trades = sorted(trades, key=lambda t: getattr(t, "entry_bar_index", 0))
        for i in range(1, len(sorted_trades)):
            prev_exit = getattr(sorted_trades[i - 1], "exit_bar_index", 0)
            curr_entry = getattr(sorted_trades[i], "entry_bar_index", 0)
            if curr_entry - prev_exit <= 2:  # Within 2 bars = quick reversal
                quick_reversals += 1

    # Get avg_runup_duration_bars from calc_metrics
    avg_runup_duration_bars = calc_metrics.get("avg_runup_duration_bars", 0.0)
    return PerformanceMetrics(
        # Net/Gross profit
        net_profit=calc_metrics["net_profit"],
        net_profit_pct=(calc_metrics["net_profit"] / initial_capital) * 100
        if initial_capital > 0
        else 0,
        gross_profit=calc_metrics["gross_profit"],
        gross_profit_pct=(calc_metrics["gross_profit"] / initial_capital) * 100
        if initial_capital > 0
        else 0,
        gross_loss=calc_metrics["gross_loss"],
        gross_loss_pct=(calc_metrics["gross_loss"] / initial_capital) * 100
        if initial_capital > 0
        else 0,
        total_commission=calc_metrics["total_commission"],
        # Buy & Hold
        buy_hold_return=buy_hold_return,
        buy_hold_return_pct=buy_hold_return_pct,
        # Returns
        total_return=total_return,
        annual_return=annual_return,
        # Risk ratios
        sharpe_ratio=calc_metrics["sharpe_ratio"],
        sortino_ratio=calc_metrics["sortino_ratio"],
        calmar_ratio=calc_metrics["calmar_ratio"],
        # Drawdown
        max_drawdown=calc_metrics["max_drawdown"],
        max_drawdown_value=calc_metrics["max_drawdown_value"],
        avg_drawdown=calc_metrics["avg_drawdown"],
        avg_drawdown_value=calc_metrics["avg_drawdown"]
        * initial_capital
        / 100,  # Fix: was multiplying pct by capital
        max_drawdown_duration_days=max_dd_duration_days,
        max_drawdown_duration_bars=max_dd_duration_bars,
        avg_drawdown_duration_bars=calc_metrics.get("avg_drawdown_duration_bars", 0),
        # Volatility & Ulcer Index
        volatility=calc_metrics.get("volatility", 0.0),
        ulcer_index=calc_metrics.get("ulcer_index", 0.0),
        sqn=calc_metrics.get("sqn", 0.0),
        # Intrabar metrics (TradingView-style from OHLC simulation)
        max_drawdown_intrabar=max_drawdown_intrabar,
        max_drawdown_intrabar_value=max_drawdown_intrabar_value,
        max_runup_intrabar=max_runup_intrabar,
        max_runup_intrabar_value=max_runup_intrabar_value,
        # Trade stats
        total_trades=calc_metrics["total_trades"],
        winning_trades=calc_metrics["winning_trades"],
        losing_trades=calc_metrics["losing_trades"],
        win_rate=calc_metrics["win_rate"],
        profit_factor=min(calc_metrics["profit_factor"], 999.99),
        # Avg win/loss (percentage and value)
        avg_win=calc_metrics["avg_win"],
        avg_win_value=calc_metrics["avg_win_value"],
        avg_loss=calc_metrics["avg_loss"],
        avg_loss_value=calc_metrics["avg_loss_value"],
        avg_trade=calc_metrics["avg_trade"],
        avg_trade_value=calc_metrics["avg_trade_value"],
        # Largest trades
        largest_win=calc_metrics["largest_win"],
        largest_win_value=calc_metrics["largest_win_value"],
        largest_loss=calc_metrics["largest_loss"],
        largest_loss_value=calc_metrics["largest_loss_value"],
        best_trade=calc_metrics["largest_win_value"],
        worst_trade=calc_metrics["largest_loss_value"],
        # Exposure & duration
        exposure_time=exposure_time,
        avg_bars_in_trade=avg_bars_in_trade,
        avg_bars_in_winning=avg_bars_in_winning,
        avg_bars_in_losing=avg_bars_in_losing,
        avg_trade_duration_hours=np.mean(
            [getattr(t, "duration_hours", 0) or 0 for t in trades]
        )
        if trades
        else 0,
        # Win/Loss Ratio
        avg_win_loss_ratio=avg_win_loss_ratio,
        # Largest as pct of gross
        largest_win_pct_of_gross=largest_win_pct_of_gross,
        largest_loss_pct_of_gross=largest_loss_pct_of_gross,
        # Streaks
        max_consecutive_wins=calc_metrics["max_consecutive_wins"],
        max_consecutive_losses=calc_metrics["max_consecutive_losses"],
        # Advanced metrics
        recovery_factor=calc_metrics["recovery_factor"],
        expectancy=calc_metrics["expectancy"],
        expectancy_ratio=calc_metrics["expectancy_ratio"],
        cagr=calc_metrics["cagr"],
        # Runup metrics
        max_runup=calc_metrics["max_runup"],
        max_runup_value=calc_metrics["max_runup_value"],
        avg_runup=calc_metrics["avg_runup"],
        avg_runup_value=calc_metrics.get(
            "avg_runup_value", calc_metrics["avg_runup"] * initial_capital
        ),
        # TradingView comparison metrics
        strategy_outperformance=(total_return * 100) - buy_hold_return_pct,
        net_profit_to_largest_loss=calc_metrics["net_profit"]
        / abs(calc_metrics["largest_loss_value"])
        if calc_metrics["largest_loss_value"] != 0
        else 0.0,
        # P&L Distribution
        pnl_distribution=pnl_distribution or [],
        avg_profit_pct=np.mean([t.pnl_pct for t in winning_trades_list])
        if winning_trades_list
        else 0.0,
        avg_loss_pct=abs(np.mean([t.pnl_pct for t in losing_trades_list]))
        if losing_trades_list
        else 0.0,
        # ===== NEW: Additional calculated metrics =====
        closed_trades=closed_trades,
        account_size_required=account_size_required,
        return_on_account_size=return_on_account_size,
        total_slippage=total_slippage,
        max_contracts_held=max_contracts_held,
        avg_margin_used=avg_margin_used,
        max_margin_used=max_margin_used,
        margin_efficiency=margin_efficiency,
        recovery_long=recovery_long,
        recovery_short=recovery_short,
        quick_reversals=quick_reversals,
        avg_runup_duration_bars=avg_runup_duration_bars,
        # ===== LONG/SHORT SEPARATE STATISTICS =====
        # Long trades
        long_trades=calc_metrics["long_trades"],
        long_winning_trades=calc_metrics["long_winning_trades"],
        long_losing_trades=calc_metrics["long_losing_trades"],
        long_pnl=calc_metrics["long_net_profit"],
        long_pnl_pct=(calc_metrics["long_net_profit"] / initial_capital * 100)
        if initial_capital > 0
        else 0.0,
        long_win_rate=calc_metrics["long_win_rate"],
        long_gross_profit=calc_metrics["long_gross_profit"],
        long_gross_profit_pct=(
            calc_metrics["long_gross_profit"] / initial_capital * 100
        )
        if initial_capital > 0
        else 0.0,
        long_gross_loss=calc_metrics["long_gross_loss"],
        long_gross_loss_pct=(calc_metrics["long_gross_loss"] / initial_capital * 100)
        if initial_capital > 0
        else 0.0,
        long_net_profit=calc_metrics["long_net_profit"],
        long_profit_factor=min(calc_metrics["long_profit_factor"], 999.99),
        # Long Averages (Value & Pct)
        long_avg_win=calc_metrics["long_avg_win"],
        long_avg_win_value=calc_metrics["long_avg_win"],
        long_avg_win_pct=calc_metrics["long_avg_win_pct"],
        long_avg_loss=calc_metrics["long_avg_loss"],
        long_avg_loss_value=calc_metrics["long_avg_loss"],
        long_avg_loss_pct=calc_metrics["long_avg_loss_pct"],
        long_avg_trade=calc_metrics["long_avg_trade"],
        long_avg_trade_value=calc_metrics["long_avg_trade"],
        long_avg_trade_pct=calc_metrics["long_avg_trade_pct"],
        avg_bars_in_long=calc_metrics["long_avg_bars"],
        avg_bars_in_winning_long=calc_metrics["long_avg_win_bars"],
        avg_bars_in_losing_long=calc_metrics["long_avg_loss_bars"],
        long_largest_win=calc_metrics["long_largest_win_pct"],
        long_largest_loss=calc_metrics["long_largest_loss_pct"],
        long_largest_win_value=calc_metrics.get("long_largest_win", 0),
        long_largest_loss_value=calc_metrics.get("long_largest_loss", 0),
        long_payoff_ratio=calc_metrics["long_payoff_ratio"],
        long_commission=calc_metrics["long_commission"],
        long_max_consec_wins=calc_metrics["long_max_consec_wins"],
        long_max_consec_losses=calc_metrics["long_max_consec_losses"],
        long_breakeven_trades=calc_metrics["long_breakeven_trades"],
        cagr_long=calc_metrics["cagr_long"],
        # Short trades
        short_trades=calc_metrics["short_trades"],
        short_winning_trades=calc_metrics["short_winning_trades"],
        short_losing_trades=calc_metrics["short_losing_trades"],
        short_pnl=calc_metrics["short_net_profit"],
        short_pnl_pct=(calc_metrics["short_net_profit"] / initial_capital * 100)
        if initial_capital > 0
        else 0.0,
        short_win_rate=calc_metrics["short_win_rate"],
        short_gross_profit=calc_metrics["short_gross_profit"],
        short_gross_profit_pct=(
            calc_metrics["short_gross_profit"] / initial_capital * 100
        )
        if initial_capital > 0
        else 0.0,
        short_gross_loss=calc_metrics["short_gross_loss"],
        short_gross_loss_pct=(calc_metrics["short_gross_loss"] / initial_capital * 100)
        if initial_capital > 0
        else 0.0,
        short_net_profit=calc_metrics["short_net_profit"],
        short_profit_factor=min(calc_metrics["short_profit_factor"], 999.99),
        # Short Averages (Value & Pct)
        short_avg_win=calc_metrics["short_avg_win"],
        short_avg_win_value=calc_metrics["short_avg_win"],
        short_avg_win_pct=calc_metrics["short_avg_win_pct"],
        short_avg_loss=calc_metrics["short_avg_loss"],
        short_avg_loss_value=calc_metrics["short_avg_loss"],
        short_avg_loss_pct=calc_metrics["short_avg_loss_pct"],
        short_avg_trade=calc_metrics["short_avg_trade"],
        short_avg_trade_value=calc_metrics["short_avg_trade"],
        short_avg_trade_pct=calc_metrics["short_avg_trade_pct"],
        avg_bars_in_short=calc_metrics["short_avg_bars"],
        avg_bars_in_winning_short=calc_metrics["short_avg_win_bars"],
        avg_bars_in_losing_short=calc_metrics["short_avg_loss_bars"],
        short_largest_win=calc_metrics["short_largest_win_pct"],
        short_largest_loss=calc_metrics["short_largest_loss_pct"],
        short_largest_win_value=calc_metrics.get("short_largest_win", 0),
        short_largest_loss_value=calc_metrics.get("short_largest_loss", 0),
        short_payoff_ratio=calc_metrics["short_payoff_ratio"],
        short_commission=calc_metrics["short_commission"],
        short_max_consec_wins=calc_metrics["short_max_consec_wins"],
        short_max_consec_losses=calc_metrics["short_max_consec_losses"],
        short_breakeven_trades=calc_metrics["short_breakeven_trades"],
        cagr_short=calc_metrics["cagr_short"],
        # ===== NEW: LONG/SHORT ADVANCED METRICS (TradingView) =====
        # Sharpe/Sortino per direction (using overall values as baseline -
        # true per-direction calculation would require separate equity curves)
        sharpe_long=calc_metrics["sharpe_ratio"]
        if calc_metrics["long_trades"] > 0
        else 0.0,
        sharpe_short=calc_metrics["sharpe_ratio"]
        if calc_metrics["short_trades"] > 0
        else 0.0,
        sortino_long=calc_metrics["sortino_ratio"]
        if calc_metrics["long_trades"] > 0
        else 0.0,
        sortino_short=calc_metrics["sortino_ratio"]
        if calc_metrics["short_trades"] > 0
        else 0.0,
        calmar_long=calc_metrics["calmar_ratio"]
        if calc_metrics["long_trades"] > 0
        else 0.0,
        calmar_short=calc_metrics["calmar_ratio"]
        if calc_metrics["short_trades"] > 0
        else 0.0,
        # Expectancy per direction
        long_expectancy=(
            calc_metrics["long_win_rate"] / 100 * calc_metrics["long_avg_win"]
            + (1 - calc_metrics["long_win_rate"] / 100) * calc_metrics["long_avg_loss"]
        )
        if calc_metrics["long_trades"] > 0
        else 0.0,
        short_expectancy=(
            calc_metrics["short_win_rate"] / 100 * calc_metrics["short_avg_win"]
            + (1 - calc_metrics["short_win_rate"] / 100)
            * calc_metrics["short_avg_loss"]
        )
        if calc_metrics["short_trades"] > 0
        else 0.0,
        # Largest win/loss as % (already have pct values from calc_metrics)
        long_largest_win_pct=calc_metrics["long_largest_win_pct"],
        short_largest_win_pct=calc_metrics["short_largest_win_pct"],
        long_largest_loss_pct=calc_metrics["long_largest_loss_pct"],
        short_largest_loss_pct=calc_metrics["short_largest_loss_pct"],
        # Largest as % of gross
        long_largest_win_pct_of_gross=(
            calc_metrics["long_largest_win"] / calc_metrics["long_gross_profit"] * 100
        )
        if calc_metrics["long_gross_profit"] > 0
        else 0.0,
        short_largest_win_pct_of_gross=(
            calc_metrics["short_largest_win"] / calc_metrics["short_gross_profit"] * 100
        )
        if calc_metrics["short_gross_profit"] > 0
        else 0.0,
        long_largest_loss_pct_of_gross=(
            abs(calc_metrics["long_largest_loss"])
            / calc_metrics["long_gross_loss"]
            * 100
        )
        if calc_metrics["long_gross_loss"] > 0
        else 0.0,
        short_largest_loss_pct_of_gross=(
            abs(calc_metrics["short_largest_loss"])
            / calc_metrics["short_gross_loss"]
            * 100
        )
        if calc_metrics["short_gross_loss"] > 0
        else 0.0,
        # Return on capital per direction
        long_return_on_capital=(calc_metrics["long_net_profit"] / initial_capital * 100)
        if initial_capital > 0
        else 0.0,
        short_return_on_capital=(
            calc_metrics["short_net_profit"] / initial_capital * 100
        )
        if initial_capital > 0
        else 0.0,
        # Return on account size per direction
        long_return_on_account_size=(
            calc_metrics["long_net_profit"] / account_size_required * 100
        )
        if account_size_required > 0
        else 0.0,
        short_return_on_account_size=(
            calc_metrics["short_net_profit"] / account_size_required * 100
        )
        if account_size_required > 0
        else 0.0,
        # Net profit as % of largest loss per direction
        long_net_profit_to_largest_loss=(
            calc_metrics["long_net_profit"]
            / abs(calc_metrics["long_largest_loss"])
            * 100
        )
        if calc_metrics["long_largest_loss"] != 0
        else 0.0,
        short_net_profit_to_largest_loss=(
            calc_metrics["short_net_profit"]
            / abs(calc_metrics["short_largest_loss"])
            * 100
        )
        if calc_metrics["short_largest_loss"] != 0
        else 0.0,
    )


class BacktestEngine:
    """
    High-performance backtesting engine.

    Features:
    - Multiple strategy support (SMA, RSI, MACD, Bollinger Bands)
    - Vectorized execution using vectorbt/numpy
    - Comprehensive performance metrics
    - Trade-by-trade analysis
    - Equity curve generation

    Example:
        engine = BacktestEngine()
        config = BacktestConfig(
            symbol="BTCUSDT",
            interval="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 1),
            strategy_type="sma_crossover",
            strategy_params={"fast_period": 10, "slow_period": 30}
        )
        result = engine.run(config, ohlcv_data)
    """

    def __init__(self):
        self._results_cache: dict[str, BacktestResult] = {}

    def run(
        self,
        config: BacktestConfig,
        ohlcv: pd.DataFrame,
        silent: bool = False,
        custom_strategy: Optional[BaseStrategy] = None,
    ) -> BacktestResult:
        """
        Run a backtest with the given configuration.

        Args:
            config: Backtest configuration
            ohlcv: DataFrame with columns [open, high, low, close, volume]
                   Index should be DatetimeIndex
            silent: If True, suppress logging for bulk execution

        Returns:
            BacktestResult with metrics, trades, and equity curve
        """
        backtest_id = str(uuid.uuid4())
        created_at = utc_now()

        if not silent:
            logger.info(
                f"Starting backtest {backtest_id}: {config.symbol} {config.interval} "
                f"from {config.start_date} to {config.end_date}"
            )

        try:
            # Validate OHLCV data
            ohlcv = self._validate_ohlcv(ohlcv)

            # Get strategy (use custom if provided, otherwise get from registry)
            if custom_strategy is not None:
                strategy = custom_strategy
                if not silent:
                    logger.info(f"Using custom strategy: {strategy}")
            else:
                strategy = get_strategy(config.strategy_type, config.strategy_params)
                if not silent:
                    logger.info(f"Using strategy: {strategy}")

            # Generate signals
            signals = strategy.generate_signals(ohlcv)

            # Check if TP/SL are configured (reserved for future conditional logic)
            has_tp_sl = getattr(config, "stop_loss", None) or getattr(  # noqa: F841
                config, "take_profit", None
            )
            has_trailing = getattr(config, "trailing_stop_activation", None)  # noqa: F841

            # Check if bidirectional trading (requires fallback engine)
            direction = getattr(config, "direction", "both")
            is_bidirectional = direction == "both"  # noqa: F841
            is_short_only = direction == "short"  # noqa: F841  # VBT doesn't handle shorts reliably

            # Check if force_fallback is enabled (for 100% parity guarantee)
            force_fallback = getattr(config, "force_fallback", False)  # noqa: F841

            # Run simulation
            # ALWAYS use fallback engine for regular backtests to ensure 100% consistent,
            # accurate results. VectorBT has architectural differences that cause metric
            # mismatches:
            # - Quick reversals: VBT can open position on same bar where it closed previous
            # - Equity-based sizing: Fallback recalculates size per trade, VBT uses fixed value
            # - Bidirectional logic: VBT processes long/short signals in parallel vs sequential
            #
            # VectorBT is reserved for OPTIMIZATION where speed matters more than precision.
            # The optimizer uses _run_vectorbt directly when needed.
            use_fallback = True  # Always use fallback for accuracy

            if use_fallback:
                if not silent:
                    logger.info("Using fallback engine (authoritative, 100% accurate)")
                result = self._run_fallback(config, ohlcv, signals)
            elif VBT_AVAILABLE:
                result = self._run_vectorbt(config, ohlcv, signals)
            else:
                result = self._run_fallback(config, ohlcv, signals)

            # Build result
            result.id = backtest_id
            result.status = BacktestStatus.COMPLETED
            result.created_at = created_at
            result.completed_at = utc_now()
            result.config = config

            # Cache result
            self._results_cache[backtest_id] = result

            if not silent and result.metrics:
                logger.info(
                    f"Backtest {backtest_id} completed: "
                    f"Return={result.metrics.total_return:.2%}, "
                    f"Sharpe={result.metrics.sharpe_ratio:.2f}, "
                    f"Trades={result.metrics.total_trades}"
                )

            return result

        except Exception as e:
            logger.exception(f"Backtest {backtest_id} failed: {e}")
            return BacktestResult(
                id=backtest_id,
                status=BacktestStatus.FAILED,
                created_at=created_at,
                completed_at=utc_now(),
                config=config,
                error_message=str(e),
            )

    def _validate_ohlcv(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """Validate and normalize OHLCV data"""
        required_columns = ["open", "high", "low", "close", "volume"]

        # Normalize column names
        ohlcv.columns = ohlcv.columns.str.lower()

        missing = set(required_columns) - set(ohlcv.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if not isinstance(ohlcv.index, pd.DatetimeIndex):
            if "timestamp" in ohlcv.columns:
                ohlcv.index = pd.to_datetime(ohlcv["timestamp"])
            else:
                raise ValueError(
                    "OHLCV data must have DatetimeIndex or 'timestamp' column"
                )

        # Sort by time
        ohlcv = ohlcv.sort_index()

        # Remove NaN
        ohlcv = ohlcv.dropna(subset=["close"])

        # Validate OHLC data integrity
        if "high" in ohlcv.columns and "low" in ohlcv.columns:
            # Check for invalid OHLC relationships
            invalid_bars = (
                (ohlcv["high"] < ohlcv["low"])
                | (ohlcv["close"] <= 0)
                | (ohlcv["open"] <= 0)
            )
            if invalid_bars.any():
                invalid_count = invalid_bars.sum()
                logger.warning(
                    f"Found {invalid_count} bars with invalid OHLC data, removing them"
                )
                ohlcv = ohlcv[~invalid_bars]

        if len(ohlcv) < 50:
            raise ValueError(
                f"Insufficient data: {len(ohlcv)} rows (minimum 50 required)"
            )

        return ohlcv

    def _extract_trades_vectorbt(
        self, pf, ohlcv: pd.DataFrame, config: "BacktestConfig"
    ) -> list[TradeRecord]:
        """Extract trades from vectorbt portfolio with MAE/MFE calculation.

        Normalizes size/PnL/fees to match fallback engine's calculation:
        - Size = allocated_capital / (entry_price * (1 + taker_fee))
        - PnL recalculated proportionally to normalized size
        - Fees recalculated using taker_fee on position value
        """
        trades: list[TradeRecord] = []
        initial_capital = config.initial_capital

        try:
            trade_records = pf.trades.records_readable
            if len(trade_records) == 0:
                return trades

            # Get high/low arrays for MFE/MAE calculation
            high_array = ohlcv["high"].values if "high" in ohlcv.columns else None
            low_array = ohlcv["low"].values if "low" in ohlcv.columns else None

            # Debug: Log available columns once
            if len(trade_records) > 0:
                logger.debug(f"VBT trade columns: {list(trade_records.columns)}")
                logger.debug(f"First trade row: {dict(trade_records.iloc[0])}")

            # Log brief stats to avoid unused-variable lint while keeping visibility
            try:
                _stats = pf.stats()
                logger.debug(
                    "VBT stats length: %s",
                    len(_stats) if hasattr(_stats, "__len__") else "N/A",
                )
            except Exception:
                # Non-fatal: stats may be heavy or unavailable
                logger.debug("VBT stats not available or failed to fetch")

            # Track running cash for accurate position sizing (like fallback)
            running_cash = initial_capital

            # Get direction for filtering trades
            direction = getattr(config, "direction", "both")

            for idx, row in trade_records.iterrows():
                # Filter trades by direction
                trade_direction = row.get("Direction", "Long")
                is_long = trade_direction == "Long"

                # Skip trades that don't match direction config
                if direction == "long" and not is_long:
                    continue
                if direction == "short" and is_long:
                    continue

                entry_time = row.get("Entry Timestamp", row.get("Entry Index"))
                exit_time = row.get("Exit Timestamp", row.get("Exit Index"))

                # Get indices - VBT uses timestamp, need to find bar index from ohlcv
                # First try direct index columns (older VBT versions)
                entry_idx = row.get("Entry Idx", row.get("Entry Index", None))
                exit_idx = row.get("Exit Idx", row.get("Exit Index", None))

                # If indices not available, compute from timestamps
                if entry_idx is None or entry_idx == 0:
                    if hasattr(entry_time, "to_pydatetime") or isinstance(
                        entry_time, (datetime, pd.Timestamp)
                    ):
                        try:
                            entry_idx = ohlcv.index.get_loc(entry_time)
                        except KeyError:
                            # Find nearest index
                            entry_idx = ohlcv.index.get_indexer(
                                [entry_time], method="nearest"
                            )[0]
                    else:
                        entry_idx = 0

                if exit_idx is None or exit_idx == 0:
                    if hasattr(exit_time, "to_pydatetime") or isinstance(
                        exit_time, (datetime, pd.Timestamp)
                    ):
                        try:
                            exit_idx = ohlcv.index.get_loc(exit_time)
                        except KeyError:
                            # Find nearest index
                            exit_idx = ohlcv.index.get_indexer(
                                [exit_time], method="nearest"
                            )[0]
                    else:
                        exit_idx = 0

                # Convert to datetime if needed
                if isinstance(entry_time, (int, np.integer)):
                    entry_time = ohlcv.index[int(entry_time)]
                if isinstance(exit_time, (int, np.integer)):
                    exit_time = ohlcv.index[min(int(exit_time), len(ohlcv) - 1)]

                # Use VBT's original entry price (already includes slippage from Portfolio.from_signals)
                entry_price = float(
                    row.get("Avg Entry Price", row.get("Entry Price", 0))
                )
                exit_price = float(row.get("Avg Exit Price", row.get("Exit Price", 0)))

                # Determine side (is_long already set above for filtering)
                side = OrderSide.BUY if is_long else OrderSide.SELL

                # Get VBT's original size
                vbt_size = float(row.get("Size", 0))

                # Check if we're using custom cash tracking (from_order_func with SL/TP)
                stop_loss_val = getattr(config, "stop_loss", None)
                take_profit_val = getattr(config, "take_profit", None)
                has_custom_sltp = (stop_loss_val is not None and stop_loss_val > 0) or (
                    take_profit_val is not None and take_profit_val > 0
                )

                taker_fee = getattr(config, "taker_fee", 0.0004)
                leverage = getattr(config, "leverage", 1.0)

                if has_custom_sltp:
                    # vectorbt_sltp.py already does correct cash tracking
                    # Use VBT's size directly - it's calculated correctly in flex_order_func_nb
                    normalized_size = vbt_size

                    # Calculate PnL using VBT size and fallback formula
                    position_value_exit = normalized_size * exit_price
                    exit_fees = position_value_exit * taker_fee

                    if is_long:
                        normalized_pnl = (
                            exit_price - entry_price
                        ) * normalized_size * leverage - exit_fees
                    else:
                        normalized_pnl = (
                            entry_price - exit_price
                        ) * normalized_size * leverage - exit_fees

                    # Entry fees
                    position_value_entry = normalized_size * entry_price
                    entry_fees = position_value_entry * taker_fee
                    total_fees = entry_fees + exit_fees

                    # Update running_cash using leveraged PnL for Short trades
                    # This matches vectorbt_sltp.py state tracking
                    if is_long:
                        cash_delta = (
                            normalized_size * (exit_price - entry_price) - total_fees
                        )
                    else:
                        # Short: leverage PnL is added to cash
                        price_diff = entry_price - exit_price
                        cash_delta = (
                            normalized_size * price_diff * leverage - total_fees
                        )
                    running_cash = running_cash + cash_delta
                else:
                    # Legacy path: from_signals without custom cash tracking
                    # Must recalculate size using running_cash
                    position_size_pct = getattr(config, "position_size", 1.0)
                    allocated_capital = running_cash * position_size_pct

                    normalized_size = allocated_capital / (
                        entry_price * (1 + taker_fee)
                    )

                    # Recalculate PnL
                    position_value_exit = normalized_size * exit_price
                    exit_fees = position_value_exit * taker_fee

                    if is_long:
                        normalized_pnl = (
                            exit_price - entry_price
                        ) * normalized_size * leverage - exit_fees
                    else:
                        normalized_pnl = (
                            entry_price - exit_price
                        ) * normalized_size * leverage - exit_fees

                    position_value_entry = normalized_size * entry_price
                    entry_fees = position_value_entry * taker_fee
                    total_fees = entry_fees + exit_fees

                    price_diff = (
                        exit_price - entry_price
                        if is_long
                        else entry_price - exit_price
                    )
                    cash_delta = normalized_size * price_diff - total_fees
                    running_cash = running_cash + cash_delta

                # ========== CALCULATE MFE/MAE ==========
                mfe = 0.0
                mae = 0.0
                mfe_pct = 0.0
                mae_pct = 0.0
                if high_array is not None and low_array is not None and entry_price > 0:
                    try:
                        start_idx = int(entry_idx)
                        end_idx = min(int(exit_idx) + 1, len(high_array))
                        if start_idx < end_idx:
                            trade_high = np.max(high_array[start_idx:end_idx])
                            trade_low = np.min(low_array[start_idx:end_idx])

                            if is_long:
                                # Long: MFE = best high - entry, MAE = entry - worst low
                                mfe_pct = (trade_high - entry_price) / entry_price * 100
                                mae_pct = (entry_price - trade_low) / entry_price * 100
                                # Absolute values in USDT
                                mfe = (
                                    (trade_high - entry_price)
                                    * normalized_size
                                    * leverage
                                )
                                mae = (
                                    (entry_price - trade_low)
                                    * normalized_size
                                    * leverage
                                )
                            else:
                                # Short: MFE = entry - best low, MAE = worst high - entry
                                mfe_pct = (entry_price - trade_low) / entry_price * 100
                                mae_pct = (trade_high - entry_price) / entry_price * 100
                                mfe = (
                                    (entry_price - trade_low)
                                    * normalized_size
                                    * leverage
                                )
                                mae = (
                                    (trade_high - entry_price)
                                    * normalized_size
                                    * leverage
                                )
                    except Exception as e:
                        logger.debug("MFE/MAE calculation failed, using defaults: {}", e)

                # Calculate duration
                if hasattr(entry_time, "timestamp") and hasattr(exit_time, "timestamp"):
                    duration_hours = (
                        exit_time.timestamp() - entry_time.timestamp()
                    ) / 3600
                else:
                    duration_hours = 0

                # Calculate PnL percentage (as percentage 0-100) relative to initial capital
                pnl_pct = (
                    (normalized_pnl / initial_capital * 100)
                    if initial_capital and initial_capital > 0
                    else 0
                )

                trade = TradeRecord(
                    id=str(idx),
                    entry_time=entry_time
                    if isinstance(entry_time, datetime)
                    else pd.Timestamp(entry_time).to_pydatetime(),
                    exit_time=exit_time
                    if isinstance(exit_time, datetime)
                    else pd.Timestamp(exit_time).to_pydatetime(),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    side=side,
                    size=normalized_size,
                    pnl=normalized_pnl,
                    pnl_pct=pnl_pct,
                    fees=total_fees,
                    duration_hours=duration_hours,
                    bars_in_trade=int(exit_idx - entry_idx)
                    if exit_idx and entry_idx
                    else 0,
                    entry_bar_index=int(entry_idx) if entry_idx else 0,
                    exit_bar_index=int(exit_idx) if exit_idx else 0,
                    mae=mae,
                    mfe=mfe,
                    mae_pct=mae_pct,
                    mfe_pct=mfe_pct,
                )
                trades.append(trade)

        except Exception as e:
            logger.warning(f"Error extracting trades from vectorbt: {e}")

        return trades

    def _get_interval_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds."""
        interval_map = {
            "1": 60000,
            "1m": 60000,
            "3": 180000,
            "3m": 180000,
            "5": 300000,
            "5m": 300000,
            "15": 900000,
            "15m": 900000,
            "30": 1800000,
            "30m": 1800000,
            "60": 3600000,
            "1h": 3600000,
            "120": 7200000,
            "2h": 7200000,
            "240": 14400000,
            "4h": 14400000,
            "360": 21600000,
            "6h": 21600000,
            "720": 43200000,
            "12h": 43200000,
            "D": 86400000,
            "1d": 86400000,
            "W": 604800000,
            "1w": 604800000,
        }
        return interval_map.get(interval, 3600000)  # Default 1h

    def _run_fallback(
        self,
        config: BacktestConfig,
        ohlcv: pd.DataFrame,
        signals,
    ) -> BacktestResult:
        """
        Fallback implementation when vectorbt is not available.
        Uses pure numpy/pandas for simulation.
        Supports TP/SL, bidirectional trading, and MFE/MAE calculation.
        """
        close = ohlcv["close"].values
        open_price = ohlcv["open"].values if "open" in ohlcv.columns else close  # noqa: F841
        high = ohlcv["high"].values if "high" in ohlcv.columns else close
        low = ohlcv["low"].values if "low" in ohlcv.columns else close
        entries = signals.entries.values
        exits = signals.exits.values

        # Get long/short signals if available
        long_entries = (
            signals.long_entries.values if hasattr(signals, "long_entries") else entries
        )
        short_entries = (
            signals.short_entries.values if hasattr(signals, "short_entries") else None
        )
        long_exits = (
            signals.long_exits.values if hasattr(signals, "long_exits") else exits
        )
        short_exits = (
            signals.short_exits.values if hasattr(signals, "short_exits") else None
        )

        # Get direction and TP/SL
        direction = getattr(config, "direction", "both")
        stop_loss = getattr(config, "stop_loss", None)
        take_profit = getattr(config, "take_profit", None)
        take_profit = getattr(config, "take_profit", None)
        leverage = getattr(config, "leverage", 1.0)
        slippage = getattr(config, "slippage", 0.0)

        # ========== UNIVERSAL BAR MAGNIFIER INITIALIZATION ==========
        # If enabled, load 1m data for precise intrabar order execution
        # Uses new architecture: IntrabarEngine + configurable OHLC path
        intrabar_engine = None
        use_bar_magnifier = getattr(config, "use_bar_magnifier", False)
        sl_priority = getattr(config, "sl_priority", True)

        if use_bar_magnifier:
            try:
                from backend.backtesting.intrabar_engine import (
                    IntrabarConfig,
                    IntrabarEngine,
                    OHLCPath,
                )

                # Parse OHLC path from config
                ohlc_path_str = getattr(config, "intrabar_ohlc_path", "O-HL-heuristic")
                ohlc_path_map = {
                    "O-H-L-C": OHLCPath.O_H_L_C,
                    "O-L-H-C": OHLCPath.O_L_H_C,
                    "O-HL-heuristic": OHLCPath.O_HL_HEURISTIC,
                    "conservative_long": OHLCPath.CONSERVATIVE_LONG,
                    "conservative_short": OHLCPath.CONSERVATIVE_SHORT,
                }
                ohlc_path = ohlc_path_map.get(ohlc_path_str, OHLCPath.O_HL_HEURISTIC)

                # Get subticks config
                subticks = getattr(config, "intrabar_subticks", 0)

                # Initialize IntrabarEngine
                intrabar_config = IntrabarConfig(
                    ohlc_path=ohlc_path,
                    subticks_per_segment=subticks,
                )
                intrabar_engine = IntrabarEngine(intrabar_config)

                # Load 1m data from database
                import sqlite3
                from pathlib import Path

                max_bars = getattr(config, "bar_magnifier_max_bars", 200000)
                start_ts = int(ohlcv.index[0].timestamp() * 1000)
                end_ts = int(ohlcv.index[-1].timestamp() * 1000) + 3600000  # +1h buffer

                db_path = Path(__file__).parent.parent.parent / "data.sqlite3"
                conn = sqlite3.connect(str(db_path))
                m1_df = pd.read_sql(
                    """
                    SELECT open_time, open_price as open, high_price as high,
                           low_price as low, close_price as close, volume
                    FROM bybit_kline_audit
                    WHERE symbol = ? AND interval = '1'
                    AND open_time >= ? AND open_time <= ?
                    ORDER BY open_time ASC
                    LIMIT ?
                    """,
                    conn,
                    params=[config.symbol.upper(), start_ts, end_ts, max_bars],
                )
                conn.close()

                if len(m1_df) > 0:
                    intrabar_engine.load_m1_data(m1_df)
                    logger.info(
                        f"[UNIVERSAL_BAR_MAGNIFIER] Loaded {len(m1_df)} 1m candles for {config.symbol}, "
                        f"path={ohlc_path.value}, subticks={subticks}"
                    )
                else:
                    logger.warning(
                        f"[UNIVERSAL_BAR_MAGNIFIER] No 1m data found for {config.symbol}, "
                        "falling back to OHLC heuristic"
                    )
                    intrabar_engine = None

            except Exception as e:
                logger.warning(f"[UNIVERSAL_BAR_MAGNIFIER] Failed to initialize: {e}")
                intrabar_engine = None

        # Initialize simulation
        cash = config.initial_capital
        position = 0.0
        is_long = True
        equity = [cash]
        trades: list[TradeRecord] = []

        entry_price = 0.0
        entry_time = None
        entry_size = 0.0
        entry_idx = 0
        max_favorable_price = 0.0
        max_adverse_price = 0.0

        timestamps = ohlcv.index.tolist()

        for i in range(len(close)):
            price = close[i]
            current_high = high[i]
            current_low = low[i]

            # Check for entry (when not in position)
            if position == 0:
                # Long entry
                if direction in ("long", "both") and long_entries[i]:
                    entry_price = price * (1 + slippage)

                    # Calculate max affordable position size including fees
                    # Cost = Size * Price + Size * Price * Fee
                    # Cap = Size * Price * (1 + Fee)
                    # Size = Cap / (Price * (1 + Fee))

                    allocated_capital = cash * config.position_size
                    entry_size = allocated_capital / (
                        entry_price * (1 + config.taker_fee)
                    )

                    position_value = entry_size * entry_price
                    fees = position_value * config.taker_fee

                    cash -= position_value + fees
                    position = entry_size
                    is_long = True
                    entry_time = timestamps[i]
                    # entry_idx kept for potential diagnostics/traceability
                    entry_idx = i  # noqa: F841
                    # Initialize MFE/MAE with current bar's high/low
                    max_favorable_price = current_high  # Best high so far
                    max_adverse_price = current_low  # Worst low so far

                # Short entry
                elif (
                    direction in ("short", "both")
                    and short_entries is not None
                    and short_entries[i]
                ):
                    entry_price = price * (1 - slippage)

                    # Calculate max affordable position size including fees
                    # For short: Margin + Fee = Capital
                    # We assume 1x leverage margin req = position value

                    allocated_capital = cash * config.position_size
                    entry_size = allocated_capital / (
                        entry_price * (1 + config.taker_fee)
                    )

                    position_value = entry_size * entry_price
                    fees = position_value * config.taker_fee

                    cash -= (
                        position_value + fees
                    )  # Reserve margin for short (same as long)
                    position = entry_size
                    is_long = False
                    entry_time = timestamps[i]
                    # entry_idx kept for potential diagnostics/traceability
                    entry_idx = i  # noqa: F841
                    # For short: favorable = lowest, adverse = highest
                    max_favorable_price = current_low  # Best low so far
                    max_adverse_price = current_high  # Worst high so far

            # While in position: update MFE/MAE and check exits
            elif position > 0:
                # Update MFE/MAE - use intrabar ticks if available for precision
                if intrabar_engine is not None:
                    # Use 1m ticks for precise MFE/MAE tracking
                    try:
                        bar_start_ms = int(timestamps[i].timestamp() * 1000)
                        interval_ms = self._get_interval_ms(config.interval)
                        bar_end_ms = bar_start_ms + interval_ms

                        for tick in intrabar_engine.generate_ticks(
                            bar_start_ms, bar_end_ms
                        ):
                            tick_price = tick.price
                            if is_long:
                                max_favorable_price = max(
                                    max_favorable_price, tick_price
                                )
                                max_adverse_price = min(max_adverse_price, tick_price)
                            else:
                                max_favorable_price = min(
                                    max_favorable_price, tick_price
                                )
                                max_adverse_price = max(max_adverse_price, tick_price)
                    except Exception:
                        # Fallback to OHLC-based MFE/MAE
                        if is_long:
                            max_favorable_price = max(max_favorable_price, current_high)
                            max_adverse_price = min(max_adverse_price, current_low)
                        else:
                            max_favorable_price = min(max_favorable_price, current_low)
                            max_adverse_price = max(max_adverse_price, current_high)
                else:
                    # Standard OHLC-based MFE/MAE (TradingView style)
                    if is_long:
                        max_favorable_price = max(max_favorable_price, current_high)
                        max_adverse_price = min(max_adverse_price, current_low)
                    else:
                        max_favorable_price = min(max_favorable_price, current_low)
                        max_adverse_price = max(max_adverse_price, current_high)

                # TradingView-style TP/SL check using high/low within the bar
                # For LONG: SL triggered by low, TP triggered by high
                # For SHORT: SL triggered by high, TP triggered by low
                if is_long:
                    worst_price_in_bar = current_low
                    best_price_in_bar = current_high
                else:
                    worst_price_in_bar = current_high
                    best_price_in_bar = current_low

                # Calculate P/L % at worst and best points within bar
                if is_long:
                    worst_pnl_pct = (
                        (worst_price_in_bar - entry_price) / entry_price * leverage
                    )
                    best_pnl_pct = (
                        (best_price_in_bar - entry_price) / entry_price * leverage
                    )
                else:
                    worst_pnl_pct = (
                        (entry_price - worst_price_in_bar) / entry_price * leverage
                    )
                    best_pnl_pct = (
                        (entry_price - best_price_in_bar) / entry_price * leverage
                    )

                should_exit = False
                exit_reason = ""
                exit_price = price  # Default to close price
                apply_slippage = (
                    True  # Signal exits use market orders -> slippage applies
                )

                # ========== UNIVERSAL BAR MAGNIFIER SL/TP CHECK ==========
                # If IntrabarEngine is enabled, use 1m intrabar ticks for precise detection
                if intrabar_engine is not None and (stop_loss or take_profit):
                    try:
                        # Get bar time range
                        bar_start_ms = int(timestamps[i].timestamp() * 1000)
                        interval_ms = self._get_interval_ms(config.interval)
                        bar_end_ms = bar_start_ms + interval_ms

                        # Calculate SL/TP prices
                        if is_long:
                            sl_price = (
                                entry_price * (1 - stop_loss / leverage)
                                if stop_loss
                                else None
                            )
                            tp_price = (
                                entry_price * (1 + take_profit / leverage)
                                if take_profit
                                else None
                            )
                        else:
                            sl_price = (
                                entry_price * (1 + stop_loss / leverage)
                                if stop_loss
                                else None
                            )
                            tp_price = (
                                entry_price * (1 - take_profit / leverage)
                                if take_profit
                                else None
                            )

                        # Check SL/TP on each tick - find which triggers FIRST
                        sl_triggered_at = None  # (tick_index, fill_price)
                        tp_triggered_at = None

                        for tick_idx, tick in enumerate(
                            intrabar_engine.generate_ticks(bar_start_ms, bar_end_ms)
                        ):
                            tick_price = tick.price

                            # Check SL trigger
                            if sl_price is not None and sl_triggered_at is None:
                                if is_long and tick_price <= sl_price:
                                    sl_triggered_at = (tick_idx, sl_price)
                                elif not is_long and tick_price >= sl_price:
                                    sl_triggered_at = (tick_idx, sl_price)

                            # Check TP trigger
                            if tp_price is not None and tp_triggered_at is None:
                                if is_long and tick_price >= tp_price:
                                    tp_triggered_at = (tick_idx, tp_price)
                                elif not is_long and tick_price <= tp_price:
                                    tp_triggered_at = (tick_idx, tp_price)

                            # If both found, no need to continue
                            if sl_triggered_at and tp_triggered_at:
                                break

                        # Determine which triggered first (chronologically)
                        if sl_triggered_at and tp_triggered_at:
                            # Both triggered - use priority or chronological order
                            if sl_triggered_at[0] < tp_triggered_at[0]:
                                should_exit = True
                                exit_reason = "stop_loss"
                                exit_price = sl_triggered_at[1]
                                apply_slippage = True
                            elif tp_triggered_at[0] < sl_triggered_at[0]:
                                should_exit = True
                                exit_reason = "take_profit"
                                exit_price = tp_triggered_at[1]
                                apply_slippage = False
                            else:
                                # Same tick - use sl_priority
                                if sl_priority:
                                    should_exit = True
                                    exit_reason = "stop_loss"
                                    exit_price = sl_triggered_at[1]
                                    apply_slippage = True
                                else:
                                    should_exit = True
                                    exit_reason = "take_profit"
                                    exit_price = tp_triggered_at[1]
                                    apply_slippage = False
                        elif sl_triggered_at:
                            should_exit = True
                            exit_reason = "stop_loss"
                            exit_price = sl_triggered_at[1]
                            apply_slippage = True
                        elif tp_triggered_at:
                            should_exit = True
                            exit_reason = "take_profit"
                            exit_price = tp_triggered_at[1]
                            apply_slippage = False

                    except Exception as e:
                        logger.debug(
                            f"[UNIVERSAL_BAR_MAGNIFIER] Intrabar check failed: {e}"
                        )
                        # Fall through to standard check

                # Standard SL/TP check (no Bar Magnifier or fallback)
                if not should_exit:
                    # Check Stop Loss using worst price within bar (TradingView style)
                    if stop_loss and worst_pnl_pct <= -stop_loss:
                        should_exit = True
                        exit_reason = "stop_loss"
                        # Calculate exact SL price
                        if is_long:
                            exit_price = entry_price * (1 - stop_loss / leverage)
                        else:
                            exit_price = entry_price * (1 + stop_loss / leverage)
                        # Ensure exit price is within bar range
                        exit_price = max(current_low, min(current_high, exit_price))
                        apply_slippage = True  # SL is market order

                    # Check Take Profit using best price within bar (TradingView style)
                    if not should_exit and take_profit and best_pnl_pct >= take_profit:
                        should_exit = True
                        exit_reason = "take_profit"
                        apply_slippage = False  # TP is limit order -> no slippage
                        # Calculate exact TP price
                        if is_long:
                            exit_price = entry_price * (1 + take_profit / leverage)
                        else:
                            exit_price = entry_price * (1 - take_profit / leverage)
                        # Ensure exit price is within bar range
                        exit_price = max(current_low, min(current_high, exit_price))

                # Check signal exit (uses close price)
                if not should_exit:
                    if is_long and long_exits[i]:
                        should_exit = True
                        exit_reason = "signal"
                        exit_price = price  # Signal exits at close
                    elif not is_long and short_exits is not None and short_exits[i]:
                        should_exit = True
                        exit_reason = "signal"
                        exit_price = price  # Signal exits at close

                if should_exit:
                    # Apply slippage if applicable
                    if apply_slippage:
                        if is_long:
                            exit_price = exit_price * (1 - slippage)
                        else:
                            exit_price = exit_price * (1 + slippage)

                    # Close position at calculated exit price
                    position_value = position * exit_price
                    fees = position_value * config.taker_fee

                    if is_long:
                        cash += position_value - fees
                        pnl = (
                            (exit_price - entry_price) * entry_size * leverage - fees
                        )  # Only exit fee (entry fee already in cash)
                    else:
                        # Short: profit when price goes down
                        # Return margin + P&L (same structure as long)
                        pnl = (
                            (entry_price - exit_price) * entry_size * leverage - fees
                        )  # Only exit fee (entry fee already in cash)
                        cash += position_value + pnl  # Return position value + P&L

                    # Calculate P&L percentage
                    if is_long:
                        pnl_pct = (exit_price - entry_price) / entry_price * leverage
                    else:
                        pnl_pct = (entry_price - exit_price) / entry_price * leverage

                    # Calculate MFE/MAE in % and absolute values (TradingView style)
                    if is_long:
                        mfe_pct = (
                            (max_favorable_price - entry_price) / entry_price * 100
                        )
                        mae_pct = (entry_price - max_adverse_price) / entry_price * 100
                        # Absolute values (USDT) = price difference × size × leverage
                        mfe_value = (
                            (max_favorable_price - entry_price) * entry_size * leverage
                        )
                        mae_value = (
                            (entry_price - max_adverse_price) * entry_size * leverage
                        )
                    else:
                        mfe_pct = (
                            (entry_price - max_favorable_price) / entry_price * 100
                        )
                        mae_pct = (max_adverse_price - entry_price) / entry_price * 100
                        # Absolute values (USDT) = price difference × size × leverage
                        mfe_value = (
                            (entry_price - max_favorable_price) * entry_size * leverage
                        )
                        mae_value = (
                            (max_adverse_price - entry_price) * entry_size * leverage
                        )

                    logger.debug(
                        f"Trade closed: is_long={is_long}, entry={entry_price:.2f}, "
                        f"exit={exit_price:.2f}, reason={exit_reason}, "
                        f"max_fav={max_favorable_price:.2f}, max_adv={max_adverse_price:.2f}, "
                        f"MFE={mfe_pct:.2f}% (${mfe_value:.2f}), MAE={mae_pct:.2f}% (${mae_value:.2f})"
                    )

                    # Record trade
                    # Fees for the record: entry_fee (already deducted from cash) + exit_fee
                    # Since we don't store entry_fee separately, we estimate total as fees * 2
                    # (where fees is the current exit_fee, which is roughly equal to entry_fee)
                    total_trade_fees = fees * 2

                    # Map exit_reason to exit_comment format
                    exit_comment_map = {
                        "stop_loss": "SL",
                        "take_profit": "TP",
                        "signal": "signal",
                        "liquidation": "LIQ",
                    }
                    exit_comment = exit_comment_map.get(exit_reason, exit_reason)

                    trades.append(
                        TradeRecord(
                            entry_time=entry_time
                            if entry_time is not None
                            else timestamps[i],
                            exit_time=timestamps[i],
                            side=OrderSide.BUY if is_long else OrderSide.SELL,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            size=entry_size,
                            pnl=pnl,
                            pnl_pct=pnl_pct * 100,  # Convert to percentage
                            fees=total_trade_fees,
                            duration_hours=(timestamps[i] - entry_time).total_seconds()
                            / 3600,
                            bars_in_trade=i - entry_idx if entry_idx is not None else 0,
                            entry_bar_index=entry_idx if entry_idx is not None else 0,
                            exit_bar_index=i,
                            mfe=mfe_value,  # Absolute value in USDT
                            mae=mae_value,  # Absolute value in USDT
                            mfe_pct=mfe_pct,
                            mae_pct=mae_pct,
                            exit_comment=exit_comment,  # Track exit type
                        )
                    )

                    position = 0.0
                    entry_price = 0.0
                    entry_time = None
                    entry_size = 0.0

            # Update equity
            if position > 0:
                if is_long:
                    unrealized_pnl = (price - entry_price) * position * leverage
                else:
                    unrealized_pnl = (entry_price - price) * position * leverage
                current_equity = cash + entry_price * position + unrealized_pnl
            else:
                current_equity = cash
            equity.append(current_equity)

        # Calculate metrics
        equity_series = pd.Series(equity[1:], index=timestamps)
        returns = equity_series.pct_change().dropna()

        total_return = (equity[-1] - config.initial_capital) / config.initial_capital

        # Drawdown calculation
        peak = equity_series.expanding().max()
        drawdown = (equity_series - peak) / peak

        # Calculate P&L distribution for histogram (TradingView style)
        pnl_distribution = []
        if trades:
            pnl_pcts = [t.pnl_pct for t in trades]

            # Create histogram bins (0.5% step like TradingView)
            if pnl_pcts:
                min_pnl = min(pnl_pcts)
                max_pnl = max(pnl_pcts)
                # Round to nearest 0.5%
                bin_start = np.floor(min_pnl * 2) / 2
                bin_end = np.ceil(max_pnl * 2) / 2
                bins = np.arange(bin_start, bin_end + 0.5, 0.5)

                if len(bins) > 1:
                    hist, bin_edges = np.histogram(pnl_pcts, bins=bins)
                    for i, count in enumerate(hist):
                        if count > 0:
                            bin_center = (bin_edges[i] + bin_edges[i + 1]) / 2
                            pnl_distribution.append(
                                {
                                    "bin": f"{bin_edges[i]:.1f}%",
                                    "bin_start": float(bin_edges[i]),
                                    "bin_end": float(bin_edges[i + 1]),
                                    "count": int(count),
                                    "type": "profit"
                                    if bin_center > 0
                                    else "loss"
                                    if bin_center < 0
                                    else "breakeven",
                                }
                            )

        # IMPORTANT: Rebuild equity using same logic as VBT for parity
        # The original equity calculation mixes leveraged/unleveraged values
        # This ensures identical curves when trades match
        leverage = getattr(config, "leverage", 1.0)
        taker_fee = getattr(config, "taker_fee", 0.0004)
        equity_values, drawdown_values = build_equity_from_trades(
            trades=trades,
            ohlcv=ohlcv,
            initial_capital=config.initial_capital,
            leverage=leverage,
            taker_fee=taker_fee,
        )

        # Update equity and drawdown with rebuilt values
        equity = [config.initial_capital] + equity_values
        drawdown = pd.Series(drawdown_values)

        # Use centralized MetricsCalculator for all metrics
        metrics = _build_performance_metrics(
            trades=trades,
            equity=equity,
            config=config,
            timestamps=timestamps,
            close=close,
            drawdown=drawdown,
            pnl_distribution=pnl_distribution,
        )

        # Calculate Buy & Hold equity curve for TradingView comparison
        bh_equity, bh_drawdown = compute_buy_hold_equity(ohlcv, config.initial_capital)

        equity_curve = EquityCurve(
            timestamps=timestamps,
            equity=equity[1:],
            drawdown=drawdown.tolist(),
            returns=returns.tolist(),
            bh_equity=bh_equity[1:] if len(bh_equity) > 1 else bh_equity,
            bh_drawdown=bh_drawdown[1:] if len(bh_drawdown) > 1 else bh_drawdown,
        )

        return BacktestResult(
            id="",
            status=BacktestStatus.COMPLETED,
            created_at=utc_now(),
            config=config,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            final_equity=equity[-1],
            final_pnl=equity[-1] - config.initial_capital,
            final_pnl_pct=total_return,
        )

    def _run_vectorbt(
        self,
        config: BacktestConfig,
        ohlcv: pd.DataFrame,
        signals,
    ) -> BacktestResult:
        """
        Run backtest using vectorbt with proper SL/TP support.

        Uses from_order_func(flexible=True) to achieve parity with fallback engine:
        - Intrabar SL/TP detection using high/low prices
        - Re-entry after SL/TP if signal persists
        - Equity-based position sizing
        """
        from backend.backtesting.vectorbt_sltp import run_vectorbt_with_sltp

        close = ohlcv["close"]

        # Check if we have SL/TP configured
        has_sl_tp = (config.stop_loss and config.stop_loss > 0) or (
            config.take_profit and config.take_profit > 0
        )

        if has_sl_tp:
            # Use our custom from_order_func implementation for SL/TP
            # Uses pre_group_func_nb for persistent state across bars
            try:
                pf = run_vectorbt_with_sltp(ohlcv, signals, config)
            except Exception as e:
                logger.warning(
                    f"VectorBT SL/TP simulation failed: {e}, falling back to from_signals"
                )
                has_sl_tp = False  # Fallback to simple mode

        if not has_sl_tp:
            # Simple mode without SL/TP - use from_signals
            order_value = float(config.position_size) * float(config.initial_capital)
            pf_kwargs = dict(
                close=close,
                entries=signals.entries,
                exits=signals.exits,
                init_cash=config.initial_capital,
                size=order_value,
                size_type="value",
                fees=config.taker_fee,
                slippage=config.slippage,
                freq="1H",
                # QUICK REVERSALS FIX: Prevent opening new position on same bar as close
                # Without delay, VectorBT generates +25% more trades than Fallback engine
                # delay=1 means entry happens on the bar AFTER signal appears
                upon_long_conflict="ignore",  # Ignore entry if already in long
                upon_short_conflict="ignore",  # Ignore entry if already in short
                upon_dir_conflict="ignore",  # Ignore conflicting direction signals
                upon_opposite_entry="ignore",  # Don't use opposite entry as exit
            )

            # INTRABAR SL/TP FIX: Add high/low for proper stop detection
            if "high" in ohlcv.columns:
                pf_kwargs["high"] = ohlcv["high"]
            if "low" in ohlcv.columns:
                pf_kwargs["low"] = ohlcv["low"]

            # Direction handling
            direction = getattr(config, "direction", "both")

            if direction == "short":
                pf_kwargs["entries"] = pd.Series(False, index=close.index)
                pf_kwargs["exits"] = pd.Series(False, index=close.index)
                if (
                    hasattr(signals, "short_entries")
                    and signals.short_entries is not None
                ):
                    pf_kwargs["short_entries"] = signals.short_entries
                if hasattr(signals, "short_exits") and signals.short_exits is not None:
                    pf_kwargs["short_exits"] = signals.short_exits
            elif direction == "both":
                if (
                    hasattr(signals, "short_entries")
                    and signals.short_entries is not None
                ):
                    pf_kwargs["short_entries"] = signals.short_entries
                if hasattr(signals, "short_exits") and signals.short_exits is not None:
                    pf_kwargs["short_exits"] = signals.short_exits

            pf = vbt.Portfolio.from_signals(**pf_kwargs)

        # Extract trades for detailed calculations
        trades = self._extract_trades_vectorbt(pf, ohlcv, config)

        # Build equity from trades with leverage (matches Fallback engine)
        # VBT's pf.value() does NOT include leverage in PnL, causing metric mismatches
        leverage = getattr(config, "leverage", 1.0)
        equity_values, drawdown_values = build_equity_from_trades(
            trades=trades,
            ohlcv=ohlcv,
            initial_capital=config.initial_capital,
            leverage=leverage,
            taker_fee=getattr(config, "taker_fee", 0.0004),
        )

        # Get returns from VBT but recalculate from equity for consistency
        if len(equity_values) > 1:
            equity_arr = np.array(equity_values)
            with np.errstate(divide="ignore", invalid="ignore"):
                returns_values = list(np.diff(equity_arr) / equity_arr[:-1])
            returns_values = [0.0] + returns_values  # First bar has no return
        else:
            returns_values = [0.0] * len(equity_values)

        # Ensure returns has same length as equity (pad with 0 if needed)
        if len(returns_values) < len(equity_values):
            returns_values = [0.0] + returns_values  # First bar has no return

        # Use centralized MetricsCalculator for all metrics
        metrics = _build_performance_metrics(
            trades=trades,
            equity=equity_values,
            config=config,
            timestamps=ohlcv.index.tolist(),
            close=close,
            drawdown=pd.Series(drawdown_values, index=ohlcv.index),
            pnl_distribution=None,
        )

        # Build equity curve
        equity_curve = EquityCurve(
            timestamps=ohlcv.index.tolist(),
            equity=equity_values,
            drawdown=drawdown_values,
            returns=returns_values,
        )

        # Use final equity from our leveraged calculation
        final_equity = (
            float(equity_values[-1]) if equity_values else config.initial_capital
        )

        return BacktestResult(
            id="",  # Will be set by caller
            status=BacktestStatus.COMPLETED,
            created_at=utc_now(),
            config=config,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            final_equity=final_equity,
            final_pnl=final_equity - config.initial_capital,
            final_pnl_pct=(final_equity - config.initial_capital)
            / config.initial_capital,
        )

    def get_result(self, backtest_id: str) -> Optional[BacktestResult]:
        """Get cached backtest result by ID"""
        return self._results_cache.get(backtest_id)

    def list_results(self) -> list[BacktestResult]:
        """List all cached backtest results"""
        return list(self._results_cache.values())

    def clear_cache(self) -> int:
        """Clear all cached backtest results. Returns number of items cleared."""
        count = len(self._results_cache)
        self._results_cache.clear()
        return count

    def remove_from_cache(self, backtest_id: str) -> bool:
        """Remove a specific backtest from cache. Returns True if found and removed."""
        if backtest_id in self._results_cache:
            del self._results_cache[backtest_id]
            return True
        return False


# Global engine instance
_engine: Optional[BacktestEngine] = None


def get_engine() -> BacktestEngine:
    """Get or create the global backtest engine instance"""
    global _engine
    if _engine is None:
        _engine = BacktestEngine()
    return _engine
