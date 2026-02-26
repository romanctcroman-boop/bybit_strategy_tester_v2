"""
Full backtest of Strategy_RSI_L/S_10 with TV-exact parameters.
Compares engine results vs TV reference (as1-as5.csv).

TV Reference:
  - Initial capital: 1,000,000 USDT
  - Position size: 10% of capital
  - Leverage: 10x
  - Commission: 0.07%
  - TP: 2.3%, SL: 13.2%
  - Pyramiding: 1
  - Closed trades: 150 (29L + 121S)
  - Net profit: 1069.94 USDT
  - Win rate: 90.67% (136/150)
  - Profit factor: 1.573
  - Max DD (intrabar): 670.46 USDT
  - Avg bars in trade: 101
  - Commission paid: 210.06 USDT
"""

import asyncio
import json
import sqlite3
import sys
import warnings

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

# ── TV Reference values ──────────────────────────────────────────────────────
TV = {
    "total_trades": 150,
    "long_trades": 29,
    "short_trades": 121,
    "winning_trades": 136,
    "losing_trades": 14,
    "win_rate": 90.67,
    "net_profit": 1069.94,
    "gross_profit": 2938.78,
    "gross_loss": 1868.84,
    "profit_factor": 1.573,
    "max_dd_intrabar": 670.46,
    "commission_paid": 210.06,
    "avg_bars_in_trade": 101,
    "avg_profit_trade": 21.61,
    "avg_loss_trade": 133.49,
    "sharpe": -9.48,
    "sortino": -0.994,
}

STRATEGY_ID = "dd2969a2-bbba-410e-b190-be1e8cc50b21"
DB_PATH = r"d:\bybit_strategy_tester_v2\data.sqlite3"
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-02-24", tz="UTC")


def pct_diff(engine_val, tv_val, label):
    if tv_val == 0:
        return f"  {label:42s}  TV={tv_val}  Engine={engine_val:.4f}  (TV=0, skip)"
    diff = engine_val - tv_val
    pct = abs(diff) / abs(tv_val) * 100
    status = "OK" if pct < 1.0 else ("WARN" if pct < 5.0 else "FAIL")
    return f"  {label:42s}  TV={tv_val:>12}  Engine={engine_val:>12.4f}  diff={diff:+.4f} ({pct:.2f}%)  [{status}]"


async def main():
    svc = BacktestService()

    # ── Load strategy graph ──────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name,builder_blocks,builder_connections,builder_graph FROM strategies WHERE id=?", (STRATEGY_ID,)
    ).fetchone()
    conn.close()
    name, br, cr, gr = row
    blocks = json.loads(br) if isinstance(br, str) else (br or [])
    conns = json.loads(cr) if isinstance(cr, str) else (cr or [])
    gp = json.loads(gr) if isinstance(gr, str) else (gr or {})
    ms = gp.get("main_strategy", {})
    graph = {
        "name": name,
        "blocks": blocks,
        "connections": conns,
        "market_type": "linear",
        "direction": "both",
        "interval": "30",
    }
    if ms:
        graph["main_strategy"] = ms

    print(f"Strategy: {name}  (ID: {STRATEGY_ID})")
    print(f"  Symbol: ETHUSDT  TF: 30m  Period: 2025-01-01..2026-02-24")
    print(f"  Capital: 1,000,000  Size: 10%  Leverage: 10x  Commission: 0.07%")
    print(f"  TP: 2.3%  SL: 13.2%  Pyramiding: 1")
    print()

    # ── Fetch ETH candles (main chart instrument) ─────────────────────────────
    candles = await svc._fetch_historical_data(
        symbol="ETHUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    print(f"ETH 30m (Bybit): {len(candles)} bars  [{candles.index[0]} .. {candles.index[-1]}]")

    # ── Fetch BTC with 2020 warmup (TV source = BYBIT:BTCUSDT) ───────────────
    btc_start = pd.Timestamp("2020-01-01", tz="UTC")
    btc_warmup = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=btc_start, end_date=START_DATE
    )
    btc_main = await svc._fetch_historical_data(
        symbol="BTCUSDT", interval="30", start_date=START_DATE, end_date=END_DATE
    )
    btc_candles = pd.concat([btc_warmup, btc_main]).sort_index()
    btc_candles = btc_candles[~btc_candles.index.duplicated(keep="last")]
    print(f"BTC 30m (Bybit): {len(btc_candles)} bars (warmup from {btc_start.date()})")

    # ── Fetch BTC 1m candles for intra-bar RSI cross detection (TV parity) ──
    # TV's calc_on_every_tick evaluates RSI on each 1m tick within the 30m bar.
    # Algorithm: one-step hypothetical RSI from fixed bar k-1 state.
    btc_1m = await svc._fetch_historical_data(symbol="BTCUSDT", interval="1", start_date=START_DATE, end_date=END_DATE)
    print(f"BTC 1m  (Bybit): {len(btc_1m)} bars (for intra-bar RSI)")

    # ── Generate signals (NO intra-bar — baseline 150-trade parity) ─────────
    adapter = StrategyBuilderAdapter(graph, btcusdt_ohlcv=btc_candles, btcusdt_5m_ohlcv=None)
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
    print(f"Signals: {le.sum()} long_entries  {se.sum()} short_entries")
    print()

    # ── Run FallbackEngineV4 with TV-exact parameters ─────────────────────────
    # TV position size "10%" with capital 1M = 1000 USDT notional per trade.
    # Verified from as4.csv: position value = 999.72 USDT (0.2998 ETH * 3334.62).
    # With leverage=1: order_capital = 1M * 0.001 = 1000 USDT = notional ✅
    # Commission: 1000 * 0.0007 * 2 * 150 = 210 USDT ✅
    result = FallbackEngineV4().run(
        BacktestInput(
            candles=candles,
            long_entries=le,
            long_exits=lx,
            short_entries=se,
            short_exits=sx,
            initial_capital=1_000_000.0,
            position_size=0.001,  # 0.1% → 1000 USDT notional with leverage=1
            use_fixed_amount=False,
            leverage=1,  # no leverage multiplier (TV backtester doesn't multiply notional)
            stop_loss=0.132,  # 13.2%
            take_profit=0.023,  # 2.3%
            taker_fee=0.0007,  # 0.07%
            slippage=0.0,
            direction=TradeDirection.BOTH,
            pyramiding=1,
            interval="30",
            entry_on_next_bar_open=True,
        )
    )

    trades = result.trades
    metrics = result.metrics if hasattr(result, "metrics") and result.metrics else {}

    # ── Trade counts ──────────────────────────────────────────────────────────
    # TradeRecord fields: pnl (profit/loss), fees (commission), duration_bars
    longs = [t for t in trades if t.direction == "long"]
    shorts = [t for t in trades if t.direction == "short"]
    wins = [t for t in trades if (t.pnl or 0) > 0]
    # TV convention: END_OF_DATA trades with tiny loss are excluded from losing count
    from backend.backtesting.interfaces import ExitReason

    sl_losses = [t for t in trades if (t.pnl or 0) < 0 and t.exit_reason != ExitReason.END_OF_DATA]
    eod_losses = [t for t in trades if (t.pnl or 0) < 0 and t.exit_reason == ExitReason.END_OF_DATA]

    print("=" * 80)
    print("TRADE COUNTS:")
    count_status = "OK" if len(trades) == TV["total_trades"] else "FAIL"
    print(f"  Total closed trades:  TV={TV['total_trades']:4d}  Engine={len(trades):4d}  [{count_status}]")
    l_status = "OK" if len(longs) == TV["long_trades"] else "FAIL"
    print(f"  Long  trades:         TV={TV['long_trades']:4d}  Engine={len(longs):4d}  [{l_status}]")
    s_status = "OK" if len(shorts) == TV["short_trades"] else "FAIL"
    print(f"  Short trades:         TV={TV['short_trades']:4d}  Engine={len(shorts):4d}  [{s_status}]")
    w_status = "OK" if len(wins) == TV["winning_trades"] else "FAIL"
    print(f"  Winning trades:       TV={TV['winning_trades']:4d}  Engine={len(wins):4d}  [{w_status}]")
    lo_status = "OK" if len(sl_losses) == TV["losing_trades"] else "FAIL"
    print(f"  Losing  trades:       TV={TV['losing_trades']:4d}  Engine={len(sl_losses):4d}  [{lo_status}]")
    if eod_losses:
        print(
            f"  END_OF_DATA trades:         {len(eod_losses):4d}  (pnl={sum(t.pnl for t in eod_losses):.2f}, excluded from avg loss)"
        )

    # ── Compute metrics ───────────────────────────────────────────────────────
    if trades:
        profits = [t.pnl for t in trades if t.pnl is not None]
        gross_p = sum(p for p in profits if p > 0)
        gross_l = abs(sum(p for p in profits if p < 0))
        net_p = sum(profits)
        pf = gross_p / gross_l if gross_l > 0 else float("inf")
        # Win rate uses meaningful trades (wins + SL losses), TV convention
        wr = len(wins) / (len(wins) + len(sl_losses)) * 100 if (len(wins) + len(sl_losses)) > 0 else 0.0
        avg_win_v = gross_p / len(wins) if wins else 0.0
        # Avg loss excludes END_OF_DATA trades (TV convention)
        loss_pnl_list = [abs(t.pnl) for t in sl_losses]
        avg_loss_v = sum(loss_pnl_list) / len(loss_pnl_list) if loss_pnl_list else 0.0

        # Commission — TradeRecord.fees
        commission_paid = sum(t.fees for t in trades if t.fees is not None)

        # Avg bars in trade — TradeRecord.duration_bars
        dur_list = [t.duration_bars for t in trades if t.duration_bars is not None]
        avg_bars_val = sum(dur_list) / len(dur_list) if dur_list else float("nan")

        # Max drawdown — from result.metrics (preferred) or manual equity curve
        # result.metrics.max_drawdown is in % (e.g., 0.069 = 0.069% of capital)
        max_dd_usdt = float("nan")
        if metrics:
            for attr in ("max_drawdown_intrabar", "max_drawdown", "maxDrawdown"):
                v = getattr(metrics, attr, None) if not isinstance(metrics, dict) else metrics.get(attr)
                if v is not None:
                    # Convert from % to USDT: value_in_pct / 100 * initial_capital
                    max_dd_usdt = float(v) / 100.0 * 1_000_000.0
                    break
        if max_dd_usdt != max_dd_usdt:  # still nan — compute manually
            equity = 1_000_000.0
            peak = equity
            dd = 0.0
            for t in trades:
                equity += t.pnl or 0
                if equity > peak:
                    peak = equity
                dd = max(dd, peak - equity)
            max_dd_usdt = dd
    else:
        net_p = gross_p = gross_l = pf = wr = 0.0
        avg_win_v = avg_loss_v = commission_paid = max_dd_usdt = avg_bars_val = float("nan")

    # ── Key metrics comparison ─────────────────────────────────────────────────
    print()
    print("KEY METRICS:")
    print(pct_diff(net_p, TV["net_profit"], "Net profit (USDT)"))
    print(pct_diff(gross_p, TV["gross_profit"], "Gross profit (USDT)"))
    print(pct_diff(gross_l, TV["gross_loss"], "Gross loss (USDT)"))
    print(pct_diff(wr, TV["win_rate"], "Win rate (%)"))
    print(pct_diff(pf, TV["profit_factor"], "Profit factor"))
    print(pct_diff(max_dd_usdt, TV["max_dd_intrabar"], "Max drawdown intrabar (USDT)"))
    print(pct_diff(commission_paid, TV["commission_paid"], "Commission paid (USDT)"))
    print(pct_diff(avg_bars_val, TV["avg_bars_in_trade"], "Avg bars in trade"))
    print(pct_diff(avg_win_v, TV["avg_profit_trade"], "Avg winning trade (USDT)"))
    print(pct_diff(avg_loss_v, TV["avg_loss_trade"], "Avg losing trade (USDT)"))

    # ── Available metric attributes (debug) ───────────────────────────────────
    if metrics:
        print()
        print("ALL AVAILABLE METRICS (result.metrics):")
        if isinstance(metrics, dict):
            for k, v in sorted(metrics.items()):
                if isinstance(v, (int, float)):
                    print(f"  {k:45s} = {v}")
        else:
            for attr in sorted(dir(metrics)):
                if not attr.startswith("_"):
                    v = getattr(metrics, attr, None)
                    if isinstance(v, (int, float)):
                        print(f"  {attr:45s} = {v}")

    # ── First 10 trades ────────────────────────────────────────────────────────
    print()
    print("FIRST 10 CLOSED TRADES (engine):")
    print(
        f"  {'#':3s}  {'dir':5s}  {'entry_time':19s}  {'entry_px':10s}  {'exit_time':19s}  {'pnl':10s}  {'exit_reason':14s}  {'bars':5s}"
    )
    for i, t in enumerate(trades[:10], 1):
        et = str(t.entry_time)[:19] if t.entry_time else ""
        xt = str(t.exit_time)[:19] if t.exit_time else ""
        ep = t.entry_price or 0
        pr = t.pnl or 0
        dr = t.direction[:5] if t.direction else ""
        xr = str(t.exit_reason)[:14] if t.exit_reason else ""
        db = t.duration_bars or 0
        print(f"  {i:3d}  {dr:5s}  {et:19s}  {ep:10.2f}  {xt:19s}  {pr:10.4f}  {xr:14s}  {db:5d}")

    print()
    print("=" * 80)
    diff = TV["total_trades"] - len(trades)
    print(f"RESULT: engine={len(trades)}  TV={TV['total_trades']}  diff={diff:+d}")
    if diff == 0:
        print("TRADE COUNT MATCHES TV!")
    else:
        print(f"Trade count off by {abs(diff)}.")
    print("=" * 80)

    # ══════════════════════════════════════════════════════════════════════════
    # TRADE-BY-TRADE COMPARISON vs as4.csv
    # ══════════════════════════════════════════════════════════════════════════
    import os

    as4_path = r"c:\Users\roman\Downloads\as4.csv"
    if not os.path.exists(as4_path):
        print("\n[SKIP] as4.csv not found — trade comparison skipped")
    else:
        tv_df = pd.read_csv(as4_path, sep=";")

        # Parse entries and exits from TV
        tv_entries = tv_df[tv_df["Тип"].str.contains("Entry|Вход", case=False, na=False)].copy()
        tv_exits = tv_df[tv_df["Тип"].str.contains("Exit|Выход", case=False, na=False)].copy()
        tv_entries = tv_entries.sort_values("№ Сделки").reset_index(drop=True)
        tv_exits = tv_exits.sort_values("№ Сделки").reset_index(drop=True)

        # Convert Moscow time (UTC+3) to UTC
        tv_entries["ts_utc"] = pd.to_datetime(tv_entries["Дата и время"]) - pd.Timedelta(hours=3)
        tv_exits["ts_utc"] = pd.to_datetime(tv_exits["Дата и время"]) - pd.Timedelta(hours=3)

        def tv_side(row):
            s = str(row.get("Сигнал", ""))
            t = str(row.get("Тип", ""))
            if "short" in t.lower() or "коротк" in t.lower() or "RsiSE" in s:
                return "short"
            if "long" in t.lower() or "длинн" in t.lower() or "RsiLE" in s:
                return "long"
            return "?"

        def tv_exit_reason(row):
            s = str(row.get("Сигнал", ""))
            if "TP" in s or "Достигнут" in s:
                return "TP"
            if "SL" in s or "Стоп" in s:
                return "SL"
            if "RsiLX" in s or "RsiSX" in s:
                return "signal"
            return s[:20]

        tv_entries["side"] = tv_entries.apply(tv_side, axis=1)
        tv_exits["exit_reason_tv"] = tv_exits.apply(tv_exit_reason, axis=1)

        # Parse TV pnl
        def parse_float(val):
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(",", ".").replace("\xa0", "").strip())

        tv_exits["pnl_tv"] = tv_exits["Чистая прибыль / убыток USDT"].apply(parse_float)
        tv_entries["entry_px_tv"] = tv_entries["Цена USDT"].apply(parse_float)
        tv_exits["exit_px_tv"] = tv_exits["Цена USDT"].apply(parse_float)
        tv_entries["pos_size_tv"] = tv_entries["Размер позиции (кол-во)"].apply(parse_float)
        tv_exits["cum_pnl_tv"] = tv_exits["Совокупные ПР/УБ USDT"].apply(parse_float)

        print()
        print("=" * 120)
        print("TRADE-BY-TRADE COMPARISON: Engine vs TV (as4.csv)")
        print("=" * 120)

        n = min(len(trades), len(tv_entries), len(tv_exits))
        header = (
            f"{'#':>3}  {'dir_e':5} {'dir_tv':6} {'d_ok':4}  "
            f"{'entry_e':>19}  {'entry_tv':>19}  {'t_ok':4}  "
            f"{'exit_e':>19}  {'exit_tv':>19}  {'xt_ok':5}  "
            f"{'epx_e':>10} {'epx_tv':>10} {'xpx_e':>10} {'xpx_tv':>10}  "
            f"{'pnl_e':>10} {'pnl_tv':>10} {'pnl_d':>10}  "
            f"{'xr_e':>8} {'xr_tv':>8}"
        )
        print(header)
        print("-" * 120)

        diverge_list = []
        cum_pnl_engine = 0.0

        for i in range(n):
            t = trades[i]
            tv_e = tv_entries.iloc[i]
            tv_x = tv_exits.iloc[i]

            # Engine values
            e_dir = t.direction[:5]
            e_et = str(t.entry_time)[:19].replace("T", " ")
            e_xt = str(t.exit_time)[:19].replace("T", " ")
            e_ep = t.entry_price or 0
            e_xp = t.exit_price or 0
            e_pnl = t.pnl or 0
            e_xr = str(t.exit_reason).split(".")[-1][:8] if t.exit_reason else ""
            cum_pnl_engine += e_pnl

            # TV values
            tv_dir = tv_e["side"]
            tv_et = str(tv_e["ts_utc"])[:19]
            tv_xt = str(tv_x["ts_utc"])[:19]
            tv_ep = tv_e["entry_px_tv"]
            tv_xp = tv_x["exit_px_tv"]
            tv_pnl = tv_x["pnl_tv"]
            tv_xr = tv_x["exit_reason_tv"]

            # Checks
            d_ok = e_dir == tv_dir[:5]
            t_ok = e_et == tv_et
            xt_ok = e_xt == tv_xt
            pnl_d = e_pnl - tv_pnl

            is_diverged = not d_ok or not t_ok or not xt_ok or abs(pnl_d) > 0.5

            marker = ""
            if is_diverged:
                diverge_list.append(i + 1)
                marker = " <---"

            print(
                f"{i + 1:3d}  {e_dir:5} {tv_dir:6} {'OK' if d_ok else 'FAIL':4}  "
                f"{e_et:19}  {tv_et:19}  {'OK' if t_ok else 'FAIL':4}  "
                f"{e_xt:19}  {tv_xt:19}  {'OK' if xt_ok else 'FAIL':5}  "
                f"{e_ep:10.2f} {tv_ep:10.2f} {e_xp:10.2f} {tv_xp:10.2f}  "
                f"{e_pnl:10.4f} {tv_pnl:10.4f} {pnl_d:+10.4f}  "
                f"{e_xr:>8} {tv_xr:>8}{marker}"
            )

        print()
        print(f"Total divergences: {len(diverge_list)} at trades: {diverge_list}")
        print(f"Cumulative PnL engine: {cum_pnl_engine:.4f}  TV: {tv_exits.iloc[n - 1]['cum_pnl_tv']:.4f}")

        # Summary of divergence categories
        dir_mismatches = []
        time_mismatches = []
        exit_mismatches = []
        pnl_mismatches = []
        for i in range(n):
            t = trades[i]
            tv_e = tv_entries.iloc[i]
            tv_x = tv_exits.iloc[i]
            e_dir = t.direction[:5]
            tv_dir = tv_e["side"][:5]
            e_et = str(t.entry_time)[:19].replace("T", " ")
            tv_et = str(tv_e["ts_utc"])[:19]
            e_xt = str(t.exit_time)[:19].replace("T", " ")
            tv_xt = str(tv_x["ts_utc"])[:19]
            e_pnl = t.pnl or 0
            tv_pnl = tv_x["pnl_tv"]
            if e_dir != tv_dir:
                dir_mismatches.append(i + 1)
            if e_et != tv_et:
                time_mismatches.append(i + 1)
            if e_xt != tv_xt:
                exit_mismatches.append(i + 1)
            if abs(e_pnl - tv_pnl) > 0.5:
                pnl_mismatches.append(i + 1)

        print(f"\nDirection mismatches ({len(dir_mismatches)}): {dir_mismatches}")
        print(f"Entry time mismatches ({len(time_mismatches)}): {time_mismatches}")
        print(f"Exit time mismatches ({len(exit_mismatches)}): {exit_mismatches}")
        print(f"PnL mismatches >0.5 USDT ({len(pnl_mismatches)}): {pnl_mismatches}")

    print("\nDone.")


asyncio.run(main())
