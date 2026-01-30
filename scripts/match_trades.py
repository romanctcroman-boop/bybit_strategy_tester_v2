# -*- coding: utf-8 -*-
"""Match trades between V2 and V3 by exit_price/exit_time."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import numpy as np

# Load data
ohlc = pd.read_csv('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True).dt.tz_localize(None)
long_signals = np.load('d:/TV/long_signals.npy')
short_signals = np.load('d:/TV/short_signals.npy')

from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3

candles = ohlc.reset_index(drop=True)
input_data = BacktestInput(
    candles=candles, candles_1m=None, initial_capital=1_000_000.0,
    use_fixed_amount=True, fixed_amount=100.0, leverage=10,
    take_profit=0.015, stop_loss=0.03, taker_fee=0.0007,
    direction=TradeDirection.BOTH,
    long_entries=long_signals, short_entries=short_signals,
    use_bar_magnifier=False,
)

v2 = FallbackEngineV2()
r2 = v2.run(input_data)
v3 = FallbackEngineV3()
r3 = v3.run(input_data)

print(f"V2: {len(r2.trades)} trades, Net Profit: {r2.metrics.net_profit:.2f}")
print(f"V3: {len(r3.trades)} trades, Net Profit: {r3.metrics.net_profit:.2f}")
print()

# Match trades by exit_time (most reliable)
mismatches = []
for i, t2 in enumerate(r2.trades):
    # Find matching V3 trade by exit_time
    found = False
    for j, t3 in enumerate(r3.trades):
        if t2.exit_time == t3.exit_time and t2.direction == t3.direction:
            found = True
            if abs(t2.entry_price - t3.entry_price) > 0.01:
                mismatches.append({
                    'v2_idx': i+1, 'v3_idx': j+1,
                    'direction': t2.direction,
                    'v2_entry': t2.entry_price, 'v3_entry': t3.entry_price,
                    'v2_exit': t2.exit_price, 'v3_exit': t3.exit_price,
                    'v2_pnl': t2.pnl, 'v3_pnl': t3.pnl,
                    'exit_time': t2.exit_time,
                })
            break
    if not found:
        mismatches.append({
            'v2_idx': i+1, 'v3_idx': 'NOT FOUND',
            'direction': t2.direction,
            'v2_entry': t2.entry_price, 'v3_entry': None,
            'exit_time': t2.exit_time,
        })

print(f"Mismatches found: {len(mismatches)}")
for m in mismatches[:10]:
    print(f"\nV2 Trade {m['v2_idx']} vs V3 Trade {m.get('v3_idx')}:")
    print(f"  Direction: {m['direction']}")
    print(f"  V2 entry: {m['v2_entry']:.2f}" if m['v2_entry'] else "  V2 entry: None")
    print(f"  V3 entry: {m['v3_entry']:.2f}" if m.get('v3_entry') else "  V3 entry: None")
    if m.get('v2_pnl') is not None:
        print(f"  V2 PnL: {m['v2_pnl']:.2f}, V3 PnL: {m['v3_pnl']:.2f}")
        print(f"  Δ PnL: {m['v3_pnl'] - m['v2_pnl']:.2f}")
