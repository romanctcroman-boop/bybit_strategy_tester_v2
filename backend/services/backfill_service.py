from __future__ import annotations

"""
Historical Backfill Service

- Fetches historical candles from BybitAdapter in pages (most-recent backwards by start_time)
- Persists into BybitKlineAudit idempotently (UNIQUE(symbol, open_time))
- Supports lookback minutes or explicit date range
"""
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger

from backend.database import Base, SessionLocal, engine
from backend.models.backfill_progress import BackfillProgress
from backend.services.adapters.bybit import BybitAdapter


def utc_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=UTC).timestamp() * 1000)


def ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


@dataclass
class BackfillConfig:
    symbol: str
    interval: str = "1"
    lookback_minutes: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    page_limit: int = 1000
    pause_sec: float = 0.2
    max_pages: int = 500


class BackfillService:
    def __init__(self, adapter: BybitAdapter | None = None):
        self.adapter = adapter or BybitAdapter()

    def backfill(self, cfg: BackfillConfig, *, resume: bool = True, return_stats: bool = False):
        """Run backfill according to config.

        Returns by default a tuple (upserts, pages).
        If return_stats=True, returns (upserts, pages, eta_seconds, est_pages_left).
        """
        # Ensure schema exists (safe for sqlite tests)
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass

        end_ms = utc_ms(cfg.end_at) if cfg.end_at else int(time.time() * 1000)
        if cfg.lookback_minutes and not cfg.start_at:
            start_ms = end_ms - cfg.lookback_minutes * 60 * 1000
        else:
            start_ms = utc_ms(cfg.start_at) if cfg.start_at else None

        done = 0
        pages = 0
        current_cursor = end_ms

        # resume support: load cursor from BackfillProgress (walk back from stored cursor)
        if resume:
            try:
                s = SessionLocal()
                try:
                    rec = (
                        s.query(BackfillProgress)
                        .filter(
                            BackfillProgress.symbol == cfg.symbol,
                            BackfillProgress.interval == cfg.interval,
                        )
                        .one_or_none()
                    )
                    if (
                        rec
                        and rec.current_cursor_ms is not None
                        and rec.current_cursor_ms < current_cursor
                    ):
                        current_cursor = rec.current_cursor_ms
                finally:
                    s.close()
            except Exception:
                pass

        started_at = time.perf_counter()

        while pages < cfg.max_pages:
            pages += 1
            # Fetch a page from adapter (most recent page up to current_cursor)
            rows = self._fetch_page_with_retries(
                cfg.symbol, cfg.interval, cfg.page_limit, current_cursor
            )
            if not rows:
                logger.info("No more rows from adapter; stop")
                break

            # Filter by start_ms if given
            if start_ms is not None:
                rows = [r for r in rows if r.get("open_time") and r["open_time"] >= start_ms]
                if not rows:
                    logger.info("Reached start boundary; stop")
                    break

            # Persist idempotently
            inserted = self._persist(cfg.symbol, rows)
            done += inserted

            # Move cursor back by one bar from the oldest row in this page
            oldest_ms = min(r["open_time"] for r in rows if r.get("open_time"))
            # subtract 1 ms to avoid including the same oldest row next page
            current_cursor = oldest_ms - 1

            # persist progress cursor
            try:
                s = SessionLocal()
                try:
                    rec = (
                        s.query(BackfillProgress)
                        .filter(
                            BackfillProgress.symbol == cfg.symbol,
                            BackfillProgress.interval == cfg.interval,
                        )
                        .one_or_none()
                    )
                    if not rec:
                        rec = BackfillProgress(
                            symbol=cfg.symbol,
                            interval=cfg.interval,
                            current_cursor_ms=current_cursor,
                        )
                        s.add(rec)
                    else:
                        rec.current_cursor_ms = current_cursor
                    s.commit()
                finally:
                    s.close()
            except Exception:
                pass

            # simple live metrics and ETA estimation
            elapsed = max(time.perf_counter() - started_at, 1e-6)
            rps = done / elapsed
            est_pages_left = None
            eta = None
            if len(rows) > 0 and cfg.page_limit > 0 and start_ms is not None:
                # milliseconds remaining until reaching start_ms boundary
                ms_left = max(current_cursor - start_ms, 0)
                # approx span per page based on current page
                try:
                    span_ms = rows[-1]["open_time"] - rows[0]["open_time"]
                    if span_ms <= 0:
                        span_ms = 60_000
                except Exception:
                    span_ms = 60_000
                est_pages_left = int(ms_left / max(span_ms, 1))
                eta = (
                    (elapsed / max(pages, 1)) * est_pages_left
                    if est_pages_left is not None
                    else None
                )

            logger.info(
                f"Backfill page {pages}: {len(rows)} rows, total upserts {done}, rps={rps:.1f}, est_pages_left={est_pages_left}, eta={eta and round(eta, 1)}s"
            )
            time.sleep(cfg.pause_sec)

        if return_stats:
            return done, pages, eta, est_pages_left
        return done, pages

    def _fetch_page(
        self, symbol: str, interval: str, limit: int, end_open_time_ms: int | None
    ) -> list[dict]:
        """
        Adapter currently does not expose time-bounded params. We'll fetch `limit` most-recent
        and then rely on DB idempotency and the moving cursor to walk back. If adapter later supports
        `end`/`from` params, wire them here.
        """
        try:
            rows = self.adapter.get_klines(symbol=symbol, interval=interval, limit=limit)
            # Adapter returns newest-first or oldest-first depending on endpoint; sort asc by open_time
            rows = [r for r in rows if r.get("open_time")]
            rows.sort(key=lambda r: r["open_time"])
            # If end_open_time_ms is given, drop rows newer than it
            if end_open_time_ms is not None:
                rows = [r for r in rows if r["open_time"] <= end_open_time_ms]
            return rows
        except Exception as e:
            logger.error(f"Adapter fetch failed: {e}")
            return []

    def _fetch_page_with_retries(
        self, symbol: str, interval: str, limit: int, end_open_time_ms: int | None
    ) -> list[dict]:
        max_attempts = 6
        base_backoff = 0.5
        for attempt in range(1, max_attempts + 1):
            rows = self._fetch_page(symbol, interval, limit, end_open_time_ms)
            if rows:
                return rows
            # No rows or error; inspect adapter last status if available
            status = getattr(self.adapter, "_last_status", None)
            # 2xx/304 with empty -> assume end-of-data quickly
            if status is None or (200 <= status < 300) or status == 304:
                if attempt >= 2:
                    return []
                delay = base_backoff * (2 ** (attempt - 1))
                logger.warning(
                    f"Empty page (status={status}), retrying briefly in {delay:.1f}s (attempt {attempt}/{max_attempts})"
                )
                time.sleep(delay)
                continue
            # 429 or 5xx -> exponential backoff and keep trying a few times
            if status == 429 or 500 <= status < 600:
                delay = min(8.0, base_backoff * (2 ** (attempt - 1)))
                logger.warning(
                    f"HTTP {status} from adapter; backoff {delay:.1f}s (attempt {attempt}/{max_attempts})"
                )
                time.sleep(delay)
                continue
            # Other 4xx -> likely fatal for this request; stop early
            if 400 <= status < 500:
                logger.error(
                    f"HTTP {status} from adapter; treating as terminal error/end-of-data for this window"
                )
                return []
            # Fallback generic small backoff
            delay = base_backoff * (2 ** (attempt - 1))
            logger.warning(f"Adapter status unknown={status}; retry in {delay:.1f}s")
            time.sleep(delay)
        return []

    def _persist(self, symbol: str, rows: list[dict]) -> int:
        # Use BybitAdapter persistence helper (idempotent upsert), decoupled from fetch adapter
        try:
            BybitAdapter()._persist_klines_to_db(symbol, rows)
            return len(rows)
        except Exception as e:
            logger.error(f"Persist failed: {e}")
            return 0


def backfill_cli(symbol: str, interval: str = "1", lookback_days: int = 7, page_limit: int = 1000):
    svc = BackfillService()
    cfg = BackfillConfig(
        symbol=symbol,
        interval=interval,
        lookback_minutes=lookback_days * 24 * 60,
        page_limit=page_limit,
    )
    n, pages = svc.backfill(cfg)
    logger.info(f"Backfill completed: upserts={n}, pages={pages}")
