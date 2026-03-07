"""
Run backtest for Strategy_MACD_07 via builder endpoint, verify open position fix.
"""

import sys

import requests

strategy_id = "963da4df-8e09-4c8e-a361-3143914b3581"

payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00",
    "end_date": "2026-03-05T23:59:59",
    "initial_capital": 10000,
    "leverage": 10,
    "commission": 0.0007,
    "direction": "both",
    "position_size": 0.1,
    "position_size_type": "percent",
    "stop_loss_pct": 0.132,
    "take_profit_pct": 0.066,
    "market_type": "linear",
    "pyramiding": 1,
}

url = f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest"
print(f"POST {url}", flush=True)
r = requests.post(url, json=payload, timeout=180)
print("Status:", r.status_code, flush=True)

if r.status_code == 200:
    data = r.json()
    bt = data.get("backtest", data)
    print("Backtest ID:", bt.get("id"))
    print("Status:", bt.get("status"))
    print("Total trades:", bt.get("total_trades"))
    trades = bt.get("trades", [])
    print("Trades in response:", len(trades))
    if trades:
        last = trades[-1]
        print("--- Last trade ---")
        print("  exit_comment:", last.get("exit_comment"))
        print("  is_open:", last.get("is_open"))
        print("  entry_time:", last.get("entry_time"))
        print("  entry_price:", last.get("entry_price"))
        print("  exit_time:", last.get("exit_time"))
        print("  exit_price:", last.get("exit_price"))
        print("  direction:", last.get("direction"))
        print("  pnl:", last.get("pnl"))
    metrics = bt.get("metrics", {})
    if metrics:
        print("\n--- Key metrics ---")
        print("  net_profit:", metrics.get("net_profit"))
        print("  total_trades:", metrics.get("total_trades"))
        print("  open_trades:", metrics.get("open_trades"))
else:
    print("Error:", r.text[:2000])

sys.exit(0)

# --- OLD CODE BELOW ---
import sqlite3

sys.path.insert(0, "d:/bybit_strategy_tester_v2")


from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
from backend.backtesting.models import BacktestConfig
from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
from backend.services.data_service import DataService

# Параметры TV
TV_PARAMS = {
    "symbol": "ETHUSDT",
    "interval": "30m",
    "start_date": "2025-01-01T00:00:00+00:00",
    "end_date": "2026-02-27T23:00:00+00:00",
    "initial_capital": 10000,
    "commission_value": 0.0007,
    "slippage_value": 0.0,
    "position_size_pct": 10,
    "leverage": 10,
    "pyramiding": 1,
}

# TV результаты (эталон)
TV_RESULTS = {
    "net_profit": 1001.98,
    "net_profit_percent": 10.02,
    "total_trades": 154,
    "winning_trades": 139,
    "win_rate": 90.26,
    "avg_profit": 21.61,
    "avg_loss": 133.44,
    "total_commission": 215.03,
    "long_trades": 30,
    "short_trades": 124,
}

print("=" * 100)
print("ЗАПУСК БЭКТЕСТА Strategy_RSI_L\\S_15")
print("=" * 100)

# Загружаем стратегию из БД
DB_PATH = "d:/bybit_strategy_tester_v2/data.sqlite3"
conn = sqlite3.connect(DB_PATH)
row = conn.execute(
    "SELECT id, name, builder_blocks, builder_connections FROM strategies WHERE id=?",
    ("2e5bb802-572b-473f-9ee9-44d38bf9c531",),
).fetchone()
conn.close()

if not row:
    print("❌ Стратегия не найдена!")
    exit(1)

strategy_id, name, blocks_json, connections_json = row
blocks = json.loads(blocks_json)
connections = json.loads(connections_json) if connections_json else []

print(f"\nСтратегия: {name}")
print(f"ID: {strategy_id}")

# Загружаем данные
print(f"\n📊 Загрузка данных: {TV_PARAMS['symbol']} {TV_PARAMS['interval']}...")
data_service = DataService()
ohlcv = data_service.load_ohlcv(
    symbol=TV_PARAMS["symbol"],
    interval=TV_PARAMS["interval"],
    start_date=TV_PARAMS["start_date"],
    end_date=TV_PARAMS["end_date"],
)
print(f"  Загружено баров: {len(ohlcv)}")
print(f"  Диапазон: {ohlcv.index.min()} — {ohlcv.index.max()}")

# Загружаем BTC данные для RSI
print("\n📊 Загрузка BTC данных для RSI...")
btc_ohlcv = data_service.load_ohlcv(
    symbol="BTCUSDT",
    interval=TV_PARAMS["interval"],
    start_date=TV_PARAMS["start_date"],
    end_date=TV_PARAMS["end_date"],
)
print(f"  Загружено баров: {len(btc_ohlcv)}")

# Создаем адаптер стратегии
print("\n🔧 Генерация сигналов...")
adapter = StrategyBuilderAdapter()
adapter._btcusdt_30m_ohlcv = btc_ohlcv

strategy_graph = {
    "blocks": blocks,
    "connections": connections,
    "market_type": "linear",
    "direction": "both",
}

signals = adapter.generate_signals(
    strategy_graph=strategy_graph,
    ohlcv=ohlcv,
)

print(f"  LONG сигналов: {signals['long'].sum()}")
print(f"  SHORT сигналов: {signals['short'].sum()}")

# Запускаем бэктест
print("\n🚀 Запуск бэктеста...")
config = BacktestConfig(
    symbol=TV_PARAMS["symbol"],
    interval=TV_PARAMS["interval"],
    initial_capital=TV_PARAMS["initial_capital"],
    commission_value=TV_PARAMS["commission_value"],
    slippage_value=TV_PARAMS["slippage_value"],
    position_size_pct=TV_PARAMS["position_size_pct"],
    leverage=TV_PARAMS["leverage"],
    pyramiding=TV_PARAMS["pyramiding"],
    long_enabled=True,
    short_enabled=True,
)

engine = FallbackEngineV4()
result = engine.run(
    ohlcv=ohlcv,
    signals=signals,
    config=config,
    strategy_graph=strategy_graph,
)

print("\n✅ Бэктест завершен!")
print(f"  Всего сделок: {len(result.trades)}")

if hasattr(result, "metrics") and result.metrics:
    print("\n📊 МЕТРИКИ:")
    metrics = result.metrics
    print(f"  Чистая прибыль: {metrics.get('net_profit', 'N/A')}")
    print(f"  Чистая прибыль %: {metrics.get('net_profit_percent', 'N/A')}")
    print(f"  Всего сделок: {metrics.get('total_trades', 'N/A')}")
    print(f"  Прибыльных сделок: {metrics.get('winning_trades', 'N/A')}")
    print(f"  Процент прибыльных: {metrics.get('win_rate', 'N/A')}%")

print("\n" + "=" * 100)
print("СРАВНЕНИЕ С TRADINGVIEW")
print("=" * 100)

print(f"\n{'Метрика':<30} {'TV Эталон':<15} {'Наш результат':<15} {'Совпадает':<10}")
print("-" * 100)
