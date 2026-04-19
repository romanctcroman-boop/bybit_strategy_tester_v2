# L2 Order Book & Generative LOB (экспериментально)

## Обзор

Модуль для работы с L2 order book:
1. **Загрузка** — Bybit REST API (orderbook snapshot)
2. **Сбор** — периодический сбор снимков в NDJSON
3. **Replay** — использование сохранённых снимков в OrderBookSimulator
4. **Generative LOB** — research: CGAN для синтеза стакана

## Использование

### Загрузка снимка
```python
from backend.experimental.l2_lob import fetch_orderbook, L2Snapshot

snap = fetch_orderbook("BTCUSDT", category="linear", limit=50)
if snap:
    print(f"Mid: {snap.mid_price}, Spread: {snap.spread_bps} bps")
```

### Сбор снимков
```python
from pathlib import Path
from backend.experimental.l2_lob.collector import collect_snapshots

# Собрать 100 снимков с интервалом 1 сек, сохранить в файл
snaps = collect_snapshots(
    symbol="BTCUSDT",
    interval_sec=1.0,
    output_path=Path("l2_btcusdt.ndjson"),
    max_snapshots=100,
)
```

### Replay в бэктесте
```python
from pathlib import Path
from backend.experimental.l2_lob.replay import load_snapshots_ndjson, snapshot_to_orderbook_simulator

for snap in load_snapshots_ndjson(Path("l2_btcusdt.ndjson")):
    sim = snapshot_to_orderbook_simulator(snap)
    # sim — OrderBookSimulator с реальными уровнями
    break
```

## Bybit API

- REST: `GET /v5/market/orderbook` (category, symbol, limit)
- WebSocket: `orderbook.{depth}.{symbol}` — для real-time сбора (не реализовано)

## WebSocket collector (real-time)
```python
from backend.experimental.l2_lob.websocket_collector import run_collector_sync

run_collector_sync(
    symbol="BTCUSDT",
    depth=50,
    output_path=Path("l2_btcusdt_ws.ndjson"),
    max_duration_sec=60,
)
```
Or: `python scripts/l2_lob_collect_ws.py --duration 60`

## Generative LOB (CGAN)
Требует: `pip install torch`
```python
from backend.experimental.l2_lob.generative_cgan import LOB_CGAN

model = LOB_CGAN()
model.fit(Path("l2_btcusdt.ndjson"), epochs=50)
model.save(Path("lob_cgan.pt"))
bids, asks = model.generate(mid_price=100000, spread_bps=10)[0]
```
Training: `python scripts/l2_lob_train_cgan.py --data l2.ndjson --epochs 50`
With WebSocket collect: `python scripts/l2_lob_train_cgan.py --collect 120 --epochs 30`
