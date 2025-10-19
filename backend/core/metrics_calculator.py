"""
Metrics Calculator - Расчет метрик производительности бэктеста

Этот модуль отвечает за:
- Расчет 20+ метрик производительности
- Анализ equity curve
- Расчет drawdown
- Risk-adjusted returns (Sharpe, Sortino, Calmar)
- Trade statistics (Win Rate, Profit Factor)
"""

from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Калькулятор метрик для бэктеста
    
    Рассчитывает 20+ метрик производительности:
    - Returns: Total, Annual, Monthly
    - Risk metrics: Sharpe, Sortino, Calmar
    - Drawdown: Max, Average, Duration
    - Trade stats: Win Rate, Profit Factor, Expectancy
    - Position stats: Average, Largest, Count
    
    Example:
        calculator = MetricsCalculator()
        
        metrics = calculator.calculate_all(
            trades=trades_list,
            equity_curve=equity_series,
            initial_capital=10000.0,
            risk_free_rate=0.02
        )
        
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Инициализация Metrics Calculator
        
        Args:
            risk_free_rate: Безрисковая ставка (по умолчанию 2% годовых)
        """
        self.risk_free_rate = risk_free_rate
        logger.info(f"MetricsCalculator initialized: risk_free_rate={risk_free_rate*100:.2f}%")
    
    def calculate_all(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: pd.Series,
        initial_capital: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Рассчитать все метрики
        
        Args:
            trades: Список сделок (dict с полями: pnl, entry_time, exit_time, side, etc.)
            equity_curve: Equity curve (pd.Series с timestamp index)
            initial_capital: Начальный капитал
            start_date: Дата начала бэктеста
            end_date: Дата окончания бэктеста
            
        Returns:
            Dict с метриками
        """
        metrics = {}
        
        # Базовые метрики
        final_capital = equity_curve.iloc[-1] if len(equity_curve) > 0 else initial_capital
        total_return = ((final_capital - initial_capital) / initial_capital) * 100
        
        metrics['initial_capital'] = initial_capital
        metrics['final_capital'] = final_capital
        metrics['total_return'] = total_return
        
        # Временные метрики
        if start_date and end_date:
            duration_days = (end_date - start_date).days
            metrics['duration_days'] = duration_days
            metrics['annual_return'] = self._annualize_return(total_return / 100, duration_days) * 100
        else:
            metrics['duration_days'] = None
            metrics['annual_return'] = None
        
        # Trade metrics
        if trades:
            trade_metrics = self._calculate_trade_metrics(trades)
            metrics.update(trade_metrics)
        else:
            metrics.update(self._empty_trade_metrics())
        
        # Equity curve metrics
        if len(equity_curve) > 1:
            equity_metrics = self._calculate_equity_metrics(
                equity_curve,
                initial_capital,
                self.risk_free_rate
            )
            metrics.update(equity_metrics)
        else:
            metrics.update(self._empty_equity_metrics())
        
        # Drawdown metrics
        if len(equity_curve) > 1:
            drawdown_metrics = self._calculate_drawdown_metrics(equity_curve)
            metrics.update(drawdown_metrics)
        else:
            metrics.update(self._empty_drawdown_metrics())
        
        # Risk-adjusted metrics
        if metrics.get('sharpe_ratio') and metrics.get('max_drawdown'):
            metrics['calmar_ratio'] = self._calculate_calmar_ratio(
                metrics.get('annual_return', 0),
                metrics['max_drawdown']
            )
        else:
            metrics['calmar_ratio'] = None
        
        # Recovery factor
        if metrics['max_drawdown'] and metrics['max_drawdown'] != 0:
            metrics['recovery_factor'] = total_return / abs(metrics['max_drawdown'])
        else:
            metrics['recovery_factor'] = None
        
        logger.info(
            f"Metrics calculated: Return={total_return:.2f}%, "
            f"Sharpe={metrics.get('sharpe_ratio', 0):.2f}, "
            f"MaxDD={metrics.get('max_drawdown', 0):.2f}%"
        )
        
        return metrics
    
    # ========================================================================
    # TRADE METRICS
    # ========================================================================
    
    def _calculate_trade_metrics(self, trades: List[Dict]) -> Dict[str, Any]:
        """Рассчитать метрики по сделкам"""
        
        if not trades:
            return self._empty_trade_metrics()
        
        # Фильтрация закрытых сделок с PnL
        closed_trades = [t for t in trades if t.get('exit_time') is not None]
        
        if not closed_trades:
            return self._empty_trade_metrics()
        
        # PnL данные
        pnls = [t.get('pnl', 0) for t in closed_trades]
        net_pnls = [t.get('net_pnl', t.get('pnl', 0)) for t in closed_trades]
        
        # Winning/Losing trades
        winning_trades = [t for t in closed_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in closed_trades if t.get('pnl', 0) < 0]
        breakeven_trades = [t for t in closed_trades if t.get('pnl', 0) == 0]
        
        # Counts
        total_trades = len(closed_trades)
        winning_count = len(winning_trades)
        losing_count = len(losing_trades)
        
        # Win rate
        win_rate = (winning_count / total_trades * 100) if total_trades > 0 else 0
        
        # Average PnL
        avg_trade = np.mean(net_pnls) if net_pnls else 0
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Largest win/loss
        largest_win = max([t['pnl'] for t in winning_trades], default=0)
        largest_loss = min([t['pnl'] for t in losing_trades], default=0)
        
        # Profit factor
        total_wins = sum([t['pnl'] for t in winning_trades])
        total_losses = abs(sum([t['pnl'] for t in losing_trades]))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Expectancy
        expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * abs(avg_loss))
        
        # Average duration
        durations = []
        for t in closed_trades:
            if t.get('entry_time') and t.get('exit_time'):
                if isinstance(t['entry_time'], datetime) and isinstance(t['exit_time'], datetime):
                    duration = (t['exit_time'] - t['entry_time']).total_seconds()
                    durations.append(duration)
        
        avg_duration = np.mean(durations) if durations else 0
        
        # Consecutive wins/losses
        consecutive_wins = self._calculate_consecutive_wins(closed_trades)
        consecutive_losses = self._calculate_consecutive_losses(closed_trades)
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_count,
            'losing_trades': losing_count,
            'breakeven_trades': len(breakeven_trades),
            'win_rate': win_rate,
            'avg_trade_pnl': avg_trade,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'avg_trade_duration_seconds': avg_duration,
            'avg_trade_duration_minutes': avg_duration / 60,
            'max_consecutive_wins': consecutive_wins,
            'max_consecutive_losses': consecutive_losses
        }
    
    def _empty_trade_metrics(self) -> Dict[str, Any]:
        """Пустые метрики для случая без сделок"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'breakeven_trades': 0,
            'win_rate': 0.0,
            'avg_trade_pnl': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'profit_factor': 0.0,
            'expectancy': 0.0,
            'avg_trade_duration_seconds': 0.0,
            'avg_trade_duration_minutes': 0.0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0
        }
    
    # ========================================================================
    # EQUITY CURVE METRICS
    # ========================================================================
    
    def _calculate_equity_metrics(
        self,
        equity_curve: pd.Series,
        initial_capital: float,
        risk_free_rate: float
    ) -> Dict[str, Any]:
        """Рассчитать метрики на основе equity curve"""
        
        # Returns
        returns = equity_curve.pct_change().dropna()
        
        if len(returns) == 0:
            return self._empty_equity_metrics()
        
        # Volatility (annualized)
        volatility = returns.std() * np.sqrt(252)  # Assuming daily data
        
        # Sharpe ratio
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / returns.std() if returns.std() > 0 else 0
        
        # Sortino ratio (только negative returns)
        negative_returns = returns[returns < 0]
        downside_deviation = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
        sortino_ratio = np.sqrt(252) * excess_returns.mean() / downside_deviation if downside_deviation > 0 else 0
        
        return {
            'volatility': volatility * 100,  # В процентах
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio
        }
    
    def _empty_equity_metrics(self) -> Dict[str, Any]:
        """Пустые метрики для equity curve"""
        return {
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0
        }
    
    # ========================================================================
    # DRAWDOWN METRICS
    # ========================================================================
    
    def _calculate_drawdown_metrics(self, equity_curve: pd.Series) -> Dict[str, Any]:
        """Рассчитать метрики drawdown"""
        
        # Running maximum
        running_max = equity_curve.expanding().max()
        
        # Drawdown (в процентах)
        drawdown = ((equity_curve - running_max) / running_max) * 100
        
        # Max drawdown
        max_drawdown = drawdown.min()
        
        # Max drawdown date
        max_dd_date = drawdown.idxmin() if not drawdown.empty else None
        
        # Average drawdown
        negative_dd = drawdown[drawdown < 0]
        avg_drawdown = negative_dd.mean() if len(negative_dd) > 0 else 0
        
        # Max drawdown duration
        max_dd_duration = self._calculate_max_drawdown_duration(equity_curve, running_max)
        
        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_date': max_dd_date,
            'avg_drawdown': avg_drawdown,
            'max_drawdown_duration_periods': max_dd_duration
        }
    
    def _empty_drawdown_metrics(self) -> Dict[str, Any]:
        """Пустые метрики для drawdown"""
        return {
            'max_drawdown': 0.0,
            'max_drawdown_date': None,
            'avg_drawdown': 0.0,
            'max_drawdown_duration_periods': 0
        }
    
    def _calculate_max_drawdown_duration(
        self,
        equity_curve: pd.Series,
        running_max: pd.Series
    ) -> int:
        """Рассчитать максимальную длительность drawdown (в периодах)"""
        
        # Найти все периоды drawdown
        is_drawdown = equity_curve < running_max
        
        # Группировка последовательных True
        drawdown_groups = (is_drawdown != is_drawdown.shift()).cumsum()
        
        # Фильтрация только drawdown периодов
        drawdown_periods = is_drawdown[is_drawdown].groupby(drawdown_groups[is_drawdown])
        
        # Максимальная длительность
        if len(drawdown_periods) > 0:
            max_duration = drawdown_periods.size().max()
            return int(max_duration)
        
        return 0
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _annualize_return(self, total_return: float, days: int) -> float:
        """Аннуализировать доходность"""
        if days <= 0:
            return 0.0
        
        years = days / 365.25
        annual_return = (1 + total_return) ** (1 / years) - 1
        return annual_return
    
    def _calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
        """Рассчитать Calmar ratio"""
        if max_drawdown == 0:
            return 0.0
        
        return annual_return / abs(max_drawdown)
    
    def _calculate_consecutive_wins(self, trades: List[Dict]) -> int:
        """Рассчитать максимальное количество последовательных прибыльных сделок"""
        if not trades:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade.get('pnl', 0) > 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_consecutive_losses(self, trades: List[Dict]) -> int:
        """Рассчитать максимальное количество последовательных убыточных сделок"""
        if not trades:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade.get('pnl', 0) < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def format_metrics(self, metrics: Dict[str, Any]) -> str:
        """
        Форматировать метрики для вывода
        
        Args:
            metrics: Dictionary с метриками
            
        Returns:
            str: Отформатированная строка
        """
        lines = []
        lines.append("=" * 70)
        lines.append("  BACKTEST RESULTS")
        lines.append("=" * 70)
        
        # Capital
        lines.append("\n📊 Capital:")
        lines.append(f"  Initial Capital:    ${metrics.get('initial_capital', 0):,.2f}")
        lines.append(f"  Final Capital:      ${metrics.get('final_capital', 0):,.2f}")
        lines.append(f"  Total Return:       {metrics.get('total_return', 0):+.2f}%")
        if metrics.get('annual_return') is not None:
            lines.append(f"  Annual Return:      {metrics.get('annual_return', 0):+.2f}%")
        
        # Trades
        lines.append("\n📈 Trades:")
        lines.append(f"  Total Trades:       {metrics.get('total_trades', 0)}")
        lines.append(f"  Winning:            {metrics.get('winning_trades', 0)}")
        lines.append(f"  Losing:             {metrics.get('losing_trades', 0)}")
        lines.append(f"  Win Rate:           {metrics.get('win_rate', 0):.2f}%")
        
        # PnL
        lines.append("\n💰 PnL:")
        lines.append(f"  Avg Trade:          ${metrics.get('avg_trade_pnl', 0):,.2f}")
        lines.append(f"  Avg Win:            ${metrics.get('avg_win', 0):,.2f}")
        lines.append(f"  Avg Loss:           ${metrics.get('avg_loss', 0):,.2f}")
        lines.append(f"  Largest Win:        ${metrics.get('largest_win', 0):,.2f}")
        lines.append(f"  Largest Loss:       ${metrics.get('largest_loss', 0):,.2f}")
        lines.append(f"  Profit Factor:      {metrics.get('profit_factor', 0):.2f}")
        lines.append(f"  Expectancy:         ${metrics.get('expectancy', 0):,.2f}")
        
        # Risk Metrics
        lines.append("\n⚠️  Risk Metrics:")
        lines.append(f"  Max Drawdown:       {metrics.get('max_drawdown', 0):.2f}%")
        lines.append(f"  Avg Drawdown:       {metrics.get('avg_drawdown', 0):.2f}%")
        lines.append(f"  Volatility:         {metrics.get('volatility', 0):.2f}%")
        lines.append(f"  Sharpe Ratio:       {metrics.get('sharpe_ratio', 0):.2f}")
        lines.append(f"  Sortino Ratio:      {metrics.get('sortino_ratio', 0):.2f}")
        if metrics.get('calmar_ratio') is not None:
            lines.append(f"  Calmar Ratio:       {metrics.get('calmar_ratio', 0):.2f}")
        if metrics.get('recovery_factor') is not None:
            lines.append(f"  Recovery Factor:    {metrics.get('recovery_factor', 0):.2f}")
        
        # Duration
        if metrics.get('avg_trade_duration_minutes'):
            lines.append("\n⏱️  Duration:")
            lines.append(f"  Avg Trade:          {metrics.get('avg_trade_duration_minutes', 0):.1f} min")
        
        lines.append("\n" + "=" * 70)
        
        return "\n".join(lines)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> float:
    """
    Рассчитать Sharpe Ratio
    
    Args:
        returns: Series с returns
        risk_free_rate: Годовая безрисковая ставка
        periods_per_year: Периодов в году (252 для дневных данных)
        
    Returns:
        float: Sharpe Ratio
    """
    excess_returns = returns - (risk_free_rate / periods_per_year)
    sharpe = np.sqrt(periods_per_year) * excess_returns.mean() / returns.std()
    return sharpe if not np.isnan(sharpe) else 0.0


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Рассчитать максимальный drawdown
    
    Args:
        equity_curve: Equity curve (pd.Series)
        
    Returns:
        float: Max drawdown в процентах (отрицательное число)
    """
    running_max = equity_curve.expanding().max()
    drawdown = ((equity_curve - running_max) / running_max) * 100
    return drawdown.min()


def calculate_win_rate(trades: List[Dict]) -> float:
    """
    Рассчитать win rate
    
    Args:
        trades: Список сделок с полем 'pnl'
        
    Returns:
        float: Win rate в процентах
    """
    if not trades:
        return 0.0
    
    winning = sum(1 for t in trades if t.get('pnl', 0) > 0)
    return (winning / len(trades)) * 100


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    print("="*70)
    print("  METRICS CALCULATOR - EXAMPLE USAGE")
    print("="*70)
    
    # Создание MetricsCalculator
    calculator = MetricsCalculator(risk_free_rate=0.02)
    
    # Пример данных
    # 1. Trades
    trades = [
        {'pnl': 100, 'net_pnl': 94, 'entry_time': datetime(2024, 1, 1, 10, 0), 'exit_time': datetime(2024, 1, 1, 14, 0)},
        {'pnl': -50, 'net_pnl': -53, 'entry_time': datetime(2024, 1, 2, 10, 0), 'exit_time': datetime(2024, 1, 2, 12, 0)},
        {'pnl': 150, 'net_pnl': 144, 'entry_time': datetime(2024, 1, 3, 10, 0), 'exit_time': datetime(2024, 1, 3, 15, 0)},
        {'pnl': -30, 'net_pnl': -32, 'entry_time': datetime(2024, 1, 4, 10, 0), 'exit_time': datetime(2024, 1, 4, 11, 0)},
        {'pnl': 200, 'net_pnl': 194, 'entry_time': datetime(2024, 1, 5, 10, 0), 'exit_time': datetime(2024, 1, 5, 16, 0)},
    ]
    
    # 2. Equity curve
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    initial_capital = 10000.0
    
    # Симуляция роста капитала с волатильностью
    np.random.seed(42)
    daily_returns = np.random.normal(0.001, 0.02, 100)  # 0.1% средний дневной рост, 2% волатильность
    equity_values = initial_capital * (1 + daily_returns).cumprod()
    equity_curve = pd.Series(equity_values, index=dates)
    
    # Расчет метрик
    print("\n📊 Calculating metrics...")
    metrics = calculator.calculate_all(
        trades=trades,
        equity_curve=equity_curve,
        initial_capital=initial_capital,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 4, 9)
    )
    
    # Вывод результатов
    print("\n" + calculator.format_metrics(metrics))
    
    # Отдельные метрики
    print("\n📈 Key Metrics:")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown: {metrics['max_drawdown']:.2f}%")
    print(f"  Win Rate: {metrics['win_rate']:.2f}%")
    print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
    
    print("\n" + "="*70)
    print("  ✅ Metrics Calculator working correctly!")
    print("="*70)
