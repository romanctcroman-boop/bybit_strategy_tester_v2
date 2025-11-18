"""
ML-модуль для автоматизированной оптимизации торговых стратегий
Использует CatBoost, XGBoost, LightGBM для поиска оптимальных параметров

Quick Win #3: Tournament + ML Integration
Added: Optuna optimizer, Market Regime Detector
"""

# Legacy optimizers
try:
    from .optimizer import (
        MLOptimizer,
        CatBoostOptimizer,
        XGBoostOptimizer,
        LightGBMOptimizer,
        HybridOptimizer,
        OptimizationResult as LegacyOptimizationResult,
    )
    LEGACY_OPTIMIZERS_AVAILABLE = True
except ImportError:
    LEGACY_OPTIMIZERS_AVAILABLE = False

# Quick Win #3: New components
from .optuna_optimizer import (
    StrategyOptimizer,
    OptimizationConfig,
    OptimizationResult
)

from .market_regime_detector import (
    MarketRegimeDetector,
    MarketRegime,
    RegimeDetectionResult,
    TechnicalIndicators
)

__all__ = [
    # Quick Win #3
    "StrategyOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "MarketRegimeDetector",
    "MarketRegime",
    "RegimeDetectionResult",
    "TechnicalIndicators",
]

# Add legacy if available
if LEGACY_OPTIMIZERS_AVAILABLE:
    __all__.extend([
        'MLOptimizer',
        'CatBoostOptimizer', 
        'XGBoostOptimizer',
        'LightGBMOptimizer',
        'HybridOptimizer',
        'LegacyOptimizationResult',
    ])
