"""
Calibrate FallbackEngineV4 - Reference Engine Calibration Test.

This script tests the reference backtesting engine with various parameter
configurations to find profitable settings and validate metric calculations.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)


def load_btc_data(
    start_date: datetime, end_date: datetime, interval: str = "15"
) -> pd.DataFrame:
    """Load BTCUSDT data from database."""
    db_path = Path("data.sqlite3")
    conn = sqlite3.connect(str(db_path))

    query = f"""
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT'
        AND interval = '{interval}'
        AND open_time >= {int(start_date.timestamp() * 1000)}
        AND open_time < {int(end_date.timestamp() * 1000)}
        ORDER BY open_time
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if len(df) > 0:
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df.set_index("open_time", inplace=True)

    return df


def generate_rsi_signals(
    candles: pd.DataFrame,
    period: int = 14,
    overbought: int = 70,
    oversold: int = 30,
    direction: str = "both",
) -> tuple:
    """Generate RSI-based entry/exit signals."""
    close = candles["close"].values

    # Calculate RSI
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    # EMA for RSI
    avg_gain = np.zeros_like(gain, dtype=np.float64)
    avg_loss = np.zeros_like(loss, dtype=np.float64)

    # Initialize
    avg_gain[period] = np.mean(gain[1 : period + 1])
    avg_loss[period] = np.mean(loss[1 : period + 1])

    # Calculate EMA
    alpha = 1.0 / period
    for i in range(period + 1, len(close)):
        avg_gain[i] = alpha * gain[i] + (1 - alpha) * avg_gain[i - 1]
        avg_loss[i] = alpha * loss[i] + (1 - alpha) * avg_loss[i - 1]

    # RSI
    rs = np.where(avg_loss > 0, avg_gain / avg_loss, 0)
    rsi = 100 - (100 / (1 + rs))

    # Generate signals
    n = len(candles)
    long_entries = np.zeros(n, dtype=bool)
    long_exits = np.zeros(n, dtype=bool)
    short_entries = np.zeros(n, dtype=bool)
    short_exits = np.zeros(n, dtype=bool)

    # Simple RSI strategy
    for i in range(period + 1, n):
        if direction in ("long", "both"):
            # Long entry: RSI crosses above oversold
            if rsi[i - 1] < oversold and rsi[i] >= oversold:
                long_entries[i] = True
            # Long exit: RSI crosses below overbought
            if rsi[i - 1] > overbought and rsi[i] <= overbought:
                long_exits[i] = True

        if direction in ("short", "both"):
            # Short entry: RSI crosses below overbought
            if rsi[i - 1] > overbought and rsi[i] <= overbought:
                short_entries[i] = True
            # Short exit: RSI crosses above oversold
            if rsi[i - 1] < oversold and rsi[i] >= oversold:
                short_exits[i] = True

    return long_entries, long_exits, short_entries, short_exits


def run_backtest(
    candles: pd.DataFrame,
    direction: str = "long",
    tp_pct: float = 0.02,
    sl_pct: float = 0.01,
    leverage: int = 10,
    use_atr: bool = False,
    atr_multiplier: float = 2.0,
    rsi_period: int = 14,
    rsi_overbought: int = 70,
    rsi_oversold: int = 30,
) -> dict:
    """Run backtest using FallbackEngineV4."""
    from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
    from backend.backtesting.interfaces import (
        BacktestInput,
        SlMode,
        TpMode,
        TradeDirection,
    )

    # Generate signals
    long_entries, long_exits, short_entries, short_exits = generate_rsi_signals(
        candles,
        period=rsi_period,
        overbought=rsi_overbought,
        oversold=rsi_oversold,
        direction=direction,
    )

    # Map direction
    dir_map = {
        "long": TradeDirection.LONG,
        "short": TradeDirection.SHORT,
        "both": TradeDirection.BOTH,
    }
    trade_dir = dir_map.get(direction, TradeDirection.BOTH)

    # Build input
    input_data = BacktestInput(
        candles=candles,
        candles_1m=None,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        symbol="BTCUSDT",
        interval="15",
        initial_capital=10000.0,
        position_size=0.10,  # 10% per trade
        leverage=leverage,
        direction=trade_dir,
        take_profit=tp_pct if not use_atr else 0.05,  # 5% default for ATR mode
        stop_loss=sl_pct if not use_atr else 0.03,  # 3% default for ATR mode
        tp_mode=TpMode.ATR if use_atr else TpMode.FIXED,
        sl_mode=SlMode.ATR if use_atr else SlMode.FIXED,
        atr_period=14,
        atr_tp_multiplier=atr_multiplier,
        atr_sl_multiplier=atr_multiplier * 0.5,
        taker_fee=0.0007,  # 0.07% - TradingView parity
        slippage=0.0005,
        use_bar_magnifier=False,
    )

    # Run backtest
    engine = FallbackEngineV4()
    output = engine.run(input_data)

    metrics = output.metrics
    return {
        "strategy": f"{direction}_rsi",
        "direction": direction,
        "total_trades": metrics.total_trades,
        "winning_trades": metrics.winning_trades,
        "losing_trades": metrics.losing_trades,
        "win_rate": metrics.win_rate,
        "net_profit": metrics.net_profit,
        "total_return": metrics.total_return,
        "max_drawdown": metrics.max_drawdown,
        "sharpe_ratio": metrics.sharpe_ratio,
        "profit_factor": metrics.profit_factor,
        "avg_trade": metrics.net_profit / max(metrics.total_trades, 1),
    }


def main():
    logger.info("=" * 70)
    logger.info("🔧 REFERENCE ENGINE CALIBRATION")
    logger.info("=" * 70)

    # Load data
    start_date = datetime(2025, 6, 1)
    end_date = datetime(2026, 1, 27)

    logger.info(f"\n📥 Loading data: {start_date.date()} to {end_date.date()}")
    candles = load_btc_data(start_date, end_date, "15")
    logger.info(f"Loaded {len(candles)} candles")

    # Price change during period
    start_price = candles.iloc[0]["close"]
    end_price = candles.iloc[-1]["close"]
    price_change = ((end_price / start_price) - 1) * 100
    logger.info(f"BTC: ${start_price:.2f} -> ${end_price:.2f} ({price_change:+.2f}%)")
    logger.info(
        f"📉 Period trend: {'BEARISH' if price_change < -5 else 'BULLISH' if price_change > 5 else 'SIDEWAYS'}"
    )

    # Test configurations
    configs = [
        # Long strategies with different parameters
        {
            "direction": "long",
            "tp_pct": 0.015,
            "sl_pct": 0.01,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
        },
        {
            "direction": "long",
            "tp_pct": 0.02,
            "sl_pct": 0.015,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
        },
        {
            "direction": "long",
            "tp_pct": 0.03,
            "sl_pct": 0.015,
            "rsi_oversold": 25,
            "rsi_overbought": 80,
        },
        # Short strategies (should perform better in bear market)
        {
            "direction": "short",
            "tp_pct": 0.015,
            "sl_pct": 0.01,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
        },
        {
            "direction": "short",
            "tp_pct": 0.02,
            "sl_pct": 0.015,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
        },
        {
            "direction": "short",
            "tp_pct": 0.03,
            "sl_pct": 0.015,
            "rsi_oversold": 20,
            "rsi_overbought": 75,
        },
        # Both directions
        {
            "direction": "both",
            "tp_pct": 0.02,
            "sl_pct": 0.01,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
        },
        {
            "direction": "both",
            "tp_pct": 0.025,
            "sl_pct": 0.0125,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
        },
        # ATR-based
        {
            "direction": "long",
            "use_atr": True,
            "atr_multiplier": 2.0,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
        },
        {
            "direction": "short",
            "use_atr": True,
            "atr_multiplier": 2.0,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
        },
        {
            "direction": "both",
            "use_atr": True,
            "atr_multiplier": 2.5,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
        },
    ]

    results = []
    logger.info("\n" + "=" * 70)
    logger.info("🧪 RUNNING CALIBRATION TESTS")
    logger.info("=" * 70)

    for i, config in enumerate(configs, 1):
        try:
            result = run_backtest(candles, **config)
            results.append(result)

            status = "✅" if result["net_profit"] > 0 else "❌"
            logger.info(
                f"\n{status} Test {i}: {result['strategy']} ({config.get('direction', 'both')})\n"
                f"   Trades: {result['total_trades']} | WR: {result['win_rate']:.1f}%\n"
                f"   PnL: ${result['net_profit']:.2f} ({result['total_return']:.2f}%)\n"
                f"   DD: {result['max_drawdown']:.2f}% | Sharpe: {result['sharpe_ratio']:.2f}\n"
                f"   PF: {result['profit_factor']:.2f}"
            )
        except Exception as e:
            logger.error(f"Test {i} failed: {e}")
            import traceback

            traceback.print_exc()

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 CALIBRATION SUMMARY")
    logger.info("=" * 70)

    profitable = [r for r in results if r["net_profit"] > 0]
    logger.info(f"\nProfitable strategies: {len(profitable)}/{len(results)}")

    if profitable:
        # Sort by profit factor
        profitable.sort(key=lambda x: x["profit_factor"], reverse=True)
        logger.info("\n🏆 Top Profitable Strategies:")
        for i, r in enumerate(profitable[:5], 1):
            logger.info(
                f"  {i}. {r['strategy']}: ${r['net_profit']:.2f} | "
                f"WR: {r['win_rate']:.1f}% | PF: {r['profit_factor']:.2f} | "
                f"Sharpe: {r['sharpe_ratio']:.2f}"
            )
    else:
        logger.warning(
            "\n⚠️ No profitable strategies found - market conditions unfavorable"
        )
        # Show best performers even if unprofitable
        results.sort(key=lambda x: x.get("net_profit", -float("inf")), reverse=True)
        logger.info("\n📈 Best performing (least loss):")
        for i, r in enumerate(results[:3], 1):
            logger.info(
                f"  {i}. {r['strategy']}: ${r['net_profit']:.2f} | "
                f"WR: {r['win_rate']:.1f}%"
            )

    # Recommendations
    logger.info("\n" + "=" * 70)
    logger.info("📝 RECOMMENDATIONS FOR DCA STRATEGIES")
    logger.info("=" * 70)

    if price_change < -10:
        logger.info("\n🐻 BEAR MARKET DETECTED - Recommended settings:")
        logger.info("  - Prefer SHORT direction or hedge mode")
        logger.info("  - Use wider SL (3-5%) to avoid stop hunting")
        logger.info("  - Smaller TP (1-2%) for quick profits")
        logger.info("  - More Safety Orders (5-8) for averaging")
    elif price_change > 10:
        logger.info("\n🐂 BULL MARKET DETECTED - Recommended settings:")
        logger.info("  - Prefer LONG direction")
        logger.info("  - Standard SL (2-3%)")
        logger.info("  - Larger TP (2-4%) to catch trends")
    else:
        logger.info("\n📊 SIDEWAYS MARKET - Recommended settings:")
        logger.info("  - Use BOTH directions for range trading")
        logger.info("  - Tight SL (1-2%)")
        logger.info("  - Quick TP (0.5-1.5%)")
        logger.info("  - Multi-TP for partial profit taking")


if __name__ == "__main__":
    main()
