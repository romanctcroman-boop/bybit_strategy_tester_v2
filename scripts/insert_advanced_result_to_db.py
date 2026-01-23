import json
from datetime import datetime

from backend.database import SessionLocal
from backend.database.models.backtest import Backtest, BacktestStatus

# Load the saved advanced result
with open("advanced_result.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Build Backtest model fields
# Note: this script is minimal and maps commonly used fields only
bt = Backtest()
bt.id = data.get("id") or None
bt.status = BacktestStatus.COMPLETED
bt.symbol = data.get("config", {}).get("symbol", "BTCUSDT")
bt.timeframe = data.get("config", {}).get("interval", "1h")
# Required fields: strategy_type is NOT NULL in DB schema
bt.strategy_type = data.get("config", {}).get("strategy_type") or "advanced"
bt.strategy_id = data.get("config", {}).get("strategy_id")

# start_date/end_date may be in config (ISO strings) - fallback to now
start = data.get("config", {}).get("start_date")
end = data.get("config", {}).get("end_date")
try:
    bt.start_date = (
        datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None
    )
    bt.end_date = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else None
except Exception:
    bt.start_date = None
    bt.end_date = None

bt.initial_capital = data.get("config", {}).get("initial_capital", 10000.0)
bt.parameters = data.get("config", {}).get("strategy_params", {})

# Metrics
perf = data.get("performance", {})
bt.final_capital = perf.get("final_capital") or perf.get("final_equity")
bt.total_return = perf.get("total_return")
bt.net_profit = perf.get("net_profit")
bt.gross_profit = perf.get("gross_profit")
bt.gross_loss = perf.get("gross_loss")
bt.sharpe_ratio = perf.get("sharpe_ratio")
bt.sortino_ratio = perf.get("sortino_ratio")
bt.max_drawdown = perf.get("max_drawdown")
bt.profit_factor = perf.get("profit_factor")

# Trades and equity curve
bt.trades = data.get("all_trades") or data.get("trades") or []
bt.equity_curve = data.get("equity_curve")

# Timestamps
created_at = data.get("created_at")
completed_at = data.get("completed_at")
try:
    bt.created_at = (
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if created_at
        else None
    )
    bt.completed_at = (
        datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        if completed_at
        else None
    )
except Exception:
    pass

# Ensure required date fields are set (DB schema may require start_date/end_date)
if not getattr(bt, "start_date", None):
    bt.start_date = bt.created_at or datetime.utcnow()
if not getattr(bt, "end_date", None):
    bt.end_date = bt.completed_at or bt.start_date

# Insert into DB
session = SessionLocal()
try:
    # If id exists and record present, update; otherwise insert
    if bt.id:
        existing = session.query(Backtest).get(bt.id)
        if existing:
            print("Updating existing backtest", bt.id)
            for k, v in bt.__dict__.items():
                if k.startswith("_"):
                    continue
                setattr(existing, k, v)
            session.add(existing)
        else:
            print("Inserting new backtest", bt.id)
            session.add(bt)
    else:
        session.add(bt)
    session.commit()
    print("Saved backtest to DB")
finally:
    session.close()
