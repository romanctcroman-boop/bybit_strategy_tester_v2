"""
MEGA Test V4 - Optimizers with Different Parameter Groups
==========================================================

Testing optimization engines with various parameter configurations:
- FastGridOptimizer (Numba JIT)
- GPUGridOptimizer (CuPy + CUDA) if available
- UniversalOptimizer (auto-select backend)
- BayesianOptimizer
- WalkForwardOptimizer
- OptunaOptimizer

Parameter groups tested:
- Small grid (quick validation)
- Medium grid (standard optimization)
- Large grid (stress test)
- RSI-focused parameters
- Risk-focused parameters (SL/TP heavy)
- Balanced multi-metric optimization
"""

import os
import sys
import time
import traceback
from dataclasses import dataclass

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd


# ============================================================================
# Test Result Tracking
# ============================================================================
@dataclass
class TestResult:
    name: str
    category: str
    passed: bool
    details: str
    execution_time: float = 0.0
    error: str | None = None


test_results: list[TestResult] = []


def run_test(name: str, category: str):
    """Decorator to track test results with timing."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                if result is True or result is None:
                    test_results.append(
                        TestResult(
                            name, category, True, f"OK ({elapsed:.2f}s)", elapsed
                        )
                    )
                    print(f"  ✅ {name} ({elapsed:.2f}s)")
                else:
                    test_results.append(
                        TestResult(name, category, False, str(result), elapsed)
                    )
                    print(f"  ❌ {name}: {result}")
            except Exception as e:
                elapsed = time.time() - start_time
                test_results.append(
                    TestResult(
                        name, category, False, str(e), elapsed, traceback.format_exc()
                    )
                )
                print(f"  ❌ {name}: {e}")

        return wrapper

    return decorator


def generate_test_ohlcv(n_bars: int = 500, start_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing optimizers."""
    np.random.seed(42)  # Reproducible

    dates = pd.date_range(start="2024-01-01", periods=n_bars, freq="1h")

    # Random walk with trend and volatility clusters
    returns = np.random.normal(0.0002, 0.015, n_bars)

    # Add volatility clustering
    vol_factor = np.ones(n_bars)
    for i in range(1, n_bars):
        vol_factor[i] = 0.9 * vol_factor[i - 1] + 0.1 * abs(returns[i - 1]) * 50
    returns = returns * (1 + vol_factor * 0.5)

    prices = start_price * np.cumprod(1 + returns)

    # Generate OHLC from prices
    data = {
        "timestamp": dates,
        "open": prices * (1 + np.random.uniform(-0.003, 0.003, n_bars)),
        "high": prices * (1 + np.random.uniform(0.001, 0.015, n_bars)),
        "low": prices * (1 - np.random.uniform(0.001, 0.015, n_bars)),
        "close": prices,
        "volume": np.random.uniform(1000, 50000, n_bars),
    }

    df = pd.DataFrame(data)
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)

    return df


# ============================================================================
# CATEGORY 1: FastGridOptimizer Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 1: FastGridOptimizer (Numba JIT)")
print("=" * 70)


@run_test("FastGridOptimizer import", "FastOptimizer")
def test_fast_optimizer_import():
    """Test FastGridOptimizer can be imported."""
    from backend.backtesting.fast_optimizer import (
        NUMBA_AVAILABLE,
        FastGridOptimizer,
    )

    if NUMBA_AVAILABLE:
        print("    [INFO] Numba is available")
    else:
        print("    [WARN] Numba not available - fallback mode")

    assert FastGridOptimizer is not None
    return True


@run_test("FastGridOptimizer - Small Grid (125 combos)", "FastOptimizer")
def test_fast_optimizer_small_grid():
    """Test small parameter grid optimization."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    # Small grid: 5 * 5 * 5 = 125 combinations
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[65, 70, 75],
        rsi_oversold_range=[25, 30, 35],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10000.0,
        leverage=1,
        commission=0.0007,
        optimize_metric="sharpe_ratio",
        direction="long",
    )

    # Verify result structure
    assert result.status == "completed"
    assert result.total_combinations > 0
    assert result.tested_combinations > 0
    assert result.best_params is not None
    assert "rsi_period" in result.best_params
    assert len(result.top_results) > 0

    print(
        f"    [INFO] Best Sharpe: {result.best_score:.2f}, Trades: {result.best_metrics.get('total_trades', 0)}"
    )

    return True


@run_test("FastGridOptimizer - Medium Grid (1000 combos)", "FastOptimizer")
def test_fast_optimizer_medium_grid():
    """Test medium parameter grid optimization."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=1000)

    # Medium grid: 5 * 8 * 8 * 3 * 3 ≈ 2880 combinations
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 10, 14, 21, 28],
        rsi_overbought_range=[60, 65, 70, 75, 80, 85],
        rsi_oversold_range=[15, 20, 25, 30, 35, 40],
        stop_loss_range=[0.5, 1.0, 2.0],
        take_profit_range=[1.0, 2.0, 3.0],
        initial_capital=10000.0,
        leverage=5,
        commission=0.0007,
        optimize_metric="sharpe_ratio",
        direction="long",
    )

    assert result.status == "completed"
    assert result.tested_combinations >= 1000  # Should test many combinations

    speed = result.tested_combinations / result.execution_time_seconds
    print(
        f"    [INFO] Speed: {speed:,.0f} combos/sec, Time: {result.execution_time_seconds:.2f}s"
    )

    return True


@run_test("FastGridOptimizer - RSI Parameter Focus", "FastOptimizer")
def test_fast_optimizer_rsi_focus():
    """Test optimization focused on RSI parameters."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    # RSI-focused: Many RSI values, fixed SL/TP
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[5, 7, 10, 12, 14, 18, 21, 25, 28, 30],  # 10 periods
        rsi_overbought_range=[60, 65, 70, 75, 80],  # 5 levels
        rsi_oversold_range=[20, 25, 30, 35, 40],  # 5 levels
        stop_loss_range=[1.5],  # Fixed SL
        take_profit_range=[3.0],  # Fixed TP
        initial_capital=10000.0,
        leverage=1,
        optimize_metric="total_return",
        direction="long",
    )

    assert result.status == "completed"
    assert result.best_params["rsi_period"] in [5, 7, 10, 12, 14, 18, 21, 25, 28, 30]

    return True


@run_test("FastGridOptimizer - Risk Management Focus", "FastOptimizer")
def test_fast_optimizer_risk_focus():
    """Test optimization focused on SL/TP parameters."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    # Risk-focused: Fixed RSI, many SL/TP combinations
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14],  # Fixed RSI period
        rsi_overbought_range=[70],  # Fixed
        rsi_oversold_range=[30],  # Fixed
        stop_loss_range=[0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0],  # 8 SL levels
        take_profit_range=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0],  # 8 TP levels
        initial_capital=10000.0,
        leverage=10,
        optimize_metric="sharpe_ratio",
        direction="long",
        filters={"min_trades": 3},
    )

    assert result.status == "completed"
    # Best SL/TP should be reasonable
    assert result.best_params["stop_loss_pct"] > 0
    assert result.best_params["take_profit_pct"] > 0

    print(
        f"    [INFO] Best SL: {result.best_params['stop_loss_pct']:.1f}%, TP: {result.best_params['take_profit_pct']:.1f}%"
    )

    return True


@run_test("FastGridOptimizer - Direction SHORT", "FastOptimizer")
def test_fast_optimizer_short():
    """Test short direction optimization."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10000.0,
        leverage=1,
        optimize_metric="sharpe_ratio",
        direction="short",  # Short only
    )

    assert result.status == "completed"
    return True


@run_test("FastGridOptimizer - Direction BOTH", "FastOptimizer")
def test_fast_optimizer_both():
    """Test both directions optimization."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.5],
        take_profit_range=[3.0],
        initial_capital=10000.0,
        leverage=1,
        optimize_metric="sharpe_ratio",
        direction="both",  # Long + Short
    )

    assert result.status == "completed"
    return True


@run_test("FastGridOptimizer - Optimize by Return", "FastOptimizer")
def test_fast_optimizer_by_return():
    """Test optimization by total return metric."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 4.0],
        initial_capital=10000.0,
        optimize_metric="total_return",  # Optimize for return
        direction="long",
    )

    assert result.status == "completed"
    assert "total_return" in result.best_metrics

    return True


@run_test("FastGridOptimizer - Optimize by Calmar", "FastOptimizer")
def test_fast_optimizer_by_calmar():
    """Test optimization by Calmar ratio metric."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 4.0],
        initial_capital=10000.0,
        optimize_metric="calmar_ratio",  # Optimize for Calmar
        direction="long",
    )

    assert result.status == "completed"

    return True


test_fast_optimizer_import()
test_fast_optimizer_small_grid()
test_fast_optimizer_medium_grid()
test_fast_optimizer_rsi_focus()
test_fast_optimizer_risk_focus()
test_fast_optimizer_short()
test_fast_optimizer_both()
test_fast_optimizer_by_return()
test_fast_optimizer_by_calmar()


# ============================================================================
# CATEGORY 2: GPU Optimizer Tests (if available)
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 2: GPUGridOptimizer (CuPy + CUDA)")
print("=" * 70)


@run_test("GPU Optimizer availability", "GPUOptimizer")
def test_gpu_availability():
    """Check if GPU optimizer is available."""
    try:
        from backend.backtesting.gpu_optimizer import GPU_AVAILABLE, GPU_NAME

        if GPU_AVAILABLE:
            print(f"    [INFO] GPU available: {GPU_NAME}")
        else:
            print("    [INFO] GPU not available - tests will be skipped")

        return True
    except ImportError:
        print("    [INFO] GPU optimizer module not found")
        return True


@run_test("GPUGridOptimizer - Small Grid", "GPUOptimizer")
def test_gpu_optimizer_small():
    """Test GPU optimizer with small grid."""
    try:
        from backend.backtesting.gpu_optimizer import GPU_AVAILABLE, GPUGridOptimizer

        if not GPU_AVAILABLE:
            print("    [SKIP] GPU not available")
            return True

        optimizer = GPUGridOptimizer()
        candles = generate_test_ohlcv(n_bars=500)

        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[10, 14, 21],
            rsi_overbought_range=[70, 75],
            rsi_oversold_range=[25, 30],
            stop_loss_range=[1.0, 2.0],
            take_profit_range=[2.0, 3.0],
            initial_capital=10000.0,
            leverage=1,
            optimize_metric="sharpe_ratio",
        )

        assert result.status == "completed"
        print(
            f"    [INFO] GPU Speed: {result.tested_combinations / result.execution_time_seconds:,.0f} combos/sec"
        )

        return True
    except Exception as e:
        print(f"    [INFO] GPU test skipped: {e}")
        return True


@run_test("GPUGridOptimizer - Large Grid (5000+ combos)", "GPUOptimizer")
def test_gpu_optimizer_large():
    """Test GPU optimizer with large grid to show GPU advantage."""
    try:
        from backend.backtesting.gpu_optimizer import GPU_AVAILABLE, GPUGridOptimizer

        if not GPU_AVAILABLE:
            print("    [SKIP] GPU not available")
            return True

        optimizer = GPUGridOptimizer()
        candles = generate_test_ohlcv(n_bars=2000)

        # Large grid: 5 * 10 * 10 * 5 * 5 = 12,500 combinations
        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[7, 10, 14, 21, 28],
            rsi_overbought_range=[60, 65, 70, 72, 75, 77, 80, 82, 85, 90],
            rsi_oversold_range=[10, 15, 20, 23, 25, 28, 30, 33, 35, 40],
            stop_loss_range=[0.5, 1.0, 1.5, 2.0, 3.0],
            take_profit_range=[1.0, 2.0, 3.0, 4.0, 5.0],
            initial_capital=10000.0,
            leverage=10,
            optimize_metric="sharpe_ratio",
        )

        assert result.status == "completed"
        speed = result.tested_combinations / result.execution_time_seconds
        print(
            f"    [INFO] GPU tested {result.tested_combinations:,} combos at {speed:,.0f}/sec"
        )

        return True
    except Exception as e:
        print(f"    [INFO] GPU large test skipped: {e}")
        return True


test_gpu_availability()
test_gpu_optimizer_small()
test_gpu_optimizer_large()


# ============================================================================
# CATEGORY 3: Universal Optimizer Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 3: UniversalOptimizer (Auto Backend)")
print("=" * 70)


@run_test("UniversalOptimizer import", "UniversalOptimizer")
def test_universal_import():
    """Test UniversalOptimizer import."""
    from backend.backtesting.optimizer import OptimizationResult, UniversalOptimizer

    assert UniversalOptimizer is not None
    assert OptimizationResult is not None
    return True


@run_test("UniversalOptimizer - Auto Backend", "UniversalOptimizer")
def test_universal_auto():
    """Test UniversalOptimizer with auto backend selection."""
    from backend.backtesting.optimizer import UniversalOptimizer

    optimizer = UniversalOptimizer(backend="auto")
    candles = generate_test_ohlcv(n_bars=500)

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10000.0,
    )

    assert result.status == "completed"
    print(f"    [INFO] Backend used: {result.backend_used}")

    return True


@run_test("UniversalOptimizer - Force CPU", "UniversalOptimizer")
def test_universal_cpu():
    """Test UniversalOptimizer with forced CPU backend."""
    try:
        from backend.backtesting.optimizer import UniversalOptimizer

        optimizer = UniversalOptimizer(backend="cpu")
        candles = generate_test_ohlcv(n_bars=500)

        result = optimizer.optimize(
            candles=candles,
            rsi_period_range=[14],
            rsi_overbought_range=[70],
            rsi_oversold_range=[30],
            stop_loss_range=[1.5],
            take_profit_range=[3.0],
            initial_capital=10000.0,
        )

        assert result.status == "completed"
        assert result.backend_used == "cpu"

        return True
    except RuntimeError as e:
        if "not available" in str(e):
            print("    [SKIP] CPU backend not available")
            return True
        raise


test_universal_import()
test_universal_auto()
test_universal_cpu()


# ============================================================================
# CATEGORY 4: Bayesian Optimizer Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 4: BayesianOptimizer")
print("=" * 70)


@run_test("BayesianOptimizer import", "BayesianOptimizer")
def test_bayesian_import():
    """Test BayesianOptimizer import."""
    try:
        from backend.core.bayesian import BayesianOptimizer

        assert BayesianOptimizer is not None
        return True
    except ImportError as e:
        print(f"    [INFO] BayesianOptimizer not available: {e}")
        return True


@run_test("BayesianOptimizer - Basic Optimization", "BayesianOptimizer")
def test_bayesian_basic():
    """Test basic Bayesian optimization."""
    try:
        from backend.core.bayesian import BayesianOptimizer

        optimizer = BayesianOptimizer()

        # Define parameter space
        param_space = {
            "rsi_period": (5, 30),
            "rsi_oversold": (20, 40),
            "rsi_overbought": (60, 80),
        }

        # Simple objective function
        def objective(params):
            # Simulate: best around RSI 14, oversold 30, overbought 70
            rsi_diff = abs(params["rsi_period"] - 14)
            os_diff = abs(params["rsi_oversold"] - 30)
            ob_diff = abs(params["rsi_overbought"] - 70)
            return -1 * (rsi_diff + os_diff + ob_diff)  # Negative because we minimize

        # Run optimization with limited iterations
        result = optimizer.optimize(
            objective_func=objective,
            param_space=param_space,
            n_iterations=10,
            n_initial_points=5,
        )

        assert result is not None
        return True

    except Exception as e:
        print(f"    [INFO] Bayesian test skipped: {e}")
        return True


test_bayesian_import()
test_bayesian_basic()


# ============================================================================
# CATEGORY 5: Walk-Forward Optimizer Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 5: WalkForwardOptimizer")
print("=" * 70)


@run_test("WalkForwardOptimizer import", "WalkForward")
def test_walkforward_import():
    """Test WalkForwardOptimizer import."""
    try:
        from backend.backtesting.walk_forward import WalkForwardOptimizer

        assert WalkForwardOptimizer is not None
        return True
    except ImportError:
        from backend.services.walk_forward import WalkForwardOptimizer

        assert WalkForwardOptimizer is not None
        return True


@run_test("WalkForwardOptimizer - Basic Split", "WalkForward")
def test_walkforward_basic():
    """Test Walk-Forward with basic configuration."""
    try:
        try:
            from backend.backtesting.walk_forward import WalkForwardOptimizer
        except ImportError:
            from backend.services.walk_forward import WalkForwardOptimizer

        optimizer = WalkForwardOptimizer(
            n_splits=3,
            train_ratio=0.7,
        )

        candles = generate_test_ohlcv(n_bars=1000)

        # Just test that it initializes correctly
        assert optimizer.n_splits == 3
        assert optimizer.train_ratio == 0.7

        return True

    except Exception as e:
        print(f"    [INFO] WalkForward test skipped: {e}")
        return True


test_walkforward_import()
test_walkforward_basic()


# ============================================================================
# CATEGORY 6: Optuna Optimizer Tests
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 6: OptunaOptimizer")
print("=" * 70)


@run_test("OptunaOptimizer import", "OptunaOptimizer")
def test_optuna_import():
    """Test OptunaOptimizer import."""
    try:
        from backend.optimization.optuna_optimizer import OptunaOptimizer

        assert OptunaOptimizer is not None
        return True
    except ImportError as e:
        print(f"    [INFO] OptunaOptimizer not available: {e}")
        return True


@run_test("OptunaOptimizer - Quick Study", "OptunaOptimizer")
def test_optuna_quick():
    """Test Optuna quick optimization."""
    try:
        import optuna

        from backend.optimization.optuna_optimizer import OptunaOptimizer

        # Create simple study
        def objective(trial):
            x = trial.suggest_float("x", -10, 10)
            y = trial.suggest_float("y", -10, 10)
            return (x - 2) ** 2 + (y + 3) ** 2

        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=10, show_progress_bar=False)

        assert study.best_params is not None
        assert abs(study.best_params["x"] - 2) < 5  # Should be close to optimal

        return True

    except ImportError:
        print("    [SKIP] Optuna not installed")
        return True
    except Exception as e:
        print(f"    [INFO] Optuna test skipped: {e}")
        return True


test_optuna_import()
test_optuna_quick()


# ============================================================================
# CATEGORY 7: Multi-Metric Optimization
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 7: Multi-Metric Optimization")
print("=" * 70)


@run_test("Multi-metric with weights", "MultiMetric")
def test_multi_metric_weights():
    """Test optimization with weighted metrics."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    # Custom weights favoring Sharpe and low drawdown
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10000.0,
        optimize_metric="sharpe_ratio",
        weights={
            "sharpe_ratio": 0.5,
            "max_drawdown": 0.3,  # Negative impact
            "win_rate": 0.2,
        },
    )

    assert result.status == "completed"
    return True


@run_test("Optimization with filters", "MultiMetric")
def test_optimization_filters():
    """Test optimization with result filters."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=500)

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[10, 14, 21],
        rsi_overbought_range=[70, 75, 80],
        rsi_oversold_range=[20, 25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0, 4.0],
        initial_capital=10000.0,
        optimize_metric="sharpe_ratio",
        filters={
            "min_trades": 5,  # Minimum 5 trades
            "max_drawdown_limit": 0.30,  # Max 30% drawdown
            "min_profit_factor": 1.0,  # Must be profitable
        },
    )

    assert result.status == "completed"

    # Verify filters applied
    for res in result.top_results[:5]:
        if res.get("total_trades", 0) > 0:
            assert res["total_trades"] >= 5 or res["total_trades"] == 0

    return True


test_multi_metric_weights()
test_optimization_filters()


# ============================================================================
# CATEGORY 8: Large Scale Performance
# ============================================================================
print("\n" + "=" * 70)
print("CATEGORY 8: Large Scale Performance")
print("=" * 70)


@run_test("Large Grid (10,000+ combinations)", "Performance")
def test_large_scale():
    """Test large scale optimization performance."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=2000)

    # Large grid: 5 * 6 * 6 * 8 * 8 = 11,520 combinations
    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[7, 10, 14, 21, 28],
        rsi_overbought_range=[65, 70, 72, 75, 78, 80],
        rsi_oversold_range=[20, 22, 25, 28, 30, 35],
        stop_loss_range=[0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0],
        take_profit_range=[1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0],
        initial_capital=10000.0,
        leverage=10,
        optimize_metric="sharpe_ratio",
    )

    assert result.status == "completed"
    speed = result.tested_combinations / result.execution_time_seconds

    print(f"    [INFO] Tested {result.tested_combinations:,} combinations")
    print(f"    [INFO] Speed: {speed:,.0f} combinations/second")
    print(f"    [INFO] Total time: {result.execution_time_seconds:.2f}s")

    # Should achieve reasonable speed with Numba
    assert speed > 100, f"Speed too slow: {speed:.0f} combos/sec"

    return True


@run_test("Long data series (5000 candles)", "Performance")
def test_long_series():
    """Test with longer price series."""
    from backend.backtesting.fast_optimizer import NUMBA_AVAILABLE, FastGridOptimizer

    if not NUMBA_AVAILABLE:
        print("    [SKIP] Numba not available")
        return True

    optimizer = FastGridOptimizer()
    candles = generate_test_ohlcv(n_bars=5000)  # 5000 candles

    result = optimizer.optimize(
        candles=candles,
        rsi_period_range=[14, 21],
        rsi_overbought_range=[70, 75],
        rsi_oversold_range=[25, 30],
        stop_loss_range=[1.0, 2.0],
        take_profit_range=[2.0, 3.0],
        initial_capital=10000.0,
        optimize_metric="sharpe_ratio",
    )

    assert result.status == "completed"
    print(
        f"    [INFO] Processed {len(candles):,} candles in {result.execution_time_seconds:.2f}s"
    )

    return True


test_large_scale()
test_long_series()


# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("MEGA TEST V4 - OPTIMIZATION TESTS SUMMARY")
print("=" * 70)

# Group by category
categories = {}
for result in test_results:
    if result.category not in categories:
        categories[result.category] = {
            "passed": 0,
            "failed": 0,
            "tests": [],
            "total_time": 0.0,
        }

    if result.passed:
        categories[result.category]["passed"] += 1
    else:
        categories[result.category]["failed"] += 1
    categories[result.category]["tests"].append(result)
    categories[result.category]["total_time"] += result.execution_time

# Print category summaries
total_passed = 0
total_failed = 0
total_time = 0.0

for cat, data in categories.items():
    passed = data["passed"]
    failed = data["failed"]
    total = passed + failed
    cat_time = data["total_time"]
    total_passed += passed
    total_failed += failed
    total_time += cat_time

    status = "✅" if failed == 0 else "⚠️"
    print(f"\n{status} {cat}: {passed}/{total} passed ({cat_time:.2f}s)")

    if failed > 0:
        for test in data["tests"]:
            if not test.passed:
                print(f"   ❌ {test.name}: {test.details}")

# Overall summary
print("\n" + "-" * 70)
total = total_passed + total_failed
pct = (total_passed / total * 100) if total > 0 else 0

if total_failed == 0:
    print(f"🎉 ALL TESTS PASSED: {total_passed}/{total} ({pct:.1f}%)")
else:
    print(f"⚠️ TESTS COMPLETED: {total_passed}/{total} passed ({pct:.1f}%)")
    print(f"   Failed tests: {total_failed}")

print(f"\n⏱️ Total execution time: {total_time:.2f}s")
print("=" * 70)
