# 🏗️ Strategy Builder Architecture

## Bybit Strategy Tester v2 - Visual Strategy Builder

> **Version**: 1.0.0  
> **Last Updated**: 2026-01-29  
> **Status**: Implementation Phase

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Models](#data-models)
4. [REST API Contract](#rest-api-contract)
5. [Frontend-Backend Integration](#frontend-backend-integration)
6. [Code Generation & Execution](#code-generation--execution)
7. [Backtest Integration](#backtest-integration)
8. [AI Agent Integration](#ai-agent-integration)
9. [Implementation Plan](#implementation-plan)

---

## Overview

Strategy Builder is a **visual, block-based strategy composition system** that allows users to:

- **Drag-and-drop** blocks (indicators, conditions, actions) onto a canvas
- **Connect blocks** via ports to create trading logic
- **Generate Python code** automatically from visual graphs
- **Run backtests** directly from the builder
- **Save/load strategies** to/from database
- **Use templates** for quick strategy creation

### Key Features

- ✅ Visual block-based editor (drag & drop)
- ✅ Real-time validation
- ✅ Code generation (Python)
- ✅ Template library
- ✅ Integration with backtesting engines
- ✅ Database persistence
- ✅ Version control
- ✅ AI agent support (DeepSeek, Perplexity)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                 │
│  strategy-builder.html + strategy_builder.js                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Block Library│  │   Canvas    │  │  Properties  │         │
│  │  (Sidebar)   │  │  (Graph)    │  │   Panel      │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ REST API (JSON)
┌─────────────────────────────▼───────────────────────────────────┐
│                    FASTAPI BACKEND                              │
│  /api/v1/strategy-builder/*                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Strategy Builder Router                                │   │
│  │  - CRUD strategies                                       │   │
│  │  - Block operations                                      │   │
│  │  - Connection management                                 │   │
│  │  - Validation                                            │   │
│  │  - Code generation                                       │   │
│  │  - Template management                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  Strategy Builder Services                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ StrategyGraph│  │ CodeGenerator│  │ Validator   │   │   │
│  │  │   Builder    │  │              │  │             │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  Database Integration                                   │   │
│  │  ┌──────────────┐  ┌──────────────┐                    │   │
│  │  │  Strategy    │  │  Backtest    │                    │   │
│  │  │   Model      │  │   Model      │                    │   │
│  │  └──────────────┘  └──────────────┘                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  Backtesting Integration                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ Engine       │  │ Strategy     │  │ Metrics      │   │   │
│  │  │ Selector     │  │ Adapter      │  │ Calculator   │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

---

## Data Models

### Strategy Graph JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "name", "blocks", "connections"],
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique strategy ID (UUID)"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100,
      "description": "Strategy name"
    },
    "description": {
      "type": "string",
      "maxLength": 1000,
      "description": "Strategy description"
    },
    "timeframe": {
      "type": "string",
      "pattern": "^(1m|3m|5m|15m|30m|1h|2h|4h|6h|12h|1d|1w|1M)$",
      "description": "Trading timeframe"
    },
    "symbol": {
      "type": "string",
      "pattern": "^[A-Z]{2,10}USDT$",
      "description": "Trading symbol (e.g., BTCUSDT)"
    },
    "market_type": {
      "type": "string",
      "enum": ["spot", "linear"],
      "description": "SPOT = TradingView parity, LINEAR = perpetual futures"
    },
    "direction": {
      "type": "string",
      "enum": ["long", "short", "both"],
      "description": "Allowed trading directions"
    },
    "initial_capital": {
      "type": "number",
      "minimum": 100,
      "maximum": 100000000,
      "default": 10000,
      "description": "Initial capital for backtesting"
    },
    "blocks": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/Block"
      },
      "description": "Array of strategy blocks"
    },
    "connections": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/Connection"
      },
      "description": "Array of connections between blocks"
    },
    "metadata": {
      "type": "object",
      "properties": {
        "created_at": {
          "type": "string",
          "format": "date-time"
        },
        "updated_at": {
          "type": "string",
          "format": "date-time"
        },
        "version": {
          "type": "integer",
          "minimum": 1,
          "default": 1
        },
        "author": {
          "type": "string"
        },
        "tags": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    }
  },
  "definitions": {
    "Block": {
      "type": "object",
      "required": ["id", "type", "category", "name"],
      "properties": {
        "id": {
          "type": "string",
          "description": "Unique block ID"
        },
        "type": {
          "type": "string",
          "description": "Block type identifier (e.g., 'rsi', 'crossover', 'buy')"
        },
        "category": {
          "type": "string",
          "enum": ["indicator", "condition", "action", "logic", "input", "strategy"],
          "description": "Block category"
        },
        "name": {
          "type": "string",
          "description": "Human-readable block name"
        },
        "icon": {
          "type": "string",
          "description": "Bootstrap icon name (e.g., 'graph-up')"
        },
        "x": {
          "type": "number",
          "description": "X position on canvas"
        },
        "y": {
          "type": "number",
          "description": "Y position on canvas"
        },
        "params": {
          "type": "object",
          "description": "Block-specific parameters",
          "additionalProperties": true
        },
        "isMain": {
          "type": "boolean",
          "default": false,
          "description": "True for main Strategy node (cannot be deleted)"
        }
      }
    },
    "Connection": {
      "type": "object",
      "required": ["id", "source", "target"],
      "properties": {
        "id": {
          "type": "string",
          "description": "Unique connection ID"
        },
        "source": {
          "type": "object",
          "required": ["blockId", "portId"],
          "properties": {
            "blockId": {
              "type": "string",
              "description": "Source block ID"
            },
            "portId": {
              "type": "string",
              "description": "Source port ID"
            }
          }
        },
        "target": {
          "type": "object",
          "required": ["blockId", "portId"],
          "properties": {
            "blockId": {
              "type": "string",
              "description": "Target block ID"
            },
            "portId": {
              "type": "string",
              "description": "Target port ID"
            }
          }
        },
        "type": {
          "type": "string",
          "enum": ["data", "condition", "flow"],
          "description": "Connection type (data flow, condition, execution flow)"
        }
      }
    }
  }
}
```

### Block Types Reference

#### Indicators
- `rsi` - Relative Strength Index
- `macd` - Moving Average Convergence Divergence
- `ema` - Exponential Moving Average
- `sma` - Simple Moving Average
- `bollinger` - Bollinger Bands
- `atr` - Average True Range
- `stochastic` - Stochastic Oscillator
- `adx` - Average Directional Index

#### Conditions
- `crossover` - Value A crosses above B
- `crossunder` - Value A crosses below B
- `greater_than` - A > B
- `less_than` - A < B
- `equals` - A == B
- `between` - Value in range [min, max]

#### Actions
- `buy` - Open long position
- `sell` - Open short position
- `close` - Close current position
- `stop_loss` - Set stop loss level
- `take_profit` - Set take profit level
- `trailing_stop` - Set trailing stop

#### Logic
- `and` - Logical AND
- `or` - Logical OR
- `not` - Logical NOT
- `delay` - Wait N bars
- `filter` - Filter signals

#### Inputs
- `price` - OHLCV price data
- `volume` - Trading volume
- `constant` - Fixed numeric value
- `timeframe` - Chart timeframe

#### Strategy Node
- `strategy` - Main strategy node (receives entry/exit signals)
  - Input ports: `entry_long`, `exit_long`, `entry_short`, `exit_short`
  - Cannot be deleted

### Port Types

- **data** - Numeric/array data flow (e.g., indicator values)
- **condition** - Boolean condition (true/false)
- **flow** - Execution flow (for actions)

---

## REST API Contract

### Base URL
```
/api/v1/strategy-builder
```

### Endpoints

#### Strategy CRUD

##### Create Strategy
```http
POST /api/v1/strategy-builder/strategies
Content-Type: application/json

{
  "name": "My RSI Strategy",
  "description": "RSI oversold/overbought strategy",
  "timeframe": "1h",
  "symbol": "BTCUSDT",
  "market_type": "linear",
  "direction": "both",
  "initial_capital": 10000
}
```

**Response:**
```json
{
  "id": "strategy_abc123",
  "name": "My RSI Strategy",
  "description": "RSI oversold/overbought strategy",
  "timeframe": "1h",
  "symbol": "BTCUSDT",
  "market_type": "linear",
  "direction": "both",
  "initial_capital": 10000,
  "blocks": [],
  "connections": [],
  "version": 1,
  "created_at": "2026-01-29T10:00:00Z",
  "updated_at": "2026-01-29T10:00:00Z"
}
```

##### Get Strategy
```http
GET /api/v1/strategy-builder/strategies/{strategy_id}
```

##### Update Strategy
```http
PUT /api/v1/strategy-builder/strategies/{strategy_id}
Content-Type: application/json

{
  "name": "Updated Strategy Name",
  "blocks": [...],
  "connections": [...]
}
```

##### Delete Strategy
```http
DELETE /api/v1/strategy-builder/strategies/{strategy_id}
```

##### List Strategies
```http
GET /api/v1/strategy-builder/strategies?page=1&page_size=20
```

#### Block Operations

##### Add Block
```http
POST /api/v1/strategy-builder/blocks
Content-Type: application/json

{
  "strategy_id": "strategy_abc123",
  "block_type": "rsi",
  "x": 100,
  "y": 200,
  "parameters": {
    "period": 14,
    "overbought": 70,
    "oversold": 30
  }
}
```

##### Update Block
```http
PUT /api/v1/strategy-builder/blocks
Content-Type: application/json

{
  "strategy_id": "strategy_abc123",
  "block_id": "block_xyz789",
  "parameters": {
    "period": 21
  },
  "position_x": 150,
  "position_y": 250
}
```

##### Delete Block
```http
DELETE /api/v1/strategy-builder/blocks/{strategy_id}/{block_id}
```

#### Connection Operations

##### Create Connection
```http
POST /api/v1/strategy-builder/connections
Content-Type: application/json

{
  "strategy_id": "strategy_abc123",
  "source_block_id": "block_rsi",
  "source_output": "value",
  "target_block_id": "block_less_than",
  "target_input": "a"
}
```

##### Delete Connection
```http
DELETE /api/v1/strategy-builder/connections/{strategy_id}/{connection_id}
```

#### Validation

##### Validate Strategy
```http
POST /api/v1/strategy-builder/validate/{strategy_id}?mode=standard
```

**Response:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    {
      "type": "missing_entry_signals",
      "message": "Strategy has no entry signals connected to main node",
      "block_id": "main_strategy"
    }
  ],
  "complexity_score": 5.2,
  "estimated_lookback": 50
}
```

**Validation Modes:**
- `standard` - Basic validation (default)
- `backtest` - Validation for backtesting
- `live` - Validation for live trading

#### Code Generation

##### Generate Code
```http
POST /api/v1/strategy-builder/generate
Content-Type: application/json

{
  "strategy_id": "strategy_abc123",
  "template": "backtest",
  "include_comments": true,
  "include_logging": true
}
```

**Response:**
```json
{
  "success": true,
  "code": "def generate_signals(ohlcv):\n    ...",
  "strategy_name": "My RSI Strategy",
  "strategy_id": "strategy_abc123",
  "version": "1.0.0",
  "dependencies": ["pandas", "numpy", "vectorbt"],
  "errors": [],
  "warnings": []
}
```

**Templates:**
- `basic` - Basic strategy code
- `backtest` - Backtest-ready code (default)
- `live` - Live trading code
- `optimization` - Optimization-ready code

#### Templates

##### List Templates
```http
GET /api/v1/strategy-builder/templates?category=trend_following
```

##### Get Template
```http
GET /api/v1/strategy-builder/templates/{template_id}
```

##### Instantiate Template
```http
POST /api/v1/strategy-builder/templates/instantiate
Content-Type: application/json

{
  "template_id": "rsi_oversold",
  "name": "My RSI Strategy",
  "symbols": ["BTCUSDT"],
  "timeframe": "1h"
}
```

#### Backtest Integration

##### Run Backtest from Strategy Builder
```http
POST /api/v1/strategy-builder/strategies/{strategy_id}/backtest
Content-Type: application/json

{
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-12-31T23:59:59Z",
  "engine": "fallback_v4",
  "commission": 0.0007,
  "slippage": 0.0005,
  "leverage": 10,
  "pyramiding": 1,
  "stop_loss": 0.02,
  "take_profit": 0.03
}
```

**Response:**
```json
{
  "backtest_id": "backtest_xyz789",
  "strategy_id": "strategy_abc123",
  "status": "completed",
  "results": {
    "total_return": 0.15,
    "sharpe_ratio": 1.2,
    "win_rate": 0.55,
    "total_trades": 120
  },
  "redirect_url": "/frontend/backtest-results.html?backtest_id=backtest_xyz789"
}
```

---

## Frontend-Backend Integration

### Frontend State Management

The frontend (`strategy_builder.js`) maintains:

```javascript
let strategyBlocks = [];      // Array of block objects
const connections = [];        // Array of connection objects
let selectedBlockId = null;   // Currently selected block
let zoom = 1;                 // Canvas zoom level
```

### Save Strategy Flow

```javascript
async function saveStrategy() {
  const strategy = {
    name: document.getElementById("strategyName").value,
    timeframe: document.getElementById("strategyTimeframe").value,
    symbol: document.getElementById("strategySymbol").value,
    market_type: document.getElementById("builderMarketType").value,
    direction: document.getElementById("builderDirection").value,
    initial_capital: parseFloat(document.getElementById("initialCapital").value),
    blocks: strategyBlocks,
    connections: connections,
  };

  try {
    const response = await fetch("/api/v1/strategy-builder/strategies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(strategy),
    });

    if (response.ok) {
      const data = await response.json();
      updateLastSaved();
      showNotification("Strategy saved successfully!", "success");
      // Update URL with strategy ID if new
      if (!window.location.search.includes("id=")) {
        window.history.pushState({}, "", `?id=${data.id}`);
      }
    } else {
      const error = await response.json();
      showNotification(`Error: ${error.detail}`, "error");
    }
  } catch (err) {
    showNotification("Failed to save strategy", "error");
  }
}
```

### Load Strategy Flow

```javascript
async function loadStrategy(strategyId) {
  try {
    const response = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}`);
    if (response.ok) {
      const strategy = await response.json();
      
      // Update UI
      document.getElementById("strategyName").value = strategy.name;
      document.getElementById("strategyTimeframe").value = strategy.timeframe;
      document.getElementById("strategySymbol").value = strategy.symbol;
      document.getElementById("builderMarketType").value = strategy.market_type;
      document.getElementById("builderDirection").value = strategy.direction;
      document.getElementById("initialCapital").value = strategy.initial_capital;
      
      // Restore blocks and connections
      strategyBlocks = strategy.blocks;
      connections.length = 0;
      connections.push(...strategy.connections);
      
      // Re-render canvas
      renderBlocks();
      renderConnections();
      
      updateLastSaved(strategy.updated_at);
    }
  } catch (err) {
    showNotification("Failed to load strategy", "error");
  }
}

// Load on page load if ID in URL
document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const strategyId = urlParams.get("id");
  if (strategyId) {
    loadStrategy(strategyId);
  }
});
```

---

## Code Generation & Execution

### Code Generation Process

1. **Validate Strategy Graph**
   - Check all blocks are connected
   - Verify port types match
   - Ensure main strategy node has entry signals

2. **Topological Sort**
   - Order blocks by execution dependencies
   - Indicators → Conditions → Actions → Strategy Node

3. **Generate Code**
   - Map blocks to Python code snippets
   - Connect via variables
   - Add imports and structure

4. **Return Generated Code**
   - Python code string
   - Dependencies list
   - Warnings/errors

### Generated Code Structure

```python
"""
Generated Strategy: My RSI Strategy
Generated: 2026-01-29T10:00:00Z
Version: 1.0.0
"""

import pandas as pd
import numpy as np
try:
    import vectorbt as vbt
except ImportError:
    vbt = None

def generate_signals(ohlcv: pd.DataFrame) -> dict:
    """
    Generate trading signals from OHLCV data.
    
    Args:
        ohlcv: DataFrame with columns: open, high, low, close, volume
               Index should be datetime
    
    Returns:
        dict with keys: entries, exits, short_entries, short_exits
    """
    # Block: RSI Indicator
    rsi_period = 14
    rsi_values = vbt.RSI.run(ohlcv['close'], window=rsi_period).rsi
    
    # Block: Constant (30)
    constant_30 = 30
    
    # Block: Less Than Condition
    less_than_result = rsi_values < constant_30
    
    # Block: Constant (70)
    constant_70 = 70
    
    # Block: Greater Than Condition
    greater_than_result = rsi_values > constant_70
    
    # Strategy Node: Entry/Exit Signals
    entries = less_than_result  # RSI < 30 → Entry Long
    exits = greater_than_result  # RSI > 70 → Exit Long
    short_entries = greater_than_result  # RSI > 70 → Entry Short
    short_exits = less_than_result  # RSI < 30 → Exit Short
    
    return {
        "entries": entries,
        "exits": exits,
        "short_entries": short_entries,
        "short_exits": short_exits,
    }
```

### Strategy Adapter for Backtesting

The generated code is wrapped in a `StrategyBuilderAdapter` that implements the `BaseStrategy` interface:

```python
class StrategyBuilderAdapter(BaseStrategy):
    """Adapter for Strategy Builder generated strategies"""
    
    def __init__(self, strategy_graph: dict):
        self.graph = strategy_graph
        self.name = strategy_graph["name"]
        self.description = strategy_graph.get("description", "")
        self.params = self._extract_params(strategy_graph)
        
    def generate_signals(self, ohlcv: pd.DataFrame) -> SignalResult:
        """Generate signals using generated code"""
        # Execute generated code
        signals = self._execute_generated_code(ohlcv)
        
        return SignalResult(
            entries=signals["entries"],
            exits=signals["exits"],
            short_entries=signals.get("short_entries"),
            short_exits=signals.get("short_exits"),
        )
```

---

## Backtest Integration

### Backtest Request Flow

```
Frontend (strategy_builder.js)
  ↓ POST /api/v1/strategy-builder/strategies/{id}/backtest
Backend (strategy_builder.py)
  ↓ Load strategy graph
  ↓ Validate strategy
  ↓ Generate code (if needed)
  ↓ Create StrategyBuilderAdapter
  ↓ POST /api/v1/backtests/
Backend (backtests.py)
  ↓ Select engine (based on strategy features)
  ↓ Run backtest
  ↓ Return results
Frontend
  ↓ Redirect to backtest-results.html
```

### Engine Selection Logic

```python
def select_engine_for_strategy(strategy_graph: dict) -> str:
    """Select appropriate backtesting engine"""
    
    # Check for Multi-TP / DCA / ATR
    has_multi_tp = any(
        block.get("type") == "take_profit" and 
        block.get("params", {}).get("multi_levels")
        for block in strategy_graph["blocks"]
    )
    
    has_dca = any(
        block.get("type") in ["buy", "sell"] and
        block.get("params", {}).get("pyramiding", 0) > 1
        for block in strategy_graph["blocks"]
    )
    
    has_atr = any(
        block.get("type") in ["stop_loss", "take_profit"] and
        block.get("params", {}).get("use_atr", False)
        for block in strategy_graph["blocks"]
    )
    
    if has_multi_tp or has_dca or has_atr:
        return "fallback_v4"  # Only V4 supports these features
    
    # Check for pyramiding
    has_pyramiding = any(
        block.get("params", {}).get("pyramiding", 0) > 1
        for block in strategy_graph["blocks"]
    )
    
    if has_pyramiding:
        return "fallback_v3"  # V3 supports pyramiding
    
    # Default: use fastest engine
    return "numba_v2"  # Fast optimization
```

---

## AI Agent Integration

### For DeepSeek & Perplexity Agents

AI agents should understand:

1. **Strategy Builder Structure**
   - Blocks are visual representations of trading logic
   - Connections define data flow
   - Main strategy node receives entry/exit signals

2. **How to Work with Strategy Builder**
   - Create/modify strategies via API
   - Understand block types and their parameters
   - Generate code from graphs
   - Run backtests

3. **API Endpoints to Use**
   - `POST /api/v1/strategy-builder/strategies` - Create strategy
   - `GET /api/v1/strategy-builder/strategies/{id}` - Get strategy
   - `PUT /api/v1/strategy-builder/strategies/{id}` - Update strategy
   - `POST /api/v1/strategy-builder/generate` - Generate code
   - `POST /api/v1/strategy-builder/strategies/{id}/backtest` - Run backtest

### Example: AI Agent Creating a Strategy

```python
# AI Agent code (pseudo-code)
async def create_rsi_strategy():
    # 1. Create strategy
    strategy = await api.post("/api/v1/strategy-builder/strategies", {
        "name": "AI Generated RSI Strategy",
        "timeframe": "1h",
        "symbol": "BTCUSDT",
        "market_type": "linear",
        "direction": "both"
    })
    
    # 2. Add blocks
    rsi_block = await api.post("/api/v1/strategy-builder/blocks", {
        "strategy_id": strategy["id"],
        "block_type": "rsi",
        "x": 100,
        "y": 200,
        "parameters": {"period": 14, "overbought": 70, "oversold": 30}
    })
    
    const_30 = await api.post("/api/v1/strategy-builder/blocks", {
        "strategy_id": strategy["id"],
        "block_type": "constant",
        "x": 100,
        "y": 300,
        "parameters": {"value": 30}
    })
    
    less_than = await api.post("/api/v1/strategy-builder/blocks", {
        "strategy_id": strategy["id"],
        "block_type": "less_than",
        "x": 350,
        "y": 250
    })
    
    # 3. Connect blocks
    await api.post("/api/v1/strategy-builder/connections", {
        "strategy_id": strategy["id"],
        "source_block_id": rsi_block["id"],
        "source_output": "value",
        "target_block_id": less_than["id"],
        "target_input": "a"
    })
    
    await api.post("/api/v1/strategy-builder/connections", {
        "strategy_id": strategy["id"],
        "source_block_id": const_30["id"],
        "source_output": "value",
        "target_block_id": less_than["id"],
        "target_input": "b"
    })
    
    # 4. Connect to main strategy node
    main_node = strategy["blocks"].find(b => b.type === "strategy")
    await api.post("/api/v1/strategy-builder/connections", {
        "strategy_id": strategy["id"],
        "source_block_id": less_than["id"],
        "source_output": "result",
        "target_block_id": main_node["id"],
        "target_input": "entry_long"
    })
    
    # 5. Validate
    validation = await api.post(f"/api/v1/strategy-builder/validate/{strategy['id']}")
    
    # 6. Run backtest
    backtest = await api.post(f"/api/v1/strategy-builder/strategies/{strategy['id']}/backtest", {
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-12-31T23:59:59Z"
    })
    
    return backtest
```

---

## Implementation Plan

### Phase 1: Database Integration ✅
- [x] Extend Strategy model to store graph data
- [x] Create migration for graph storage
- [ ] Update Strategy CRUD to handle graphs

### Phase 2: API Endpoints ✅
- [x] Strategy CRUD endpoints
- [x] Block operations endpoints
- [x] Connection operations endpoints
- [x] Validation endpoints
- [x] Code generation endpoints
- [ ] Backtest integration endpoint

### Phase 3: Frontend Integration 🔄
- [ ] Update `saveStrategy()` to use new API
- [ ] Update `loadStrategy()` to use new API
- [ ] Update `runBacktest()` to use new API
- [ ] Add auto-save functionality
- [ ] Add version control UI

### Phase 4: Code Generation 🔄
- [ ] Implement code generator for all block types
- [ ] Create StrategyBuilderAdapter
- [ ] Integrate with backtesting engines
- [ ] Test generated code execution

### Phase 5: AI Agent Support 🔄
- [ ] Document API for AI agents
- [ ] Create example workflows
- [ ] Add AI-friendly error messages
- [ ] Test with DeepSeek/Perplexity

---

## References

- [Backtesting Engine Architecture](./ENGINE_ARCHITECTURE.md)
- [Strategy Process Flow](./STRATEGIES_PROCESS_FLOW.md)
- [API Reference](../../API_REFERENCE.md)
- [Frontend Strategy Builder](../../frontend/js/pages/strategy_builder.js)

---

**Last Updated**: 2026-01-29  
**Maintainer**: Development Team  
**Status**: Implementation Phase
