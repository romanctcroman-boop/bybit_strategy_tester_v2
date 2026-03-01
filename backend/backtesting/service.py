"""
Backtest Data Service

Integrates BacktestEngine with Market Data sources (BybitAdapter, Cache, Local DB).
"""

import time
from datetime import datetime

import pandas as pd
from loguru import logger

from backend.backtesting.engine import BacktestEngine, get_engine
from backend.backtesting.engine_selector import get_engine as select_engine
from backend.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    BacktestStatus,
)
from backend.database.repository.kline_repository import KlineRepository
from backend.services.adapters.bybit import BybitAdapter
from backend.utils.time import utc_now


class BacktestService:
    """
    Service layer for backtesting.

    Handles:
    - Fetching historical data from Bybit API
    - Running backtests via BacktestEngine
    - Caching and retrieving results
    """

    def __init__(self, engine: BacktestEngine | None = None):
        self.engine: BacktestEngine = engine or get_engine()
        self._adapter: BybitAdapter | None = None

    @property
    def adapter(self) -> BybitAdapter:
        """Lazy-load Bybit adapter"""
        if self._adapter is None:
            self._adapter = BybitAdapter()
        return self._adapter

    async def run_backtest(self, config: BacktestConfig) -> BacktestResult:
        """
        Run a complete backtest.

        1. Fetch historical OHLCV data from Bybit
        2. Run strategy on data
        3. Return results with metrics

        Args:
            config: Backtest configuration

        Returns:
            BacktestResult with metrics, trades, and equity curve
        """
        logger.info(
            f"BacktestService: Starting backtest for {config.symbol} "
            f"{config.interval} from {config.start_date} to {config.end_date}"
        )

        started_at = time.perf_counter()

        def _record_metrics(result: BacktestResult):
            """Best-effort Prometheus metrics update (does not break flow)."""

            try:
                from backend.monitoring.prometheus_metrics import (
                    get_metrics_collector,
                )

                collector = get_metrics_collector()
                duration = time.perf_counter() - started_at

                status_str = getattr(result.status, "value", str(result.status))
                strategy_label = getattr(config.strategy_type, "value", str(config.strategy_type))

                metrics = result.metrics

                collector.record_backtest(
                    asset=config.symbol,
                    timeframe=config.interval,
                    duration_seconds=duration,
                    status=status_str,
                    strategy=strategy_label,
                    win_rate=metrics.win_rate if metrics else None,
                    profit_factor=metrics.profit_factor if metrics else None,
                    max_drawdown=metrics.max_drawdown if metrics else None,
                    sharpe_ratio=metrics.sharpe_ratio if metrics else None,
                )
            except Exception as exc:  # pragma: no cover - metrics must not break flow
                logger.debug(f"Prometheus backtest metrics skipped: {exc}")

        try:
            # Fetch historical data (use market_type for data source selection)
            # SPOT = TradingView parity, LINEAR = perpetual futures
            market_type = getattr(config, "market_type", "linear")
            ohlcv = await self._fetch_historical_data(
                symbol=config.symbol,
                interval=config.interval,
                start_date=config.start_date,
                end_date=config.end_date,
                market_type=market_type,
            )

            if ohlcv is None or len(ohlcv) == 0:
                result = BacktestResult(
                    id="",
                    status=BacktestStatus.FAILED,
                    created_at=utc_now(),
                    config=config,
                    error_message=f"No data available for {config.symbol} {config.interval}",
                )
                _record_metrics(result)
                return result

            logger.info(f"Fetched {len(ohlcv)} candles for backtest")

            # Dynamically select engine based on config.dca_enabled
            # If dca_enabled=True, use DCAEngine; otherwise use default engine
            dca_enabled = getattr(config, "dca_enabled", False)
            if dca_enabled:
                from backend.backtesting.engines.dca_engine import DCAEngine

                _base_engine = select_engine(
                    engine_type=getattr(config, "engine_type", "auto"),
                    dca_enabled=True,
                    pyramiding=getattr(config, "pyramiding", 1),
                    strategy_type=getattr(config, "strategy_type", None),
                )
                logger.info("Using DCAEngine for DCA-enabled backtest")
                # DCAEngine uses run_from_config method
                assert isinstance(_base_engine, DCAEngine), (
                    "Expected DCAEngine from select_engine with dca_enabled=True"
                )
                result = _base_engine.run_from_config(config, ohlcv)
            else:
                # Standard engine (BacktestEngine) uses run(config, ohlcv)
                result = self.engine.run(config, ohlcv)

            _record_metrics(result)
            return result

        except Exception as e:
            logger.exception(f"BacktestService error: {e}")
            result = BacktestResult(
                id="",
                status=BacktestStatus.FAILED,
                created_at=utc_now(),
                config=config,
                error_message=str(e),
            )
            _record_metrics(result)
            return result

    async def _fetch_historical_data(
        self,
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime,
        market_type: str = "linear",
    ) -> pd.DataFrame | None:
        """
        Fetch historical OHLCV data, prioritizing local database.

        Priority:
        1. Check local SQLite database for cached klines
        2. If not found or incomplete, fetch from Bybit API

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            interval: Candle interval (e.g., 1h, 4h, 1d)
            start_date: Start datetime
            end_date: End datetime
            market_type: 'spot' (TradingView parity) or 'linear' (perpetual futures)

        Returns:
            DataFrame with OHLCV data
        """
        # Convert interval format (UI uses "1h", DB uses "60")
        interval_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "6h": "360",
            "12h": "720",
            "1d": "D",
            "1w": "W",
            "1M": "M",
        }
        db_interval = interval_map.get(interval, interval)

        # Convert to timestamps (ms)
        # Ensure timezone-aware UTC to avoid local-timezone offset on naive datetimes
        import datetime as _dtmod

        def _to_utc_ts(dt: "datetime") -> int:
            if dt.tzinfo is None:
                # Treat naive datetime as UTC (server may be in non-UTC timezone)
                dt = dt.replace(tzinfo=_dtmod.UTC)
            return int(dt.timestamp() * 1000)

        start_ts = _to_utc_ts(start_date)
        end_ts = _to_utc_ts(end_date)

        # ===== STEP 1: Try local database first =====
        try:
            from backend.database import SessionLocal

            with SessionLocal() as session:
                repo = KlineRepository(session)

                # Get klines from local DB (filter by market_type for SPOT/LINEAR)
                logger.info(f"Querying local DB for {symbol} {interval} market_type={market_type}")
                local_klines = repo.get_klines(
                    symbol=symbol,
                    interval=db_interval,
                    start_time=start_ts,
                    end_time=end_ts,
                    limit=100000,  # Large limit for backtest
                    ascending=True,
                    market_type=market_type,  # SPOT or LINEAR filter
                )

                if local_klines and len(local_klines) > 0:
                    logger.info(
                        f"Found {len(local_klines)} candles in local DB for "
                        f"{symbol} {interval} market_type={market_type} ({start_date} to {end_date})"
                    )

                    # Convert to DataFrame
                    df = pd.DataFrame(
                        [
                            {
                                "timestamp": k.open_time,
                                "open": k.open_price,
                                "high": k.high_price,
                                "low": k.low_price,
                                "close": k.close_price,
                                "volume": k.volume,
                            }
                            for k in local_klines
                        ]
                    )

                    # Set datetime index
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    df = df.set_index("timestamp")
                    df = df.sort_index()

                    # Check if we have enough data (at least 50 candles)
                    if len(df) >= 50:
                        # ── Gap-prefill: if local data starts significantly later than
                        # requested start_date, attempt to fetch the missing warmup bars
                        # from the Bybit API and prepend them.  This is critical for
                        # indicators like Wilder's RSI that need warm-up history to
                        # converge to TradingView-parity values (e.g. BTC RSI source
                        # when the DB only has data from DATA_START_DATE = 2025-01-01).
                        first_local_ts = df.index[0]
                        # Use a 2-bar tolerance to avoid unnecessary API calls
                        try:
                            _interval_minutes_gap = int(db_interval)
                        except ValueError:
                            _interval_minutes_gap = 1440  # daily
                        _tolerance = pd.Timedelta(minutes=_interval_minutes_gap * 2)
                        start_date_tz = (
                            pd.Timestamp(start_date).tz_localize("UTC")
                            if start_date.tzinfo is None
                            else pd.Timestamp(start_date)
                        )
                        if first_local_ts.tz is None:
                            first_local_ts_tz = first_local_ts.tz_localize("UTC")
                        else:
                            first_local_ts_tz = first_local_ts
                        gap = first_local_ts_tz - start_date_tz
                        if gap > _tolerance:
                            logger.info(
                                f"Local DB starts at {first_local_ts} but requested from {start_date}; "
                                f"fetching {gap} of warmup data from Bybit API"
                            )
                            try:
                                warmup_candles = await self.adapter.get_historical_klines(
                                    symbol=symbol,
                                    interval=db_interval,
                                    start_time=start_ts,
                                    end_time=int(first_local_ts_tz.timestamp() * 1000) - 1,
                                    market_type=market_type,
                                )
                                if warmup_candles:
                                    warmup_df = pd.DataFrame(warmup_candles)
                                    # Normalise columns
                                    col_map = {
                                        "startTime": "timestamp",
                                        "openPrice": "open",
                                        "highPrice": "high",
                                        "lowPrice": "low",
                                        "closePrice": "close",
                                        "open_time": "timestamp",
                                    }
                                    for old_c, new_c in col_map.items():
                                        if old_c in warmup_df.columns and new_c not in warmup_df.columns:
                                            warmup_df = warmup_df.rename(columns={old_c: new_c})
                                    for col in ["open", "high", "low", "close", "volume"]:
                                        if col in warmup_df.columns:
                                            warmup_df[col] = pd.to_numeric(warmup_df[col], errors="coerce")
                                    if "timestamp" in warmup_df.columns:
                                        if warmup_df["timestamp"].dtype in ["int64", "float64"]:
                                            warmup_df["timestamp"] = pd.to_datetime(warmup_df["timestamp"], unit="ms")
                                        else:
                                            warmup_df["timestamp"] = pd.to_datetime(warmup_df["timestamp"])
                                        warmup_df = warmup_df.set_index("timestamp")
                                    warmup_df = warmup_df.sort_index()
                                    # Drop any overlap
                                    warmup_df = warmup_df[
                                        warmup_df.index < first_local_ts_tz.tz_localize(None)
                                        if first_local_ts.tz is None
                                        else first_local_ts_tz
                                    ]
                                    if len(warmup_df) > 0:
                                        df = pd.concat([warmup_df, df])
                                        df = df[~df.index.duplicated(keep="last")]
                                        df = df.sort_index()
                                        logger.info(
                                            f"Prepended {len(warmup_df)} warmup candles from API; total={len(df)}"
                                        )
                            except Exception as _gap_err:
                                logger.warning(
                                    f"Failed to fetch warmup gap from API: {_gap_err} — continuing without it"
                                )

                        logger.info(f"Using {len(df)} candles from local database")
                        return df
                    else:
                        logger.info(f"Local DB has only {len(df)} candles, need more data")

        except Exception as e:
            logger.warning(f"Error reading from local DB: {e}, falling back to API")

        # ===== STEP 2: Fetch from Bybit API =====
        try:
            logger.info(f"Fetching data from Bybit API for {symbol} {interval} market_type={market_type}")

            # Fetch data via adapter (pass market_type for SPOT/LINEAR selection)
            candles = await self.adapter.get_historical_klines(
                symbol=symbol,
                interval=db_interval,
                start_time=start_ts,
                end_time=end_ts,
                market_type=market_type,  # SPOT for TradingView parity
            )

            if not candles:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(candles)

            # Normalize columns - support both old and new formats
            column_map = {
                # Old format (Bybit API direct)
                "startTime": "timestamp",
                "openPrice": "open",
                "highPrice": "high",
                "lowPrice": "low",
                "closePrice": "close",
                # New format (normalized by adapter)
                "open_time": "timestamp",
            }

            # Check if columns need renaming
            for old_col, new_col in column_map.items():
                if old_col in df.columns and new_col not in df.columns:
                    df = df.rename(columns={old_col: new_col})

            # Ensure numeric types
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Set datetime index
            if "timestamp" in df.columns:
                # Handle both ms timestamp and datetime
                if df["timestamp"].dtype in ["int64", "float64"]:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                else:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp")

            df = df.sort_index()

            logger.info(f"Fetched {len(df)} candles from Bybit API")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            raise

    def get_result(self, backtest_id: str) -> BacktestResult | None:
        """Get cached backtest result by ID"""
        return self.engine.get_result(backtest_id)

    def list_results(self, limit: int = 100) -> list[BacktestResult]:
        """List all cached backtest results"""
        results = self.engine.list_results()
        return results[:limit]


# Global service instance
_service: BacktestService | None = None


def get_backtest_service() -> BacktestService:
    """Get or create the global backtest service instance"""
    global _service
    if _service is None:
        _service = BacktestService()
    return _service
