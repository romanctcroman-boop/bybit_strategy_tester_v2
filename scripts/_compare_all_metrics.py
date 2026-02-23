"""
Full metric parity comparison: our engine vs TradingView.
TV settings from 5.csv: slippage=0 ticks, commission=0.07%, leverage=10,
position_size=10% of equity, initial_capital=10000.
"""

import datetime as dt
import json
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
STRATEGY_ID = "5a1741ac-ad9e-4285-a9d6-58067c56407a"
TV_CSV = r"C:\Users\roman\Downloads\4.csv"  # semicolon-delimited full trade list


# ── Load TV reference data from the CSV files ─────────────────────────────────
TV_METRICS = {
    # From 2.csv (trade stats)
    "total_closed_trades": 128,
    "total_open_trades": 1,
    "total_trades": 129,  # 128 closed + 1 open
    "winning_trades": 101,
    "losing_trades": 27,
    "win_rate_pct": 78.91,
    "avg_pnl_usd": 3.77,
    "avg_pnl_pct": 0.38,
    "avg_win_usd": 13.71,
    "avg_win_pct": 1.37,
    "avg_loss_usd": -33.43,
    "avg_loss_pct": -3.34,
    "largest_win_usd": 24.50,
    "largest_win_pct": 2.45,
    "largest_loss_usd": -33.42,
    "largest_loss_pct": -3.34,
    "avg_bars_in_trade": 74,
    "avg_bars_in_win": 66,
    "avg_bars_in_loss": 101,
    # From 1.csv (financial metrics)
    "net_profit_usd": 482.16,
    "net_profit_pct": 4.82,
    "gross_profit_usd": 1384.65,
    "gross_profit_pct": 13.85,
    "gross_loss_usd": -902.50,
    "gross_loss_pct": -9.02,
    "commission_paid_usd": 179.79,
    # From 3.csv (ratios)
    "sharpe_ratio": 0.895,
    "sortino_ratio": 16.708,
    "profit_factor": 1.534,
    # From 1.csv continued
    "max_drawdown_usd": 146.99,  # Макс. просадка (внутри бара)
    "max_drawdown_pct": 1.44,
    "max_drawdown_close_usd": 141.28,  # от закрытия до закрытия
    "max_drawdown_close_pct": 1.41,
}

TV_LONG = {
    "winning_trades": 44,
    "losing_trades": 13,
    "win_rate_pct": 77.19,
    "net_profit_usd": 174.95,
    "net_profit_pct": 1.75,
    "gross_profit_usd": 608.85,
    "gross_loss_usd": -433.90,
}

TV_SHORT = {
    "winning_trades": 57,
    "losing_trades": 14,
    "win_rate_pct": 80.28,
    "net_profit_usd": 307.20,
    "net_profit_pct": 3.07,
    "gross_profit_usd": 775.80,
    "gross_loss_usd": -468.60,
}


def load_tv_trades():
    df = pd.read_csv(TV_CSV, sep=";", encoding="utf-8-sig")
    df.columns = [
        "trade_num",
        "type",
        "datetime",
        "signal",
        "price",
        "size_qty",
        "size_price",
        "pnl_usd",
        "pnl_pct",
        "fav_usd",
        "fav_pct",
        "adv_usd",
        "adv_pct",
        "cum_pnl_usd",
        "cum_pnl_pct",
    ]
    entries = df[df["type"].str.startswith("Entry")].copy()
    exits = df[df["type"].str.startswith("Exit")].copy()
    entries["dt_utc"] = pd.to_datetime(entries["datetime"], format="%Y-%m-%d %H:%M") - pd.Timedelta(hours=3)
    exits["exit_utc"] = pd.to_datetime(exits["datetime"], format="%Y-%m-%d %H:%M") - pd.Timedelta(hours=3)
    entries["side"] = entries["type"].apply(lambda x: "buy" if "long" in x.lower() else "sell")
    tv = entries.merge(
        exits[["trade_num", "exit_utc", "pnl_usd", "pnl_pct", "signal"]].rename(
            columns={"pnl_usd": "exit_pnl_usd", "pnl_pct": "exit_pnl_pct", "signal": "exit_signal"}
        ),
        on="trade_num",
        how="left",
    )
    tv = tv.sort_values("trade_num").reset_index(drop=True)
    return tv


def load_ohlcv():
    conn = sqlite3.connect(DB_PATH)
    start_ms = int(dt.datetime(2025, 11, 1, tzinfo=dt.UTC).timestamp() * 1000)
    end_ms = int(dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC).timestamp() * 1000)
    df = pd.read_sql_query(
        "SELECT open_time, open_price as open, high_price as high, "
        "low_price as low, close_price as close, volume "
        "FROM bybit_kline_audit "
        "WHERE symbol='BTCUSDT' AND interval='15' AND market_type='linear' "
        "AND open_time >= ? AND open_time <= ? ORDER BY open_time ASC",
        conn,
        params=(start_ms, end_ms),
    )
    conn.close()
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def run_backtest(slippage_val: float):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).fetchone()
    col_names = [d[0] for d in conn.execute("SELECT * FROM strategies WHERE id=?", (STRATEGY_ID,)).description]
    conn.close()
    strat = dict(zip(col_names, row, strict=False))

    builder_blocks = json.loads(strat["builder_blocks"])
    builder_connections = json.loads(strat["builder_connections"])
    builder_graph_raw = json.loads(strat["builder_graph"])
    strategy_graph = {
        "name": strat["name"],
        "description": strat.get("description") or "",
        "blocks": builder_blocks,
        "connections": builder_connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "15",
    }
    if builder_graph_raw and builder_graph_raw.get("main_strategy"):
        strategy_graph["main_strategy"] = builder_graph_raw["main_strategy"]

    from backend.backtesting.engine import BacktestEngine
    from backend.backtesting.models import BacktestConfig
    from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

    adapter = StrategyBuilderAdapter(strategy_graph)
    ohlcv = load_ohlcv()
    params = json.loads(strat["parameters"])

    config = BacktestConfig(
        symbol="BTCUSDT",
        interval="15",
        start_date=dt.datetime(2025, 11, 1, tzinfo=dt.UTC),
        end_date=dt.datetime(2026, 2, 23, 23, 59, tzinfo=dt.UTC),
        initial_capital=10000.0,
        commission_value=float(params.get("_commission", 0.0007)),
        slippage=slippage_val,
        leverage=float(params.get("_leverage", 10.0)),
        position_size=0.1,
        pyramiding=int(params.get("_pyramiding", 1)),
        direction="both",
        stop_loss=0.032,
        take_profit=0.015,
    )

    engine = BacktestEngine()
    result = engine.run(config, ohlcv, custom_strategy=adapter)
    return result, config


def calc_metrics(result, config):
    trades = result.trades
    initial = config.initial_capital

    closed = [t for t in trades if not getattr(t, "is_open", False)]
    # Trade #129 (last) may be open - check exit_reason
    # Closed = all trades that have a real exit_time
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl < 0]

    gross_profit = sum(t.pnl for t in wins)
    gross_loss = sum(t.pnl for t in losses)  # negative
    total_pnl = sum(t.pnl for t in closed)
    total_fees = sum(t.fees for t in closed)

    longs = [t for t in closed if t.side in ("buy", "long")]
    shorts = [t for t in closed if t.side in ("sell", "short")]

    long_wins = [t for t in longs if t.pnl > 0]
    long_losses = [t for t in longs if t.pnl < 0]
    short_wins = [t for t in shorts if t.pnl > 0]
    short_losses = [t for t in shorts if t.pnl < 0]

    n = len(closed)
    return {
        "total_closed_trades": n,
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": 100 * len(wins) / n if n else 0,
        "net_profit_usd": total_pnl,
        "net_profit_pct": 100 * total_pnl / initial,
        "gross_profit_usd": gross_profit,
        "gross_profit_pct": 100 * gross_profit / initial,
        "gross_loss_usd": gross_loss,
        "gross_loss_pct": 100 * gross_loss / initial,
        "avg_pnl_usd": total_pnl / n if n else 0,
        "avg_pnl_pct": sum(t.pnl_pct for t in closed) / n if n else 0,
        "avg_win_usd": gross_profit / len(wins) if wins else 0,
        "avg_loss_usd": gross_loss / len(losses) if losses else 0,
        "largest_win_usd": max((t.pnl for t in wins), default=0),
        "largest_loss_usd": min((t.pnl for t in losses), default=0),
        "commission_paid_usd": total_fees,
        "profit_factor": abs(gross_profit / gross_loss) if gross_loss else float("inf"),
        # Long breakdown
        "long_winning": len(long_wins),
        "long_losing": len(long_losses),
        "long_net_pnl": sum(t.pnl for t in longs),
        "long_gross_profit": sum(t.pnl for t in long_wins),
        "long_gross_loss": sum(t.pnl for t in long_losses),
        # Short breakdown
        "short_winning": len(short_wins),
        "short_losing": len(short_losses),
        "short_net_pnl": sum(t.pnl for t in shorts),
        "short_gross_profit": sum(t.pnl for t in short_wins),
        "short_gross_loss": sum(t.pnl for t in short_losses),
    }


def compare(tv_val, our_val, label, fmt=".2f", tol=1.0):
    if isinstance(tv_val, (int, float)) and isinstance(our_val, (int, float)):
        diff = our_val - tv_val
        pct_diff = 100 * diff / abs(tv_val) if tv_val != 0 else 0
        ok = abs(diff) <= tol
        marker = "OK" if ok else "!!"
        print(f"  {marker} {label:<45} TV={tv_val:{fmt}}  Ours={our_val:{fmt}}  diff={diff:+{fmt}} ({pct_diff:+.1f}%)")
    else:
        ok = str(tv_val) == str(our_val)
        marker = "OK" if ok else "!!"
        print(f"  {marker} {label:<45} TV={tv_val}  Ours={our_val}")


def main():
    print("=" * 80)
    print("RUNNING BACKTEST WITH slippage=0 (TV setting = current config)")
    print("=" * 80)
    result_zero, config_zero = run_backtest(0.0)
    metrics_zero = calc_metrics(result_zero, config_zero)
    metrics_slip = metrics_zero  # slippage now matches TV

    trades_zero = result_zero.trades
    print(f"Trades with slippage=0: {len(trades_zero)}")

    print()
    print("=" * 80)
    print("TRADE-LEVEL COMPARISON (slippage=0) vs TV")
    print("=" * 80)
    tv_trades = load_tv_trades()
    tv_closed = tv_trades[~tv_trades["exit_signal"].str.contains("Открыт", na=False)].copy()
    our_closed = list(trades_zero)

    print(f"TV closed trades: {len(tv_closed)}  |  Ours: {len(our_closed)}")
    print()
    print(
        f"{'#':<4} {'Side':<5} {'TV Entry':>10} {'Ours Entry':>12} {'dE':>6} {'TV PnL':>8} {'Ours PnL':>9} {'dPnL':>8} {'TV Exit':>10} {'Ours Exit':>12} {'dX':>6}"
    )
    total_pnl_diff = 0
    entry_price_diffs = []
    pnl_diffs = []

    for idx in range(min(len(tv_closed), len(our_closed))):
        tv_t = tv_closed.iloc[idx]
        our_t = our_closed[idx]
        tv_entry = float(tv_t["price"])
        tv_exit = float(tv_t.get("exit_pnl_usd", 0))  # not exit price, need another way
        our_entry = our_t.entry_price
        our_pnl = our_t.pnl
        tv_pnl = float(tv_t["exit_pnl_usd"])
        d_entry = our_entry - tv_entry
        d_pnl = our_pnl - tv_pnl
        total_pnl_diff += d_pnl
        entry_price_diffs.append(abs(d_entry))
        pnl_diffs.append(abs(d_pnl))

    # Reparse tv exit prices from the CSV properly
    df_raw = pd.read_csv(TV_CSV, sep=";", encoding="utf-8-sig")
    df_raw.columns = [
        "trade_num",
        "type",
        "datetime",
        "signal",
        "price",
        "size_qty",
        "size_price",
        "pnl_usd",
        "pnl_pct",
        "fav_usd",
        "fav_pct",
        "adv_usd",
        "adv_pct",
        "cum_pnl_usd",
        "cum_pnl_pct",
    ]
    tv_exits_map = {}
    tv_entries_map = {}
    for _, row in df_raw.iterrows():
        tn = int(row["trade_num"])
        if row["type"].startswith("Exit"):
            tv_exits_map[tn] = float(row["price"])
        elif row["type"].startswith("Entry"):
            tv_entries_map[tn] = float(row["price"])

    print(
        f"\n{'#':<4} {'Side':<5} {'TV_e':>10} {'Our_e':>10} {'dE':>7} {'TV_x':>10} {'Our_x':>10} {'dX':>7} {'TV_pnl':>8} {'Our_pnl':>8} {'dP':>8}"
    )
    total_pnl_diff = 0
    for idx in range(min(len(tv_closed), len(our_closed))):
        tv_t = tv_closed.iloc[idx]
        our_t = our_closed[idx]
        tn = int(tv_t["trade_num"])
        tv_entry = tv_entries_map.get(tn, 0)
        tv_exit = tv_exits_map.get(tn, 0)
        our_entry = our_t.entry_price
        our_exit = our_t.exit_price
        tv_pnl = float(tv_t["exit_pnl_usd"])
        our_pnl = our_t.pnl
        d_entry = our_entry - tv_entry
        d_exit = our_exit - tv_exit
        d_pnl = our_pnl - tv_pnl
        total_pnl_diff += d_pnl
        marker = "" if abs(d_pnl) < 1.0 else " <<<"
        side = "buy" if "long" in str(tv_t["type"]).lower() else "sell"
        print(
            f"{tn:<4} {side:<5} {tv_entry:>10.2f} {our_entry:>10.2f} {d_entry:>+7.2f} {tv_exit:>10.2f} {our_exit:>10.2f} {d_exit:>+7.2f} {tv_pnl:>8.2f} {our_pnl:>8.2f} {d_pnl:>+8.2f}{marker}"
        )

    print(f"\nTotal PnL diff: {total_pnl_diff:+.2f}")

    print()
    print("=" * 80)
    print("METRICS COMPARISON (slippage=0 vs TV)")
    print("=" * 80)

    m = metrics_zero
    compare(128, m["total_closed_trades"], "Closed trades")
    compare(101, m["winning_trades"], "Winning trades", fmt=".0f", tol=0)
    compare(27, m["losing_trades"], "Losing trades", fmt=".0f", tol=0)
    compare(78.91, m["win_rate_pct"], "Win rate %", tol=0.1)
    compare(482.16, m["net_profit_usd"], "Net profit USD", tol=5.0)
    compare(4.82, m["net_profit_pct"], "Net profit %", tol=0.1)
    compare(1384.65, m["gross_profit_usd"], "Gross profit USD", tol=10.0)
    compare(-902.50, m["gross_loss_usd"], "Gross loss USD", tol=10.0)
    compare(179.79, m["commission_paid_usd"], "Commission paid USD", tol=5.0)
    compare(1.534, m["profit_factor"], "Profit factor", fmt=".3f", tol=0.05)
    compare(3.77, m["avg_pnl_usd"], "Avg PnL per trade USD", tol=0.5)
    compare(13.71, m["avg_win_usd"], "Avg winning trade USD", tol=0.5)
    compare(-33.43, m["avg_loss_usd"], "Avg losing trade USD", tol=0.5)
    compare(24.50, m["largest_win_usd"], "Largest win USD", tol=1.0)
    compare(-33.42, m["largest_loss_usd"], "Largest loss USD", tol=0.5)

    print()
    print("LONG breakdown:")
    compare(44, m["long_winning"], "  Long winning trades", fmt=".0f", tol=0)
    compare(13, m["long_losing"], "  Long losing trades", fmt=".0f", tol=0)
    compare(174.95, m["long_net_pnl"], "  Long net PnL USD", tol=5.0)
    compare(608.85, m["long_gross_profit"], "  Long gross profit USD", tol=10.0)
    compare(-433.90, m["long_gross_loss"], "  Long gross loss USD", tol=10.0)

    print()
    print("SHORT breakdown:")
    compare(57, m["short_winning"], "  Short winning trades", fmt=".0f", tol=0)
    compare(14, m["short_losing"], "  Short losing trades", fmt=".0f", tol=0)
    compare(307.20, m["short_net_pnl"], "  Short net PnL USD", tol=5.0)
    compare(775.80, m["short_gross_profit"], "  Short gross profit USD", tol=10.0)
    compare(-468.60, m["short_gross_loss"], "  Short gross loss USD", tol=10.0)

    print()
    print("=" * 80)
    print("CURRENT CONFIG (slippage=0, matches TV):")
    print("=" * 80)
    m2 = metrics_slip
    compare(482.16, m2["net_profit_usd"], "Net profit USD", tol=5.0)
    compare(4.82, m2["net_profit_pct"], "Net profit %", tol=0.1)
    compare(179.79, m2["commission_paid_usd"], "Commission paid USD", tol=5.0)


if __name__ == "__main__":
    main()
