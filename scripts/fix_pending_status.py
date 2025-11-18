"""Fix old backtests with 'pending' status to 'queued'."""
import sys
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///d:/bybit_strategy_tester_v2/demo.db"

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.database import SessionLocal
from backend.models import Backtest

db = SessionLocal()

# Count pending
pending_count = db.query(Backtest).filter(Backtest.status == 'pending').count()
print(f"Found {pending_count} backtests with 'pending' status")

# Update to queued
if pending_count > 0:
    db.query(Backtest).filter(Backtest.status == 'pending').update({'status': 'queued'})
    db.commit()
    print(f"✅ Updated {pending_count} backtests to 'queued' status")
else:
    print("✅ No backtests to update")

db.close()
