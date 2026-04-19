"""
🔬 Bar Magnifier Metrics Comparison Script

Сравнение метрик бэктеста с использованием внутрибаровых тиковых вычислений
(Bar Magnifier - аналог TradingView Premium) и без них.

Показывает разницу при использовании 1-минутных данных для точного
определения порядка срабатывания SL/TP внутри бара.

Created: 2026-01-24
"""

import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.interfaces import BacktestInput, TradeDirection


def load_ohlc_data(filepath: Path, timeframe: str = "15") -> pd.DataFrame:
    """Загрузка OHLC данных из CSV."""
    df = pd.read_csv(filepath)

    # Нормализация колонок
    column_map = {
        "time": "timestamp",
        "Time": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    df.rename(columns=column_map, inplace=True)

    # Parse timestamps - ensure proper datetime type
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        # Remove timezone info for consistency
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        df.set_index("timestamp", inplace=True)

    # Ensure OHLC columns are float
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def generate_rsi_signals(
    df: pd.DataFrame,
    rsi_length: int = 14,
    oversold: int = 25,
    overbought: int = 70,
) -> tuple:
    """Генерация RSI сигналов."""
    # RSI calculation (если нет в данных)
    if "RSI" not in df.columns:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=rsi_length).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_length).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

    rsi = df["RSI"].values

    # Long entry: RSI crosses above oversold
    long_entries = np.zeros(len(df), dtype=bool)
    for i in range(1, len(df)):
        if not np.isnan(rsi[i]) and not np.isnan(rsi[i - 1]) and rsi[i - 1] < oversold and rsi[i] >= oversold:
            long_entries[i] = True

    # Short entry: RSI crosses below overbought
    short_entries = np.zeros(len(df), dtype=bool)
    for i in range(1, len(df)):
        if not np.isnan(rsi[i]) and not np.isnan(rsi[i - 1]) and rsi[i - 1] > overbought and rsi[i] <= overbought:
            short_entries[i] = True

    return long_entries, short_entries


def run_backtest_comparison(
    ohlc_15m: pd.DataFrame,
    ohlc_1m: pd.DataFrame | None,
    initial_capital: float = 1_000_000.0,
    fixed_amount: float = 100.0,
    leverage: int = 10,
    take_profit: float = 0.015,
    stop_loss: float = 0.03,
    commission: float = 0.0007,
    rsi_length: int = 14,
    oversold: int = 25,
    overbought: int = 70,
) -> dict[str, Any]:
    """
    Запуск бэктеста в двух режимах: с Bar Magnifier и без.
    """
    results = {}

    # Generate signals
    long_entries, short_entries = generate_rsi_signals(ohlc_15m.copy(), rsi_length, oversold, overbought)

    # Reset index for engine
    candles = ohlc_15m.reset_index()
    candles_1m = ohlc_1m.reset_index() if ohlc_1m is not None else None

    engine = FallbackEngineV2()

    # === RUN WITHOUT BAR MAGNIFIER ===
    print("\n🔧 Запуск БЕЗ Bar Magnifier (стандартный режим)...")
    input_standard = BacktestInput(
        candles=candles,
        candles_1m=None,  # Нет 1m данных
        initial_capital=initial_capital,
        use_fixed_amount=True,
        fixed_amount=fixed_amount,
        leverage=leverage,
        take_profit=take_profit,
        stop_loss=stop_loss,
        taker_fee=commission,
        direction=TradeDirection.BOTH,
        long_entries=long_entries,
        short_entries=short_entries,
        use_bar_magnifier=False,
    )

    start = time.time()
    result_standard = engine.run(input_standard)
    time_standard = time.time() - start

    results["standard"] = {
        "metrics": result_standard.metrics,
        "trades": result_standard.trades,
        "execution_time": time_standard,
    }

    print(f"   ✅ Завершено за {time_standard:.2f}s")
    print(f"   📊 Сделок: {result_standard.metrics.total_trades}")
    print(f"   💰 Net Profit: {result_standard.metrics.net_profit:.2f} USDT")

    # === RUN WITH BAR MAGNIFIER ===
    if candles_1m is not None and len(candles_1m) > 0:
        print("\n🔬 Запуск С Bar Magnifier (внутрибаровые вычисления)...")
        input_magnifier = BacktestInput(
            candles=candles,
            candles_1m=candles_1m,
            initial_capital=initial_capital,
            use_fixed_amount=True,
            fixed_amount=fixed_amount,
            leverage=leverage,
            take_profit=take_profit,
            stop_loss=stop_loss,
            taker_fee=commission,
            direction=TradeDirection.BOTH,
            long_entries=long_entries,
            short_entries=short_entries,
            use_bar_magnifier=True,
        )

        start = time.time()
        result_magnifier = engine.run(input_magnifier)
        time_magnifier = time.time() - start

        results["magnifier"] = {
            "metrics": result_magnifier.metrics,
            "trades": result_magnifier.trades,
            "execution_time": time_magnifier,
        }

        print(f"   ✅ Завершено за {time_magnifier:.2f}s")
        print(f"   📊 Сделок: {result_magnifier.metrics.total_trades}")
        print(f"   💰 Net Profit: {result_magnifier.metrics.net_profit:.2f} USDT")
    else:
        print("\n⚠️ Нет 1-минутных данных для Bar Magnifier")
        results["magnifier"] = None

    return results


def print_comparison_report(results: dict[str, Any]):
    """Вывод отчёта сравнения."""
    print("\n" + "=" * 90)
    print("🔬 СРАВНЕНИЕ МЕТРИК: Standard vs Bar Magnifier")
    print("=" * 90)

    standard = results["standard"]["metrics"]
    magnifier = results.get("magnifier")

    if magnifier is None:
        print("\n⚠️ Bar Magnifier не был запущен (нет 1m данных)")
        print("\n📊 Результаты стандартного режима:")
        print(f"   • Сделок: {standard.total_trades}")
        print(f"   • Net Profit: {standard.net_profit:.2f} USDT")
        print(f"   • Win Rate: {standard.win_rate * 100:.2f}%")
        print(f"   • Profit Factor: {standard.profit_factor:.3f}")
        return

    mag = magnifier["metrics"]

    print(f"\n{'Метрика':<30} {'Standard':>15} {'Bar Magnifier':>15} {'Разница':>12} {'%':>10}")
    print("-" * 90)

    metrics_to_compare = [
        ("total_trades", "Всего сделок", 0),
        ("winning_trades", "Выигрышных", 0),
        ("losing_trades", "Проигрышных", 0),
        ("net_profit", "Net Profit", 2),
        ("gross_profit", "Gross Profit", 2),
        ("gross_loss", "Gross Loss", 2),
        ("win_rate", "Win Rate", 4),
        ("profit_factor", "Profit Factor", 3),
        ("max_drawdown", "Max Drawdown", 2),
        ("avg_trade", "Avg Trade", 2),
        ("avg_win", "Avg Win", 2),
        ("avg_loss", "Avg Loss", 2),
    ]

    for attr, name, decimals in metrics_to_compare:
        std_val = getattr(standard, attr, 0) or 0
        mag_val = getattr(mag, attr, 0) or 0

        if isinstance(std_val, float):
            diff = mag_val - std_val
            pct = (diff / std_val * 100) if std_val != 0 else 0

            std_str = f"{std_val:.{decimals}f}"
            mag_str = f"{mag_val:.{decimals}f}"
            diff_str = f"{diff:+.{decimals}f}"
            pct_str = f"{pct:+.2f}%"
        else:
            diff = mag_val - std_val
            pct = (diff / std_val * 100) if std_val != 0 else 0

            std_str = str(std_val)
            mag_str = str(mag_val)
            diff_str = f"{diff:+d}" if isinstance(diff, int) else f"{diff:+.0f}"
            pct_str = f"{pct:+.2f}%"

        # Highlight differences
        status = ("📊" if abs(pct) < 1 else "🔺" if diff > 0 else "🔻") if diff != 0 else "✅"

        print(f"{name:<30} {std_str:>15} {mag_str:>15} {diff_str:>12} {pct_str:>10} {status}")

    print("-" * 90)

    # Time comparison
    time_std = results["standard"]["execution_time"]
    time_mag = magnifier["execution_time"]
    slowdown = time_mag / time_std if time_std > 0 else 0

    print("\n⏱️ Время выполнения:")
    print(f"   Standard:      {time_std:.2f}s")
    print(f"   Bar Magnifier: {time_mag:.2f}s (x{slowdown:.1f} медленнее)")

    # MFE/MAE comparison for first few trades
    print("\n📈 Сравнение MFE/MAE (первые 5 сделок):")
    std_trades = results["standard"]["trades"][:5]
    mag_trades = magnifier["trades"][:5]

    print(f"{'#':<3} {'MFE Std':>12} {'MFE Mag':>12} {'MAE Std':>12} {'MAE Mag':>12}")
    print("-" * 55)
    for i, (st, mt) in enumerate(zip(std_trades, mag_trades, strict=False)):
        print(f"{i + 1:<3} {st.mfe:>12.2f} {mt.mfe:>12.2f} {st.mae:>12.2f} {mt.mae:>12.2f}")


def main():
    """Главная функция."""
    print("🔬 Bar Magnifier Metrics Comparison Script")
    print("=" * 60)

    # Paths to data files
    tv_data_dir = Path("d:/TV")
    ohlc_15m_file = tv_data_dir / "BYBIT_BTCUSDT.P, 15 (3).csv"

    # Check for 1-minute data in database
    # For now, we'll check if we can load it from TV export
    ohlc_1m_file = tv_data_dir / "BYBIT_BTCUSDT.P, 1.csv"  # If exists

    if not ohlc_15m_file.exists():
        print(f"❌ Файл не найден: {ohlc_15m_file}")
        return

    print(f"✅ Загрузка 15m данных: {ohlc_15m_file.name}")
    ohlc_15m = load_ohlc_data(ohlc_15m_file)
    print(f"   Загружено {len(ohlc_15m)} баров")

    # Try to load 1m data from database
    ohlc_1m = None
    try:
        from sqlalchemy import select

        from backend.database.connection import get_session
        from backend.database.models.kline import Kline

        print("\n🔍 Поиск 1m данных в базе...")
        with get_session() as session:
            # Get date range from 15m data
            start_date = ohlc_15m.index.min()
            end_date = ohlc_15m.index.max()

            stmt = (
                select(Kline)
                .where(Kline.symbol == "BTCUSDT")
                .where(Kline.interval == "1")
                .where(Kline.timestamp >= start_date)
                .where(Kline.timestamp <= end_date)
                .order_by(Kline.timestamp)
            )

            klines = session.execute(stmt).scalars().all()

            if klines:
                ohlc_1m = pd.DataFrame(
                    [
                        {
                            "timestamp": k.timestamp,
                            "open": k.open,
                            "high": k.high,
                            "low": k.low,
                            "close": k.close,
                            "volume": k.volume,
                        }
                        for k in klines
                    ]
                )
                ohlc_1m.set_index("timestamp", inplace=True)
                print(f"   ✅ Загружено {len(ohlc_1m)} баров 1m из базы")
            else:
                print("   ⚠️ 1m данные не найдены в базе")
    except Exception as e:
        print(f"   ⚠️ Ошибка загрузки 1m данных: {e}")

    # Also try file
    if ohlc_1m is None and ohlc_1m_file.exists():
        print(f"\n✅ Загрузка 1m данных из файла: {ohlc_1m_file.name}")
        ohlc_1m = load_ohlc_data(ohlc_1m_file)
        print(f"   Загружено {len(ohlc_1m)} баров")

    # Strategy parameters
    print("\n📋 Параметры стратегии:")
    print("   RSI: 14/25/70")
    print("   TP: 1.5%, SL: 3%")
    print("   Capital: 1,000,000 USDT")
    print("   Position: 100 USDT x 10 leverage")
    print("   Commission: 0.07%")

    # Run comparison
    results = run_backtest_comparison(
        ohlc_15m=ohlc_15m,
        ohlc_1m=ohlc_1m,
        initial_capital=1_000_000.0,
        fixed_amount=100.0,
        leverage=10,
        take_profit=0.015,
        stop_loss=0.03,
        commission=0.0007,
        rsi_length=14,
        oversold=25,
        overbought=70,
    )

    # Print report
    print_comparison_report(results)

    print("\n✅ Сравнение завершено!")

    return results


if __name__ == "__main__":
    results = main()
