"""
📊 MTF Data Loader Module

Loads and aligns multi-timeframe data for backtesting.
Handles:
- LTF (Lower Timeframe) candles
- HTF (Higher Timeframe) candles
- Reference symbol candles (e.g., BTC for correlation)
- HTF index mapping with lookahead prevention
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from backend.backtesting.mtf.index_mapper import (
    create_htf_index_map,
    interval_to_minutes,
)
from backend.services.candle_cache import CANDLE_CACHE
from backend.services.mtf_manager import MTF_MANAGER

logger = logging.getLogger(__name__)


@dataclass
class MTFData:
    """
    Container for Multi-Timeframe data.

    Attributes:
        symbol: Trading pair (e.g., "BTCUSDT")
        ltf_interval: Lower timeframe interval (e.g., "5")
        htf_interval: Higher timeframe interval (e.g., "60")
        ltf_candles: DataFrame with LTF OHLCV data
        htf_candles: DataFrame with HTF OHLCV data
        htf_index_map: Array mapping LTF bar index → visible HTF bar index
        reference_symbol: Optional reference symbol (e.g., "BTCUSDT" for correlation)
        reference_candles: Optional DataFrame with reference symbol data
        reference_index_map: Optional mapping for reference symbol
        lookahead_mode: "none" (safe) or "allow" (research)
        metadata: Additional metadata
    """

    symbol: str
    ltf_interval: str
    htf_interval: str
    ltf_candles: pd.DataFrame
    htf_candles: pd.DataFrame
    htf_index_map: np.ndarray
    reference_symbol: str | None = None
    reference_candles: pd.DataFrame | None = None
    reference_index_map: np.ndarray | None = None
    lookahead_mode: str = "none"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate data after initialization."""
        if len(self.ltf_candles) != len(self.htf_index_map):
            raise ValueError(
                f"LTF candles ({len(self.ltf_candles)}) and "
                f"htf_index_map ({len(self.htf_index_map)}) length mismatch"
            )

    @property
    def n_ltf_bars(self) -> int:
        """Number of LTF bars."""
        return len(self.ltf_candles)

    @property
    def n_htf_bars(self) -> int:
        """Number of HTF bars."""
        return len(self.htf_candles)

    @property
    def bars_ratio(self) -> int:
        """Number of LTF bars per HTF bar."""
        ltf_min = interval_to_minutes(self.ltf_interval)
        htf_min = interval_to_minutes(self.htf_interval)
        if ltf_min and htf_min:
            return htf_min // ltf_min
        return 1

    def get_htf_at_ltf(self, ltf_idx: int) -> pd.Series | None:
        """
        Get HTF candle visible at a specific LTF bar index.

        Args:
            ltf_idx: LTF bar index

        Returns:
            HTF candle as pd.Series, or None if not available
        """
        if ltf_idx < 0 or ltf_idx >= len(self.htf_index_map):
            return None

        htf_idx = self.htf_index_map[ltf_idx]
        if htf_idx < 0 or htf_idx >= len(self.htf_candles):
            return None

        return self.htf_candles.iloc[htf_idx]

    def get_reference_at_ltf(self, ltf_idx: int) -> pd.Series | None:
        """
        Get reference symbol candle visible at a specific LTF bar index.

        Args:
            ltf_idx: LTF bar index

        Returns:
            Reference candle as pd.Series, or None if not available
        """
        if self.reference_candles is None or self.reference_index_map is None:
            return None

        if ltf_idx < 0 or ltf_idx >= len(self.reference_index_map):
            return None

        ref_idx = self.reference_index_map[ltf_idx]
        if ref_idx < 0 or ref_idx >= len(self.reference_candles):
            return None

        return self.reference_candles.iloc[ref_idx]


class MTFDataLoader:
    """
    Multi-Timeframe Data Loader.

    Loads candle data for multiple timeframes and creates proper
    index mappings with lookahead prevention.
    """

    def __init__(self, use_cache: bool = True):
        """
        Initialize MTF Data Loader.

        Args:
            use_cache: Whether to use candle cache (default: True)
        """
        self.use_cache = use_cache
        logger.info("MTF Data Loader initialized")

    def load(
        self,
        symbol: str,
        ltf_interval: str,
        htf_interval: str,
        start_date: str | None = None,
        end_date: str | None = None,
        load_limit: int = 5000,
        lookahead_mode: str = "none",
        reference_symbol: str | None = None,
        reference_interval: str | None = None,
    ) -> MTFData:
        """
        Load multi-timeframe data with proper alignment.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            ltf_interval: Lower timeframe interval (e.g., "5")
            htf_interval: Higher timeframe interval (e.g., "60")
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            load_limit: Maximum candles to load per timeframe
            lookahead_mode: "none" (safe) or "allow" (research)
            reference_symbol: Optional reference symbol for correlation
            reference_interval: Interval for reference symbol (defaults to htf_interval)

        Returns:
            MTFData object with aligned data

        Raises:
            ValueError: If data cannot be loaded or intervals are invalid
        """
        logger.info(
            f"Loading MTF data: {symbol} LTF={ltf_interval} HTF={htf_interval} "
            f"lookahead={lookahead_mode}"
        )

        # Validate intervals
        ltf_minutes = interval_to_minutes(ltf_interval)
        htf_minutes = interval_to_minutes(htf_interval)

        if ltf_minutes is None or htf_minutes is None:
            raise ValueError(
                f"Invalid intervals: LTF={ltf_interval}, HTF={htf_interval}"
            )

        if htf_minutes <= ltf_minutes:
            raise ValueError(
                f"HTF ({htf_interval}={htf_minutes}min) must be larger than "
                f"LTF ({ltf_interval}={ltf_minutes}min)"
            )

        # Load LTF candles
        ltf_candles = self._load_candles(
            symbol, ltf_interval, start_date, end_date, load_limit
        )
        if ltf_candles.empty:
            raise ValueError(f"No LTF data for {symbol} {ltf_interval}")

        # Load HTF candles
        htf_candles = self._load_candles(
            symbol, htf_interval, start_date, end_date, load_limit
        )
        if htf_candles.empty:
            raise ValueError(f"No HTF data for {symbol} {htf_interval}")

        # Create HTF index map
        ltf_timestamps = self._get_timestamps(ltf_candles)
        htf_timestamps = self._get_timestamps(htf_candles)
        htf_index_map = create_htf_index_map(
            ltf_timestamps, htf_timestamps, lookahead_mode
        )

        # Load reference symbol if specified
        reference_candles = None
        reference_index_map = None
        if reference_symbol:
            ref_interval = reference_interval or htf_interval
            reference_candles = self._load_candles(
                reference_symbol, ref_interval, start_date, end_date, load_limit
            )
            if not reference_candles.empty:
                ref_timestamps = self._get_timestamps(reference_candles)
                reference_index_map = create_htf_index_map(
                    ltf_timestamps, ref_timestamps, lookahead_mode
                )
            else:
                logger.warning(f"No reference data for {reference_symbol}")

        # Build metadata
        metadata = {
            "ltf_bars": len(ltf_candles),
            "htf_bars": len(htf_candles),
            "bars_ratio": htf_minutes // ltf_minutes,
            "start_date": ltf_candles["time"].min() if "time" in ltf_candles else None,
            "end_date": ltf_candles["time"].max() if "time" in ltf_candles else None,
        }

        logger.info(
            f"Loaded MTF data: {metadata['ltf_bars']} LTF bars, "
            f"{metadata['htf_bars']} HTF bars, ratio={metadata['bars_ratio']}"
        )

        return MTFData(
            symbol=symbol,
            ltf_interval=ltf_interval,
            htf_interval=htf_interval,
            ltf_candles=ltf_candles,
            htf_candles=htf_candles,
            htf_index_map=htf_index_map,
            reference_symbol=reference_symbol,
            reference_candles=reference_candles,
            reference_index_map=reference_index_map,
            lookahead_mode=lookahead_mode,
            metadata=metadata,
        )

    def _load_candles(
        self,
        symbol: str,
        interval: str,
        start_date: str | None,
        end_date: str | None,
        load_limit: int,
    ) -> pd.DataFrame:
        """
        Load candles from cache or API.

        Args:
            symbol: Trading pair
            interval: Interval string
            start_date: Start date
            end_date: End date
            load_limit: Max candles

        Returns:
            DataFrame with OHLCV data
        """
        try:
            if self.use_cache:
                # Try cache first
                candles = CANDLE_CACHE.get_working_set(
                    symbol, interval, ensure_loaded=False
                )
                if candles:
                    df = self._candles_to_df(candles)
                    df = self._filter_by_date(df, start_date, end_date)
                    if not df.empty:
                        return df

                # Load from API via cache
                candles = CANDLE_CACHE.load_initial(
                    symbol, interval, load_limit=load_limit, persist=True
                )
                if candles:
                    df = self._candles_to_df(candles)
                    df = self._filter_by_date(df, start_date, end_date)
                    return df

            # Fallback to MTF Manager
            result = MTF_MANAGER.get_working_sets(symbol, [interval], load_limit)
            candles = result.data.get(interval, [])
            if candles:
                df = self._candles_to_df(candles)
                df = self._filter_by_date(df, start_date, end_date)
                return df

        except Exception as e:
            logger.error(f"Failed to load candles {symbol} {interval}: {e}")

        return pd.DataFrame()

    def _candles_to_df(self, candles: list[dict]) -> pd.DataFrame:
        """Convert list of candle dicts to DataFrame."""
        if not candles:
            return pd.DataFrame()

        df = pd.DataFrame(candles)

        # Standardize column names
        column_map = {
            "openTime": "time",
            "open_time": "time",
            "timestamp": "time",
        }
        df = df.rename(columns=column_map)

        # Ensure required columns
        required = ["time", "open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                if col == "volume":
                    df[col] = 0.0
                else:
                    logger.warning(f"Missing column: {col}")

        # Convert time to datetime if needed
        if "time" in df.columns:
            if df["time"].dtype == "int64" or df["time"].dtype == "float64":
                # Assume milliseconds
                if df["time"].iloc[0] > 1e12:
                    df["time"] = pd.to_datetime(df["time"], unit="ms")
                else:
                    df["time"] = pd.to_datetime(df["time"], unit="s")

        return df

    def _filter_by_date(
        self, df: pd.DataFrame, start_date: str | None, end_date: str | None
    ) -> pd.DataFrame:
        """Filter DataFrame by date range."""
        if df.empty or "time" not in df.columns:
            return df

        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df["time"] >= start_dt]

        if end_date:
            end_dt = pd.to_datetime(end_date)
            df = df[df["time"] <= end_dt]

        return df.reset_index(drop=True)

    def _get_timestamps(self, df: pd.DataFrame) -> np.ndarray:
        """Extract timestamps as numpy array."""
        if "time" not in df.columns:
            return np.arange(len(df))

        if df["time"].dtype == "datetime64[ns]":
            return df["time"].values.astype("datetime64[ms]").astype(np.int64)
        elif df["time"].dtype == "int64":
            return df["time"].values
        else:
            return (
                pd.to_datetime(df["time"])
                .values.astype("datetime64[ms]")
                .astype(np.int64)
            )
