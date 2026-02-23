"""
Full 104-trade comparison: Engine vs TradingView (tv_trades_104.csv).
Loads ALL 104 TV trades, runs backtest, matches by (side, entry_price±0.5),
shows every divergence: EXIT_T, EXIT_P, PNL.
"""

import csv
import json
import sqlite3
import sys
import warnings
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

warnings.filterwarnings("ignore")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5c03fd86-a821-4a62-a783-4d617bf25bc7"
TV_CSV = r"d:\bybit_strategy_tester_v2\scripts\tv_trades_104.csv"
UTC3 = timedelta(hours=3)


# ── Parse TV CSV ───────────────────────────────────────────────────────────────
def parse_tv_csv():
    """
    Returns list of dicts with entry/exit times already in UTC.
    TV timestamps are UTC+3 → subtract 3h.
    """
    trades_raw = {}
    with open(TV_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            num = int(row["№ Сделки"])
            typ = row["Тип"].strip()
            dt_str = row["Дата и время"].strip()
            dt_utc3 = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            dt_utc = dt_utc3 - UTC3
            price = float(row["Цена USDT"])
            pnl_val = float(row["Чистая прибыль / убыток USDT"])
            signal = row["Сигнал"].strip()

            if num not in trades_raw:
                trades_raw[num] = {}

            if "Entry" in typ:
                trades_raw[num]["side"] = "long" if "long" in typ.lower() else "short"
                trades_raw[num]["entry_time"] = dt_utc
                trades_raw[num]["entry_price"] = price
            elif "Exit" in typ:
                trades_raw[num]["exit_time"] = dt_utc
                trades_raw[num]["exit_price"] = price
                trades_raw[num]["pnl"] = pnl_val
                trades_raw[num]["exit_signal"] = signal

    result = []
    for num in sorted(trades_raw.keys()):
        d = trades_raw[num]
        if "entry_time" in d and "exit_time" in d:
            result.append(
                {
                    "num": num,
                    "side": d["side"],
                    "entry_time": d["entry_time"],
                    "exit_time": d["exit_time"],
                    "entry_price": d["entry_price"],
                    "exit_price": d["exit_price"],
                    "pnl": d["pnl"],
                    "exit_signal": d.get("exit_signal", ""),
                }
            )
    return result


# ── Load OHLCV from DB ─────────────────────────────────────────────────────────
def load_ohlcv() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 2, 25, tzinfo=UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='30' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


# ── Load strategy graph ────────────────────────────────────────────────────────
def load_strategy_graph() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cursor.fetchone()
    col_names = [d[0] for d in cursor.description]
    conn.close()
    strat = dict(zip(col_names, row, strict=True))

    def jl(v):
        return json.loads(v) if isinstance(v, str) else v

    graph = {
        "name": strat["name"],
        "description": strat.get("description") or "",
        "blocks": jl(strat["builder_blocks"]),
        "connections": jl(strat["builder_connections"]),
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    bgr = jl(strat["builder_graph"])
    if bgr and isinstance(bgr, dict) and bgr.get("main_strategy"):
        graph["main_strategy"] = bgr["main_strategy"]
    return graph


# ── Load backtest params ───────────────────────────────────────────────────────
def load_bt_params() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT parameters, builder_blocks, timeframe FROM strategies WHERE id=?", (STRATEGY_ID,))
    row = cur.fetchone()
    conn.close()

    def jl(v):
        return json.loads(v) if isinstance(v, str) else (v or {})

    params = jl(row[0])
    blocks = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
    timeframe = row[2]

    sltp_block = next((b for b in blocks if b.get("type") == "static_sltp"), {})
    sltp_params = sltp_block.get("params", {})

    return {
        "slippage": float(params.get("_slippage", 0.0)),
        "taker_fee": float(params.get("_commission", 0.0007)),
        "leverage": int(params.get("_leverage", 10)),
        "pyramiding": int(params.get("_pyramiding", 1)),
        "take_profit": float(sltp_params.get("take_profit_percent", 1.5)) / 100.0,
        "stop_loss": float(sltp_params.get("stop_loss_percent", 9.1)) / 100.0,
        "interval": str(timeframe or "30"),
    }


# ── Run backtest ───────────────────────────────────────────────────────────────
def run_engine(ohlcv: pd.DataFrame, p: dict):
    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import BacktestInput, TradeDirection
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    adapter = StrategyBuilderAdapter(load_strategy_graph())
    signals = adapter.generate_signals(ohlcv)

    def to_bool(s):
        return np.asarray(s.values, dtype=bool) if s is not None else np.zeros(len(ohlcv), dtype=bool)

    bt_input = BacktestInput(
        candles=ohlcv,
        long_entries=to_bool(signals.entries),
        long_exits=to_bool(getattr(signals, "exits", None)),
        short_entries=to_bool(getattr(signals, "short_entries", None)),
        short_exits=to_bool(getattr(signals, "short_exits", None)),
        initial_capital=1_000_000.0,
        position_size=0.10,
        use_fixed_amount=True,
        fixed_amount=100.0,
        leverage=p["leverage"],
        stop_loss=p["stop_loss"],
        take_profit=p["take_profit"],
        taker_fee=p["taker_fee"],
        slippage=p["slippage"],
        direction=TradeDirection.BOTH,
        pyramiding=p["pyramiding"],
        interval=p["interval"],
    )

    engine = FallbackEngineV4()
    result = engine.run(bt_input)
    return result.trades


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    p = load_bt_params()
    print("=" * 112)
    print("RSI_6 — Full 104-trade comparison: Engine vs TradingView")
    print(
        f"Params: TF={p['interval']}m | SL={p['stop_loss'] * 100:.1f}% | TP={p['take_profit'] * 100:.1f}% | "
        f"fee={p['taker_fee']} | slip={p['slippage']} | lev={p['leverage']}x | pyramid={p['pyramiding']}"
    )
    print("IC=1,000,000  BaseCash=100 USDT")
    print("=" * 112)

    tv_trades = parse_tv_csv()
    print(f"TV trades loaded: {len(tv_trades)}")

    ohlcv = load_ohlcv()
    print(f"OHLCV: {len(ohlcv)} bars  ({ohlcv.index[0]} .. {ohlcv.index[-1]})")

    eng_trades = run_engine(ohlcv, p)
    print(f"Engine trades:    {len(eng_trades)}")
    print()

    # Print header
    print(
        f"{'#':>3}  {'TV#':>4}  {'side':5}  {'entry_p':>10}  "
        f"{'our_exit(UTC)':19}  {'tv_exit(UTC)':19}  "
        f"{'our_ep':>10}  {'tv_ep':>10}  "
        f"{'our_pnl':>8}  {'tv_pnl':>8}  STATUS"
    )
    print("-" * 120)

    ok_count = 0
    diff_count = 0
    unmatched_tv = []
    used_eng_idx: set[int] = set()

    for tv in tv_trades:
        best = None
        best_delta = 999999.0
        best_idx = -1
        for idx, t in enumerate(eng_trades):
            if idx in used_eng_idx:
                continue
            if t.direction != tv["side"]:
                continue
            delta = abs(t.entry_price - tv["entry_price"])
            if delta < 0.5 and delta < best_delta:
                best_delta = delta
                best = t
                best_idx = idx

        tv_exit_str = tv["exit_time"].strftime("%Y-%m-%d %H:%M:%S")
        tv_num = tv["num"]

        if best is None:
            unmatched_tv.append(tv)
            print(
                f"{'?':>3}  {tv_num:>4}  {tv['side']:5}  "
                f"{tv['entry_price']:>10.1f}  "
                f"{'---':19}  {tv_exit_str:19}  "
                f"{'---':>10}  {tv['exit_price']:>10.1f}  "
                f"{'---':>8}  {tv['pnl']:>8.2f}  [X] NO MATCH"
            )
            diff_count += 1
            continue

        used_eng_idx.add(best_idx)

        # Normalize to naive datetime for comparison
        our_exit = best.exit_time
        if our_exit and hasattr(our_exit, "tzinfo") and our_exit.tzinfo:
            our_exit = our_exit.replace(tzinfo=None)
        our_exit_str = our_exit.strftime("%Y-%m-%d %H:%M:%S") if our_exit else "—"

        tv_exit_naive = tv["exit_time"]  # already naive (no tzinfo added from strptime)

        our_ep = best.exit_price
        tv_ep = tv["exit_price"]
        our_pnl = round(best.pnl, 2)
        tv_pnl = round(tv["pnl"], 2)

        diffs = []

        if our_exit and tv_exit_naive:
            delta_min = int((our_exit - tv_exit_naive).total_seconds() / 60)
            if delta_min != 0:
                diffs.append(f"EXIT_T:{delta_min:+d}m")

        if abs(our_ep - tv_ep) > 0.2:
            diffs.append(f"EXIT_P:{our_ep - tv_ep:+.1f}")

        if abs(our_pnl - tv_pnl) > 0.05:
            diffs.append(f"PNL:{our_pnl - tv_pnl:+.2f}")

        status = "[OK]" if not diffs else f"DIFF: {' '.join(diffs)}"
        ok_count += 1 if not diffs else 0
        diff_count += 0 if not diffs else 1

        row_num = len(used_eng_idx)
        print(
            f"{row_num:>3}  {tv_num:>4}  {best.direction:5}  "
            f"{best.entry_price:>10.1f}  "
            f"{our_exit_str:19}  {tv_exit_str:19}  "
            f"{our_ep:>10.1f}  {tv_ep:>10.1f}  "
            f"{our_pnl:>8.2f}  {tv_pnl:>8.2f}  {status}"
        )

    # Summary
    print()
    print("=" * 112)
    print(f"[OK] MATCHED:  {ok_count:>3} / {len(tv_trades)}  -- perfect (same exit_time, exit_price, pnl)")
    print(f"[X]  DIVERGED: {diff_count:>3} / {len(tv_trades)}  -- has differences")
    print(f"Engine total: {len(eng_trades)}  TV: {len(tv_trades)}")

    our_net = sum(t.pnl for t in eng_trades)
    tv_net = sum(t["pnl"] for t in tv_trades)
    print(f"\nNet profit: ours={our_net:.2f}  TV={tv_net:.2f}  gap={our_net - tv_net:+.2f}")

    if unmatched_tv:
        print(f"\n=== {len(unmatched_tv)} TV trades -- NO engine match ===")
        for tv in unmatched_tv:
            print(
                f"  TV#{tv['num']:>3} {tv['side']:5}  entry={tv['entry_price']:.1f} "
                f"@ {tv['entry_time'].strftime('%Y-%m-%d %H:%M UTC')}  "
                f"exit={tv['exit_price']:.1f} @ {tv['exit_time'].strftime('%Y-%m-%d %H:%M UTC')}  "
                f"pnl={tv['pnl']:.2f}  [{tv['exit_signal']}]"
            )

    unmatched_eng = [t for idx, t in enumerate(eng_trades) if idx not in used_eng_idx]
    if unmatched_eng:
        print(f"\n=== {len(unmatched_eng)} Engine trades -- NO TV match ===")
        for t in unmatched_eng:
            et = t.entry_time.strftime("%Y-%m-%d %H:%M UTC") if t.entry_time else "?"
            xt = t.exit_time.strftime("%Y-%m-%d %H:%M UTC") if t.exit_time else "?"
            print(
                f"  {t.direction:5}  entry={t.entry_price:.1f} @ {et}  "
                f"exit={t.exit_price:.1f} @ {xt}  pnl={t.pnl:.2f}  [{t.exit_reason}]"
            )

    sys.exit(0 if diff_count == 0 else 1)


if __name__ == "__main__":
    main()
