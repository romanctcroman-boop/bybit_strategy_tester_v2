"""
📊 ПОКАЗАТЬ ВСЕ 147 МЕТРИК С ИХ ЗНАЧЕНИЯМИ
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sqlite3
from dataclasses import fields

print("=" * 100)
print("📊 ВСЕ 147 МЕТРИК СО ЗНАЧЕНИЯМИ")
print("=" * 100)

# Загрузка данных
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 1000
""", conn)
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df.set_index('open_time', inplace=True)
conn.close()

# RSI function
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(df['close'], period=7)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

from backend.backtesting.interfaces import BacktestInput, TradeDirection, BacktestMetrics
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.core.extended_metrics import ExtendedMetricsCalculator, ExtendedMetricsResult
from backend.core.metrics_calculator import TradeMetrics, RiskMetrics, LongShortMetrics, MetricsCalculator

input_data = BacktestInput(
    candles=df,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    symbol="BTCUSDT",
    interval="60",
    initial_capital=10000,
    position_size=0.15,
    leverage=10,
    stop_loss=0.03,
    take_profit=0.05,
    direction=TradeDirection.BOTH,
    taker_fee=0.001,
    slippage=0.0005,
)

result = FallbackEngineV2().run(input_data)
print(f"\n📈 Trades: {len(result.trades)}, Net Profit: ${result.metrics.net_profit:,.2f}")

if len(result.trades) == 0:
    print("❌ Нет сделок для анализа!")
    sys.exit(1)

# Все метрики
ext_calc = ExtendedMetricsCalculator()
ext_metrics = ext_calc.calculate_all(result.equity_curve, result.trades)

metrics_calc = MetricsCalculator()
trade_metrics = metrics_calc.calculate_trade_metrics(result.trades, result.equity_curve, 10000)
risk_metrics = metrics_calc.calculate_risk_metrics(result.trades, result.equity_curve, 10000)
long_short = metrics_calc.calculate_long_short_metrics(result.trades)

# Подсчёт
all_values = {}
non_zero = 0
total = 0

# === BacktestMetrics ===
print(f"\n{'='*60}")
print(f"📂 BacktestMetrics (32 метрик)")
print(f"{'='*60}")
for f in fields(BacktestMetrics):
    if not f.name.startswith('_'):
        v = getattr(result.metrics, f.name)
        total += 1
        if v is not None and (isinstance(v, (int, np.integer)) or abs(float(v)) > 1e-10):
            non_zero += 1
            all_values[f"backtest.{f.name}"] = v
            if isinstance(v, (int, np.integer)):
                print(f"   ✅ {f.name}: {v}")
            else:
                print(f"   ✅ {f.name}: {v:.6f}")
        else:
            print(f"   ⚪ {f.name}: 0 or None")

# === ExtendedMetrics ===
print(f"\n{'='*60}")
print(f"📂 ExtendedMetrics (14 метрик)")
print(f"{'='*60}")
for f in fields(ExtendedMetricsResult):
    if not f.name.startswith('_'):
        v = getattr(ext_metrics, f.name)
        total += 1
        if v is not None and abs(float(v)) > 1e-10:
            non_zero += 1
            all_values[f"extended.{f.name}"] = v
            print(f"   ✅ {f.name}: {v:.6f}")
        else:
            print(f"   ⚪ {f.name}: 0 or None")

# === TradeMetrics ===
print(f"\n{'='*60}")
print(f"📂 TradeMetrics (26 метрик)")
print(f"{'='*60}")
for f in fields(TradeMetrics):
    if not f.name.startswith('_'):
        v = getattr(trade_metrics, f.name, None)
        total += 1
        if v is not None and (isinstance(v, (int, np.integer)) or abs(float(v)) > 1e-10):
            non_zero += 1
            all_values[f"trade.{f.name}"] = v
            if isinstance(v, (int, np.integer)):
                print(f"   ✅ {f.name}: {v}")
            else:
                print(f"   ✅ {f.name}: {v:.6f}")
        else:
            print(f"   ⚪ {f.name}: 0 or None")

# === RiskMetrics ===
print(f"\n{'='*60}")
print(f"📂 RiskMetrics (21 метрик)")
print(f"{'='*60}")
for f in fields(RiskMetrics):
    if not f.name.startswith('_'):
        v = getattr(risk_metrics, f.name, None)
        total += 1
        if v is not None and (isinstance(v, (int, np.integer)) or abs(float(v)) > 1e-10):
            non_zero += 1
            all_values[f"risk.{f.name}"] = v
            if isinstance(v, (int, np.integer)):
                print(f"   ✅ {f.name}: {v}")
            else:
                print(f"   ✅ {f.name}: {v:.6f}")
        else:
            print(f"   ⚪ {f.name}: 0 or None")

# === LongShortMetrics ===
print(f"\n{'='*60}")
print(f"📂 LongShortMetrics (54 метрик)")
print(f"{'='*60}")
for f in fields(LongShortMetrics):
    if not f.name.startswith('_'):
        v = getattr(long_short, f.name, None)
        total += 1
        if v is not None and (isinstance(v, (int, np.integer)) or abs(float(v)) > 1e-10):
            non_zero += 1
            all_values[f"longshort.{f.name}"] = v
            if isinstance(v, (int, np.integer)):
                print(f"   ✅ {f.name}: {v}")
            else:
                print(f"   ✅ {f.name}: {v:.6f}")
        else:
            print(f"   ⚪ {f.name}: 0 or None")

# === ИТОГО ===
print(f"\n{'='*100}")
print(f"📊 ФИНАЛЬНЫЙ ИТОГ")
print(f"{'='*100}")
print(f"   Всего метрик проверено:   {total}")
print(f"   Ненулевых значений:       {non_zero} ({non_zero/total*100:.1f}%)")
print(f"   Нулевых/None:             {total - non_zero}")

if non_zero >= 120:
    print(f"\n   🎉 БОЛЕЕ 120 МЕТРИК ИМЕЮТ РЕАЛЬНЫЕ НЕНУЛЕВЫЕ ЗНАЧЕНИЯ!")
print("=" * 100)
