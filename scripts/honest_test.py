"""
🔬 ЧЕСТНЫЙ ТЕСТ: Реальный бэктест через существующий движок
Используем production код, а не тестовые обёртки
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
import time
from datetime import datetime

import pandas as pd

print("=" * 80)
print("🔬 ЧЕСТНЫЙ ТЕСТ БЭКТЕСТА (Production Code)")
print("=" * 80)
print(f"Время: {datetime.now()}")

# ============================================================================
# 1. Загрузка РЕАЛЬНЫХ данных
# ============================================================================
print("\n📊 Загрузка данных из БД...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

# Проверим сколько данных есть
info = pd.read_sql(
    """
    SELECT symbol, interval, COUNT(*) as cnt,
           MIN(open_time) as min_time, MAX(open_time) as max_time
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT'
    GROUP BY symbol, interval
    ORDER BY cnt DESC
""",
    conn,
)
print("\nДоступные данные BTCUSDT:")
for _, row in info.iterrows():
    start = pd.to_datetime(row["min_time"], unit="ms")
    end = pd.to_datetime(row["max_time"], unit="ms")
    print(f"  {row['interval']:>4}: {row['cnt']:>6} баров ({start.date()} - {end.date()})")

# Загружаем 1h данные
df = pd.read_sql(
    """
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
""",
    conn,
)
conn.close()

df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
df.set_index("open_time", inplace=True)
print(f"\n✅ Загружено {len(df)} часовых баров для BTCUSDT")
print(f"   Период: {df.index.min()} - {df.index.max()}")

# ============================================================================
# 2. Создаём конфигурацию бэктеста
# ============================================================================
print("\n" + "=" * 80)
print("⚙️ КОНФИГУРАЦИЯ БЭКТЕСТА")
print("=" * 80)

from backend.backtesting.models import BacktestConfig

config = BacktestConfig(
    symbol="BTCUSDT",
    interval="60",
    start_date=str(df.index.min().date()),
    end_date=str(df.index.max().date()),
    initial_capital=10000.0,
    leverage=1,
    taker_fee=0.0004,
    slippage=0.0001,
    stop_loss=0.03,  # 3% SL
    take_profit=0.06,  # 6% TP
    direction="both",
    strategy_type="rsi",
    strategy_params={"period": 14, "overbought": 70, "oversold": 30},
    use_bar_magnifier=False,
)

print(f"  Symbol:     {config.symbol}")
print(f"  Interval:   {config.interval}")
print(f"  Period:     {config.start_date} - {config.end_date}")
print(f"  Capital:    ${config.initial_capital:,.0f}")
print(f"  Leverage:   {config.leverage}x")
print(f"  Fee:        {config.taker_fee * 100:.2f}%")
print(f"  Slippage:   {config.slippage * 100:.2f}%")
print(f"  Stop Loss:  {config.stop_loss * 100:.1f}%")
print(f"  Take Profit:{config.take_profit * 100:.1f}%")
print(f"  Direction:  {config.direction}")
print("  Strategy:   RSI(14, 70, 30)")

# ============================================================================
# 3. Запускаем РЕАЛЬНЫЙ бэктест через Fallback Engine
# ============================================================================
print("\n" + "=" * 80)
print("🚀 ЗАПУСК БЭКТЕСТА (Fallback Engine)")
print("=" * 80)

from backend.backtesting.engine import get_engine
from backend.backtesting.strategies import RSIStrategy

engine = get_engine()

# Генерируем сигналы
strategy = RSIStrategy(params={"period": 14, "overbought": 70, "oversold": 30})
signals = strategy.generate_signals(df)

print("\n📊 Сигналы стратегии:")
print(f"   Long entries:  {signals.entries.sum()}")
print(f"   Long exits:    {signals.exits.sum()}")
print(f"   Short entries: {signals.short_entries.sum()}")
print(f"   Short exits:   {signals.short_exits.sum()}")

# Запускаем бэктест
start_time = time.time()
result = engine._run_fallback(config, df, signals)
elapsed = time.time() - start_time

print(f"\n⏱️ Время выполнения: {elapsed:.2f}s")

# ============================================================================
# 4. РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ
# ============================================================================
print("\n" + "=" * 80)
print("📈 РЕЗУЛЬТАТЫ БЭКТЕСТА")
print("=" * 80)

metrics = result.metrics
print("\n💰 Финансовые результаты:")
print(f"   Net Profit:    ${metrics.net_profit:,.2f}")
print(f"   Total Return:  {metrics.total_return:.2f}%")
print(f"   Max Drawdown:  {metrics.max_drawdown:.2f}%")

print("\n📊 Метрики риска:")
print(f"   Sharpe Ratio:  {metrics.sharpe_ratio:.2f}")
print(f"   Profit Factor: {metrics.profit_factor:.2f}")
print(f"   Win Rate:      {metrics.win_rate:.1f}%")

print("\n📉 Статистика сделок:")
print(f"   Total Trades:  {metrics.total_trades}")
print(f"   Long Trades:   {metrics.long_trades}")
print(f"   Short Trades:  {metrics.short_trades}")
print(f"   Avg Win:       ${metrics.avg_win:.2f}")
print(f"   Avg Loss:      ${metrics.avg_loss:.2f}")

# ============================================================================
# 5. Проверка сделок
# ============================================================================
print("\n" + "=" * 80)
print("📋 ДЕТАЛИ СДЕЛОК (первые 10)")
print("=" * 80)

if result.trades:
    for i, trade in enumerate(result.trades[:10]):
        direction = "LONG" if trade.is_long else "SHORT"
        print(
            f"{i + 1:>2}. {direction:>5} | Entry: ${trade.entry_price:,.2f} -> Exit: ${trade.exit_price:,.2f} | "
            f"PnL: ${trade.pnl:>8.2f} | Exit: {trade.exit_reason}"
        )
else:
    print("   ❌ Нет сделок!")

# ============================================================================
# 6. Equity Curve
# ============================================================================
print("\n" + "=" * 80)
print("📊 EQUITY CURVE")
print("=" * 80)

if result.equity_curve:
    equity = result.equity_curve.equity
    print(f"   Start:  ${equity[0]:,.2f}")
    print(f"   End:    ${equity[-1]:,.2f}")
    print(f"   Min:    ${min(equity):,.2f}")
    print(f"   Max:    ${max(equity):,.2f}")
    print(f"   Points: {len(equity)}")

print("\n" + "=" * 80)
print("✅ ТЕСТ ЗАВЕРШЁН - ЭТО РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ ИЗ PRODUCTION КОДА")
print("=" * 80)
