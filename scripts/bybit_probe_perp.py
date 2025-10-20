"""Probe Bybit v5 for linear perpetual instruments and fetch a small kline sample.

Usage (PowerShell):
$env:BYBIT_API_KEY='...'; $env:BYBIT_API_SECRET='...'; D:/bybit_strategy_tester_v2/.venv/Scripts/python.exe scripts/bybit_probe_perp.py

This script prints a short summary (first 5 instruments found) and a kline sample for the selected symbol.
"""
import os
import sys
import time
import requests
import json

BASE = os.environ.get('BYBIT_BASE_URL', 'https://api.bybit.com')
TIMEOUT = 10


def fetch_instruments(category='linear'):
    url = f"{BASE}/v5/market/instruments-info"
    params = {'category': category}
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_kline(symbol, interval='1m', limit=5):
    # normalize interval for Bybit v5: '1m' -> '1', '1h' -> '60'
    itv = str(interval)
    if itv.endswith('m'):
        itv = itv[:-1]
    elif itv.endswith('h'):
        itv = str(int(itv[:-1]) * 60)
    elif itv.endswith('d'):
        itv = 'D'
    url = f"{BASE}/v5/market/kline"
    params = {'category': 'linear', 'symbol': symbol, 'interval': itv, 'limit': limit}
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def main():
    print('Bybit probe starting — base URL:', BASE)
    try:
        info = fetch_instruments('linear')
    except Exception as e:
        print('instruments-info failed:', e)
        sys.exit(1)

    # normalize
    result = info.get('result') or {}
    instruments = []
    if isinstance(result, dict):
        instruments = result.get('list') or []
    elif isinstance(result, list):
        instruments = result

    print('discovered_instruments_count=', len(instruments))
    for i, itm in enumerate(instruments[:5]):
        print(f'[{i}]', json.dumps(itm, ensure_ascii=False))

    # choose a symbol to test
    preferred = os.environ.get('BYBIT_SYMBOL')
    if not preferred and instruments:
        preferred = instruments[0].get('symbol') if isinstance(instruments[0], dict) else instruments[0]

    if not preferred:
        print('No symbol selected/found to probe')
        sys.exit(1)

    print('\nProbing klines for symbol=', preferred)

    def try_symbol(sym):
        try:
            k = fetch_kline(sym, interval=os.environ.get('BYBIT_INTERVAL','1m'), limit=5)
            print('kline payload keys:', list(k.keys()))
            res = k.get('result') or k.get('data') or k
            if isinstance(res, dict) and 'list' in res:
                data = res['list']
            elif isinstance(res, list):
                data = res
            else:
                data = []
            print('kline_count=', len(data), 'for', sym)
            if data:
                print('first_kline=', data[0])
                return True
            return False
        except Exception as e:
            print(f'kline fetch failed for {sym}:', e)
            return False

    ok = False
    if preferred:
        ok = try_symbol(preferred)

    # If preferred didn't return data, try a short list of popular perpetual symbols
    # Always test BTCUSDT and ETHUSDT explicitly (user requested)
    for mandatory in ['BTCUSDT', 'ETHUSDT']:
        if preferred and mandatory == preferred:
            continue
        print('Testing mandatory symbol:', mandatory)
        try_symbol(mandatory)

    if not ok:
        # fall back to other popular perpetuals
        popular = ['XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
        for sym in popular:
            if sym == preferred:
                continue
            print('Trying popular symbol:', sym)
            if try_symbol(sym):
                ok = True
                break

    if not ok:
        print('No kline data found for preferred/popular symbols. You can set BYBIT_SYMBOL env to try a specific contract.')


if __name__ == '__main__':
    main()
