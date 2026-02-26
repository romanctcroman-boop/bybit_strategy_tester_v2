"""
RSI_L/S_7 ETHUSDT 30m — full metrics comparison between engine and TradingView.
TV reference: z1.csv (perf), z2.csv (trade stats), z3.csv (ratios)
"""

import asyncio
import json
import sqlite3
import sys
import warnings

# Fix Windows console encoding for Unicode
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")
sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

import numpy as np
import pandas as pd

from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.interfaces import BacktestInput, TradeDirection
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "30501562-69f0-4d35-ac63-b2b47644ee8b"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")
WARMUP_BARS = 500


def load_graph():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name, builder_blocks, builder_connections, builder_graph FROM strategies WHERE id=?",
        (STRATEGY_ID,),
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    return {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
        **({"main_strategy": ms} if ms else {}),
    }


async def run_engine():
    graph = load_graph()
    svc = BacktestService()

    candles = await svc._fetch_historical_data("ETHUSDT", "30", START_DATE, END_DATE)

    # Fetch BTC with 500-bar warmup
    btc_start = START_DATE - pd.Timedelta(minutes=WARMUP_BARS * 30)
    btc_main = await svc._fetch_historical_data("BTCUSDT", "30", START_DATE, END_DATE)
    warmup_ts_start = int(btc_start.timestamp() * 1000)
    warmup_ts_end = int(START_DATE.timestamp() * 1000)
    raw_warmup = await svc.adapter.get_historical_klines(
        "BTCUSDT", "30", warmup_ts_start, warmup_ts_end, market_type="linear"
    )
    if raw_warmup:
        df_w = pd.DataFrame(raw_warmup)
        for old, new in {
            "startTime": "timestamp",
            "open_time": "timestamp",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "closePrice": "close",
        }.items():
            if old in df_w.columns and new not in df_w.columns:
                df_w = df_w.rename(columns={old: new})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df_w.columns:
                df_w[col] = pd.to_numeric(df_w[col], errors="coerce")
        if df_w["timestamp"].dtype in ["int64", "float64"]:
            df_w["timestamp"] = pd.to_datetime(df_w["timestamp"], unit="ms")
        df_w = df_w.set_index("timestamp").sort_index()
        if btc_main.index.tz is None:
            df_w.index = df_w.index.tz_localize(None)
        btc_candles = pd.concat([df_w, btc_main]).sort_index()
        btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    else:
        btc_candles = btc_main

    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles)
    signals = adapter.generate_signals(candles)

    le = np.asarray(signals.entries.values, dtype=bool)
    se = (
        np.asarray(signals.short_entries.values, dtype=bool)
        if signals.short_entries is not None
        else np.zeros(len(le), dtype=bool)
    )
    lx = np.asarray(signals.exits.values, dtype=bool) if signals.exits is not None else np.zeros(len(le), dtype=bool)
    sx = (
        np.asarray(signals.short_exits.values, dtype=bool)
        if signals.short_exits is not None
        else np.zeros(len(le), dtype=bool)
    )

    result = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=1_000_000.0,
            position_size=0.10,
            use_fixed_amount=True,
            fixed_amount=100.0,
            leverage=10,
            stop_loss=0.132,
            take_profit=0.023,
            taker_fee=0.0007,
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
        )
    )
    return result


def compute_metrics_from_result(result) -> dict:
    """Extract key metrics from engine result for comparison."""
    trades = result.trades
    m = result.metrics or {}

    from backend.backtesting.interfaces import ExitReason

    # Basic counts
    # Trades closed via END_OF_DATA are effectively "open" positions — exclude from stats
    closed = [t for t in trades if t.exit_reason != ExitReason.END_OF_DATA]
    open_trades = [t for t in trades if t.exit_reason == ExitReason.END_OF_DATA]
    long_closed = [t for t in closed if t.direction == "long"]
    short_closed = [t for t in closed if t.direction == "short"]

    winning_all = [t for t in closed if t.pnl > 0]
    winning_long = [t for t in long_closed if t.pnl > 0]
    winning_short = [t for t in short_closed if t.pnl > 0]
    losing_all = [t for t in closed if t.pnl < 0]
    losing_long = [t for t in long_closed if t.pnl < 0]
    losing_short = [t for t in short_closed if t.pnl < 0]

    n_closed = len(closed)
    n_long = len(long_closed)
    n_short = len(short_closed)

    gross_profit_all = sum(t.pnl for t in winning_all)
    gross_profit_long = sum(t.pnl for t in winning_long)
    gross_profit_short = sum(t.pnl for t in winning_short)
    gross_loss_all = abs(sum(t.pnl for t in losing_all))
    gross_loss_long = abs(sum(t.pnl for t in losing_long))
    gross_loss_short = abs(sum(t.pnl for t in losing_short))

    net_profit_all = gross_profit_all - gross_loss_all
    net_profit_long = gross_profit_long - gross_loss_long
    net_profit_short = gross_profit_short - gross_loss_short

    pct_winning_all = 100.0 * len(winning_all) / n_closed if n_closed else 0
    pct_winning_long = 100.0 * len(winning_long) / n_long if n_long else 0
    pct_winning_short = 100.0 * len(winning_short) / n_short if n_short else 0

    avg_win_all = gross_profit_all / len(winning_all) if winning_all else 0
    avg_win_long = gross_profit_long / len(winning_long) if winning_long else 0
    avg_win_short = gross_profit_short / len(winning_short) if winning_short else 0
    avg_loss_all = gross_loss_all / len(losing_all) if losing_all else 0
    avg_loss_long = gross_loss_long / len(losing_long) if losing_long else 0
    avg_loss_short = gross_loss_short / len(losing_short) if losing_short else 0

    avg_trade_all = net_profit_all / n_closed if n_closed else 0
    avg_trade_long = net_profit_long / n_long if n_long else 0
    avg_trade_short = net_profit_short / n_short if n_short else 0

    best_win_all = max((t.pnl for t in winning_all), default=0)
    best_win_long = max((t.pnl for t in winning_long), default=0)
    best_win_short = max((t.pnl for t in winning_short), default=0)
    worst_loss_all = abs(min((t.pnl for t in losing_all), default=0))
    worst_loss_long = abs(min((t.pnl for t in losing_long), default=0))
    worst_loss_short = abs(min((t.pnl for t in losing_short), default=0))

    profit_factor_all = gross_profit_all / gross_loss_all if gross_loss_all else float("inf")
    profit_factor_long = gross_profit_long / gross_loss_long if gross_loss_long else float("inf")
    profit_factor_short = gross_profit_short / gross_loss_short if gross_loss_short else float("inf")

    avg_rw_ratio_all = avg_win_all / avg_loss_all if avg_loss_all else float("inf")

    # Bars in trade
    def bars_in_trade(tlist):
        durs = []
        for t in tlist:
            entry_ts = pd.Timestamp(t.entry_time)
            exit_ts = pd.Timestamp(t.exit_time)
            durs.append((exit_ts - entry_ts).total_seconds() / 1800)
        return durs

    all_bars = bars_in_trade(closed)
    long_bars = bars_in_trade(long_closed)
    short_bars = bars_in_trade(short_closed)
    win_bars = bars_in_trade(winning_all)
    loss_bars = bars_in_trade(losing_all)

    avg_bars_all = sum(all_bars) / len(all_bars) if all_bars else 0
    avg_bars_long = sum(long_bars) / len(long_bars) if long_bars else 0
    avg_bars_short = sum(short_bars) / len(short_bars) if short_bars else 0
    avg_bars_win = sum(win_bars) / len(win_bars) if win_bars else 0
    avg_bars_loss = sum(loss_bars) / len(loss_bars) if loss_bars else 0

    # Commission — field is 'fees' in TradeRecord
    commission_all = sum(getattr(t, "fees", 0.0) or 0 for t in closed)
    commission_long = sum(getattr(t, "fees", 0.0) or 0 for t in long_closed)
    commission_short = sum(getattr(t, "fees", 0.0) or 0 for t in short_closed)

    # From result metrics (MDD, Sharpe, etc.) — BacktestMetrics is a dataclass
    # max_drawdown is stored as PERCENTAGE (already multiplied by 100 in engine)
    mdd_pct = getattr(m, "max_drawdown", 0) or 0  # e.g. 0.0684 means 0.0684%
    mdd_abs = mdd_pct / 100.0 * 1_000_000  # convert % to absolute USDT on 1M capital
    sharpe = getattr(m, "sharpe_ratio", 0) or 0
    sortino = getattr(m, "sortino_ratio", 0) or 0

    # Commission from BacktestMetrics if individual trade fees are zero
    if not commission_all:
        commission_all = getattr(m, "commission_paid", 0) or 0

    # Unrealised PnL: for open (END_OF_DATA) trades use the pnl as of last bar
    unrealised = sum(t.pnl for t in open_trades) if open_trades else 0.0

    return {
        "n_open": len(open_trades),
        "n_closed": n_closed,
        "n_long": n_long,
        "n_short": n_short,
        "n_winning_all": len(winning_all),
        "n_winning_long": len(winning_long),
        "n_winning_short": len(winning_short),
        "n_losing_all": len(losing_all),
        "n_losing_long": len(losing_long),
        "n_losing_short": len(losing_short),
        "pct_winning_all": pct_winning_all,
        "pct_winning_long": pct_winning_long,
        "pct_winning_short": pct_winning_short,
        "net_profit_all": net_profit_all,
        "net_profit_long": net_profit_long,
        "net_profit_short": net_profit_short,
        "gross_profit_all": gross_profit_all,
        "gross_profit_long": gross_profit_long,
        "gross_profit_short": gross_profit_short,
        "gross_loss_all": gross_loss_all,
        "gross_loss_long": gross_loss_long,
        "gross_loss_short": gross_loss_short,
        "avg_trade_all": avg_trade_all,
        "avg_win_all": avg_win_all,
        "avg_win_long": avg_win_long,
        "avg_win_short": avg_win_short,
        "avg_loss_all": avg_loss_all,
        "avg_loss_long": avg_loss_long,
        "avg_loss_short": avg_loss_short,
        "best_win_all": best_win_all,
        "best_win_long": best_win_long,
        "best_win_short": best_win_short,
        "worst_loss_all": worst_loss_all,
        "worst_loss_long": worst_loss_long,
        "worst_loss_short": worst_loss_short,
        "profit_factor_all": profit_factor_all,
        "profit_factor_long": profit_factor_long,
        "profit_factor_short": profit_factor_short,
        "avg_rw_ratio_all": avg_rw_ratio_all,
        "avg_bars_all": avg_bars_all,
        "avg_bars_long": avg_bars_long,
        "avg_bars_short": avg_bars_short,
        "avg_bars_win": avg_bars_win,
        "avg_bars_loss": avg_bars_loss,
        "commission_all": commission_all,
        "commission_long": commission_long,
        "commission_short": commission_short,
        "mdd_pct": mdd_pct,
        "mdd_abs": mdd_abs,
        "sharpe": sharpe,
        "sortino": sortino,
        "unrealised": unrealised,
    }


def compare_and_print(eng: dict) -> None:
    """Compare engine metrics vs TradingView reference."""
    # TV reference values from z1.csv, z2.csv, z3.csv
    tv = {
        # z2.csv
        "n_open": 1,
        "n_closed": 146,
        "n_long": 31,
        "n_short": 115,
        "n_winning_all": 132,
        "n_winning_long": 28,
        "n_winning_short": 104,
        "n_losing_all": 14,
        "n_losing_long": 3,
        "n_losing_short": 11,
        "pct_winning_all": 90.41,
        "pct_winning_long": 90.32,
        "pct_winning_short": 90.43,
        "avg_rw_ratio_all": 0.162,
        "avg_win_all": 21.61,
        "avg_win_long": 21.58,
        "avg_win_short": 21.61,
        "avg_loss_all": 133.49,
        "avg_loss_long": 133.51,
        "avg_loss_short": 133.48,
        "best_win_all": 21.62,
        "best_win_long": 21.59,
        "best_win_short": 21.62,
        "worst_loss_all": 133.49,
        "worst_loss_long": 133.30,
        "worst_loss_short": 133.49,
        "avg_bars_all": 104,
        "avg_bars_long": 53,
        "avg_bars_short": 117,
        "avg_bars_win": 86,
        "avg_bars_loss": 268,
        # z3.csv
        "sharpe": -9.154,
        "sortino": -0.994,
        "profit_factor_all": 1.526,
        "profit_factor_long": 1.509,
        "profit_factor_short": 1.531,
        # z1.csv
        "net_profit_all": 983.4,
        "net_profit_long": 203.8,
        "net_profit_short": 779.61,
        "gross_profit_all": 2852.24,
        "gross_profit_long": 604.32,
        "gross_profit_short": 2247.93,
        "gross_loss_all": 1868.84,
        "gross_loss_long": 400.52,
        "gross_loss_short": 1468.32,
        "avg_trade_all": 6.74,
        "commission_all": 204.58,
        "commission_long": 44.27,
        "commission_short": 160.32,
        "unrealised": 2.55,
        "mdd_abs": 735.35,  # Max intra-bar DD in USDT
        "mdd_pct": 0.07,  # 0.07% of 1M capital
    }

    # --- Print header ---
    print(f"\n{'Metric':<40} {'TV':>15} {'Engine':>15} {'Match':>7}")
    print("─" * 80)

    TOLERANCE = {
        "n_open": 0,
        "n_closed": 0,
        "n_long": 0,
        "n_short": 0,
        "n_winning_all": 0,
        "n_winning_long": 0,
        "n_winning_short": 0,
        "n_losing_all": 0,
        "n_losing_long": 0,
        "n_losing_short": 0,
        "pct_winning_all": 1.0,
        "pct_winning_long": 1.0,
        "pct_winning_short": 1.0,
        "avg_rw_ratio_all": 0.05,
        "avg_win_all": 1.0,
        "avg_win_long": 1.0,
        "avg_win_short": 1.0,
        "avg_loss_all": 2.0,
        "avg_loss_long": 2.0,
        "avg_loss_short": 2.0,
        "best_win_all": 0.5,
        "best_win_long": 0.5,
        "best_win_short": 0.5,
        "worst_loss_all": 2.0,
        "worst_loss_long": 2.0,
        "worst_loss_short": 2.0,
        "avg_bars_all": 10,
        "avg_bars_long": 10,
        "avg_bars_short": 10,
        "avg_bars_win": 10,
        "avg_bars_loss": 30,
        "sharpe": 1.0,
        "sortino": 0.5,
        "profit_factor_all": 0.05,
        "profit_factor_long": 0.1,
        "profit_factor_short": 0.05,
        "net_profit_all": 30.0,
        "net_profit_long": 20.0,
        "net_profit_short": 30.0,
        "gross_profit_all": 50.0,
        "gross_profit_long": 20.0,
        "gross_profit_short": 50.0,
        "gross_loss_all": 50.0,
        "gross_loss_long": 20.0,
        "gross_loss_short": 50.0,
        "avg_trade_all": 1.0,
        "commission_all": 10.0,
        "commission_long": 5.0,
        "commission_short": 10.0,
        "unrealised": 5.0,
        "mdd_abs": 50.0,
        "mdd_pct": 0.5,
    }

    matches = 0
    mismatches = 0
    for key, tv_val in tv.items():
        eng_val = eng.get(key, float("nan"))
        tol = TOLERANCE.get(key, 0.01)
        if isinstance(eng_val, float) and isinstance(tv_val, float):
            ok = abs(eng_val - tv_val) <= tol
        elif isinstance(eng_val, int) and isinstance(tv_val, int):
            ok = eng_val == tv_val
        else:
            try:
                ok = abs(float(eng_val) - float(tv_val)) <= tol
            except Exception:
                ok = eng_val == tv_val

        sym = "✅" if ok else "❌"
        if ok:
            matches += 1
        else:
            mismatches += 1

        # Format for display
        def fmt(v):
            if isinstance(v, float):
                return f"{v:.2f}"
            return str(v)

        print(f"  {key:<38} {fmt(tv_val):>15} {fmt(eng_val):>15} {sym:>7}")

    print("─" * 80)
    print(f"  TOTAL: {matches}/{matches + mismatches} matched  ({100 * matches / (matches + mismatches):.0f}%)")


async def main():
    print("Running engine (with BTC warmup)...")
    result = await run_engine()

    trades = result.trades
    closed = [t for t in trades if not getattr(t, "is_open", False)]
    open_trades = [t for t in trades if getattr(t, "is_open", False)]
    print(f"Engine: {len(closed)} closed + {len(open_trades)} open = {len(trades)} total")

    eng = compute_metrics_from_result(result)
    compare_and_print(eng)

    # Print some raw values for debugging
    print("\nRaw engine metrics:")
    if result.metrics:
        m = result.metrics
        for k in [
            "max_drawdown",
            "sharpe_ratio",
            "sortino_ratio",
            "profit_factor",
            "net_profit",
            "gross_profit",
            "gross_loss",
            "commission_paid",
            "win_rate",
            "total_trades",
        ]:
            print(f"  {k}: {getattr(m, k, 'N/A')}")


asyncio.run(main())
