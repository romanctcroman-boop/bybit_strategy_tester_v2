"""
🔬 ТЕСТ INTRABAR ВЫЧИСЛЕНИЙ (Bar Magnifier, Ticks, Subticks)
Проверяет точность внутри-баровых расчётов SL/TP
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
from datetime import datetime

import pandas as pd

print("=" * 120)
print("🔬 ТЕСТ INTRABAR ВЫЧИСЛЕНИЙ (Bar Magnifier, Precise Intrabar)")
print("=" * 120)
print(f"Время: {datetime.now()}")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("\n📊 Загрузка данных...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))

# 1H данные
df_1h = pd.read_sql(
    """
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 500
""",
    conn,
)
df_1h["open_time"] = pd.to_datetime(df_1h["open_time"], unit="ms")
df_1h.set_index("open_time", inplace=True)

# 1M данные (для Bar Magnifier - 60 subticks per hour bar)
df_1m = pd.read_sql(
    f"""
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '1'
    AND open_time >= {int(df_1h.index[0].timestamp() * 1000)}
    AND open_time <= {int(df_1h.index[-1].timestamp() * 1000)}
    ORDER BY open_time ASC
""",
    conn,
)
df_1m["open_time"] = pd.to_datetime(df_1m["open_time"], unit="ms")
df_1m.set_index("open_time", inplace=True)
conn.close()

print(f"   📅 Период: {df_1h.index[0]} — {df_1h.index[-1]}")
print(f"   📊 1H баров: {len(df_1h)}")
print(f"   📊 1M баров (subticks): {len(df_1m)}")
print(f"   📊 Subticks per bar: ~{len(df_1m) / len(df_1h):.0f}")


# ============================================================================
# RSI СИГНАЛЫ
# ============================================================================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


rsi = calculate_rsi(df_1h["close"], period=7)
long_entries = (rsi < 30).values
long_exits = (rsi > 70).values
short_entries = (rsi > 70).values
short_exits = (rsi < 30).values

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, ExitReason, TradeDirection
from backend.core.extended_metrics import ExtendedMetricsCalculator

# ============================================================================
# ТЕСТЫ
# ============================================================================
print("\n" + "=" * 120)
print("🔬 СРАВНЕНИЕ: БЕЗ BAR MAGNIFIER vs С BAR MAGNIFIER")
print("=" * 120)

# Общие параметры
base_config = {
    "symbol": "BTCUSDT",
    "interval": "60",
    "initial_capital": 10000.0,
    "position_size": 0.15,
    "leverage": 20,
    "stop_loss": 0.015,  # 1.5% SL - tight для intrabar hits
    "take_profit": 0.025,  # 2.5% TP
    "direction": TradeDirection.BOTH,
    "taker_fee": 0.001,
    "slippage": 0.0005,
}

fallback = FallbackEngineV2()
numba_engine = NumbaEngineV2()
ext_calc = ExtendedMetricsCalculator()

# Тест 1: Без Bar Magnifier
print("\n" + "-" * 80)
print("📊 РЕЖИМ 1: Стандартный (без Bar Magnifier)")
print("-" * 80)

input_no_bm = BacktestInput(
    candles=df_1h,
    candles_1m=None,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    use_bar_magnifier=False,
    **base_config,
)

fb_no_bm = fallback.run(input_no_bm)
nb_no_bm = numba_engine.run(input_no_bm)

print(f"   Fallback:  {len(fb_no_bm.trades)} trades, Net Profit: ${fb_no_bm.metrics.net_profit:,.2f}")
print(f"   Numba:     {len(nb_no_bm.trades)} trades, Net Profit: ${nb_no_bm.metrics.net_profit:,.2f}")


# Анализ exit reasons
def analyze_exits(trades, name):
    sl_count = sum(1 for t in trades if t.exit_reason == ExitReason.STOP_LOSS)
    tp_count = sum(1 for t in trades if t.exit_reason == ExitReason.TAKE_PROFIT)
    signal_count = sum(1 for t in trades if t.exit_reason == ExitReason.SIGNAL)
    eod_count = sum(1 for t in trades if t.exit_reason == ExitReason.END_OF_DATA)
    intrabar_sl = sum(1 for t in trades if getattr(t, "intrabar_sl_hit", False))
    intrabar_tp = sum(1 for t in trades if getattr(t, "intrabar_tp_hit", False))

    print(f"\n   {name} Exit Analysis:")
    print(f"   ├─ Stop Loss:     {sl_count} ({sl_count / len(trades) * 100:.1f}%)" if trades else "")
    print(f"   ├─ Take Profit:   {tp_count} ({tp_count / len(trades) * 100:.1f}%)" if trades else "")
    print(f"   ├─ Signal Exit:   {signal_count}")
    print(f"   ├─ End of Data:   {eod_count}")
    print(f"   ├─ Intrabar SL:   {intrabar_sl}")
    print(f"   └─ Intrabar TP:   {intrabar_tp}")

    return {
        "sl": sl_count,
        "tp": tp_count,
        "signal": signal_count,
        "intrabar_sl": intrabar_sl,
        "intrabar_tp": intrabar_tp,
    }


no_bm_fb_exits = analyze_exits(fb_no_bm.trades, "Fallback")
no_bm_nb_exits = analyze_exits(nb_no_bm.trades, "Numba")

# Тест 2: С Bar Magnifier
print("\n" + "-" * 80)
print("📊 РЕЖИМ 2: Bar Magnifier (Precise Intrabar, 60 subticks)")
print("-" * 80)

input_with_bm = BacktestInput(
    candles=df_1h,
    candles_1m=df_1m,
    long_entries=long_entries,
    long_exits=long_exits,
    short_entries=short_entries,
    short_exits=short_exits,
    use_bar_magnifier=True,
    **base_config,
)

fb_with_bm = fallback.run(input_with_bm)
nb_with_bm = numba_engine.run(input_with_bm)

print(f"   Fallback:  {len(fb_with_bm.trades)} trades, Net Profit: ${fb_with_bm.metrics.net_profit:,.2f}")
print(f"   Numba:     {len(nb_with_bm.trades)} trades, Net Profit: ${nb_with_bm.metrics.net_profit:,.2f}")

bm_fb_exits = analyze_exits(fb_with_bm.trades, "Fallback")
bm_nb_exits = analyze_exits(nb_with_bm.trades, "Numba")

# ============================================================================
# СРАВНЕНИЕ МЕТРИК
# ============================================================================
print("\n" + "=" * 120)
print("📊 СРАВНЕНИЕ МЕТРИК: БЕЗ BM vs С BM")
print("=" * 120)


def compare_metrics(m1, m2, name1, name2):
    print(f"\n{'Метрика':<30} {name1:>20} {name2:>20} {'Разница':>15}")
    print("-" * 90)

    metrics_to_compare = [
        ("total_trades", "Total Trades"),
        ("net_profit", "Net Profit ($)"),
        ("total_return", "Total Return (%)"),
        ("win_rate", "Win Rate"),
        ("profit_factor", "Profit Factor"),
        ("max_drawdown", "Max Drawdown (%)"),
        ("sharpe_ratio", "Sharpe Ratio"),
        ("sortino_ratio", "Sortino Ratio"),
        ("avg_win", "Avg Win ($)"),
        ("avg_loss", "Avg Loss ($)"),
    ]

    for attr, label in metrics_to_compare:
        v1 = getattr(m1, attr, 0) or 0
        v2 = getattr(m2, attr, 0) or 0

        if isinstance(v1, int):
            diff = v2 - v1
            print(f"{label:<30} {v1:>20} {v2:>20} {diff:>+15}")
        else:
            diff = v2 - v1
            print(f"{label:<30} {v1:>20.4f} {v2:>20.4f} {diff:>+15.4f}")


print("\n📈 FALLBACK ENGINE:")
compare_metrics(fb_no_bm.metrics, fb_with_bm.metrics, "Без BM", "С BM")

print("\n📈 NUMBA ENGINE:")
compare_metrics(nb_no_bm.metrics, nb_with_bm.metrics, "Без BM", "С BM")

# ============================================================================
# ПРОВЕРКА PARITY С BAR MAGNIFIER
# ============================================================================
print("\n" + "=" * 120)
print("🔬 ПРОВЕРКА PARITY: Fallback vs Numba (с Bar Magnifier)")
print("=" * 120)

metrics_to_check = [
    "net_profit",
    "total_return",
    "gross_profit",
    "gross_loss",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "total_trades",
    "winning_trades",
    "losing_trades",
    "win_rate",
    "profit_factor",
    "avg_win",
    "avg_loss",
    "avg_trade",
    "largest_win",
    "largest_loss",
    "expectancy",
    "payoff_ratio",
]

matches = 0
total = len(metrics_to_check)

print(f"\n{'Метрика':<25} {'Fallback':>18} {'Numba':>18} {'Match':>8}")
print("-" * 75)

for metric in metrics_to_check:
    fb_val = getattr(fb_with_bm.metrics, metric, 0) or 0
    nb_val = getattr(nb_with_bm.metrics, metric, 0) or 0

    # Сравнение с tolerance
    if (
        (abs(fb_val) < 1e-10 and abs(nb_val) < 1e-10)
        or abs(fb_val - nb_val) < 1e-6
        or (abs(fb_val) > 1e-10 and abs(fb_val - nb_val) / abs(fb_val) < 0.0001)
    ):
        match = True
    else:
        match = False

    if match:
        matches += 1

    status = "✅" if match else "❌"

    if isinstance(fb_val, int):
        print(f"{metric:<25} {fb_val:>18} {nb_val:>18} {status:>8}")
    else:
        print(f"{metric:<25} {fb_val:>18.6f} {nb_val:>18.6f} {status:>8}")

print("-" * 75)
print(f"{'ИТОГО':<25} {'':>18} {'':>18} {matches}/{total}")

# ============================================================================
# ДЕТАЛЬНЫЙ АНАЛИЗ INTRABAR HITS
# ============================================================================
print("\n" + "=" * 120)
print("🎯 ДЕТАЛЬНЫЙ АНАЛИЗ INTRABAR SL/TP HITS")
print("=" * 120)


def analyze_intrabar_detail(trades, name):
    if not trades:
        print(f"\n   {name}: Нет сделок")
        return

    intrabar_sl = [t for t in trades if getattr(t, "intrabar_sl_hit", False)]
    intrabar_tp = [t for t in trades if getattr(t, "intrabar_tp_hit", False)]

    print(f"\n   {name}:")
    print(f"   ├─ Всего сделок:           {len(trades)}")
    print(f"   ├─ Intrabar SL hits:       {len(intrabar_sl)} ({len(intrabar_sl) / len(trades) * 100:.1f}%)")
    print(f"   └─ Intrabar TP hits:       {len(intrabar_tp)} ({len(intrabar_tp) / len(trades) * 100:.1f}%)")

    if intrabar_sl:
        print("\n   Примеры Intrabar SL (первые 3):")
        for t in intrabar_sl[:3]:
            print(f"      Entry: {t.entry_time}, Exit: {t.exit_time}, PnL: ${t.pnl:.2f}")

    if intrabar_tp:
        print("\n   Примеры Intrabar TP (первые 3):")
        for t in intrabar_tp[:3]:
            print(f"      Entry: {t.entry_time}, Exit: {t.exit_time}, PnL: ${t.pnl:.2f}")


analyze_intrabar_detail(fb_with_bm.trades, "Fallback (BM)")
analyze_intrabar_detail(nb_with_bm.trades, "Numba (BM)")

# ============================================================================
# ФИНАЛЬНЫЙ ВЕРДИКТ
# ============================================================================
print("\n" + "=" * 120)
print("📊 ФИНАЛЬНЫЙ ВЕРДИКТ")
print("=" * 120)

# Проверяем основные критерии
trades_match = len(fb_with_bm.trades) == len(nb_with_bm.trades)
pnl_match = abs(fb_with_bm.metrics.net_profit - nb_with_bm.metrics.net_profit) < 0.01
metrics_pct = matches / total * 100

print(f"""
   🔬 INTRABAR / BAR MAGNIFIER ТЕСТ:

   ├─ Режим:                   Precise Intrabar (60 subticks/bar)
   ├─ 1M данных использовано:  {len(df_1m):,} баров
   ├─ Trades совпадают:        {"✅" if trades_match else "❌"} (FB: {len(fb_with_bm.trades)}, NB: {len(nb_with_bm.trades)})
   ├─ Net Profit совпадает:    {"✅" if pnl_match else "❌"} (FB: ${fb_with_bm.metrics.net_profit:.2f}, NB: ${nb_with_bm.metrics.net_profit:.2f})
   ├─ Метрики совпадают:       {matches}/{total} ({metrics_pct:.1f}%)
   └─ Exit Reasons (BM):
      ├─ FB:  SL={bm_fb_exits["sl"]}, TP={bm_fb_exits["tp"]}, Signal={bm_fb_exits["signal"]}
      └─ NB:  SL={bm_nb_exits["sl"]}, TP={bm_nb_exits["tp"]}, Signal={bm_nb_exits["signal"]}
""")

if trades_match and pnl_match and metrics_pct >= 95:
    print("""
    ✅ INTRABAR ВЫЧИСЛЕНИЯ РАБОТАЮТ КОРРЕКТНО!
    ✅ Bar Magnifier точно определяет момент срабатывания SL/TP
    ✅ Fallback и Numba дают идентичные результаты с 1M данными
    """)
else:
    print("""
    ⚠️ Обнаружены расхождения в intrabar вычислениях
    """)

print("=" * 120)
