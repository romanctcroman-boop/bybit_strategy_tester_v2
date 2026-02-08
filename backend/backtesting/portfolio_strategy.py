"""
Strategy Portfolio Backtester

Runs FallbackEngineV4 backtests across multiple assets and aggregates results
into a portfolio view with shared capital allocation.

Usage:
    from backend.backtesting.portfolio_strategy import StrategyPortfolioBacktester

    backtester = StrategyPortfolioBacktester(
        symbols=['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
        initial_capital=10000.0,
    )

    result = backtester.run(
        data={'BTCUSDT': btc_candles, 'ETHUSDT': eth_candles, ...},
        strategy_config=BacktestInput(...),
        allocation=AssetAllocation(method=AllocationMethod.EQUAL_WEIGHT),
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, BacktestOutput
from backend.services.advanced_backtesting.portfolio import (
    AllocationMethod,
    AssetAllocation,
    CorrelationAnalysis,
    PortfolioMetrics,
)

logger = logging.getLogger(__name__)


@dataclass
class StrategyPortfolioResult:
    """Result of strategy portfolio backtest."""

    status: str = "completed"

    # Per-asset results
    per_asset: dict[str, BacktestOutput] = field(default_factory=dict)

    # Aggregated portfolio metrics
    portfolio_metrics: PortfolioMetrics = field(default_factory=PortfolioMetrics)

    # Portfolio equity curve (combined)
    portfolio_equity_curve: list[float] = field(default_factory=list)

    # All trades across assets (sorted by time)
    all_trades: list[dict] = field(default_factory=list)

    # Correlation analysis
    correlation: CorrelationAnalysis = field(default_factory=CorrelationAnalysis)

    # Configuration used
    config: dict[str, Any] = field(default_factory=dict)

    # Duration
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "status": self.status,
            "per_asset": {
                symbol: {
                    "total_trades": len(result.trades),
                    "net_profit": result.metrics.net_profit,
                    "total_return": result.metrics.total_return,
                    "max_drawdown": result.metrics.max_drawdown,
                    "win_rate": result.metrics.win_rate,
                    "profit_factor": result.metrics.profit_factor,
                    "sharpe_ratio": result.metrics.sharpe_ratio,
                }
                for symbol, result in self.per_asset.items()
            },
            "portfolio_metrics": self.portfolio_metrics.to_dict(),
            "portfolio_equity_curve": self.portfolio_equity_curve[-1000:],  # Last 1000
            "all_trades": self.all_trades[-500:],  # Last 500
            "correlation": self.correlation.to_dict(),
            "config": self.config,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class StrategyPortfolioBacktester:
    """
    Multi-asset strategy backtester.

    Runs FallbackEngineV4 for each asset with allocated capital,
    then aggregates results into portfolio-level metrics.
    """

    def __init__(
        self,
        symbols: list[str],
        initial_capital: float = 10000.0,
        commission: float = 0.0007,  # 0.07% default
    ):
        """
        Initialize strategy portfolio backtester.

        Args:
            symbols: List of trading symbols
            initial_capital: Total portfolio capital
            commission: Trading commission rate
        """
        self.symbols = symbols
        self.initial_capital = initial_capital
        self.commission = commission

        # Engine instance
        self.engine = FallbackEngineV4()

        # Results storage
        self.per_asset_results: dict[str, BacktestOutput] = {}
        self.all_trades: list[dict] = []

    def run(
        self,
        data: dict[str, pd.DataFrame],
        strategy_config: BacktestInput,
        allocation: AssetAllocation | None = None,
    ) -> StrategyPortfolioResult:
        """
        Run strategy backtest for all assets.

        Args:
            data: Dictionary mapping symbols to candle DataFrames
            strategy_config: Template configuration (symbol and candles will be overridden)
            allocation: Capital allocation (default: equal weight)

        Returns:
            StrategyPortfolioResult with aggregated results
        """
        start_time = datetime.now()
        result = StrategyPortfolioResult()

        # Validate data
        missing = [s for s in self.symbols if s not in data]
        if missing:
            result.status = "error"
            result.config["error"] = f"Missing data for: {missing}"
            return result

        # Default allocation: equal weight
        if allocation is None:
            allocation = AssetAllocation(method=AllocationMethod.EQUAL_WEIGHT)
            weight = 1.0 / len(self.symbols)
            allocation.weights = dict.fromkeys(self.symbols, weight)

        # Ensure allocation has weights for all symbols
        if not allocation.weights:
            if allocation.method == AllocationMethod.EQUAL_WEIGHT:
                weight = 1.0 / len(self.symbols)
                allocation.weights = dict.fromkeys(self.symbols, weight)
            else:
                allocation.weights = self._calculate_allocation(data, allocation.method)

        allocation.normalize()

        # Run backtest for each asset
        for symbol in self.symbols:
            candles = data[symbol]
            symbol_capital = self.initial_capital * allocation.weights.get(symbol, 0)

            if symbol_capital <= 0:
                logger.warning(f"No capital allocated to {symbol}, skipping")
                continue

            # Create symbol-specific config
            symbol_config = self._create_symbol_config(
                symbol, candles, symbol_capital, strategy_config
            )

            # Run backtest
            try:
                asset_result = self.engine.run(symbol_config)
                self.per_asset_results[symbol] = asset_result

                # Collect trades with symbol tag
                for trade in asset_result.trades:
                    self.all_trades.append(
                        {
                            "symbol": symbol,
                            "entry_time": str(trade.entry_time),
                            "exit_time": str(trade.exit_time),
                            "side": trade.side,
                            "entry_price": trade.entry_price,
                            "exit_price": trade.exit_price,
                            "size": trade.size,
                            "pnl": trade.pnl,
                            "pnl_pct": trade.pnl_pct,
                            "commission": trade.commission,
                            "exit_reason": trade.exit_reason,
                        }
                    )

            except Exception as e:
                logger.error(f"Backtest failed for {symbol}: {e}")
                continue

        # Sort trades by time
        self.all_trades.sort(key=lambda t: t.get("entry_time", ""))

        # Aggregate results
        result.per_asset = self.per_asset_results
        result.all_trades = self.all_trades
        result.portfolio_equity_curve = self._aggregate_equity_curves(allocation)
        result.portfolio_metrics = self._calculate_portfolio_metrics(allocation)
        result.correlation = self._analyze_correlations(data)

        # Store config
        result.config = {
            "symbols": self.symbols,
            "initial_capital": self.initial_capital,
            "allocation_method": allocation.method.value,
            "weights": {k: round(v, 4) for k, v in allocation.weights.items()},
        }

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result

    def _create_symbol_config(
        self,
        symbol: str,
        candles: pd.DataFrame,
        capital: float,
        template: BacktestInput,
    ) -> BacktestInput:
        """Create configuration for specific symbol."""
        # Generate signals based on template strategy
        long_entries, long_exits, short_entries, short_exits = self._generate_signals(
            candles, template
        )

        # Create new config with symbol-specific values
        return BacktestInput(
            candles=candles,
            long_entries=long_entries,
            long_exits=long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol=symbol,
            interval=template.interval,
            initial_capital=capital,
            position_size=template.position_size,
            leverage=template.leverage,
            stop_loss=template.stop_loss,
            take_profit=template.take_profit,
            direction=template.direction,
            taker_fee=self.commission,
            maker_fee=self.commission,
            slippage=template.slippage,
            use_bar_magnifier=False,  # Disable for multi-asset (no 1m data)
            pyramiding=template.pyramiding,
            atr_enabled=template.atr_enabled,
            atr_period=template.atr_period,
            atr_sl_multiplier=template.atr_sl_multiplier,
            atr_tp_multiplier=template.atr_tp_multiplier,
        )

    def _generate_signals(
        self,
        candles: pd.DataFrame,
        config: BacktestInput,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate trading signals based on strategy configuration.

        This is a simplified signal generator. For production, should use
        the actual strategy classes.
        """
        n = len(candles)
        closes = candles["close"].values

        long_entries = np.zeros(n, dtype=bool)
        long_exits = np.zeros(n, dtype=bool)
        short_entries = np.zeros(n, dtype=bool)
        short_exits = np.zeros(n, dtype=bool)

        # Default: simple RSI strategy
        # TODO: Use proper strategy classes based on config
        period = 14
        overbought = 70
        oversold = 30

        # Calculate RSI
        rsi = np.full(n, 50.0)
        for i in range(period, n):
            gains = []
            losses = []
            for j in range(i - period + 1, i + 1):
                change = closes[j] - closes[j - 1]
                if change > 0:
                    gains.append(change)
                else:
                    losses.append(abs(change))
            avg_gain = np.mean(gains) if gains else 0.0001
            avg_loss = np.mean(losses) if losses else 0.0001
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))

        # Generate signals
        for i in range(period + 1, n):
            # Long entry: RSI crosses above oversold
            if rsi[i] > oversold and rsi[i - 1] <= oversold:
                long_entries[i] = True

            # Short entry: RSI crosses below overbought
            if rsi[i] < overbought and rsi[i - 1] >= overbought:
                short_entries[i] = True

            # Exits: opposite RSI zone
            if rsi[i] > overbought:
                long_exits[i] = True
            if rsi[i] < oversold:
                short_exits[i] = True

        return long_entries, long_exits, short_entries, short_exits

    def _calculate_allocation(
        self,
        data: dict[str, pd.DataFrame],
        method: AllocationMethod,
    ) -> dict[str, float]:
        """Calculate allocation weights based on method."""
        weights = {}

        if method == AllocationMethod.EQUAL_WEIGHT:
            weight = 1.0 / len(self.symbols)
            weights = dict.fromkeys(self.symbols, weight)

        elif method == AllocationMethod.RISK_PARITY:
            # Inverse volatility
            volatilities = {}
            for symbol, candles in data.items():
                returns = candles["close"].pct_change().dropna().values
                volatilities[symbol] = np.std(returns) if len(returns) > 0 else 0.02

            total_inv_vol = sum(1 / v for v in volatilities.values() if v > 0)
            weights = {
                s: (1 / v) / total_inv_vol if v > 0 else 0
                for s, v in volatilities.items()
            }

        elif method == AllocationMethod.MOMENTUM:
            # Lookback momentum
            lookback = 30
            momentum_scores = {}
            for symbol, candles in data.items():
                if len(candles) > lookback:
                    old_price = candles["close"].iloc[-lookback]
                    new_price = candles["close"].iloc[-1]
                    momentum_scores[symbol] = (new_price / old_price) - 1
                else:
                    momentum_scores[symbol] = 0

            positive = {k: max(0, v) for k, v in momentum_scores.items()}
            total = sum(positive.values())
            if total > 0:
                weights = {k: v / total for k, v in positive.items()}
            else:
                weights = {s: 1.0 / len(self.symbols) for s in self.symbols}

        else:
            # Default: equal weight
            weight = 1.0 / len(self.symbols)
            weights = dict.fromkeys(self.symbols, weight)

        return weights

    def _aggregate_equity_curves(
        self,
        allocation: AssetAllocation,
    ) -> list[float]:
        """Aggregate per-asset equity curves into portfolio equity."""
        if not self.per_asset_results:
            return [self.initial_capital]

        # Get max length
        max_len = max(len(r.equity_curve) for r in self.per_asset_results.values())

        portfolio_equity = []
        for i in range(max_len):
            total = 0.0
            for symbol, result in self.per_asset_results.items():
                if i < len(result.equity_curve):
                    total += result.equity_curve[i]
                else:
                    # Use last known value
                    total += result.equity_curve[-1] if result.equity_curve else 0

            portfolio_equity.append(total)

        return portfolio_equity

    def _calculate_portfolio_metrics(
        self,
        allocation: AssetAllocation,
    ) -> PortfolioMetrics:
        """Calculate aggregated portfolio metrics."""
        metrics = PortfolioMetrics()

        if not self.per_asset_results:
            return metrics

        equity = (
            self.portfolio_equity_curve
            if hasattr(self, "portfolio_equity_curve")
            else []
        )
        if not equity:
            equity = self._aggregate_equity_curves(allocation)

        if len(equity) < 2:
            return metrics

        # Total return
        metrics.total_return = (equity[-1] / self.initial_capital) - 1

        # Annualized return (assuming daily bars, adjust as needed)
        days = len(equity)
        if metrics.total_return > -1:
            metrics.annualized_return = (1 + metrics.total_return) ** (365 / days) - 1

        # Volatility
        returns = np.diff(equity) / equity[:-1]
        metrics.volatility = np.std(returns) * np.sqrt(365)

        # Max drawdown
        equity_arr = np.array(equity)
        running_max = np.maximum.accumulate(equity_arr)
        drawdowns = (running_max - equity_arr) / running_max
        metrics.max_drawdown = np.max(drawdowns)

        # VaR and CVaR (95%)
        sorted_returns = np.sort(returns)
        var_idx = int(0.05 * len(sorted_returns))
        if var_idx > 0:
            metrics.var_95 = abs(sorted_returns[var_idx])
            metrics.cvar_95 = abs(np.mean(sorted_returns[:var_idx]))

        # Sharpe ratio (assuming 0% risk-free rate)
        if metrics.volatility > 0:
            metrics.sharpe_ratio = metrics.annualized_return / metrics.volatility

        # Sortino ratio
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_vol = np.std(negative_returns) * np.sqrt(365)
            if downside_vol > 0:
                metrics.sortino_ratio = metrics.annualized_return / downside_vol

        # Calmar ratio
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.annualized_return / metrics.max_drawdown

        # Asset contributions
        total_pnl = sum(r.metrics.net_profit for r in self.per_asset_results.values())
        if total_pnl != 0:
            for symbol, result in self.per_asset_results.items():
                metrics.asset_contributions[symbol] = (
                    result.metrics.net_profit / total_pnl
                )

        # Concentration (Herfindahl index)
        weights = list(allocation.weights.values())
        metrics.concentration_ratio = sum(w**2 for w in weights)

        return metrics

    def _analyze_correlations(
        self,
        data: dict[str, pd.DataFrame],
    ) -> CorrelationAnalysis:
        """Analyze asset correlations."""
        analysis = CorrelationAnalysis()

        if len(self.symbols) < 2:
            return analysis

        # Calculate returns for each asset
        asset_returns = {}
        for symbol, candles in data.items():
            returns = candles["close"].pct_change().dropna().values
            asset_returns[symbol] = returns

        # Truncate to same length
        min_len = min(len(r) for r in asset_returns.values())
        for symbol in asset_returns:
            asset_returns[symbol] = asset_returns[symbol][:min_len]

        if min_len < 2:
            return analysis

        # Calculate correlation matrix
        correlations = []
        symbols_list = list(self.symbols)

        for i, s1 in enumerate(symbols_list):
            row = {}
            for j, s2 in enumerate(symbols_list):
                if i == j:
                    corr = 1.0
                else:
                    r1 = asset_returns.get(s1, [])
                    r2 = asset_returns.get(s2, [])
                    if len(r1) > 0 and len(r2) > 0:
                        corr = float(np.corrcoef(r1, r2)[0, 1])
                    else:
                        corr = 0.0
                row[s2] = round(corr, 4)
                if i < j:
                    correlations.append(corr)
            analysis.correlation_matrix[s1] = row

        # Statistics
        if correlations:
            analysis.avg_correlation = float(np.mean(correlations))
            analysis.max_correlation = float(np.max(correlations))
            analysis.min_correlation = float(np.min(correlations))

            # Find most/least correlated pairs
            max_corr = -2
            min_corr = 2
            for i, s1 in enumerate(symbols_list):
                for j, s2 in enumerate(symbols_list):
                    if i < j:
                        c = analysis.correlation_matrix[s1][s2]
                        if c > max_corr:
                            max_corr = c
                            analysis.most_correlated_pair = (s1, s2)
                        if c < min_corr:
                            min_corr = c
                            analysis.least_correlated_pair = (s1, s2)

        return analysis


# Convenience function
def run_strategy_portfolio_backtest(
    data: dict[str, pd.DataFrame],
    strategy_config: BacktestInput,
    allocation_method: str = "equal_weight",
    initial_capital: float = 10000.0,
    commission: float = 0.0007,
) -> StrategyPortfolioResult:
    """
    Convenience function to run strategy portfolio backtest.

    Args:
        data: Asset price data
        strategy_config: Strategy configuration
        allocation_method: Allocation method name
        initial_capital: Starting capital
        commission: Trading commission

    Returns:
        StrategyPortfolioResult
    """
    symbols = list(data.keys())
    backtester = StrategyPortfolioBacktester(symbols, initial_capital, commission)

    allocation = AssetAllocation(method=AllocationMethod(allocation_method))

    return backtester.run(data, strategy_config, allocation)
