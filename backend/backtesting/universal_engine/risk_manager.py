"""
Universal Risk Manager - Управление рисками для ВСЕХ сценариев.

Функции:
- Max drawdown limit: Стоп торговли при просадке
- Max consecutive losses: Стоп после N убытков подряд
- Cooldown after loss: Пауза после убыточной сделки
- Re-entry delay: Задержка перед повторным входом
- Max trades per day/week: Лимит сделок
- Portfolio heat limit: Максимальный риск портфеля

Автор: AI Agent
Версия: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TradeResult:
    """Result of a closed trade for risk tracking."""

    pnl: float
    pnl_pct: float
    exit_time: datetime
    exit_bar: int
    is_win: bool


@dataclass
class RiskConfig:
    """Configuration for risk management."""

    # Drawdown limits
    max_drawdown_limit: float = 0.0  # 0 = no limit, 0.2 = 20%

    # Consecutive losses
    max_consecutive_losses: int = 0  # 0 = no limit
    cooldown_after_loss: int = 0  # Bars to wait after loss

    # Re-entry rules
    allow_re_entry: bool = True
    re_entry_delay_bars: int = 0

    # Trade limits
    max_trades_per_day: int = 0  # 0 = no limit
    max_trades_per_week: int = 0

    # Portfolio heat
    portfolio_heat_limit: float = 0.0  # Max total risk (0 = no limit)


@dataclass
class RiskState:
    """Current state of risk management."""

    # Trade history
    recent_trades: list[TradeResult] = field(default_factory=list)

    # Consecutive tracking
    consecutive_losses: int = 0
    consecutive_wins: int = 0

    # Equity tracking
    peak_equity: float = 0.0
    current_equity: float = 0.0
    current_drawdown: float = 0.0

    # Cooldown tracking
    cooldown_until_bar: int = 0
    last_exit_bar: int = -1

    # Trade counts
    trades_today: int = 0
    trades_this_week: int = 0
    current_day: int | None = None  # Day of year
    current_week: int | None = None  # Week of year

    # Circuit breaker
    trading_halted: bool = False
    halt_reason: str = ""


class UniversalRiskManager:
    """
    Universal risk manager for all risk control scenarios.

    Features:
    - Drawdown monitoring and limits
    - Consecutive loss tracking
    - Cooldown periods
    - Trade frequency limits
    - Portfolio heat management
    """

    def __init__(self, config: RiskConfig, initial_capital: float = 10000.0):
        self.config = config
        self.initial_capital = initial_capital
        self.state = RiskState(
            peak_equity=initial_capital, current_equity=initial_capital
        )

    def can_trade(
        self, current_bar: int, current_time: datetime | None = None
    ) -> tuple:
        """
        Check if trading is allowed based on all risk rules.

        Args:
            current_bar: Current bar index
            current_time: Current timestamp (for day/week tracking)

        Returns:
            (can_trade: bool, reason: str)
        """
        cfg = self.config
        state = self.state

        # Check if trading is halted
        if state.trading_halted:
            return False, f"Trading halted: {state.halt_reason}"

        # Check max drawdown
        if (
            cfg.max_drawdown_limit > 0
            and state.current_drawdown >= cfg.max_drawdown_limit
        ):
            state.trading_halted = True
            state.halt_reason = f"Max drawdown reached: {state.current_drawdown:.2%}"
            return False, state.halt_reason

        # Check consecutive losses
        if (
            cfg.max_consecutive_losses > 0
            and state.consecutive_losses >= cfg.max_consecutive_losses
        ):
            return False, f"Max consecutive losses reached: {state.consecutive_losses}"

        # Check cooldown
        if current_bar < state.cooldown_until_bar:
            return False, f"In cooldown until bar {state.cooldown_until_bar}"

        # Check re-entry delay
        if cfg.re_entry_delay_bars > 0 and state.last_exit_bar >= 0:
            if current_bar < state.last_exit_bar + cfg.re_entry_delay_bars:
                return (
                    False,
                    f"Re-entry delay: {cfg.re_entry_delay_bars - (current_bar - state.last_exit_bar)} bars remaining",
                )

        # Check daily/weekly limits
        if current_time:
            self._update_time_tracking(current_time)

            if (
                cfg.max_trades_per_day > 0
                and state.trades_today >= cfg.max_trades_per_day
            ):
                return False, f"Max daily trades reached: {state.trades_today}"

            if (
                cfg.max_trades_per_week > 0
                and state.trades_this_week >= cfg.max_trades_per_week
            ):
                return False, f"Max weekly trades reached: {state.trades_this_week}"

        return True, "OK"

    def record_trade(self, trade_result: TradeResult, current_bar: int):
        """
        Record a completed trade and update risk state.

        Args:
            trade_result: Result of the closed trade
            current_bar: Current bar index
        """
        cfg = self.config
        state = self.state

        # Add to history
        state.recent_trades.append(trade_result)

        # Keep only last 100 trades
        if len(state.recent_trades) > 100:
            state.recent_trades = state.recent_trades[-100:]

        # Update consecutive tracking
        if trade_result.is_win:
            state.consecutive_wins += 1
            state.consecutive_losses = 0
        else:
            state.consecutive_losses += 1
            state.consecutive_wins = 0

            # Apply cooldown after loss
            if cfg.cooldown_after_loss > 0:
                state.cooldown_until_bar = current_bar + cfg.cooldown_after_loss

        # Update exit tracking
        state.last_exit_bar = trade_result.exit_bar

        # Update trade counts
        state.trades_today += 1
        state.trades_this_week += 1

    def update_equity(self, new_equity: float):
        """
        Update equity and drawdown tracking.

        Args:
            new_equity: Current equity value
        """
        state = self.state

        state.current_equity = new_equity

        # Update peak
        if new_equity > state.peak_equity:
            state.peak_equity = new_equity

        # Calculate drawdown
        if state.peak_equity > 0:
            state.current_drawdown = (
                state.peak_equity - new_equity
            ) / state.peak_equity

    def _update_time_tracking(self, current_time: datetime):
        """Update day/week tracking for trade limits."""
        state = self.state

        day_of_year = current_time.timetuple().tm_yday
        week_of_year = current_time.isocalendar()[1]

        # Reset daily counter on new day
        if state.current_day is None or state.current_day != day_of_year:
            state.current_day = day_of_year
            state.trades_today = 0

        # Reset weekly counter on new week
        if state.current_week is None or state.current_week != week_of_year:
            state.current_week = week_of_year
            state.trades_this_week = 0

    def get_max_position_risk(self, current_open_risk: float = 0.0) -> float:
        """
        Get maximum allowed risk for new position based on portfolio heat.

        Args:
            current_open_risk: Total risk of currently open positions

        Returns:
            Maximum allowed risk for new position (0-1)
        """
        cfg = self.config

        if cfg.portfolio_heat_limit <= 0:
            return 1.0  # No limit

        remaining_heat = cfg.portfolio_heat_limit - current_open_risk
        return max(0.0, remaining_heat)

    def reset(self):
        """Reset risk manager to initial state."""
        self.state = RiskState(
            peak_equity=self.initial_capital, current_equity=self.initial_capital
        )

    def get_risk_stats(self) -> dict:
        """Get current risk statistics."""
        state = self.state

        # Calculate win rate from recent trades
        if state.recent_trades:
            wins = sum(1 for t in state.recent_trades if t.is_win)
            win_rate = wins / len(state.recent_trades)
        else:
            win_rate = 0.5

        return {
            "current_drawdown": round(state.current_drawdown * 100, 2),
            "peak_equity": round(state.peak_equity, 2),
            "current_equity": round(state.current_equity, 2),
            "consecutive_losses": state.consecutive_losses,
            "consecutive_wins": state.consecutive_wins,
            "trades_today": state.trades_today,
            "trades_this_week": state.trades_this_week,
            "trading_halted": state.trading_halted,
            "halt_reason": state.halt_reason,
            "recent_win_rate": round(win_rate * 100, 1),
        }

    @staticmethod
    def from_backtest_input(
        input_data, initial_capital: float
    ) -> "UniversalRiskManager":
        """
        Create RiskManager from BacktestInput.

        Args:
            input_data: BacktestInput instance
            initial_capital: Starting capital

        Returns:
            Configured UniversalRiskManager
        """
        config = RiskConfig(
            max_drawdown_limit=getattr(input_data, "max_drawdown_limit", 0.0),
            max_consecutive_losses=getattr(input_data, "max_consecutive_losses", 0),
            cooldown_after_loss=getattr(input_data, "cooldown_after_loss", 0),
            allow_re_entry=getattr(input_data, "allow_re_entry", True),
            re_entry_delay_bars=getattr(input_data, "re_entry_delay_bars", 0),
            max_trades_per_day=getattr(input_data, "max_trades_per_day", 0),
            max_trades_per_week=getattr(input_data, "max_trades_per_week", 0),
            portfolio_heat_limit=getattr(input_data, "portfolio_heat_limit", 0.0),
        )
        return UniversalRiskManager(config, initial_capital)
