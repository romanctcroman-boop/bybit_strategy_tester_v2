"""Thin Bybit API v5 adapter.

Behavior:
 - If `pybit` is installed, use its SDK for authenticated calls.
 - Otherwise, fall back to direct REST calls using `requests` for public endpoints.

This module focuses on a small subset used by the strategy tester: fetching klines (candles) and recent trades.
"""

import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from typing import Any

import requests

# Try to import project-specific modules; fall back to defaults if not available
try:
    from backend.core.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

try:
    from backend.reliability.http_retry import requests_retry

    _HAS_RETRY = True
except ImportError:
    _HAS_RETRY = False

    def requests_retry(operation_name: str, func):
        """Fallback: just call the function directly."""
        return func()


try:
    # pybit v2+ (the unofficial/official clients vary by name); attempt common import
    from pybit import HTTP as PybitHTTP  # type: ignore

    _HAS_PYBIT = True
except Exception:
    PybitHTTP = None
    _HAS_PYBIT = False


class BybitAdapter:
    """
    Bybit API adapter for market data fetching.

    NOTE: API credentials are stored with basic XOR obfuscation in memory.
    For production with private endpoints, use proper secrets management.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: int = 10,
    ):
        # Basic XOR obfuscation for in-memory credential storage
        # NOTE: For production, use proper secrets management (Vault, AWS Secrets, etc.)
        import secrets

        self._session_key = secrets.token_bytes(16)
        self._api_key_encrypted = self._xor_encrypt(api_key.encode(), self._session_key) if api_key else b""
        self._api_secret_encrypted = self._xor_encrypt(api_secret.encode(), self._session_key) if api_secret else b""

        self.timeout = timeout
        self.session = requests.Session()
        self.last_chosen_symbol: str | None = None

        if _HAS_PYBIT and api_key and api_secret:
            # pybit HTTP client (uses linear/perpetual endpoints by default)
            try:
                self._client = PybitHTTP(api_key=api_key, api_secret=api_secret)
            except Exception:
                self._client = None
        else:
            self._client = None

        # cache of discovered instruments: symbol -> metadata
        self._instruments_cache: dict[str, dict] = {}
        self._instruments_cache_at: float | None = None
        # cache TTL in seconds
        self._instruments_cache_ttl = 60 * 5

    @staticmethod
    def _xor_encrypt(data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption for in-memory credential obfuscation."""
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    @property
    def api_key(self) -> str | None:
        """Decrypt and return API key."""
        if not self._api_key_encrypted:
            return None
        return self._xor_encrypt(self._api_key_encrypted, self._session_key).decode()

    @property
    def api_secret(self) -> str | None:
        """Decrypt and return API secret."""
        if not self._api_secret_encrypted:
            return None
        return self._xor_encrypt(self._api_secret_encrypted, self._session_key).decode()

    def _requests_get(
        self,
        operation_name: str,
        url: str,
        *,
        params: dict | None = None,
        timeout: float = 2.0,
    ):
        """Perform a GET request with the shared retry strategy."""

        def _call():
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response

        return requests_retry(operation_name, _call)

    def get_klines(self, symbol: str, interval: str = "1", limit: int = 200) -> list[dict]:
        """Fetch kline/candle data. interval is minutes as string in Bybit public API mapping.

        Returns list of dicts with keys: open_time, open, high, low, close, volume
        """

        # normalize interval to Bybit v5 format: minutes as integer strings (e.g. '1', '3', '60')
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
                # Bybit often uses 'D' for daily; return 'D'
                return "D"
            return itv

        interval_norm = _to_v5_interval(interval)

        if self._client:
            try:
                res = requests_retry(
                    "bybit.get_klines",
                    lambda: self._client.kline(symbol=symbol, interval=interval, limit=limit),
                )
                # pybit may return nested structure; attempt to normalize
                data = res.get("result") if isinstance(res, dict) and "result" in res else res
                if isinstance(data, dict) and "list" in data:
                    data = data["list"]
                return [self._normalize_kline_row(r) for r in data]
            except Exception:
                logger.exception("pybit client kline failed, falling back to REST")

        # Prefer perpetual/linear futures (category='linear') — discover available instruments first
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
            # Build a mapping of symbol -> instrument metadata for smarter selection
            available_meta = {
                itm.get("symbol"): itm for itm in instruments if isinstance(itm, dict) and itm.get("symbol")
            }
            available = set(available_meta.keys())
        except Exception:
            logger.debug(
                "Could not discover linear instruments via instruments-info; will still try kline endpoints",
                exc_info=True,
            )
            available = set()
            available_meta = {}

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

        # If discovery returned many instruments, try to pick a sane default
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
                r = self._requests_get(
                    "bybit.get_klines",
                    v5_kline_url,
                    params=params,
                    timeout=2,
                )
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
                        self._persist_klines_to_db(chosen, normalized)
                    except Exception:
                        logger.exception("Failed to persist klines to DB")
                    return normalized
            except Exception:
                logger.debug("Bybit linear kline probe failed for %s", chosen, exc_info=True)

        # If we reach here, try the legacy/public endpoints as fallback (best-effort)

        # Try spot quote v1 endpoint (older path)
        try:
            url_spot = "https://api.bybit.com/spot/quote/v1/kline"
            params = {"symbol": symbol, "interval": interval_norm, "limit": limit}
            r = self._requests_get(
                "bybit.get_spot_kline",
                url_spot,
                params=params,
                timeout=2,
            )
            payload = r.json()
            data = payload.get("result") or payload.get("data") or payload.get("list") or []
            if isinstance(data, dict) and "list" in data:
                data = data["list"]
            if data:
                normalized = [self._normalize_kline_row(d) for d in data]
                try:
                    self._persist_klines_to_db(symbol, normalized)
                except Exception:
                    logger.exception("Failed to persist klines to DB")
                return normalized
        except Exception:
            logger.debug(
                "Bybit spot quote probe failed, falling back to legacy/public endpoints",
                exc_info=True,
            )

        # Legacy / older linear kline endpoint fallback
        try:
            url = "https://api.bybit.com/public/linear/kline"
            params = {
                "symbol": symbol,
                "interval": interval_norm.replace("m", ""),
                "limit": limit,
            }
            r = self._requests_get(
                "bybit.get_legacy_kline",
                url,
                params=params,
                timeout=2,
            )
            payload = r.json()
            data = payload.get("result") or payload.get("data") or []
            if isinstance(data, dict) and "list" in data:
                data = data["list"]
            return [self._normalize_kline_row(d) for d in data]
        except Exception:
            logger.exception("All Bybit probes failed")
            raise

    def get_klines_historical(
        self,
        symbol: str,
        interval: str = "1",
        total_candles: int = 2000,
        end_time: int | None = None,
    ) -> list[dict]:
        """Load historical candles, handling API limit of 1000 candles per request.

        Makes multiple requests, moving backwards in time.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Candle interval ('1', '5', '15', '60', 'D' etc.)
            total_candles: Total number of candles to load
            end_time: End timestamp (ms). If None - current time

        Returns:
            List of candles, sorted by time (oldest to newest)
        """

        # Calculate interval in milliseconds
        def get_interval_ms(interval_str: str) -> int:
            interval_str = str(interval_str)
            if interval_str == "D":
                return 86400000  # 24 hours in ms
            elif interval_str == "W":
                return 604800000  # 7 days in ms
            elif interval_str.endswith("m") or interval_str.endswith("M"):
                minutes = int(interval_str[:-1])
                return minutes * 60000
            elif interval_str.endswith("h") or interval_str.endswith("H"):
                hours = int(interval_str[:-1])
                return hours * 3600000
            else:
                # Assume minutes
                return int(interval_str) * 60000

        interval_ms = get_interval_ms(interval)
        current_end = end_time or int(time.time() * 1000)

        all_candles: list[dict] = []
        batch_size = 1000  # Maximum per request
        requests_made = 0
        max_requests = (total_candles // batch_size) + 2  # +2 for buffer

        logger.info(
            f"Starting historical fetch: {symbol} {interval}, target={total_candles} candles, end={current_end}"
        )

        while len(all_candles) < total_candles and requests_made < max_requests:
            # Calculate startTime for current batch
            # Moving backwards: end - (batch_size * interval)
            start_time = current_end - (batch_size * interval_ms)

            logger.info(f"Batch {requests_made + 1}: fetching {batch_size} candles, from {start_time} to {current_end}")

            # Request API with startTime and endTime
            batch = self._fetch_klines_with_time_range(
                symbol=symbol,
                interval=interval,
                limit=batch_size,
                start_time=start_time,
                end_time=current_end,
            )

            if not batch:
                logger.warning(f"No data returned for batch {requests_made + 1}, stopping")
                break

            logger.info(f"Received {len(batch)} candles in batch {requests_made + 1}")

            # Add to beginning of list (since we're going backwards in time)
            all_candles = batch + all_candles

            # Update end_time for next iteration
            if batch:
                # Get time of oldest candle in batch
                oldest_candle_time = min(c.get("open_time", 0) for c in batch)
                current_end = oldest_candle_time - interval_ms  # Shift backwards
            else:
                break

            requests_made += 1

            # Pause between requests to respect rate limits
            if requests_made < max_requests and len(all_candles) < total_candles:
                time.sleep(0.2)  # 200ms between requests

        # Deduplicate and sort
        seen_times: set[int] = set()
        unique_candles: list[dict] = []
        for candle in sorted(all_candles, key=lambda c: c.get("open_time", 0)):
            candle_time = candle.get("open_time")
            if candle_time and candle_time not in seen_times:
                seen_times.add(candle_time)
                unique_candles.append(candle)

        # Trim to requested count (take last N)
        result = unique_candles[-total_candles:] if len(unique_candles) > total_candles else unique_candles

        logger.info(f"Historical fetch complete: {len(result)} unique candles ({requests_made} API requests)")

        return result

    def _fetch_klines_with_time_range(
        self, symbol: str, interval: str, limit: int, start_time: int, end_time: int
    ) -> list[dict]:
        """Internal method to fetch candles with time range.

        Uses start and end API parameters of Bybit.
        """

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
        v5_kline_url = "https://api.bybit.com/v5/market/kline"

        candidates = [symbol, symbol.upper()]
        if not symbol.upper().endswith("USDT"):
            candidates.append(symbol.upper() + "USDT")

        for chosen_symbol in candidates:
            try:
                params = {
                    "category": "linear",
                    "symbol": chosen_symbol,
                    "interval": interval_norm,
                    "limit": limit,
                    "start": start_time,
                    "end": end_time,
                }

                r = self._requests_get(
                    "bybit.get_klines_historical",
                    v5_kline_url,
                    params=params,
                    timeout=5,
                )
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
                    return normalized

            except Exception as ex:
                logger.debug(
                    f"Fetch with time range failed for {chosen_symbol}: {ex}",
                    exc_info=False,
                )
                continue

        return []

    def get_recent_trades(self, symbol: str, limit: int = 250) -> list[dict]:
        """Fetch recent trades/ticks for a symbol.

        Returns list of dicts with keys: time, price, qty, side
        This provides real-time data that updates every tick (not every minute like candles).
        """
        # Try v5 public trades endpoint
        v5_trades_url = "https://api.bybit.com/v5/market/recent-trade"
        candidates = [symbol, symbol.upper()]
        if not symbol.upper().endswith("USDT"):
            candidates.append(symbol.upper() + "USDT")

        for chosen_symbol in candidates:
            try:
                params = {"category": "linear", "symbol": chosen_symbol, "limit": limit}
                r = self._requests_get(
                    "bybit.get_trades",
                    v5_trades_url,
                    params=params,
                    timeout=2,
                )
                payload = r.json()
                result = payload.get("result") or payload.get("data") or payload
                if isinstance(result, dict) and "list" in result:
                    data = result["list"]
                elif isinstance(result, list):
                    data = result
                else:
                    data = []

                if data:
                    logger.info(f"Successfully fetched {len(data)} trades from Bybit for {chosen_symbol}")
                    # Normalize trades
                    normalized = []
                    for trade in data:
                        if isinstance(trade, dict):
                            normalized.append(
                                {
                                    "time": int(trade.get("execTime", trade.get("time", 0))),
                                    "price": float(trade.get("price", 0)),
                                    "qty": float(trade.get("size", trade.get("qty", 0))),
                                    "side": trade.get("side", "Unknown").lower(),
                                }
                            )
                    return normalized
            except Exception:
                logger.debug(f"Bybit v5 trades fetch failed for {chosen_symbol}", exc_info=False)
                continue

        # Fallback: return empty list if all failed
        logger.warning(f"Could not fetch recent trades for {symbol}")
        return []

    def _normalize_kline_row(self, row: dict | list) -> dict:
        """Normalize kline row to standard format.

        Accept both list-style and dict-style rows.
        Always preserve the original data under 'raw' to avoid any data loss.
        """
        if isinstance(row, list):
            raw: Any = list(row)
            # Bybit v5 list format: [startTime, open, high, low, close, volume, turnover?]
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
            parsed: dict[str, Any] = {"raw": raw}
            # Common key aliases used across Bybit responses
            start_candidates = [
                raw.get("startTime"),
                raw.get("start_at"),
                raw.get("t"),
                raw.get("open_time"),
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
            parsed["open_time_dt"] = (
                datetime.fromtimestamp(start_ms / 1000.0, tz=UTC) if start_ms is not None else None
            )

            def get_str(*keys) -> str | None:
                for k in keys:
                    v = raw.get(k)
                    if v is not None:
                        return str(v)
                return None

            parsed["open_price_str"] = get_str("openPrice", "open", "o")
            parsed["open"] = _safe_float(parsed.get("open_price_str"))
            parsed["high_price_str"] = get_str("highPrice", "high", "h")
            parsed["high"] = _safe_float(parsed.get("high_price_str"))
            parsed["low_price_str"] = get_str("lowPrice", "low", "l")
            parsed["low"] = _safe_float(parsed.get("low_price_str"))
            parsed["close_price_str"] = get_str("closePrice", "close", "c")
            parsed["close"] = _safe_float(parsed.get("close_price_str"))
            parsed["volume_str"] = get_str("volume", "v")
            parsed["volume"] = _safe_float(parsed.get("volume_str"))
            parsed["turnover_str"] = get_str("turnover")
            parsed["turnover"] = _safe_float(parsed.get("turnover_str"))
            return parsed

        else:
            return {"raw": row}

    def _persist_klines_to_db(
        self,
        symbol: str,
        normalized_rows: list[dict],
        db: object | None = None,
        engine: object | None = None,
    ) -> None:
        """Persist normalized klines into audit table.

        Behaviour: best-effort; uses UNIQUE(symbol, open_time) to avoid duplicates.
        """
        # import DB objects lazily to avoid import-time circular dependencies in tests
        from sqlalchemy import text

        try:
            from backend.database import SessionLocal
            from backend.models.bybit_kline_audit import BybitKlineAudit
        except ImportError:
            logger.debug("Could not import database modules; skipping persistence")
            return

        # Respect env var BYBIT_PERSIST_KLINES (default true)
        persist_flag = os.environ.get("BYBIT_PERSIST_KLINES", "1").lower()
        if persist_flag not in ("1", "true", "yes", "y"):
            logger.debug("BYBIT_PERSIST_KLINES is false; skipping DB persistence")
            return

        # Prepare parameter rows
        params_list = []
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

            # Accept both styles: 'open'/'close' or 'open_price'/'close_price'.
            def _pick(*keys):
                for k in keys:
                    if k in row and row.get(k) is not None:
                        return row.get(k)
                return None

            params_list.append(
                {
                    "symbol": symbol,
                    "open_time": open_time,
                    "open_time_dt": row.get("open_time_dt") or _to_dt(open_time),
                    "open_price": _pick("open", "open_price", "open_price_str"),
                    "high_price": _pick("high", "high_price", "high_price_str"),
                    "low_price": _pick("low", "low_price", "low_price_str"),
                    "close_price": _pick("close", "close_price", "close_price_str"),
                    "volume": _pick("volume", "volume_str"),
                    "turnover": _pick("turnover", "turnover_str"),
                    "raw": raw_val,
                }
            )

        if not params_list:
            return

        # Allow callers to inject a DB session or engine for deterministic behavior in tests
        from sqlalchemy import create_engine as _create_engine

        _engine = engine
        user_db = db
        if db is None:
            # Try to use the project's canonical engine/session factory
            try:
                import backend.database as _dbmod

                _engine = _engine or getattr(_dbmod, "engine", None)
                SessionLocal = getattr(_dbmod, "SessionLocal", SessionLocal)
            except Exception:
                pass

        if _engine is None:
            # Last-resort: create engine from DATABASE_URL
            _database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
            connect_args = {"check_same_thread": False} if _database_url.startswith("sqlite") else {}
            _engine = _create_engine(_database_url, connect_args=connect_args)

        # determine dialect from engine
        bind = _engine
        dialect = bind.dialect.name if hasattr(bind, "dialect") else "sqlite"

        # Ensure the audit table exists
        try:
            target_bind = None
            if db is not None and hasattr(db, "get_bind"):
                try:
                    target_bind = db.get_bind()
                except Exception:
                    pass
            if target_bind is None:
                target_bind = _engine
            try:
                BybitKlineAudit.__table__.create(bind=target_bind, checkfirst=True)
            except Exception:
                pass
        except Exception:
            pass

        # Get a session
        candidate = None
        try:
            candidate = SessionLocal()
        except Exception:
            candidate = None

        # If the candidate session exposes get_bind(), prefer its engine
        try:
            if candidate is not None and hasattr(candidate, "get_bind"):
                session_engine = candidate.get_bind()
                if session_engine is not None:
                    _engine = session_engine
        except Exception:
            pass

        def _is_session_like(o):
            return o is not None and (
                hasattr(o, "execute") or hasattr(o, "query") or hasattr(o, "begin") or hasattr(o, "get_bind")
            )

        if _is_session_like(candidate):
            db = candidate
        else:
            from sqlalchemy.orm import sessionmaker as _sessionmaker

            db = _sessionmaker(bind=_engine)()

        try:
            if dialect in ("postgres", "postgresql"):
                sql = text("""
                    INSERT INTO bybit_kline_audit
                        (symbol, open_time, open_time_dt, open_price, high_price,
                         low_price, close_price, volume, turnover, raw)
                    VALUES
                        (:symbol, :open_time, :open_time_dt, :open_price, :high_price,
                         :low_price, :close_price, :volume, :turnover, :raw)
                    ON CONFLICT (symbol, open_time) DO UPDATE SET
                        open_time_dt = EXCLUDED.open_time_dt,
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        turnover = EXCLUDED.turnover,
                        raw = EXCLUDED.raw
                """)
                if user_db is not None:
                    with user_db.begin():
                        user_db.execute(sql, params_list)
                else:
                    try:
                        with _engine.begin() as conn:
                            conn.execute(sql, params_list)
                    except Exception:
                        with db.begin():
                            db.execute(sql, params_list)

            elif dialect.startswith("sqlite"):
                sql = text("""
                    INSERT INTO bybit_kline_audit
                        (symbol, open_time, open_time_dt, open_price, high_price,
                         low_price, close_price, volume, turnover, raw)
                    VALUES
                        (:symbol, :open_time, :open_time_dt, :open_price, :high_price,
                         :low_price, :close_price, :volume, :turnover, :raw)
                    ON CONFLICT(symbol, open_time) DO UPDATE SET
                        open_time_dt = excluded.open_time_dt,
                        open_price = excluded.open_price,
                        high_price = excluded.high_price,
                        low_price = excluded.low_price,
                        close_price = excluded.close_price,
                        volume = excluded.volume,
                        turnover = excluded.turnover,
                        raw = excluded.raw
                """)
                if user_db is not None:
                    with user_db.begin():
                        user_db.execute(sql, params_list)
                else:
                    try:
                        with _engine.begin() as conn:
                            conn.execute(sql, params_list)
                    except Exception:
                        with db.begin():
                            db.execute(sql, params_list)

            else:
                # Generic ORM fallback
                for p in params_list:
                    existing = (
                        db.query(BybitKlineAudit)
                        .filter(
                            BybitKlineAudit.symbol == p["symbol"],
                            BybitKlineAudit.open_time == p["open_time"],
                        )
                        .one_or_none()
                    )
                    if existing:
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
                        obj.raw = p["raw"]
                    except Exception:
                        obj.raw = str(p["raw"])
                    db.add(obj)
                db.commit()

        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                if db:
                    db.close()
            except Exception:
                pass

    # Instrument discovery and validation
    def _refresh_instruments_cache(self, force: bool = False) -> None:
        now = time.time()
        if (
            not force
            and self._instruments_cache
            and self._instruments_cache_at
            and (now - self._instruments_cache_at) < self._instruments_cache_ttl
        ):
            return

        v5_url_info = "https://api.bybit.com/v5/market/instruments-info"
        try:
            r = self._requests_get(
                "bybit.instrument_discovery",
                v5_url_info,
                params={"category": "linear"},
                timeout=self.timeout,
            )
            info = r.json()
            instruments = (
                info.get("result", {}).get("list", [])
                if isinstance(info.get("result"), dict)
                else info.get("result") or []
            )
            self._instruments_cache = {
                itm.get("symbol"): itm for itm in instruments if isinstance(itm, dict) and itm.get("symbol")
            }
            self._instruments_cache_at = now
        except Exception:
            logger.exception("Failed to refresh instruments cache")

    def validate_symbol(self, symbol: str) -> str:
        """Validate and normalize a symbol.

        Returns the canonical symbol if valid, else raises ValueError.

        Behavior:
        - Refreshes instruments cache if stale
        - Accepts lower/upper case and optionally missing USDT suffix
        - Prefers exact match in cache, otherwise tries adding USDT suffix
        - Raises ValueError if no valid trading instrument found
        """
        if not symbol:
            raise ValueError("empty symbol")

        self._refresh_instruments_cache()
        s = symbol.upper()

        # direct match
        if s in self._instruments_cache:
            meta = self._instruments_cache[s]
            if meta.get("status") == "Trading" and not meta.get("isPreListing"):
                return s
            raise ValueError(f"symbol {s} not trading")

        # try adding USDT
        if not s.endswith("USDT"):
            cand = s + "USDT"
            if cand in self._instruments_cache:
                meta = self._instruments_cache[cand]
                if meta.get("status") == "Trading" and not meta.get("isPreListing"):
                    return cand
                raise ValueError(f"symbol {cand} not trading")

        raise ValueError(f"symbol {symbol} not found in instruments-info")


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
