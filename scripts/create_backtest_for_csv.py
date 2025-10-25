"""Quick script to create backtest for CSV import."""

import sys
import os
import json

os.environ["DATABASE_URL"] = "sqlite:///d:/bybit_strategy_tester_v2/demo.db"

from pathlib import Path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.services.data_service import DataService

# Create backtest for real CSV import
with DataService() as ds:
    # Create strategy with JSON config
    strategy = ds.create_strategy(
        name=f"BTCUSDT Trailing {os.getpid()}",
        description="Long Trail Strategy from CSV",
        config={"trail_percent": 2.0},  # Already a dict
        strategy_type="Long_Trail",
    )
    
    backtest = ds.create_backtest(
        strategy_id=strategy.id,
        symbol="BTCUSDT",
        timeframe="5m",
        start_date="2025-07-01T00:00:00Z",
        end_date="2025-07-31T23:59:59Z",
        initial_capital=10000.0,
        config={"trail_pct": 2.0},  # Already a dict
    )
    
    print(f"✅ Created backtest #{backtest.id} for strategy #{strategy.id}")
    print(f"\nNext step:")
    print(f'  python scripts/import_real_trades.py {backtest.id} "d:/PERP/Список сделок.csv"')
