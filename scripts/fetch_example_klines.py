"""Example script: fetch recent klines from Bybit and Binance using the adapter layer.

Run with the project venv python to print sample candles.
"""
import os
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')
from backend.services.adapters.bybit import BybitAdapter
from backend.services.adapters.binance import BinanceAdapter

def sample_bybit():
    # Read credentials from environment if provided (safer than embedding them in commands)
    api_key = os.environ.get('BYBIT_API_KEY')
    api_secret = os.environ.get('BYBIT_API_SECRET')
    b = BybitAdapter(api_key=api_key, api_secret=api_secret)
    try:
        # request 1-minute interval last 5 candles
        klines = b.get_klines('BTCUSDT', interval='1', limit=5)
        chosen = getattr(b, 'last_chosen_symbol', None)
        print('Bybit adapter chose symbol:', chosen)
        print('Bybit sample klines (parsed):')
        for k in klines:
            # print human-friendly datetime and numeric fields if available
            dt = k.get('open_time_dt') or None
            openp = k.get('open')
            high = k.get('high')
            low = k.get('low')
            close = k.get('close')
            vol = k.get('volume')
            print(dt, openp, high, low, close, vol)
    except Exception as e:
        print('Bybit fetch failed:', e)

def sample_binance():
    b = BinanceAdapter()
    try:
        klines = b.get_klines('BTCUSDT', interval='1m', limit=5)
        print('Binance sample klines (first):', klines[0])
    except Exception as e:
        print('Binance fetch failed:', e)

if __name__ == '__main__':
    # Print BTC and ETH 1-minute candles for last 5 minutes
    print('\n=== BTCUSDT (1m last 5) ===')
    sample_bybit()
    print('\n=== ETHUSDT (1m last 5) ===')
    # ETH sample
    api_key = os.environ.get('BYBIT_API_KEY')
    api_secret = os.environ.get('BYBIT_API_SECRET')
    b = BybitAdapter(api_key=api_key, api_secret=api_secret)
    try:
        klines = b.get_klines('ETHUSDT', interval='1', limit=5)
        chosen = getattr(b, 'last_chosen_symbol', None)
        print('Bybit adapter chose symbol:', chosen)
        for k in klines:
            print(k.get('open_time_dt'), k.get('open'), k.get('high'), k.get('low'), k.get('close'), k.get('volume'))
    except Exception as e:
        print('Bybit ETH fetch failed:', e)
