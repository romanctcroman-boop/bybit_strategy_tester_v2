# -*- coding: utf-8 -*-
"""
📥 Download 15m OHLC Data from Bybit API

Downloads BTCUSDT.P 15-minute candles for the calibration period.
Period: Oct 1, 2025 - Jan 24, 2026

Created: 2026-01-24
"""

import requests
import pandas as pd
import time
from datetime import datetime, timezone
from pathlib import Path

# Bybit API endpoint
BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"

# Parameters
SYMBOL = "BTCUSDT"
CATEGORY = "linear"  # Perpetual futures
INTERVAL = "15"  # 15 minutes

# Date range
START_DATE = datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
END_DATE = datetime(2026, 1, 24, 23, 59, 59, tzinfo=timezone.utc)

# Output
OUTPUT_DIR = Path("d:/TV")
OUTPUT_FILE = OUTPUT_DIR / "BYBIT_BTCUSDT.P_15m_full.csv"


def fetch_klines(start_ms: int, end_ms: int, limit: int = 1000) -> list:
    """Fetch klines from Bybit API."""
    params = {
        "category": CATEGORY,
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "start": start_ms,
        "end": end_ms,
        "limit": limit,
    }
    
    response = requests.get(BYBIT_KLINE_URL, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    if data.get("retCode") != 0:
        raise Exception(f"API Error: {data.get('retMsg')}")
    
    return data.get("result", {}).get("list", [])


def download_full_period():
    """Download all 15m candles for the period."""
    print(f"📥 Downloading 15m OHLC from Bybit API")
    print(f"   Symbol: {SYMBOL}")
    print(f"   Period: {START_DATE.date()} to {END_DATE.date()}")
    print(f"   Interval: {INTERVAL}m")
    print()
    
    start_ms = int(START_DATE.timestamp() * 1000)
    end_ms = int(END_DATE.timestamp() * 1000)
    
    all_candles = []
    current_end = end_ms
    
    batch = 0
    while current_end > start_ms:
        batch += 1
        print(f"   Batch {batch}: fetching up to {datetime.fromtimestamp(current_end/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')}...", end=" ")
        
        try:
            klines = fetch_klines(start_ms, current_end)
            
            if not klines:
                print("no data")
                break
            
            print(f"{len(klines)} candles")
            all_candles.extend(klines)
            
            # Bybit returns newest first, so find oldest and continue from there
            oldest_ts = min(int(k[0]) for k in klines)
            current_end = oldest_ts - 1
            
            # Rate limiting
            time.sleep(0.2)
            
        except Exception as e:
            print(f"Error: {e}")
            break
    
    if not all_candles:
        print("\n❌ No data downloaded!")
        return None
    
    # Convert to DataFrame
    # Bybit format: [timestamp, open, high, low, close, volume, turnover]
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
    
    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms', utc=True)
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = pd.to_numeric(df[col])
    
    # Sort by time (oldest first)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['timestamp'], keep='first')
    
    # Filter to exact date range
    df = df[(df['timestamp'] >= START_DATE) & (df['timestamp'] <= END_DATE)]
    
    print(f"\n📊 Downloaded {len(df)} candles")
    print(f"   First: {df.iloc[0]['timestamp']}")
    print(f"   Last: {df.iloc[-1]['timestamp']}")
    
    # Save
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Saved to {OUTPUT_FILE}")
    
    return df


if __name__ == "__main__":
    download_full_period()
