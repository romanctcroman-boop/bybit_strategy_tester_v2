# -*- coding: utf-8 -*-
"""Compare individual trades between V2 and V3."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import numpy as np

# Load data
ohlc_file = Path('d:/TV/BYBIT_BTCUSDT.P_15m_full.csv')
ohlc = pd.read_csv(ohlc_file)
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp'], utc=True)
ohlc['timestamp'] = ohlc['timestamp'].dt.tz_localize(None)
print(f"OHLC: {len(ohlc)} bars")

# Load signals
long_signals = np.load('d:/TV/long_signals.npy')
short_signals = np.load('d:/TV/short_signals.npy')
print(f"Signals: {long_signals.sum()} long, {short_signals.sum()} short")

# Config
from backend.backtesting.interfaces import BacktestInput, TradeDirection

config = {
    'initial_capital': 1_000_000.0,
    'fixed_amount': 100.0,
    'leverage': 10,
    'take_profit': 0.015,
    'stop_loss': 0.03,
    'commission': 0.0007,
}

candles = ohlc.reset_index(drop=True)

input_data = BacktestInput(
    candles=candles,
    candles_1m=None,
    initial_capital=config['initial_capital'],
    use_fixed_amount=True,
    fixed_amount=config['fixed_amount'],
    leverage=config['leverage'],
    take_profit=config['take_profit'],
    stop_loss=config['stop_loss'],
    taker_fee=config['commission'],
    direction=TradeDirection.BOTH,
    long_entries=long_signals,
    short_entries=short_signals,
    use_bar_magnifier=False,
)

# Run V2
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
v2 = FallbackEngineV2()
r2 = v2.run(input_data)
print(f"\nV2: {len(r2.trades)} trades, Net Profit: {r2.metrics.net_profit:.2f}")

# Run V3
from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
v3 = FallbackEngineV3()
r3 = v3.run(input_data)
print(f"V3: {len(r3.trades)} trades, Net Profit: {r3.metrics.net_profit:.2f}")

# Compare trades
print("\n" + "="*80)
print("TRADE-BY-TRADE COMPARISON")
print("="*80)

# Match trades by index
min_trades = min(len(r2.trades), len(r3.trades))
diff_count = 0

for i in range(min_trades):
    t2 = r2.trades[i]
    t3 = r3.trades[i]
    
    pnl_diff = t3.pnl - t2.pnl
    if abs(pnl_diff) > 0.01:
        diff_count += 1
        print(f"\nTrade {i+1}: {t2.direction}")
        print(f"  V2: entry={t2.entry_price:.2f}, exit={t2.exit_price:.2f}, pnl={t2.pnl:.2f}, fees={t2.fees:.2f}")
        print(f"  V3: entry={t3.entry_price:.2f}, exit={t3.exit_price:.2f}, pnl={t3.pnl:.2f}, fees={t3.fees:.2f}")
        print(f"  Δ PnL: {pnl_diff:.4f}")

print(f"\n\nTotal trades with differences: {diff_count}/{min_trades}")
print(f"Total PnL difference: {r3.metrics.net_profit - r2.metrics.net_profit:.2f}")
