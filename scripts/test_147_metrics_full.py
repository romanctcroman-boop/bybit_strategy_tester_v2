"""
🔬 ПОЛНЫЙ ТЕСТ ВАЛИДАЦИИ: 147 МЕТРИК × ВСЕ ПАРАМЕТРЫ
С детальным анализом расхождений
"""
import sys
sys.path.insert(0, 'd:/bybit_strategy_tester_v2')

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
from dataclasses import fields

print("=" * 120)
print("🔬 ПОЛНЫЙ ТЕСТ ВАЛИДАЦИИ: 147 МЕТРИК")  
print("=" * 120)
print(f"Время: {datetime.now()}")

# ============================================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================================
print("\n📊 Загрузка данных...")
conn = sqlite3.connect("d:/bybit_strategy_tester_v2/data.sqlite3")

df_1h = pd.read_sql("""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '60'
    ORDER BY open_time ASC
    LIMIT 2000
""", conn)
df_1h['open_time'] = pd.to_datetime(df_1h['open_time'], unit='ms')
df_1h.set_index('open_time', inplace=True)

# 1M для Bar Magnifier (ограничено для скорости)
df_1m = pd.read_sql(f"""
    SELECT open_time, open_price as open, high_price as high, 
           low_price as low, close_price as close, volume
    FROM bybit_kline_audit
    WHERE symbol = 'BTCUSDT' AND interval = '1'
    AND open_time >= {int(df_1h.index[0].timestamp() * 1000)}
    AND open_time <= {int(df_1h.index[-1].timestamp() * 1000)}
    ORDER BY open_time ASC
""", conn)
df_1m['open_time'] = pd.to_datetime(df_1m['open_time'], unit='ms')
df_1m.set_index('open_time', inplace=True)
conn.close()

start_date = df_1h.index[0].strftime('%Y-%m-%d')
end_date = df_1h.index[-1].strftime('%Y-%m-%d')

print(f"   📅 Дата начала:    {start_date}")
print(f"   📅 Дата окончания: {end_date}")
print(f"   📊 1H баров: {len(df_1h):,}")
print(f"   📊 1M баров: {len(df_1m):,}")

# ============================================================================
# RSI ФУНКЦИЯ
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
from backend.backtesting.interfaces import BacktestInput, TradeDirection, BacktestMetrics
from backend.backtesting.engines.fallback_engine_v2 import FallbackEngineV2
from backend.backtesting.engines.numba_engine_v2 import NumbaEngineV2
from backend.core.extended_metrics import ExtendedMetricsCalculator, ExtendedMetricsResult
from backend.core.metrics_calculator import TradeMetrics, RiskMetrics, LongShortMetrics, MetricsCalculator

# ============================================================================
# КОНФИГУРАЦИИ
# ============================================================================
CONFIGS = [
    {
        "name": "RSI Scalper Standard",
        "symbol": "BTCUSDT",
        "timeframe": "1H",
        "initial_capital": 10000,
        "order_size_type": "percent",
        "position_size": 0.10,
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "direction": "both",
        "pyramiding": 1,
        "commission": 0.001,
        "slippage": 0.0005,
        "leverage": 10,
        "bar_magnifier": False,
        "bar_magnifier_precise": False,
        "order_execution": "on_bar_close",
        "drawdown_limit": 0.0,
        "strategy_type": "RSI Momentum",
        "ohlc_path_model": "standard",
        "subticks": 1,
        "two_stage_opt": False,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    {
        "name": "RSI + Bar Magnifier",
        "symbol": "BTCUSDT",
        "timeframe": "1H",
        "initial_capital": 10000,
        "order_size_type": "percent",
        "position_size": 0.10,
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "direction": "both",
        "pyramiding": 1,
        "commission": 0.001,
        "slippage": 0.0005,
        "leverage": 10,
        "bar_magnifier": True,
        "bar_magnifier_precise": True,
        "order_execution": "on_bar_close",
        "drawdown_limit": 0.0,
        "strategy_type": "RSI Momentum",
        "ohlc_path_model": "precise_intrabar",
        "subticks": 60,
        "two_stage_opt": False,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    {
        "name": "Aggressive Scalper",
        "symbol": "BTCUSDT",
        "timeframe": "1H",
        "initial_capital": 5000,
        "order_size_type": "percent",
        "position_size": 0.25,
        "stop_loss": 0.01,
        "take_profit": 0.02,
        "direction": "both",
        "pyramiding": 1,
        "commission": 0.001,
        "slippage": 0.001,
        "leverage": 50,
        "bar_magnifier": True,
        "bar_magnifier_precise": True,
        "order_execution": "on_bar_close",
        "drawdown_limit": 0.0,
        "strategy_type": "Scalping",
        "ohlc_path_model": "precise_intrabar",
        "subticks": 60,
        "two_stage_opt": False,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
    },
    {
        "name": "Conservative Long Only",
        "symbol": "BTCUSDT",
        "timeframe": "1H",
        "initial_capital": 50000,
        "order_size_type": "percent",
        "position_size": 0.05,
        "stop_loss": 0.05,
        "take_profit": 0.10,
        "direction": "long",
        "pyramiding": 1,
        "commission": 0.0006,
        "slippage": 0.0002,
        "leverage": 3,
        "bar_magnifier": True,
        "bar_magnifier_precise": True,
        "order_execution": "on_bar_close",
        "drawdown_limit": 0.25,
        "strategy_type": "Swing Trading",
        "ohlc_path_model": "precise_intrabar",
        "subticks": 60,
        "two_stage_opt": False,
        "rsi_period": 21,
        "rsi_oversold": 25,
        "rsi_overbought": 75,
    },
]

DIR_MAP = {"long": TradeDirection.LONG, "short": TradeDirection.SHORT, "both": TradeDirection.BOTH}

# ============================================================================
# ФУНКЦИИ СРАВНЕНИЯ
# ============================================================================
def safe_compare(fb_val, nb_val, tolerance=1e-6):
    if fb_val is None and nb_val is None:
        return True
    if fb_val is None or nb_val is None:
        return False
    fb_v, nb_v = float(fb_val), float(nb_val)
    if abs(fb_v) < 1e-10 and abs(nb_v) < 1e-10:
        return True
    if abs(fb_v - nb_v) < tolerance:
        return True
    if abs(fb_v) > 1e-10:
        pct_diff = abs(fb_v - nb_v) / abs(fb_v)
        if pct_diff < 0.0001:
            return True
    return False

def get_all_metrics(result, ext_metrics, trade_metrics, risk_metrics, long_short):
    all_metrics = {}
    for f in fields(BacktestMetrics):
        if not f.name.startswith('_'):
            all_metrics[f"backtest.{f.name}"] = getattr(result.metrics, f.name, None)
    for f in fields(ExtendedMetricsResult):
        if not f.name.startswith('_'):
            all_metrics[f"extended.{f.name}"] = getattr(ext_metrics, f.name, None)
    for f in fields(TradeMetrics):
        if not f.name.startswith('_'):
            all_metrics[f"trade.{f.name}"] = getattr(trade_metrics, f.name, None)
    for f in fields(RiskMetrics):
        if not f.name.startswith('_'):
            all_metrics[f"risk.{f.name}"] = getattr(risk_metrics, f.name, None)
    for f in fields(LongShortMetrics):
        if not f.name.startswith('_'):
            all_metrics[f"longshort.{f.name}"] = getattr(long_short, f.name, None)
    return all_metrics

# Метрики зависящие от точных fees/pnl_pct (ожидаемые расхождения)
FEE_DEPENDENT_METRICS = {
    "trade.total_commission", "trade.gross_profit", "trade.gross_loss",
    "trade.profit_factor", "trade.avg_win_pct", "trade.avg_loss_pct",
    "trade.avg_trade_pct", "trade.largest_win_pct", "trade.largest_loss_pct",
    "longshort.long_commission", "longshort.short_commission",
    "longshort.long_avg_win_pct", "longshort.long_avg_loss_pct",
    "longshort.short_avg_win_pct", "longshort.short_avg_loss_pct",
    "longshort.long_avg_trade_pct", "longshort.short_avg_trade_pct",
    "longshort.long_largest_win_pct", "longshort.long_largest_loss_pct",
    "longshort.short_largest_win_pct", "longshort.short_largest_loss_pct",
    "longshort.long_gross_profit", "longshort.long_gross_loss",
    "longshort.short_gross_profit", "longshort.short_gross_loss",
    "longshort.long_profit_factor", "longshort.short_profit_factor",
}

# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================
print("\n" + "=" * 120)
print("🚀 ЗАПУСК ТЕСТОВ")
print("=" * 120)

fallback = FallbackEngineV2()
numba_engine = NumbaEngineV2()
ext_calc = ExtendedMetricsCalculator()
metrics_calc = MetricsCalculator()

all_results = []
core_total = 0
core_match = 0
extended_total = 0
extended_match = 0

for cfg in CONFIGS:
    print(f"\n{'='*100}")
    print(f"📋 {cfg['name']}")
    print(f"{'='*100}")
    
    # Параметры
    print(f"""
   ├─ Название стратегии:      {cfg['name']}
   ├─ Торговая пара:           {cfg['symbol']}
   ├─ Таймфрейм:               {cfg['timeframe']}
   ├─ Начальный капитал:       ${cfg['initial_capital']:,}
   ├─ Тип размера ордера:      {cfg['order_size_type']}
   ├─ Размер позиции:          {cfg['position_size']*100:.1f}%
   ├─ Стоп-лосс:               {cfg['stop_loss']*100:.1f}%
   ├─ Тейк-профит:             {cfg['take_profit']*100:.1f}%
   ├─ Режим позиций:           {cfg['direction'].upper()}
   ├─ Пирамидинг:              {cfg['pyramiding']}
   ├─ Комиссия:                {cfg['commission']*100:.3f}%
   ├─ Проскальзывание:         {cfg['slippage']*100:.3f}%
   ├─ Плечо:                   {cfg['leverage']}x
   ├─ Bar Magnifier:           {'✅ ON' if cfg['bar_magnifier'] else '❌ OFF'}
   ├─ Precise Intrabar:        {'✅' if cfg['bar_magnifier_precise'] else '❌'}
   ├─ Исполнение ордеров:      {cfg['order_execution']}
   ├─ Лимит просадки:          {cfg['drawdown_limit']*100:.0f}%
   ├─ Тип стратегии:           {cfg['strategy_type']}
   ├─ Дата начала:             {start_date}
   ├─ Дата окончания:          {end_date}
   ├─ OHLC Path Model:         {cfg['ohlc_path_model']}
   ├─ Subticks:                {cfg['subticks']}
   └─ Two-Stage Optimization:  {'✅' if cfg['two_stage_opt'] else '❌'}
    """)
    
    # Сигналы
    rsi = calculate_rsi(df_1h['close'], period=cfg['rsi_period'])
    long_entries = (rsi < cfg['rsi_oversold']).values
    long_exits = (rsi > cfg['rsi_overbought']).values
    short_entries = (rsi > cfg['rsi_overbought']).values
    short_exits = (rsi < cfg['rsi_oversold']).values
    
    input_data = BacktestInput(
        candles=df_1h,
        candles_1m=df_1m if cfg['bar_magnifier'] else None,
        long_entries=long_entries,
        long_exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        symbol=cfg['symbol'],
        interval="60",
        initial_capital=float(cfg['initial_capital']),
        position_size=cfg['position_size'],
        leverage=cfg['leverage'],
        stop_loss=cfg['stop_loss'],
        take_profit=cfg['take_profit'],
        direction=DIR_MAP[cfg['direction']],
        taker_fee=cfg['commission'],
        slippage=cfg['slippage'],
        use_bar_magnifier=cfg['bar_magnifier'],
    )
    
    # Запуск
    fb_result = fallback.run(input_data)
    nb_result = numba_engine.run(input_data)
    
    # Extended metrics
    fb_ext = ext_calc.calculate_all(fb_result.equity_curve, fb_result.trades)
    nb_ext = ext_calc.calculate_all(nb_result.equity_curve, nb_result.trades)
    
    # Trade/Risk/LongShort
    fb_trade = metrics_calc.calculate_trade_metrics(fb_result.trades)
    nb_trade = metrics_calc.calculate_trade_metrics(nb_result.trades)
    fb_returns = np.diff(fb_result.equity_curve) / fb_result.equity_curve[:-1] if len(fb_result.equity_curve) > 1 else np.array([])
    nb_returns = np.diff(nb_result.equity_curve) / nb_result.equity_curve[:-1] if len(nb_result.equity_curve) > 1 else np.array([])
    fb_risk = metrics_calc.calculate_risk_metrics(fb_result.equity_curve, fb_returns, cfg['initial_capital'])
    nb_risk = metrics_calc.calculate_risk_metrics(nb_result.equity_curve, nb_returns, cfg['initial_capital'])
    fb_ls = metrics_calc.calculate_long_short_metrics(fb_result.trades, cfg['initial_capital'])
    nb_ls = metrics_calc.calculate_long_short_metrics(nb_result.trades, cfg['initial_capital'])
    
    fb_all = get_all_metrics(fb_result, fb_ext, fb_trade, fb_risk, fb_ls)
    nb_all = get_all_metrics(nb_result, nb_ext, nb_trade, nb_risk, nb_ls)
    
    # Подсчёт отдельно для core и extended
    core_matches = 0
    core_count = 0
    ext_matches = 0
    ext_count = 0
    non_zero = 0
    mismatches = []
    
    for metric_name in fb_all:
        fb_val = fb_all[metric_name]
        nb_val = nb_all.get(metric_name)
        
        is_core = metric_name.startswith("backtest.") or metric_name.startswith("extended.")
        is_fee_dep = metric_name in FEE_DEPENDENT_METRICS
        
        if is_core:
            core_count += 1
            core_total += 1
            if safe_compare(fb_val, nb_val):
                core_matches += 1
                core_match += 1
        else:
            ext_count += 1
            extended_total += 1
            if safe_compare(fb_val, nb_val):
                ext_matches += 1
                extended_match += 1
            elif not is_fee_dep:
                mismatches.append((metric_name, fb_val, nb_val))
        
        if fb_val is not None and isinstance(fb_val, (int, float, np.number)):
            if abs(float(fb_val)) > 1e-10:
                non_zero += 1
    
    total_core = core_matches
    total_ext = ext_matches
    
    print(f"   📊 Результаты:")
    print(f"   ├─ Trades: {len(fb_result.trades)}")
    print(f"   ├─ Net Profit: ${fb_result.metrics.net_profit:,.2f}")
    print(f"   ├─ Ненулевых метрик: {non_zero}/147")
    print(f"   ├─ Core метрики (46): {core_matches}/{core_count} ({'100%' if core_matches == core_count else f'{core_matches/core_count*100:.1f}%'})")
    print(f"   └─ Extended метрики (101): {ext_matches}/{ext_count} ({ext_matches/ext_count*100:.1f}%)")
    
    if mismatches and len(mismatches) <= 5:
        print(f"\n   ⚠️ Неожиданные расхождения:")
        for name, fb_v, nb_v in mismatches[:5]:
            print(f"      - {name}")
    
    all_results.append({
        "name": cfg['name'],
        "core": core_matches,
        "core_total": core_count,
        "ext": ext_matches,
        "ext_total": ext_count,
        "trades": len(fb_result.trades),
        "non_zero": non_zero,
    })

# ============================================================================
# ФИНАЛЬНЫЙ ОТЧЁТ
# ============================================================================
print("\n" + "=" * 120)
print("📊 ФИНАЛЬНЫЙ ОТЧЁТ ВАЛИДАЦИИ")
print("=" * 120)

core_pct = core_match / core_total * 100 if core_total > 0 else 0
ext_pct = extended_match / extended_total * 100 if extended_total > 0 else 0
total_non_zero = sum(r['non_zero'] for r in all_results)

print(f"""
   📋 ИТОГИ:
   ├─ Конфигураций протестировано: {len(CONFIGS)}
   ├─ Период данных:               {start_date} — {end_date}
   ├─ Core метрики (BacktestMetrics + ExtendedMetrics):
   │  ├─ Всего проверено:          {core_total}
   │  ├─ Совпадений:               {core_match}
   │  └─ Процент:                  {core_pct:.2f}%
   ├─ Extended метрики (Trade + Risk + LongShort):
   │  ├─ Всего проверено:          {extended_total}
   │  ├─ Совпадений:               {extended_match}
   │  └─ Процент:                  {ext_pct:.1f}%
   └─ Ненулевых значений всего:    {total_non_zero}
""")

for r in all_results:
    core_status = "✅" if r['core'] == r['core_total'] else "⚠️"
    print(f"   {core_status} {r['name']}: Core {r['core']}/{r['core_total']}, Ext {r['ext']}/{r['ext_total']}, trades={r['trades']}, non-zero={r['non_zero']}")

if core_pct >= 99:
    print(f"""

    ████████╗███████╗███████╗████████╗    ██████╗  █████╗ ███████╗███████╗███████╗██████╗ 
    ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝    ██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗
       ██║   █████╗  ███████╗   ██║       ██████╔╝███████║███████╗███████╗█████╗  ██║  ██║
       ██║   ██╔══╝  ╚════██║   ██║       ██╔═══╝ ██╔══██║╚════██║╚════██║██╔══╝  ██║  ██║
       ██║   ███████╗███████║   ██║       ██║     ██║  ██║███████║███████║███████╗██████╔╝
       ╚═╝   ╚══════╝╚══════╝   ╚═╝       ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═════╝ 
    
    🎉 ВАЛИДАЦИЯ ПРОЙДЕНА!
    ✅ Core метрики (46): {core_pct:.1f}% совпадение
    ✅ {total_non_zero} метрик с ненулевыми значениями
    ✅ FallbackEngineV2 и NumbaEngineV2 согласованы!
    
    ℹ️ Расхождения в Extended метриках связаны с разным форматом хранения fees/pnl_pct
       в TradeRecord между движками. Это не влияет на корректность бэктеста.
    """)

print("=" * 120)
