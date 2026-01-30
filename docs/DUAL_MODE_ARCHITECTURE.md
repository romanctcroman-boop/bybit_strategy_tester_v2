# 🔄 Dual-Mode Architecture: Manual & AI-Assisted

> **Document**: Unified Strategy Builder Platform Architecture
> **Version**: 1.0
> **Date**: 2025-01-29

---

## 📋 Executive Summary

Strategy Builder serves as the **unified platform** for both:

1. **Manual Mode (User-Driven)**: User creates strategies, sets criteria, runs optimization
2. **AI-Assisted Mode**: AI agents use same platform to build and optimize strategies

Both modes share the same:

- Block system (nodes)
- Connection graph
- Validation engine
- Code generation
- Backtest infrastructure
- Optimization pipeline

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STRATEGY BUILDER PLATFORM                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────┐     ┌─────────────────────────────┐       │
│  │     MANUAL MODE (User)      │     │   AI-ASSISTED MODE (Agent)  │       │
│  ├─────────────────────────────┤     ├─────────────────────────────┤       │
│  │ • Visual Canvas (drag/drop) │     │ • Natural Language Input    │       │
│  │ • Block Library Browser     │     │ • Perplexity Research       │       │
│  │ • Properties Panel          │     │ • DeepSeek Code Generation  │       │
│  │ • Manual Parameter Tuning   │     │ • Multi-Agent Consensus     │       │
│  │ • Criteria Selection UI     │     │ • Auto-Optimization         │       │
│  └──────────────┬──────────────┘     └──────────────┬──────────────┘       │
│                 │                                    │                      │
│                 ▼                                    ▼                      │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                  SHARED STRATEGY GRAPH                           │       │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐       │       │
│  │  │ Candle  │───▶│   RSI   │───▶│ Compare │───▶│   Buy   │       │       │
│  │  │  Data   │    │         │    │  < 30   │    │ Signal  │       │       │
│  │  └─────────┘    └─────────┘    └─────────┘    └─────────┘       │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                 ┌──────────────────┴──────────────────┐                    │
│                 ▼                                      ▼                    │
│  ┌─────────────────────────────┐     ┌─────────────────────────────┐       │
│  │      VALIDATION ENGINE      │     │     CODE GENERATOR          │       │
│  │  • Graph integrity          │     │  • Python strategy code     │       │
│  │  • Type checking            │     │  • Include indicators       │       │
│  │  • Cycle detection          │     │  • Async/sync modes         │       │
│  │  • Backtest compatibility   │     │  • Comments & logging       │       │
│  └──────────────┬──────────────┘     └──────────────┬──────────────┘       │
│                 │                                    │                      │
│                 ▼                                    ▼                      │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    BACKTEST ENGINE                               │       │
│  │  • FallbackEngineV2/V3/V4                                       │       │
│  │  • NumbaV2 (fast optimization)                                  │       │
│  │  • GPU support                                                  │       │
│  │  • 166 metrics calculation                                      │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                  OPTIMIZATION PIPELINE                           │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │       │
│  │  │   Grid   │ │  Random  │ │ Bayesian │ │Walk-Fwd  │            │       │
│  │  │  Search  │ │  Search  │ │   TPE    │ │ Analysis │            │       │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    ML ANALYSIS LAYER                             │       │
│  │  • Concept Drift Detection                                      │       │
│  │  • Regime Classification                                        │       │
│  │  • Overfitting Detection                                        │       │
│  │  • Meta-Learning Recommendations                                │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎛️ Mode Comparison

| Feature                | Manual Mode (User)        | AI-Assisted Mode (Agent)      |
| ---------------------- | ------------------------- | ----------------------------- |
| **Entry Point**        | Visual Canvas UI          | Natural Language / API        |
| **Block Selection**    | Browse library, drag/drop | AI selects based on analysis  |
| **Parameter Tuning**   | Manual input fields       | AI suggests optimal ranges    |
| **Connection Logic**   | User draws connections    | AI generates graph structure  |
| **Validation**         | User clicks "Validate"    | Auto-validation on generation |
| **Criteria Selection** | UI dropdown/checkboxes    | AI determines based on goals  |
| **Optimization**       | User configures ranges    | AI determines search space    |
| **Analysis**           | User interprets results   | AI explains & recommends      |

---

## 🔧 Manual Mode (User-Driven) Workflow

### Phase 1: Strategy Creation

```
User Actions:
1. Open Strategy Builder canvas
2. Browse block library
3. Drag blocks to canvas:
   - Candle Data
   - Indicator (RSI, MACD, etc.)
   - Condition (Compare, Cross)
   - Action (Buy, Sell)
4. Connect block ports
5. Configure parameters
6. Set market type (SPOT/Futures)
7. Set direction (Long/Short/Both)
```

### Phase 2: Evaluation Criteria

```
User Configures:
1. Primary metric (Sharpe, Sortino, Total Return)
2. Secondary metrics (Win Rate, Max DD, Profit Factor)
3. Constraints:
   - Maximum drawdown limit
   - Minimum trade count
   - Maximum trade duration
4. Sorting preferences (multi-metric)
```

**Required UI Components:**

```javascript
// Evaluation Criteria Panel
{
  primaryMetric: "sharpe_ratio",      // Main optimization target
  secondaryMetrics: [                 // Display & filter
    "win_rate",
    "max_drawdown",
    "profit_factor"
  ],
  constraints: {
    max_drawdown: 0.15,               // Max 15% drawdown
    min_trades: 50,                   // Minimum trades
    min_win_rate: 0.4                 // Minimum 40% win rate
  },
  sortOrder: [                        // Multi-metric sort
    { metric: "sharpe_ratio", direction: "desc" },
    { metric: "profit_factor", direction: "desc" }
  ]
}
```

### Phase 3: Optimization Configuration

```
User Configures:
1. Select optimization method:
   - Grid Search (exhaustive)
   - Bayesian (smart)
   - Walk-Forward (robust)
2. Define parameter ranges:
   - RSI period: 10-30, step=2
   - Overbought: 65-80, step=5
   - Oversold: 20-35, step=5
3. Set data period:
   - Start date
   - End date
   - Train/test split
4. Set computational limits:
   - Max trials
   - Timeout
   - Parallel workers
```

**Required UI Components:**

```javascript
// Optimization Configuration Panel
{
  method: "bayesian",

  paramRanges: {
    "rsi.period": {
      type: "int",
      low: 10,
      high: 30,
      step: 2
    },
    "rsi.overbought": {
      type: "int",
      low: 65,
      high: 80,
      step: 5
    },
    "rsi.oversold": {
      type: "int",
      low: 20,
      high: 35,
      step: 5
    }
  },

  dataPeriod: {
    start: "2024-01-01",
    end: "2025-01-01",
    trainSplit: 0.8
  },

  limits: {
    maxTrials: 200,
    timeout: 3600,
    workers: 4
  }
}
```

### Phase 4: Run & Analyze

```
User Actions:
1. Click "Start Optimization"
2. Monitor progress (real-time)
3. View results table:
   - Parameter combinations
   - Metric values
   - Rank by criteria
4. Select best result
5. Apply to strategy
6. Run final backtest
7. Save strategy version
```

---

## 🤖 AI-Assisted Mode Workflow

### Phase 1: User Input

```
User Provides:
- Natural language description:
  "Create a mean reversion strategy for BTC
   using RSI oversold conditions with
   reasonable risk management"
- Or selects from AI suggestions
```

### Phase 2: AI Research (Perplexity)

```
Agent Actions:
1. Analyze user request
2. Research via Perplexity:
   - Similar strategies
   - Market conditions
   - Best practices
3. Generate strategy concept
```

### Phase 3: Multi-Agent Consensus

```
Agent Actions:
1. Primary agent generates proposal
2. Secondary agents review:
   - Risk assessment
   - Backtesting viability
   - Market fit analysis
3. Consensus reached
4. Confidence score calculated
```

### Phase 4: Strategy Generation (DeepSeek)

```
Agent Actions:
1. DeepSeek generates Strategy Builder graph
2. Graph validated automatically
3. Code generated
4. Initial backtest run
```

### Phase 5: AI Optimization

```
Agent Actions:
1. Auto-detect optimizable parameters
2. Determine search space from:
   - Historical performance
   - Market regime analysis
   - Risk constraints
3. Run optimization
4. Apply best parameters
```

### Phase 6: Human Review

```
User Actions:
1. Review AI-generated strategy
2. Modify if needed (using Manual Mode UI)
3. Approve for live/paper trading
```

---

## 📦 API Design for Both Modes

### Unified Strategy Graph Schema

```python
class StrategyGraph:
    """Same structure used by both Manual and AI modes"""

    id: str                          # Unique identifier
    name: str                        # Strategy name
    description: str                 # Description

    # Graph structure
    blocks: Dict[str, StrategyBlock] # All blocks
    connections: List[BlockConnection] # All connections

    # Settings
    timeframe: str                   # Default timeframe
    symbols: List[str]               # Target symbols
    market_type: str                 # spot/linear
    direction: str                   # long/short/both

    # Metadata
    created_by: str                  # "user" or "ai_agent"
    source_agent: Optional[str]      # Agent ID if AI-created
    version: int                     # Version number
    created_at: datetime
    updated_at: datetime
```

### Manual Mode API Calls

```python
# User creates strategy
POST /api/v1/strategy-builder/strategies
{
  "name": "My RSI Strategy",
  "blocks": [...],
  "connections": [...],
  "created_by": "user"
}

# User configures evaluation criteria
POST /api/v1/strategy-builder/strategies/{id}/criteria
{
  "primary_metric": "sharpe_ratio",
  "constraints": {...}
}

# User configures optimization
POST /api/v1/optimizations/
{
  "strategy_id": 123,
  "optimization_type": "bayesian",
  "param_ranges": {...},
  "metric": "sharpe_ratio"
}
```

### AI Mode API Calls

```python
# AI submits strategy
POST /api/v1/strategy-builder/strategies
{
  "name": "AI Mean Reversion v1",
  "blocks": [...],
  "connections": [...],
  "created_by": "ai_agent",
  "source_agent": "deepseek_strategist",
  "agent_reasoning": "..."
}

# AI requests optimization (same endpoint!)
POST /api/v1/optimizations/
{
  "strategy_id": 456,
  "optimization_type": "bayesian",
  "param_ranges": {...},  # AI-determined ranges
  "metric": "sharpe_ratio"
}
```

---

## 🎯 Feature Requirements Summary

### For Manual Mode (User-Driven)

| Feature                      | Priority | Status     |
| ---------------------------- | -------- | ---------- |
| Block Library Browser        | HIGH     | ✅ Done    |
| Visual Canvas Editor         | HIGH     | ✅ Done    |
| Parameter Configuration      | HIGH     | ✅ Done    |
| **Evaluation Criteria UI**   | HIGH     | ❌ Missing |
| **Optimization Config UI**   | HIGH     | ❌ Missing |
| **Results Comparison View**  | HIGH     | ❌ Missing |
| Multi-metric Sorting         | MEDIUM   | ❌ Missing |
| Parameter Sensitivity Charts | MEDIUM   | ❌ Missing |
| Strategy Templates Library   | MEDIUM   | ⚠️ Partial |
| Version Comparison           | LOW      | ⚠️ Basic   |

### For AI-Assisted Mode

| Feature                   | Priority | Status     |
| ------------------------- | -------- | ---------- |
| Perplexity Integration    | HIGH     | ✅ Done    |
| DeepSeek Integration      | HIGH     | ✅ Done    |
| Multi-Agent Consensus     | HIGH     | ✅ Done    |
| Strategy Graph Generation | HIGH     | ✅ Done    |
| Auto Parameter Detection  | MEDIUM   | ❌ Missing |
| Regime-Aware Optimization | MEDIUM   | ⚠️ Partial |
| Human Review Interface    | MEDIUM   | ❌ Missing |
| Explanation Generation    | LOW      | ⚠️ Basic   |

---

## 🛠️ Implementation Plan

### Phase 1: Manual Mode Enhancements (Priority)

1. **Evaluation Criteria Panel**
    - Add UI in Properties sidebar
    - Metric selection dropdown
    - Constraint configuration
    - Multi-metric sorting

2. **Optimization Configuration Panel**
    - Parameter range sliders
    - Method selection
    - Data period picker
    - Limit configuration

3. **Results Viewer**
    - Table with all runs
    - Charts (convergence, sensitivity)
    - Filter/sort by metrics
    - Export functionality

### Phase 2: AI Mode Integration

1. **AI Strategy Editor**
    - Natural language input
    - Preview AI-generated graph
    - Edit before saving

2. **Auto-Optimization**
    - Detect parameters from graph
    - Suggest optimal ranges
    - Run with single click

3. **Human Review Flow**
    - AI explanation panel
    - Approve/reject/modify
    - Feedback for RLHF

---

## 📝 Conclusion

Strategy Builder is the **common ground** for both user-driven and AI-assisted trading strategy development. The unified architecture ensures:

1. **Consistency**: Same blocks, validation, and backtest for both modes
2. **Flexibility**: Users can switch between manual and AI assistance
3. **Transparency**: AI-generated strategies are fully editable
4. **Collaboration**: Users can start manually, then ask AI to optimize

**Next Steps**:

1. Build Evaluation Criteria UI
2. Build Optimization Config UI
3. Build Results Comparison View
4. Enhance AI → Strategy Builder integration

---

_Document created: 2025-01-29_
_Author: AI Agent (Audit Session)_
