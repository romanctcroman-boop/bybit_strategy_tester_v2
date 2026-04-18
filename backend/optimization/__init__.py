"""
Backend Optimization Module.

Extracted from the monolithic optimizations.py router into focused modules:
- models.py: Pydantic request/response models
- scoring.py: Composite score calculation, multi-criteria ranking
- filters.py: Static and dynamic constraint filtering
- recommendations.py: Smart recommendation generation
- utils.py: DRY helpers (BacktestInput builder, train/test split, timeout, early stopping)
- workers.py: Multiprocessing batch worker
- builder_optimizer.py: Node-based Strategy Builder optimization
"""

from .builder_optimizer import (
    clone_graph_with_params,
    extract_optimizable_params,
    generate_builder_param_combinations,
    run_builder_backtest,
    run_builder_grid_search,
    run_builder_optuna_search,
)
from .filters import passes_dynamic_constraints, passes_filters
from .models import (
    OptimizationResult,
    OptunaSyncRequest,
    SmartRecommendation,
    SmartRecommendations,
    SyncOptimizationRequest,
    SyncOptimizationResponse,
    VectorbtOptimizationRequest,
    VectorbtOptimizationResponse,
)
from .optuna_optimizer import (
    OPTUNA_AVAILABLE,
    OptunaOptimizationResult,
    OptunaOptimizer,
    TradingStrategyOptimizer,
    create_full_strategy_param_space,
    create_rsi_param_space,
    create_sltp_param_space,
)
from .overfit_guards import (
    GuardResult,
    GuardThresholds,
    evaluate_overfit_guards,
    thresholds_from_config,
)
from .post_grid import build_refinement_grid, refine_top_k
from .ray_optimizer import (
    RAY_AVAILABLE,
    MultiprocessingOptimizer,
    ParallelOptimizationResult,
    RayParallelOptimizer,
    get_parallel_optimizer,
)
from .recommendations import generate_smart_recommendations
from .sampler_factory import (
    SamplerRecommendation,
    pick_sampler,
    prefer_for_high_dim,
    recommend,
    recommend_n_startup,
    recommend_n_trials,
)
from .scoring import apply_custom_sort_order, calculate_composite_score, rank_by_multi_criteria
from .utils import (
    EarlyStopper,
    TimeoutChecker,
    build_backtest_input,
    combo_to_params,
    extract_metrics_from_output,
    generate_param_combinations,
    parse_trade_direction,
    serialize_equity_curve,
    serialize_trades,
    split_candles,
)
from .walk_forward import FoldSpec, build_folds, wrap_walk_forward

__all__ = [
    "OPTUNA_AVAILABLE",
    "RAY_AVAILABLE",
    "EarlyStopper",
    "FoldSpec",
    "GuardResult",
    "GuardThresholds",
    "MultiprocessingOptimizer",
    "OptimizationResult",
    "OptunaOptimizationResult",
    "OptunaOptimizer",
    "OptunaSyncRequest",
    "ParallelOptimizationResult",
    "RayParallelOptimizer",
    "SamplerRecommendation",
    "SmartRecommendation",
    "SmartRecommendations",
    "SyncOptimizationRequest",
    "SyncOptimizationResponse",
    "TimeoutChecker",
    "TradingStrategyOptimizer",
    "VectorbtOptimizationRequest",
    "VectorbtOptimizationResponse",
    "apply_custom_sort_order",
    "build_backtest_input",
    "build_folds",
    "build_refinement_grid",
    "calculate_composite_score",
    "clone_graph_with_params",
    "combo_to_params",
    "create_full_strategy_param_space",
    "create_rsi_param_space",
    "create_sltp_param_space",
    "evaluate_overfit_guards",
    "extract_metrics_from_output",
    "extract_optimizable_params",
    "generate_builder_param_combinations",
    "generate_param_combinations",
    "generate_smart_recommendations",
    "get_parallel_optimizer",
    "parse_trade_direction",
    "passes_dynamic_constraints",
    "passes_filters",
    "pick_sampler",
    "prefer_for_high_dim",
    "rank_by_multi_criteria",
    "recommend",
    "recommend_n_startup",
    "recommend_n_trials",
    "refine_top_k",
    "run_builder_backtest",
    "run_builder_grid_search",
    "run_builder_optuna_search",
    "serialize_equity_curve",
    "serialize_trades",
    "split_candles",
    "thresholds_from_config",
    "wrap_walk_forward",
]
