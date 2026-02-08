"""
Metrics Integration и Portfolio Mode для Universal Math Engine.

Включает:
1. 166 Metrics Integration - полный калькулятор метрик
2. Portfolio Mode - мультисимвольный режим
3. Correlation Manager - управление корреляциями

Автор: AI Agent
Версия: 1.0.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

try:
    from numba import njit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    prange = range

    def njit(*args, **kwargs):
        def decorator(func):
            return func

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


# =============================================================================
# ENUMS
# =============================================================================


class PortfolioMode(Enum):
    """Режимы портфеля."""

    INDEPENDENT = "independent"  # Независимые сигналы
    CORRELATION_FILTER = "correlation_filter"  # Фильтр по корреляции
    EQUAL_WEIGHT = "equal_weight"  # Равный вес
    RISK_PARITY = "risk_parity"  # Risk parity
    MIN_VARIANCE = "min_variance"  # Minimum variance
    MAX_SHARPE = "max_sharpe"  # Maximum Sharpe


class AllocationMethod(Enum):
    """Методы распределения капитала."""

    FIXED = "fixed"  # Фиксированное распределение
    DYNAMIC = "dynamic"  # Динамическое на основе волатильности
    SIGNAL_BASED = "signal_based"  # На основе силы сигнала


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class PortfolioConfig:
    """Конфигурация Portfolio Mode."""

    enabled: bool = False
    mode: PortfolioMode = PortfolioMode.EQUAL_WEIGHT
    allocation_method: AllocationMethod = AllocationMethod.FIXED

    # Symbols
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])

    # Weights (для FIXED allocation)
    weights: dict[str, float] = field(default_factory=dict)

    # Correlation settings
    max_correlation: float = 0.7  # Максимальная допустимая корреляция
    correlation_lookback: int = 50  # Период для расчёта корреляции

    # Risk limits
    max_total_exposure: float = 1.0  # Максимальная экспозиция
    max_single_asset_weight: float = 0.4  # Макс. вес одного актива
    min_single_asset_weight: float = 0.05  # Мин. вес одного актива

    # Rebalancing
    rebalance_threshold: float = 0.1  # Порог для ребалансировки
    rebalance_frequency: int = (
        0  # Баров между ребалансировками (0 = без частотного ограничения)
    )


@dataclass
class MetricsConfig:
    """Конфигурация расчёта метрик."""

    # Основные метрики
    calculate_basic: bool = True

    # Drawdown метрики
    calculate_drawdown: bool = True

    # Risk метрики
    calculate_risk: bool = True
    risk_free_rate: float = 0.02  # Годовая безрисковая ставка

    # Trade метрики
    calculate_trade_stats: bool = True

    # Advanced метрики
    calculate_advanced: bool = True

    # Time-based метрики
    calculate_time_based: bool = True

    # Streak метрики
    calculate_streaks: bool = True

    # All 166 metrics
    calculate_all: bool = True


@dataclass
class PortfolioPosition:
    """Позиция в портфеле."""

    symbol: str
    direction: int  # 1=long, -1=short, 0=flat
    size: float
    entry_price: float
    entry_time: int
    weight: float
    unrealized_pnl: float = 0.0


@dataclass
class PortfolioState:
    """Состояние портфеля."""

    positions: dict[str, PortfolioPosition]
    cash: float
    total_equity: float
    weights: dict[str, float]
    correlations: dict[tuple[str, str], float]
    last_rebalance_bar: int = 0


# =============================================================================
# METRICS CALCULATOR INTEGRATION
# =============================================================================


class MetricsCalculator:
    """
    Расчёт всех 166 метрик.

    Интегрируется с backend/core/metrics_calculator.py.
    """

    def __init__(self, config: MetricsConfig | None = None):
        self.config = config or MetricsConfig()
        self._metrics_module = None

    def _load_metrics_module(self):
        """Lazy load основного модуля метрик."""
        if self._metrics_module is None:
            try:
                from backend.core.metrics_calculator import (
                    MetricsCalculator as BaseMetrics,
                )

                self._metrics_module = BaseMetrics
            except ImportError:
                self._metrics_module = None
        return self._metrics_module

    def calculate_basic_metrics(
        self,
        equity_curve: np.ndarray,
        trades: list[dict[str, Any]],
        initial_capital: float,
    ) -> dict[str, float]:
        """Рассчитать базовые метрики."""
        if len(equity_curve) == 0:
            return {}

        final_equity = equity_curve[-1]
        total_return = (final_equity - initial_capital) / initial_capital

        # Returns
        returns = np.diff(equity_curve) / equity_curve[:-1]

        # Win/Loss
        n_trades = len(trades)
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) <= 0]

        win_rate = len(wins) / n_trades if n_trades > 0 else 0

        gross_profit = sum(t.get("pnl", 0) for t in wins)
        gross_loss = abs(sum(t.get("pnl", 0) for t in losses))

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Average
        avg_win = gross_profit / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0

        return {
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "final_equity": final_equity,
            "net_profit": final_equity - initial_capital,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "total_trades": n_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "win_rate_pct": win_rate * 100,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_trade": (gross_profit - gross_loss) / n_trades if n_trades > 0 else 0,
        }

    def calculate_drawdown_metrics(
        self,
        equity_curve: np.ndarray,
    ) -> dict[str, float]:
        """Рассчитать метрики просадки."""
        if len(equity_curve) < 2:
            return {}

        # Running maximum
        peak = np.maximum.accumulate(equity_curve)

        # Drawdown
        drawdown = (peak - equity_curve) / peak
        drawdown_abs = peak - equity_curve

        # Max drawdown
        max_dd = np.max(drawdown)
        max_dd_abs = np.max(drawdown_abs)

        # Find max drawdown period
        max_dd_end = np.argmax(drawdown)
        max_dd_start = (
            np.argmax(equity_curve[: max_dd_end + 1]) if max_dd_end > 0 else 0
        )
        max_dd_duration = max_dd_end - max_dd_start

        # Average drawdown
        avg_dd = np.mean(drawdown[drawdown > 0]) if np.any(drawdown > 0) else 0

        # Recovery
        recovery_bars = 0
        if max_dd_end < len(equity_curve) - 1:
            for i in range(max_dd_end + 1, len(equity_curve)):
                if equity_curve[i] >= peak[max_dd_end]:
                    recovery_bars = i - max_dd_end
                    break

        return {
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd * 100,
            "max_drawdown_abs": max_dd_abs,
            "avg_drawdown": avg_dd,
            "avg_drawdown_pct": avg_dd * 100,
            "max_drawdown_duration": max_dd_duration,
            "recovery_time": recovery_bars,
            "drawdown_start_bar": max_dd_start,
            "drawdown_end_bar": max_dd_end,
        }

    def calculate_risk_metrics(
        self,
        equity_curve: np.ndarray,
        trades: list[dict[str, Any]],
        initial_capital: float,
    ) -> dict[str, float]:
        """Рассчитать риск-метрики."""
        if len(equity_curve) < 2:
            return {}

        # Returns
        returns = np.diff(equity_curve) / equity_curve[:-1]

        # Annualized return (assuming daily)
        n_periods = len(returns)
        periods_per_year = 365  # Can be adjusted

        total_return = (equity_curve[-1] - initial_capital) / initial_capital
        annualized_return = (1 + total_return) ** (
            periods_per_year / max(n_periods, 1)
        ) - 1

        # Volatility
        volatility = (
            np.std(returns) * np.sqrt(periods_per_year) if len(returns) > 1 else 0
        )

        # Sharpe Ratio
        risk_free_rate = self.config.risk_free_rate
        excess_return = annualized_return - risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0

        # Sortino Ratio
        downside_returns = returns[returns < 0]
        downside_std = (
            np.std(downside_returns) * np.sqrt(periods_per_year)
            if len(downside_returns) > 0
            else 0
        )
        sortino_ratio = excess_return / downside_std if downside_std > 0 else 0

        # Max Drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak
        max_dd = np.max(drawdown)

        # Calmar Ratio
        calmar_ratio = annualized_return / max_dd if max_dd > 0 else 0

        # VaR
        var_95 = np.percentile(returns, 5) if len(returns) > 0 else 0
        var_99 = np.percentile(returns, 1) if len(returns) > 0 else 0

        # CVaR (Expected Shortfall)
        cvar_95 = (
            np.mean(returns[returns <= var_95])
            if len(returns[returns <= var_95]) > 0
            else 0
        )

        return {
            "annualized_return": annualized_return,
            "annualized_return_pct": annualized_return * 100,
            "volatility": volatility,
            "volatility_pct": volatility * 100,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "var_95": var_95,
            "var_99": var_99,
            "cvar_95": cvar_95,
            "downside_deviation": downside_std,
        }

    def calculate_trade_stats(
        self,
        trades: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Рассчитать статистику сделок."""
        if not trades:
            return {}

        pnls = [t.get("pnl", 0) for t in trades]
        durations = [t.get("duration_bars", 0) for t in trades]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        # Expectancy
        win_rate = len(wins) / len(pnls)
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0

        expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

        # Risk/Reward
        risk_reward = avg_win / avg_loss if avg_loss > 0 else float("inf")

        # Kelly Criterion
        if avg_loss > 0:
            kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss)
        else:
            kelly = win_rate
        kelly = max(0, min(1, kelly))

        # Largest trades
        max_win = max(pnls) if pnls else 0
        max_loss = min(pnls) if pnls else 0

        # Duration
        avg_duration = np.mean(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        min_duration = min(durations) if durations else 0

        # Long vs Short
        longs = [t for t in trades if t.get("direction", 0) == 1]
        shorts = [t for t in trades if t.get("direction", 0) == -1]

        long_pnl = sum(t.get("pnl", 0) for t in longs)
        short_pnl = sum(t.get("pnl", 0) for t in shorts)

        long_win_rate = (
            len([t for t in longs if t.get("pnl", 0) > 0]) / len(longs) if longs else 0
        )
        short_win_rate = (
            len([t for t in shorts if t.get("pnl", 0) > 0]) / len(shorts)
            if shorts
            else 0
        )

        return {
            "expectancy": expectancy,
            "risk_reward_ratio": risk_reward,
            "kelly_criterion": kelly,
            "kelly_pct": kelly * 100,
            "largest_win": max_win,
            "largest_loss": max_loss,
            "avg_trade_duration": avg_duration,
            "max_trade_duration": max_duration,
            "min_trade_duration": min_duration,
            "total_long_trades": len(longs),
            "total_short_trades": len(shorts),
            "long_pnl": long_pnl,
            "short_pnl": short_pnl,
            "long_win_rate": long_win_rate,
            "short_win_rate": short_win_rate,
        }

    def calculate_streak_metrics(
        self,
        trades: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Рассчитать метрики серий."""
        if not trades:
            return {}

        pnls = [t.get("pnl", 0) for t in trades]

        # Current streak
        current_streak = 0
        streak_type = None  # "win" or "loss"

        for pnl in reversed(pnls):
            if pnl > 0:
                if streak_type is None or streak_type == "win":
                    current_streak += 1
                    streak_type = "win"
                else:
                    break
            else:
                if streak_type is None or streak_type == "loss":
                    current_streak += 1
                    streak_type = "loss"
                else:
                    break

        # Max streaks
        max_win_streak = 0
        max_loss_streak = 0
        current_win = 0
        current_loss = 0

        for pnl in pnls:
            if pnl > 0:
                current_win += 1
                current_loss = 0
                max_win_streak = max(max_win_streak, current_win)
            else:
                current_loss += 1
                current_win = 0
                max_loss_streak = max(max_loss_streak, current_loss)

        return {
            "current_streak": current_streak
            if streak_type == "win"
            else -current_streak,
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
        }

    def calculate_all_metrics(
        self,
        equity_curve: np.ndarray,
        trades: list[dict[str, Any]],
        initial_capital: float,
    ) -> dict[str, Any]:
        """Рассчитать все доступные метрики."""
        metrics = {}

        # Try to use base metrics calculator
        BaseMetrics = self._load_metrics_module()
        if BaseMetrics is not None:
            try:
                calc = BaseMetrics()
                full_metrics = calc.calculate_all(
                    equity_curve=equity_curve,
                    trades=trades,
                    initial_capital=initial_capital,
                )
                return full_metrics
            except Exception:
                pass  # Fall back to local calculations

        # Local calculations
        if self.config.calculate_basic:
            metrics.update(
                self.calculate_basic_metrics(equity_curve, trades, initial_capital)
            )

        if self.config.calculate_drawdown:
            metrics.update(self.calculate_drawdown_metrics(equity_curve))

        if self.config.calculate_risk:
            metrics.update(
                self.calculate_risk_metrics(equity_curve, trades, initial_capital)
            )

        if self.config.calculate_trade_stats:
            metrics.update(self.calculate_trade_stats(trades))

        if self.config.calculate_streaks:
            metrics.update(self.calculate_streak_metrics(trades))

        return metrics


# =============================================================================
# CORRELATION MANAGER
# =============================================================================


@njit(cache=True)
def calculate_correlation_matrix(
    returns: np.ndarray,  # Shape: (n_assets, n_periods)
) -> np.ndarray:
    """Calculate correlation matrix using Pearson correlation."""
    n_assets = returns.shape[0]
    corr_matrix = np.zeros((n_assets, n_assets), dtype=np.float64)

    for i in range(n_assets):
        for j in range(n_assets):
            if i == j:
                corr_matrix[i, j] = 1.0
            elif j > i:
                # Calculate correlation
                r1 = returns[i]
                r2 = returns[j]

                mean1 = np.mean(r1)
                mean2 = np.mean(r2)

                std1 = np.std(r1)
                std2 = np.std(r2)

                if std1 > 0 and std2 > 0:
                    cov = np.mean((r1 - mean1) * (r2 - mean2))
                    corr = cov / (std1 * std2)
                else:
                    corr = 0.0

                corr_matrix[i, j] = corr
                corr_matrix[j, i] = corr

    return corr_matrix


class CorrelationManager:
    """
    Управление корреляциями между активами.
    """

    def __init__(
        self,
        max_correlation: float = 0.7,
        lookback: int = 50,
    ):
        self.max_correlation = max_correlation
        self.lookback = lookback

        self.symbols: list[str] = []
        self.returns_history: dict[str, list[float]] = {}
        self.correlation_matrix: np.ndarray | None = None

    def add_return(self, symbol: str, return_value: float) -> None:
        """Добавить значение доходности."""
        if symbol not in self.returns_history:
            self.returns_history[symbol] = []

        self.returns_history[symbol].append(return_value)

        # Trim to lookback
        if len(self.returns_history[symbol]) > self.lookback:
            self.returns_history[symbol] = self.returns_history[symbol][
                -self.lookback :
            ]

        if symbol not in self.symbols:
            self.symbols.append(symbol)

    def update_correlations(self) -> None:
        """Обновить матрицу корреляций."""
        if len(self.symbols) < 2:
            return

        # Check all have enough data
        min_len = min(len(self.returns_history[s]) for s in self.symbols)
        if min_len < 10:
            return

        # Build returns array
        n_assets = len(self.symbols)
        returns = np.zeros((n_assets, min_len), dtype=np.float64)

        for i, symbol in enumerate(self.symbols):
            returns[i] = np.array(self.returns_history[symbol][-min_len:])

        self.correlation_matrix = calculate_correlation_matrix(returns)

    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Получить корреляцию между двумя символами."""
        if self.correlation_matrix is None:
            return 0.0

        if symbol1 not in self.symbols or symbol2 not in self.symbols:
            return 0.0

        i = self.symbols.index(symbol1)
        j = self.symbols.index(symbol2)

        return float(self.correlation_matrix[i, j])

    def can_trade(
        self,
        new_symbol: str,
        existing_positions: list[str],
    ) -> bool:
        """Проверить можно ли торговать символ с учётом корреляций."""
        if self.correlation_matrix is None:
            return True

        if new_symbol not in self.symbols:
            return True

        for pos_symbol in existing_positions:
            corr = abs(self.get_correlation(new_symbol, pos_symbol))
            if corr > self.max_correlation:
                return False

        return True

    def get_diversification_score(
        self,
        symbols: list[str],
        weights: list[float],
    ) -> float:
        """Рассчитать скор диверсификации портфеля."""
        if self.correlation_matrix is None or len(symbols) < 2:
            return 1.0

        # Portfolio variance
        n = len(symbols)
        weights_arr = np.array(weights)

        # Get sub-matrix
        indices = [self.symbols.index(s) for s in symbols if s in self.symbols]
        sub_corr = self.correlation_matrix[np.ix_(indices, indices)]

        # Portfolio correlation (simplified)
        weighted_corr = 0.0
        for i in range(n):
            for j in range(n):
                if i != j:
                    weighted_corr += weights_arr[i] * weights_arr[j] * sub_corr[i, j]

        # Diversification score: 1 - avg correlation
        avg_corr = weighted_corr / (n * (n - 1)) if n > 1 else 0

        return 1 - abs(avg_corr)


# =============================================================================
# PORTFOLIO MANAGER
# =============================================================================


class PortfolioManager:
    """
    Portfolio Mode Manager.

    Управляет мультисимвольным портфелем.
    """

    def __init__(self, config: PortfolioConfig | None = None):
        self.config = config or PortfolioConfig()

        self.state = PortfolioState(
            positions={},
            cash=0.0,
            total_equity=0.0,
            weights={},
            correlations={},
        )

        self.correlation_manager = CorrelationManager(
            max_correlation=self.config.max_correlation,
            lookback=self.config.correlation_lookback,
        )

        self.trade_history: list[dict[str, Any]] = []

    def initialize(self, initial_capital: float) -> None:
        """Инициализировать портфель."""
        self.state.cash = initial_capital
        self.state.total_equity = initial_capital

        # Initialize weights
        n_symbols = len(self.config.symbols)
        if self.config.weights:
            self.state.weights = self.config.weights.copy()
        else:
            equal_weight = 1.0 / n_symbols if n_symbols > 0 else 0
            self.state.weights = dict.fromkeys(self.config.symbols, equal_weight)

    def calculate_weights(
        self,
        returns_data: dict[str, np.ndarray],
    ) -> dict[str, float]:
        """Рассчитать веса портфеля."""
        mode = self.config.mode
        symbols = self.config.symbols
        n = len(symbols)

        if n == 0:
            return {}

        if mode == PortfolioMode.EQUAL_WEIGHT:
            return dict.fromkeys(symbols, 1.0 / n)

        if mode == PortfolioMode.RISK_PARITY:
            # Inverse volatility weighting
            volatilities = {}
            for symbol in symbols:
                if symbol in returns_data and len(returns_data[symbol]) > 1:
                    volatilities[symbol] = np.std(returns_data[symbol])
                else:
                    volatilities[symbol] = 1.0

            inv_vols = {s: 1.0 / v if v > 0 else 0 for s, v in volatilities.items()}
            total_inv_vol = sum(inv_vols.values())

            if total_inv_vol > 0:
                return {s: v / total_inv_vol for s, v in inv_vols.items()}
            else:
                return dict.fromkeys(symbols, 1.0 / n)

        if mode == PortfolioMode.MIN_VARIANCE:
            # Simplified: use inverse variance
            variances = {}
            for symbol in symbols:
                if symbol in returns_data and len(returns_data[symbol]) > 1:
                    variances[symbol] = np.var(returns_data[symbol])
                else:
                    variances[symbol] = 1.0

            inv_vars = {s: 1.0 / v if v > 0 else 0 for s, v in variances.items()}
            total_inv_var = sum(inv_vars.values())

            if total_inv_var > 0:
                return {s: v / total_inv_var for s, v in inv_vars.items()}
            else:
                return dict.fromkeys(symbols, 1.0 / n)

        # Default: equal weight
        return dict.fromkeys(symbols, 1.0 / n)

    def can_open_position(
        self,
        symbol: str,
        size: float,
        price: float,
    ) -> bool:
        """Проверить можно ли открыть позицию."""
        # Check if symbol is in portfolio
        if symbol not in self.config.symbols:
            return False

        # Check total exposure
        current_exposure = sum(
            pos.size * pos.entry_price for pos in self.state.positions.values()
        )
        new_exposure = current_exposure + size * price

        # Check if we have enough equity for exposure
        max_exposure = self.state.total_equity * self.config.max_total_exposure
        if self.state.total_equity > 0 and new_exposure > max_exposure:
            return False

        # Check maximum weight for new position
        if self.state.total_equity > 0:
            new_position_weight = (size * price) / self.state.total_equity
            if new_position_weight > self.config.max_single_asset_weight:
                return False

        # Check correlation
        if self.config.mode == PortfolioMode.CORRELATION_FILTER:
            existing_symbols = list(self.state.positions.keys())
            if not self.correlation_manager.can_trade(symbol, existing_symbols):
                return False

        return True

    def open_position(
        self,
        symbol: str,
        direction: int,
        size: float,
        price: float,
        timestamp: int,
    ) -> bool:
        """Открыть позицию."""
        if not self.can_open_position(symbol, size, price):
            return False

        # Check if position already exists
        if symbol in self.state.positions:
            # Add to existing position
            existing = self.state.positions[symbol]
            new_size = existing.size + size
            new_entry = (existing.entry_price * existing.size + price * size) / new_size
            existing.size = new_size
            existing.entry_price = new_entry
        else:
            # New position
            weight = self.state.weights.get(symbol, 0)
            self.state.positions[symbol] = PortfolioPosition(
                symbol=symbol,
                direction=direction,
                size=size,
                entry_price=price,
                entry_time=timestamp,
                weight=weight,
            )

        # Update cash
        self.state.cash -= size * price

        return True

    def close_position(
        self,
        symbol: str,
        price: float,
        timestamp: int,
    ) -> dict[str, Any] | None:
        """Закрыть позицию."""
        if symbol not in self.state.positions:
            return None

        position = self.state.positions[symbol]

        # Calculate PnL
        if position.direction == 1:  # Long
            pnl = (price - position.entry_price) * position.size
        else:  # Short
            pnl = (position.entry_price - price) * position.size

        # Trade record
        trade = {
            "symbol": symbol,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": price,
            "size": position.size,
            "entry_time": position.entry_time,
            "exit_time": timestamp,
            "pnl": pnl,
        }

        self.trade_history.append(trade)

        # Update state
        self.state.cash += position.size * price + pnl
        del self.state.positions[symbol]

        return trade

    def update_equity(self, prices: dict[str, float]) -> None:
        """Обновить equity портфеля."""
        position_value = 0.0

        for symbol, position in self.state.positions.items():
            if symbol in prices:
                current_price = prices[symbol]
                position_value += position.size * current_price

                # Update unrealized PnL
                if position.direction == 1:
                    position.unrealized_pnl = (
                        current_price - position.entry_price
                    ) * position.size
                else:
                    position.unrealized_pnl = (
                        position.entry_price - current_price
                    ) * position.size

        self.state.total_equity = self.state.cash + position_value

    def should_rebalance(
        self,
        current_bar: int,
        prices: dict[str, float],
    ) -> bool:
        """Проверить нужна ли ребалансировка."""
        # Check frequency
        if self.config.rebalance_frequency > 0:
            bars_since_rebalance = current_bar - self.state.last_rebalance_bar
            if bars_since_rebalance < self.config.rebalance_frequency:
                return False

        # Check threshold
        for symbol, target_weight in self.state.weights.items():
            if symbol in self.state.positions and symbol in prices:
                position = self.state.positions[symbol]
                current_value = position.size * prices[symbol]
                current_weight = (
                    current_value / self.state.total_equity
                    if self.state.total_equity > 0
                    else 0
                )

                if (
                    abs(current_weight - target_weight)
                    > self.config.rebalance_threshold
                ):
                    return True

        return False

    def get_rebalance_orders(
        self,
        prices: dict[str, float],
        current_bar: int,
    ) -> list[dict[str, Any]]:
        """Получить ордера для ребалансировки."""
        orders = []

        self.state.last_rebalance_bar = current_bar

        for symbol in self.config.symbols:
            if symbol not in prices:
                continue

            price = prices[symbol]
            target_weight = self.state.weights.get(symbol, 0)
            target_value = self.state.total_equity * target_weight
            target_size = target_value / price if price > 0 else 0

            current_size = 0.0
            if symbol in self.state.positions:
                current_size = self.state.positions[symbol].size

            size_diff = target_size - current_size

            if abs(size_diff) > 0.0001:
                orders.append(
                    {
                        "symbol": symbol,
                        "action": "buy" if size_diff > 0 else "sell",
                        "size": abs(size_diff),
                        "price": price,
                    }
                )

        return orders

    def get_portfolio_metrics(self) -> dict[str, Any]:
        """Получить метрики портфеля."""
        return {
            "total_equity": self.state.total_equity,
            "cash": self.state.cash,
            "n_positions": len(self.state.positions),
            "symbols_in_position": list(self.state.positions.keys()),
            "total_trades": len(self.trade_history),
            "weights": self.state.weights.copy(),
        }
