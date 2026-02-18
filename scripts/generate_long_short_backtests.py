"""
Generate test backtests for Long-only and Short-only to verify chart rendering.
Uses the backtest engine directly with a simple EMA crossover strategy.
"""

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_ema_signals(df: pd.DataFrame, direction: str, fast: int = 9, slow: int = 21) -> pd.DataFrame:
    """Generate EMA crossover signals.

    direction: 'long', 'short', or 'both'
    Signal: 1=long entry, -1=short entry, 0=no action
    """
    data = df.copy()

    # Calculate EMAs
    data["ema_fast"] = data["close"].ewm(span=fast, adjust=False).mean()
    data["ema_slow"] = data["close"].ewm(span=slow, adjust=False).mean()

    # Cross detection
    data["cross_up"] = (data["ema_fast"] > data["ema_slow"]) & (data["ema_fast"].shift(1) <= data["ema_slow"].shift(1))
    data["cross_down"] = (data["ema_fast"] < data["ema_slow"]) & (
        data["ema_fast"].shift(1) >= data["ema_slow"].shift(1)
    )

    # Generate signals based on direction
    data["signal"] = 0
    if direction in ("long", "both"):
        data.loc[data["cross_up"], "signal"] = 1
    if direction in ("short", "both"):
        data.loc[data["cross_down"], "signal"] = -1

    return data


async def run_backtest_direct(direction: str, symbol: str = "BTCUSDT", interval: str = "15") -> dict | None:
    """Run backtest directly using FallbackEngineV4."""
    from backend.backtesting.engines.fallback_engine_v4 import BacktestInput, FallbackEngineV4
    from backend.database import SessionLocal
    from backend.database.repository.kline_repository import KlineRepository

    start_date = datetime(2025, 1, 10, tzinfo=UTC)
    end_date = datetime(2025, 2, 10, tzinfo=UTC)
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    # Fetch klines from DB
    with SessionLocal() as session:
        repo = KlineRepository(session)
        klines = repo.get_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_ts,
            end_time=end_ts,
            limit=100000,
            ascending=True,
            market_type="linear",
        )

    if not klines:
        print(f"  ERROR: No klines found for {symbol}/{interval}")
        return None

    print(f"  Loaded {len(klines)} candles from DB")

    # Convert to DataFrame
    df = pd.DataFrame(
        [
            {
                "open": float(k.open_price),
                "high": float(k.high_price),
                "low": float(k.low_price),
                "close": float(k.close_price),
                "volume": float(k.volume),
            }
            for k in klines
        ]
    )
    df.index = pd.DatetimeIndex([datetime.fromtimestamp(float(k.open_time) / 1000, tz=UTC) for k in klines])

    # Generate signals
    df = generate_ema_signals(df, direction=direction, fast=9, slow=21)
    signal_count = (df["signal"] != 0).sum()
    long_signals = (df["signal"] == 1).sum()
    short_signals = (df["signal"] == -1).sum()
    print(f"  Signals: {signal_count} total ({long_signals} long, {short_signals} short)")

    if signal_count == 0:
        print("  WARNING: No signals generated!")

    # Build boolean signal arrays for FallbackEngineV4
    n = len(df)
    long_entry = np.zeros(n, dtype=bool)
    long_exit = np.zeros(n, dtype=bool)
    short_entry = np.zeros(n, dtype=bool)
    short_exit = np.zeros(n, dtype=bool)

    if direction in ("long", "both"):
        long_entry = (df["signal"] == 1).values
        long_exit = (df["signal"] == -1).values  # exit long on short signal
    if direction in ("short", "both"):
        short_entry = (df["signal"] == -1).values
        short_exit = (df["signal"] == 1).values  # exit short on long signal

    # Map direction string to enum
    from backend.backtesting.interfaces import TradeDirection

    dir_map = {"long": TradeDirection.LONG, "short": TradeDirection.SHORT, "both": TradeDirection.BOTH}

    # Build BacktestInput
    bi = BacktestInput(
        candles=df[["open", "high", "low", "close", "volume"]],
        long_entries=long_entry,
        long_exits=long_exit,
        short_entries=short_entry,
        short_exits=short_exit,
        symbol=symbol,
        interval=interval,
        initial_capital=10000.0,
        position_size=1.0,
        leverage=10,
        stop_loss=0.03,
        take_profit=0.05,
        direction=dir_map.get(direction, TradeDirection.BOTH),
        taker_fee=0.0007,
        maker_fee=0.0002,
        slippage=0.0005,
    )

    # Run engine
    engine = FallbackEngineV4()
    result = engine.run(bi)

    trades_raw = result.trades if hasattr(result, "trades") else []
    metrics_raw = result.metrics if hasattr(result, "metrics") else None

    # Convert trades to dicts (include mfe/mae for excursion bars)
    trades: list[dict[str, Any]] = []
    for tr in trades_raw:
        # Get side/direction
        if hasattr(tr, "side"):
            side_val = tr.side.value if hasattr(tr.side, "value") else str(tr.side)
        elif hasattr(tr, "direction"):
            side_val = tr.direction.value if hasattr(tr.direction, "value") else str(tr.direction)
        else:
            side_val = direction

        td = {
            "entry_time": str(tr.entry_time) if hasattr(tr, "entry_time") else "",
            "exit_time": str(tr.exit_time) if hasattr(tr, "exit_time") else "",
            "entry_price": float(tr.entry_price) if hasattr(tr, "entry_price") else 0,
            "exit_price": float(tr.exit_price) if hasattr(tr, "exit_price") else 0,
            "side": side_val,
            "size": float(tr.size) if hasattr(tr, "size") else 0,
            "pnl": float(tr.pnl) if hasattr(tr, "pnl") else 0,
            "pnl_pct": float(tr.pnl_pct) if hasattr(tr, "pnl_pct") else 0,
            "fees": float(tr.fees) if hasattr(tr, "fees") else 0,
            "duration_bars": int(tr.bars_in_trade) if hasattr(tr, "bars_in_trade") else 0,
            # MFE/MAE for trade excursion bars (critical for chart rendering)
            "mfe": float(tr.mfe) if hasattr(tr, "mfe") else 0,
            "mae": float(tr.mae) if hasattr(tr, "mae") else 0,
        }
        trades.append(td)

    # Convert metrics to dict
    metrics = {}
    if metrics_raw:
        for field_name in vars(metrics_raw):
            val = getattr(metrics_raw, field_name)
            if isinstance(val, (int, float, str, bool, type(None))):
                metrics[field_name] = val

    # Build equity curve in dict-of-arrays format (one entry per trade exit)
    # Format: {"timestamps": [ISO strings], "equity": [], "drawdown": [],
    #          "bh_equity": [], "bh_drawdown": [], "returns": [], "runup": []}
    equity_curve = None
    if hasattr(result, "equity_curve") and result.equity_curve is not None:
        ec = result.equity_curve

        # Extract per-bar equity values from engine result
        if isinstance(ec, np.ndarray):
            equity_per_bar = ec.tolist()
        elif isinstance(ec, pd.DataFrame) and "equity" in ec.columns:
            equity_per_bar = ec["equity"].tolist()
        elif isinstance(ec, list):
            # Already a list of floats or dicts
            equity_per_bar = [p.get("equity", 0) for p in ec] if ec and isinstance(ec[0], dict) else ec
        else:
            equity_per_bar = []

        if equity_per_bar and trades:
            # Build dict-of-arrays at trade exit timestamps only
            bar_timestamps = list(df.index[: len(equity_per_bar)])  # DatetimeIndex

            # Build Buy & Hold equity curve (full series, one per bar)
            initial_capital = 10000.0
            first_close = float(df["close"].iloc[0])
            bh_equity_per_bar = [
                initial_capital * (float(df["close"].iloc[i]) / first_close) for i in range(len(equity_per_bar))
            ]

            # Calculate drawdown per bar for strategy
            peak_equity = equity_per_bar[0]
            dd_per_bar = []
            for ev in equity_per_bar:
                peak_equity = max(peak_equity, ev)
                dd = ((ev - peak_equity) / peak_equity * 100) if peak_equity > 0 else 0
                dd_per_bar.append(round(dd, 4))

            # Calculate drawdown per bar for Buy & Hold
            peak_bh = bh_equity_per_bar[0]
            bh_dd_per_bar = []
            for bv in bh_equity_per_bar:
                peak_bh = max(peak_bh, bv)
                dd = ((bv - peak_bh) / peak_bh * 100) if peak_bh > 0 else 0
                bh_dd_per_bar.append(round(dd, 4))

            # Create timestamp -> bar index mapping for fast lookup
            ts_to_idx = {}
            for i, ts in enumerate(bar_timestamps):
                ts_iso = ts.isoformat()
                # Store multiple normalizations for matching
                ts_to_idx[ts_iso] = i
                ts_to_idx[ts_iso.replace("+00:00", "")] = i
                ts_to_idx[ts_iso.replace("+00:00", "Z")] = i

            # Collect data at each trade exit point
            exit_timestamps = []
            exit_equity = []
            exit_drawdown = []
            exit_bh_equity = []
            exit_bh_drawdown = []
            exit_returns = []

            for td_item in trades:
                exit_time_str = str(td_item.get("exit_time", ""))
                if not exit_time_str:
                    continue

                # Find bar index for this exit time
                idx = ts_to_idx.get(exit_time_str)
                if idx is None:
                    # Try normalizing the trade exit time
                    normalized = exit_time_str.replace("+00:00", "").replace("Z", "")
                    idx = ts_to_idx.get(normalized)
                if idx is None:
                    # Fallback: search for closest timestamp
                    try:
                        exit_dt = pd.Timestamp(exit_time_str)
                        diffs = [(abs((ts - exit_dt).total_seconds()), i) for i, ts in enumerate(bar_timestamps)]
                        idx = min(diffs, key=lambda x: x[0])[1]
                    except Exception:
                        continue

                exit_timestamps.append(bar_timestamps[idx].strftime("%Y-%m-%dT%H:%M:%S"))
                exit_equity.append(round(equity_per_bar[idx], 2))
                exit_drawdown.append(dd_per_bar[idx])
                exit_bh_equity.append(round(bh_equity_per_bar[idx], 2))
                exit_bh_drawdown.append(bh_dd_per_bar[idx])
                exit_returns.append(round(float(td_item.get("return_pct", 0)), 4))

            equity_curve = {
                "timestamps": exit_timestamps,
                "equity": exit_equity,
                "drawdown": exit_drawdown,
                "bh_equity": exit_bh_equity,
                "bh_drawdown": exit_bh_drawdown,
                "returns": exit_returns,
                "runup": [],
            }
            print(f"  Equity curve: {len(exit_timestamps)} points (one per trade exit)")
        elif equity_per_bar:
            # No trades - use start and end points
            equity_curve = {
                "timestamps": [
                    df.index[0].strftime("%Y-%m-%dT%H:%M:%S"),
                    df.index[-1].strftime("%Y-%m-%dT%H:%M:%S"),
                ],
                "equity": [round(equity_per_bar[0], 2), round(equity_per_bar[-1], 2)],
                "drawdown": [0, 0],
                "bh_equity": [],
                "bh_drawdown": [],
                "returns": [],
                "runup": [],
            }

    print(f"  Trades: {len(trades)}")
    net_profit = float(metrics.get("net_profit", 0) or 0)
    print(f"  Net P&L: ${net_profit:.2f}")

    # Save to DB
    backtest_id = str(uuid.uuid4())
    from backend.database.models.backtest import Backtest, BacktestStatus

    with SessionLocal() as session:
        bt = Backtest(
            id=backtest_id,
            strategy_type="custom",
            status=BacktestStatus.COMPLETED,
            symbol=symbol,
            timeframe=interval,
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0,
            parameters={
                "fast_ema": 9,
                "slow_ema": 21,
                "direction": direction,
                "_direction": direction,
                "strategy_params": {"fast_ema": 9, "slow_ema": 21, "direction": direction},
            },
            # Performance metrics
            total_return=metrics.get("total_return"),
            net_profit=metrics.get("net_profit"),
            net_profit_pct=metrics.get("net_profit_pct"),
            gross_profit=metrics.get("gross_profit"),
            gross_loss=metrics.get("gross_loss"),
            max_drawdown=metrics.get("max_drawdown"),
            sharpe_ratio=metrics.get("sharpe_ratio"),
            sortino_ratio=metrics.get("sortino_ratio"),
            win_rate=metrics.get("win_rate"),
            profit_factor=metrics.get("profit_factor"),
            total_trades=len(trades),
            winning_trades=metrics.get("winning_trades"),
            losing_trades=metrics.get("losing_trades"),
            avg_trade_pnl=metrics.get("avg_trade"),
            best_trade=metrics.get("largest_win"),
            worst_trade=metrics.get("largest_loss"),
            final_capital=10000.0 + float(metrics.get("net_profit") or 0),
            total_commission=metrics.get("total_commission"),
            long_trades=metrics.get("long_trades"),
            short_trades=metrics.get("short_trades"),
            long_pnl=metrics.get("long_profit"),
            short_pnl=metrics.get("short_profit"),
            # JSON blobs
            equity_curve=equity_curve,
            trades=trades,
            metrics_json=metrics,
        )
        session.add(bt)
        session.commit()
        print(f"  Saved: {backtest_id}")

    return {
        "id": backtest_id,
        "direction": direction,
        "trades": len(trades),
        "net_profit": metrics.get("net_profit", 0),
    }


async def main():
    print("=" * 60)
    print("Generate Long-only & Short-only Backtests (EMA Crossover)")
    print("=" * 60)

    long_result = None
    short_result = None

    # LONG-only
    print("\n--- LONG-only backtest ---")
    try:
        long_result = await run_backtest_direct("long")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback

        traceback.print_exc()

    # SHORT-only
    print("\n--- SHORT-only backtest ---")
    try:
        short_result = await run_backtest_direct("short")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback

        traceback.print_exc()

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    if long_result:
        print(
            f"  LONG:  {long_result['trades']} trades, "
            f"P&L=${long_result['net_profit']:.2f}, ID={long_result['id'][:12]}..."
        )
    if short_result:
        print(
            f"  SHORT: {short_result['trades']} trades, "
            f"P&L=${short_result['net_profit']:.2f}, ID={short_result['id'][:12]}..."
        )
    print("\nOpen http://localhost:8000/frontend/backtest-results.html to view")
    print("Press Ctrl+Shift+R in browser to force-reload JS")


if __name__ == "__main__":
    asyncio.run(main())
