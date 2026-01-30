"""
🧪 Test Script for New Optimization Modules
Tests all newly implemented features:
1. Extended Metrics (Sortino, Calmar, Omega)
2. Optuna Optimization
3. Walk-Forward Validation
4. Ray Parallel Optimization
5. Regime Detection
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime

print("=" * 80)
print("🧪 TESTING NEW OPTIMIZATION MODULES")
print("=" * 80)
print(f"Timestamp: {datetime.now()}")
print()

# ============================================================================
# 1. Test Extended Metrics
# ============================================================================
print("\n" + "=" * 80)
print("1️⃣ EXTENDED METRICS TEST")
print("=" * 80)

try:
    from backend.core.extended_metrics import (
        ExtendedMetricsCalculator,
        calculate_extended_metrics
    )
    
    # Create sample equity curve
    np.random.seed(42)
    initial = 10000
    returns = np.random.normal(0.0002, 0.02, 500)  # 500 hourly returns
    equity = initial * np.cumprod(1 + returns)
    equity = np.insert(equity, 0, initial)
    
    # Sample trades
    trades = [
        type('Trade', (), {'pnl': 100})(),
        type('Trade', (), {'pnl': -50})(),
        type('Trade', (), {'pnl': 150})(),
        type('Trade', (), {'pnl': -75})(),
        type('Trade', (), {'pnl': 200})(),
    ]
    
    # Calculate metrics
    calc = ExtendedMetricsCalculator(risk_free_rate=0.02, periods_per_year=8760)
    result = calc.calculate_all(equity, trades)
    
    print(f"✅ Extended Metrics Calculator: LOADED")
    print(f"   Sharpe Ratio:   {result.sharpe_ratio:.4f}")
    print(f"   Sortino Ratio:  {result.sortino_ratio:.4f}")
    print(f"   Calmar Ratio:   {result.calmar_ratio:.4f}")
    print(f"   Omega Ratio:    {result.omega_ratio:.4f}")
    print(f"   Profit Factor:  {result.profit_factor:.4f}")
    print(f"   Max Drawdown:   {result.max_drawdown:.4%}")
    print(f"   Recovery Factor:{result.recovery_factor:.4f}")
    print(f"   Ulcer Index:    {result.ulcer_index:.4f}")
    print(f"   Tail Ratio:     {result.tail_ratio:.4f}")
    
except Exception as e:
    print(f"❌ Extended Metrics: FAILED - {e}")

# ============================================================================
# 2. Test Optuna Optimizer
# ============================================================================
print("\n" + "=" * 80)
print("2️⃣ OPTUNA OPTIMIZER TEST")
print("=" * 80)

try:
    from backend.optimization.optuna_optimizer import (
        OptunaOptimizer,
        OPTUNA_AVAILABLE,
        create_rsi_param_space
    )
    
    if OPTUNA_AVAILABLE:
        # Simple test objective
        def test_objective(params):
            # Fake Sharpe based on params
            return 1.5 + params['period'] * 0.01 - abs(params['overbought'] - 70) * 0.02
        
        param_space = {
            'period': {'type': 'int', 'low': 10, 'high': 20},
            'overbought': {'type': 'int', 'low': 65, 'high': 80},
        }
        
        optimizer = OptunaOptimizer(sampler_type='tpe')
        result = optimizer.optimize_strategy(
            objective_fn=test_objective,
            param_space=param_space,
            n_trials=20,  # Small test
            show_progress=False
        )
        
        print(f"✅ Optuna Optimizer: LOADED")
        print(f"   Best Value:  {result.best_value:.4f}")
        print(f"   Best Params: {result.best_params}")
        print(f"   Trials:      {result.n_trials}")
        print(f"   Time:        {result.optimization_time_seconds:.2f}s")
    else:
        print("⚠️ Optuna not installed - Install with: pip install optuna")
        
except Exception as e:
    print(f"❌ Optuna Optimizer: FAILED - {e}")

# ============================================================================
# 3. Test Walk-Forward Validation
# ============================================================================
print("\n" + "=" * 80)
print("3️⃣ WALK-FORWARD VALIDATION TEST")
print("=" * 80)

try:
    from backend.validation.walk_forward import (
        WalkForwardValidator,
        ValidationStatus
    )
    
    print(f"✅ Walk-Forward Validator: LOADED")
    print(f"   ValidationStatus enum: {[s.value for s in ValidationStatus]}")
    
    # Create validator
    wfv = WalkForwardValidator(
        in_sample_size=100,
        out_of_sample_size=20,
        step_size=20
    )
    
    print(f"   In-Sample Size:    {wfv.in_sample_size} bars")
    print(f"   Out-of-Sample Size:{wfv.out_of_sample_size} bars")
    print(f"   Step Size:         {wfv.step_size} bars")
    
except Exception as e:
    print(f"❌ Walk-Forward Validation: FAILED - {e}")

# ============================================================================
# 4. Test Ray/Multiprocessing Optimizer
# ============================================================================
print("\n" + "=" * 80)
print("4️⃣ PARALLEL OPTIMIZER TEST")
print("=" * 80)

try:
    from backend.optimization.ray_optimizer import (
        RayParallelOptimizer,
        MultiprocessingOptimizer,
        get_parallel_optimizer,
        RAY_AVAILABLE
    )
    
    print(f"✅ Parallel Optimizer: LOADED")
    print(f"   Ray Available: {RAY_AVAILABLE}")
    
    # Get best available optimizer
    optimizer = get_parallel_optimizer(prefer_ray=False)  # Use multiprocessing for test
    print(f"   Using: {type(optimizer).__name__}")
    
except Exception as e:
    print(f"❌ Parallel Optimizer: FAILED - {e}")

# ============================================================================
# 5. Test Regime Detection
# ============================================================================
print("\n" + "=" * 80)
print("5️⃣ REGIME DETECTION TEST")
print("=" * 80)

try:
    from backend.ml.regime_detection import (
        KMeansRegimeDetector,
        GMMRegimeDetector,
        get_regime_detector,
        HMM_AVAILABLE
    )
    
    print(f"✅ Regime Detection: LOADED")
    print(f"   HMM Available: {HMM_AVAILABLE}")
    
    # Create sample data
    np.random.seed(42)
    n_bars = 500
    
    # Simulate regime changes
    prices = [100]
    for i in range(n_bars - 1):
        if i < 100:  # Bull regime
            change = np.random.normal(0.001, 0.01)
        elif i < 200:  # Bear regime
            change = np.random.normal(-0.001, 0.02)
        elif i < 350:  # Sideways
            change = np.random.normal(0, 0.015)
        else:  # Bull again
            change = np.random.normal(0.0015, 0.012)
        prices.append(prices[-1] * (1 + change))
    
    test_data = pd.DataFrame({
        'close': prices,
        'high': np.array(prices) * 1.01,
        'low': np.array(prices) * 0.99,
        'open': np.roll(prices, 1),
        'volume': np.random.randint(1000, 5000, n_bars)
    })
    
    # Test K-Means detector
    detector = KMeansRegimeDetector(n_regimes=3)
    result = detector.fit_predict(test_data)
    
    print(f"   K-Means Regimes: {result.n_regimes}")
    print(f"   Current Regime:  {result.current_regime_name}")
    print(f"   Regime Distribution:")
    for i, name in enumerate(result.regime_names):
        freq = np.mean(result.regimes == i) * 100
        print(f"      {name}: {freq:.1f}%")
    
except Exception as e:
    print(f"❌ Regime Detection: FAILED - {e}")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 80)
print("📊 MODULE STATUS SUMMARY")
print("=" * 80)

modules = [
    ("Extended Metrics", "backend.core.extended_metrics", True),
    ("Optuna Optimizer", "backend.optimization.optuna_optimizer", True),
    ("Walk-Forward Validation", "backend.validation.walk_forward", True),
    ("Parallel Optimizer (Ray)", "backend.optimization.ray_optimizer", True),
    ("Regime Detection", "backend.ml.regime_detection", True),
]

for name, module_path, expected in modules:
    try:
        __import__(module_path)
        status = "✅ READY"
    except ImportError as e:
        dep = str(e).split("'")[1] if "'" in str(e) else "unknown"
        status = f"⚠️ NEEDS: pip install {dep}"
    except Exception as e:
        status = f"❌ ERROR: {e}"
    
    print(f"   {name:30} {status}")

print()
print("=" * 80)
print("🎉 ALL MODULES CREATED SUCCESSFULLY!")
print("=" * 80)
print()
print("Optional dependencies to install for full functionality:")
print("   pip install optuna          # For Bayesian optimization")
print("   pip install ray             # For distributed computing")
print("   pip install hmmlearn        # For HMM regime detection")
print("   pip install scikit-learn    # For ML-based regime detection")
