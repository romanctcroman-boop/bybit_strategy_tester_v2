"""
🔍 ДИАГНОСТИКА РАЗЛИЧИЯ Bar Magnifier
Aggressive Scalper: 50x leverage, 1% SL, 2% TP
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import pandas as pd

print("=" * 80)
print("🔍 ДИАГНОСТИКА Bar Magnifier - Aggressive Scalper")
print("=" * 80)

# Загрузка данных
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df_1h = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 500
""", conn)
df_1h['open_time'] = pd.to_datetime(df_1h['open_time'], unit='ms')
df_1h.set_index('open_time', inplace=True)

df_1m = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '1'
    ORDER BY open_time ASC
""", conn)
df_1m['open_time'] = pd.to_datetime(df_1m['open_time'], unit='ms')
df_1m.set_index('open_time', inplace=True)
df_1m = df_1m[(df_1m.index >= df_1h.index[0]) & (df_1m.index <= df_1h.index[-1])]
conn.close()

print(f"1H bars: {len(df_1h)}, 1M bars: {len(df_1m)}")

# RSI signals
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(df_1h['close'], period=7)
long_entries = (rsi < 20).values
long_exits = (rsi > 80).values
short_entries = (rsi > 80).values
short_exits = (rsi < 20).values

# Импорты
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection

config = {
    "initial_capital": 5000,
    "position_size": 0.25,
    "stop_loss": 0.01,  # 1%
    "take_profit": 0.02,  # 2%
    "leverage": 50,
    "taker_fee": 0.001,
    "slippage": 0.001,
}

input_data = BacktestInput(
    candles=df_1h,
    candles_1m=df_1m,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    symbol="BTCUSDT",
    interval="60",
    initial_capital=config['initial_capital'],
    position_size=config['position_size'],
    leverage=config['leverage'],
    stop_loss=config['stop_loss'],
    take_profit=config['take_profit'],
    direction=TradeDirection.BOTH,
    taker_fee=config['taker_fee'],
    slippage=config['slippage'],
    use_bar_magnifier=True,
)

# Запуск
fb = FallbackEngineV2()
nb = NumbaEngineV2()

fb_result = fb.run(input_data)
nb_result = nb.run(input_data)

print("\n📊 РЕЗУЛЬТАТЫ:")
print(f"   Fallback: {len(fb_result.trades)} trades, ${fb_result.metrics.net_profit:,.2f}")
print(f"   Numba:    {len(nb_result.trades)} trades, ${nb_result.metrics.net_profit:,.2f}")

# Детальное сравнение
print("\n📋 ДЕТАЛЬНОЕ СРАВНЕНИЕ СДЕЛОК:")
print(f"{'#':<4} {'Dir':<6} {'FB Entry':>10} {'NB Entry':>10} {'FB Exit':>10} {'NB Exit':>10} {'FB PnL':>10} {'NB PnL':>10} {'Match':>6}")
print("-" * 90)

max_trades = max(len(fb_result.trades), len(nb_result.trades))
differences = []

for i in range(min(max_trades, 70)):
    fb_t = fb_result.trades[i] if i < len(fb_result.trades) else None
    nb_t = nb_result.trades[i] if i < len(nb_result.trades) else None

    if fb_t and nb_t:
        fb_entry = fb_t.entry_price
        nb_entry = nb_t.entry_price
        fb_exit = fb_t.exit_price
        nb_exit = nb_t.exit_price
        fb_pnl = fb_t.pnl
        nb_pnl = nb_t.pnl

        entry_match = abs(fb_entry - nb_entry) < 0.01
        exit_match = abs(fb_exit - nb_exit) < 0.01
        pnl_match = abs(fb_pnl - nb_pnl) < 0.01

        match = "✅" if (entry_match and exit_match and pnl_match) else "❌"

        if not (entry_match and exit_match and pnl_match):
            differences.append(i)

        print(f"{i+1:<4} {fb_t.direction:<6} {fb_entry:>10.2f} {nb_entry:>10.2f} {fb_exit:>10.2f} {nb_exit:>10.2f} {fb_pnl:>10.2f} {nb_pnl:>10.2f} {match:>6}")
    elif fb_t:
        print(f"{i+1:<4} {fb_t.direction:<6} {fb_t.entry_price:>10.2f} {'---':>10} {fb_t.exit_price:>10.2f} {'---':>10} {fb_t.pnl:>10.2f} {'---':>10} {'❌':>6}")
        differences.append(i)
    elif nb_t:
        print(f"{i+1:<4} {nb_t.direction:<6} {'---':>10} {nb_t.entry_price:>10.2f} {'---':>10} {nb_t.exit_price:>10.2f} {'---':>10} {nb_t.pnl:>10.2f} {'❌':>6}")
        differences.append(i)

print(f"\n📍 РАСХОЖДЕНИЯ НА СДЕЛКАХ: {differences[:10]}")

# Анализ первого расхождения
if differences:
    idx = differences[0]
    print(f"\n🔍 АНАЛИЗ ПЕРВОГО РАСХОЖДЕНИЯ (сделка #{idx+1}):")

    if idx < len(fb_result.trades):
        fb_t = fb_result.trades[idx]
        print("   Fallback:")
        print(f"      Entry: {fb_t.entry_time} @ ${fb_t.entry_price:.2f}")
        print(f"      Exit:  {fb_t.exit_time} @ ${fb_t.exit_price:.2f}")
        print(f"      PnL:   ${fb_t.pnl:.2f}")
        print(f"      Reason: {fb_t.exit_reason}")

    if idx < len(nb_result.trades):
        nb_t = nb_result.trades[idx]
        print("   Numba:")
        print(f"      Entry: {nb_t.entry_time} @ ${nb_t.entry_price:.2f}")
        print(f"      Exit:  {nb_t.exit_time} @ ${nb_t.exit_price:.2f}")
        print(f"      PnL:   ${nb_t.pnl:.2f}")
        print(f"      Reason: {nb_t.exit_reason}")

print("\n" + "=" * 80)
