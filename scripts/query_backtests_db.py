from backend.database import SessionLocal
from backend.database.models.backtest import Backtest

session = SessionLocal()
try:
    rows = session.query(Backtest).all()
    print(f"Found {len(rows)} backtests in DB")
    for b in rows:
        trades_len = len(b.trades) if b.trades else 0
        print(
            f"id={b.id}, status={b.status}, trades_len={trades_len}, net_profit={b.net_profit}"
        )
finally:
    session.close()
