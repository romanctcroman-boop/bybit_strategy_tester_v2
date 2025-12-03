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
    OptimizationResult,
)

from .market_regime_detector import (
    MarketRegimeDetector,
    MarketRegime,
    RegimeDetectionResult,
    TechnicalIndicators,
)

from .drift_detector import (
    ModelDriftDetector,
    MultiModelDriftDetector,
    DriftEvent,
)

from .online_learner import OnlineLearner, ModelUpdateStats
from .training_scheduler import TrainingDecision, TrainingScheduler

__all__ = [
    # Quick Win #3
    "StrategyOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "MarketRegimeDetector",
    "MarketRegime",
    "RegimeDetectionResult",
    "TechnicalIndicators",
    "ModelDriftDetector",
    "MultiModelDriftDetector",
    "DriftEvent",
    "OnlineLearner",
    "ModelUpdateStats",
    "TrainingScheduler",
    "TrainingDecision",
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
