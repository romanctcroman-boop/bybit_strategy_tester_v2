"""Thin Bybit API v5 adapter.

Behavior:
 - If `pybit` is installed, use its SDK for authenticated calls.
 - Otherwise, fall back to direct REST calls using `requests` for public endpoints.

This module focuses on a small subset used by the strategy tester: fetching klines (candles) and recent trades.
"""

import contextlib
import json
import logging
import os
import re
import threading
import time
from datetime import UTC, datetime
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)

# Simple in-memory cache for tickers (reduces API calls from 4s to ~0ms)
_tickers_cache: dict[str, Any] = {"data": None, "timestamp": 0, "ttl": 30}  # 30 sec TTL

# Circuit breaker for API resilience
_circuit_registry: Any = None
_HAS_CIRCUIT_BREAKER = False
try:
    from backend.core.circuit_breaker import get_circuit_registry

    _circuit_registry = get_circuit_registry()
    _HAS_CIRCUIT_BREAKER = True
except ImportError:
    pass

try:
    # pybit v2+ (the unofficial/official clients vary by name); attempt common import
    from pybit import HTTP as PybitHTTP  # type: ignore

    _HAS_PYBIT = True
except Exception:
    PybitHTTP = None
    _HAS_PYBIT = False


def _with_circuit_breaker(name: str = "bybit_api"):
    """Decorator to wrap API calls with circuit breaker protection.

    Note: circuit breaker record_success/record_failure are async;
    in this sync context we only use can_execute() (which is sync).
    """

    def decorator(func):
        if not _HAS_CIRCUIT_BREAKER or _circuit_registry is None:
            return func

        def wrapper(*args, **kwargs):
            breaker = _circuit_registry.get_or_create(name)
            if not breaker.can_execute():
                raise ConnectionError(f"Circuit breaker '{name}' is OPEN - API calls blocked")
            return func(*args, **kwargs)

        return wrapper

    return decorator


class BybitAdapter:
    """Bybit API v5 adapter with thread-safe caching and circuit breaker."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: int = 10,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        if _HAS_PYBIT and api_key and api_secret:
            # pybit HTTP client (uses linear/perpetual endpoints by default)
            try:
                self._client = PybitHTTP(api_key=api_key, api_secret=api_secret)
            except Exception:
                self._client = None
        else:
            self._client = None

        # Thread-safe cache for instruments
        self._cache_lock = threading.RLock()
        self._instruments_cache: dict[str, dict] = {}
        self._instruments_cache_at: float | None = None
        # cache TTL in seconds
        self._instruments_cache_ttl = 60 * 5

        # Circuit breaker for API calls
        self._circuit_breaker = None
        if _HAS_CIRCUIT_BREAKER and _circuit_registry:
            self._circuit_breaker = _circuit_registry.get_or_create("bybit_api")

    def _api_get(self, url: str, params: dict, timeout: int | None = None) -> requests.Response:
        """Make GET request with circuit breaker protection.

        Note: circuit breaker record_success/record_failure are async;
        in this sync context we only use can_execute() (which is sync).
        """
        if self._circuit_breaker and not self._circuit_breaker.can_execute():
            raise ConnectionError("Circuit breaker OPEN - Bybit API temporarily unavailable")

        r = requests.get(url, params=params, timeout=timeout or self.timeout)
        r.raise_for_status()
        return r

    def get_klines(self, symbol: str, interval: str = "1", limit: int = 200) -> list[dict]:
        """Fetch kline/candle data. interval is minutes as string in Bybit public API mapping.

        Returns list of dicts with keys: open_time, open, high, low, close, volume
        """

        # Normalize interval to Bybit v5 format: 1,3,5,15,30,60,120,240,360,720,D,W,M
        def _to_v5_interval(itv: str) -> str:
            itv = str(itv).strip()
            u = itv.upper()
            if u in ("W", "1W"):
                return "W"
            if u in ("M", "1M"):
                return "M"
            if itv.endswith("d") or itv.endswith("D"):
                return "D"
            if itv.endswith("h") or itv.endswith("H"):
                try:
                    return str(int(itv[:-1]) * 60)
                except Exception:
                    return itv[:-1]
            if itv.endswith("m"):
                return itv[:-1]
            if itv.endswith("M"):
                return itv[:-1]
            return itv

        interval_norm = _to_v5_interval(interval)

        # Skip pybit client - use direct REST for better performance
        # FAST PATH: For well-known symbols ending in USDT, skip discovery and fetch directly
        symbol_upper = symbol.upper()
        if symbol_upper.endswith("USDT") and len(symbol_upper) >= 6:
            v5_kline_url = "https://api.bybit.com/v5/market/kline"
            params: dict[str, str | int] = {
                "category": "linear",
                "symbol": symbol_upper,
                "interval": interval_norm,
                "limit": limit,
            }
            self.last_chosen_symbol = symbol_upper
            try:
                r = requests.get(v5_kline_url, params=params, timeout=self.timeout)
                r.raise_for_status()
                payload = r.json()
                result = payload.get("result") or payload.get("data") or payload
                if isinstance(result, dict) and "list" in result:
                    data = result["list"]
                elif isinstance(result, list):
                    data = result
                else:
                    data = []
                if data:
                    return [self._normalize_kline_row(d) for d in data]
            except Exception:
                logger.debug(
                    "Fast path failed for %s, falling back to discovery",
                    symbol_upper,
                    exc_info=True,
                )

        # Prefer perpetual/linear futures (category='linear') — discover available instruments first
        v5_url_info = "https://api.bybit.com/v5/market/instruments-info"
        # Best-effort: try to ensure audit table exists if the project's DB models are available.
        # Use local imports to avoid circular imports at module import time.
        try:
            from backend.models.bybit_kline_audit import BybitKlineAudit  # type: ignore

            try:
                # try to discover the project's engine if available
                from backend import database as _dbmod  # type: ignore

                _target_bind = getattr(_dbmod, "engine", None)
            except Exception:
                _target_bind = None

            if _target_bind is not None:
                with contextlib.suppress(Exception):
                    BybitKlineAudit.__table__.create(bind=_target_bind, checkfirst=True)
        except Exception:
            # models or database not available in this runtime (e.g. stripped tests); ignore
            pass

        try:
            r = requests.get(v5_url_info, params={"category": "linear"}, timeout=self.timeout)
            r.raise_for_status()
            info = r.json()
            instruments = (
                info.get("result", {}).get("list", [])
                if isinstance(info.get("result"), dict)
                else info.get("result") or []
            )
            # Build a mapping of symbol -> instrument metadata for smarter selection
            available_meta: dict[str, dict] = {
                str(itm.get("symbol")): itm for itm in instruments if isinstance(itm, dict) and itm.get("symbol")
            }
            available = set(available_meta.keys())
        except Exception:
            logger.debug(
                "Could not discover linear instruments via instruments-info; will still try kline endpoints",
                exc_info=True,
            )
            available = set()

        candidates = [symbol, symbol.upper()]
        # common heuristics: add USDT suffix if missing (most linear perpetuals are SYMBOLUSDT)
        if not symbol.upper().endswith("USDT"):
            candidates.append(symbol.upper() + "USDT")

        # Prefer instrument discovery picks that look like normal USDT perpetuals and are trading
        chosen = None
        # candidate list first (explicit symbol requested by caller)
        for c in candidates:
            if not available or c in available:
                chosen = c
                break

        # If discovery returned many instruments, try to pick a sane default: Trading, not pre-listing,
        # and symbol matching common pattern (letters then USDT), prefer BTC/ETH if present.
        if not chosen and available:
            # prefer canonical pairs
            prefer_order = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
            for p in prefer_order:
                if p in available:
                    chosen = p
                    break

        if not chosen and available:
            # filter Trading & not pre-listing & symbol looks like LETTERS+USDT
            pattern = re.compile(r"^[A-Z]{3,}USDT$")
            for sym, meta in available_meta.items():
                try:
                    if meta.get("status") == "Trading" and not meta.get("isPreListing") and pattern.match(sym):
                        chosen = sym
                        break
                except Exception:
                    continue

        # final fallback: pick any available symbol reported by instruments-info
        if not chosen and available:
            chosen = next(iter(available))

        v5_kline_url = "https://api.bybit.com/v5/market/kline"
        if chosen:
            params = {
                "category": "linear",
                "symbol": chosen,
                "interval": interval_norm,
                "limit": limit,
            }
            # persist which symbol we chose for this request (useful for callers)
            self.last_chosen_symbol = chosen
            # validate chosen symbol against instruments cache (auto-refresh if needed)
            try:
                valid = self.validate_symbol(chosen)
                if valid != chosen:
                    # use normalized/validated symbol
                    chosen = valid
                    params["symbol"] = chosen
                    self.last_chosen_symbol = chosen
            except Exception:
                # validation failed; continue and let the request proceed (we still try)
                logger.debug("Symbol validation failed for %s", chosen, exc_info=True)
            try:
                r = requests.get(v5_kline_url, params=params, timeout=self.timeout)
                r.raise_for_status()
                payload = r.json()
                # Persist raw payload for audit (append JSONL)
                try:
                    logs_dir = os.path.join(os.getcwd(), "logs")
                    os.makedirs(logs_dir, exist_ok=True)
                    log_path = os.path.join(logs_dir, "bybit_kline_raw.jsonl")
                    with open(log_path, "a", encoding="utf-8") as fh:
                        entry = {
                            "fetched_at": int(time.time() * 1000),
                            "category": "linear",
                            "symbol": chosen,
                            "params": params,
                            "payload": payload,
                        }
                        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                except Exception:
                    logger.exception("Failed to write raw bybit payload to logs")
                result = payload.get("result") or payload.get("data") or payload
                if isinstance(result, dict) and "list" in result:
                    data = result["list"]
                elif isinstance(result, list):
                    data = result
                elif isinstance(result, dict) and "data" in result:
                    data = result["data"]
                else:
                    data = []
                if data:
                    normalized = [self._normalize_kline_row(d) for d in data]
                    # attempt to persist normalized candles to audit table (best-effort)
                    try:
                        self._persist_klines_to_db(chosen, normalized, interval=interval_norm)
                    except Exception:
                        logger.exception("Failed to persist klines to DB")
                    return normalized
            except Exception:
                logger.debug("Bybit linear kline probe failed for %s", chosen, exc_info=True)

        # If we reach here, try v5 spot API as fallback (best-effort)
        # NOTE: Legacy endpoints (/public/linear/kline and /spot/quote/v1/kline) are deprecated and return 404

        # Try v5 spot kline endpoint as fallback
        try:
            v5_spot_url = "https://api.bybit.com/v5/market/kline"
            # For spot, symbol format is usually just BTCUSDT without special suffix
            spot_symbol = symbol.upper()
            params = {
                "category": "spot",
                "symbol": spot_symbol,
                "interval": interval_norm,
                "limit": limit,
            }
            r = requests.get(v5_spot_url, params=params, timeout=self.timeout)
            r.raise_for_status()
            payload = r.json()
            result = payload.get("result") or payload.get("data") or payload
            if isinstance(result, dict) and "list" in result:
                data = result["list"]
            elif isinstance(result, list):
                data = result
            else:
                data = []
            if data:
                normalized = [self._normalize_kline_row(d) for d in data]
                try:
                    self._persist_klines_to_db(spot_symbol, normalized, interval=interval_norm)
                except Exception:
                    logger.exception("Failed to persist klines to DB")
                return normalized
        except Exception:
            logger.debug(
                "Bybit v5 spot probe failed",
                exc_info=True,
            )

        # Final fallback: try v5 inverse perpetuals
        try:
            v5_inverse_url = "https://api.bybit.com/v5/market/kline"
            # Inverse perpetuals use different symbol format (e.g., BTCUSD)
            inverse_symbol = symbol.upper().replace("USDT", "USD") if "USDT" in symbol.upper() else symbol.upper()
            params = {
                "category": "inverse",
                "symbol": inverse_symbol,
                "interval": interval_norm,
                "limit": limit,
            }
            r = requests.get(v5_inverse_url, params=params, timeout=self.timeout)
            r.raise_for_status()
            payload = r.json()
            result = payload.get("result") or payload.get("data") or payload
            if isinstance(result, dict) and "list" in result:
                data = result["list"]
            elif isinstance(result, list):
                data = result
            else:
                data = []
            if data:
                return [self._normalize_kline_row(d) for d in data]
        except Exception:
            logger.exception("All Bybit v5 probes failed (linear, spot, inverse)")
            raise

        # If all paths failed but no exception was raised, return empty list
        return []

    def get_klines_before(
        self,
        symbol: str,
        interval: str = "60",
        end_time: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """
        Fetch historical klines BEFORE a specific timestamp.
        Used for infinite scroll / loading more history.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            interval: Timeframe in minutes as string
            end_time: Milliseconds timestamp - fetch data before this time
            limit: Number of candles to fetch
        """

        # Normalize interval
        def _to_v5_interval(itv: str) -> str:
            itv = str(itv)
            if itv.endswith("m") or itv.endswith("M"):
                return itv[:-1]
            if itv.endswith("h") or itv.endswith("H"):
                try:
                    return str(int(itv[:-1]) * 60)
                except Exception:
                    return itv[:-1]
            if itv.endswith("d") or itv.endswith("D"):
                return "D"
            return itv

        interval_norm = _to_v5_interval(interval)
        symbol_upper = symbol.upper()

        v5_kline_url = "https://api.bybit.com/v5/market/kline"
        params: dict[str, str | int] = {
            "category": "linear",
            "symbol": symbol_upper,
            "interval": interval_norm,
            "limit": limit,
        }

        if end_time:
            params["end"] = end_time

        try:
            r = requests.get(v5_kline_url, params=params, timeout=self.timeout)
            r.raise_for_status()
            payload = r.json()
            result = payload.get("result") or payload.get("data") or payload

            if isinstance(result, dict) and "list" in result:
                data = result["list"]
            elif isinstance(result, list):
                data = result
            else:
                data = []

            if data:
                normalized = [self._normalize_kline_row(d) for d in data]
                # Add interval to each row
                for row in normalized:
                    row["interval"] = interval
                return normalized
            return []
        except Exception as e:
            logger.exception(f"Failed to fetch historical klines: {e}")
            raise

    def get_klines_historical(
        self,
        symbol: str,
        interval: str = "60",
        total_candles: int = 2000,
        end_time: int | None = None,
        market_type: str = "linear",
    ) -> list[dict]:
        """
        Load historical candles in chunks of 1000 (Bybit API limit per request).
        Sync version for SmartKlineService background loading.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            interval: Timeframe ('1', '5', '15', '60', 'D' etc.)
            total_candles: Target number of candles to load
            end_time: End timestamp (ms). If None, use current time
            market_type: 'spot' or 'linear'

        Returns:
            List of candles sorted by open_time ascending
        """

        # Normalize interval to Bybit v5
        def _to_v5(itv: str) -> str:
            itv = str(itv)
            if itv.endswith("m") or itv.endswith("M"):
                return itv[:-1]
            if itv.endswith("h") or itv.endswith("H"):
                try:
                    return str(int(itv[:-1]) * 60)
                except Exception:
                    return itv
            if itv.lower() in ("d", "1d"):
                return "D"
            if itv.lower() in ("w", "1w"):
                return "W"
            return itv

        interval_norm = _to_v5(interval)
        symbol_upper = symbol.upper()
        category = "spot" if market_type == "spot" else "linear"
        v5_kline_url = "https://api.bybit.com/v5/market/kline"
        batch_size = 1000  # Bybit max per request
        all_candles: list[dict] = []
        current_end = end_time or int(time.time() * 1000)
        max_iterations = (total_candles // batch_size) + 2
        iteration = 0

        while len(all_candles) < total_candles and iteration < max_iterations:
            params: dict[str, str | int] = {
                "category": category,
                "symbol": symbol_upper,
                "interval": interval_norm,
                "limit": batch_size,
                "end": current_end,
            }
            try:
                r = requests.get(v5_kline_url, params=params, timeout=self.timeout)
                r.raise_for_status()
                payload = r.json()
                result = payload.get("result") or payload.get("data") or payload
                if isinstance(result, dict) and "list" in result:
                    data = result["list"]
                elif isinstance(result, list):
                    data = result
                else:
                    data = []
                if not data:
                    break
                normalized = [self._normalize_kline_row(d) for d in data]
                all_candles.extend(normalized)
                oldest = min(c.get("open_time", 0) for c in normalized)
                current_end = oldest - 1
                iteration += 1
                if len(data) < batch_size:
                    break
                time.sleep(0.02)
            except Exception as e:
                logger.exception("get_klines_historical batch failed: %s", e)
                break

        all_candles.sort(key=lambda x: x.get("open_time", 0))
        seen = set()
        unique = []
        for c in all_candles:
            t = c.get("open_time")
            if t is not None and t not in seen:
                seen.add(t)
                unique.append(c)
        return unique

    async def get_historical_klines(
        self,
        symbol: str,
        interval: str = "60",
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
        market_type: str = "linear",
    ) -> list[dict]:
        """
        Fetch historical klines between start_time and end_time.
        Uses pagination to fetch more than 1000 candles.
        Used for backtesting.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            interval: Timeframe (e.g. '60' for 1h, 'D' for daily)
            start_time: Milliseconds timestamp - fetch data FROM this time
            end_time: Milliseconds timestamp - fetch data TO this time
            limit: Max number of candles per request (max 1000)
            market_type: 'spot' (TradingView parity) or 'linear' (perpetual futures)

        Returns:
            List of normalized kline dicts sorted by time ascending
        """
        import asyncio

        # Normalize interval (Bybit v5: 1,5,15,30,60,240,D,W,M). D/W/M — не обрезать.
        def _to_v5_interval(itv: str) -> str:
            itv = str(itv).strip()
            if not itv:
                return "60"
            u = itv.upper()
            if u in ("D", "W", "M"):
                return u
            if itv.endswith("m") and itv[:-1].isdigit():
                return itv[:-1]
            if itv.endswith("h") or itv.endswith("H"):
                try:
                    return str(int(itv[:-1]) * 60)
                except Exception:
                    return itv[:-1]
            if u in ("D", "1D"):
                return "D"
            if u in ("W", "1W"):
                return "W"
            return itv

        interval_norm = _to_v5_interval(interval)
        symbol_upper = symbol.upper()

        all_candles = []
        # Bybit v5 returns data in DESCENDING order (newest first)
        # So we paginate backwards using 'end' parameter
        current_end = end_time

        v5_kline_url = "https://api.bybit.com/v5/market/kline"
        max_iterations = 500  # Safety limit to prevent infinite loops

        # Use market_type for category selection (spot for TradingView parity)
        category = "spot" if market_type == "spot" else "linear"
        logger.info(f"Fetching klines with category={category} (market_type={market_type})")

        for iteration in range(max_iterations):
            params: dict[str, str | int] = {
                "category": category,
                "symbol": symbol_upper,
                "interval": interval_norm,
                "limit": min(limit, 1000),
            }

            # Bybit v5 returns data in DESCENDING order (newest first)
            # We use 'start' to set the minimum time and 'end' to paginate backwards
            if start_time:
                params["start"] = start_time
            if current_end:
                params["end"] = current_end

            try:
                # Run sync request in executor to not block event loop
                loop = asyncio.get_event_loop()
                r = await loop.run_in_executor(
                    None,
                    lambda p=params: requests.get(  # type: ignore[misc]
                        v5_kline_url, params=p, timeout=self.timeout
                    ),
                )
                r.raise_for_status()
                payload = r.json()
                result = payload.get("result") or payload.get("data") or payload

                if isinstance(result, dict) and "list" in result:
                    data = result["list"]
                elif isinstance(result, list):
                    data = result
                else:
                    data = []

                if not data:
                    break

                normalized = [self._normalize_kline_row(d) for d in data]
                all_candles.extend(normalized)

                logger.debug(
                    f"Fetched {len(data)} candles for {symbol_upper}/{interval_norm}, iteration {iteration + 1}"
                )

                # Check if we got all data or need to paginate
                if len(data) < limit:
                    break

                # Bybit returns newest first, so oldest is at the end
                # Get the oldest candle time and set end to just before it
                oldest_time = min(c.get("open_time", 0) for c in normalized)

                # If we've reached start_time, stop
                if start_time and oldest_time <= start_time:
                    break

                # Move end backwards for next iteration
                current_end = oldest_time - 1

                # Minimal pause: Bybit ~120 req/s per IP, 8 TF in parallel — 0.02s is enough
                await asyncio.sleep(0.02)

            except Exception as e:
                logger.exception(f"Failed to fetch historical klines: {e}")
                raise

        # Sort by time ascending and remove duplicates
        all_candles.sort(key=lambda x: x.get("open_time", 0))
        seen = set()
        unique_candles = []
        for c in all_candles:
            t = c.get("open_time")
            if t not in seen:
                seen.add(t)
                unique_candles.append(c)

        logger.info(
            f"Historical fetch complete: {len(unique_candles)} unique candles for {symbol_upper}/{interval_norm}"
        )

        return unique_candles

    async def get_historical_klines_chunked(
        self,
        symbol: str,
        interval: str = "60",
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
        market_type: str = "linear",
        persist_every: int = 5000,
        on_progress: Callable[[int, int], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> int:
        """
        Fetch historical klines with chunked persistence and progress reporting.

        Unlike get_historical_klines(), this method:
        - Saves data to DB every `persist_every` candles (no data loss on timeout)
        - Reports progress via on_progress callback
        - Supports cancellation via cancel_check callback

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            interval: Timeframe (e.g. '60' for 1h, 'D' for daily)
            start_time: Milliseconds timestamp - fetch data FROM this time
            end_time: Milliseconds timestamp - fetch data TO this time
            limit: Max number of candles per request (max 1000)
            market_type: 'spot' or 'linear'
            persist_every: Save to DB after this many candles (default 5000)
            on_progress: Callback(fetched_so_far, estimated_total) called after each batch
            cancel_check: Callback() -> bool, return True to cancel

        Returns:
            Total number of new candles persisted
        """
        import asyncio

        # Normalize interval
        def _to_v5_interval(itv: str) -> str:
            itv = str(itv).strip()
            if not itv:
                return "60"
            u = itv.upper()
            if u in ("D", "W", "M"):
                return u
            if itv.endswith("m") and itv[:-1].isdigit():
                return itv[:-1]
            if itv.endswith("h") or itv.endswith("H"):
                try:
                    return str(int(itv[:-1]) * 60)
                except Exception:
                    return itv[:-1]
            return itv

        interval_norm = _to_v5_interval(interval)
        symbol_upper = symbol.upper()
        category = "spot" if market_type == "spot" else "linear"

        v5_kline_url = "https://api.bybit.com/v5/market/kline"
        max_iterations = 1500  # Safety limit (enough for ~1.5M candles)

        total_persisted = 0
        pending_candles: list[dict] = []
        seen_times: set[int] = set()
        current_end = end_time

        # Estimate total candles for progress reporting
        interval_ms_map = {
            "1": 60_000,
            "5": 300_000,
            "15": 900_000,
            "30": 1_800_000,
            "60": 3_600_000,
            "240": 14_400_000,
            "D": 86_400_000,
            "W": 604_800_000,
            "M": 2_592_000_000,
        }
        estimated_total = 0
        if start_time and end_time:
            ims = interval_ms_map.get(interval_norm, 3_600_000)
            estimated_total = max(1, (end_time - start_time) // ims)

        logger.info(
            f"[ChunkedFetch] Starting {symbol_upper}/{interval_norm} "
            f"from {start_time} to {end_time}, estimated ~{estimated_total} candles"
        )

        for iteration in range(max_iterations):
            # Check cancellation
            if cancel_check and cancel_check():
                logger.info(f"[ChunkedFetch] Cancelled at iteration {iteration}")
                break

            params: dict[str, str | int] = {
                "category": category,
                "symbol": symbol_upper,
                "interval": interval_norm,
                "limit": min(limit, 1000),
            }
            if start_time:
                params["start"] = start_time
            if current_end:
                params["end"] = current_end

            try:
                loop = asyncio.get_event_loop()
                r = await loop.run_in_executor(
                    None,
                    lambda p=params: requests.get(v5_kline_url, params=p, timeout=self.timeout),
                )
                r.raise_for_status()
                payload = r.json()
                result = payload.get("result") or payload.get("data") or payload

                if isinstance(result, dict) and "list" in result:
                    data = result["list"]
                elif isinstance(result, list):
                    data = result
                else:
                    data = []

                if not data:
                    break

                normalized = [self._normalize_kline_row(d) for d in data]

                # Deduplicate within this fetch
                for c in normalized:
                    t = c.get("open_time")
                    if t is not None and t not in seen_times:
                        seen_times.add(t)
                        pending_candles.append(c)

                # Persist chunk if enough candles accumulated
                if len(pending_candles) >= persist_every:
                    rows_with_interval = [{**c, "interval": interval_norm} for c in pending_candles]
                    self._persist_klines_to_db(symbol_upper, rows_with_interval, market_type=market_type)
                    total_persisted += len(pending_candles)
                    logger.info(
                        f"[ChunkedFetch] Persisted chunk: {len(pending_candles)} candles, "
                        f"total={total_persisted} for {symbol_upper}/{interval_norm}"
                    )
                    pending_candles.clear()

                # Report progress
                fetched_so_far = total_persisted + len(pending_candles)
                if on_progress:
                    with contextlib.suppress(Exception):
                        on_progress(fetched_so_far, estimated_total)

                # Check pagination
                if len(data) < limit:
                    break

                oldest_time = min(c.get("open_time", 0) for c in normalized)
                if start_time and oldest_time <= start_time:
                    break

                current_end = oldest_time - 1
                await asyncio.sleep(0.02)

            except Exception as e:
                logger.error(f"[ChunkedFetch] Error at iteration {iteration}: {e}")
                # Persist whatever we have so far before re-raising
                if pending_candles:
                    rows_with_interval = [{**c, "interval": interval_norm} for c in pending_candles]
                    self._persist_klines_to_db(symbol_upper, rows_with_interval, market_type=market_type)
                    total_persisted += len(pending_candles)
                    pending_candles.clear()
                    logger.info(f"[ChunkedFetch] Saved {total_persisted} candles before error")
                raise

        # Persist remaining candles
        if pending_candles:
            rows_with_interval = [{**c, "interval": interval_norm} for c in pending_candles]
            self._persist_klines_to_db(symbol_upper, rows_with_interval, market_type=market_type)
            total_persisted += len(pending_candles)
            pending_candles.clear()

        logger.info(f"[ChunkedFetch] Complete: {total_persisted} candles for {symbol_upper}/{interval_norm}")
        return total_persisted

    def _normalize_kline_row(self, row: dict) -> dict:
        # Accept both list-style and dict-style rows
        # Always preserve the original data under 'raw' to avoid any data loss
        if isinstance(row, list):
            raw: Any = list(row)
            # Bybit v5 list format documented: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover?]
            parsed: dict[str, Any] = {"raw": raw}
            try:
                start_ms = int(raw[0])
                parsed["open_time"] = start_ms
                parsed["open_time_dt"] = datetime.fromtimestamp(start_ms / 1000.0, tz=UTC)
            except Exception:
                parsed["open_time"] = None
                parsed["open_time_dt"] = None

            # map string fields and keep originals
            def _as_str(idx: int) -> str | None:
                try:
                    return str(raw[idx])
                except Exception:
                    return None

            def _as_float(val: str | None) -> float | None:
                try:
                    return float(val) if val is not None and val != "" else None
                except Exception:
                    return None

            parsed["open_price_str"] = _as_str(1)
            parsed["open"] = _as_float(parsed["open_price_str"])
            parsed["high_price_str"] = _as_str(2)
            parsed["high"] = _as_float(parsed["high_price_str"])
            parsed["low_price_str"] = _as_str(3)
            parsed["low"] = _as_float(parsed["low_price_str"])
            parsed["close_price_str"] = _as_str(4)
            parsed["close"] = _as_float(parsed["close_price_str"])
            parsed["volume_str"] = _as_str(5)
            parsed["volume"] = _as_float(parsed["volume_str"])
            # turnover is optional (index 6)
            parsed["turnover_str"] = _as_str(6) if len(raw) > 6 else None
            parsed["turnover"] = _as_float(parsed["turnover_str"]) if parsed.get("turnover_str") is not None else None
            return parsed
        elif isinstance(row, dict):
            raw = dict(row)
            parsed = {"raw": raw}
            # Common key aliases used across Bybit responses
            start_candidates = [
                raw.get("startTime"),
                raw.get("start_at"),
                raw.get("t"),
                raw.get("open_time"),
                raw.get("startTime"),
            ]
            start_ms = None
            for cand in start_candidates:
                if cand is None:
                    continue
                try:
                    start_ms = int(cand)
                    break
                except Exception:
                    try:
                        start_ms = int(float(cand))
                        break
                    except Exception:
                        continue
            parsed["open_time"] = start_ms
            parsed["open_time_dt"] = datetime.fromtimestamp(start_ms / 1000.0, tz=UTC) if start_ms is not None else None

            def get_str(*keys) -> str | None:
                for k in keys:
                    v = raw.get(k)
                    if v is not None:
                        return str(v)
                return None

            parsed["open_price_str"] = get_str("openPrice", "open", "o")
            parsed["open"] = _safe_float(parsed["open_price_str"]) if "open_price_str" in parsed else None
            parsed["high_price_str"] = get_str("highPrice", "high", "h")
            parsed["high"] = _safe_float(parsed["high_price_str"])
            parsed["low_price_str"] = get_str("lowPrice", "low", "l")
            parsed["low"] = _safe_float(parsed["low_price_str"])
            parsed["close_price_str"] = get_str("closePrice", "close", "c")
            parsed["close"] = _safe_float(parsed["close_price_str"])
            parsed["volume_str"] = get_str("volume", "v")
            parsed["volume"] = _safe_float(parsed["volume_str"])
            parsed["turnover_str"] = get_str("turnover")
            parsed["turnover"] = _safe_float(parsed["turnover_str"])
            return parsed
        else:
            return {"raw": row}

    def _persist_klines_to_db(
        self,
        symbol: str,
        normalized_rows: list[dict],
        db: Any = None,
        engine: Any = None,
        market_type: str = "linear",
        interval: str | None = None,
    ) -> None:
        """Persist normalized klines (list of dicts as returned by _normalize_kline_row) into audit table.

        Args:
            symbol: Trading pair symbol (e.g. BTCUSDT).
            normalized_rows: List of normalized kline dicts.
            db: Optional SQLAlchemy session for deterministic behavior in tests.
            engine: Optional SQLAlchemy engine.
            market_type: Market type (linear/spot).
            interval: Timeframe interval (e.g. "15", "60", "D"). If not provided,
                      extracted from each row's 'interval' key; rows without valid
                      interval are skipped to prevent "UNKNOWN" pollution.

        Behaviour: best-effort; uses UNIQUE(symbol, open_time) to avoid duplicates.
        """
        # import DB objects lazily to avoid import-time circular dependencies in tests
        import os

        from sqlalchemy import text

        from backend.database import SessionLocal
        from backend.models.bybit_kline_audit import BybitKlineAudit

        # Respect env var BYBIT_PERSIST_KLINES (default true)
        persist_flag = os.environ.get("BYBIT_PERSIST_KLINES", "1").lower()
        if persist_flag not in ("1", "true", "yes", "y"):
            logger.debug("BYBIT_PERSIST_KLINES is false; skipping DB persistence")
            return

        # Prepare parameter rows
        params = []
        for row in normalized_rows:
            open_time = row.get("open_time")
            if open_time is None:
                continue
            try:
                raw_val = row.get("raw") if "raw" in row else row
                # ensure JSON/text serializable raw
                if not isinstance(raw_val, str):
                    raw_val = json.dumps(raw_val, ensure_ascii=False)
            except Exception:
                raw_val = str(row)

            # Accept both styles used across tests and normalizers: keys may be named 'open'/'close' or 'open_price'/'close_price'.
            def _pick(*keys, _row=row):
                for k in keys:
                    if k in _row and _row.get(k) is not None:
                        return _row.get(k)
                return None

            # Extract interval from row, or use explicit parameter.
            # NEVER fall back to "UNKNOWN" — skip rows without valid interval.
            VALID_INTERVALS = {"1", "5", "15", "30", "60", "240", "D", "W", "M"}
            row_interval = interval or _pick("interval")
            if not row_interval or row_interval not in VALID_INTERVALS:
                logger.debug(
                    "Skipping persist for %s: invalid interval '%s'",
                    symbol,
                    row_interval,
                )
                continue

            params.append(
                {
                    "symbol": symbol,
                    "interval": row_interval,
                    "market_type": market_type,
                    "open_time": open_time,
                    "open_time_dt": row.get("open_time_dt")
                    if row.get("open_time_dt") is not None
                    else _to_dt(open_time),
                    "open_price": _pick("open", "open_price", "open_price_str"),
                    "high_price": _pick("high", "high_price", "high_price_str"),
                    "low_price": _pick("low", "low_price", "low_price_str"),
                    "close_price": _pick("close", "close_price", "close_price_str"),
                    "volume": _pick("volume", "volume_str"),
                    "turnover": _pick("turnover", "turnover_str"),
                    "raw": raw_val,
                }
            )

        if not params:
            return

        # Allow callers to inject a DB session or engine for deterministic behavior in tests.
        from sqlalchemy import create_engine as _create_engine

        _engine = engine
        user_db = db
        if db is None:
            # Try to use the project's canonical engine/session factory when available so in-memory
            # sqlite tests (which create schema via backend.database.engine) remain consistent.
            try:
                import backend.database as _dbmod

                _engine = _engine or getattr(_dbmod, "engine", None)
                SessionLocal = getattr(_dbmod, "SessionLocal", SessionLocal)
            except Exception as e:
                logger.debug("Database module import/bind skipped: %s", e)

        if _engine is None:
            # Last-resort: create engine from DATABASE_URL
            _database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
            _engine = _create_engine(
                _database_url,
                connect_args={"check_same_thread": False} if _database_url.startswith("sqlite") else {},
            )

        # determine dialect from engine
        bind = _engine
        dialect = bind.dialect.name if hasattr(bind, "dialect") else "sqlite"

        # Ensure the audit table exists on the target bind/engine. This is a best-effort
        # helper to make in-memory sqlite tests (which create the schema elsewhere)
        # visible to the engine/session we're about to use.
        try:
            target_bind = None
            try:
                if db is not None and hasattr(db, "get_bind"):
                    target_bind = db.get_bind()
            except Exception:
                target_bind = None
            if target_bind is None:
                target_bind = _engine
            with contextlib.suppress(Exception):
                BybitKlineAudit.__table__.create(bind=target_bind, checkfirst=True)
        except Exception:
            # swallow any unexpected errors in this best-effort block
            pass

        # then try to get a session from the project's SessionLocal; if that fails,
        # create a fresh sessionmaker bound to the engine
        candidate = None
        try:
            candidate = SessionLocal()
        except Exception:
            candidate = None

        # If the candidate session exposes get_bind(), prefer its engine (this keeps
        # the same in-memory sqlite engine used elsewhere in tests).
        try:
            if candidate is not None and hasattr(candidate, "get_bind"):
                try:
                    session_engine = candidate.get_bind()
                    if session_engine is not None:
                        _engine = session_engine
                except Exception as e:
                    logger.debug("get_bind failed: %s", e)
        except Exception as e:
            logger.debug("Session candidate resolution failed: %s", e)

        # Accept the candidate only if it looks like a real SQLAlchemy Session
        def _is_session_like(o):
            return o is not None and (
                hasattr(o, "execute") or hasattr(o, "query") or hasattr(o, "begin") or hasattr(o, "get_bind")
            )

        if _is_session_like(candidate):
            db = candidate
        else:
            # fallback: create a proper sessionmaker bound to the engine
            from sqlalchemy.orm import sessionmaker as _sessionmaker

            db = _sessionmaker(bind=_engine)()  # type: ignore[arg-type]

        try:
            if dialect in ("postgres", "postgresql"):
                sql = text(
                    """
                    INSERT INTO bybit_kline_audit
                        (symbol, interval, market_type, open_time, open_time_dt, open_price, high_price, low_price, close_price, volume, turnover, raw)
                    VALUES
                        (:symbol, :interval, :market_type, :open_time, :open_time_dt, :open_price, :high_price, :low_price, :close_price, :volume, :turnover, :raw)
                    ON CONFLICT (symbol, interval, market_type, open_time) DO UPDATE SET
                        open_time_dt = EXCLUDED.open_time_dt,
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        turnover = EXCLUDED.turnover,
                        raw = EXCLUDED.raw
                    """
                )
                # If the caller provided a session, use it (keeps same in-memory DB).
                if user_db is not None:
                    with user_db.begin():
                        user_db.execute(sql, params)
                else:
                    # Execute directly on the engine to avoid session/engine mismatches
                    try:
                        with _engine.begin() as conn:
                            conn.execute(sql, params)
                    except Exception:
                        # fallback to session execute if engine execution fails
                        with db.begin():
                            db.execute(sql, params)
            elif dialect.startswith("sqlite"):
                sql = text(
                    """
                    INSERT INTO bybit_kline_audit
                        (symbol, interval, market_type, open_time, open_time_dt, open_price, high_price, low_price, close_price, volume, turnover, raw)
                    VALUES
                        (:symbol, :interval, :market_type, :open_time, :open_time_dt, :open_price, :high_price, :low_price, :close_price, :volume, :turnover, :raw)
                    ON CONFLICT(symbol, interval, market_type, open_time) DO UPDATE SET
                        open_time_dt = excluded.open_time_dt,
                        open_price = excluded.open_price,
                        high_price = excluded.high_price,
                        low_price = excluded.low_price,
                        close_price = excluded.close_price,
                        volume = excluded.volume,
                        turnover = excluded.turnover,
                        raw = excluded.raw
                    """
                )
                # If the caller provided a session, use it (keeps same in-memory DB).
                if user_db is not None:
                    with user_db.begin():
                        user_db.execute(sql, params)
                else:
                    # Execute directly on the engine for sqlite in-memory consistency
                    try:
                        with _engine.begin() as conn:
                            conn.execute(sql, params)
                    except Exception:
                        with db.begin():
                            db.execute(sql, params)
            else:
                # Generic ORM fallback
                for p in params:
                    existing = (
                        db.query(BybitKlineAudit)
                        .filter(
                            BybitKlineAudit.symbol == p["symbol"],
                            BybitKlineAudit.open_time == p["open_time"],
                        )
                        .one_or_none()
                    )
                    if existing:
                        # update fields to newest
                        existing.open_time_dt = p["open_time_dt"]
                        existing.open_price = p["open_price"]
                        existing.high_price = p["high_price"]
                        existing.low_price = p["low_price"]
                        existing.close_price = p["close_price"]
                        existing.volume = p["volume"]
                        existing.turnover = p["turnover"]
                        existing.raw = p["raw"]
                        continue
                    obj = BybitKlineAudit(
                        symbol=p["symbol"],
                        interval=p["interval"],
                        market_type=p["market_type"],
                        open_time=p["open_time"],
                        open_time_dt=p["open_time_dt"],
                        open_price=p["open_price"],
                        high_price=p["high_price"],
                        low_price=p["low_price"],
                        close_price=p["close_price"],
                        volume=p["volume"],
                        turnover=p["turnover"],
                    )
                    try:
                        obj.raw = p["raw"]  # type: ignore[assignment]
                    except Exception:
                        obj.raw = str(p["raw"])  # type: ignore[assignment]
                    db.add(obj)
                db.commit()
        except Exception:
            # safest rollback attempt for real sessions
            with contextlib.suppress(Exception):
                db.rollback()
            raise
        finally:
            with contextlib.suppress(Exception):
                if db:
                    db.close()

    # Instrument discovery and validation (thread-safe)
    def _refresh_instruments_cache(self, force: bool = False):
        """Refresh instruments cache with thread-safety."""
        now = time.time()

        # Quick check without lock (read-only, safe for concurrent access)
        if (
            not force
            and self._instruments_cache
            and self._instruments_cache_at
            and (now - self._instruments_cache_at) < self._instruments_cache_ttl
        ):
            return

        # Acquire lock for potential write
        with self._cache_lock:
            # Double-check after acquiring lock (another thread may have refreshed)
            if (
                not force
                and self._instruments_cache
                and self._instruments_cache_at
                and (time.time() - self._instruments_cache_at) < self._instruments_cache_ttl
            ):
                return

            v5_url_info = "https://api.bybit.com/v5/market/instruments-info"
            try:
                r = requests.get(v5_url_info, params={"category": "linear"}, timeout=self.timeout)
                r.raise_for_status()
                info = r.json()
                instruments = (
                    info.get("result", {}).get("list", [])
                    if isinstance(info.get("result"), dict)
                    else info.get("result") or []
                )
                self._instruments_cache = {
                    str(itm.get("symbol")): itm for itm in instruments if isinstance(itm, dict) and itm.get("symbol")
                }
                self._instruments_cache_at = time.time()
            except Exception:
                logger.exception("Failed to refresh instruments cache")

    def validate_symbol(self, symbol: str) -> str:
        """Validate and normalize a symbol. Returns the canonical symbol if valid, else raises ValueError.

        Behavior:
        - Refreshes instruments cache if stale (thread-safe)
        - Accepts lower/upper case and optionally missing USDT suffix
        - Prefers exact match in cache, otherwise tries adding USDT suffix
        - Raises ValueError if no valid trading instrument found
        """
        if not symbol:
            raise ValueError("empty symbol")
        self._refresh_instruments_cache()
        s = symbol.upper()

        # Thread-safe read from cache
        with self._cache_lock:
            cache_snapshot = dict(self._instruments_cache)

        # direct match
        if s in cache_snapshot:
            meta = cache_snapshot[s]
            if meta.get("status") == "Trading" and not meta.get("isPreListing"):
                return s
            raise ValueError(f"symbol {s} not trading")
        # try adding USDT
        if not s.endswith("USDT"):
            cand = s + "USDT"
            if cand in cache_snapshot:
                meta = cache_snapshot[cand]
                if meta.get("status") == "Trading" and not meta.get("isPreListing"):
                    return cand
                raise ValueError(f"symbol {cand} not trading")
        raise ValueError(f"symbol {symbol} not found in instruments-info")

    def get_tickers(self, symbols: list[str] | None = None, category: str = "linear") -> list[dict[str, Any]]:
        """Fetch real-time ticker data from Bybit V5 API.

        Args:
            symbols: Optional list of symbols. If None, returns all tickers for category.
            category: 'linear' (USDT perpetual) or 'spot'.

        Returns:
            List of ticker dicts with: symbol, lastPrice, price24hPcnt, volume24h, highPrice24h, lowPrice24h
        """
        global _tickers_cache

        v5_tickers_url = "https://api.bybit.com/v5/market/tickers"
        current_time = time.time()
        cat = "spot" if category == "spot" else "linear"

        # Use cache if available and not expired (only for "all tickers" requests, per category)
        cache_key = f"tickers_{cat}"
        if not hasattr(_tickers_cache, "by_cat"):
            _tickers_cache["by_cat"] = {}
        bc = _tickers_cache["by_cat"]
        if symbols is None and cache_key in bc:
            entry = bc[cache_key]
            if entry and current_time - entry.get("timestamp", 0) < _tickers_cache.get("ttl", 30):
                logger.debug(f"Using cached tickers for {cat}")
                cached_data: list[dict[str, Any]] = list(entry.get("data", []))
                return cached_data

        try:
            params = {"category": cat}
            r = requests.get(v5_tickers_url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()

            tickers = data.get("result", {}).get("list", [])

            result = []
            for ticker in tickers:
                sym = ticker.get("symbol", "")
                # Filter by requested symbols if provided
                if symbols and sym not in symbols:
                    continue
                # For linear: only USDT perpetuals; for spot: include USDT pairs (main liquid pairs)
                if cat == "linear" and not sym.endswith("USDT"):
                    continue

                result.append(
                    {
                        "symbol": sym,
                        "price": _safe_float(ticker.get("lastPrice")),
                        "change_24h": (_safe_float(ticker.get("price24hPcnt")) or 0) * 100,
                        "volume_24h": _safe_float(ticker.get("volume24h")),
                        "high_24h": _safe_float(ticker.get("highPrice24h")),
                        "low_24h": _safe_float(ticker.get("lowPrice24h")),
                        "turnover_24h": _safe_float(ticker.get("turnover24h")),
                        "bid_price": _safe_float(ticker.get("bid1Price")),
                        "ask_price": _safe_float(ticker.get("ask1Price")),
                    }
                )

            # Update cache for "all tickers" requests
            if symbols is None:
                if "by_cat" not in _tickers_cache:
                    _tickers_cache["by_cat"] = {}
                _tickers_cache["by_cat"][cache_key] = {"data": result, "timestamp": current_time}
                logger.debug(f"Cached {len(result)} tickers for {cat}")

            return result

        except Exception as e:
            logger.error(f"Failed to fetch tickers from Bybit: {e}")
            return []

    def get_ticker(self, symbol: str) -> dict[str, Any] | None:
        """Fetch ticker for a single symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Ticker dict or None if not found
        """
        tickers = self.get_tickers(symbols=[symbol.upper()])
        return tickers[0] if tickers else None

    def get_orderbook(
        self,
        symbol: str,
        category: str = "linear",
        limit: int = 25,
    ) -> dict[str, Any] | None:
        """Fetch L2 order book snapshot from Bybit.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            category: spot, linear, inverse, option
            limit: Depth levels. linear/inverse: 1-500, spot: 1-200, option: 1-25

        Returns:
            Dict with keys: symbol, bids [[price, size], ...], asks, ts (ms), u, seq, cts
            or None on error
        """
        v5_url = "https://api.bybit.com/v5/market/orderbook"
        try:
            ob_params: dict[str, str | int] = {
                "category": category,
                "symbol": symbol.upper(),
                "limit": limit,
            }
            r = requests.get(v5_url, params=ob_params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            if data.get("retCode", -1) != 0:
                logger.warning("get_orderbook retCode=%s", data.get("retMsg", ""))
                return None
            result: dict[str, Any] | None = data.get("result") or data.get("data")
            return result
        except Exception as e:
            logger.error("get_orderbook failed: %s", e)
            return None

    def get_symbols_list(self, category: str = "linear", trading_only: bool = True) -> list[str]:
        """Fetch full list of symbols from Bybit instruments-info (all pages).

        Args:
            category: 'linear' (USDT perpetual), 'spot', or 'inverse'
            trading_only: If True, return only instruments with status 'Trading'

        Returns:
            List of symbol strings (e.g. ['BTCUSDT', 'ETHUSDT', ...])
        """
        v5_url = "https://api.bybit.com/v5/market/instruments-info"
        result: list[str] = []
        cursor: str | None = None
        limit = 1000  # max per request
        max_pages = 50  # safety
        timeout_sec = max(self.timeout, 30)  # instruments-info can be slow (many pages)
        try:
            for _page in range(max_pages):
                params: dict[str, Any] = {"category": category, "limit": limit}
                if cursor:
                    params["cursor"] = cursor
                r = requests.get(v5_url, params=params, timeout=timeout_sec)
                r.raise_for_status()
                data = r.json()
                ret_code = data.get("retCode", -1)
                if ret_code != 0:
                    logger.warning(
                        "get_symbols_list Bybit retCode=%s retMsg=%s",
                        ret_code,
                        data.get("retMsg", ""),
                    )
                    break
                res = data.get("result")
                if not isinstance(res, dict):
                    break
                items = res.get("list") or []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    sym = it.get("symbol", "")
                    if not sym:
                        continue
                    if trading_only and it.get("status") != "Trading":
                        continue
                    if category == "linear" and not sym.endswith("USDT"):
                        continue
                    if category == "spot" and "USDT" not in sym:
                        continue
                    result.append(sym)
                next_cursor = res.get("nextPageCursor")
                if not next_cursor or len(items) < limit:
                    break
                cursor = next_cursor
            out = sorted(set(result))
            logger.info("get_symbols_list category=%s count=%d", category, len(out))
            return out
        except requests.exceptions.RequestException as e:
            logger.warning("get_symbols_list network failed: %s", e)
            return []
        except Exception as e:
            logger.warning("get_symbols_list failed: %s", e)
            return []

    def get_klines_both_markets(
        self,
        symbol: str,
        interval: str = "15",
        limit: int = 200,
    ) -> dict[str, list[dict]]:
        """
        Fetch klines from BOTH SPOT and LINEAR markets in parallel.

        This is essential for TradingView parity since TV uses SPOT data,
        while we may want LINEAR for actual perpetual trading.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            interval: Timeframe (e.g. '15' for 15m)
            limit: Number of candles to fetch

        Returns:
            Dict with 'spot' and 'linear' keys, each containing list of candles
        """
        import concurrent.futures

        results: dict[str, list[dict]] = {"spot": [], "linear": []}

        def fetch_market(market_type: str) -> list[dict]:
            """Fetch klines for a specific market type."""
            v5_kline_url = "https://api.bybit.com/v5/market/kline"
            symbol_upper = symbol.upper()

            # Normalize interval
            interval_norm = interval
            if interval.endswith("m"):
                interval_norm = interval[:-1]
            elif interval.endswith("h"):
                interval_norm = str(int(interval[:-1]) * 60)

            params: dict[str, str | int] = {
                "category": market_type,
                "symbol": symbol_upper,
                "interval": interval_norm,
                "limit": limit,
            }

            try:
                r = requests.get(v5_kline_url, params=params, timeout=self.timeout)
                r.raise_for_status()
                payload = r.json()

                result = payload.get("result") or payload.get("data") or payload
                if isinstance(result, dict) and "list" in result:
                    data = result["list"]
                elif isinstance(result, list):
                    data = result
                else:
                    data = []

                if data:
                    normalized = [self._normalize_kline_row(d) for d in data]
                    # Add market_type and interval to each row
                    for row in normalized:
                        row["market_type"] = market_type
                        row["interval"] = interval
                    return normalized
                return []
            except Exception as e:
                logger.warning(f"Failed to fetch {market_type} klines for {symbol}: {e}")
                return []

        # Fetch both markets in parallel using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            spot_future = executor.submit(fetch_market, "spot")
            linear_future = executor.submit(fetch_market, "linear")

            results["spot"] = spot_future.result()
            results["linear"] = linear_future.result()

        logger.info(
            f"Fetched SPOT: {len(results['spot'])} candles, "
            f"LINEAR: {len(results['linear'])} candles for {symbol}/{interval}"
        )

        return results

    def persist_klines_with_market_type(
        self,
        symbol: str,
        market_type: str,
        normalized_rows: list[dict],
    ) -> int:
        """
        Persist klines with explicit market_type (spot/linear).

        Args:
            symbol: Trading pair
            market_type: 'spot' or 'linear'
            normalized_rows: List of normalized kline dicts

        Returns:
            Number of rows inserted
        """
        from sqlalchemy import text

        from backend.database import SessionLocal

        if not normalized_rows:
            return 0

        inserted = 0

        try:
            with SessionLocal() as session:
                for row in normalized_rows:
                    open_time = row.get("open_time")
                    if open_time is None:
                        continue

                    # Check if already exists
                    existing = session.execute(
                        text("""
                            SELECT id FROM bybit_kline_audit
                            WHERE symbol = :symbol
                            AND interval = :interval
                            AND market_type = :market_type
                            AND open_time = :open_time
                        """),
                        {
                            "symbol": symbol,
                            "interval": row.get("interval", "UNKNOWN"),
                            "market_type": market_type,
                            "open_time": open_time,
                        },
                    ).fetchone()

                    if existing:
                        continue

                    # Insert new row
                    raw_val = row.get("raw") if "raw" in row else row
                    if not isinstance(raw_val, str):
                        raw_val = json.dumps(raw_val, ensure_ascii=False)

                    session.execute(
                        text("""
                            INSERT INTO bybit_kline_audit
                            (symbol, interval, market_type, open_time, open_time_dt,
                             open_price, high_price, low_price, close_price, volume, turnover, raw)
                            VALUES
                            (:symbol, :interval, :market_type, :open_time, :open_time_dt,
                             :open_price, :high_price, :low_price, :close_price, :volume, :turnover, :raw)
                        """),
                        {
                            "symbol": symbol,
                            "interval": row.get("interval", "UNKNOWN"),
                            "market_type": market_type,
                            "open_time": open_time,
                            "open_time_dt": row.get("open_time_dt"),
                            "open_price": row.get("open") or row.get("open_price"),
                            "high_price": row.get("high") or row.get("high_price"),
                            "low_price": row.get("low") or row.get("low_price"),
                            "close_price": row.get("close") or row.get("close_price"),
                            "volume": row.get("volume"),
                            "turnover": row.get("turnover"),
                            "raw": raw_val,
                        },
                    )
                    inserted += 1

                session.commit()

        except Exception as e:
            logger.error(f"Failed to persist klines: {e}")

        return inserted


def _safe_float(val: str | None) -> float | None:
    try:
        return float(val) if val is not None and val != "" else None
    except Exception:
        return None


def _to_dt(ms: int | None):
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=UTC) if ms is not None else None
    except Exception:
        return None
