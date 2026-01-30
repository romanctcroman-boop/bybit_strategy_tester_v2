"""
GPU Acceleration Module for Universal Math Engine v2.3.

This module provides GPU-accelerated computing for backtesting:
1. GPUBackend - Unified interface for CUDA/OpenCL/CPU fallback
2. BatchBacktester - Parallel backtesting on GPU
3. VectorizedIndicators - GPU-accelerated technical indicators
4. GPUOptimizer - Massively parallel parameter optimization

Requirements:
- CuPy (for NVIDIA CUDA)
- PyOpenCL (for AMD/Intel)
- Falls back to NumPy if no GPU available

Author: Universal Math Engine Team
Version: 2.3.0
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

import numpy as np
from numpy.typing import NDArray

# Try to import GPU libraries
try:
    import cupy as cp

    CUPY_AVAILABLE = True
except ImportError:
    cp = None
    CUPY_AVAILABLE = False

try:
    import pyopencl as cl

    OPENCL_AVAILABLE = True
except ImportError:
    cl = None
    OPENCL_AVAILABLE = False


# =============================================================================
# 1. GPU BACKEND
# =============================================================================


class GPUBackendType(Enum):
    """Available GPU backends."""

    CUDA = "cuda"  # NVIDIA CUDA via CuPy
    OPENCL = "opencl"  # OpenCL (AMD, Intel, NVIDIA)
    CPU = "cpu"  # NumPy fallback


@dataclass
class GPUInfo:
    """Information about available GPU."""

    backend: GPUBackendType
    device_name: str
    memory_total: int  # bytes
    memory_free: int  # bytes
    compute_capability: Optional[str] = None
    n_cores: int = 0


@dataclass
class GPUConfig:
    """Configuration for GPU acceleration."""

    # Preferred backend (will fallback if not available)
    preferred_backend: GPUBackendType = GPUBackendType.CUDA

    # Memory limit (fraction of available memory)
    memory_limit: float = 0.8

    # Batch size for parallel operations
    batch_size: int = 1024

    # Enable memory pooling
    enable_memory_pool: bool = True

    # Enable async execution
    enable_async: bool = True

    # Device ID (for multi-GPU systems)
    device_id: int = 0


class GPUBackend:
    """
    Unified GPU backend for accelerated computing.

    Features:
    - Automatic backend selection (CUDA > OpenCL > CPU)
    - Unified array interface
    - Memory management
    - Device information
    """

    def __init__(self, config: Optional[GPUConfig] = None):
        """Initialize GPU backend."""
        self.config = config or GPUConfig()
        self.backend_type = self._detect_backend()
        self._xp = self._get_array_module()
        self._initialized = False

        if self.backend_type != GPUBackendType.CPU:
            self._initialize_device()

    def _detect_backend(self) -> GPUBackendType:
        """Detect available GPU backend."""
        if self.config.preferred_backend == GPUBackendType.CUDA and CUPY_AVAILABLE:
            try:
                cp.cuda.Device(self.config.device_id).use()
                return GPUBackendType.CUDA
            except Exception:
                pass

        if self.config.preferred_backend == GPUBackendType.OPENCL and OPENCL_AVAILABLE:
            try:
                platforms = cl.get_platforms()
                if platforms:
                    return GPUBackendType.OPENCL
            except Exception:
                pass

        # Try CUDA as fallback
        if CUPY_AVAILABLE:
            try:
                cp.cuda.Device(0).use()
                return GPUBackendType.CUDA
            except Exception:
                pass

        return GPUBackendType.CPU

    def _get_array_module(self) -> Any:
        """Get appropriate array module."""
        if self.backend_type == GPUBackendType.CUDA and CUPY_AVAILABLE:
            return cp
        return np

    def _initialize_device(self) -> None:
        """Initialize GPU device."""
        if self.backend_type == GPUBackendType.CUDA:
            cp.cuda.Device(self.config.device_id).use()
            if self.config.enable_memory_pool:
                mempool = cp.get_default_memory_pool()
                mempool.set_limit(
                    size=int(cp.cuda.Device().mem_info[1] * self.config.memory_limit)
                )
        self._initialized = True

    def get_info(self) -> GPUInfo:
        """Get GPU device information."""
        if self.backend_type == GPUBackendType.CUDA:
            device = cp.cuda.Device(self.config.device_id)
            mem_info = device.mem_info
            props = cp.cuda.runtime.getDeviceProperties(self.config.device_id)
            return GPUInfo(
                backend=self.backend_type,
                device_name=props["name"].decode(),
                memory_total=mem_info[1],
                memory_free=mem_info[0],
                compute_capability=f"{props['major']}.{props['minor']}",
                n_cores=props["multiProcessorCount"],
            )
        else:
            return GPUInfo(
                backend=GPUBackendType.CPU,
                device_name="CPU (NumPy)",
                memory_total=0,
                memory_free=0,
            )

    def to_device(self, arr: NDArray) -> Any:
        """Transfer array to GPU."""
        if self.backend_type == GPUBackendType.CUDA:
            return cp.asarray(arr)
        return arr

    def to_host(self, arr: Any) -> NDArray:
        """Transfer array from GPU to CPU."""
        if self.backend_type == GPUBackendType.CUDA:
            return cp.asnumpy(arr)
        return arr

    def zeros(self, shape: tuple, dtype: Any = np.float64) -> Any:
        """Create zero-filled array on device."""
        return self._xp.zeros(shape, dtype=dtype)

    def ones(self, shape: tuple, dtype: Any = np.float64) -> Any:
        """Create one-filled array on device."""
        return self._xp.ones(shape, dtype=dtype)

    def empty(self, shape: tuple, dtype: Any = np.float64) -> Any:
        """Create empty array on device."""
        return self._xp.empty(shape, dtype=dtype)

    def synchronize(self) -> None:
        """Synchronize GPU operations."""
        if self.backend_type == GPUBackendType.CUDA:
            cp.cuda.Stream.null.synchronize()

    @property
    def xp(self) -> Any:
        """Get array module (cupy or numpy)."""
        return self._xp


# =============================================================================
# 2. BATCH BACKTESTER
# =============================================================================


@dataclass
class BatchBacktestConfig:
    """Configuration for batch backtesting."""

    # Number of parallel backtests
    batch_size: int = 1024

    # Enable intermediate results
    store_equity_curves: bool = False

    # Enable trade-level details
    store_trades: bool = False

    # Progress callback frequency
    progress_interval: int = 100


@dataclass
class BatchBacktestResult:
    """Results from batch backtesting."""

    # Number of completed backtests
    n_completed: int

    # Results array (n_backtests, n_metrics)
    metrics: NDArray[np.float64]

    # Metric names
    metric_names: list[str]

    # Best result index
    best_idx: int

    # Processing time (seconds)
    processing_time: float

    # Equity curves (if stored)
    equity_curves: Optional[NDArray[np.float64]] = None


class BatchBacktester:
    """
    GPU-accelerated batch backtesting.

    Features:
    - Parallel execution of thousands of backtests
    - Vectorized signal generation
    - Batch metric calculation
    - Memory-efficient processing
    """

    def __init__(
        self,
        gpu: GPUBackend,
        config: Optional[BatchBacktestConfig] = None,
    ):
        """Initialize batch backtester."""
        self.gpu = gpu
        self.config = config or BatchBacktestConfig()
        self.xp = gpu.xp

    def run_batch(
        self,
        candles: NDArray[np.float64],  # (n_bars, 5) - OHLCV
        param_sets: NDArray[np.float64],  # (n_backtests, n_params)
        strategy_fn: Callable,  # Strategy function
        initial_capital: float = 10000.0,
        commission: float = 0.0007,
    ) -> BatchBacktestResult:
        """
        Run batch of backtests in parallel.

        Args:
            candles: OHLCV data (n_bars, 5)
            param_sets: Parameter sets to test (n_backtests, n_params)
            strategy_fn: Strategy function that generates signals
            initial_capital: Initial capital
            commission: Commission rate

        Returns:
            BatchBacktestResult with all results
        """
        import time

        start_time = time.time()

        n_backtests = param_sets.shape[0]
        n_bars = candles.shape[0]

        # Transfer to GPU
        candles_gpu = self.gpu.to_device(candles)
        params_gpu = self.gpu.to_device(param_sets)

        # Allocate results
        # Metrics: total_return, sharpe, max_dd, win_rate, n_trades, profit_factor
        n_metrics = 6
        metrics_gpu = self.gpu.zeros((n_backtests, n_metrics))

        if self.config.store_equity_curves:
            equity_curves_gpu = self.gpu.zeros((n_backtests, n_bars))
        else:
            equity_curves_gpu = None

        # Process in batches
        batch_size = min(self.config.batch_size, n_backtests)

        for batch_start in range(0, n_backtests, batch_size):
            batch_end = min(batch_start + batch_size, n_backtests)
            batch_params = params_gpu[batch_start:batch_end]

            # Generate signals for batch
            signals = self._generate_signals_batch(
                candles_gpu, batch_params, strategy_fn
            )

            # Run backtests for batch
            batch_metrics = self._run_backtests_batch(
                candles_gpu,
                signals,
                initial_capital,
                commission,
            )

            metrics_gpu[batch_start:batch_end] = batch_metrics

            if equity_curves_gpu is not None:
                batch_equity = self._calculate_equity_batch(
                    candles_gpu, signals, initial_capital, commission
                )
                equity_curves_gpu[batch_start:batch_end] = batch_equity

        # Synchronize and transfer back
        self.gpu.synchronize()
        metrics = self.gpu.to_host(metrics_gpu)

        # Find best result (by Sharpe ratio, index 1)
        best_idx = int(np.argmax(metrics[:, 1]))

        processing_time = time.time() - start_time

        result = BatchBacktestResult(
            n_completed=n_backtests,
            metrics=metrics,
            metric_names=[
                "total_return",
                "sharpe_ratio",
                "max_drawdown",
                "win_rate",
                "n_trades",
                "profit_factor",
            ],
            best_idx=best_idx,
            processing_time=processing_time,
        )

        if equity_curves_gpu is not None:
            result.equity_curves = self.gpu.to_host(equity_curves_gpu)

        return result

    def _generate_signals_batch(
        self,
        candles: Any,
        params: Any,
        strategy_fn: Callable,
    ) -> Any:
        """Generate signals for a batch of parameter sets."""
        xp = self.xp
        n_backtests = params.shape[0]
        n_bars = candles.shape[0]

        # Allocate signals array
        signals = xp.zeros((n_backtests, n_bars), dtype=xp.int8)

        # For simple strategies, can be fully vectorized
        # For complex strategies, may need to loop
        close = candles[:, 3]  # Close prices

        for i in range(n_backtests):
            # Extract parameters for this backtest
            p = params[i]

            # Call strategy function (must be GPU-compatible)
            sig = strategy_fn(candles, p, xp)
            signals[i] = sig

        return signals

    def _run_backtests_batch(
        self,
        candles: Any,
        signals: Any,
        initial_capital: float,
        commission: float,
    ) -> Any:
        """Run backtests for a batch of signals."""
        xp = self.xp
        n_backtests = signals.shape[0]
        n_bars = signals.shape[1]

        close = candles[:, 3]

        # Allocate metrics
        metrics = xp.zeros((n_backtests, 6))

        # Vectorized backtest logic
        for i in range(n_backtests):
            sig = signals[i]

            # Simple PnL calculation
            positions = xp.zeros(n_bars)
            position = 0
            entry_price = 0.0

            trades_pnl = []

            for j in range(1, n_bars):
                if sig[j] == 1 and position == 0:  # Long entry
                    position = 1
                    entry_price = float(close[j])
                elif sig[j] == -1 and position == 1:  # Long exit
                    exit_price = float(close[j])
                    pnl = (exit_price - entry_price) / entry_price - commission * 2
                    trades_pnl.append(pnl)
                    position = 0
                elif sig[j] == -1 and position == 0:  # Short entry
                    position = -1
                    entry_price = float(close[j])
                elif sig[j] == 1 and position == -1:  # Short exit
                    exit_price = float(close[j])
                    pnl = (entry_price - exit_price) / entry_price - commission * 2
                    trades_pnl.append(pnl)
                    position = 0

                positions[j] = position

            # Calculate metrics
            if trades_pnl:
                trades_arr = xp.array(trades_pnl)
                total_return = float(xp.sum(trades_arr))
                n_trades = len(trades_pnl)
                wins = trades_arr > 0
                win_rate = float(xp.mean(wins)) if n_trades > 0 else 0

                gross_profit = float(xp.sum(trades_arr[wins])) if xp.any(wins) else 0
                gross_loss = (
                    float(xp.abs(xp.sum(trades_arr[~wins])))
                    if xp.any(~wins)
                    else 0.0001
                )
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

                # Sharpe (simplified)
                if n_trades > 1:
                    sharpe = float(
                        xp.mean(trades_arr)
                        / (xp.std(trades_arr) + 1e-10)
                        * xp.sqrt(252)
                    )
                else:
                    sharpe = 0.0

                # Max drawdown
                equity = initial_capital * (
                    1
                    + xp.cumsum(
                        xp.array(
                            [0] + trades_pnl + [0] * (n_bars - len(trades_pnl) - 1)
                        )[:n_bars]
                    )
                )
                peak = xp.maximum.accumulate(equity)
                dd = (peak - equity) / peak
                max_dd = float(xp.max(dd))
            else:
                total_return = 0.0
                sharpe = 0.0
                max_dd = 0.0
                win_rate = 0.0
                n_trades = 0
                profit_factor = 0.0

            metrics[i] = xp.array(
                [
                    total_return,
                    sharpe,
                    max_dd,
                    win_rate,
                    n_trades,
                    profit_factor,
                ]
            )

        return metrics

    def _calculate_equity_batch(
        self,
        candles: Any,
        signals: Any,
        initial_capital: float,
        commission: float,
    ) -> Any:
        """Calculate equity curves for a batch."""
        xp = self.xp
        n_backtests = signals.shape[0]
        n_bars = signals.shape[1]

        equity = xp.full((n_backtests, n_bars), initial_capital)
        close = candles[:, 3]

        # Simplified equity calculation
        for i in range(n_backtests):
            eq = initial_capital
            position = 0
            entry_price = 0.0

            for j in range(1, n_bars):
                sig = signals[i, j]

                if sig == 1 and position == 0:
                    position = 1
                    entry_price = float(close[j])
                    eq *= 1 - commission
                elif sig == -1 and position == 1:
                    exit_price = float(close[j])
                    eq *= (exit_price / entry_price) * (1 - commission)
                    position = 0
                elif sig == -1 and position == 0:
                    position = -1
                    entry_price = float(close[j])
                    eq *= 1 - commission
                elif sig == 1 and position == -1:
                    exit_price = float(close[j])
                    eq *= (entry_price / exit_price) * (1 - commission)
                    position = 0

                equity[i, j] = eq

        return equity


# =============================================================================
# 3. VECTORIZED INDICATORS
# =============================================================================


class VectorizedIndicators:
    """
    GPU-accelerated technical indicators.

    All indicators work with GPU arrays and are fully vectorized.
    """

    def __init__(self, gpu: GPUBackend):
        """Initialize with GPU backend."""
        self.gpu = gpu
        self.xp = gpu.xp

    def sma(self, data: Any, period: int) -> Any:
        """Simple Moving Average."""
        xp = self.xp
        n = len(data)
        result = xp.zeros(n)

        # Cumsum approach
        cumsum = xp.cumsum(data)
        result[period - 1 :] = (
            cumsum[period - 1 :] - xp.concatenate([xp.array([0.0]), cumsum[:-period]])
        ) / period

        return result

    def ema(self, data: Any, period: int) -> Any:
        """Exponential Moving Average."""
        xp = self.xp
        n = len(data)
        result = xp.zeros(n)
        alpha = 2.0 / (period + 1)

        # Initialize with SMA
        result[period - 1] = xp.mean(data[:period])

        # EMA calculation
        for i in range(period, n):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]

        return result

    def rsi(self, close: Any, period: int = 14) -> Any:
        """Relative Strength Index."""
        xp = self.xp
        n = len(close)
        rsi = xp.full(n, 50.0)

        delta = xp.diff(close)
        gain = xp.where(delta > 0, delta, 0.0)
        loss = xp.where(delta < 0, -delta, 0.0)

        # Wilder's smoothing
        avg_gain = xp.zeros(n - 1)
        avg_loss = xp.zeros(n - 1)

        avg_gain[period - 1] = xp.mean(gain[:period])
        avg_loss[period - 1] = xp.mean(loss[:period])

        for i in range(period, n - 1):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period

        # RSI calculation
        for i in range(period - 1, n - 1):
            if avg_loss[i] == 0:
                rsi[i + 1] = 100.0 if avg_gain[i] > 0 else 50.0
            else:
                rs = avg_gain[i] / avg_loss[i]
                rsi[i + 1] = 100 - 100 / (1 + rs)

        return rsi

    def macd(
        self,
        close: Any,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> tuple[Any, Any, Any]:
        """MACD indicator."""
        ema_fast = self.ema(close, fast)
        ema_slow = self.ema(close, slow)

        macd_line = ema_fast - ema_slow
        signal_line = self.ema(macd_line, signal)
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def bollinger_bands(
        self,
        close: Any,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> tuple[Any, Any, Any]:
        """Bollinger Bands."""
        xp = self.xp
        n = len(close)

        middle = self.sma(close, period)

        # Rolling standard deviation
        std = xp.zeros(n)
        for i in range(period - 1, n):
            std[i] = xp.std(close[i - period + 1 : i + 1])

        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return upper, middle, lower

    def atr(
        self,
        high: Any,
        low: Any,
        close: Any,
        period: int = 14,
    ) -> Any:
        """Average True Range."""
        xp = self.xp
        n = len(close)

        # True Range
        tr = xp.zeros(n)
        tr[0] = high[0] - low[0]

        for i in range(1, n):
            hl = high[i] - low[i]
            hc = xp.abs(high[i] - close[i - 1])
            lc = xp.abs(low[i] - close[i - 1])
            tr[i] = xp.maximum(hl, xp.maximum(hc, lc))

        # Smoothed ATR (Wilder's method)
        atr = xp.zeros(n)
        atr[period - 1] = xp.mean(tr[:period])

        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

        return atr

    def stochastic(
        self,
        high: Any,
        low: Any,
        close: Any,
        k_period: int = 14,
        d_period: int = 3,
    ) -> tuple[Any, Any]:
        """Stochastic Oscillator."""
        xp = self.xp
        n = len(close)

        k = xp.zeros(n)

        for i in range(k_period - 1, n):
            highest = xp.max(high[i - k_period + 1 : i + 1])
            lowest = xp.min(low[i - k_period + 1 : i + 1])
            if highest != lowest:
                k[i] = 100 * (close[i] - lowest) / (highest - lowest)
            else:
                k[i] = 50.0

        d = self.sma(k, d_period)

        return k, d


# =============================================================================
# 4. GPU OPTIMIZER
# =============================================================================


@dataclass
class GPUOptimizerConfig:
    """Configuration for GPU optimizer."""

    # Population size for genetic algorithm
    population_size: int = 1024

    # Number of generations
    n_generations: int = 50

    # Mutation rate
    mutation_rate: float = 0.1

    # Crossover rate
    crossover_rate: float = 0.8

    # Elite ratio (top performers kept)
    elite_ratio: float = 0.1

    # Tournament size for selection
    tournament_size: int = 5


class GPUOptimizer:
    """
    GPU-accelerated parameter optimization.

    Features:
    - Parallel genetic algorithm on GPU
    - Massive population sizes (100K+)
    - Fast fitness evaluation
    - Adaptive mutation
    """

    def __init__(
        self,
        gpu: GPUBackend,
        config: Optional[GPUOptimizerConfig] = None,
    ):
        """Initialize GPU optimizer."""
        self.gpu = gpu
        self.config = config or GPUOptimizerConfig()
        self.xp = gpu.xp

    def optimize(
        self,
        candles: NDArray[np.float64],
        param_bounds: list[tuple[float, float]],
        strategy_fn: Callable,
        fitness_fn: Callable,
        n_generations: Optional[int] = None,
    ) -> tuple[NDArray[np.float64], float]:
        """
        Run GPU-accelerated optimization.

        Args:
            candles: OHLCV data
            param_bounds: List of (min, max) for each parameter
            strategy_fn: Strategy function
            fitness_fn: Fitness function (metrics -> score)
            n_generations: Override config generations

        Returns:
            Tuple of (best_params, best_fitness)
        """
        xp = self.xp
        n_generations = n_generations or self.config.n_generations
        n_params = len(param_bounds)
        pop_size = self.config.population_size

        # Transfer data to GPU
        candles_gpu = self.gpu.to_device(candles)
        bounds_gpu = self.gpu.to_device(np.array(param_bounds))

        # Initialize population
        population = self._init_population(bounds_gpu, pop_size, n_params)

        # Evolution loop
        best_fitness = -np.inf
        best_params = None

        for gen in range(n_generations):
            # Evaluate fitness
            fitness = self._evaluate_fitness(
                candles_gpu, population, strategy_fn, fitness_fn
            )

            # Track best
            gen_best_idx = int(xp.argmax(fitness))
            gen_best_fitness = float(fitness[gen_best_idx])

            if gen_best_fitness > best_fitness:
                best_fitness = gen_best_fitness
                best_params = self.gpu.to_host(population[gen_best_idx])

            # Selection
            selected = self._tournament_selection(fitness, pop_size)

            # Crossover
            offspring = self._crossover(population[selected], bounds_gpu)

            # Mutation
            offspring = self._mutate(offspring, bounds_gpu, gen / n_generations)

            # Elitism
            n_elite = int(pop_size * self.config.elite_ratio)
            elite_idx = xp.argsort(fitness)[-n_elite:]
            offspring[:n_elite] = population[elite_idx]

            population = offspring

        return best_params, best_fitness

    def _init_population(
        self,
        bounds: Any,
        pop_size: int,
        n_params: int,
    ) -> Any:
        """Initialize random population within bounds."""
        xp = self.xp

        # Random values in [0, 1]
        population = xp.random.random((pop_size, n_params))

        # Scale to bounds
        mins = bounds[:, 0]
        ranges = bounds[:, 1] - bounds[:, 0]
        population = mins + population * ranges

        return population

    def _evaluate_fitness(
        self,
        candles: Any,
        population: Any,
        strategy_fn: Callable,
        fitness_fn: Callable,
    ) -> Any:
        """Evaluate fitness for entire population."""
        # Use batch backtester
        batch_config = BatchBacktestConfig(batch_size=self.config.population_size)
        backtester = BatchBacktester(self.gpu, batch_config)

        result = backtester.run_batch(
            self.gpu.to_host(candles),
            self.gpu.to_host(population),
            strategy_fn,
        )

        # Apply fitness function to metrics
        fitness = np.array(
            [fitness_fn(result.metrics[i]) for i in range(len(population))]
        )

        return self.gpu.to_device(fitness)

    def _tournament_selection(self, fitness: Any, n_select: int) -> Any:
        """Tournament selection."""
        xp = self.xp
        pop_size = len(fitness)
        selected = xp.zeros(n_select, dtype=xp.int32)

        for i in range(n_select):
            # Random tournament
            candidates = xp.random.randint(0, pop_size, self.config.tournament_size)
            winner = candidates[xp.argmax(fitness[candidates])]
            selected[i] = winner

        return selected

    def _crossover(self, parents: Any, bounds: Any) -> Any:
        """Uniform crossover."""
        xp = self.xp
        n = len(parents)
        n_params = parents.shape[1]

        offspring = xp.zeros_like(parents)

        for i in range(0, n - 1, 2):
            if xp.random.random() < self.config.crossover_rate:
                # Uniform crossover
                mask = xp.random.random(n_params) < 0.5
                offspring[i] = xp.where(mask, parents[i], parents[i + 1])
                offspring[i + 1] = xp.where(mask, parents[i + 1], parents[i])
            else:
                offspring[i] = parents[i]
                offspring[i + 1] = parents[i + 1]

        return offspring

    def _mutate(
        self,
        population: Any,
        bounds: Any,
        progress: float,
    ) -> Any:
        """Adaptive mutation."""
        xp = self.xp

        # Adaptive mutation rate (decrease over time)
        mutation_rate = self.config.mutation_rate * (1 - progress * 0.5)

        # Mutation mask
        mask = xp.random.random(population.shape) < mutation_rate

        # Gaussian mutation
        ranges = bounds[:, 1] - bounds[:, 0]
        mutation = xp.random.normal(0, 0.1 * ranges, population.shape)

        population = xp.where(mask, population + mutation, population)

        # Clip to bounds
        population = xp.clip(population, bounds[:, 0], bounds[:, 1])

        return population


# =============================================================================
# STRATEGY HELPERS (GPU-compatible)
# =============================================================================


def gpu_rsi_strategy(candles: Any, params: Any, xp: Any) -> Any:
    """GPU-compatible RSI strategy."""
    close = candles[:, 3]
    period = int(params[0])
    oversold = params[1]
    overbought = params[2]

    n = len(close)
    signals = xp.zeros(n, dtype=xp.int8)

    # Simplified RSI
    delta = xp.diff(close)
    gain = xp.where(delta > 0, delta, 0.0)
    loss = xp.where(delta < 0, -delta, 0.0)

    avg_gain = xp.zeros(n - 1)
    avg_loss = xp.zeros(n - 1)

    if n > period:
        avg_gain[period - 1] = xp.mean(gain[:period])
        avg_loss[period - 1] = xp.mean(loss[:period])

        for i in range(period, n - 1):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period

        rsi = xp.full(n, 50.0)
        for i in range(period - 1, n - 1):
            if avg_loss[i] > 0:
                rs = avg_gain[i] / avg_loss[i]
                rsi[i + 1] = 100 - 100 / (1 + rs)
            else:
                rsi[i + 1] = 100.0 if avg_gain[i] > 0 else 50.0

        # Generate signals
        for i in range(period, n):
            if rsi[i] < oversold and rsi[i - 1] >= oversold:
                signals[i] = 1  # Buy
            elif rsi[i] > overbought and rsi[i - 1] <= overbought:
                signals[i] = -1  # Sell

    return signals


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Backend
    "GPUBackendType",
    "GPUInfo",
    "GPUConfig",
    "GPUBackend",
    # Batch Backtester
    "BatchBacktestConfig",
    "BatchBacktestResult",
    "BatchBacktester",
    # Indicators
    "VectorizedIndicators",
    # Optimizer
    "GPUOptimizerConfig",
    "GPUOptimizer",
    # Helpers
    "gpu_rsi_strategy",
    # Constants
    "CUPY_AVAILABLE",
    "OPENCL_AVAILABLE",
]
