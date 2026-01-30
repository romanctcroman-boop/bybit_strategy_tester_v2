# 🔧 Strategy Builder - Implementation Roadmap

> **Document**: Missing Features & Implementation Plan
> **Version**: 1.0
> **Date**: 2025-01-29

---

## 📋 Overview

This document outlines the missing features for a complete Manual Mode (User-Driven) workflow in Strategy Builder, with implementation specifications.

---

## ❌ Gap Analysis

### Critical Missing Components

| Component                  | Description                                     | Priority | Effort |
| -------------------------- | ----------------------------------------------- | -------- | ------ |
| **Evaluation Criteria UI** | Select metrics, set constraints, define sorting | 🔴 P0    | Medium |
| **Optimization Config UI** | Parameter ranges, method selection, limits      | 🔴 P0    | Medium |
| **Results Viewer**         | Table, charts, comparison, export               | 🔴 P0    | High   |
| **Parameter Range Editor** | Visual sliders for optimization ranges          | 🟡 P1    | Medium |
| **Constraint Builder**     | Define metric constraints (max DD, min trades)  | 🟡 P1    | Low    |
| **Sensitivity Charts**     | Parameter sensitivity visualization             | 🟢 P2    | Medium |

---

## 🎯 Feature 1: Evaluation Criteria Panel

### Purpose

Allow users to configure which metrics to optimize and how to rank results.

### UI Location

Properties Panel (Right Sidebar) → New Section "📊 Evaluation Criteria"

### Wireframe

```
┌─────────────────────────────────────┐
│ 📊 Evaluation Criteria              │
├─────────────────────────────────────┤
│ Primary Metric                      │
│ ┌─────────────────────────────────┐ │
│ │ Sharpe Ratio              ▼     │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Secondary Metrics (for display)     │
│ ☑ Win Rate                         │
│ ☑ Max Drawdown                     │
│ ☑ Profit Factor                    │
│ ☐ Sortino Ratio                    │
│ ☐ Calmar Ratio                     │
│                                     │
│ Constraints                         │
│ ┌─────────────────────────────────┐ │
│ │ Max Drawdown    ≤   15   %      │ │
│ │ Min Trades      ≥   50          │ │
│ │ Min Win Rate    ≥   40   %      │ │
│ │ [+ Add Constraint]              │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Sort Results By                     │
│ 1. Sharpe Ratio ↓                  │
│ 2. Profit Factor ↓                 │
│ [+ Add Sort Level]                 │
└─────────────────────────────────────┘
```

### Data Model

```python
class EvaluationCriteria(BaseModel):
    """User-defined evaluation criteria"""

    primary_metric: str = Field(
        default="sharpe_ratio",
        description="Main metric to optimize"
    )

    secondary_metrics: List[str] = Field(
        default=["win_rate", "max_drawdown", "profit_factor"],
        description="Metrics to display in results"
    )

    constraints: List[MetricConstraint] = Field(
        default_factory=list,
        description="Hard constraints that must be satisfied"
    )

    sort_order: List[SortSpec] = Field(
        default_factory=list,
        description="Multi-level sorting for results"
    )


class MetricConstraint(BaseModel):
    """Single metric constraint"""

    metric: str                      # e.g., "max_drawdown"
    operator: str                    # "<=", ">=", "==", "!="
    value: float                     # threshold value


class SortSpec(BaseModel):
    """Single sort specification"""

    metric: str
    direction: str = "desc"          # "asc" or "desc"
```

### API Endpoint

```python
@router.post("/strategies/{strategy_id}/criteria")
async def set_evaluation_criteria(
    strategy_id: str,
    criteria: EvaluationCriteria,
    db: Session = Depends(get_db)
):
    """Set evaluation criteria for a strategy"""
    # Save to strategy.evaluation_criteria JSON field
    pass


@router.get("/strategies/{strategy_id}/criteria")
async def get_evaluation_criteria(
    strategy_id: str,
    db: Session = Depends(get_db)
) -> EvaluationCriteria:
    """Get evaluation criteria for a strategy"""
    pass
```

### Available Metrics

```python
AVAILABLE_METRICS = {
    # Performance
    "total_return": "Total Return %",
    "cagr": "CAGR %",
    "sharpe_ratio": "Sharpe Ratio",
    "sortino_ratio": "Sortino Ratio",
    "calmar_ratio": "Calmar Ratio",

    # Risk
    "max_drawdown": "Max Drawdown %",
    "avg_drawdown": "Avg Drawdown %",
    "volatility": "Volatility",
    "var_95": "VaR 95%",

    # Trade Quality
    "win_rate": "Win Rate %",
    "profit_factor": "Profit Factor",
    "avg_win": "Avg Win %",
    "avg_loss": "Avg Loss %",
    "expectancy": "Expectancy",

    # Activity
    "total_trades": "Total Trades",
    "avg_trade_duration": "Avg Trade Duration",
    "trades_per_month": "Trades/Month",
}
```

---

## 🎯 Feature 2: Optimization Configuration Panel

### Purpose

Allow users to configure optimization parameters, method, and data period.

### UI Location

Properties Panel (Right Sidebar) → New Section "⚙️ Optimization"

### Wireframe

```
┌─────────────────────────────────────┐
│ ⚙️ Optimization Settings            │
├─────────────────────────────────────┤
│ Method                              │
│ ┌─────────────────────────────────┐ │
│ │ ○ Grid Search (exhaustive)      │ │
│ │ ● Bayesian (recommended)        │ │
│ │ ○ Walk-Forward (robust)         │ │
│ │ ○ Random Search (fast)          │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Parameter Ranges                    │
│ ┌─────────────────────────────────┐ │
│ │ RSI Period                      │ │
│ │ [======●=====] 10 - 30 (step 2) │ │
│ │                                 │ │
│ │ RSI Overbought                  │ │
│ │ [========●===] 65 - 80 (step 5) │ │
│ │                                 │ │
│ │ RSI Oversold                    │ │
│ │ [===●========] 20 - 35 (step 5) │ │
│ │                                 │ │
│ │ [+ Add Parameter]               │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Data Period                         │
│ ┌─────────────────────────────────┐ │
│ │ Start: [2024-01-01] 📅          │ │
│ │ End:   [2025-01-01] 📅          │ │
│ │ Train/Test Split: [====●] 80%   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Limits                              │
│ ┌─────────────────────────────────┐ │
│ │ Max Trials:   [200]             │ │
│ │ Timeout (s):  [3600]            │ │
│ │ Workers:      [4]               │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [▶ Start Optimization]              │
└─────────────────────────────────────┘
```

### Data Model

```python
class OptimizationConfig(BaseModel):
    """User-defined optimization configuration"""

    method: str = Field(
        default="bayesian",
        description="Optimization method"
    )

    param_ranges: Dict[str, ParamRangeSpec] = Field(
        default_factory=dict,
        description="Parameter search space"
    )

    data_period: DataPeriod = Field(
        default_factory=DataPeriod,
        description="Backtest data period"
    )

    limits: OptimizationLimits = Field(
        default_factory=OptimizationLimits,
        description="Computational limits"
    )


class ParamRangeSpec(BaseModel):
    """Single parameter range"""

    param_path: str                  # e.g., "rsi.period"
    type: str                        # "int", "float", "categorical"
    low: Optional[float] = None
    high: Optional[float] = None
    step: Optional[float] = None
    values: Optional[List[Any]] = None


class DataPeriod(BaseModel):
    """Data period configuration"""

    start_date: str
    end_date: str
    train_split: float = 0.8

    # Walk-forward specific
    train_size: Optional[int] = None
    test_size: Optional[int] = None
    step_size: Optional[int] = None


class OptimizationLimits(BaseModel):
    """Computational limits"""

    max_trials: int = 200
    timeout_seconds: int = 3600
    workers: int = 4
```

### Auto-Detection of Parameters

```python
def detect_optimizable_parameters(graph: StrategyGraph) -> List[ParamRangeSpec]:
    """
    Auto-detect parameters from strategy graph that can be optimized.

    Rules:
    - Numeric parameters of indicators
    - Threshold values in conditions
    - Position size percentages
    - Stop loss / take profit values
    """
    optimizable = []

    for block_id, block in graph.blocks.items():
        block_def = BLOCK_DEFINITIONS.get(block.block_type, {})

        for param in block_def.get("parameters", []):
            if param["param_type"] in ("int", "float"):
                optimizable.append(ParamRangeSpec(
                    param_path=f"{block_id}.{param['name']}",
                    type=param["param_type"],
                    low=param.get("min_value"),
                    high=param.get("max_value"),
                    step=param.get("step", 1 if param["param_type"] == "int" else 0.01)
                ))

    return optimizable
```

---

## 🎯 Feature 3: Results Viewer

### Purpose

Display optimization results in a sortable, filterable table with visualization.

### UI Location

New page: `/frontend/optimization-results.html?optimization_id={id}`

### Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 📊 Optimization Results - RSI Strategy                         [Export CSV] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ Summary                                                                     │
│ ┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐    │
│ │ Total Runs  │ Best Sharpe │ Best Return │ Best WinRate│ Duration    │    │
│ │    156      │    2.34     │   45.6%     │    62%      │   12m 34s   │    │
│ └─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘    │
│                                                                             │
│ ┌─────────────────────────────────────┬─────────────────────────────────┐  │
│ │ Convergence Chart                   │ Parameter Sensitivity           │  │
│ │                                     │                                 │  │
│ │     ●                               │  RSI Period vs Sharpe           │  │
│ │    ●  ●●●●                          │  [scatter plot]                 │  │
│ │   ●      ●●●●●●●●●●                 │                                 │  │
│ │  ●            ●●●●●●●●●●●●●         │                                 │  │
│ │ ●───────────────────────▶           │                                 │  │
│ │ Trial                               │                                 │  │
│ └─────────────────────────────────────┴─────────────────────────────────┘  │
│                                                                             │
│ All Results                                              [Filter] [Sort]   │
│ ┌───────┬────────┬────────┬────────┬────────┬────────┬────────┬─────────┐ │
│ │ Rank  │ RSI    │ OB     │ OS     │ Sharpe │ Return │ Win %  │ Trades  │ │
│ │       │ Period │        │        │        │        │        │         │ │
│ ├───────┼────────┼────────┼────────┼────────┼────────┼────────┼─────────┤ │
│ │ 🥇 1  │   14   │   70   │   30   │  2.34  │ 45.6%  │  62%   │   87    │ │
│ │ 🥈 2  │   16   │   70   │   25   │  2.28  │ 43.2%  │  60%   │   92    │ │
│ │ 🥉 3  │   14   │   75   │   30   │  2.21  │ 41.8%  │  59%   │   85    │ │
│ │    4  │   12   │   70   │   30   │  2.15  │ 40.1%  │  58%   │   94    │ │
│ │    5  │   14   │   65   │   35   │  2.10  │ 38.7%  │  61%   │   79    │ │
│ │   ...                                                                  │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ [◀ Page 1 of 16 ▶]                                                         │
│                                                                             │
│ [Apply Best Parameters] [Run Secondary Backtest] [Compare Selected]        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### API Endpoints

```python
@router.get("/optimizations/{id}/results")
async def get_optimization_results(
    id: int,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "rank",
    sort_order: str = "asc",
    filters: Optional[str] = None,  # JSON encoded
    db: Session = Depends(get_db)
) -> OptimizationResultsResponse:
    """Get paginated, sorted, filtered optimization results"""
    pass


@router.get("/optimizations/{id}/charts/convergence")
async def get_convergence_data(id: int) -> List[Dict]:
    """Get convergence chart data (trial vs best score)"""
    pass


@router.get("/optimizations/{id}/charts/sensitivity/{param}")
async def get_sensitivity_data(id: int, param: str) -> List[Dict]:
    """Get parameter sensitivity data"""
    pass


@router.post("/optimizations/{id}/apply/{result_rank}")
async def apply_optimization_result(
    id: int,
    result_rank: int,
    strategy_id: str,
    db: Session = Depends(get_db)
):
    """Apply optimization result parameters to strategy"""
    pass
```

---

## 📁 File Structure for New Features

```
frontend/
├── strategy-builder.html          # Add new panel sections
├── optimization-results.html      # NEW: Results viewer page
├── css/
│   ├── strategy_builder.css       # Update for new panels
│   └── optimization_results.css   # NEW: Results page styling
├── js/
│   ├── pages/
│   │   ├── strategy_builder.js    # Add criteria & optimization logic
│   │   └── optimization_results.js # NEW: Results page logic
│   └── components/
│       ├── criteria_panel.js      # NEW: Evaluation criteria component
│       ├── optimization_panel.js  # NEW: Optimization config component
│       └── results_table.js       # NEW: Results table component

backend/
├── api/routers/
│   ├── strategy_builder.py        # Add criteria endpoints
│   └── optimizations.py           # Add results/charts endpoints
├── database/models/
│   └── strategy.py                # Add evaluation_criteria field
```

---

## 📝 Database Schema Updates

```python
# Add to Strategy model
class Strategy(Base):
    # ... existing fields ...

    # NEW: Evaluation criteria JSON
    evaluation_criteria = Column(JSON, nullable=True)

    # NEW: Default optimization config JSON
    optimization_config = Column(JSON, nullable=True)


# Add to Optimization model
class Optimization(Base):
    # ... existing fields ...

    # NEW: All results JSON array (for quick access)
    all_results = Column(JSON, nullable=True)

    # NEW: Charts data JSON
    convergence_data = Column(JSON, nullable=True)
    sensitivity_data = Column(JSON, nullable=True)
```

---

## 🔄 Migration Script

```python
"""Add evaluation and optimization fields to Strategy

Revision ID: add_eval_opt_fields
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


def upgrade():
    # Add evaluation_criteria to strategies
    op.add_column(
        'strategies',
        sa.Column('evaluation_criteria', JSON, nullable=True)
    )

    # Add optimization_config to strategies
    op.add_column(
        'strategies',
        sa.Column('optimization_config', JSON, nullable=True)
    )

    # Add all_results to optimizations
    op.add_column(
        'optimizations',
        sa.Column('all_results', JSON, nullable=True)
    )


def downgrade():
    op.drop_column('strategies', 'evaluation_criteria')
    op.drop_column('strategies', 'optimization_config')
    op.drop_column('optimizations', 'all_results')
```

---

## 📅 Implementation Timeline

| Week | Task                      | Deliverable               |
| ---- | ------------------------- | ------------------------- |
| 1    | Evaluation Criteria Panel | UI + API + DB             |
| 2    | Optimization Config Panel | UI + API                  |
| 3    | Results Viewer Page       | Table + Pagination        |
| 4    | Charts & Visualization    | Convergence + Sensitivity |
| 5    | Integration & Testing     | E2E tests                 |

---

## ✅ Acceptance Criteria

### Evaluation Criteria Panel

- [ ] User can select primary metric from dropdown
- [ ] User can check/uncheck secondary metrics
- [ ] User can add/remove constraints
- [ ] User can set multi-level sort order
- [ ] Criteria saved to database
- [ ] Criteria loaded on strategy open

### Optimization Config Panel

- [ ] User can select optimization method
- [ ] User can configure parameter ranges with sliders
- [ ] User can set data period with date pickers
- [ ] User can set computational limits
- [ ] Config saved to database
- [ ] "Start Optimization" launches job

### Results Viewer

- [ ] Table shows all optimization runs
- [ ] Table is sortable by any column
- [ ] Table is filterable by constraints
- [ ] Pagination works correctly
- [ ] Convergence chart displays correctly
- [ ] Sensitivity chart displays correctly
- [ ] "Apply Best Parameters" updates strategy
- [ ] Export to CSV works

---

_Document created: 2025-01-29_
_Status: Ready for implementation_
