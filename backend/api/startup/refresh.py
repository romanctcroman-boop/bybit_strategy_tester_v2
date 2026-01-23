"""
Daily Data Refresh Module

Handles background refresh of daily candle data for volatility calculations.
Extracted from app.py lifespan for better modularity.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def refresh_daily_data_background(
    initial_delay: float = 5.0,
    rate_limit_delay: float = 0.2,
) -> None:
    """
    Refresh daily candle data for all symbols in background.

    This ensures daily volatility data is available for risk calculations.

    Args:
        initial_delay: Seconds to wait before starting (default 5s)
        rate_limit_delay: Seconds between API calls (default 0.2s)
    """
    await asyncio.sleep(initial_delay)  # Wait for server to fully start

    try:
        from sqlalchemy import distinct, func

        from backend.database import SessionLocal
        from backend.models.bybit_kline_audit import BybitKlineAudit
        from backend.services.adapters.bybit import BybitAdapter

        db = SessionLocal()
        try:
            # Get all unique symbols
            symbols = db.query(distinct(BybitKlineAudit.symbol)).all()
            symbols = [s[0] for s in symbols if s[0]]

            if not symbols:
                logger.info("[VOLATILITY] No symbols in DB to refresh daily data")
                return

            adapter = BybitAdapter(
                api_key=os.environ.get("BYBIT_API_KEY"),
                api_secret=os.environ.get("BYBIT_API_SECRET"),
            )

            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            one_day_ms = 24 * 60 * 60 * 1000
            updated = 0

            for symbol in symbols:
                # Check latest daily candle
                latest = (
                    db.query(func.max(BybitKlineAudit.open_time))
                    .filter(
                        BybitKlineAudit.symbol == symbol,
                        BybitKlineAudit.interval == "D",
                    )
                    .scalar()
                )

                # Skip if fresh (less than 1 day old)
                if latest and (now_ms - latest) < one_day_ms:
                    continue

                # Fetch and persist daily candles
                try:
                    rows = adapter.get_klines(symbol=symbol, interval="D", limit=90)
                    if rows:
                        rows_with_interval = [{**r, "interval": "D"} for r in rows]
                        adapter._persist_klines_to_db(symbol, rows_with_interval)
                        updated += 1
                except Exception as e:
                    logger.info(f"[VOLATILITY] Skipped refresh {symbol}: {e}")

                await asyncio.sleep(rate_limit_delay)  # Rate limiting

            logger.info(
                f"[VOLATILITY] Daily data refresh: {updated}/{len(symbols)} symbols updated"
            )
        finally:
            db.close()

    except Exception as e:
        logger.info(f"[VOLATILITY] Background refresh skipped: {e}")


def start_daily_refresh_task() -> asyncio.Task:
    """
    Start the daily data refresh as a background task.

    Returns:
        The created asyncio Task
    """
    return asyncio.create_task(refresh_daily_data_background())


__all__ = ["refresh_daily_data_background", "start_daily_refresh_task"]
