"""
Debug data loading
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

from backend.services.data_service import DataService
from datetime import datetime

SYMBOL = "ETHUSDT"
INTERVAL = "30m"
START_DATE = "2025-01-01T00:00:00+00:00"
END_DATE = "2026-02-27T23:00:00+00:00"

print(f"Loading {SYMBOL} {INTERVAL}...")

with DataService() as ds:
    # Try with '30' instead of '30m'
    eth_data = ds.get_market_data(
        symbol=SYMBOL,
        timeframe="30",  # Try without 'm'
        start_time=START_DATE,
        end_time=END_DATE,
        limit=100000,
    )
    print(f"  ETHUSDT bars (timeframe='30'): {len(eth_data)}")
    
    if len(eth_data) > 0:
        print(f"  First bar: {eth_data[0].open_time_dt} - O={eth_data[0].open_price}")
        print(f"  Last bar: {eth_data[-1].open_time_dt} - C={eth_data[-1].close_price}")
    
    # Also try BTC
    btc_data = ds.get_market_data(
        symbol="BTCUSDT",
        timeframe="30",
        start_time=START_DATE,
        end_time=END_DATE,
        limit=100000,
    )
    print(f"  BTCUSDT bars (timeframe='30'): {len(btc_data)}")
    
    if len(btc_data) > 0:
        print(f"  First bar: {btc_data[0].open_time_dt} - O={btc_data[0].open_price}")
        print(f"  Last bar: {btc_data[-1].open_time_dt} - C={btc_data[-1].close_price}")
