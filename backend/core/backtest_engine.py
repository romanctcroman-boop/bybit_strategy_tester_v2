"""Backtest Engine - основной движок бэктестирования.

Реализует bar-by-bar симуляцию торговли с поддержкой:
- Простых индикаторных стратегий (EMA crossover, RSI, etc.)
- TP/SL/Trailing stop
- Commission и Slippage
- Расчёт всех метрик из ТЗ (Performance, Risk, Trades-analysis)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Открытая позиция."""
    entry_time: datetime
    entry_price: float
    quantity: float
    side: str  # 'long' or 'short'
    entry_bar_index: int
    
    # Tracking для Run-up/Drawdown
    highest_price: float = 0.0
    lowest_price: float = float('inf')
    
    def __post_init__(self):
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price
        if self.lowest_price == float('inf'):
            self.lowest_price = self.entry_price


@dataclass
class Trade:
    """Закрытая сделка."""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    side: str
    pnl: float
    pnl_pct: float
    commission: float
    run_up: float = 0.0
    run_up_pct: float = 0.0
    drawdown: float = 0.0
    drawdown_pct: float = 0.0
    bars_held: int = 0
    exit_reason: str = ''


@dataclass
class BacktestState:
    """Состояние бэктеста."""
    capital: float
    equity: float
    positions: list[Position] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    
    # Indicators cache
    indicators: dict[str, pd.Series] = field(default_factory=dict)


class BacktestEngine:
    """Движок бэктестирования с bar-by-bar симуляцией."""
    
    def __init__(
        self,
        initial_capital: float = 10_000.0,
        commission: float = 0.0006,  # 0.06% (Bybit taker fee)
        slippage_pct: float = 0.05,  # 0.05% slippage
        leverage: int = 1,  # Плечо (1x-100x)
        order_size_usd: float | None = None,  # Фиксированный размер ордера в USDT
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage_pct = slippage_pct
        self.leverage = leverage
        self.order_size_usd = order_size_usd
        
    def run(self, data: pd.DataFrame, strategy_config: dict) -> dict[str, Any]:
        """Запуск бэктеста.
        
        Args:
            data: OHLCV данные с колонками [timestamp, open, high, low, close, volume]
            strategy_config: Конфигурация стратегии
            
        Returns:
            Словарь с результатами: метрики, сделки, equity curve
        """
        if data.empty:
            logger.warning("Empty data provided to backtest engine")
            return self._empty_result()
        
        # Подготовка данных
        df = self._prepare_data(data)
        
        # Инициализация состояния
        state = BacktestState(
            capital=self.initial_capital,
            equity=self.initial_capital
        )
        
        # Расчёт индикаторов
        state.indicators = self._calculate_indicators(df, strategy_config)
        
        # Основной цикл бэктеста
        for i in range(len(df)):
            bar = df.iloc[i]
            self._process_bar(i, bar, df, state, strategy_config)
        
        # Закрытие всех открытых позиций
        self._close_all_positions(len(df) - 1, df.iloc[-1], state, "end_of_data")
        
        # Расчёт метрик
        results = self._calculate_metrics(state, df)
        
        return results
    
    def _prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Подготовка и валидация данных."""
        df = data.copy()
        
        # Ensure required columns
        required = ['close']
        if not all(col in df.columns for col in required):
            raise ValueError(f"Data must contain columns: {required}")
        
        # Add OHLC if missing (use close as fallback)
        for col in ['open', 'high', 'low']:
            if col not in df.columns:
                df[col] = df['close']
        
        # Ensure timestamp
        if 'timestamp' not in df.columns:
            if df.index.name == 'timestamp' or isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
            else:
                df['timestamp'] = pd.date_range(start='2020-01-01', periods=len(df), freq='1h')
        
        # Convert timestamp to datetime
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df = df.reset_index(drop=True)
        
        return df
    
    def _calculate_indicators(self, df: pd.DataFrame, config: dict) -> dict[str, pd.Series]:
        """Расчёт технических индикаторов."""
        indicators = {}
        
        strategy_type = config.get('type', 'ema_crossover')
        
        if strategy_type == 'ema_crossover':
            # EMA Crossover стратегия
            fast_period = config.get('fast_ema', 50)
            slow_period = config.get('slow_ema', 200)
            
            indicators['ema_fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
            indicators['ema_slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
            
        elif strategy_type == 'rsi':
            # RSI стратегия
            period = config.get('rsi_period', 14)
            indicators['rsi'] = self._calculate_rsi(df['close'], period)
            
            # MA для фильтра тренда
            ma_period = config.get('ma_period', 200)
            indicators['ma'] = df['close'].rolling(window=ma_period).mean()
        
        return indicators
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Расчёт RSI индикатора."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _process_bar(
        self,
        i: int,
        bar: pd.Series,
        df: pd.DataFrame,
        state: BacktestState,
        config: dict
    ):
        """Обработка одного бара данных."""
        # 1. Update existing positions (Run-up/Drawdown tracking)
        for pos in state.positions:
            pos.highest_price = max(pos.highest_price, bar['high'])
            pos.lowest_price = min(pos.lowest_price, bar['low'])
        
        # 2. Check exit conditions for open positions
        self._check_exits(i, bar, state, config)
        
        # 3. Check entry conditions (if no positions or pyramiding allowed)
        max_positions = config.get('max_positions', 1)
        if len(state.positions) < max_positions:
            self._check_entry(i, bar, df, state, config)
        
        # 4. Update equity curve
        unrealized_pnl = self._calculate_unrealized_pnl(bar, state)
        state.equity = state.capital + unrealized_pnl
        
        state.equity_curve.append({
            'timestamp': bar['timestamp'],
            'equity': state.equity,
            'capital': state.capital,
            'unrealized_pnl': unrealized_pnl,
            'positions_count': len(state.positions)
        })
    
    def _check_entry(
        self,
        i: int,
        bar: pd.Series,
        df: pd.DataFrame,
        state: BacktestState,
        config: dict
    ):
        """Проверка условий входа в позицию."""
        if i < 1:  # Need at least 2 bars for crossover
            return
        
        strategy_type = config.get('type', 'ema_crossover')
        direction = config.get('direction', 'long')  # 'long' or 'short'
        
        signal = False
        signal_side = None
        
        if strategy_type == 'ema_crossover':
            # EMA Crossover: fast crosses above slow
            ema_fast = state.indicators['ema_fast']
            ema_slow = state.indicators['ema_slow']
            
            if pd.isna(ema_fast.iloc[i]) or pd.isna(ema_slow.iloc[i]):
                return
            
            # Long signal: fast crosses above slow
            if ema_fast.iloc[i] > ema_slow.iloc[i] and ema_fast.iloc[i - 1] <= ema_slow.iloc[i - 1]:
                signal = True
                signal_side = 'long'
            
            # Short signal: fast crosses below slow
            elif ema_fast.iloc[i] < ema_slow.iloc[i] and ema_fast.iloc[i - 1] >= ema_slow.iloc[i - 1]:
                signal = True
                signal_side = 'short'
            
        elif strategy_type == 'rsi':
            # RSI strategy: RSI < oversold (long) or RSI > overbought (short)
            rsi = state.indicators['rsi']
            ma = state.indicators.get('ma')
            
            oversold = config.get('rsi_oversold', 30)
            overbought = config.get('rsi_overbought', 70)
            
            if pd.isna(rsi.iloc[i]):
                return
            
            # Long signal
            if rsi.iloc[i] < oversold:
                signal = True
                signal_side = 'long'
                # Optional trend filter
                if ma is not None and not pd.isna(ma.iloc[i]):
                    if bar['close'] <= ma.iloc[i]:
                        signal = False
            
            # Short signal
            elif rsi.iloc[i] > overbought:
                signal = True
                signal_side = 'short'
                # Optional trend filter
                if ma is not None and not pd.isna(ma.iloc[i]):
                    if bar['close'] >= ma.iloc[i]:
                        signal = False
        
        # Filter by direction config
        if signal and signal_side:
            if direction == 'both' or direction == signal_side:
                self._open_position(i, bar, state, config, signal_side)
    
    def _open_position(
        self,
        i: int,
        bar: pd.Series,
        state: BacktestState,
        config: dict,
        side: str = 'long'
    ):
        """Открытие новой позиции."""
        # Position sizing
        if self.order_size_usd is not None:
            # Фиксированный размер ордера
            position_value = self.order_size_usd * self.leverage
        else:
            # Процент от капитала
            risk_per_trade = config.get('risk_per_trade_pct', 2.0) / 100.0  # 2% default
            position_value = state.capital * risk_per_trade * self.leverage
        
        # Entry price with slippage
        if side == 'long':
            entry_price = bar['close'] * (1 + self.slippage_pct / 100.0)
        else:  # short
            entry_price = bar['close'] * (1 - self.slippage_pct / 100.0)
        
        # Quantity (с учётом плеча)
        quantity = position_value / entry_price
        
        # Margin required (без плеча)
        margin_required = position_value / self.leverage
        
        # Check if we have enough capital
        if margin_required > state.capital:
            logger.debug(f"Insufficient capital: need ${margin_required:.2f}, have ${state.capital:.2f}")
            return
        
        # Commission (на полную позицию с плечом)
        commission = position_value * self.commission
        
        # Update capital (только маржа + комиссия)
        state.capital -= (margin_required + commission)
        
        # Create position
        pos = Position(
            entry_time=bar['timestamp'],
            entry_price=entry_price,
            quantity=quantity,
            side=side,
            entry_bar_index=i
        )
        
        state.positions.append(pos)
        
        logger.debug(
            f"Opened {side} position at ${entry_price:.2f}, qty={quantity:.4f}, "
            f"margin=${margin_required:.2f}, leverage={self.leverage}x, commission=${commission:.2f}"
        )
    
    def _check_exits(
        self,
        i: int,
        bar: pd.Series,
        state: BacktestState,
        config: dict
    ):
        """Проверка условий выхода из позиций."""
        positions_to_close = []
        
        for pos in state.positions:
            exit_reason = None
            exit_price = None
            
            # Calculate current PnL
            if pos.side == 'long':
                unrealized_pnl_pct = ((bar['close'] / pos.entry_price) - 1) * 100.0
            else:  # short
                unrealized_pnl_pct = ((pos.entry_price / bar['close']) - 1) * 100.0
            
            # Take Profit
            tp_pct = config.get('take_profit_pct', 5.0)
            if tp_pct > 0:
                if unrealized_pnl_pct >= tp_pct:
                    if pos.side == 'long':
                        exit_price = pos.entry_price * (1 + tp_pct / 100.0)
                        # Use high if reached
                        if bar['high'] >= exit_price:
                            exit_reason = 'take_profit'
                    else:  # short
                        exit_price = pos.entry_price * (1 - tp_pct / 100.0)
                        # Use low if reached
                        if bar['low'] <= exit_price:
                            exit_reason = 'take_profit'
            
            # Stop Loss
            sl_pct = config.get('stop_loss_pct', 2.0)
            if sl_pct > 0 and exit_reason is None:
                if unrealized_pnl_pct <= -sl_pct:
                    if pos.side == 'long':
                        exit_price = pos.entry_price * (1 - sl_pct / 100.0)
                        # Use low if hit
                        if bar['low'] <= exit_price:
                            exit_reason = 'stop_loss'
                    else:  # short
                        exit_price = pos.entry_price * (1 + sl_pct / 100.0)
                        # Use high if hit
                        if bar['high'] >= exit_price:
                            exit_reason = 'stop_loss'
            
            # Trailing Stop
            trailing_pct = config.get('trailing_stop_pct', 0) or 0
            if trailing_pct > 0 and exit_reason is None:
                if pos.side == 'long':
                    trailing_price = pos.highest_price * (1 - trailing_pct / 100.0)
                    if bar['low'] <= trailing_price:
                        exit_price = trailing_price
                        exit_reason = 'trailing_stop'
                else:  # short
                    trailing_price = pos.lowest_price * (1 + trailing_pct / 100.0)
                    if bar['high'] >= trailing_price:
                        exit_price = trailing_price
                        exit_reason = 'trailing_stop'
            
            # Signal exit (e.g., EMA crossover down for long, up for short)
            if exit_reason is None and config.get('signal_exit', False):
                if self._check_exit_signal(i, bar, state, config, pos.side):
                    exit_price = bar['close']
                    exit_reason = 'signal_exit'
            
            if exit_reason:
                positions_to_close.append((pos, exit_price, exit_reason))
        
        # Close positions
        for pos, exit_price, exit_reason in positions_to_close:
            self._close_position(i, bar, pos, exit_price, state, exit_reason)
    
    def _check_exit_signal(
        self,
        i: int,
        bar: pd.Series,
        state: BacktestState,
        config: dict,
        position_side: str
    ) -> bool:
        """Проверка сигнала выхода (противоположный кроссовер)."""
        if i < 1:
            return False
        
        strategy_type = config.get('type', 'ema_crossover')
        
        if strategy_type == 'ema_crossover':
            ema_fast = state.indicators['ema_fast']
            ema_slow = state.indicators['ema_slow']
            
            if pd.isna(ema_fast.iloc[i]) or pd.isna(ema_slow.iloc[i]):
                return False
            
            # Exit long: fast crosses below slow
            if position_side == 'long':
                return (
                    ema_fast.iloc[i] < ema_slow.iloc[i] and
                    ema_fast.iloc[i - 1] >= ema_slow.iloc[i - 1]
                )
            # Exit short: fast crosses above slow
            else:
                return (
                    ema_fast.iloc[i] > ema_slow.iloc[i] and
                    ema_fast.iloc[i - 1] <= ema_slow.iloc[i - 1]
                )
        
        return False
    
    def _close_position(
        self,
        i: int,
        bar: pd.Series,
        pos: Position,
        exit_price: float,
        state: BacktestState,
        exit_reason: str
    ):
        """Закрытие позиции."""
        # Apply slippage
        if pos.side == 'long':
            exit_price = exit_price * (1 - self.slippage_pct / 100.0)
        else:  # short
            exit_price = exit_price * (1 + self.slippage_pct / 100.0)
        
        # Calculate PnL (с учётом плеча и направления)
        position_value_entry = pos.quantity * pos.entry_price
        position_value_exit = pos.quantity * exit_price
        
        if pos.side == 'long':
            gross_pnl = position_value_exit - position_value_entry
        else:  # short
            gross_pnl = position_value_entry - position_value_exit
        
        # Commission (на выходе)
        commission = position_value_exit * self.commission
        net_pnl = gross_pnl - commission
        
        # Return margin + PnL
        margin_used = position_value_entry / self.leverage
        state.capital += margin_used + net_pnl
        
        # Calculate Run-up and Drawdown (с учётом направления)
        if pos.side == 'long':
            run_up = (pos.highest_price - pos.entry_price) * pos.quantity
            run_up_pct = ((pos.highest_price / pos.entry_price) - 1) * 100.0
            drawdown = (pos.entry_price - pos.lowest_price) * pos.quantity
            drawdown_pct = (1 - (pos.lowest_price / pos.entry_price)) * 100.0
        else:  # short
            run_up = (pos.entry_price - pos.lowest_price) * pos.quantity
            run_up_pct = ((pos.entry_price / pos.lowest_price) - 1) * 100.0
            drawdown = (pos.highest_price - pos.entry_price) * pos.quantity
            drawdown_pct = ((pos.highest_price / pos.entry_price) - 1) * 100.0
        
        # Bars held
        bars_held = i - pos.entry_bar_index
        
        # PnL percentage (с учётом направления)
        if pos.side == 'long':
            pnl_pct = ((exit_price / pos.entry_price) - 1) * 100.0
        else:  # short
            pnl_pct = ((pos.entry_price / exit_price) - 1) * 100.0
        
        # Create trade record
        trade = Trade(
            entry_time=pos.entry_time,
            exit_time=bar['timestamp'],
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=pos.quantity,
            side=pos.side,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            run_up=run_up,
            run_up_pct=run_up_pct,
            drawdown=drawdown,
            drawdown_pct=drawdown_pct,
            bars_held=bars_held,
            exit_reason=exit_reason
        )
        
        state.trades.append(trade)
        state.positions.remove(pos)
        
        logger.debug(
            f"Closed {pos.side} position: entry=${pos.entry_price:.2f}, exit=${exit_price:.2f}, "
            f"PnL=${net_pnl:.2f} ({pnl_pct:.2f}%), reason={exit_reason}"
        )
    
    def _close_all_positions(
        self,
        i: int,
        bar: pd.Series,
        state: BacktestState,
        reason: str = "end_of_data"
    ):
        """Закрытие всех открытых позиций."""
        for pos in list(state.positions):
            self._close_position(i, bar, pos, bar['close'], state, reason)
    
    def _calculate_unrealized_pnl(self, bar: pd.Series, state: BacktestState) -> float:
        """Расчёт нереализованного PnL (с учётом направления позиций)."""
        unrealized = 0.0
        for pos in state.positions:
            if pos.side == 'long':
                current_value = pos.quantity * bar['close']
                entry_value = pos.quantity * pos.entry_price
                unrealized += current_value - entry_value
            else:  # short
                entry_value = pos.quantity * pos.entry_price
                current_value = pos.quantity * bar['close']
                unrealized += entry_value - current_value
        return unrealized
    
    def _calculate_metrics(self, state: BacktestState, df: pd.DataFrame) -> dict[str, Any]:
        """Расчёт всех метрик по ТЗ."""
        trades = state.trades
        
        if not trades:
            return self._empty_result()
        
        # Basic stats
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        num_wins = len(winning_trades)
        num_losses = len(losing_trades)
        
        win_rate = (num_wins / total_trades) if total_trades > 0 else 0.0
        
        # PnL stats
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = sum(t.pnl for t in losing_trades)
        net_profit = sum(t.pnl for t in trades)
        total_commission = sum(t.commission for t in trades)
        
        profit_factor = (gross_profit / abs(gross_loss)) if gross_loss < 0 else float('inf')
        
        # Returns
        final_capital = state.capital
        total_return = ((final_capital / self.initial_capital) - 1) * 100.0
        
        # Equity curve analysis
        equity_values = np.array([point['equity'] for point in state.equity_curve])
        
        # Drawdown
        peak = np.maximum.accumulate(equity_values)
        drawdown = peak - equity_values
        max_drawdown_abs = np.max(drawdown)
        max_drawdown_pct = (max_drawdown_abs / self.initial_capital) * 100.0
        
        # Run-up
        runup = equity_values - self.initial_capital
        max_runup_abs = np.max(runup) if len(runup) > 0 else 0.0
        max_runup_pct = (max_runup_abs / self.initial_capital) * 100.0
        
        # Risk metrics
        returns = pd.Series(equity_values).pct_change().dropna()
        
        if len(returns) > 1:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
            
            # Sortino (downside deviation)
            downside_returns = returns[returns < 0]
            sortino_ratio = (
                (returns.mean() / downside_returns.std()) * np.sqrt(252)
                if len(downside_returns) > 0 and downside_returns.std() > 0
                else 0.0
            )
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0
        
        # Buy & Hold return
        buy_hold_return = ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100.0
        
        # Average stats
        avg_pnl = net_profit / total_trades if total_trades > 0 else 0.0
        avg_win = gross_profit / num_wins if num_wins > 0 else 0.0
        avg_loss = gross_loss / num_losses if num_losses > 0 else 0.0
        
        max_win = max((t.pnl for t in winning_trades), default=0.0)
        max_loss = min((t.pnl for t in losing_trades), default=0.0)
        
        avg_bars = np.mean([t.bars_held for t in trades]) if trades else 0.0
        avg_bars_win = np.mean([t.bars_held for t in winning_trades]) if winning_trades else 0.0
        avg_bars_loss = np.mean([t.bars_held for t in losing_trades]) if losing_trades else 0.0
        
        # Build result matching expected format
        return {
            'final_capital': float(final_capital),
            'total_return': float(total_return / 100.0),  # as decimal
            'total_trades': int(total_trades),
            'winning_trades': int(num_wins),
            'losing_trades': int(num_losses),
            'win_rate': float(win_rate),
            'sharpe_ratio': float(sharpe_ratio),
            'sortino_ratio': float(sortino_ratio),
            'max_drawdown': float(max_drawdown_pct / 100.0),  # as decimal
            'profit_factor': float(profit_factor),
            
            # Extended metrics
            'metrics': {
                'net_profit': float(net_profit),
                'net_profit_pct': float(total_return),
                'gross_profit': float(gross_profit),
                'gross_loss': float(gross_loss),
                'total_commission': float(total_commission),
                'max_drawdown_abs': float(max_drawdown_abs),
                'max_drawdown_pct': float(max_drawdown_pct),
                'max_runup_abs': float(max_runup_abs),
                'max_runup_pct': float(max_runup_pct),
                'buy_hold_return': float(buy_hold_return),
                'avg_pnl': float(avg_pnl),
                'avg_win': float(avg_win),
                'avg_loss': float(avg_loss),
                'max_win': float(max_win),
                'max_loss': float(max_loss),
                'avg_bars': float(avg_bars),
                'avg_bars_win': float(avg_bars_win),
                'avg_bars_loss': float(avg_bars_loss),
            },
            
            # Trades list (for detailed analysis)
            'trades': [
                {
                    'entry_time': t.entry_time.to_pydatetime().isoformat() if hasattr(t.entry_time, 'to_pydatetime') else t.entry_time.isoformat(),
                    'exit_time': t.exit_time.to_pydatetime().isoformat() if hasattr(t.exit_time, 'to_pydatetime') else t.exit_time.isoformat(),
                    'entry_price': float(t.entry_price),
                    'exit_price': float(t.exit_price),
                    'quantity': float(t.quantity),
                    'side': t.side,
                    'pnl': float(t.pnl),
                    'pnl_pct': float(t.pnl_pct),
                    'commission': float(t.commission),
                    'run_up': float(t.run_up),
                    'run_up_pct': float(t.run_up_pct),
                    'drawdown': float(t.drawdown),
                    'drawdown_pct': float(t.drawdown_pct),
                    'bars_held': int(t.bars_held),
                    'exit_reason': t.exit_reason,
                    'cumulative_pnl': float(t.pnl),  # For compatibility
                }
                for t in trades
            ],
            
            # Equity curve (convert to JSON-serializable list)
            'equity_curve': [
                {
                    'timestamp': point['timestamp'].to_pydatetime().isoformat() if hasattr(point['timestamp'], 'to_pydatetime') else point['timestamp'].isoformat(),
                    'equity': float(point['equity']),
                }
                for point in state.equity_curve
            ] if state.equity_curve else [],
        }
    
    def _empty_result(self) -> dict[str, Any]:
        """Результат для пустого бэктеста."""
        return {
            'final_capital': self.initial_capital,
            'total_return': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0,
            'metrics': {},
            'trades': [],
            'equity_curve': [],
        }
