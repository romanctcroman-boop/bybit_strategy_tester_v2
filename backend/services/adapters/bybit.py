"""Thin Bybit API v5 adapter.

Behavior:
 - If `pybit` is installed, use its SDK for authenticated calls.
 - Otherwise, fall back to direct REST calls using `requests` for public endpoints.

This module focuses on a small subset used by the strategy tester: fetching klines (candles) and recent trades.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    # pybit v2+ (the unofficial/official clients vary by name); attempt common import
    from pybit import HTTP as PybitHTTP  # type: ignore

    _HAS_PYBIT = True
except Exception:
    PybitHTTP = None
    _HAS_PYBIT = False

import requests


class BybitAdapter:
    def __init__(
        self, api_key: Optional[str] = None, api_secret: Optional[str] = None, timeout: int = 10
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
        # cache of discovered instruments: symbol -> metadata
        self._instruments_cache: Dict[str, Dict] = {}
        self._instruments_cache_at: Optional[float] = None
        # cache TTL in seconds
        self._instruments_cache_ttl = 60 * 5
        # last HTTP status observed (for observability/backoff tuning)
        self._last_status: Optional[int] = None

    def get_klines(self, symbol: str, interval: str = "1", limit: int = 200) -> List[Dict]:
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
                res = self._client.kline(symbol=symbol, interval=interval, limit=limit)
                # pybit may return nested structure; attempt to normalize
                data = res.get("result") if isinstance(res, dict) and "result" in res else res
                if isinstance(data, dict) and "list" in data:
                    data = data["list"]
                return [self._normalize_kline_row(r) for r in data]
            except Exception:
                logger.exception("pybit client kline failed, falling back to REST")

        # FAST PATH: Try direct v5 kline endpoint first (2 second timeout, no instrument discovery)
        v5_kline_url = "https://api.bybit.com/v5/market/kline"
        candidates = [symbol, symbol.upper()]
        # common heuristics: add USDT suffix if missing (most linear perpetuals are SYMBOLUSDT)
        if not symbol.upper().endswith("USDT"):
            candidates.append(symbol.upper() + "USDT")

        for chosen_symbol in candidates:
            try:
                params = {
                    "category": "linear",
                    "symbol": chosen_symbol,
                    "interval": interval_norm,
                    "limit": limit,
                }
                r = requests.get(v5_kline_url, params=params, timeout=2)  # SHORT timeout: 2 seconds
                r.raise_for_status()
                payload = r.json()
                self._last_status = r.status_code
                result = payload.get("result") or payload.get("data") or payload
                if isinstance(result, dict) and "list" in result:
                    data = result["list"]
                elif isinstance(result, list):
                    data = result
                else:
                    data = []

                if data:
                    logger.info(
                        f"Successfully fetched {len(data)} klines from Bybit for {chosen_symbol}"
                    )
                    normalized = [self._normalize_kline_row(d) for d in data]
                    # attempt to persist normalized candles to audit table (best-effort)
                    try:
                        self._persist_klines_to_db(chosen_symbol, normalized)
                    except Exception:
                        logger.exception("Failed to persist klines to DB")
                    return normalized
            except Exception as ex:
                try:
                    # record status code if available
                    self._last_status = (
                        getattr(ex.response, "status_code", None)
                        if hasattr(ex, "response")
                        else None
                    )
                except Exception:
                    pass
                logger.debug(
                    f"Bybit v5 kline fetch failed for {chosen_symbol}, trying next candidate...",
                    exc_info=False,
                )
                continue

        # Try spot quote v1 endpoint (older path)
        try:
            url_spot = "https://api.bybit.com/spot/quote/v1/kline"
            params = {"symbol": symbol, "interval": interval_norm, "limit": limit}
            r = requests.get(url_spot, params=params, timeout=2)
            r.raise_for_status()
            payload = r.json()
            self._last_status = r.status_code
            data = payload.get("result") or payload.get("data") or payload.get("list") or []
            if isinstance(data, dict) and "list" in data:
                data = data["list"]
            if data:
                logger.info(f"Successfully fetched {len(data)} klines from Bybit Spot")
                normalized = [self._normalize_kline_row(d) for d in data]
                try:
                    self._persist_klines_to_db(symbol, normalized)
                except Exception:
                    logger.exception("Failed to persist klines to DB")
                return normalized
        except Exception as ex:
            try:
                self._last_status = (
                    getattr(ex.response, "status_code", None) if hasattr(ex, "response") else None
                )
            except Exception:
                pass
            logger.debug("Bybit spot quote probe failed, trying legacy endpoint...", exc_info=False)

        # Legacy / older linear kline endpoint fallback
        try:
            url = "https://api.bybit.com/public/linear/kline"
            params = {"symbol": symbol, "interval": interval_norm.replace("m", ""), "limit": limit}
            r = requests.get(url, params=params, timeout=2)
            r.raise_for_status()
            payload = r.json()
            self._last_status = r.status_code
            data = payload.get("result") or payload.get("data") or []
            if isinstance(data, dict) and "list" in data:
                data = data["list"]
            if data:
                logger.info(f"Successfully fetched {len(data)} klines from legacy endpoint")
                return [self._normalize_kline_row(d) for d in data]
        except Exception as ex:
            try:
                self._last_status = (
                    getattr(ex.response, "status_code", None) if hasattr(ex, "response") else None
                )
            except Exception:
                pass
            logger.exception("All Bybit probes failed")
            raise

    def _normalize_kline_row(self, row: Dict) -> Dict:
        # Accept both list-style and dict-style rows
        # Always preserve the original data under 'raw' to avoid any data loss
        if isinstance(row, list):
            raw: Any = list(row)
            # Bybit v5 list format documented: [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover?]
            parsed: Dict[str, Any] = {"raw": raw}
            try:
                start_ms = int(raw[0])
                parsed["open_time"] = start_ms
                parsed["open_time_dt"] = datetime.fromtimestamp(start_ms / 1000.0, tz=timezone.utc)
            except Exception:
                parsed["open_time"] = None
                parsed["open_time_dt"] = None

            # map string fields and keep originals
            def _as_str(idx: int) -> Optional[str]:
                try:
                    return str(raw[idx])
                except Exception:
                    return None

            def _as_float(val: Optional[str]) -> Optional[float]:
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
            parsed["turnover"] = (
                _as_float(parsed["turnover_str"])
                if parsed.get("turnover_str") is not None
                else None
            )
            return parsed
        elif isinstance(row, dict):
            raw = dict(row)
            parsed: Dict[str, Any] = {"raw": raw}
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
            parsed["open_time_dt"] = (
                datetime.fromtimestamp(start_ms / 1000.0, tz=timezone.utc)
                if start_ms is not None
                else None
            )

            def get_str(*keys) -> Optional[str]:
                for k in keys:
                    v = raw.get(k)
                    if v is not None:
                        return str(v)
                return None

            parsed["open_price_str"] = get_str("openPrice", "open", "o")
            parsed["open"] = (
                _safe_float(parsed["open_price_str"]) if "open_price_str" in parsed else None
            )
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
        normalized_rows: List[Dict],
        db: Optional[object] = None,
        engine: Optional[object] = None,
    ):
        """Persist normalized klines (list of dicts as returned by _normalize_kline_row) into audit table.

        Behaviour: best-effort; uses UNIQUE(symbol, open_time) to avoid duplicates.
        """
        # import DB objects lazily to avoid import-time circular dependencies in tests
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
            def _pick(*keys):
                for k in keys:
                    if k in row and row.get(k) is not None:
                        return row.get(k)
                return None

            params.append(
                {
                    "symbol": symbol,
                    "open_time": open_time,
                    "open_time_dt": (
                        row.get("open_time_dt")
                        if row.get("open_time_dt") is not None
                        else _to_dt(open_time)
                    ),
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
            except Exception:
                pass

        if _engine is None:
            # Last-resort: create engine from DATABASE_URL
            _database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
            _engine = _create_engine(
                _database_url,
                connect_args=(
                    {"check_same_thread": False} if _database_url.startswith("sqlite") else {}
                ),
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
            try:
                BybitKlineAudit.__table__.create(bind=target_bind, checkfirst=True)
            except Exception:
                # ignore create failures; we'll surface DB errors during execute
                pass
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
                except Exception:
                    pass
        except Exception:
            pass

        # Accept the candidate only if it looks like a real SQLAlchemy Session
        def _is_session_like(o):
            return o is not None and (
                hasattr(o, "execute")
                or hasattr(o, "query")
                or hasattr(o, "begin")
                or hasattr(o, "get_bind")
            )

        if _is_session_like(candidate):
            db = candidate
        else:
            # fallback: create a proper sessionmaker bound to the engine
            from sqlalchemy.orm import sessionmaker as _sessionmaker

            db = _sessionmaker(bind=_engine)()

        try:
            if dialect in ("postgres", "postgresql"):
                sql = text(
                    """
                    INSERT INTO bybit_kline_audit
                        (symbol, open_time, open_time_dt, open_price, high_price, low_price, close_price, volume, turnover, raw)
                    VALUES
                        (:symbol, :open_time, :open_time_dt, :open_price, :high_price, :low_price, :close_price, :volume, :turnover, :raw)
                    ON CONFLICT (symbol, open_time) DO UPDATE SET
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
                        (symbol, open_time, open_time_dt, open_price, high_price, low_price, close_price, volume, turnover, raw)
                    VALUES
                        (:symbol, :open_time, :open_time_dt, :open_price, :high_price, :low_price, :close_price, :volume, :turnover, :raw)
                    ON CONFLICT(symbol, open_time) DO UPDATE SET
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
            # safest rollback attempt for real sessions
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
                # best-effort close; ignore errors closing the session
                pass

    # Instrument discovery and validation
    def _refresh_instruments_cache(self, force: bool = False):
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
            r = requests.get(v5_url_info, params={"category": "linear"}, timeout=self.timeout)
            r.raise_for_status()
            info = r.json()
            instruments = (
                info.get("result", {}).get("list", [])
                if isinstance(info.get("result"), dict)
                else info.get("result") or []
            )
            self._instruments_cache = {
                itm.get("symbol"): itm
                for itm in instruments
                if isinstance(itm, dict) and itm.get("symbol")
            }
            self._instruments_cache_at = now
        except Exception:
            logger.exception("Failed to refresh instruments cache")

    def get_recent_trades(self, symbol: str, limit: int = 250) -> List[Dict]:
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
                r = requests.get(v5_trades_url, params=params, timeout=2)
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
                    logger.info(
                        f"Successfully fetched {len(data)} trades from Bybit for {chosen_symbol}"
                    )
                    # Normalize trades
                    normalized = []
                    for trade in data:
                        if isinstance(trade, dict):
                            normalized.append(
                                {
                                    "time": int(trade.get("execTime", trade.get("time", 0))),
                                    "price": float(trade.get("price", 0)),
                                    "qty": float(trade.get("size", trade.get("qty", 0))),
                                    "side": trade.get("side", "Unknown").lower(),  # 'Buy' or 'Sell'
                                }
                            )
                    return normalized
            except Exception:
                logger.debug(f"Bybit v5 trades fetch failed for {chosen_symbol}", exc_info=False)
                continue

        # Fallback: return empty list if all failed
        logger.warning(f"Could not fetch recent trades for {symbol}")
        return []

    def validate_symbol(self, symbol: str) -> str:
        """Validate and normalize a symbol. Returns the canonical symbol if valid, else raises ValueError.

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


def _safe_float(val: Optional[str]) -> Optional[float]:
    try:
        return float(val) if val is not None and val != "" else None
    except Exception:
        return None


def _to_dt(ms: Optional[int]):
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc) if ms is not None else None
    except Exception:
        return None
