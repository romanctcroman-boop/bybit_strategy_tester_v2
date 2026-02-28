"""Full trade-by-trade comparison table: Ours vs TradingView."""

import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from backend.backtesting.engine import BacktestEngine
from backend.backtesting.models import BacktestConfig, StrategyType
from backend.backtesting.service import BacktestService
from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter


async def run():
    conn_db = sqlite3.connect(r"d:\bybit_strategy_tester_v2\data.sqlite3")
    cur = conn_db.cursor()
    cur.execute(
        "SELECT builder_blocks, builder_connections, builder_graph "
        "FROM strategies WHERE id = '2e5bb802-572b-473f-9ee9-44d38bf9c531'"
    )
    row = cur.fetchone()
    conn_db.close()

    blocks = json.loads(row[0])
    connections = json.loads(row[1])
    builder_graph = json.loads(row[2]) if row[2] else {}

    strategy_graph = {
        "name": "Test",
        "blocks": blocks,
        "connections": connections,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if builder_graph.get("main_strategy"):
        strategy_graph["main_strategy"] = builder_graph["main_strategy"]

    svc = BacktestService()
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 28, tzinfo=timezone.utc)
    warmup = pd.Timedelta(minutes=500 * 30)

    btc_ohlcv = await svc._fetch_historical_data("BTCUSDT", "30", start - warmup, end, "spot")
    eth_ohlcv = await svc._fetch_historical_data("ETHUSDT", "30", start, end, "linear")

    adapter = StrategyBuilderAdapter(strategy_graph, btcusdt_ohlcv=btc_ohlcv)

    config = BacktestConfig(
        symbol="ETHUSDT",
        interval="30",
        start_date=start,
        end_date=end,
        strategy_type=StrategyType.CUSTOM,
        strategy_params={},
        initial_capital=10000.0,
        position_size=0.1,
        leverage=10.0,
        direction="both",
        stop_loss=0.132,
        take_profit=0.023,
        taker_fee=0.0007,
        maker_fee=0.0007,
        slippage=0.0,
        pyramiding=1,
        market_type="linear",
    )

    result = BacktestEngine().run(config, eth_ohlcv, custom_strategy=adapter)

    # Build our trades list
    our_trades = []
    for t in result.trades:
        entry_ts = getattr(t, "entry_time", None)
        exit_ts = getattr(t, "exit_time", None)
        if entry_ts is None:
            continue
        entry_dt = (
            pd.Timestamp(entry_ts, tz="UTC")
            if not hasattr(entry_ts, "tzinfo") or entry_ts.tzinfo is None
            else pd.Timestamp(entry_ts).tz_convert("UTC")
        )
        exit_dt = None
        if exit_ts is not None:
            exit_dt = (
                pd.Timestamp(exit_ts, tz="UTC")
                if not hasattr(exit_ts, "tzinfo") or exit_ts.tzinfo is None
                else pd.Timestamp(exit_ts).tz_convert("UTC")
            )

        our_trades.append(
            {
                "entry_utc": entry_dt,
                "entry_price": round(getattr(t, "entry_price", 0), 2),
                "exit_utc": exit_dt,
                "exit_price": round(getattr(t, "exit_price", 0), 2),
                "side": "SHORT" if getattr(t, "side", "") == "sell" else "LONG",
                "exit_reason": getattr(t, "exit_reason", "?"),
                "pnl": round(getattr(t, "pnl", 0), 2),
            }
        )
    our_trades.sort(key=lambda x: x["entry_utc"])

    # Build TV trades list from CSV
    df = pd.read_csv(r"d:\bybit_strategy_tester_v2\temp_analysis\a4.csv", sep=";")
    entries = df[df["Тип"].str.contains("Вход")].copy()
    exits = df[df["Тип"].str.contains("Выход")].copy()

    entries["dt_utc"] = pd.to_datetime(entries["Дата и время"]) - pd.Timedelta(hours=3)
    exits["dt_utc"] = pd.to_datetime(exits["Дата и время"]) - pd.Timedelta(hours=3)
    entries["dir"] = entries["Тип"].apply(lambda x: "LONG" if "длинную" in x else "SHORT")
    entries["trade_no"] = entries["№ Сделки"].astype(int)
    exits["trade_no"] = exits["№ Сделки"].astype(int)

    exits_map = {}
    for _, r in exits.iterrows():
        no = int(r["trade_no"])
        reason_raw = str(r.get("Сигнал", ""))
        if "TP" in reason_raw or "Достигнут" in reason_raw:
            reason = "TP"
        elif "SL" in reason_raw or "Stop" in reason_raw:
            reason = "SL"
        else:
            reason = reason_raw[:12]
        exits_map[no] = {
            "exit_dt": r["dt_utc"],
            "exit_price": round(float(r["Цена USDT"]), 2),
            "exit_reason": reason,
            "pnl": round(float(r["Чистая прибыль / убыток USDT"]), 2),
        }

    tv_trades = []
    for _, r in entries.iterrows():
        no = int(r["trade_no"])
        ex = exits_map.get(no, {})
        tv_trades.append(
            {
                "no": no,
                "entry_utc": r["dt_utc"],
                "entry_price": round(float(r["Цена USDT"]), 2),
                "exit_utc": ex.get("exit_dt"),
                "exit_price": ex.get("exit_price", "?"),
                "side": r["dir"],
                "exit_reason": ex.get("exit_reason", "?"),
                "pnl": ex.get("pnl", "?"),
            }
        )
    tv_trades.sort(key=lambda x: x["entry_utc"])

    # Build lookup by entry_price+side for matching
    our_by_key = {(t["entry_price"], t["side"]): t for t in our_trades}

    def divergence_pct(tv: dict, our: dict) -> float:
        """
        Composite divergence % across all comparable trade fields.
        Each field contributes a normalised absolute deviation:
          - entry_price   : |our - tv| / tv  * 100
          - exit_price    : |our - tv| / tv  * 100
          - pnl           : |our - tv| / |tv| * 100  (skip if tv==0)
          - entry_time    : |offset_min| / 30 * 100  (30 min = 1 bar = 100%)
          - exit_time     : |offset_min| / 30 * 100
        Final = average of all applicable components.
        """
        components = []

        # entry price
        if tv["entry_price"] and tv["entry_price"] != 0:
            components.append(abs(our["entry_price"] - tv["entry_price"]) / tv["entry_price"] * 100)

        # exit price
        tv_ep = tv.get("exit_price")
        our_ep = our.get("exit_price")
        if isinstance(tv_ep, float) and isinstance(our_ep, float) and tv_ep != 0:
            components.append(abs(our_ep - tv_ep) / tv_ep * 100)

        # pnl
        tv_pnl = tv.get("pnl")
        our_pnl = our.get("pnl")
        if isinstance(tv_pnl, float) and isinstance(our_pnl, float) and tv_pnl != 0:
            components.append(abs(our_pnl - tv_pnl) / abs(tv_pnl) * 100)

        # entry time delta (in 30-min bars)
        try:
            tv_et = pd.Timestamp(tv["entry_utc"])
            our_et = pd.Timestamp(our["entry_utc"])
            delta_min = abs((our_et - tv_et).total_seconds()) / 60
            components.append(delta_min / 30 * 100)
        except Exception:
            pass

        # exit time delta
        try:
            tv_xt = tv.get("exit_utc")
            our_xt = our.get("exit_utc")
            if tv_xt is not None and our_xt is not None:
                tv_xt = pd.Timestamp(tv_xt)
                our_xt = pd.Timestamp(our_xt)
                delta_min = abs((our_xt - tv_xt).total_seconds()) / 60
                components.append(delta_min / 30 * 100)
        except Exception:
            pass

        return sum(components) / len(components) if components else 0.0

    # ── Header ──
    col = "{:>3}  {:5}  {:19}  {:>9}  {:>9}  {:>9}  {:>9}  {:5}  {:19}  {:>9}  {:>9}  {:>9}  {:>9}  {:>7}  {:4}"
    hdr = col.format(
        "#",
        "Side",
        "TV Entry (UTC)",
        "TV Entr$",
        "Our Entr$",
        "TV Exit$",
        "Our Exit$",
        "Match",
        "TV Exit (UTC)",
        "TV P&L",
        "Our P&L",
        "ΔP&L",
        "ΔEntry$",
        "Div%",
        "Exit",
    )
    sep = "─" * len(hdr)
    print(hdr)
    print(sep)

    matched = 0
    total_div = []
    divergent_rows = []  # trades with div > 0

    for tv in tv_trades:
        key = (tv["entry_price"], tv["side"])
        our = our_by_key.get(key)
        match_str = "✅" if our else "❌"

        tv_entry_price = tv["entry_price"]
        tv_exit_price = tv.get("exit_price")
        tv_pnl = tv.get("pnl")
        tv_entry_str = str(tv["entry_utc"])[:19]
        tv_exit_str = str(tv["exit_utc"])[:16] if tv.get("exit_utc") is not None else "—"

        if our:
            matched += 1
            div = divergence_pct(tv, our)
            total_div.append(div)

            our_ep_str = f"{our['entry_price']:9.2f}"
            our_xp_str = f"{our['exit_price']:9.2f}"
            tv_ep_str = f"{tv_entry_price:9.2f}"
            tv_xp_str = f"{tv_exit_price:9.2f}" if isinstance(tv_exit_price, float) else f"{'?':>9}"
            tv_pnl_str = f"{tv_pnl:9.2f}" if isinstance(tv_pnl, float) else f"{'?':>9}"
            our_pnl_str = f"{our['pnl']:9.2f}"
            dpnl = our["pnl"] - tv_pnl if isinstance(tv_pnl, float) else None
            dpnl_str = f"{dpnl:+9.2f}" if dpnl is not None else f"{'—':>9}"
            dentr_str = f"{our['entry_price'] - tv_entry_price:+9.4f}"
            div_str = f"{div:7.4f}%"

            # flag if any divergence
            if div > 0.0001:
                divergent_rows.append((tv["no"], tv["side"], tv_entry_str, div, our, tv))
        else:
            our_ep_str = f"{'—':>9}"
            our_xp_str = f"{'—':>9}"
            tv_ep_str = f"{tv_entry_price:9.2f}"
            tv_xp_str = f"{tv_exit_price:9.2f}" if isinstance(tv_exit_price, float) else f"{'?':>9}"
            tv_pnl_str = f"{tv_pnl:9.2f}" if isinstance(tv_pnl, float) else f"{'?':>9}"
            our_pnl_str = f"{'—':>9}"
            dpnl_str = f"{'—':>9}"
            dentr_str = f"{'—':>9}"
            div_str = f"{'N/A':>7} "

        print(
            col.format(
                tv["no"],
                tv["side"],
                tv_entry_str,
                tv_ep_str,
                our_ep_str,
                tv_xp_str,
                our_xp_str,
                match_str,
                tv_exit_str,
                tv_pnl_str,
                our_pnl_str,
                dpnl_str,
                dentr_str,
                div_str,
                tv["exit_reason"],
            )
        )

    print(sep)
    print(f"Matched: {matched}/{len(tv_trades)}")

    avg_div = sum(total_div) / len(total_div) if total_div else 0
    max_div = max(total_div) if total_div else 0
    print(f"\nAvg divergence (matched trades): {avg_div:.4f}%   Max: {max_div:.4f}%")

    # Show divergent trades summary
    if divergent_rows:
        print(f"\n── Divergent trades (div > 0.0001%) ──")
        for no, side, ts, div, our, tv in sorted(divergent_rows, key=lambda x: -x[3]):
            tv_pnl = tv.get("pnl")
            dpnl = our["pnl"] - tv_pnl if isinstance(tv_pnl, float) else None
            print(
                f"  #{no:>3} {side:5} {ts}  "
                f"Δentry={our['entry_price'] - tv['entry_price']:+.4f}  "
                f"Δexit={our['exit_price'] - tv['exit_price']:+.4f}  "
                f"ΔP&L={dpnl:+.2f}  "
                f"Div={div:.4f}%"
            )
    else:
        print("\n✅ No divergences — all matched trades are 100% identical.")

    print(f"\nOur total : {len(our_trades)} trades  Net P&L: {sum(t['pnl'] for t in our_trades):.2f} USDT")
    print(
        f"TV  total : {len(tv_trades)} trades  Net P&L: {sum(t['pnl'] for t in tv_trades if isinstance(t['pnl'], float)):.2f} USDT"
    )


asyncio.run(run())
