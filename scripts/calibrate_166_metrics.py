"""
🎯 TradingView 166-Metrics Calibration Script

Калибровка всех 150+ метрик против золотого эталона TradingView.
Использует данные экспорта стратегии RSI Strategy with TP/SL (FIXED).

Настройки стратегии:
- RSI Length: 14
- Oversold: 25
- Overbought: 70
- Take Profit %: 1.5
- Stop Loss %: 3
- Base Qty (USDT): 100
- Leverage: 10
- Commission: 0.07%
- Period: Oct 1, 2025 - Jan 24, 2026

Источники данных:
- BYBIT_BTCUSDT.P, 15 (3).csv - OHLC с RSI + TP/SL уровнями
- BYBIT_BTCUSDT.P, 15 (4).csv - чистый OHLC
- RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-24.csv - список сделок

Created: 2026-01-24
"""

import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class MetricCategory(Enum):
    """Категории метрик по TradingView."""
    # Performance Overview
    OVERVIEW = "Overview"
    # Кривая капитала
    EQUITY_CURVE = "Equity Curve"
    # Сравнение с эталонами
    BENCHMARK = "Benchmark"
    # Риск-метрики
    RISK = "Risk"
    # Использование маржи
    MARGIN = "Margin"
    # Рост и просадки
    DRAWDOWN = "Drawdown"
    # Статистика сделок
    TRADE_STATS = "Trade Stats"
    # Продвинутые метрики
    ADVANCED = "Advanced"


@dataclass
class TradingViewMetric:
    """Определение одной метрики TradingView."""
    name_ru: str
    name_en: str
    category: MetricCategory
    tv_value_all: float | None = None
    tv_value_long: float | None = None
    tv_value_short: float | None = None
    calculated_value_all: float | None = None
    calculated_value_long: float | None = None
    calculated_value_short: float | None = None
    tolerance_percent: float = 0.5  # Допустимое отклонение %
    tolerance_absolute: float | None = None  # Абсолютное допустимое отклонение
    is_percentage: bool = False
    unit: str = "USDT"


@dataclass
class TradingViewGoldenReference:
    """Золотой эталон метрик TradingView."""

    # ===== OVERVIEW =====
    initial_capital: float = 1_000_000.00
    unrealized_pnl: float = 0.0

    net_profit_all: float = 173.59
    net_profit_all_pct: float = 0.02
    net_profit_long: float = 99.66
    net_profit_long_pct: float = 0.01
    net_profit_short: float = 73.93
    net_profit_short_pct: float = 0.01

    gross_profit_all: float = 864.40
    gross_profit_all_pct: float = 0.09
    gross_profit_long: float = 413.44
    gross_profit_long_pct: float = 0.04
    gross_profit_short: float = 450.96
    gross_profit_short_pct: float = 0.05

    gross_loss_all: float = 690.81
    gross_loss_all_pct: float = 0.07
    gross_loss_long: float = 313.78
    gross_loss_long_pct: float = 0.03
    gross_loss_short: float = 377.03
    gross_loss_short_pct: float = 0.04

    profit_factor_all: float = 1.251
    profit_factor_long: float = 1.318
    profit_factor_short: float = 1.196

    commission_paid_all: float = 119.01
    commission_paid_long: float = 56.11
    commission_paid_short: float = 62.90

    max_drawdown_value: float = 112.63
    max_drawdown_pct: float = 0.01

    # ===== TRADE STATISTICS =====
    total_trades_all: int = 85
    total_trades_long: int = 40
    total_trades_short: int = 45

    open_trades_all: int = 0
    open_trades_long: int = 0
    open_trades_short: int = 0

    winning_trades_all: int = 63
    winning_trades_long: int = 30
    winning_trades_short: int = 33

    losing_trades_all: int = 22
    losing_trades_long: int = 10
    losing_trades_short: int = 12

    win_rate_all: float = 74.12
    win_rate_long: float = 75.00
    win_rate_short: float = 73.33

    # ===== AVERAGE P&L =====
    avg_trade_pnl_all: float = 2.04
    avg_trade_pnl_all_pct: float = 0.20
    avg_trade_pnl_long: float = 2.49
    avg_trade_pnl_long_pct: float = 0.25
    avg_trade_pnl_short: float = 1.64
    avg_trade_pnl_short_pct: float = 0.16

    avg_win_all: float = 13.72
    avg_win_all_pct: float = 1.37
    avg_win_long: float = 13.78
    avg_win_long_pct: float = 1.38
    avg_win_short: float = 13.67
    avg_win_short_pct: float = 1.37

    avg_loss_all: float = 31.40
    avg_loss_all_pct: float = 3.14
    avg_loss_long: float = 31.38
    avg_loss_long_pct: float = 3.14
    avg_loss_short: float = 31.42
    avg_loss_short_pct: float = 3.14

    payoff_ratio_all: float = 0.437
    payoff_ratio_long: float = 0.439
    payoff_ratio_short: float = 0.435

    # ===== EXTREMES =====
    largest_win_all: float = 19.34
    largest_win_long: float = 19.34
    largest_win_short: float = 15.43

    largest_win_pct_all: float = 1.93
    largest_win_pct_long: float = 1.93
    largest_win_pct_short: float = 1.54

    largest_win_of_gross_all: float = 2.24
    largest_win_of_gross_long: float = 4.68
    largest_win_of_gross_short: float = 3.42

    largest_loss_all: float = 31.42
    largest_loss_long: float = 31.38
    largest_loss_short: float = 31.42

    largest_loss_pct_all: float = 3.14
    largest_loss_pct_long: float = 3.14
    largest_loss_pct_short: float = 3.14

    largest_loss_of_gross_all: float = 4.55
    largest_loss_of_gross_long: float = 10.00
    largest_loss_of_gross_short: float = 8.33

    # ===== EXPECTANCY =====
    expectancy_all: float = 2.04
    expectancy_long: float = 2.49
    expectancy_short: float = 1.64

    # ===== BARS IN POSITION =====
    avg_bars_all: int = 93
    avg_bars_long: int = 73
    avg_bars_short: int = 111

    avg_bars_win_all: int = 80
    avg_bars_win_long: int = 74
    avg_bars_win_short: int = 85

    avg_bars_loss_all: int = 131
    avg_bars_loss_long: int = 70
    avg_bars_loss_short: int = 182

    # ===== ANNUAL RETURNS =====
    cagr_all: float = 0.05
    cagr_long: float = 0.03
    cagr_short: float = 0.02

    return_on_capital_all: float = 0.00
    return_on_capital_long: float = 0.01
    return_on_capital_short: float = 0.01

    # ===== ACCOUNT SIZING =====
    required_account_size: float = 1142.45
    required_return_all: float = 15.19
    required_return_long: float = 8.72
    required_return_short: float = 6.47

    net_profit_vs_max_loss_all: float = 552.45
    net_profit_vs_max_loss_long: float = 317.59
    net_profit_vs_max_loss_short: float = 235.28

    # ===== RISK METRICS =====
    sharpe_ratio: float = -20.497
    sortino_ratio: float = -0.999

    # ===== BENCHMARK =====
    buy_hold_pnl: float = -230020.45
    buy_hold_pnl_pct: float = -23.06
    buy_hold_return_pct: float = 23.06
    strategy_outperformance: float = 230194.04

    # ===== MARGIN USAGE =====
    avg_margin_used: float = 712.76
    max_margin_used: float = 1029.80
    margin_efficiency: float = 6.11
    margin_calls: int = 0

    # ===== GROWTH =====
    avg_equity_growth_duration_days: int = 8
    avg_equity_growth_value: float = 99.79
    avg_equity_growth_pct: float = 0.01
    max_equity_growth_close: float = 176.83
    max_equity_growth_close_pct: float = 0.02
    max_equity_growth_intrabar: float = 267.76
    max_equity_growth_intrabar_pct: float = 0.03

    # ===== DRAWDOWN (from Screenshot 6: "Просадки") =====
    avg_drawdown_duration_days: int = 11
    avg_drawdown_close_value: float = 71.87
    avg_drawdown_close_pct: float = 0.01
    max_drawdown_close_value: float = 98.40
    max_drawdown_close_pct: float = 0.01
    max_drawdown_intrabar_value: float = 112.63
    max_drawdown_intrabar_pct: float = 0.01
    max_drawdown_pct_of_initial: float = 0.01
    return_on_max_drawdown: float = 1.54


def parse_tv_trades_csv(filepath: Path) -> pd.DataFrame:
    """Парсинг CSV экспорта сделок из TradingView."""
    df = pd.read_csv(filepath)

    # Переименуем колонки на английский для удобства
    column_map = {
        '№ Сделки': 'trade_num',
        'Тип': 'type',
        'Дата и время': 'datetime',
        'Сигнал': 'signal',
        'Цена USDT': 'price',
        'Размер позиции (кол-во)': 'qty',
        'Размер позиции (цена)': 'position_value',
        'Чистая прибыль / убыток USDT': 'pnl',
        'Чистая прибыль / убыток %': 'pnl_pct',
        'Благоприятное отклонение USDT': 'mfe',
        'Благоприятное отклонение %': 'mfe_pct',
        'Неблагоприятное отклонение USDT': 'mae',
        'Неблагоприятное отклонение %': 'mae_pct',
        'Совокупные ПР/УБ USDT': 'cumulative_pnl',
        'Совокупные ПР/УБ %': 'cumulative_pnl_pct',
    }
    df.rename(columns=column_map, inplace=True)

    return df

def calculate_metrics_from_trades(trades_df: pd.DataFrame, golden: TradingViewGoldenReference) -> dict[str, float]:
    """Рассчитать метрики из списка сделок с использованием Decimal для точности."""

    # Выделим только строки выхода (содержат финальный PnL)
    exits = trades_df[trades_df['type'].str.contains('Выход')].copy()

    # Разделим на лонги и шорты
    longs = exits[exits['type'].str.contains('длинной')]
    shorts = exits[exits['type'].str.contains('короткой')]

    metrics = {}

    # ===== ТОЧНЫЕ ВЫЧИСЛЕНИЯ С DECIMAL =====
    # TradingView округляет каждое значение PnL до 2 знаков, затем суммирует
    # Мы должны делать так же для точного совпадения

    def round_decimal(value: float, places: int = 2) -> Decimal:
        """Округление в стиле TradingView (ROUND_HALF_UP)."""
        d = Decimal(str(value))
        return d.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)

    def sum_pnl_precise(series: pd.Series) -> float:
        """Точная сумма PnL с округлением каждого значения как в TV."""
        if len(series) == 0:
            return 0.0
        # TradingView округляет каждый PnL до 2 знаков перед суммированием
        total = sum(round_decimal(x, 2) for x in series)
        return float(total)

    def mean_pnl_precise(series: pd.Series) -> float:
        """Точное среднее с Decimal."""
        if len(series) == 0:
            return 0.0
        total = sum(round_decimal(x, 2) for x in series)
        return float(total / len(series))

    # ===== CORE METRICS =====
    metrics['total_trades_all'] = len(exits)
    metrics['total_trades_long'] = len(longs)
    metrics['total_trades_short'] = len(shorts)

    # Net Profit - сумма округлённых PnL
    metrics['net_profit_all'] = sum_pnl_precise(exits['pnl'])
    metrics['net_profit_long'] = sum_pnl_precise(longs['pnl'])
    metrics['net_profit_short'] = sum_pnl_precise(shorts['pnl'])

    # Gross Profit - только положительные PnL
    metrics['gross_profit_all'] = sum_pnl_precise(exits[exits['pnl'] > 0]['pnl'])
    metrics['gross_profit_long'] = sum_pnl_precise(longs[longs['pnl'] > 0]['pnl'])
    metrics['gross_profit_short'] = sum_pnl_precise(shorts[shorts['pnl'] > 0]['pnl'])

    # Gross Loss - абсолютное значение суммы отрицательных PnL
    metrics['gross_loss_all'] = abs(sum_pnl_precise(exits[exits['pnl'] < 0]['pnl']))
    metrics['gross_loss_long'] = abs(sum_pnl_precise(longs[longs['pnl'] < 0]['pnl']))
    metrics['gross_loss_short'] = abs(sum_pnl_precise(shorts[shorts['pnl'] < 0]['pnl']))

    # Profit Factor с Decimal
    def calc_profit_factor(gross_profit: float, gross_loss: float) -> float:
        if gross_loss <= 0:
            return float('inf')
        pf = Decimal(str(gross_profit)) / Decimal(str(gross_loss))
        return float(pf.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))

    metrics['profit_factor_all'] = calc_profit_factor(
        metrics['gross_profit_all'], metrics['gross_loss_all']
    )

    metrics['profit_factor_long'] = calc_profit_factor(
        metrics['gross_profit_long'], metrics['gross_loss_long']
    )
    metrics['profit_factor_short'] = calc_profit_factor(
        metrics['gross_profit_short'], metrics['gross_loss_short']
    )

    # Win/Loss counts
    metrics['winning_trades_all'] = len(exits[exits['pnl'] > 0])
    metrics['winning_trades_long'] = len(longs[longs['pnl'] > 0])
    metrics['winning_trades_short'] = len(shorts[shorts['pnl'] > 0])

    metrics['losing_trades_all'] = len(exits[exits['pnl'] < 0])
    metrics['losing_trades_long'] = len(longs[longs['pnl'] < 0])
    metrics['losing_trades_short'] = len(shorts[shorts['pnl'] < 0])

    # Win Rate с Decimal
    def calc_win_rate(wins: int, total: int) -> float:
        if total <= 0:
            return 0.0
        rate = Decimal(str(wins)) / Decimal(str(total)) * Decimal('100')
        return float(rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    metrics['win_rate_all'] = calc_win_rate(
        metrics['winning_trades_all'], metrics['total_trades_all']
    )
    metrics['win_rate_long'] = calc_win_rate(
        metrics['winning_trades_long'], metrics['total_trades_long']
    )
    metrics['win_rate_short'] = calc_win_rate(
        metrics['winning_trades_short'], metrics['total_trades_short']
    )

    # Average Trade PnL с Decimal
    metrics['avg_trade_pnl_all'] = mean_pnl_precise(exits['pnl'])
    metrics['avg_trade_pnl_long'] = mean_pnl_precise(longs['pnl'])
    metrics['avg_trade_pnl_short'] = mean_pnl_precise(shorts['pnl'])

    # Average Win/Loss
    winning_trades = exits[exits['pnl'] > 0]
    losing_trades = exits[exits['pnl'] < 0]

    metrics['avg_win_all'] = mean_pnl_precise(winning_trades['pnl'])
    metrics['avg_win_long'] = mean_pnl_precise(longs[longs['pnl'] > 0]['pnl'])
    metrics['avg_win_short'] = mean_pnl_precise(shorts[shorts['pnl'] > 0]['pnl'])

    metrics['avg_loss_all'] = abs(mean_pnl_precise(losing_trades['pnl']))
    metrics['avg_loss_long'] = abs(mean_pnl_precise(longs[longs['pnl'] < 0]['pnl']))
    metrics['avg_loss_short'] = abs(mean_pnl_precise(shorts[shorts['pnl'] < 0]['pnl']))

    # Payoff Ratio (Avg Win / Avg Loss) с Decimal
    def calc_payoff_ratio(avg_win: float, avg_loss: float) -> float:
        if avg_loss <= 0:
            return float('inf')
        ratio = Decimal(str(avg_win)) / Decimal(str(avg_loss))
        return float(ratio.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))

    metrics['payoff_ratio_all'] = calc_payoff_ratio(
        metrics['avg_win_all'], metrics['avg_loss_all']
    )
    metrics['payoff_ratio_long'] = calc_payoff_ratio(
        metrics['avg_win_long'], metrics['avg_loss_long']
    )
    metrics['payoff_ratio_short'] = calc_payoff_ratio(
        metrics['avg_win_short'], metrics['avg_loss_short']
    )

    # Largest Win/Loss
    metrics['largest_win_all'] = winning_trades['pnl'].max() if len(winning_trades) > 0 else 0
    metrics['largest_win_long'] = longs[longs['pnl'] > 0]['pnl'].max() if len(longs[longs['pnl'] > 0]) > 0 else 0
    metrics['largest_win_short'] = shorts[shorts['pnl'] > 0]['pnl'].max() if len(shorts[shorts['pnl'] > 0]) > 0 else 0

    metrics['largest_loss_all'] = abs(losing_trades['pnl'].min()) if len(losing_trades) > 0 else 0
    metrics['largest_loss_long'] = abs(longs[longs['pnl'] < 0]['pnl'].min()) if len(longs[longs['pnl'] < 0]) > 0 else 0
    metrics['largest_loss_short'] = abs(shorts[shorts['pnl'] < 0]['pnl'].min()) if len(shorts[shorts['pnl'] < 0]) > 0 else 0

    # Largest Win as % of Gross Profit
    metrics['largest_win_of_gross_all'] = (
        metrics['largest_win_all'] / metrics['gross_profit_all'] * 100
        if metrics['gross_profit_all'] > 0 else 0
    )
    metrics['largest_win_of_gross_long'] = (
        metrics['largest_win_long'] / metrics['gross_profit_long'] * 100
        if metrics['gross_profit_long'] > 0 else 0
    )
    metrics['largest_win_of_gross_short'] = (
        metrics['largest_win_short'] / metrics['gross_profit_short'] * 100
        if metrics['gross_profit_short'] > 0 else 0
    )

    # Largest Loss as % of Gross Loss
    metrics['largest_loss_of_gross_all'] = (
        metrics['largest_loss_all'] / metrics['gross_loss_all'] * 100
        if metrics['gross_loss_all'] > 0 else 0
    )
    metrics['largest_loss_of_gross_long'] = (
        metrics['largest_loss_long'] / metrics['gross_loss_long'] * 100
        if metrics['gross_loss_long'] > 0 else 0
    )
    metrics['largest_loss_of_gross_short'] = (
        metrics['largest_loss_short'] / metrics['gross_loss_short'] * 100
        if metrics['gross_loss_short'] > 0 else 0
    )

    # Expectancy (same as avg trade pnl)
    metrics['expectancy_all'] = metrics['avg_trade_pnl_all']
    metrics['expectancy_long'] = metrics['avg_trade_pnl_long']
    metrics['expectancy_short'] = metrics['avg_trade_pnl_short']

    # MFE/MAE Statistics
    metrics['avg_mfe_all'] = exits['mfe'].mean()
    metrics['avg_mae_all'] = exits['mae'].mean()
    metrics['max_mfe_all'] = exits['mfe'].max()
    metrics['max_mae_all'] = exits['mae'].max()

    return metrics


def compare_metrics(calculated: dict[str, float], golden: TradingViewGoldenReference) -> list[dict]:
    """Сравнить рассчитанные метрики с золотым эталоном."""
    results = []

    # Сопоставление имён метрик - ПОЛНЫЙ СПИСОК с Long/Short
    comparisons = [
        # ===== TRADE COUNTS =====
        ('total_trades_all', golden.total_trades_all, 'Всего сделок', 0),
        ('total_trades_long', golden.total_trades_long, 'Всего сделок Long', 0),
        ('total_trades_short', golden.total_trades_short, 'Всего сделок Short', 0),

        # ===== WIN/LOSS COUNTS =====
        ('winning_trades_all', golden.winning_trades_all, 'Прибыльных сделок', 0),
        ('winning_trades_long', golden.winning_trades_long, 'Прибыльных Long', 0),
        ('winning_trades_short', golden.winning_trades_short, 'Прибыльных Short', 0),
        ('losing_trades_all', golden.losing_trades_all, 'Убыточных сделок', 0),
        ('losing_trades_long', golden.losing_trades_long, 'Убыточных Long', 0),
        ('losing_trades_short', golden.losing_trades_short, 'Убыточных Short', 0),

        # ===== NET PROFIT =====
        ('net_profit_all', golden.net_profit_all, 'Чистая прибыль', 0.1),
        ('net_profit_long', golden.net_profit_long, 'Чистая прибыль Long', 0.1),
        ('net_profit_short', golden.net_profit_short, 'Чистая прибыль Short', 0.1),

        # ===== GROSS PROFIT/LOSS =====
        ('gross_profit_all', golden.gross_profit_all, 'Валовая прибыль', 0.1),
        ('gross_profit_long', golden.gross_profit_long, 'Валовая прибыль Long', 0.1),
        ('gross_profit_short', golden.gross_profit_short, 'Валовая прибыль Short', 0.1),
        ('gross_loss_all', golden.gross_loss_all, 'Валовый убыток', 0.1),
        ('gross_loss_long', golden.gross_loss_long, 'Валовый убыток Long', 0.1),
        ('gross_loss_short', golden.gross_loss_short, 'Валовый убыток Short', 0.1),

        # ===== PROFIT FACTOR =====
        ('profit_factor_all', golden.profit_factor_all, 'Фактор прибыли', 0.01),
        ('profit_factor_long', golden.profit_factor_long, 'Фактор прибыли Long', 0.01),
        ('profit_factor_short', golden.profit_factor_short, 'Фактор прибыли Short', 0.01),

        # ===== WIN RATE =====
        ('win_rate_all', golden.win_rate_all, 'Win Rate', 0.5),
        ('win_rate_long', golden.win_rate_long, 'Win Rate Long', 0.5),
        ('win_rate_short', golden.win_rate_short, 'Win Rate Short', 0.5),

        # ===== AVERAGE TRADE P&L =====
        ('avg_trade_pnl_all', golden.avg_trade_pnl_all, 'Средний ПР/УБ', 0.05),
        ('avg_trade_pnl_long', golden.avg_trade_pnl_long, 'Средний ПР/УБ Long', 0.05),
        ('avg_trade_pnl_short', golden.avg_trade_pnl_short, 'Средний ПР/УБ Short', 0.05),

        # ===== AVERAGE WIN =====
        ('avg_win_all', golden.avg_win_all, 'Средняя прибыль', 0.05),
        ('avg_win_long', golden.avg_win_long, 'Средняя прибыль Long', 0.05),
        ('avg_win_short', golden.avg_win_short, 'Средняя прибыль Short', 0.05),

        # ===== AVERAGE LOSS =====
        ('avg_loss_all', golden.avg_loss_all, 'Средний убыток', 0.05),
        ('avg_loss_long', golden.avg_loss_long, 'Средний убыток Long', 0.05),
        ('avg_loss_short', golden.avg_loss_short, 'Средний убыток Short', 0.05),

        # ===== PAYOFF RATIO =====
        ('payoff_ratio_all', golden.payoff_ratio_all, 'Payoff Ratio', 0.01),
        ('payoff_ratio_long', golden.payoff_ratio_long, 'Payoff Ratio Long', 0.01),
        ('payoff_ratio_short', golden.payoff_ratio_short, 'Payoff Ratio Short', 0.01),

        # ===== LARGEST WIN =====
        ('largest_win_all', golden.largest_win_all, 'Макс. прибыль', 0.01),
        ('largest_win_long', golden.largest_win_long, 'Макс. прибыль Long', 0.01),
        ('largest_win_short', golden.largest_win_short, 'Макс. прибыль Short', 0.01),

        # ===== LARGEST LOSS =====
        ('largest_loss_all', golden.largest_loss_all, 'Макс. убыток', 0.01),
        ('largest_loss_long', golden.largest_loss_long, 'Макс. убыток Long', 0.01),
        ('largest_loss_short', golden.largest_loss_short, 'Макс. убыток Short', 0.01),

        # ===== LARGEST WIN % OF GROSS =====
        ('largest_win_of_gross_all', golden.largest_win_of_gross_all, 'Макс. в % от валовой', 0.1),
        ('largest_win_of_gross_long', golden.largest_win_of_gross_long, 'Макс. в % Long', 0.1),
        ('largest_win_of_gross_short', golden.largest_win_of_gross_short, 'Макс. в % Short', 0.1),

        # ===== LARGEST LOSS % OF GROSS =====
        ('largest_loss_of_gross_all', golden.largest_loss_of_gross_all, 'Макс. убыток % от валовой', 0.1),
        ('largest_loss_of_gross_long', golden.largest_loss_of_gross_long, 'Макс. убыток % Long', 0.1),
        ('largest_loss_of_gross_short', golden.largest_loss_of_gross_short, 'Макс. убыток % Short', 0.1),

        # ===== EXPECTANCY =====
        ('expectancy_all', golden.expectancy_all, 'Ожидаемая прибыль', 0.05),
        ('expectancy_long', golden.expectancy_long, 'Ожидаемая прибыль Long', 0.05),
        ('expectancy_short', golden.expectancy_short, 'Ожидаемая прибыль Short', 0.05),
    ]

    for metric_key, expected, name_ru, tolerance in comparisons:
        actual = calculated.get(metric_key)
        if actual is None:
            results.append({
                'metric': metric_key,
                'name_ru': name_ru,
                'expected': expected,
                'actual': None,
                'diff': None,
                'diff_pct': None,
                'status': '⚠️ MISSING',
                'tolerance': tolerance,
            })
            continue

        diff = actual - expected
        diff_pct = abs(diff / expected * 100) if expected != 0 else (0 if actual == 0 else float('inf'))

        if isinstance(expected, int):
            status = '✅ MATCH' if actual == expected else '❌ MISMATCH'
        else:
            status = '✅ MATCH' if abs(diff) <= tolerance else '❌ MISMATCH'

        results.append({
            'metric': metric_key,
            'name_ru': name_ru,
            'expected': expected,
            'actual': round(actual, 4) if isinstance(actual, float) else actual,
            'diff': round(diff, 4) if isinstance(diff, float) else diff,
            'diff_pct': round(diff_pct, 2),
            'status': status,
            'tolerance': tolerance,
        })

    return results


def print_calibration_report(results: list[dict]):
    """Вывести отчёт о калибровке (компактный вывод до 80 символов)."""
    w = 78
    print("\n" + "=" * w)
    print("📊 ОТЧЁТ КАЛИБРОВКИ МЕТРИК - TradingView Golden Reference")
    print("=" * w)

    total = len(results)
    matched = sum(1 for r in results if "✅" in r["status"])
    mismatched = sum(1 for r in results if "❌" in r["status"])
    missing = sum(1 for r in results if "⚠️" in r["status"])

    print(f"\n📈 Статистика: {matched}/{total} совпадений ({matched/total*100:.1f}%)")
    print(f"   ✅ Совпадают: {matched}   ❌ Расхождения: {mismatched}   ⚠️ Отсутствуют: {missing}")

    print("\n" + "-" * w)
    print(f"{'Метрика':<26} {'Ожид.':>8} {'Факт':>8} {'Δ':>8} {'%':>6} {'Статус':<10}")
    print("-" * w)

    for r in results:
        expected = f"{r['expected']:.2f}" if isinstance(r["expected"], float) else str(r["expected"])
        actual = f"{r['actual']:.2f}" if isinstance(r["actual"], float) else str(r["actual"]) if r["actual"] is not None else "N/A"
        diff = f"{r['diff']:.4f}" if r["diff"] is not None and isinstance(r["diff"], float) else str(r["diff"]) if r["diff"] is not None else "N/A"
        diff_pct = f"{r['diff_pct']:.2f}%" if r["diff_pct"] is not None else "N/A"
        name = r["name_ru"][:26] if len(r["name_ru"]) > 26 else r["name_ru"]
        print(f"{name:<26} {expected:>8} {actual:>8} {diff:>8} {diff_pct:>6} {r['status']:<10}")

    print("-" * w)

    # Подробности о расхождениях
    if mismatched > 0:
        print("\n⚠️ ДЕТАЛИ РАСХОЖДЕНИЙ:")
        for r in results:
            if '❌' in r['status']:
                print(f"   • {r['name_ru']}: ожидаемо {r['expected']}, получено {r['actual']} (Δ = {r['diff']}, tolerance = {r['tolerance']})")


def main():
    """Главная функция калибровки."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("TradingView 166-Metrics Calibration Script")
    print("=" * 60)

    # Пути к файлам (TV_DATA_DIR env или d:/TV)
    import os
    tv_data_dir = Path(os.environ.get("TV_DATA_DIR", "d:/TV"))
    trades_file = tv_data_dir / "RSI_Strategy_with_TP_SL_(FIXED)_BYBIT_BTCUSDT.P_2026-01-24.csv"
    ohlc_with_rsi = tv_data_dir / "BYBIT_BTCUSDT.P, 15 (3).csv"
    ohlc_clean = tv_data_dir / "BYBIT_BTCUSDT.P, 15 (4).csv"

    # Проверим файлы
    for f in [trades_file, ohlc_with_rsi, ohlc_clean]:
        if not f.exists():
            print(f"❌ Файл не найден: {f}")
            print("   Задайте TV_DATA_DIR (путь к папке с экспортом TradingView) или поместите файлы в d:/TV")
            return
        print(f"✅ Найден: {f.name}")

    # Загрузим данные
    print("\n📥 Загрузка данных...")
    trades_df = parse_tv_trades_csv(trades_file)
    print(f"   Загружено {len(trades_df)} строк сделок")

    ohlc_df = pd.read_csv(ohlc_with_rsi)
    print(f"   Загружено {len(ohlc_df)} баров OHLC с RSI")

    # Создадим золотой эталон
    golden = TradingViewGoldenReference()
    print("\n📊 Золотой эталон загружен:")
    print(f"   • Всего сделок: {golden.total_trades_all}")
    print(f"   • Чистая прибыль: {golden.net_profit_all} USDT")
    print(f"   • Win Rate: {golden.win_rate_all}%")
    print(f"   • Profit Factor: {golden.profit_factor_all}")

    # Рассчитаем метрики из CSV
    print("\n🔧 Расчёт метрик из экспортированных сделок...")
    calculated = calculate_metrics_from_trades(trades_df, golden)

    # Сравним с эталоном
    print("📐 Сравнение с золотым эталоном...")
    results = compare_metrics(calculated, golden)

    # Выведем отчёт
    print_calibration_report(results)

    print("\n✅ Калибровка завершена!")

    return results


if __name__ == "__main__":
    results = main()
