"""
🔬 Engine Parity Verification Script

Проверяет, что все движки backtesting (Fallback, Numba, GPU) 
дают идентичные результаты на одних и тех же данных.

Использует RSI стратегию с фиксированными параметрами для теста.

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

from backend.backtesting.interfaces import BacktestInput, TradeDirection


def load_ohlc_data(filepath: Path) -> pd.DataFrame:
    """Загрузка OHLC данных из CSV."""
    df = pd.read_csv(filepath)

    column_map = {
        'time': 'timestamp',
        'Time': 'timestamp',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume',
    }
    df.rename(columns=column_map, inplace=True)

    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    elif isinstance(df.index, pd.DatetimeIndex):
        df['timestamp'] = df.index.to_numpy()

    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def load_tv_signals():
    """Load pre-extracted TradingView signals from .npy files."""
    tv_data_dir = Path("d:/TV")

    long_signals = np.load(tv_data_dir / "long_signals.npy")
    short_signals = np.load(tv_data_dir / "short_signals.npy")

    print(f"📥 Loaded TV signals: {long_signals.sum()} long, {short_signals.sum()} short")

    return long_signals, short_signals


def run_with_engine(
    engine,
    engine_name: str,
    candles: pd.DataFrame,
    long_entries: np.ndarray,
    short_entries: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Запуск бэктеста с конкретным движком."""
    print(f"\n🔧 {engine_name}...", end=" ", flush=True)

    try:
        input_data = BacktestInput(
            candles=candles,
            candles_1m=None,
            initial_capital=config['initial_capital'],
            use_fixed_amount=True,
            fixed_amount=config['fixed_amount'],
            leverage=config['leverage'],
            take_profit=config['take_profit'],
            stop_loss=config['stop_loss'],
            taker_fee=config['commission'],
            direction=TradeDirection.BOTH,
            long_entries=long_entries,
            short_entries=short_entries,
            use_bar_magnifier=False,
        )

        start = time.time()
        result = engine.run(input_data)
        elapsed = time.time() - start

        print(f"✅ {elapsed:.3f}s")

        return {
            'engine': engine_name,
            'elapsed': elapsed,
            'metrics': result.metrics,
            'trades': result.trades,
            'success': True,
            'error': None,
        }
    except Exception as e:
        print(f"❌ {e}")
        return {
            'engine': engine_name,
            'elapsed': 0,
            'metrics': None,
            'trades': [],
            'success': False,
            'error': str(e),
        }


def compare_results(results: list[dict[str, Any]]) -> dict[str, bool]:
    """Сравнить результаты всех движков."""
    # Найдём первый успешный результат как эталон
    baseline = None
    for r in results:
        if r['success']:
            baseline = r
            break

    if baseline is None:
        print("\n❌ Нет успешных результатов для сравнения!")
        return {}

    print(f"\n📊 Эталон: {baseline['engine']}")
    parity = {}

    for r in results:
        if not r['success']:
            parity[r['engine']] = False
            continue

        if r['engine'] == baseline['engine']:
            parity[r['engine']] = True
            continue

        # Сравним метрики
        bm = baseline['metrics']
        rm = r['metrics']

        matches = True
        diffs = []

        # Ключевые метрики для сравнения
        metrics_to_check = [
            ('total_trades', 'Всего сделок', 0),
            ('net_profit', 'Net Profit', 0.01),
            ('gross_profit', 'Gross Profit', 0.01),
            ('gross_loss', 'Gross Loss', 0.01),
            ('winning_trades', 'Winning Trades', 0),
            ('losing_trades', 'Losing Trades', 0),
            ('win_rate', 'Win Rate', 0.01),
            ('profit_factor', 'Profit Factor', 0.001),
            ('max_drawdown', 'Max Drawdown', 0.01),
        ]

        for attr, name, tolerance in metrics_to_check:
            bv = getattr(bm, attr, 0) or 0
            rv = getattr(rm, attr, 0) or 0

            if isinstance(bv, (int,)) and tolerance == 0:
                if bv != rv:
                    matches = False
                    diffs.append(f"{name}: {bv} vs {rv}")
            else:
                if abs(bv - rv) > tolerance:
                    matches = False
                    diffs.append(f"{name}: {bv:.4f} vs {rv:.4f}")

        parity[r['engine']] = matches

        if not matches:
            print(f"\n⚠️ {r['engine']} расхождения:")
            for d in diffs:
                print(f"   • {d}")

    return parity


def print_comparison_table(results: list[dict[str, Any]]):
    """Вывести таблицу сравнения."""
    print("\n" + "=" * 100)
    print("📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ ДВИЖКОВ")
    print("=" * 100)

    # Заголовок
    headers = ['Метрика'] + [r['engine'] for r in results if r['success']]
    header_line = f"{'Метрика':<25}" + "".join(f"{h:>18}" for h in headers[1:])
    print(f"\n{header_line}")
    print("-" * 100)

    # Метрики
    metrics_display = [
        ('total_trades', 'Всего сделок', 0),
        ('net_profit', 'Net Profit', 2),
        ('gross_profit', 'Gross Profit', 2),
        ('gross_loss', 'Gross Loss', 2),
        ('winning_trades', 'Прибыльных', 0),
        ('losing_trades', 'Убыточных', 0),
        ('win_rate', 'Win Rate %', 2),
        ('profit_factor', 'Profit Factor', 3),
        ('max_drawdown', 'Max Drawdown', 2),
        ('avg_trade', 'Avg Trade', 2),
    ]

    for attr, name, decimals in metrics_display:
        row = f"{name:<25}"
        for r in results:
            if not r['success']:
                continue
            val = getattr(r['metrics'], attr, 0) or 0
            if decimals == 0:
                row += f"{int(val):>18}"
            else:
                row += f"{val:>18.{decimals}f}"
        print(row)

    print("-" * 100)

    # Время выполнения
    print("\n⏱️ Время выполнения:")
    for r in results:
        if r['success']:
            print(f"   {r['engine']}: {r['elapsed']:.3f}s")


def main():
    """Главная функция."""
    print("🔬 Engine Parity Verification Script")
    print("=" * 60)

    # Загрузка полных OHLC данных
    tv_data_dir = Path("d:/TV")
    ohlc_file = tv_data_dir / "BYBIT_BTCUSDT.P_15m_full.csv"

    if not ohlc_file.exists():
        print(f"❌ Файл не найден: {ohlc_file}")
        print("   Запустите scripts/download_15m_ohlc.py для скачивания")
        return None, {}

    print(f"✅ Загрузка данных: {ohlc_file.name}")
    ohlc_df = load_ohlc_data(ohlc_file)
    print(f"   {len(ohlc_df)} баров")

    # Загрузка реальных TV сигналов
    print("\n📈 Загрузка TradingView сигналов...")
    try:
        long_entries, short_entries = load_tv_signals()
    except FileNotFoundError:
        print("❌ Файлы сигналов не найдены. Запустите scripts/extract_tv_signals.py")
        return None, {}

    # Конфигурация стратегии
    config = {
        'initial_capital': 1_000_000.0,
        'fixed_amount': 100.0,
        'leverage': 10,
        'take_profit': 0.015,
        'stop_loss': 0.03,
        'commission': 0.0007,
    }

    print("\n📋 Параметры стратегии:")
    print(f"   TP: {config['take_profit']*100}%, SL: {config['stop_loss']*100}%")
    print(f"   Leverage: {config['leverage']}x, Commission: {config['commission']*100}%")

    # Подготовка данных для движков
    candles = ohlc_df.reset_index(drop=True)
    if 'timestamp' not in candles.columns and candles.index.name == 'timestamp':
        candles = candles.reset_index()

    results = []

    # === FALLBACK ENGINE V2 ===
    try:
        from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
        engine = FallbackEngineV2()
        result = run_with_engine(
            engine, "FallbackEngineV2", candles, long_entries, short_entries, config
        )
        results.append(result)
    except ImportError as e:
        print(f"\n⚠️ FallbackEngineV2 не доступен: {e}")

    # === NUMBA ENGINE V2 ===
    try:
        from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
        engine = NumbaEngineV2()
        result = run_with_engine(
            engine, "NumbaEngineV2", candles, long_entries, short_entries, config
        )
        results.append(result)
    except ImportError as e:
        print(f"\n⚠️ NumbaEngineV2 не доступен: {e}")
    except Exception as e:
        print(f"\n⚠️ NumbaEngineV2 ошибка: {e}")

    # === GPU ENGINE V2 ===
    try:
        from backend.backtesting.engines.gpu_engine_v2 import GPUEngineV2
        engine = GPUEngineV2()
        result = run_with_engine(
            engine, "GPUEngineV2", candles, long_entries, short_entries, config
        )
        results.append(result)
    except ImportError as e:
        print(f"\n⚠️ GPUEngineV2 не доступен: {e}")
    except Exception as e:
        print(f"\n⚠️ GPUEngineV2 ошибка: {e}")

    # === FALLBACK ENGINE V3 ===
    try:
        from backend.backtesting.engines.fallback_engine_v3 import FallbackEngineV3
        engine = FallbackEngineV3()
        result = run_with_engine(
            engine, "FallbackEngineV3", candles, long_entries, short_entries, config
        )
        results.append(result)
    except ImportError as e:
        print(f"\n⚠️ FallbackEngineV3 не доступен: {e}")
    except Exception as e:
        print(f"\n⚠️ FallbackEngineV3 ошибка: {e}")

    if not results:
        print("\n❌ Ни один движок не запустился!")
        return

    # Таблица сравнения
    print_comparison_table(results)

    # Проверка parity
    parity = compare_results(results)

    # Итог
    print("\n" + "=" * 100)
    print("📋 ИТОГ ПРОВЕРКИ PARITY")
    print("=" * 100)

    all_match = True
    for engine, match in parity.items():
        status = "✅ MATCH" if match else "❌ MISMATCH"
        print(f"   {engine}: {status}")
        if not match:
            all_match = False

    if all_match:
        print("\n🎉 ВСЕ ДВИЖКИ ПОКАЗЫВАЮТ ИДЕНТИЧНЫЕ РЕЗУЛЬТАТЫ!")
    else:
        print("\n⚠️ ОБНАРУЖЕНЫ РАСХОЖДЕНИЯ МЕЖДУ ДВИЖКАМИ!")

    print("=" * 100)

    return results, parity


if __name__ == "__main__":
    results, parity = main()
