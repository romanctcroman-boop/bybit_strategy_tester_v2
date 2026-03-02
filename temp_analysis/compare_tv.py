"""
Сравнение Strategy_RSI_L\\S_15 с TradingView
"""
import sqlite3
import json
import requests
import pandas as pd

DB_PATH = "d:/bybit_strategy_tester_v2/data.sqlite3"
API_URL = "http://localhost:8000/api/v1/strategy-builder/run"

# Параметры из TV (a5.csv)
TV_PARAMS = {
    "symbol": "ETHUSDT.P",
    "interval": "30m",  # 30 минут!
    "start_date": "2025-01-01T03:00:00",  # UTC
    "end_date": "2026-02-27T23:30:00",
    "initial_capital": 10000,
    "commission_value": 0.0007,  # 0.07%
    "slippage_value": 0.0,
    "position_size_pct": 10,  # 10% от капитала
    "leverage": 10,
    "pyramiding": 1,
}

# Получаем стратегию из БД
conn = sqlite3.connect(DB_PATH)
row = conn.execute(
    "SELECT id, name, builder_blocks, builder_connections FROM strategies WHERE id=?",
    ("2e5bb802-572b-473f-9ee9-44d38bf9c531",)
).fetchone()
conn.close()

if not row:
    print("❌ Стратегия не найдена!")
    exit(1)

strategy_id, name, blocks_json, connections_json = row
blocks = json.loads(blocks_json)
connections = json.loads(connections_json) if connections_json else []

print("=" * 80)
print(f"Strategy: {name} (ID: {strategy_id})")
print("=" * 80)

# Показываем параметры RSI
for b in blocks:
    if b["type"] == "rsi":
        print("\n📊 RSI Параметры:")
        for k, v in b["params"].items():
            print(f"  {k}: {v}")
    elif b["type"] == "static_sltp":
        print("\n💰 SL/TP Параметры:")
        for k, v in b["params"].items():
            print(f"  {k}: {v}")

# Формируем запрос к API
payload = {
    "strategy_id": strategy_id,
    "symbol": TV_PARAMS["symbol"],
    "interval": TV_PARAMS["interval"],
    "start_date": TV_PARAMS["start_date"],
    "end_date": TV_PARAMS["end_date"],
    "initial_capital": TV_PARAMS["initial_capital"],
    "commission_value": TV_PARAMS["commission_value"],
    "slippage_value": TV_PARAMS["slippage_value"],
    "position_size_pct": TV_PARAMS["position_size_pct"],
    "leverage": TV_PARAMS["leverage"],
    "pyramiding": TV_PARAMS["pyramiding"],
}

print("\n" + "=" * 80)
print("Запуск бэктеста через API...")
print("=" * 80)

try:
    response = requests.post(API_URL, json=payload, timeout=120)
    response.raise_for_status()
    result = response.json()
    
    print("\n✅ Бэктест завершен!")
    print("\n📊 МЕТРИКИ:")
    
    if "metrics" in result:
        metrics = result["metrics"]
        print(f"  Чистая прибыль: {metrics.get('net_profit', 'N/A')}")
        print(f"  Чистая прибыль %: {metrics.get('net_profit_percent', 'N/A')}")
        print(f"  Всего сделок: {metrics.get('total_trades', 'N/A')}")
        print(f"  Прибыльных сделок: {metrics.get('winning_trades', 'N/A')}")
        print(f"  Процент прибыльных: {metrics.get('win_rate', 'N/A')}%")
        print(f"  Средняя прибыль: {metrics.get('avg_profit', 'N/A')}")
        print(f"  Средний убыток: {metrics.get('avg_loss', 'N/A')}")
        print(f"  Профит фактор: {metrics.get('profit_factor', 'N/A')}")
        print(f"  Макс. просадка: {metrics.get('max_drawdown', 'N/A')}")
        print(f"  Комиссия: {metrics.get('total_commission', 'N/A')}")
    
    print("\n📊 СРАВНЕНИЕ С TRADINGVIEW:")
    print("-" * 80)
    print(f"{'Метрика':<40} {'TV Эталон':<20} {'Наш результат':<20}")
    print("-" * 80)
    
    tv_metrics = {
        "Чистая прибыль (USDT)": "1001.98",
        "Чистая прибыль (%)": "10.02",
        "Всего сделок": "154",
        "Прибыльных сделок": "139",
        "Процент прибыльных (%)": "90.26",
        "Средняя прибыль (USDT)": "21.61",
        "Средний убыток (USDT)": "133.44",
        "Комиссия (USDT)": "215.03",
        "LONG сделок": "30",
        "SHORT сделок": "124",
    }
    
    if "metrics" in result:
        for metric, tv_val in tv_metrics.items():
            our_val = result["metrics"].get(metric.lower().replace(" ", "_").replace("(usdt)", "").replace("(%)", ""), "N/A")
            match = "✅" if str(our_val) == tv_val else "❌"
            print(f"{match} {metric:<38} {tv_val:<20} {our_val:<20}")
    
except requests.exceptions.ConnectionError:
    print("❌ Ошибка подключения к API. Запустите сервер: python main.py server")
except requests.exceptions.Timeout:
    print("❌ Таймаут запроса. Бэктест выполняется слишком долго.")
except Exception as e:
    print(f"❌ Ошибка: {e}")
