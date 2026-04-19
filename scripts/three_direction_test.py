"""
🔬 ТРИ ОТДЕЛЬНЫХ ТЕСТА: LONG, SHORT, LONG&SHORT
Параметры: SL=3.5%, TP=1.5%, RSI(14, 70, 30) - БЕЗ ОПТИМИЗАЦИИ
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
import time
from datetime import datetime

import pandas as pd

print("=" * 100)
print("🔬 ТРИ ТЕСТА: LONG / SHORT / LONG&SHORT")
print("=" * 100)
print(f"Время: {datetime.now()}")
print("\n⚠️ БЕЗ ОПТИМИЗАЦИИ - фиксированные параметры RSI(14, 70, 30)")

# ============================================================================
# БАЗОВЫЕ ПАРАМЕТРЫ (ОДИНАКОВЫЕ ДЛЯ ВСЕХ ТЕСТОВ)
# ============================================================================
BASE_CONFIG = {
    "name": "A07",
    "symbol": "BTCUSDT",
    "interval": "30",
    "initial_capital": 10000.0,
    "position_size": 0.10,  # 10% от капитала
    "stop_loss": 0.035,  # 3.5% SL
    "take_profit": 0.015,  # 1.5% TP
    "commission": 0.001,  # 0.1%
    "slippage": 0.0005,  # 0.05%
    "leverage": 10,
    "strategy_type": "rsi",
    "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
    "start_date": "2025-12-18",
    "end_date": "2026-01-18",
}

print(f"""
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│  ФИКСИРОВАННЫЕ ПАРАМЕТРЫ (БЕЗ ОПТИМИЗАЦИИ)                                                     │
├────────────────────────────┬───────────────────────────────────────────────────────────────────┤
│  Стратегия                 │  RSI(period=14, overbought=70, oversold=30)                      │
│  Stop Loss (SL)            │  3.5%                                                             │
│  Take Profit (TP)          │  1.5%                                                             │
│  Risk/Reward               │  1:0.43 (TP < SL = агрессивный скальпинг)                        │
├────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│  Символ                    │  BTCUSDT                                                          │
│  Таймфрейм                 │  30 минут                                                         │
│  Период                    │  {BASE_CONFIG["start_date"]} - {BASE_CONFIG["end_date"]}                                │
│  Капитал                   │  $10,000                                                          │
│  Плечо                     │  10x                                                              │
│  Размер позиции            │  10%                                                              │
│  Комиссия                  │  0.1%                                                             │
│  Проскальзывание           │  0.05%                                                            │
└────────────────────────────┴───────────────────────────────────────────────────────────────────┘
""")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("=" * 100)
print("📊 ЗАГРУЗКА ДАННЫХ")
print("=" * 100)

conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
start_ts = int(pd.Timestamp(BASE_CONFIG["start_date"]).timestamp() * 1000)
end_ts = int(pd.Timestamp(BASE_CONFIG["end_date"]).timestamp() * 1000)

df = pd.read_sql(
    f"""
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = '{BASE_CONFIG["symbol"]}' AND interval = '{BASE_CONFIG["interval"]}'
    AND open_time >= {start_ts} AND open_time <= {end_ts}
    ORDER BY open_time ASC
""",
    conn,
)
conn.close()

df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
df.set_index("open_time", inplace=True)
print(f"  Загружено {len(df):,} баров ({df.index.min().date()} - {df.index.max().date()})")

# ============================================================================
# ФУНКЦИЯ БЭКТЕСТА
# ============================================================================
from backend.backtesting.engine import get_engine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import RSIStrategy

engine = get_engine()
strategy = RSIStrategy(params=BASE_CONFIG["strategy_params"])
signals = strategy.generate_signals(df)

print("\n📊 Сигналы RSI(14, 70, 30):")
print(f"   Long entries:  {signals.entries.sum()}")
print(f"   Long exits:    {signals.exits.sum()}")
print(f"   Short entries: {signals.short_entries.sum()}")
print(f"   Short exits:   {signals.short_exits.sum()}")


def run_backtest(direction: str) -> dict:
    """Запуск бэктеста с заданным направлением"""
    config = BacktestConfig(
        symbol=BASE_CONFIG["symbol"],
        interval=BASE_CONFIG["interval"],
        start_date=BASE_CONFIG["start_date"],
        end_date=BASE_CONFIG["end_date"],
        initial_capital=BASE_CONFIG["initial_capital"],
        leverage=BASE_CONFIG["leverage"],
        taker_fee=BASE_CONFIG["commission"],
        slippage=BASE_CONFIG["slippage"],
        stop_loss=BASE_CONFIG["stop_loss"],
        take_profit=BASE_CONFIG["take_profit"],
        direction=direction,
        strategy_type=BASE_CONFIG["strategy_type"],
        strategy_params=BASE_CONFIG["strategy_params"],
        position_size=BASE_CONFIG["position_size"],
    )

    start = time.time()
    result = engine._run_fallback(config, df, signals)
    elapsed = time.time() - start

    m = result.metrics
    return {
        "direction": direction.upper(),
        "net_profit": m.net_profit,
        "total_return": m.total_return,
        "max_drawdown": m.max_drawdown,
        "sharpe_ratio": m.sharpe_ratio,
        "profit_factor": m.profit_factor,
        "win_rate": m.win_rate,
        "total_trades": m.total_trades,
        "long_trades": m.long_trades,
        "short_trades": m.short_trades,
        "avg_win": m.avg_win,
        "avg_loss": m.avg_loss,
        "execution_time": elapsed,
        "trades": result.trades,
        "equity": result.equity_curve.equity if result.equity_curve else [],
    }


# ============================================================================
# ТЕСТ 1: LONG ONLY
# ============================================================================
print("\n" + "=" * 100)
print("🟢 ТЕСТ 1: LONG ONLY")
print("=" * 100)

result_long = run_backtest("long")
print(f"""
  Net Profit:     ${result_long["net_profit"]:>10,.2f}
  Total Return:   {result_long["total_return"]:>10.2f}%
  Max Drawdown:   {result_long["max_drawdown"]:>10.2f}%
  Sharpe Ratio:   {result_long["sharpe_ratio"]:>10.2f}
  Profit Factor:  {result_long["profit_factor"]:>10.2f}
  Win Rate:       {result_long["win_rate"]:>10.1f}%
  Total Trades:   {result_long["total_trades"]:>10}
  Avg Win:        ${result_long["avg_win"]:>9.2f}
  Avg Loss:       ${result_long["avg_loss"]:>9.2f}
  Time:           {result_long["execution_time"]:>10.2f}s
""")

# ============================================================================
# ТЕСТ 2: SHORT ONLY
# ============================================================================
print("=" * 100)
print("🔴 ТЕСТ 2: SHORT ONLY")
print("=" * 100)

result_short = run_backtest("short")
print(f"""
  Net Profit:     ${result_short["net_profit"]:>10,.2f}
  Total Return:   {result_short["total_return"]:>10.2f}%
  Max Drawdown:   {result_short["max_drawdown"]:>10.2f}%
  Sharpe Ratio:   {result_short["sharpe_ratio"]:>10.2f}
  Profit Factor:  {result_short["profit_factor"]:>10.2f}
  Win Rate:       {result_short["win_rate"]:>10.1f}%
  Total Trades:   {result_short["total_trades"]:>10}
  Avg Win:        ${result_short["avg_win"]:>9.2f}
  Avg Loss:       ${result_short["avg_loss"]:>9.2f}
  Time:           {result_short["execution_time"]:>10.2f}s
""")

# ============================================================================
# ТЕСТ 3: LONG & SHORT
# ============================================================================
print("=" * 100)
print("🟣 ТЕСТ 3: LONG & SHORT")
print("=" * 100)

result_both = run_backtest("both")
print(f"""
  Net Profit:     ${result_both["net_profit"]:>10,.2f}
  Total Return:   {result_both["total_return"]:>10.2f}%
  Max Drawdown:   {result_both["max_drawdown"]:>10.2f}%
  Sharpe Ratio:   {result_both["sharpe_ratio"]:>10.2f}
  Profit Factor:  {result_both["profit_factor"]:>10.2f}
  Win Rate:       {result_both["win_rate"]:>10.1f}%
  Total Trades:   {result_both["total_trades"]:>10} (Long: {result_both["long_trades"]}, Short: {result_both["short_trades"]})
  Avg Win:        ${result_both["avg_win"]:>9.2f}
  Avg Loss:       ${result_both["avg_loss"]:>9.2f}
  Time:           {result_both["execution_time"]:>10.2f}s
""")

# ============================================================================
# СРАВНИТЕЛЬНАЯ ТАБЛИЦА
# ============================================================================
print("\n" + "=" * 100)
print("📊 СРАВНИТЕЛЬНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
print("=" * 100)

print(f"""
┌─────────────────────┬────────────────┬────────────────┬────────────────┐
│  Метрика            │  🟢 LONG       │  🔴 SHORT      │  🟣 BOTH       │
├─────────────────────┼────────────────┼────────────────┼────────────────┤
│  Net Profit         │ ${result_long["net_profit"]:>11,.2f} │ ${result_short["net_profit"]:>11,.2f} │ ${result_both["net_profit"]:>11,.2f} │
│  Total Return       │ {result_long["total_return"]:>12.2f}% │ {result_short["total_return"]:>12.2f}% │ {result_both["total_return"]:>12.2f}% │
│  Max Drawdown       │ {result_long["max_drawdown"]:>12.2f}% │ {result_short["max_drawdown"]:>12.2f}% │ {result_both["max_drawdown"]:>12.2f}% │
│  Sharpe Ratio       │ {result_long["sharpe_ratio"]:>13.2f} │ {result_short["sharpe_ratio"]:>13.2f} │ {result_both["sharpe_ratio"]:>13.2f} │
│  Profit Factor      │ {result_long["profit_factor"]:>13.2f} │ {result_short["profit_factor"]:>13.2f} │ {result_both["profit_factor"]:>13.2f} │
│  Win Rate           │ {result_long["win_rate"]:>12.1f}% │ {result_short["win_rate"]:>12.1f}% │ {result_both["win_rate"]:>12.1f}% │
│  Total Trades       │ {result_long["total_trades"]:>13} │ {result_short["total_trades"]:>13} │ {result_both["total_trades"]:>13} │
│  Avg Win            │ ${result_long["avg_win"]:>11.2f} │ ${result_short["avg_win"]:>11.2f} │ ${result_both["avg_win"]:>11.2f} │
│  Avg Loss           │ ${result_long["avg_loss"]:>11.2f} │ ${result_short["avg_loss"]:>11.2f} │ ${result_both["avg_loss"]:>11.2f} │
└─────────────────────┴────────────────┴────────────────┴────────────────┘

📈 Equity Changes:
   LONG:  $10,000 → ${result_long["equity"][-1] if result_long["equity"] else 0:,.2f}
   SHORT: $10,000 → ${result_short["equity"][-1] if result_short["equity"] else 0:,.2f}
   BOTH:  $10,000 → ${result_both["equity"][-1] if result_both["equity"] else 0:,.2f}
""")

# Определяем лучший вариант
all_results = [
    ("LONG", result_long["sharpe_ratio"], result_long["net_profit"]),
    ("SHORT", result_short["sharpe_ratio"], result_short["net_profit"]),
    ("BOTH", result_both["sharpe_ratio"], result_both["net_profit"]),
]
best = max(all_results, key=lambda x: x[1])

print("=" * 100)
print(f"🏆 ЛУЧШИЙ РЕЗУЛЬТАТ ПО SHARPE: {best[0]} (Sharpe={best[1]:.2f}, Net Profit=${best[2]:,.2f})")
print("=" * 100)
print("\n⚠️ НАПОМИНАНИЕ: Это тест БЕЗ ОПТИМИЗАЦИИ с фиксированными параметрами RSI(14, 70, 30)")
