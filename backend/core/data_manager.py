"""
DataManager - Multi-timeframe data loading and synchronization (ТЗ 3.1.2)

Manages loading, caching, and synchronization of historical market data
from multiple timeframes with proper alignment.

Key Features:
- Load single timeframe from Bybit API
- Load multiple timeframes with automatic synchronization
- Cache management for performance
- Timestamp alignment across timeframes
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, List
import time

import pandas as pd
import numpy as np
from pybit.unified_trading import HTTP

logger = logging.getLogger(__name__)


class DataManager:
    """
    Manages historical market data loading and caching.
    
    Per ТЗ 3.1.2:
    - Central timeframe (e.g., 15m) + neighbors (5m, 30m)
    - Automatic synchronization by timestamp
    - Local caching for performance
    
    Args:
        symbol: Trading pair (BTCUSDT, ETHUSDT, etc.)
        cache_dir: Directory for local cache storage
        api_key: Bybit API key (optional for public data)
        api_secret: Bybit API secret (optional)
    """
    
    # Bybit API interval mapping
    INTERVAL_MAP = {
        '1': 1,      # 1 minute
        '3': 3,
        '5': 5,
        '15': 15,
        '30': 30,
        '60': 60,    # 1 hour
        '120': 120,  # 2 hours
        '240': 240,  # 4 hours
        '360': 360,  # 6 hours
        '720': 720,  # 12 hours
        'D': 'D',    # 1 day
        'W': 'W',    # 1 week
        'M': 'M'     # 1 month
    }
    
    def __init__(
        self,
        symbol: str = 'BTCUSDT',
        cache_dir: str = './data/cache',
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None
    ):
        self.symbol = symbol
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Bybit HTTP client
        self.session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret
        )
        
        logger.info(f"DataManager initialized for {symbol}")
    
    def load_historical(
        self,
        timeframe: str = '15',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Load historical OHLCV data for a single timeframe.
        
        Args:
            timeframe: Timeframe string ('1', '5', '15', '60', '240', 'D')
            start_date: Start of historical period (default: limit bars ago)
            end_date: End of period (default: now)
            limit: Max number of bars to load (default: 1000, max: 1000)
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if timeframe not in self.INTERVAL_MAP:
            raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of {list(self.INTERVAL_MAP.keys())}")
        
        # Use cache if available
        cache_file = self._get_cache_path(timeframe, start_date, end_date, limit)
        if cache_file.exists():
            logger.info(f"Loading from cache: {cache_file}")
            df = pd.read_parquet(cache_file)
            return df
        
        # Load from API
        logger.info(f"Loading {self.symbol} {timeframe} from Bybit API (limit={limit})")
        
        # Calculate time range
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        
        end_ts = int(end_date.timestamp() * 1000)
        
        # Bybit API parameters
        interval = timeframe
        
        try:
            response = self.session.get_kline(
                category="linear",
                symbol=self.symbol,
                interval=interval,
                limit=limit,
                end=end_ts
            )
            
            if response['retCode'] != 0:
                raise Exception(f"Bybit API error: {response['retMsg']}")
            
            klines = response['result']['list']
            
            if not klines:
                raise ValueError(f"No data returned for {self.symbol} {timeframe}")
            
            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
            ])
            
            # Convert types
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
                df[col] = df[col].astype(float)
            
            # Sort by timestamp ascending
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Cache the result
            self._save_cache(df, cache_file)
            
            logger.info(f"Loaded {len(df)} bars from {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise
    
    def get_multi_timeframe(
        self,
        timeframes: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
        central_tf: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load multiple timeframes with automatic synchronization.
        
        Per ТЗ 3.1.2: "central timeframe (15m) + neighbors (5m, 30m)"
        
        Args:
            timeframes: List of timeframe strings ['5', '15', '30']
            start_date: Start of historical period
            end_date: End of period
            limit: Max bars for central timeframe
            central_tf: Which timeframe to use as reference (default: middle one)
        
        Returns:
            Dict[timeframe -> aligned DataFrame]
            All DataFrames have matching timestamp index from central TF
        
        Example:
            >>> dm = DataManager('BTCUSDT')
            >>> data = dm.get_multi_timeframe(['5', '15', '30'], limit=500)
            >>> # data['15'] has 500 bars
            >>> # data['5'] and data['30'] are aligned to same timestamps
        """
        if not timeframes:
            raise ValueError("timeframes list cannot be empty")
        
        # Determine central timeframe
        if central_tf is None:
            central_tf = timeframes[len(timeframes) // 2]  # Middle one
        
        if central_tf not in timeframes:
            raise ValueError(f"central_tf '{central_tf}' must be in timeframes list")
        
        logger.info(f"Loading multi-timeframe data: {timeframes}, central={central_tf}")
        
        # Load central timeframe first
        central_data = self.load_historical(
            timeframe=central_tf,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        result = {central_tf: central_data}
        
        # Get time range from central TF
        min_ts = central_data['timestamp'].min()
        max_ts = central_data['timestamp'].max()
        
        logger.info(f"Central TF range: {min_ts} to {max_ts} ({len(central_data)} bars)")
        
        # Load other timeframes
        for tf in timeframes:
            if tf == central_tf:
                continue
            
            # Calculate required limit for this TF to cover central range
            tf_limit = self._calculate_required_limit(central_tf, tf, limit)
            
            logger.info(f"Loading {tf} with limit={tf_limit}")
            
            tf_data = self.load_historical(
                timeframe=tf,
                start_date=start_date,
                end_date=end_date,
                limit=tf_limit
            )
            
            # Filter to match central TF range
            tf_data = tf_data[
                (tf_data['timestamp'] >= min_ts) & 
                (tf_data['timestamp'] <= max_ts)
            ].copy()
            
            result[tf] = tf_data
            
            logger.info(f"  {tf}: {len(tf_data)} bars after alignment")
        
        # Validate synchronization
        self._validate_alignment(result, central_tf)
        
        return result
    
    def _calculate_required_limit(self, central_tf: str, target_tf: str, central_limit: int) -> int:
        """Calculate how many bars needed in target_tf to cover central_tf range."""
        central_mins = self._tf_to_minutes(central_tf)
        target_mins = self._tf_to_minutes(target_tf)
        
        if target_mins < central_mins:
            # Higher resolution: need more bars
            ratio = central_mins / target_mins
            return min(int(central_limit * ratio * 1.2), 1000)  # +20% margin, max 1000
        else:
            # Lower resolution: need fewer bars
            ratio = target_mins / central_mins
            return min(int(central_limit / ratio * 1.2), 1000)
    
    def _tf_to_minutes(self, tf: str) -> int:
        """Convert timeframe string to minutes."""
        if tf == 'D':
            return 1440
        elif tf == 'W':
            return 10080
        elif tf == 'M':
            return 43200
        else:
            return int(tf)
    
    def _validate_alignment(self, data: Dict[str, pd.DataFrame], central_tf: str):
        """Validate that all timeframes are properly aligned."""
        central_range = (
            data[central_tf]['timestamp'].min(),
            data[central_tf]['timestamp'].max()
        )
        
        for tf, df in data.items():
            if tf == central_tf:
                continue
            
            if df.empty:
                logger.warning(f"Timeframe {tf} has no data after alignment")
                continue
            
            tf_range = (df['timestamp'].min(), df['timestamp'].max())
            
            # Check that TF covers central range
            if tf_range[0] > central_range[0] or tf_range[1] < central_range[1]:
                logger.warning(
                    f"Timeframe {tf} doesn't fully cover central range. "
                    f"Central: {central_range}, {tf}: {tf_range}"
                )
    
    def update_cache(self):
        """Clear cache directory."""
        logger.info(f"Clearing cache: {self.cache_dir}")
        for file in self.cache_dir.glob("*.parquet"):
            file.unlink()
    
    def _get_cache_path(
        self,
        timeframe: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int
    ) -> Path:
        """Generate cache file path."""
        # Create unique cache key
        cache_key = f"{self.symbol}_{timeframe}_{limit}"
        if end_date:
            cache_key += f"_{int(end_date.timestamp())}"
        
        return self.cache_dir / f"{cache_key}.parquet"
    
    def _save_cache(self, df: pd.DataFrame, cache_file: Path):
        """Save DataFrame to cache."""
        try:
            df.to_parquet(cache_file, index=False)
            logger.debug(f"Cached to {cache_file}")
        except Exception as e:
            logger.warning(f"Failed to cache: {e}")
