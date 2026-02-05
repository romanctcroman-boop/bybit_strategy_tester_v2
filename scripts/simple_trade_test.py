"""Simple trade comparison script using sqlite3 directly."""

import json
import sqlite3

# Add project root to path
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategies import get_strategy

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data.sqlite3"


def load_candles_sqlite(
    db_path: str,
    symbol: str,
    interval: str,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame | None:
    """Load candles directly from SQLite using sqlite3."""
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    conn = sqlite3.connect(db_path, timeout=30)
    query = """
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM bybit_kline_audit
        WHERE symbol = ? AND interval = ?
          AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC
    """
    cursor = conn.cursor()
    cursor.execute(query, (symbol, interval, start_ts, end_ts))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print(f"No data found for {symbol}/{interval}")
        return None

    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    print(f"Loaded {len(df)} candles for {symbol}/{interval}")
    return df


def trade_to_dict(t: Any) -> dict[str, Any]:
    try:
        return t.model_dump() if hasattr(t, "model_dump") else t.dict()
    except Exception:
        return t.__dict__ if hasattr(t, "__dict__") else dict(t)


def dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, default=str, indent=2, ensure_ascii=False)


def main() -> int:
    symbol = "BTCUSDT"
    interval = "15"
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 11)

    # Load data directly with sqlite3
    ohlcv = load_candles_sqlite(str(DB_PATH), symbol, interval, start_date, end_date)
    if ohlcv is None:
        print("No candle data found; aborting")
        return 1

    config = BacktestConfig(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        strategy_type="rsi",
        strategy_params={"period": 21, "oversold": 30, "overbought": 70},
        direction="long",  # Use 'long' to test VBT path (bidirectional always uses fallback)
        initial_capital=10000.0,
        leverage=10.0,
        position_size=1.0,
        # force_fallback=True,  # Uncomment for 100% parity
    )

    strategy = get_strategy(config.strategy_type, config.strategy_params)
    signals = strategy.generate_signals(ohlcv)

    engine = BacktestEngine()

    print("Running fallback engine...")
    res_fallback = engine._run_fallback(config, ohlcv, signals)
    print(f"Fallback: {len(res_fallback.trades)} trades")

    print("Running vectorbt engine...")
    try:
        res_vectorbt = engine._run_vectorbt(config, ohlcv, signals)
        print(f"Vectorbt: {len(res_vectorbt.trades)} trades")
        has_vectorbt = True
    except Exception as e:
        print(f"Vectorbt failed: {e}")
        has_vectorbt = False

    fb_trades = [trade_to_dict(t) for t in res_fallback.trades]
    cfg_obj = config.model_dump() if hasattr(config, "model_dump") else {}

    dump(
        {"config": cfg_obj, "trades": fb_trades},
        ROOT / "logs" / "full_trades_fallback_new.json",
    )

    if has_vectorbt:
        vb_trades = [trade_to_dict(t) for t in res_vectorbt.trades]
        dump(
            {"config": cfg_obj, "trades": vb_trades},
            ROOT / "logs" / "full_trades_vectorbt_new.json",
        )

        # Compare sizes and PnL
        print("\n=== COMPARISON ===")
        print(f"Fallback trades: {len(fb_trades)}")
        print(f"Vectorbt trades: {len(vb_trades)}")

        fb_total_pnl = sum(t.get("pnl", 0) for t in fb_trades)
        vb_total_pnl = sum(t.get("pnl", 0) for t in vb_trades)
        print(f"Fallback total PnL: ${fb_total_pnl:.2f}")
        print(f"Vectorbt total PnL: ${vb_total_pnl:.2f}")
        print(f"PnL difference: ${abs(fb_total_pnl - vb_total_pnl):.2f}")

        # Compare first few trades
        print("\n=== TRADE COMPARISON (first 3) ===")
        for i in range(min(3, len(fb_trades), len(vb_trades))):
            fb = fb_trades[i]
            vb = vb_trades[i]
            print(f"\nTrade {i+1}:")
            print(f"  Side: FB={fb.get('side')}, VB={vb.get('side')}")
            print(f"  Size: FB={fb.get('size', 0):.6f}, VB={vb.get('size', 0):.6f}")
            print(f"  EntryPrice: FB={fb.get('entry_price', 0):.2f}, VB={vb.get('entry_price', 0):.2f}")
            print(f"  PnL: FB=${fb.get('pnl', 0):.2f}, VB=${vb.get('pnl', 0):.2f}")
            print(f"  Fees: FB=${fb.get('fees', 0):.2f}, VB=${vb.get('fees', 0):.2f}")
    else:
        print(f"\nWrote {len(fb_trades)} fallback trades only")
        fb_total_pnl = sum(t.get("pnl", 0) for t in fb_trades)
        print(f"Total PnL: ${fb_total_pnl:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
