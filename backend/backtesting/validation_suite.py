"""
🔬 Validation Suite - Engine Parity Testing

Создано по рекомендациям DeepSeek и Perplexity для мониторинга
точности между VectorBT, Fallback и Numba движками.

Функции:
- Автоматическое сравнение всех трёх движков
- Детальный отчёт о расхождениях
- Benchmark-набор разнообразных стратегий
"""

import sys
from pathlib import Path

# Dynamic path resolution - works on any system
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class EngineResult:
    """Result from a single engine run."""

    engine_name: str
    total_trades: int
    net_pnl: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    execution_time_ms: float
    trades_list: List = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Result of comparing two engines."""

    engine_a: str
    engine_b: str
    trades_diff: int
    trades_diff_pct: float
    pnl_diff: float
    pnl_diff_pct: float
    sharpe_diff: float
    sharpe_diff_pct: float
    max_dd_diff: float
    is_acceptable: bool
    tolerance_used: Dict[str, float] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Complete validation report."""

    timestamp: str
    strategy_name: str
    data_period: str
    n_candles: int

    # Engine results
    vectorbt_result: Optional[EngineResult] = None
    fallback_result: Optional[EngineResult] = None
    numba_result: Optional[EngineResult] = None

    # Comparisons
    vbt_vs_fallback: Optional[ComparisonResult] = None
    vbt_vs_numba: Optional[ComparisonResult] = None
    fallback_vs_numba: Optional[ComparisonResult] = None

    # Overall status
    all_pass: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ValidationSuite:
    """
    Engine Parity Validation Suite.

    Compares VectorBT, Fallback, and Numba engines to ensure
    they produce consistent results within acceptable tolerances.
    """

    # Default tolerances (from AI recommendations)
    DEFAULT_TOLERANCES = {
        "trades_pct": 0.05,  # 5% tolerance for trade count
        "pnl_pct": 0.02,  # 2% tolerance for PnL
        "sharpe_abs": 0.1,  # Absolute tolerance for Sharpe
        "max_dd_pct": 0.03,  # 3% tolerance for max drawdown
    }

    def __init__(self, tolerances: Dict[str, float] = None):
        """Initialize with optional custom tolerances."""
        self.tolerances = tolerances or self.DEFAULT_TOLERANCES.copy()
        self.reports: List[ValidationReport] = []

        # Try to import engines
        self._init_engines()

    def _init_engines(self):
        """Initialize engine references."""
        try:
            from backend.backtesting.engine import get_engine

            self.backtest_engine = get_engine()
            self.engines_available = {"vectorbt": True, "fallback": True}
        except ImportError as e:
            logger.warning(f"BacktestEngine not available: {e}")
            self.backtest_engine = None
            self.engines_available = {"vectorbt": False, "fallback": False}

        try:
            from backend.backtesting.numba_engine import simulate_trades_numba

            self.numba_simulate = simulate_trades_numba
            self.engines_available["numba"] = True
        except ImportError as e:
            logger.warning(f"Numba engine not available: {e}")
            self.numba_simulate = None
            self.engines_available["numba"] = False

    def run_validation(
        self,
        candles: pd.DataFrame,
        strategy_params: Dict,
        strategy_name: str = "RSI",
        initial_capital: float = 10000.0,
        leverage: float = 1.0,
        commission: float = 0.0004,
        slippage: float = 0.0001,
        stop_loss: float = 0.03,
        take_profit: float = 0.06,
        direction: str = "both",
    ) -> ValidationReport:
        """
        Run validation across all available engines.

        Args:
            candles: OHLCV DataFrame
            strategy_params: Dict with strategy parameters
            strategy_name: Name for logging

        Returns:
            ValidationReport with detailed comparison
        """

        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            strategy_name=strategy_name,
            data_period=f"{candles.index[0]} to {candles.index[-1]}",
            n_candles=len(candles),
        )

        # Prepare signals
        signals = self._generate_signals(candles, strategy_params)

        # Run each engine
        if self.engines_available.get("vectorbt"):
            report.vectorbt_result = self._run_vectorbt(
                candles,
                signals,
                initial_capital,
                leverage,
                commission,
                slippage,
                stop_loss,
                take_profit,
                direction,
            )

        if self.engines_available.get("fallback"):
            report.fallback_result = self._run_fallback(
                candles,
                signals,
                initial_capital,
                leverage,
                commission,
                slippage,
                stop_loss,
                take_profit,
                direction,
            )

        if self.engines_available.get("numba"):
            report.numba_result = self._run_numba(
                candles,
                signals,
                initial_capital,
                leverage,
                commission,
                slippage,
                stop_loss,
                take_profit,
                direction,
            )

        # Compare engines
        if report.vectorbt_result and report.fallback_result:
            report.vbt_vs_fallback = self._compare_results(report.vectorbt_result, report.fallback_result)

        if report.vectorbt_result and report.numba_result:
            report.vbt_vs_numba = self._compare_results(report.vectorbt_result, report.numba_result)

        if report.fallback_result and report.numba_result:
            report.fallback_vs_numba = self._compare_results(report.fallback_result, report.numba_result)

        # Check overall status
        report.all_pass = self._check_all_pass(report)

        self.reports.append(report)
        return report

    def _generate_signals(self, candles: pd.DataFrame, params: Dict):
        """Generate trading signals using RSI strategy."""
        from backend.backtesting.strategies import RSIStrategy

        strategy = RSIStrategy(
            params={
                "period": params.get("rsi_period", 14),
                "overbought": params.get("rsi_overbought", 70),
                "oversold": params.get("rsi_oversold", 30),
            }
        )
        return strategy.generate_signals(candles)

    def _run_vectorbt(
        self,
        candles,
        signals,
        initial_capital,
        leverage,
        commission,
        slippage,
        stop_loss,
        take_profit,
        direction,
    ) -> EngineResult:
        """Run VectorBT engine."""
        import time

        import vectorbt as vbt

        start = time.perf_counter()

        try:
            close = candles["close"]
            high = candles["high"]
            low = candles["low"]

            pf_kwargs = {
                "close": close,
                "high": high,
                "low": low,
                "entries": signals.entries,
                "exits": signals.exits,
                "init_cash": initial_capital,
                "size": 1.0,
                "size_type": "percent",
                "fees": commission,
                "sl_stop": stop_loss,
                "tp_stop": take_profit,
                "upon_long_conflict": "ignore",
                "upon_short_conflict": "ignore",
                "upon_dir_conflict": "ignore",
                "upon_opposite_entry": "ignore",
            }

            if direction in ("short", "both"):
                if signals.short_entries is not None:
                    pf_kwargs["short_entries"] = signals.short_entries
                if signals.short_exits is not None:
                    pf_kwargs["short_exits"] = signals.short_exits

            pf = vbt.Portfolio.from_signals(**pf_kwargs)

            stats = pf.stats()
            trades_df = pf.trades.records_readable

            exec_time = (time.perf_counter() - start) * 1000

            return EngineResult(
                engine_name="VectorBT",
                total_trades=int(stats.get("Total Trades", 0)),
                net_pnl=float(pf.total_profit()),
                sharpe_ratio=float(stats.get("Sharpe Ratio", 0) or 0),
                max_drawdown=abs(float(stats.get("Max Drawdown [%]", 0) or 0)),
                win_rate=float(stats.get("Win Rate [%]", 0) or 0) / 100,
                execution_time_ms=exec_time,
                trades_list=trades_df.to_dict("records") if len(trades_df) > 0 else [],
            )
        except Exception as e:
            logger.error(f"VectorBT error: {e}")
            return EngineResult(
                engine_name="VectorBT",
                total_trades=0,
                net_pnl=0,
                sharpe_ratio=0,
                max_drawdown=0,
                win_rate=0,
                execution_time_ms=0,
            )

    def _run_fallback(
        self,
        candles,
        signals,
        initial_capital,
        leverage,
        commission,
        slippage,
        stop_loss,
        take_profit,
        direction,
    ) -> EngineResult:
        """Run Fallback (Python) engine."""
        import time
        from datetime import datetime as dt

        from backend.backtesting.models import BacktestConfig

        start = time.perf_counter()

        try:
            config = BacktestConfig(
                symbol="BTCUSDT",
                interval="60",
                start_date=dt(2025, 1, 1),
                end_date=dt(2025, 1, 22),
                initial_capital=initial_capital,
                leverage=leverage,
                taker_fee=commission,
                slippage=slippage,
                stop_loss=stop_loss,
                take_profit=take_profit,
                direction=direction,
                strategy_type="rsi",
                use_bar_magnifier=False,  # For speed
            )

            result = self.backtest_engine._run_fallback(config, candles, signals)

            exec_time = (time.perf_counter() - start) * 1000

            return EngineResult(
                engine_name="Fallback",
                total_trades=len(result.trades),
                net_pnl=result.metrics.net_profit,
                sharpe_ratio=result.metrics.sharpe_ratio,
                max_drawdown=result.metrics.max_drawdown,
                win_rate=result.metrics.win_rate / 100
                if result.metrics.win_rate > 1
                else result.metrics.win_rate,  # Normalize to decimal
                execution_time_ms=exec_time,
                trades_list=[t.__dict__ if hasattr(t, "__dict__") else t for t in result.trades[:10]],
            )
        except Exception as e:
            logger.error(f"Fallback error: {e}")
            import traceback

            traceback.print_exc()
            return EngineResult(
                engine_name="Fallback",
                total_trades=0,
                net_pnl=0,
                sharpe_ratio=0,
                max_drawdown=0,
                win_rate=0,
                execution_time_ms=0,
            )

    def _run_numba(
        self,
        candles,
        signals,
        initial_capital,
        leverage,
        commission,
        slippage,
        stop_loss,
        take_profit,
        direction,
    ) -> EngineResult:
        """Run Numba JIT engine."""
        import time

        start = time.perf_counter()

        try:
            close = candles["close"].values.astype(np.float64)
            high = candles["high"].values.astype(np.float64)
            low = candles["low"].values.astype(np.float64)

            long_entries = signals.entries.values.astype(np.bool_)
            long_exits = signals.exits.values.astype(np.bool_)
            short_entries = (
                signals.short_entries.values.astype(np.bool_)
                if signals.short_entries is not None
                else np.zeros_like(long_entries, dtype=np.bool_)
            )
            short_exits = (
                signals.short_exits.values.astype(np.bool_)
                if signals.short_exits is not None
                else np.zeros_like(long_exits, dtype=np.bool_)
            )

            dir_map = {"long": 0, "short": 1, "both": 2}
            direction_int = dir_map.get(direction, 2)

            trades, equity, _, n_trades = self.numba_simulate(
                close,
                high,
                low,
                long_entries,
                long_exits,
                short_entries,
                short_exits,
                initial_capital,
                1.0,
                commission,
                slippage,
                stop_loss,
                take_profit,
                float(leverage),
                direction_int,
            )

            exec_time = (time.perf_counter() - start) * 1000

            # Calculate metrics
            if n_trades > 0:
                pnls = trades[:n_trades, 5]

                net_pnl = np.sum(pnls)
                wins = np.sum(pnls > 0)
                win_rate = wins / n_trades

                # Sharpe Ratio - EXACT match with Fallback methodology
                # Fallback: returns = np.diff(equity) / equity[:-1]
                # Then uses ALL returns (including zeros) with nan_to_num
                equity_fixed = equity.copy()
                equity_fixed[equity_fixed <= 0] = initial_capital

                if len(equity_fixed) > 1:
                    # Calculate period returns EXACTLY like Fallback
                    with np.errstate(divide="ignore", invalid="ignore"):
                        returns = np.diff(equity_fixed) / equity_fixed[:-1]
                    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

                    # Use ALL returns (same as Fallback)
                    if len(returns) > 1:
                        mean_ret = np.mean(returns)
                        std_ret = np.std(returns, ddof=1)

                        if std_ret > 1e-10:
                            # Standard annualization for hourly data
                            periods_per_year = 8760  # Hourly
                            risk_free_rate = 0.02  # 2% annual
                            period_rfr = risk_free_rate / periods_per_year

                            sharpe = (mean_ret - period_rfr) / std_ret * np.sqrt(periods_per_year)
                            sharpe = float(np.clip(sharpe, -100, 100))
                        else:
                            sharpe = 0.0
                    else:
                        sharpe = 0.0
                else:
                    sharpe = 0.0

                # Max drawdown from fixed equity
                peak = initial_capital
                max_dd = 0.0
                for eq in equity_fixed:
                    if eq > peak:
                        peak = eq
                    dd = (peak - eq) / peak if peak > 0 else 0
                    if dd > max_dd:
                        max_dd = dd
            else:
                net_pnl = 0
                win_rate = 0
                sharpe = 0
                max_dd = 0

            return EngineResult(
                engine_name="Numba",
                total_trades=n_trades,
                net_pnl=net_pnl,
                sharpe_ratio=sharpe,
                max_drawdown=max_dd * 100,
                win_rate=win_rate,
                execution_time_ms=exec_time,
            )
        except Exception as e:
            logger.error(f"Numba error: {e}")
            return EngineResult(
                engine_name="Numba",
                total_trades=0,
                net_pnl=0,
                sharpe_ratio=0,
                max_drawdown=0,
                win_rate=0,
                execution_time_ms=0,
            )

    def _compare_results(self, a: EngineResult, b: EngineResult) -> ComparisonResult:
        """Compare two engine results."""
        trades_diff = abs(a.total_trades - b.total_trades)
        trades_diff_pct = trades_diff / max(a.total_trades, b.total_trades, 1)

        pnl_diff = abs(a.net_pnl - b.net_pnl)
        pnl_diff_pct = pnl_diff / max(abs(a.net_pnl), abs(b.net_pnl), 1)

        sharpe_diff = abs(a.sharpe_ratio - b.sharpe_ratio)
        sharpe_diff_pct = sharpe_diff / max(abs(a.sharpe_ratio), abs(b.sharpe_ratio), 0.001)

        max_dd_diff = abs(a.max_drawdown - b.max_drawdown)

        is_acceptable = (
            trades_diff_pct <= self.tolerances["trades_pct"]
            and pnl_diff_pct <= self.tolerances["pnl_pct"]
            and sharpe_diff <= self.tolerances["sharpe_abs"]
        )

        return ComparisonResult(
            engine_a=a.engine_name,
            engine_b=b.engine_name,
            trades_diff=trades_diff,
            trades_diff_pct=trades_diff_pct,
            pnl_diff=pnl_diff,
            pnl_diff_pct=pnl_diff_pct,
            sharpe_diff=sharpe_diff,
            sharpe_diff_pct=sharpe_diff_pct,
            max_dd_diff=max_dd_diff,
            is_acceptable=is_acceptable,
            tolerance_used=self.tolerances,
        )

    def _check_all_pass(self, report: ValidationReport) -> bool:
        """Check if all comparisons pass."""
        checks = [
            report.vbt_vs_fallback,
            report.vbt_vs_numba,
            report.fallback_vs_numba,
        ]
        return all(c.is_acceptable for c in checks if c is not None)

    def print_report(self, report: ValidationReport):
        """Print a human-readable report."""
        print("\n" + "=" * 70)
        print("🔬 VALIDATION SUITE REPORT")
        print("=" * 70)
        print(f"Strategy: {report.strategy_name}")
        print(f"Period: {report.data_period}")
        print(f"Candles: {report.n_candles}")
        print(f"Timestamp: {report.timestamp}")

        print("\n📊 ENGINE RESULTS:")
        print("-" * 70)

        for name, result in [
            ("VectorBT", report.vectorbt_result),
            ("Fallback", report.fallback_result),
            ("Numba", report.numba_result),
        ]:
            if result:
                print(f"\n{name}:")
                print(f"   Trades: {result.total_trades}")
                print(f"   Net PnL: ${result.net_pnl:,.2f}")
                print(f"   Sharpe: {result.sharpe_ratio:.3f}")
                print(f"   Max DD: {result.max_drawdown:.2f}%")
                print(f"   Win Rate: {result.win_rate:.1%}")
                print(f"   Time: {result.execution_time_ms:.2f}ms")

        print("\n🔄 COMPARISONS:")
        print("-" * 70)

        for name, comp in [
            ("VBT vs Fallback", report.vbt_vs_fallback),
            ("VBT vs Numba", report.vbt_vs_numba),
            ("Fallback vs Numba", report.fallback_vs_numba),
        ]:
            if comp:
                status = "✅ PASS" if comp.is_acceptable else "❌ FAIL"
                print(f"\n{name}: {status}")
                print(f"   Trades diff: {comp.trades_diff} ({comp.trades_diff_pct:.1%})")
                print(f"   PnL diff: ${comp.pnl_diff:,.2f} ({comp.pnl_diff_pct:.1%})")
                print(f"   Sharpe diff: {comp.sharpe_diff:.3f}")

        print("\n" + "=" * 70)
        overall = "✅ ALL PASS" if report.all_pass else "⚠️ SOME FAILED"
        print(f"OVERALL: {overall}")
        print("=" * 70)

    def run_benchmark_suite(self, candles: pd.DataFrame) -> List[ValidationReport]:
        """
        Run a comprehensive benchmark suite with multiple strategies.
        """
        benchmark_configs = [
            {
                "name": "RSI Standard",
                "params": {"rsi_period": 14, "rsi_overbought": 70, "rsi_oversold": 30},
            },
            {
                "name": "RSI Aggressive",
                "params": {"rsi_period": 7, "rsi_overbought": 65, "rsi_oversold": 35},
            },
            {
                "name": "RSI Conservative",
                "params": {"rsi_period": 21, "rsi_overbought": 80, "rsi_oversold": 20},
            },
        ]

        sl_tp_configs = [
            {"sl": 0.02, "tp": 0.04, "name": "Tight"},
            {"sl": 0.03, "tp": 0.06, "name": "Standard"},
            {"sl": 0.05, "tp": 0.10, "name": "Wide"},
        ]

        reports = []

        for strat in benchmark_configs:
            for sltp in sl_tp_configs:
                full_name = f"{strat['name']} + {sltp['name']} SL/TP"
                print(f"\n🧪 Testing: {full_name}")

                report = self.run_validation(
                    candles=candles,
                    strategy_params=strat["params"],
                    strategy_name=full_name,
                    stop_loss=sltp["sl"],
                    take_profit=sltp["tp"],
                )

                self.print_report(report)
                reports.append(report)

        return reports

    def save_reports(self, filepath: str = "validation_reports.json"):
        """Save all reports to JSON."""
        import dataclasses

        def convert(obj):
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            return str(obj)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([convert(r) for r in self.reports], f, indent=2, default=str)

        print(f"✅ Saved {len(self.reports)} reports to {filepath}")


# ============================================================
# RUN VALIDATION
# ============================================================

if __name__ == "__main__":
    import sqlite3
    from pathlib import Path

    print("=" * 70)
    print("🔬 VALIDATION SUITE - Engine Parity Testing")
    print("=" * 70)

    # Dynamic path resolution
    project_root = Path(__file__).resolve().parents[2]
    db_path = project_root / "data.sqlite3"

    # Load data
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql(
        """
        SELECT open_time, open_price as open, high_price as high,
               low_price as low, close_price as close, volume
        FROM bybit_kline_audit
        WHERE symbol = 'BTCUSDT' AND interval = '60'
        AND open_time >= 1735689600000
        AND open_time < 1737504000000
        ORDER BY open_time ASC
    """,
        conn,
    )
    conn.close()

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df.set_index("open_time", inplace=True)

    print(f"📊 Loaded {len(df)} 1H candles")

    # Create suite
    suite = ValidationSuite()

    # Run single validation
    report = suite.run_validation(
        candles=df,
        strategy_params={"rsi_period": 14, "rsi_overbought": 70, "rsi_oversold": 30},
        strategy_name="RSI Standard",
        stop_loss=0.03,
        take_profit=0.06,
    )

    suite.print_report(report)

    # Save reports
    suite.save_reports(str(project_root / "validation_reports.json"))
