"""
⚡ Performance Profiling Module

Provides profiling tools for backtesting engine optimization.

Usage:
    from backend.core.performance_profiler import BacktestProfiler

    # Profile a backtest run
    profiler = BacktestProfiler()
    with profiler.profile():
        result = engine.run(input)

    profiler.print_stats()
    profiler.save_report("profile_report.txt")
"""

import cProfile
import io
import pstats
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps

import numpy as np


@dataclass
class TimingResult:
    """Result of timing a function or section."""

    name: str
    total_time: float
    calls: int = 1
    avg_time: float = 0.0
    min_time: float = 0.0
    max_time: float = 0.0
    times: list[float] = field(default_factory=list)

    def add_time(self, t: float) -> None:
        """Add a timing measurement."""
        self.times.append(t)
        self.calls = len(self.times)
        self.total_time = sum(self.times)
        self.avg_time = self.total_time / self.calls
        self.min_time = min(self.times)
        self.max_time = max(self.times)


@dataclass
class ProfileReport:
    """Complete profiling report."""

    total_time: float
    sections: dict[str, TimingResult]
    memory_peak_mb: float = 0.0
    trades_per_second: float = 0.0
    bars_per_second: float = 0.0
    bottlenecks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_time_sec": round(self.total_time, 4),
            "memory_peak_mb": round(self.memory_peak_mb, 2),
            "trades_per_second": round(self.trades_per_second, 2),
            "bars_per_second": round(self.bars_per_second, 2),
            "sections": {
                name: {
                    "total": round(s.total_time, 4),
                    "calls": s.calls,
                    "avg": round(s.avg_time, 6),
                    "min": round(s.min_time, 6),
                    "max": round(s.max_time, 6),
                    "pct": round(s.total_time / self.total_time * 100, 1)
                    if self.total_time > 0
                    else 0,
                }
                for name, s in self.sections.items()
            },
            "bottlenecks": self.bottlenecks,
        }


class BacktestProfiler:
    """
    Profiler for backtesting performance analysis.

    Features:
    - cProfile integration for detailed function profiling
    - Section timing for high-level analysis
    - Memory tracking (if tracemalloc available)
    - Bottleneck identification
    """

    def __init__(self, enable_cprofile: bool = False):
        """
        Initialize profiler.

        Args:
            enable_cprofile: Enable detailed cProfile (slower but more info)
        """
        self.enable_cprofile = enable_cprofile
        self._profiler: cProfile.Profile | None = None
        self._sections: dict[str, TimingResult] = {}
        self._start_time: float = 0.0
        self._total_time: float = 0.0
        self._memory_peak: float = 0.0
        self._n_trades: int = 0
        self._n_bars: int = 0

        # Try to import tracemalloc for memory tracking
        try:
            import tracemalloc

            self._tracemalloc = tracemalloc
        except ImportError:
            self._tracemalloc = None

    @contextmanager
    def profile(self):
        """
        Context manager for profiling.

        Usage:
            with profiler.profile():
                # Code to profile
        """
        self._start_time = time.perf_counter()

        # Start memory tracking
        if self._tracemalloc:
            self._tracemalloc.start()

        # Start cProfile if enabled
        if self.enable_cprofile:
            self._profiler = cProfile.Profile()
            self._profiler.enable()

        try:
            yield self
        finally:
            self._total_time = time.perf_counter() - self._start_time

            if self.enable_cprofile and self._profiler:
                self._profiler.disable()

            if self._tracemalloc:
                current, peak = self._tracemalloc.get_traced_memory()
                self._memory_peak = peak / 1024 / 1024  # MB
                self._tracemalloc.stop()

    @contextmanager
    def section(self, name: str):
        """
        Profile a specific section of code.

        Usage:
            with profiler.section("signal_generation"):
                signals = generate_signals(data)
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            if name not in self._sections:
                self._sections[name] = TimingResult(name=name, total_time=0.0)
            self._sections[name].add_time(elapsed)

    def time_function(self, name: str):
        """
        Decorator to time a function.

        Usage:
            @profiler.time_function("my_func")
            def my_func():
                pass
        """

        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.section(name):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def set_stats(self, n_trades: int = 0, n_bars: int = 0) -> None:
        """Set statistics for throughput calculation."""
        self._n_trades = n_trades
        self._n_bars = n_bars

    def get_report(self) -> ProfileReport:
        """Generate profiling report."""
        trades_per_sec = (
            self._n_trades / self._total_time if self._total_time > 0 else 0
        )
        bars_per_sec = self._n_bars / self._total_time if self._total_time > 0 else 0

        # Identify bottlenecks (sections taking >20% of time)
        bottlenecks = []
        for name, section in self._sections.items():
            pct = (
                section.total_time / self._total_time * 100
                if self._total_time > 0
                else 0
            )
            if pct > 20:
                bottlenecks.append(f"{name}: {pct:.1f}%")

        return ProfileReport(
            total_time=self._total_time,
            sections=self._sections,
            memory_peak_mb=self._memory_peak,
            trades_per_second=trades_per_sec,
            bars_per_second=bars_per_sec,
            bottlenecks=bottlenecks,
        )

    def print_stats(self, sort_by: str = "tottime", limit: int = 20) -> None:
        """Print profiling statistics."""
        print("\n" + "=" * 60)
        print("PERFORMANCE PROFILE REPORT")
        print("=" * 60)

        report = self.get_report()

        print("\n📊 Summary:")
        print(f"  Total Time: {report.total_time:.4f}s")
        print(f"  Memory Peak: {report.memory_peak_mb:.2f} MB")
        print(f"  Trades/sec: {report.trades_per_second:.2f}")
        print(f"  Bars/sec: {report.bars_per_second:.2f}")

        if report.sections:
            print("\n⏱️ Section Timings:")
            sorted_sections = sorted(
                report.sections.items(), key=lambda x: x[1].total_time, reverse=True
            )
            for name, section in sorted_sections:
                pct = (
                    section.total_time / report.total_time * 100
                    if report.total_time > 0
                    else 0
                )
                print(
                    f"  {name:30s} {section.total_time:8.4f}s ({pct:5.1f}%) x{section.calls}"
                )

        if report.bottlenecks:
            print("\n🔴 Bottlenecks (>20% of time):")
            for b in report.bottlenecks:
                print(f"  - {b}")

        if self.enable_cprofile and self._profiler:
            print(f"\n📋 cProfile Top {limit} Functions:")
            s = io.StringIO()
            ps = pstats.Stats(self._profiler, stream=s).sort_stats(sort_by)
            ps.print_stats(limit)
            print(s.getvalue())

        print("=" * 60)

    def save_report(self, filepath: str) -> None:
        """Save report to file."""
        with open(filepath, "w") as f:
            # Redirect print output to file
            import sys

            old_stdout = sys.stdout
            sys.stdout = f
            self.print_stats()
            sys.stdout = old_stdout


def benchmark_backtest_engine(
    engine_class,
    input_data,
    n_runs: int = 5,
    warmup_runs: int = 1,
) -> dict:
    """
    Benchmark a backtest engine with multiple runs.

    Args:
        engine_class: Engine class to benchmark
        input_data: Input data for backtest
        n_runs: Number of benchmark runs
        warmup_runs: Warmup runs (not counted)

    Returns:
        Benchmark results dictionary
    """
    times = []
    memory_peaks = []

    # Warmup
    for _ in range(warmup_runs):
        engine = engine_class()
        engine.run(input_data)

    # Benchmark runs
    try:
        import tracemalloc
    except ImportError:
        tracemalloc = None

    for i in range(n_runs):
        if tracemalloc:
            tracemalloc.start()

        start = time.perf_counter()
        engine = engine_class()
        _ = engine.run(input_data)  # Result not needed, just benchmarking
        elapsed = time.perf_counter() - start

        if tracemalloc:
            _, peak = tracemalloc.get_traced_memory()
            memory_peaks.append(peak / 1024 / 1024)
            tracemalloc.stop()

        times.append(elapsed)

    return {
        "n_runs": n_runs,
        "mean_time": np.mean(times),
        "std_time": np.std(times),
        "min_time": np.min(times),
        "max_time": np.max(times),
        "mean_memory_mb": np.mean(memory_peaks) if memory_peaks else 0,
        "times": times,
    }


def profile_function(func: Callable, *args, **kwargs) -> tuple:
    """
    Quick profile a single function call.

    Returns:
        (result, time_elapsed, stats_string)
    """
    profiler = cProfile.Profile()
    profiler.enable()

    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start

    profiler.disable()

    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("tottime")
    ps.print_stats(20)

    return result, elapsed, s.getvalue()
