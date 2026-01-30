"""
🧪 DCA Multi-TP Strategy Test - 8 Month Backtest on Real Data

Tests:
1. DCA Long with Multi-TP (TP1-TP4)
2. DCA Short with Multi-TP
3. DCA Long with ATR TP/SL
4. DCA Short with ATR TP/SL
5. Multi-Timeframe filtering verification

Data period: 8 months (2025-05 to 2026-01)
Symbol: BTCUSDT
Timeframes: 15m (signals), 1H (MTF filter)
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)


class DCAMultiTPTester:
    """
    Test DCA Multi-TP strategies on real market data.
    """

    def __init__(self):
        self.symbol = "BTCUSDT"
        self.ltf_interval = "15"  # 15-minute candles for signals
        self.htf_interval = "60"  # 1-hour candles for MTF filter
        self.initial_capital = 10000.0
        self.leverage = 10
        self.taker_fee = 0.0007  # 0.07% - TradingView parity
        self.slippage = 0.0005

        # Test period: 8 months
        self.end_date = datetime(2026, 1, 27)
        self.start_date = self.end_date - timedelta(days=240)  # ~8 months

        # Results storage
        self.results: Dict[str, Dict[str, Any]] = {}

    async def load_candles_from_db(
        self, symbol: str, interval: str, start_date: datetime, end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Load candles from the SQLite database.
        """
        try:
            from backend.database.kline_repository import KlineRepository

            from backend.database.session import get_session

            async with get_session() as session:
                repo = KlineRepository(session)
                candles = await repo.get_klines(
                    symbol=symbol,
                    interval=interval,
                    start_time=start_date,
                    end_time=end_date,
                )

                if candles is None or len(candles) == 0:
                    logger.warning(f"No candles found for {symbol} {interval}")
                    return None

                # Convert to DataFrame
                df = pd.DataFrame(candles)
                if "open_time" in df.columns:
                    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                    df.set_index("open_time", inplace=True)

                # Ensure required columns
                required = ["open", "high", "low", "close", "volume"]
                for col in required:
                    if col not in df.columns:
                        logger.error(f"Missing column: {col}")
                        return None

                logger.info(f"Loaded {len(df)} candles for {symbol} {interval}")
                return df

        except Exception as e:
            logger.error(f"Failed to load candles: {e}")
            return None

    def load_candles_from_audit(
        self, symbol: str, interval: str, start_date: datetime, end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Load candles from bybit_kline_audit table.
        """
        import sqlite3

        db_path = Path("data.sqlite3")
        if not db_path.exists():
            logger.error(f"Database not found: {db_path}")
            return None

        try:
            conn = sqlite3.connect(str(db_path))
            query = f"""
                SELECT open_time, open_price as open, high_price as high,
                       low_price as low, close_price as close, volume
                FROM bybit_kline_audit
                WHERE symbol = '{symbol}'
                AND interval = '{interval}'
                AND open_time >= {int(start_date.timestamp() * 1000)}
                AND open_time < {int(end_date.timestamp() * 1000)}
                ORDER BY open_time
            """
            df = pd.read_sql_query(query, conn)
            conn.close()

            if len(df) > 0:
                df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                df.set_index("open_time", inplace=True)
                logger.info(f"Loaded {len(df)} candles from bybit_kline_audit")
                return df

        except Exception as e:
            logger.error(f"Failed to load from audit table: {e}")

        return None

    def load_candles_direct(
        self, symbol: str, interval: str, start_date: datetime, end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Load candles directly from SQLite (synchronous fallback).
        """
        import sqlite3

        # First try audit table
        df = self.load_candles_from_audit(symbol, interval, start_date, end_date)
        if df is not None and len(df) > 100:
            return df

        # Try multiple database paths
        db_paths = [
            Path("data.sqlite3"),
            Path("backend/data.sqlite3"),
            Path("backend/bybit_klines_15m.db"),
        ]

        for db_path in db_paths:
            if not db_path.exists():
                continue

            try:
                conn = sqlite3.connect(str(db_path))
                query = f"""
                    SELECT open_time, open, high, low, close, volume
                    FROM klines_{symbol.lower()}_{interval}m
                    WHERE open_time >= {int(start_date.timestamp() * 1000)}
                    AND open_time < {int(end_date.timestamp() * 1000)}
                    ORDER BY open_time
                """
                df = pd.read_sql_query(query, conn)
                conn.close()

                if len(df) > 0:
                    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                    df.set_index("open_time", inplace=True)
                    logger.info(f"Loaded {len(df)} candles from {db_path}")
                    return df

            except Exception as e:
                logger.debug(f"Could not load from {db_path}: {e}")
                continue

        logger.warning("No candles loaded from any database")
        return None

    def generate_sample_data(self, bars: int = 5000) -> pd.DataFrame:
        """
        Generate sample OHLCV data for testing when DB is unavailable.
        """
        logger.warning("Generating sample data (no real DB available)")

        dates = pd.date_range(end=self.end_date, periods=bars, freq="15min")

        # Simulate BTC-like price movement
        np.random.seed(42)
        price = 90000.0
        prices = []

        for _ in range(bars):
            # Random walk with drift
            change = np.random.normal(0.0001, 0.005)  # 0.5% volatility
            price *= 1 + change
            prices.append(price)

        df = pd.DataFrame(
            {
                "open": prices,
                "high": [p * (1 + abs(np.random.normal(0, 0.002))) for p in prices],
                "low": [p * (1 - abs(np.random.normal(0, 0.002))) for p in prices],
                "close": [p * (1 + np.random.normal(0, 0.001)) for p in prices],
                "volume": [np.random.uniform(100, 1000) for _ in prices],
            },
            index=dates,
        )

        return df

    def build_htf_index_map(
        self, ltf_df: pd.DataFrame, htf_df: pd.DataFrame
    ) -> np.ndarray:
        """
        Build index mapping from LTF to HTF.

        For each LTF bar, find the most recent HTF bar that closed before it.
        """
        from backend.backtesting.mtf.index_mapper import create_htf_index_map

        return create_htf_index_map(ltf_df.index, htf_df.index)

    def run_backtest_with_engine(
        self,
        strategy_name: str,
        candles: pd.DataFrame,
        signals,
        htf_candles: Optional[pd.DataFrame] = None,
        htf_index_map: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Run backtest using FallbackEngineV4.
        """
        try:
            from backend.backtesting.engines.fallback_engine_v4 import FallbackEngineV4
            from backend.backtesting.interfaces import (
                BacktestInput,
                SlMode,
                TpMode,
                TradeDirection,
            )

            # Prepare signals
            long_entries = (
                signals.entries.values
                if hasattr(signals, "entries")
                else np.zeros(len(candles), dtype=bool)
            )
            long_exits = (
                signals.exits.values
                if hasattr(signals, "exits")
                else np.zeros(len(candles), dtype=bool)
            )
            short_entries = (
                signals.short_entries.values
                if signals.short_entries is not None
                else np.zeros(len(candles), dtype=bool)
            )
            short_exits = (
                signals.short_exits.values
                if signals.short_exits is not None
                else np.zeros(len(candles), dtype=bool)
            )

            # Determine direction
            has_long = np.any(long_entries)
            has_short = np.any(short_entries)

            if has_long and not has_short:
                direction = TradeDirection.LONG
            elif has_short and not has_long:
                direction = TradeDirection.SHORT
            else:
                direction = TradeDirection.BOTH

            # Create backtest input
            input_data = BacktestInput(
                candles=candles,
                candles_1m=None,  # Could add 1m data for Bar Magnifier
                long_entries=long_entries,
                long_exits=long_exits,
                short_entries=short_entries,
                short_exits=short_exits,
                symbol=self.symbol,
                interval=self.ltf_interval,
                initial_capital=self.initial_capital,
                position_size=0.10,  # 10% per trade
                leverage=self.leverage,
                stop_loss=0.05,  # 5% base SL
                take_profit=0.025,  # 2.5% base TP (overridden by Multi-TP)
                direction=direction,
                taker_fee=self.taker_fee,
                slippage=self.slippage,
                use_bar_magnifier=False,
                pyramiding=6,  # Allow 1 base + 5 SOs
                dca_enabled=True,
                dca_safety_orders=5,
                tp_mode=TpMode.MULTI,
                tp_levels=(0.005, 0.01, 0.015, 0.025),  # TP1-TP4
                tp_portions=(0.25, 0.25, 0.25, 0.25),
                mtf_enabled=htf_candles is not None,
                mtf_htf_candles=htf_candles,
                mtf_htf_index_map=htf_index_map,
            )

            # Run engine
            engine = FallbackEngineV4()
            output = engine.run(input_data)

            if not output.is_valid:
                logger.error(f"Backtest validation failed: {output.validation_errors}")
                return {"error": output.validation_errors}

            # Extract metrics
            metrics = output.metrics
            final_equity = self.initial_capital + metrics.net_profit
            return {
                "strategy": strategy_name,
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "win_rate": metrics.win_rate * 100,
                "total_pnl": metrics.net_profit,
                "total_pnl_pct": metrics.total_return,
                "max_drawdown": metrics.max_drawdown,
                "sharpe_ratio": metrics.sharpe_ratio,
                "profit_factor": metrics.profit_factor,
                "final_equity": final_equity,
                "execution_time_ms": output.execution_time * 1000
                if output.execution_time
                else 0,
            }

        except ImportError as e:
            logger.error(f"Import error: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.exception(f"Backtest error: {e}")
            return {"error": str(e)}

    def test_dca_long_multi_tp(
        self,
        candles: pd.DataFrame,
        htf_candles: Optional[pd.DataFrame],
        htf_index_map: Optional[np.ndarray],
    ) -> Dict[str, Any]:
        """
        Test DCA Long with Multi-TP.
        """
        logger.info("=" * 60)
        logger.info("TEST 1: DCA Long + Multi-TP (TP1-TP4)")
        logger.info("=" * 60)

        from backend.backtesting.dca_strategies.dca_multi_tp import (
            DCADirection,
            DCAMultiTPConfig,
            DCAMultiTPStrategy,
            SLMode,
            TPMode,
        )

        config = DCAMultiTPConfig(
            direction=DCADirection.LONG,
            base_order_size_pct=10.0,
            max_safety_orders=5,
            safety_order_size_pct=10.0,
            price_deviation_pct=1.0,
            step_scale=1.4,
            volume_scale=1.05,
            tp_mode=TPMode.MULTI,
            tp_levels_pct=(0.5, 1.0, 1.5, 2.5),
            tp_portions=(0.25, 0.25, 0.25, 0.25),
            sl_mode=SLMode.FIXED,
            fixed_sl_pct=5.0,
            breakeven_enabled=True,
            breakeven_offset_pct=0.1,
            rsi_enabled=True,
            rsi_period=14,
            rsi_oversold=30.0,
            mtf_enabled=htf_candles is not None,
            mtf_filter_type="sma",
            mtf_filter_period=200,
            cooldown_bars=4,
        )

        strategy = DCAMultiTPStrategy(config)
        signals = strategy.generate_signals(candles, htf_candles, htf_index_map)

        # Count signals
        entry_count = int(signals.entries.sum())
        exit_count = int(signals.exits.sum())
        logger.info(f"Generated {entry_count} entries, {exit_count} exits")

        # Run backtest
        result = self.run_backtest_with_engine(
            "DCA Long Multi-TP", candles, signals, htf_candles, htf_index_map
        )

        self._print_result(result)
        return result

    def test_dca_short_multi_tp(
        self,
        candles: pd.DataFrame,
        htf_candles: Optional[pd.DataFrame],
        htf_index_map: Optional[np.ndarray],
    ) -> Dict[str, Any]:
        """
        Test DCA Short with Multi-TP.
        """
        logger.info("=" * 60)
        logger.info("TEST 2: DCA Short + Multi-TP (TP1-TP4)")
        logger.info("=" * 60)

        from backend.backtesting.dca_strategies.dca_multi_tp import (
            DCADirection,
            DCAMultiTPConfig,
            DCAMultiTPStrategy,
            SLMode,
            TPMode,
        )

        config = DCAMultiTPConfig(
            direction=DCADirection.SHORT,
            base_order_size_pct=10.0,
            max_safety_orders=5,
            safety_order_size_pct=10.0,
            price_deviation_pct=1.0,
            step_scale=1.4,
            volume_scale=1.05,
            tp_mode=TPMode.MULTI,
            tp_levels_pct=(0.5, 1.0, 1.5, 2.5),
            tp_portions=(0.25, 0.25, 0.25, 0.25),
            sl_mode=SLMode.FIXED,
            fixed_sl_pct=5.0,
            rsi_enabled=True,
            rsi_period=14,
            rsi_overbought=70.0,
            mtf_enabled=htf_candles is not None,
            cooldown_bars=4,
        )

        strategy = DCAMultiTPStrategy(config)
        signals = strategy.generate_signals(candles, htf_candles, htf_index_map)

        entry_count = (
            int(signals.short_entries.sum()) if signals.short_entries is not None else 0
        )
        exit_count = (
            int(signals.short_exits.sum()) if signals.short_exits is not None else 0
        )
        logger.info(f"Generated {entry_count} short entries, {exit_count} short exits")

        result = self.run_backtest_with_engine(
            "DCA Short Multi-TP", candles, signals, htf_candles, htf_index_map
        )

        self._print_result(result)
        return result

    def test_dca_long_atr(
        self,
        candles: pd.DataFrame,
        htf_candles: Optional[pd.DataFrame],
        htf_index_map: Optional[np.ndarray],
    ) -> Dict[str, Any]:
        """
        Test DCA Long with ATR-based TP/SL.
        """
        logger.info("=" * 60)
        logger.info("TEST 3: DCA Long + ATR TP/SL")
        logger.info("=" * 60)

        from backend.backtesting.dca_strategies.dca_multi_tp import (
            DCADirection,
            DCAMultiTPConfig,
            DCAMultiTPStrategy,
            SLMode,
            TPMode,
        )

        config = DCAMultiTPConfig(
            direction=DCADirection.LONG,
            base_order_size_pct=10.0,
            max_safety_orders=5,
            safety_order_size_pct=10.0,
            price_deviation_pct=1.0,
            step_scale=1.4,
            volume_scale=1.0,
            tp_mode=TPMode.ATR,
            atr_tp_multiplier=2.0,
            sl_mode=SLMode.ATR,
            atr_sl_multiplier=1.5,
            atr_period=14,
            rsi_enabled=True,
            rsi_period=14,
            rsi_oversold=30.0,
            mtf_enabled=htf_candles is not None,
            cooldown_bars=4,
        )

        strategy = DCAMultiTPStrategy(config)
        signals = strategy.generate_signals(candles, htf_candles, htf_index_map)

        entry_count = int(signals.entries.sum())
        exit_count = int(signals.exits.sum())
        logger.info(f"Generated {entry_count} entries, {exit_count} exits")

        result = self.run_backtest_with_engine(
            "DCA Long ATR", candles, signals, htf_candles, htf_index_map
        )

        self._print_result(result)
        return result

    def test_dca_short_atr(
        self,
        candles: pd.DataFrame,
        htf_candles: Optional[pd.DataFrame],
        htf_index_map: Optional[np.ndarray],
    ) -> Dict[str, Any]:
        """
        Test DCA Short with ATR-based TP/SL.
        """
        logger.info("=" * 60)
        logger.info("TEST 4: DCA Short + ATR TP/SL")
        logger.info("=" * 60)

        from backend.backtesting.dca_strategies.dca_multi_tp import (
            DCADirection,
            DCAMultiTPConfig,
            DCAMultiTPStrategy,
            SLMode,
            TPMode,
        )

        config = DCAMultiTPConfig(
            direction=DCADirection.SHORT,
            base_order_size_pct=10.0,
            max_safety_orders=5,
            safety_order_size_pct=10.0,
            price_deviation_pct=1.0,
            step_scale=1.4,
            volume_scale=1.0,
            tp_mode=TPMode.ATR,
            atr_tp_multiplier=2.0,
            sl_mode=SLMode.ATR,
            atr_sl_multiplier=1.5,
            atr_period=14,
            rsi_enabled=True,
            rsi_period=14,
            rsi_overbought=70.0,
            mtf_enabled=htf_candles is not None,
            cooldown_bars=4,
        )

        strategy = DCAMultiTPStrategy(config)
        signals = strategy.generate_signals(candles, htf_candles, htf_index_map)

        entry_count = (
            int(signals.short_entries.sum()) if signals.short_entries is not None else 0
        )
        exit_count = (
            int(signals.short_exits.sum()) if signals.short_exits is not None else 0
        )
        logger.info(f"Generated {entry_count} short entries, {exit_count} short exits")

        result = self.run_backtest_with_engine(
            "DCA Short ATR", candles, signals, htf_candles, htf_index_map
        )

        self._print_result(result)
        return result

    def test_dca_trailing_stop(
        self,
        candles: pd.DataFrame,
        htf_candles: Optional[pd.DataFrame],
        htf_index_map: Optional[np.ndarray],
    ) -> Dict[str, Any]:
        """
        Test DCA Long with Trailing Stop.
        """
        logger.info("=" * 60)
        logger.info("TEST 5: DCA Long + Trailing Stop")
        logger.info("=" * 60)

        from backend.backtesting.dca_strategies.dca_multi_tp import (
            DCADirection,
            DCAMultiTPConfig,
            DCAMultiTPStrategy,
            SLMode,
            TPMode,
        )

        config = DCAMultiTPConfig(
            direction=DCADirection.LONG,
            base_order_size_pct=10.0,
            max_safety_orders=5,
            safety_order_size_pct=10.0,
            price_deviation_pct=1.0,
            step_scale=1.4,
            tp_mode=TPMode.FIXED,
            fixed_tp_pct=3.0,
            sl_mode=SLMode.TRAILING,
            trailing_activation_pct=1.0,
            trailing_distance_pct=0.5,
            fixed_sl_pct=5.0,
            rsi_enabled=True,
            rsi_oversold=30.0,
            mtf_enabled=htf_candles is not None,
            cooldown_bars=4,
        )

        strategy = DCAMultiTPStrategy(config)
        signals = strategy.generate_signals(candles, htf_candles, htf_index_map)

        entry_count = int(signals.entries.sum())
        exit_count = int(signals.exits.sum())
        logger.info(f"Generated {entry_count} entries, {exit_count} exits")

        result = self.run_backtest_with_engine(
            "DCA Long Trailing", candles, signals, htf_candles, htf_index_map
        )

        self._print_result(result)
        return result

    def _print_result(self, result: Dict[str, Any]):
        """Print test result."""
        if "error" in result:
            logger.error(f"Test failed: {result['error']}")
            return

        logger.info(f"Strategy: {result.get('strategy', 'Unknown')}")
        logger.info(f"Total Trades: {result.get('total_trades', 0)}")
        logger.info(f"Win Rate: {result.get('win_rate', 0):.2f}%")
        logger.info(
            f"Total PnL: ${result.get('total_pnl', 0):.2f} ({result.get('total_pnl_pct', 0):.2f}%)"
        )
        logger.info(f"Max Drawdown: {result.get('max_drawdown', 0):.2f}%")
        logger.info(f"Sharpe Ratio: {result.get('sharpe_ratio', 0):.2f}")
        logger.info(f"Profit Factor: {result.get('profit_factor', 0):.2f}")
        logger.info(f"Final Equity: ${result.get('final_equity', 0):.2f}")
        logger.info(f"Execution Time: {result.get('execution_time_ms', 0):.0f}ms")

    def run_all_tests(self):
        """
        Run all DCA strategy tests.
        """
        logger.info("=" * 70)
        logger.info("🚀 DCA MULTI-TP STRATEGY TEST SUITE")
        logger.info(
            f"📅 Test Period: {self.start_date.date()} to {self.end_date.date()} (~8 months)"
        )
        logger.info(f"💰 Initial Capital: ${self.initial_capital:,.2f}")
        logger.info(f"📊 Symbol: {self.symbol}")
        logger.info(
            f"⏰ Timeframes: {self.ltf_interval}m (signals), {self.htf_interval}m (MTF filter)"
        )
        logger.info("=" * 70)

        # Load data
        logger.info("\n📥 Loading market data...")

        # Try loading LTF candles
        ltf_candles = self.load_candles_direct(
            self.symbol, self.ltf_interval, self.start_date, self.end_date
        )

        if ltf_candles is None or len(ltf_candles) < 100:
            logger.warning("Using generated sample data")
            ltf_candles = self.generate_sample_data(bars=23000)  # ~8 months of 15m data

        # Try loading HTF candles
        htf_candles = self.load_candles_direct(
            self.symbol,
            self.htf_interval,
            self.start_date - timedelta(days=30),  # Extra for warmup
            self.end_date,
        )

        # Build index map
        htf_index_map = None
        if htf_candles is not None and len(htf_candles) > 0:
            try:
                htf_index_map = self.build_htf_index_map(ltf_candles, htf_candles)
                logger.info(f"Built HTF index map: {len(htf_index_map)} mappings")
            except Exception as e:
                logger.warning(f"Could not build HTF index map: {e}")
                htf_candles = None

        logger.info(f"\n📊 Data Summary:")
        logger.info(
            f"  LTF candles: {len(ltf_candles)} ({ltf_candles.index[0]} to {ltf_candles.index[-1]})"
        )
        if htf_candles is not None:
            logger.info(
                f"  HTF candles: {len(htf_candles)} ({htf_candles.index[0]} to {htf_candles.index[-1]})"
            )
        else:
            logger.warning("  HTF candles: Not available (MTF filter disabled)")

        # Run tests
        tests = [
            ("DCA Long Multi-TP", self.test_dca_long_multi_tp),
            ("DCA Short Multi-TP", self.test_dca_short_multi_tp),
            ("DCA Long ATR", self.test_dca_long_atr),
            ("DCA Short ATR", self.test_dca_short_atr),
            ("DCA Long Trailing", self.test_dca_trailing_stop),
        ]

        for test_name, test_func in tests:
            try:
                result = test_func(ltf_candles, htf_candles, htf_index_map)
                self.results[test_name] = result
            except Exception as e:
                logger.exception(f"Test '{test_name}' failed: {e}")
                self.results[test_name] = {"error": str(e)}

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 70)
        logger.info("📋 TEST SUMMARY")
        logger.info("=" * 70)

        success_count = 0
        for name, result in self.results.items():
            if "error" in result:
                status = "❌ FAILED"
            else:
                status = "✅ PASSED"
                success_count += 1

            pnl = result.get("total_pnl", 0)
            win_rate = result.get("win_rate", 0)
            trades = result.get("total_trades", 0)

            logger.info(
                f"{status} {name}: {trades} trades, {win_rate:.1f}% WR, ${pnl:+.2f}"
            )

        logger.info("-" * 70)
        logger.info(f"Total: {success_count}/{len(self.results)} tests passed")


def main():
    """Main entry point."""
    tester = DCAMultiTPTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
