#!/usr/bin/env python3
"""Database Audit Script - Full analysis of market data."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data.sqlite3"

def main():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Database statistics
    cur.execute('SELECT COUNT(*) FROM bybit_kline_audit')
    total = cur.fetchone()[0]
    print(f'=== TOTAL CANDLES: {total:,} ===')
    print()

    # By symbol and interval
    cur.execute('''
        SELECT symbol, interval, market_type, COUNT(*) as cnt,
               datetime(MIN(open_time)/1000, 'unixepoch') as start_dt,
               datetime(MAX(open_time)/1000, 'unixepoch') as end_dt
        FROM bybit_kline_audit
        GROUP BY symbol, interval, market_type
        ORDER BY symbol, interval
    ''')
    
    header = f"{'Symbol':<15} {'TF':<6} {'Type':<8} {'Count':>10} {'Start Date':<20} {'End Date':<20}"
    print(header)
    print('-' * len(header))
    
    for row in cur.fetchall():
        symbol, interval, market_type, cnt, start_dt, end_dt = row
        print(f'{symbol:<15} {interval:<6} {market_type:<8} {cnt:>10,} {start_dt:<20} {end_dt:<20}')
    
    print()
    
    # Check for UNKNOWN intervals
    cur.execute("SELECT COUNT(*) FROM bybit_kline_audit WHERE interval = 'UNKNOWN'")
    unknown_count = cur.fetchone()[0]
    print(f"=== UNKNOWN intervals: {unknown_count} ===")
    
    # Check indexes
    print("\n=== INDEXES ===")
    cur.execute('PRAGMA index_list(bybit_kline_audit)')
    for row in cur.fetchall():
        print(f"  {row}")
    
    # Check WAL mode
    cur.execute('PRAGMA journal_mode')
    journal_mode = cur.fetchone()[0]
    print(f"\n=== Journal Mode: {journal_mode} ===")
    
    # Check market_type distribution
    cur.execute('''
        SELECT market_type, COUNT(*) as cnt
        FROM bybit_kline_audit
        GROUP BY market_type
    ''')
    print("\n=== Market Type Distribution ===")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:,} candles")
    
    conn.close()

if __name__ == "__main__":
    main()
