"""Import trades from CSV file into existing backtest.

Usage:
    python scripts/import_csv_trades.py <backtest_id> <csv_path>

Example:
    python scripts/import_csv_trades.py 7 "d:/PERP/Список сделок.csv"
"""

import csv
import sys
from datetime import datetime, UTC
import requests

API_BASE = "http://127.0.0.1:8000/api/v1"


def parse_russian_datetime(s: str) -> datetime:
    """Parse Russian format datetime: '23 окт. 2024 г., 03:51:43'"""
    # Remove 'г., ' if present
    s = s.replace(" г., ", " ").replace(" г.,", " ")
    
    # Russian month abbreviations
    months = {
        "янв": "Jan",
        "фев": "Feb",
        "мар": "Mar",
        "апр": "Apr",
        "мая": "May",
        "май": "May",
        "июн": "Jun",
        "июл": "Jul",
        "авг": "Aug",
        "сен": "Sep",
        "окт": "Oct",
        "ноя": "Nov",
        "дек": "Dec",
    }
    
    for ru, en in months.items():
        s = s.replace(ru, en)
    
    # Try common formats
    for fmt in [
        "%d %b %Y %H:%M:%S",
        "%d %b. %Y %H:%M:%S",
        "%d %b %Y, %H:%M:%S",
    ]:
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse datetime: {s}")


def import_trades(backtest_id: int, csv_path: str):
    """Import trades from CSV into backtest."""
    print(f"Reading trades from {csv_path}...")
    
    trades = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        
        for row in reader:
            # Expected columns (adjust based on actual CSV):
            # Время входа, Время выхода, Сторона, Цена входа, Количество, P&L
            try:
                entry_time = parse_russian_datetime(row.get("Время входа", row.get("Entry Time", "")))
                exit_time_str = row.get("Время выхода", row.get("Exit Time", ""))
                exit_time = parse_russian_datetime(exit_time_str) if exit_time_str.strip() else None
                
                side = row.get("Сторона", row.get("Side", "LONG")).strip().upper()
                if side in ("BUY", "ПОКУПКА"):
                    side = "LONG"
                elif side in ("SELL", "ПРОДАЖА"):
                    side = "SHORT"
                
                entry_price = float(row.get("Цена входа", row.get("Entry Price", "0")).replace(",", "."))
                quantity = float(row.get("Количество", row.get("Quantity", "0")).replace(",", "."))
                pnl = float(row.get("P&L", row.get("PnL", "0")).replace(",", "."))
                
                trades.append({
                    "backtest_id": backtest_id,
                    "entry_time": entry_time.isoformat(),
                    "exit_time": exit_time.isoformat() if exit_time else None,
                    "side": side,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "pnl": pnl,
                })
            except Exception as e:
                print(f"Warning: skipping row due to error: {e}")
                print(f"  Row: {row}")
                continue
    
    print(f"Parsed {len(trades)} trades. Uploading to backtest #{backtest_id}...")
    
    # Post trades via API (if endpoint exists)
    # For now, we'll need to use DataService directly or create an endpoint
    # Let's create them via direct DB access
    
    import os
    os.environ["DATABASE_URL"] = "sqlite:///d:/bybit_strategy_tester_v2/demo.db"
    
    from backend.services.data_service import DataService
    
    with DataService() as ds:
        for trade in trades:
            ds.create_trade(**trade)
    
    print(f"✅ Successfully imported {len(trades)} trades into backtest #{backtest_id}")
    print(f"\nView results at: http://localhost:5173/backtests/{backtest_id}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    backtest_id = int(sys.argv[1])
    csv_path = sys.argv[2]
    
    import_trades(backtest_id, csv_path)
