"""
🔍 ДЕТАЛЬНАЯ ДИАГНОСТИКА РАСХОЖДЕНИЯ
Aggressive Scalper: 50x leverage, 1% SL, 2% TP + Bar Magnifier
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

import numpy as np
import pandas as pd
import sqlite3

print("=" * 80)
print("🔍 ДЕТАЛЬНАЯ ДИАГНОСТИКА Bar Magnifier расхождения")
print("=" * 80)

# Загрузка данных
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")
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

# RSI signals (RSI 14, 30/70)
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(df_1h['close'], period=14)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

# Импорты
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2

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

print(f"\n📊 РЕЗУЛЬТАТЫ:")
print(f"   Fallback: {len(fb_result.trades)} trades, ${fb_result.metrics.net_profit:,.2f}")
print(f"   Numba:    {len(nb_result.trades)} trades, ${nb_result.metrics.net_profit:,.2f}")

# Сравнение trade by trade
print(f"\n📋 ДЕТАЛЬНОЕ СРАВНЕНИЕ:")

fb_trades = fb_result.trades
nb_trades = nb_result.trades

# Найдем первое расхождение
divergence_found = False
for i in range(max(len(fb_trades), len(nb_trades))):
    fb_t = fb_trades[i] if i < len(fb_trades) else None
    nb_t = nb_trades[i] if i < len(nb_trades) else None
    
    if fb_t and nb_t:
        # Сравниваем ключевые поля
        entry_match = abs(fb_t.entry_price - nb_t.entry_price) < 0.01
        exit_match = abs(fb_t.exit_price - nb_t.exit_price) < 0.01
        dir_match = fb_t.direction == nb_t.direction
        
        if not (entry_match and exit_match and dir_match):
            print(f"\n🔴 FIRST DIVERGENCE at trade #{i+1}:")
            print(f"   FB: {fb_t.direction} entry={fb_t.entry_price:.2f} exit={fb_t.exit_price:.2f} pnl={fb_t.pnl:.2f} entry_time={fb_t.entry_time}")
            print(f"   NB: {nb_t.direction} entry={nb_t.entry_price:.2f} exit={nb_t.exit_price:.2f} pnl={nb_t.pnl:.2f} entry_time={nb_t.entry_time}")
            divergence_found = True
            
            # Покажем предыдущие trades для контекста
            if i > 0:
                print(f"\n   Previous trade #{i}:")
                fb_prev = fb_trades[i-1]
                nb_prev = nb_trades[i-1]
                print(f"   FB: {fb_prev.direction} entry={fb_prev.entry_price:.2f} exit={fb_prev.exit_price:.2f} pnl={fb_prev.pnl:.4f}")
                print(f"   NB: {nb_prev.direction} entry={nb_prev.entry_price:.2f} exit={nb_prev.exit_price:.2f} pnl={nb_prev.pnl:.4f}")
            break
    elif fb_t is None and nb_t:
        print(f"\n🔴 NUMBA HAS EXTRA TRADE #{i+1}:")
        print(f"   NB: {nb_t.direction} entry={nb_t.entry_price:.2f} exit={nb_t.exit_price:.2f} pnl={nb_t.pnl:.2f} entry_time={nb_t.entry_time}")
        divergence_found = True
        break
    elif nb_t is None and fb_t:
        print(f"\n🔴 FALLBACK HAS EXTRA TRADE #{i+1}:")
        print(f"   FB: {fb_t.direction} entry={fb_t.entry_price:.2f} exit={fb_t.exit_price:.2f} pnl={fb_t.pnl:.2f} entry_time={fb_t.entry_time}")
        divergence_found = True
        break

if not divergence_found:
    print("   ✅ All trades match!")

print("\n" + "=" * 80)
