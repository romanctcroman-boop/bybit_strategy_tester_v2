"""
Risk Management Module.

Comprehensive risk management for live trading:
- Position sizing (Kelly, fixed %, volatility-based)
- Stop loss management (trailing, breakeven, time-based)
- Exposure control (max position, correlation, leverage)
- Pre-trade validation
- Unified risk engine
"""

from backend.services.risk_management.exposure_controller import (
    ExposureController,
    ExposureLimits,
    ExposureViolationType,
    Position,
)
from backend.services.risk_management.position_sizing import (
    PositionSizer,
    SizingMethod,
    SizingResult,
    TradingStats,
)
from backend.services.risk_management.risk_engine import (
    PortfolioRiskSnapshot,
    RiskAssessment,
    RiskEngine,
    RiskEngineConfig,
    RiskLevel,
    create_aggressive_risk_engine,
    create_conservative_risk_engine,
    create_moderate_risk_engine,
)
from backend.services.risk_management.stop_loss_manager import (
    StopLossConfig,
    StopLossManager,
    StopLossOrder,
    StopLossState,
    StopLossType,
)
from backend.services.risk_management.trade_validator import (
    AccountState,
    RejectionReason,
    TradeRequest,
    TradeValidator,
    TradeValidatorBuilder,
    ValidationConfig,
    ValidationReport,
    ValidationResult,
    create_aggressive_validator,
    create_conservative_validator,
    create_moderate_validator,
)

__all__ = [
    # Position Sizing
    "PositionSizer",
    "SizingMethod",
    "SizingResult",
    "TradingStats",
    # Stop Loss
    "StopLossManager",
    "StopLossConfig",
    "StopLossType",
    "StopLossOrder",
    "StopLossState",
    # Exposure
    "ExposureController",
    "ExposureLimits",
    "ExposureViolationType",
    "Position",
    # Validation
    "TradeValidator",
    "TradeValidatorBuilder",
    "TradeRequest",
    "ValidationReport",
    "ValidationResult",
    "ValidationConfig",
    "AccountState",
    "RejectionReason",
    "create_conservative_validator",
    "create_moderate_validator",
    "create_aggressive_validator",
    # Risk Engine
    "RiskEngine",
    "RiskEngineConfig",
    "RiskLevel",
    "RiskAssessment",
    "PortfolioRiskSnapshot",
    "create_conservative_risk_engine",
    "create_moderate_risk_engine",
    "create_aggressive_risk_engine",
]
