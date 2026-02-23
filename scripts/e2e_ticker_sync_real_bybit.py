"""
E2E: выбор тикеров через фронтенд → реальные запросы к Bybit → загрузка всех TF в БД.

Все действия выполняются из фронтенда (Strategy Builder):
1. Выбор тикера 1 (DOGEUSDT) → sync → запрос к Bybit, загрузка всех TF в БД.
2. Смена тикера на 2 (BNBUSDT) → sync → запрос к Bybit, загрузка всех TF в БД.
3. Смена тикера на 3 (BTCUSDT) → sync → запрос к Bybit, загрузка всех TF в БД.

Требования:
- Запущен бэкенд (start_all.ps1 или uvicorn) на http://localhost:8000.
- Доступ к Bybit API (сеть, при необходимости API key в .env).
- Playwright: py -3.14 -m pip install playwright && py -3.14 -m playwright install chromium
  (через -m, т.к. Scripts может не быть в PATH).

Запуск:
    py -3.14 scripts/e2e_ticker_sync_real_bybit.py
    py -3.14 scripts/e2e_ticker_sync_real_bybit.py --headless
    py -3.14 scripts/e2e_ticker_sync_real_bybit.py --symbols ETHUSDT SOLUSDT XRPUSDT
"""

import argparse
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Taymaut na odnu sinhronizaciyu (vse TF, realnyy Bybit) — do 3 minut
SYNC_TIMEOUT_MS = 180_000
# Taymaut poyavleniya punkta tikera v spiske
DROPDOWN_ITEM_TIMEOUT_MS = 20_000
# Bazovyy URL prilozheniya
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"
STRATEGY_BUILDER_URL = f"{BASE_URL}/frontend/strategy-builder.html"


def verify_symbol_in_db(symbol: str, market_type: str = "linear") -> bool:
    """Proverka cherez API: tiker est v BD (est svechi po intervalam)."""
    symbol = symbol.upper()
    try:
        req = urllib.request.Request(
            f"{API_BASE}/marketdata/symbols/db-groups",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        groups = data.get("groups") or []
        for g in groups:
            if (g.get("symbol") or "").upper() == symbol and (g.get("market_type") or "linear") == market_type:
                return (g.get("total_rows") or 0) > 0
        return False
    except Exception:
        return False


async def wait_sync_complete(page, symbol: str) -> bool:
    """Zhdyot zaversheniya sync: progress skryt, indikator v klase 'available' (uspeshnyy sync)."""
    try:
        await page.wait_for_function(
            """() => {
                const progress = document.getElementById('propertiesCandleLoadingProgress');
                const indicator = document.getElementById('propertiesDataStatusIndicator');
                if (!indicator) return false;
                const progressHidden = progress && progress.classList.contains('hidden');
                const isAvailable = indicator.classList.contains('available');
                return progressHidden && isAvailable;
            }""",
            timeout=SYNC_TIMEOUT_MS,
        )
        return True
    except Exception:
        return False


async def select_ticker_and_wait_sync(page, symbol: str) -> bool:
    """Открывает выбор тикера, выбирает symbol, ждёт завершения sync (реальный Bybit + БД)."""
    print(f"  -> Vybirayu tiker {symbol}...")
    input_el = page.locator("#backtestSymbol")
    await input_el.scroll_into_view_if_needed(timeout=10_000)
    await input_el.click(timeout=15_000)
    await asyncio.sleep(0.5)
    # Ждём появления пункта в выпадающем списке (загрузка тикеров с Bybit)
    item = page.locator(f'.symbol-picker-item[data-symbol="{symbol}"]')
    try:
        await item.first.wait_for(state="visible", timeout=DROPDOWN_ITEM_TIMEOUT_MS)
    except Exception as e:
        print(f"  [FAIL] Tiker {symbol} ne nayden v spiske: {e}")
        return False
    await item.first.click()
    await asyncio.sleep(0.3)
    print(f"  -> Sync {symbol} (zapros k Bybit, zagruzka vseh TF v BD)...")
    ok = await wait_sync_complete(page, symbol)
    if not ok:
        print(f"  [FAIL] {symbol}: taymaut sinhronizacii ({SYNC_TIMEOUT_MS // 1000} s).")
        return False
    market_type = "linear"
    try:
        market_el = await page.locator("#builderMarketType").first.evaluate("el => el ? el.value : 'linear'")
        market_type = str(market_el) if market_el else "linear"
    except Exception:
        pass
    if not verify_symbol_in_db(symbol, market_type):
        print(f"  [FAIL] {symbol}: tiker ne zagruzilsya v BD (proverka API db-groups).")
        return False
    print(f"  [OK] {symbol}: sinhronizaciya zavershena, dannye v BD.")
    return True


async def run_e2e_ticker_sync(symbols: list[str], headless: bool) -> int:
    """Запуск E2E: три (или N) смены тикера с реальной синхронизацией через фронтенд."""
    if not symbols:
        symbols = ["DOGEUSDT", "BNBUSDT", "BTCUSDT"]
    print("=" * 60)
    print("E2E: vybor tikerov cherez frontend -> Bybit -> zagruzka vseh TF v BD")
    print("=" * 60)
    print(f"Tikery: {symbols}")
    print(f"URL: {STRATEGY_BUILDER_URL}")
    print(f"Taymaut na odin sync: {SYNC_TIMEOUT_MS // 1000} s")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        try:
            print("[*] Otkryvayu Strategy Builder...")
            await page.goto(STRATEGY_BUILDER_URL, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)
            # Prokrutit pole Symbol v vidimuyu oblast (plavayushchee okno Parametry)
            await page.evaluate("""() => {
                const el = document.getElementById('backtestSymbol');
                if (el) { el.scrollIntoView({ block: 'center', behavior: 'instant' }); }
            }""")
            await asyncio.sleep(0.5)

            passed = 0
            for sym in symbols:
                ok = await select_ticker_and_wait_sync(page, sym)
                if ok:
                    passed += 1
                else:
                    print(f"Propusk ostavshihsya tikerov posle oshibki dlya {sym}.")
                    break

            print()
            print("=" * 60)
            print(f"Itog: {passed}/{len(symbols)} tikerov sinhronizirovany (realnye dannye Bybit, vse TF v BD).")
            print("=" * 60)
            await browser.close()
            return 0 if passed == len(symbols) else 1
        except Exception as e:
            msg = str(e).encode("ascii", "replace").decode("ascii")
            print(f"[FAIL] Oshibka: {msg}")
            import traceback
            traceback.print_exc()
            await browser.close()
            return 1


def main():
    parser = argparse.ArgumentParser(description="E2E: выбор тикеров через фронтенд, реальный Bybit, все TF в БД.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Запуск браузера в headless.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["DOGEUSDT", "BNBUSDT", "BTCUSDT"],
        help="Тикеры по порядку (по умолчанию: DOGEUSDT BNBUSDT BTCUSDT).",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(run_e2e_ticker_sync(args.symbols, args.headless))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
