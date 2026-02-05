"""Test DCA with real OHLC data and V3 engine via selector."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from backend.backtesting.engine_selector import get_engine
from backend.backtesting.interfaces import BacktestInput, TradeDirection

# Load real OHLC data
ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True).dt.tz_localize(None)

# Use a subset (last 1000 bars)
candles = ohlc.tail(1000).reset_index(drop=True)
n = len(candles)
print(f"Data: {n} bars from {candles['timestamp'].iloc[0]} to {candles['timestamp'].iloc[-1]}")
print(f"Price range: ${candles['low'].min():.0f} - ${candles['high'].max():.0f}")

# Simple DCA entry signals: every 50 bars (20 potential entries)
long_entries = np.zeros(n, dtype=bool)
for i in range(0, n, 50):
    long_entries[i] = True

# Exit: every 100 bars OR when 5 entries accumulated
long_exits = np.zeros(n, dtype=bool)

# No short trades for this test
short_entries = np.zeros(n, dtype=bool)
short_exits = np.zeros(n, dtype=bool)

print(f"\nSignals: {sum(long_entries)} long entries every 50 bars")

# Test with pyramiding=4 (up to 4 concurrent positions)
for pyramiding in [1, 4]:
    print(f"\n{'='*60}")
    print(f"Testing with pyramiding={pyramiding}")
    print(f"{'='*60}")

    engine = get_engine(engine_type='auto', pyramiding=pyramiding)
    print(f"Engine: {engine.name}")

    input_data = BacktestInput(
        candles=candles,
        candles_1m=None,
        initial_capital=100000.0,
        use_fixed_amount=True,
        fixed_amount=1000.0,
        leverage=10,
        take_profit=0.02,  # 2% TP
        stop_loss=0.03,    # 3% SL
        taker_fee=0.0007,
        direction=TradeDirection.LONG,
        long_entries=long_entries,
        short_entries=short_entries,
        pyramiding=pyramiding,
        use_bar_magnifier=False,
    )

    result = engine.run(input_data)

    print("\nResults:")
    print(f"  Trades: {len(result.trades)}")
    print(f"  Net Profit: ${result.metrics.net_profit:.2f}")
    print(f"  Win Rate: {result.metrics.win_rate*100:.1f}%")

    if result.trades:
        print("\nFirst 3 trades:")
        for i, t in enumerate(result.trades[:3]):
            print(f"  #{i+1}: {t.direction} entry=${t.entry_price:.2f} exit=${t.exit_price:.2f} pnl=${t.pnl:.2f}")

print("\n✅ DCA Test with real data completed!")
