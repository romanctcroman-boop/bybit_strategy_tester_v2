"""
Live Signal Service.

Maintains a sliding OHLCV window and recomputes strategy signals on each
closed bar using the StrategyBuilderAdapter.

Design:
    - Initialized once per (symbol × interval × strategy) session.
    - Preloaded with historical warmup bars from DB so indicators have
      enough data to produce valid signals from the very first live bar.
    - Thread-safe: called from a single asyncio event loop (no locking needed).

Expert fixes applied (per review):
    1. push_closed_bar returns {"long": bool, "short": bool, "error": str, "bars_used": int}
       on failure — client is notified instead of receiving None silently.
    2. Empty bars (volume=0) are skipped — logged but not processed.
    3. Timing: if generate_signals() takes >2 s a WARNING is emitted.
"""

import logging
import time
from collections import deque

import pandas as pd

from backend.backtesting.strategy_builder_adapter import StrategyBuilderAdapter

logger = logging.getLogger(__name__)

# Warmup window size — covers 99% of indicator warmup periods:
#   RSI(14), MACD(26+9), Bollinger(20), Ichimoku senkou_b(52), SMA(200)
MIN_WARMUP_BARS = 500

# Performance budget — log warning if exceeded
_SIGNAL_COMPUTE_WARN_SECS = 2.0


class LiveSignalService:
    """
    Sliding OHLCV window + strategy signal recomputation for live bars.

    One instance per (symbol × interval × strategy) live-chart session.
    Created by the SSE endpoint when a valid builder_graph is available.

    Parameters
    ----------
    strategy_graph : dict
        The full builder_graph dict from the Strategy model
        (e.g. ``{"blocks": [...], "connections": [...]}``)
    warmup_bars : list[dict]
        Historical bars in chronological order.  Each bar is a dict with
        keys: "time" (epoch secs), "open", "high", "low", "close", "volume".
    warmup_size : int
        Maximum number of bars kept in the rolling window (default 500).
    symbol : str
        Symbol name — used only for logging/metrics.
    """

    def __init__(
        self,
        strategy_graph: dict,
        warmup_bars: list[dict],
        warmup_size: int = MIN_WARMUP_BARS,
        symbol: str = "UNKNOWN",
    ) -> None:
        self._adapter = StrategyBuilderAdapter(strategy_graph)
        self._warmup_size = warmup_size
        self._symbol = symbol
        self._window: deque[dict] = deque(maxlen=warmup_size)

        # Seed the window with historical bars (up to warmup_size most recent)
        for bar in warmup_bars[-warmup_size:]:
            self._window.append(bar)

        logger.info(
            "[LiveSignalService] Initialized for %s — %d warmup bars (maxlen=%d)",
            symbol,
            len(self._window),
            warmup_size,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push_closed_bar(self, candle: dict) -> dict:
        """
        Accept a closed bar, recompute strategy signals, return result.

        Parameters
        ----------
        candle : dict
            Keys: "time" (epoch secs), "open", "high", "low", "close", "volume".

        Returns
        -------
        dict
            Success: ``{"long": bool, "short": bool, "bars_used": int}``
            Failure: ``{"long": False, "short": False, "error": str, "bars_used": int}``

        Notes
        -----
        - Volume == 0 bars are skipped (returns an "empty_bar" dict).
        - If generate_signals() takes longer than 2 seconds a WARNING is logged.
        - Never raises — all exceptions are caught and reflected in the return dict.
        """
        # Expert fix #2: skip truly empty bars
        if candle.get("volume", 0) == 0:
            logger.debug(
                "[LiveSignalService] Skipping empty bar (volume=0) at t=%s for %s",
                candle.get("time"),
                self._symbol,
            )
            return {"long": False, "short": False, "empty_bar": True, "bars_used": len(self._window)}

        self._window.append(candle)
        df = self._build_df()
        bars_used = len(df)

        t0 = time.perf_counter()
        try:
            result = self._adapter.generate_signals(df)
            elapsed = time.perf_counter() - t0

            # Expert fix #3: performance budget warning
            if elapsed > _SIGNAL_COMPUTE_WARN_SECS:
                logger.warning(
                    "[LiveSignalService] generate_signals() took %.2f s for %s "
                    "(bars=%d) — consider reducing strategy complexity on 1m TF",
                    elapsed,
                    self._symbol,
                    bars_used,
                )

            last_idx = bars_used - 1
            long_signal = bool(result.entries.iloc[last_idx]) if result.entries is not None else False
            short_signal = bool(result.short_entries.iloc[last_idx]) if result.short_entries is not None else False
            return {"long": long_signal, "short": short_signal, "bars_used": bars_used}

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.error(
                "[LiveSignalService] Signal computation failed for %s after %.3f s: %s",
                self._symbol,
                elapsed,
                exc,
            )
            # Expert fix #1: return structured error so SSE client knows what happened
            return {
                "long": False,
                "short": False,
                "error": str(exc),
                "bars_used": bars_used,
            }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_df(self) -> pd.DataFrame:
        """Convert the sliding window to a DataFrame expected by StrategyBuilderAdapter."""
        bars = list(self._window)
        df = pd.DataFrame(bars)
        df.index = pd.to_datetime(df["time"], unit="s", utc=True)
        df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            },
            inplace=True,
        )
        return df

    # ------------------------------------------------------------------
    # Properties (for tests / monitoring)
    # ------------------------------------------------------------------

    @property
    def window_size(self) -> int:
        """Current number of bars in the rolling window."""
        return len(self._window)
