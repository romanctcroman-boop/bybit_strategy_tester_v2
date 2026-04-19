"""
🔬 ПОЛНЫЙ ТЕСТ ВАЛИДАЦИИ АЛГОРИТМОВ
Проверка правильности расчётов на всех параметрах
FallbackEngineV2 vs NumbaEngineV2
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3
from dataclasses import fields
from datetime import datetime

import pandas as pd

print("=" * 120)
print("🔬 ПОЛНЫЙ ТЕСТ ВАЛИДАЦИИ АЛГОРИТМОВ")
print("   Проверка правильности расчётов при различных конфигурациях")
print("=" * 120)
print(f"Время: {datetime.now()}")

# ============================================================================
# КОНФИГУРАЦИИ ДЛЯ ТЕСТИРОВАНИЯ
# ============================================================================
STRATEGY_CONFIGS = [
    # 1. RSI Стратегия - Long Only
    {
        "name": "RSI Oversold Strategy",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 10000,
        "order_type": "market",
        "position_size": 0.10,
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "direction": "long",
        "pyramiding": 1,
        "taker_fee": 0.001,
        "slippage": 0.0005,
        "leverage": 10,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.0,
        "strategy_type": "momentum",
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    # 2. RSI Стратегия - Short Only
    {
        "name": "RSI Overbought Strategy",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 10000,
        "order_type": "market",
        "position_size": 0.15,
        "stop_loss": 0.025,
        "take_profit": 0.05,
        "direction": "short",
        "pyramiding": 1,
        "taker_fee": 0.001,
        "slippage": 0.0005,
        "leverage": 5,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.0,
        "strategy_type": "momentum",
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    # 3. RSI + EMA - Both Directions
    {
        "name": "RSI + EMA Crossover",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 25000,
        "order_type": "market",
        "position_size": 0.20,
        "stop_loss": 0.03,
        "take_profit": 0.06,
        "direction": "both",
        "pyramiding": 1,
        "taker_fee": 0.0008,
        "slippage": 0.0003,
        "leverage": 20,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.50,
        "strategy_type": "trend_following",
        "rsi_period": 21,
        "rsi_oversold": 25,
        "rsi_overbought": 75,
        "ema_fast": 20,
        "ema_slow": 50,
    },
    # 4. Aggressive Strategy - High Leverage
    {
        "name": "Aggressive Scalper",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 5000,
        "order_type": "market",
        "position_size": 0.25,
        "stop_loss": 0.01,
        "take_profit": 0.02,
        "direction": "both",
        "pyramiding": 1,
        "taker_fee": 0.001,
        "slippage": 0.001,
        "leverage": 50,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.0,
        "strategy_type": "scalping",
        "rsi_period": 7,
        "rsi_oversold": 20,
        "rsi_overbought": 80,
    },
    # 5. Conservative Strategy - Low Risk
    {
        "name": "Conservative Swing",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 50000,
        "order_type": "market",
        "position_size": 0.05,
        "stop_loss": 0.05,
        "take_profit": 0.10,
        "direction": "long",
        "pyramiding": 1,
        "taker_fee": 0.0006,
        "slippage": 0.0002,
        "leverage": 3,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.25,
        "strategy_type": "swing_trading",
        "rsi_period": 28,
        "rsi_oversold": 35,
        "rsi_overbought": 65,
    },
    # 6. Very Small Position
    {
        "name": "Micro Position Test",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 1000,
        "order_type": "market",
        "position_size": 0.01,
        "stop_loss": 0.015,
        "take_profit": 0.03,
        "direction": "both",
        "pyramiding": 1,
        "taker_fee": 0.001,
        "slippage": 0.0005,
        "leverage": 10,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.0,
        "strategy_type": "test",
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    # 7. Large Capital Test
    {
        "name": "Institutional Size",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 1000000,
        "order_type": "market",
        "position_size": 0.02,
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "direction": "both",
        "pyramiding": 1,
        "taker_fee": 0.0005,
        "slippage": 0.0001,
        "leverage": 5,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.15,
        "strategy_type": "institutional",
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    # 8. High Fee Environment
    {
        "name": "High Fee Test",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 10000,
        "order_type": "market",
        "position_size": 0.10,
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "direction": "both",
        "pyramiding": 1,
        "taker_fee": 0.005,  # 0.5% fee!
        "slippage": 0.002,  # 0.2% slippage
        "leverage": 10,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.0,
        "strategy_type": "high_cost",
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    # 9. Zero Fee (for testing)
    {
        "name": "Zero Fee Environment",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 10000,
        "order_type": "market",
        "position_size": 0.10,
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "direction": "both",
        "pyramiding": 1,
        "taker_fee": 0.0,
        "slippage": 0.0,
        "leverage": 10,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.0,
        "strategy_type": "no_cost",
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    # 10. Long Only Strict RSI
    {
        "name": "Strict RSI Long",
        "symbol": "BTCUSDT",
        "interval": "60",
        "initial_capital": 10000,
        "order_type": "market",
        "position_size": 0.10,
        "stop_loss": 0.015,
        "take_profit": 0.03,
        "direction": "long",
        "pyramiding": 1,
        "taker_fee": 0.001,
        "slippage": 0.0005,
        "leverage": 10,
        "bar_magnifier": False,
        "execution": "on_bar_close",
        "max_drawdown_limit": 0.0,
        "strategy_type": "strict_rsi",
        "rsi_period": 14,
        "rsi_oversold": 20,  # Very strict
        "rsi_overbought": 80,
    },
]

print(f"\n📋 КОНФИГУРАЦИЙ ДЛЯ ТЕСТИРОВАНИЯ: {len(STRATEGY_CONFIGS)}")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("\n📊 Загрузка данных...")
conn = sqlite3.connect(str(Path(__file__).resolve().parents[1] / "data.sqlite3"))
df_1h = pd.read_sql(
    """
    SELECT open_time, open_price as open, high_price as high,
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
""",
    conn,
)
df_1h["open_time"] = pd.to_datetime(df_1h["open_time"], unit="ms")
df_1h.set_index("open_time", inplace=True)

start_date = df_1h.index[0].strftime("%Y-%m-%d %H:%M")
end_date = df_1h.index[-1].strftime("%Y-%m-%d %H:%M")

print(f"   📅 Дата начала:    {start_date}")
print(f"   📅 Дата окончания: {end_date}")
print(f"   📊 Количество баров: {len(df_1h):,}")

conn.close()


# ============================================================================
# ФУНКЦИИ
# ============================================================================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ============================================================================
# ИМПОРТЫ
# ============================================================================
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.backtesting.interfaces import BacktestInput, BacktestMetrics, TradeDirection
from backend.core.extended_metrics import ExtendedMetricsCalculator

fallback = FallbackEngineV2()
numba_engine = NumbaEngineV2()
ext_calc = ExtendedMetricsCalculator()

dir_map = {
    "long": TradeDirection.LONG,
    "short": TradeDirection.SHORT,
    "both": TradeDirection.BOTH,
}

# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================
print("\n" + "=" * 120)
print("🚀 ЗАПУСК ВАЛИДАЦИИ")
print("=" * 120)

all_results = []
total_metrics_checked = 0
total_matches = 0
problems = []

for i, config in enumerate(STRATEGY_CONFIGS):
    print(f"\n{'=' * 80}")
    print(f"[{i + 1}/{len(STRATEGY_CONFIGS)}] {config['name']}")
    print(f"{'=' * 80}")

    # Показать конфигурацию
    print(f"""
   📋 КОНФИГУРАЦИЯ:
   ├─ Название:          {config["name"]}
   ├─ Торговая пара:     {config["symbol"]}
   ├─ Таймфрейм:         {config["interval"]}
   ├─ Начальный капитал: ${config["initial_capital"]:,}
   ├─ Тип ордера:        {config["order_type"]}
   ├─ Размер позиции:    {config["position_size"] * 100:.1f}%
   ├─ Стоп-лосс:         {config["stop_loss"] * 100:.1f}%
   ├─ Тейк-профит:       {config["take_profit"] * 100:.1f}%
   ├─ Режим позиций:     {config["direction"]}
   ├─ Пирамидинг:        {config["pyramiding"]}
   ├─ Комиссия:          {config["taker_fee"] * 100:.3f}%
   ├─ Проскальзывание:   {config["slippage"] * 100:.3f}%
   ├─ Плечо:             {config["leverage"]}x
   ├─ Bar Magnifier:     {config["bar_magnifier"]}
   ├─ Исполнение:        {config["execution"]}
   ├─ Лимит просадки:    {config["max_drawdown_limit"] * 100:.1f}%
   ├─ Тип стратегии:     {config["strategy_type"]}
   ├─ RSI Period:        {config["rsi_period"]}
   ├─ RSI Oversold:      {config["rsi_oversold"]}
   └─ RSI Overbought:    {config["rsi_overbought"]}
    """)

    # Генерация сигналов
    rsi = calculate_rsi(df_1h["close"], period=config["rsi_period"])

    if config.get("ema_fast") and config.get("ema_slow"):
        ema_fast = df_1h["close"].ewm(span=config["ema_fast"]).mean()
        ema_slow = df_1h["close"].ewm(span=config["ema_slow"]).mean()
        bullish = ema_fast > ema_slow
        bearish = ema_fast < ema_slow
        long_entries = ((rsi < config["rsi_oversold"]) & bullish).values
        short_entries = ((rsi > config["rsi_overbought"]) & bearish).values
    else:
        long_entries = (rsi < config["rsi_oversold"]).values
        short_entries = (rsi > config["rsi_overbought"]).values

    long_exits = (rsi > config["rsi_overbought"]).values
    short_exits = (rsi < config["rsi_oversold"]).values

    # Создание input
    input_data = BacktestInput(
        candles=df_1h,
        candles_1m=None,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        symbol=config["symbol"],
        interval=config["interval"],
        initial_capital=config["initial_capital"],
        position_size=config["position_size"],
        leverage=config["leverage"],
        stop_loss=config["stop_loss"],
        take_profit=config["take_profit"],
        direction=dir_map[config["direction"]],
        taker_fee=config["taker_fee"],
        slippage=config["slippage"],
        use_bar_magnifier=config["bar_magnifier"],
        max_drawdown_limit=config["max_drawdown_limit"],
        pyramiding=config["pyramiding"],
    )

    # Запуск обоих движков
    fb_result = fallback.run(input_data)
    nb_result = numba_engine.run(input_data)

    # Extended metrics
    fb_ext = ext_calc.calculate_all(fb_result.equity_curve, fb_result.trades)
    nb_ext = ext_calc.calculate_all(nb_result.equity_curve, nb_result.trades)

    # Сравнение ВСЕХ 147 метрик
    fb_m = fb_result.metrics
    nb_m = nb_result.metrics

    # 1. BacktestMetrics (32 поля)
    from backend.core.extended_metrics import ExtendedMetricsResult

    all_categories = []

    # BacktestMetrics
    backtest_fields = [f.name for f in fields(BacktestMetrics) if not f.name.startswith("_")]
    all_categories.append(("BacktestMetrics", backtest_fields, fb_m, nb_m))

    # ExtendedMetrics
    extended_fields = [f.name for f in fields(ExtendedMetricsResult) if not f.name.startswith("_")]
    all_categories.append(("ExtendedMetrics", extended_fields, fb_ext, nb_ext))

    config_matches = 0
    config_total = 0

    print("\n   📊 СРАВНЕНИЕ ВСЕХ МЕТРИК:")

    for cat_name, cat_fields, fb_obj, nb_obj in all_categories:
        cat_matches = 0
        cat_total = 0

        for field_name in cat_fields:
            fb_val = getattr(fb_obj, field_name, 0)
            nb_val = getattr(nb_obj, field_name, 0)

            # Проверка совпадения
            if fb_val is None and nb_val is None:
                match = True
            elif fb_val is None or nb_val is None:
                match = False
            elif (abs(float(fb_val)) < 1e-10 and abs(float(nb_val)) < 1e-10) or abs(
                float(fb_val) - float(nb_val)
            ) < 1e-6:
                match = True
            elif abs(float(fb_val)) > 1e-10:
                pct_diff = abs(float(fb_val) - float(nb_val)) / abs(float(fb_val)) * 100
                match = pct_diff < 0.001
            else:
                match = False

            cat_matches += 1 if match else 0
            cat_total += 1

            if not match:
                problems.append((config["name"], field_name, fb_val, nb_val))

        config_matches += cat_matches
        config_total += cat_total
        status = "✅" if cat_matches == cat_total else "⚠️"
        print(f"   {status} {cat_name}: {cat_matches}/{cat_total}")

    total_metrics_checked += config_total
    total_matches += config_matches

    pct = config_matches / config_total * 100 if config_total > 0 else 0
    status_icon = "✅" if pct == 100 else "⚠️"
    print(f"\n   {status_icon} ИТОГО: {config_matches}/{config_total} ({pct:.1f}%)")
    print(f"   📈 Trades: {fb_m.total_trades}, Net Profit: ${fb_m.net_profit:,.2f}")

# ============================================================================
# ФИНАЛЬНЫЙ ОТЧЁТ
# ============================================================================
print("\n" + "=" * 120)
print("📊 ФИНАЛЬНЫЙ ОТЧЁТ ВАЛИДАЦИИ")
print("=" * 120)

overall_pct = total_matches / total_metrics_checked * 100

print(f"""
   📋 ИТОГИ:
   ├─ Конфигураций протестировано: {len(STRATEGY_CONFIGS)}
   ├─ Метрик проверено:           {total_metrics_checked:,}
   ├─ Совпадений:                 {total_matches:,}
   └─ Процент совпадения:         {overall_pct:.2f}%
""")

if problems:
    print(f"   ⚠️ ОБНАРУЖЕНЫ РАСХОЖДЕНИЯ ({len(problems)}):")
    for name, field, fb, nb in problems[:10]:
        print(f"      - {name} / {field}: Fallback={fb}, Numba={nb}")
else:
    print(f"""
   ████████╗███████╗███████╗████████╗    ██████╗  █████╗ ███████╗███████╗███████╗██████╗
   ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝    ██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗
      ██║   █████╗  ███████╗   ██║       ██████╔╝███████║███████╗███████╗█████╗  ██║  ██║
      ██║   ██╔══╝  ╚════██║   ██║       ██╔═══╝ ██╔══██║╚════██║╚════██║██╔══╝  ██║  ██║
      ██║   ███████╗███████║   ██║       ██║     ██║  ██║███████║███████║███████╗██████╔╝
      ╚═╝   ╚══════╝╚══════╝   ╚═╝       ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═════╝

   🎉 100% ВАЛИДАЦИЯ ПРОЙДЕНА!

   ВСЕ {len(STRATEGY_CONFIGS)} КОНФИГУРАЦИЙ ДАЛИ ИДЕНТИЧНЫЕ РЕЗУЛЬТАТЫ!
   FallbackEngineV2 и NumbaEngineV2 ПОЛНОСТЬЮ СОГЛАСОВАНЫ!
""")

print("=" * 120)
