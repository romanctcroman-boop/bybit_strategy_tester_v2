#!/usr/bin/env python3
"""
Тест Bybit API через реальный адаптер: 5 тикеров, по 5 циклов на тикер, по ~70 свечей на каждом TF.
Загрузка реальная (тот же путь, что в приложении); в БД не сохраняем — только статистика.
После 5 циклов для одного тикера — смена тикера и ещё 5 циклов. Всего 5 замен тикеров.

Запуск: py scripts/adhoc/test_bybit_tf_cycles.py [--delay-ms 100]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Add project root for imports
root = Path(__file__).resolve().parents[2]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

# Меньше шума от адаптера при ошибках (статистика важнее)
import logging

logging.getLogger("backend.services.adapters.bybit").setLevel(logging.WARNING)

ALL_TIMEFRAMES = ["1", "5", "15", "30", "60", "240", "D", "W", "M"]
# 5 тикеров: после 5 циклов по каждому TF меняем тикер и делаем ещё 5 циклов
TICKERS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
CANDLES_PER_REQUEST = 70  # не упираемся в лимит Bybit (M даёт ~72)
CYCLES_PER_TICKER = 5
MARKET_TYPE = "linear"

# Интервал в мс для расчёта start_time (один запрос ~70 свечей, без пагинации)
TF_MS = {
    "1": 60_000,
    "5": 5 * 60_000,
    "15": 15 * 60_000,
    "30": 30 * 60_000,
    "60": 60 * 60_000,
    "240": 240 * 60_000,
    "D": 24 * 60 * 60_000,
    "W": 7 * 24 * 60 * 60_000,
    "M": 30 * 24 * 60 * 60_000,
}


REQUEST_TIMEOUT = 25  # сек на один запрос — чтобы тест не зависал при подвисшем Bybit


async def fetch_via_adapter(adapter, symbol: str, tf: str) -> tuple[int, float, str]:
    """Реальная загрузка через адаптер приложения (без сохранения в БД). Возвращает (кол-во, сек, ошибка)."""
    now_ts = int(time.time() * 1000)
    interval_ms = TF_MS.get(tf, 60_000)
    start_ts = now_ts - (CANDLES_PER_REQUEST + 2) * interval_ms  # один запрос ~70 свечей
    t0 = time.perf_counter()
    try:
        rows = await asyncio.wait_for(
            adapter.get_historical_klines(
                symbol=symbol,
                interval=tf,
                start_time=start_ts,
                end_time=now_ts,
                limit=CANDLES_PER_REQUEST,
                market_type=MARKET_TYPE,
            ),
            timeout=REQUEST_TIMEOUT,
        )
        elapsed = time.perf_counter() - t0
        n = len(rows) if rows else 0
        return n, elapsed, ""
    except TimeoutError:
        elapsed = time.perf_counter() - t0
        return 0, elapsed, f"timeout after {REQUEST_TIMEOUT}s"
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return 0, elapsed, str(e)


async def run_cycles(delay_ms: int = 0) -> None:
    from backend.services.adapters.bybit import BybitAdapter

    adapter = BybitAdapter(
        api_key=os.environ.get("BYBIT_API_KEY"),
        api_secret=os.environ.get("BYBIT_API_SECRET"),
        timeout=15,
    )

    total_requests = len(TICKERS) * CYCLES_PER_TICKER * len(ALL_TIMEFRAMES)
    print(f"Bybit API test (real adapter): {len(TICKERS)} tickers x {CYCLES_PER_TICKER} cycles x 9 TF")
    print(f"Tickers: {' '.join(TICKERS)}")
    print(f"Timeframes: {' '.join(ALL_TIMEFRAMES)}")
    print(f"~{CANDLES_PER_REQUEST} candles per request -> {total_requests} requests total")
    if delay_ms:
        print(f"Delay between requests: {delay_ms} ms")
    print(f"Per-request timeout: {REQUEST_TIMEOUT}s (test won't hang)")
    print("Real load, no DB.\n", flush=True)

    ok = 0
    fail = 0
    total_elapsed = 0.0
    times_per_tf: dict[str, list[float]] = {tf: [] for tf in ALL_TIMEFRAMES}
    gaps_ms: list[float] = []

    t_prev_end = time.perf_counter()
    first_request = True

    for ticker_idx, symbol in enumerate(TICKERS, 1):
        print(f"========== Ticker {ticker_idx}/{len(TICKERS)}: {symbol} ==========", flush=True)
        for cycle in range(1, CYCLES_PER_TICKER + 1):
            print(f"--- {symbol}  Cycle {cycle}/{CYCLES_PER_TICKER} ---", flush=True)
            for tf in ALL_TIMEFRAMES:
                gap_ms = (time.perf_counter() - t_prev_end) * 1000
                if not first_request:
                    gaps_ms.append(gap_ms)
                first_request = False
                n, elapsed, err = await fetch_via_adapter(adapter, symbol, tf)
                t_prev_end = time.perf_counter()
                total_elapsed += elapsed
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)
                times_per_tf[tf].append(elapsed)
                if err:
                    fail += 1
                    print(f"  {tf:>3}  FAIL  {elapsed:.2f}s  (gap {gap_ms:.0f} ms)  {err}", flush=True)
                else:
                    ok += 1
                    status = "ok" if n >= CANDLES_PER_REQUEST else f"got {n}"
                    print(f"  {tf:>3}  {n:>3} candles  {elapsed:.2f}s  (gap {gap_ms:.0f} ms)  {status}", flush=True)
            print()
        print()

    print("--- Summary ---")
    print(f"OK: {ok}, FAIL: {fail}, total time: {total_elapsed:.2f}s")
    if total_requests:
        print(f"Avg per request: {total_elapsed / total_requests:.2f}s")
    if gaps_ms:
        avg_gap = sum(gaps_ms) / len(gaps_ms)
        print(f"Avg gap between requests (prev end -> next start): {avg_gap:.0f} ms")
    print("Avg per TF (across all tickers and cycles):")
    for tf in ALL_TIMEFRAMES:
        lst = times_per_tf[tf]
        avg = sum(lst) / len(lst) if lst else 0
        print(f"  {tf:>3}  {avg:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bybit TF cycles test (real adapter, ~70 candles, no DB)")
    parser.add_argument("--delay-ms", type=int, default=100, metavar="MS", help="Delay in ms between requests (default: 100)")
    args = parser.parse_args()
    asyncio.run(run_cycles(delay_ms=args.delay_ms))


if __name__ == "__main__":
    main()
