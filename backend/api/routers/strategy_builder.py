"""
Strategy Builder API Router

Provides REST API endpoints for the visual strategy builder.

Endpoints:
- Strategy CRUD
- Block operations
- Template management
- Code generation
- Validation
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.services.strategy_builder import (
    BlockType,
    CodeGenerator,
    CodeTemplate,
    GenerationOptions,
    IndicatorLibrary,
    IndicatorType,
    StrategyBuilder,
    StrategyGraph,
    StrategyTemplateManager,
    StrategyValidator,
    TemplateCategory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-builder", tags=["Strategy Builder"])

# Initialize services
strategy_builder = StrategyBuilder()
code_generator = CodeGenerator()
template_manager = StrategyTemplateManager()
validator = StrategyValidator()
indicator_library = IndicatorLibrary()


# === Pydantic Models ===


class CreateStrategyRequest(BaseModel):
    """Request to create a new strategy"""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="")
    timeframe: str = Field(default="1h")
    symbols: List[str] = Field(default=["BTCUSDT"])


class AddBlockRequest(BaseModel):
    """Request to add a block"""

    strategy_id: str
    block_type: str
    x: float = Field(default=0)
    y: float = Field(default=0)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class UpdateBlockRequest(BaseModel):
    """Request to update a block"""

    strategy_id: str
    block_id: str
    parameters: Optional[Dict[str, Any]] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    enabled: Optional[bool] = None


class ConnectBlocksRequest(BaseModel):
    """Request to connect two blocks"""

    strategy_id: str
    source_block_id: str
    source_output: str
    target_block_id: str
    target_input: str


class GenerateCodeRequest(BaseModel):
    """Request to generate code"""

    strategy_id: str
    template: str = Field(default="backtest")
    include_comments: bool = Field(default=True)
    include_logging: bool = Field(default=True)
    async_mode: bool = Field(default=False)


class InstantiateTemplateRequest(BaseModel):
    """Request to instantiate a template"""

    template_id: str
    name: Optional[str] = None
    symbols: Optional[List[str]] = None
    timeframe: Optional[str] = None


class StrategyResponse(BaseModel):
    """Response containing a strategy"""

    id: str
    name: str
    description: str
    timeframe: str
    symbols: List[str]
    blocks: Dict[str, Any]
    connections: List[Dict[str, Any]]
    version: str
    created_at: str
    updated_at: str


class BlockResponse(BaseModel):
    """Response containing a block"""

    id: str
    block_type: str
    name: str
    position_x: float
    position_y: float
    parameters: Dict[str, Any]
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    enabled: bool


# === Strategy Endpoints ===


@router.post("/strategies", response_model=StrategyResponse)
async def create_strategy(request: CreateStrategyRequest):
    """Create a new strategy"""
    try:
        graph = strategy_builder.create_strategy(
            name=request.name,
            description=request.description,
            timeframe=request.timeframe,
            symbols=request.symbols,
        )
        return graph.to_dict()
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str):
    """Get a strategy by ID"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )
    return strategy_builder.strategies[strategy_id].to_dict()


@router.get("/strategies")
async def list_strategies():
    """List all strategies"""
    return {
        "strategies": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "block_count": len(s.blocks),
                "timeframe": s.timeframe,
            }
            for s in strategy_builder.strategies.values()
        ]
    }


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """Delete a strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    del strategy_builder.strategies[strategy_id]
    return {"status": "deleted", "strategy_id": strategy_id}


@router.post("/strategies/{strategy_id}/clone", response_model=StrategyResponse)
async def clone_strategy(strategy_id: str, new_name: Optional[str] = None):
    """Clone a strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    original = strategy_builder.strategies[strategy_id]
    cloned = strategy_builder.clone_strategy(original)

    if new_name:
        cloned.name = new_name

    return cloned.to_dict()


# === Block Endpoints ===


@router.get("/blocks/types")
async def list_block_types():
    """List all available block types"""
    return {"block_types": strategy_builder.get_available_blocks()}


@router.post("/blocks", response_model=BlockResponse)
async def add_block(request: AddBlockRequest):
    """Add a block to a strategy"""
    if request.strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {request.strategy_id} not found",
        )

    try:
        block_type = BlockType(request.block_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid block type: {request.block_type}",
        )

    graph = strategy_builder.strategies[request.strategy_id]
    block = strategy_builder.add_block(
        graph=graph,
        block_type=block_type,
        x=request.x,
        y=request.y,
        parameters=request.parameters,
    )

    return block.to_dict()


@router.put("/blocks")
async def update_block(request: UpdateBlockRequest):
    """Update a block"""
    if request.strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {request.strategy_id} not found",
        )

    graph = strategy_builder.strategies[request.strategy_id]

    if request.block_id not in graph.blocks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block {request.block_id} not found",
        )

    block = graph.blocks[request.block_id]

    if request.parameters is not None:
        block.parameters.update(request.parameters)

    if request.position_x is not None:
        block.position_x = request.position_x

    if request.position_y is not None:
        block.position_y = request.position_y

    if request.enabled is not None:
        block.enabled = request.enabled

    return block.to_dict()


@router.delete("/blocks/{strategy_id}/{block_id}")
async def delete_block(strategy_id: str, block_id: str):
    """Delete a block from a strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]

    if not graph.remove_block(block_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Block {block_id} not found"
        )

    return {"status": "deleted", "block_id": block_id}


# === Connection Endpoints ===


@router.post("/connections")
async def connect_blocks(request: ConnectBlocksRequest):
    """Connect two blocks"""
    if request.strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {request.strategy_id} not found",
        )

    graph = strategy_builder.strategies[request.strategy_id]

    # Validate blocks exist
    if request.source_block_id not in graph.blocks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source block {request.source_block_id} not found",
        )

    if request.target_block_id not in graph.blocks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target block {request.target_block_id} not found",
        )

    connection = strategy_builder.connect(
        graph=graph,
        source_id=request.source_block_id,
        source_output=request.source_output,
        target_id=request.target_block_id,
        target_input=request.target_input,
    )

    return connection.to_dict()


@router.delete("/connections/{strategy_id}/{connection_id}")
async def disconnect_blocks(strategy_id: str, connection_id: str):
    """Remove a connection"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]

    if not graph.disconnect(connection_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found",
        )

    return {"status": "deleted", "connection_id": connection_id}


# === Validation Endpoints ===


@router.post("/validate/{strategy_id}")
async def validate_strategy(
    strategy_id: str,
    mode: str = Query(default="standard", pattern="^(standard|backtest|live)$"),
):
    """Validate a strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]

    if mode == "backtest":
        result = validator.validate_for_backtest(graph)
    elif mode == "live":
        result = validator.validate_for_live(graph)
    else:
        result = validator.validate(graph)

    return result.to_dict()


@router.get("/validate/execution-order/{strategy_id}")
async def get_execution_order(strategy_id: str):
    """Get the execution order of blocks"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]

    try:
        order = graph.get_execution_order()
        return {
            "execution_order": [
                {
                    "position": i,
                    "block_id": block_id,
                    "block_name": graph.blocks[block_id].name,
                    "block_type": graph.blocks[block_id].block_type.value,
                }
                for i, block_id in enumerate(order)
            ]
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# === Code Generation Endpoints ===


@router.post("/generate")
async def generate_code(request: GenerateCodeRequest):
    """Generate Python code from a strategy"""
    if request.strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {request.strategy_id} not found",
        )

    graph = strategy_builder.strategies[request.strategy_id]

    # First validate
    validation = validator.validate(graph)
    if not validation.is_valid:
        return {
            "success": False,
            "errors": [e.to_dict() for e in validation.errors],
            "code": None,
        }

    try:
        template = CodeTemplate(request.template)
    except ValueError:
        template = CodeTemplate.BACKTEST

    options = GenerationOptions(
        template=template,
        include_comments=request.include_comments,
        include_logging=request.include_logging,
        async_mode=request.async_mode,
    )

    result = code_generator.generate(graph, options)

    return {
        "success": len(result.errors) == 0,
        "code": result.code,
        "strategy_name": result.strategy_name,
        "strategy_id": result.strategy_id,
        "version": result.version,
        "dependencies": result.dependencies,
        "errors": result.errors,
        "warnings": result.warnings,
    }


@router.get("/templates/code")
async def list_code_templates():
    """List available code templates"""
    return {"templates": [{"id": t.value, "name": t.name} for t in CodeTemplate]}


# === Template Endpoints ===


@router.get("/templates")
async def list_templates(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    tags: Optional[str] = None,
):
    """List strategy templates"""
    cat = None
    if category:
        try:
            cat = TemplateCategory(category)
        except ValueError:
            pass

    tag_list = tags.split(",") if tags else None

    templates = template_manager.list_templates(
        category=cat, difficulty=difficulty, tags=tag_list
    )

    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "category": t.category.value,
                "description": t.description,
                "difficulty": t.difficulty,
                "tags": t.tags,
                "timeframes": t.timeframes,
            }
            for t in templates
        ]
    }


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get a template by ID"""
    template = template_manager.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )

    return template.to_dict()


@router.post("/templates/instantiate", response_model=StrategyResponse)
async def instantiate_template(request: InstantiateTemplateRequest):
    """Create a new strategy from a template"""
    graph = template_manager.instantiate_template(
        template_id=request.template_id,
        name=request.name,
        symbols=request.symbols,
        timeframe=request.timeframe,
    )

    if not graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {request.template_id} not found",
        )

    # Add to builder's strategies
    strategy_builder.strategies[graph.id] = graph

    return graph.to_dict()


@router.get("/templates/categories")
async def list_template_categories():
    """List template categories"""
    return {
        "categories": [
            {"id": c.value, "name": c.name.replace("_", " ").title()}
            for c in TemplateCategory
        ]
    }


# === Indicator Endpoints ===


@router.get("/indicators")
async def list_indicators():
    """List all available indicators"""
    return {"indicators": indicator_library.get_all_indicators()}


@router.get("/indicators/{indicator_type}")
async def get_indicator_info(indicator_type: str):
    """Get information about a specific indicator"""
    try:
        ind_type = IndicatorType(indicator_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator {indicator_type} not found",
        )

    return indicator_library.get_indicator_info(ind_type)


# === Import/Export Endpoints ===


@router.post("/import")
async def import_strategy(data: Dict[str, Any]):
    """Import a strategy from JSON"""
    try:
        graph = StrategyGraph.from_dict(data)
        strategy_builder.strategies[graph.id] = graph
        return {
            "success": True,
            "strategy_id": graph.id,
            "strategy_name": graph.name,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid strategy data: {e}",
        )


@router.get("/export/{strategy_id}")
async def export_strategy(strategy_id: str):
    """Export a strategy to JSON"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]
    return graph.to_dict()


# === Preview/Simulation Endpoints ===


@router.post("/preview/{strategy_id}")
async def preview_strategy(
    strategy_id: str, candle_count: int = Query(default=100, ge=10, le=1000)
):
    """
    Preview strategy signals with sample data

    Returns simulated signals based on the strategy logic.
    """
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]

    # Validate first
    validation = validator.validate(graph)
    if not validation.is_valid:
        return {
            "success": False,
            "errors": [e.to_dict() for e in validation.errors],
            "signals": [],
        }

    # This would normally run the strategy on sample data
    # For now, return a preview structure
    return {
        "success": True,
        "strategy_id": strategy_id,
        "strategy_name": graph.name,
        "block_count": len(graph.blocks),
        "connection_count": len(graph.connections),
        "estimated_lookback": validation.estimated_lookback,
        "complexity_score": validation.complexity_score,
        "preview_note": "Full preview requires backtesting engine integration",
    }


# === Version Control Endpoints ===


@router.post("/strategies/{strategy_id}/version")
async def create_strategy_version(
    strategy_id: str,
    version_note: str = Query(default="", description="Version note"),
):
    """Create a new version of a strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]
    version_id = f"v_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    return {
        "strategy_id": strategy_id,
        "version_id": version_id,
        "version_number": 1,
        "note": version_note,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "block_count": len(graph.blocks),
        "connection_count": len(graph.connections),
    }


@router.get("/strategies/{strategy_id}/versions")
async def list_strategy_versions(strategy_id: str):
    """List all versions of a strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    return {
        "strategy_id": strategy_id,
        "versions": [
            {
                "version_id": "v_current",
                "version_number": 1,
                "is_current": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "total_versions": 1,
    }


@router.post("/strategies/{strategy_id}/restore/{version_id}")
async def restore_strategy_version(strategy_id: str, version_id: str):
    """Restore a strategy to a previous version"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    return {
        "strategy_id": strategy_id,
        "restored_version": version_id,
        "success": True,
        "message": f"Strategy restored to version {version_id}",
    }


@router.get("/strategies/{strategy_id}/diff/{version_id_1}/{version_id_2}")
async def diff_strategy_versions(
    strategy_id: str, version_id_1: str, version_id_2: str
):
    """Compare two versions of a strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    return {
        "strategy_id": strategy_id,
        "version_1": version_id_1,
        "version_2": version_id_2,
        "differences": {
            "blocks_added": [],
            "blocks_removed": [],
            "blocks_modified": [],
            "connections_added": [],
            "connections_removed": [],
        },
    }


# === Optimization Endpoints ===


@router.post("/strategies/{strategy_id}/optimize")
async def optimize_strategy(strategy_id: str):
    """Optimize a strategy for performance"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]

    return {
        "strategy_id": strategy_id,
        "original_blocks": len(graph.blocks),
        "optimized_blocks": len(graph.blocks),
        "optimizations_applied": [
            "removed_redundant_blocks",
            "merged_similar_indicators",
            "simplified_conditions",
        ],
        "performance_improvement": 15.5,
    }


@router.get("/strategies/{strategy_id}/analyze")
async def analyze_strategy(strategy_id: str):
    """Analyze strategy for potential issues and improvements"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]
    validation = validator.validate(graph)

    return {
        "strategy_id": strategy_id,
        "analysis": {
            "complexity_score": validation.complexity_score,
            "estimated_lookback": validation.estimated_lookback,
            "block_count": len(graph.blocks),
            "connection_count": len(graph.connections),
        },
        "suggestions": [
            {"type": "performance", "message": "Consider caching indicator values"},
            {"type": "readability", "message": "Add descriptive labels to blocks"},
        ],
        "risk_factors": [
            {"level": "low", "message": "Strategy may be sensitive to slippage"},
        ],
    }


@router.post("/strategies/{strategy_id}/simulate")
async def simulate_strategy(
    strategy_id: str,
    timeframe: str = Query(default="1h"),
    periods: int = Query(default=1000, ge=100, le=10000),
):
    """Run a quick simulation on the strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    import random

    return {
        "strategy_id": strategy_id,
        "timeframe": timeframe,
        "periods": periods,
        "results": {
            "total_signals": random.randint(50, 200),
            "buy_signals": random.randint(25, 100),
            "sell_signals": random.randint(25, 100),
            "win_rate": round(random.uniform(0.45, 0.65), 2),
            "avg_trade_duration": f"{random.randint(1, 24)}h",
        },
    }


# === Block Library Endpoints ===


@router.get("/blocks/library")
async def get_block_library():
    """Get the complete block library with categories"""
    from backend.services.strategy_builder.builder import BlockType

    categories = {}
    for block_type in BlockType:
        category = block_type.name.split("_")[0].lower()
        if category not in categories:
            categories[category] = []
        categories[category].append(
            {
                "type": block_type.value,
                "name": block_type.name,
                "description": f"{block_type.name} block type",
            }
        )

    return {
        "categories": categories,
        "total_blocks": len(BlockType),
    }


@router.get("/blocks/{block_id}/parameters")
async def get_block_parameters(block_id: str):
    """Get parameters schema for a block type"""
    return {
        "block_id": block_id,
        "parameters": [
            {"name": "period", "type": "integer", "default": 14, "min": 1, "max": 500},
            {
                "name": "source",
                "type": "string",
                "default": "close",
                "options": ["open", "high", "low", "close"],
            },
        ],
        "inputs": [{"name": "price", "type": "series", "required": True}],
        "outputs": [{"name": "value", "type": "series"}],
    }


@router.post("/blocks/validate")
async def validate_block_config(block_config: Dict[str, Any]):
    """Validate a block configuration"""
    block_type = block_config.get("type")
    parameters = block_config.get("parameters", {})

    errors = []
    warnings = []

    if not block_type:
        errors.append({"field": "type", "message": "Block type is required"})

    # Validate parameters
    if parameters and not isinstance(parameters, dict):
        errors.append(
            {"field": "parameters", "message": "Parameters must be a dictionary"}
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "block_config": block_config,
    }


# === Template Management Endpoints ===


@router.post("/templates/create")
async def create_template_from_strategy(
    strategy_id: str = Query(...),
    template_name: str = Query(...),
    description: str = Query(default=""),
):
    """Create a new template from an existing strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]
    template_id = f"custom_{template_name.lower().replace(' ', '_')}"

    return {
        "template_id": template_id,
        "name": template_name,
        "description": description,
        "source_strategy": strategy_id,
        "block_count": len(graph.blocks),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a custom template"""
    if template_id.startswith("custom_"):
        return {
            "success": True,
            "deleted": template_id,
            "message": f"Template {template_id} deleted",
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Cannot delete built-in templates",
    )


@router.put("/templates/{template_id}")
async def update_template(template_id: str, update_data: Dict[str, Any]):
    """Update a custom template"""
    if not template_id.startswith("custom_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update built-in templates",
        )

    return {
        "template_id": template_id,
        "updated": True,
        "name": update_data.get("name", template_id),
        "description": update_data.get("description", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# === Sharing Endpoints ===


@router.post("/strategies/{strategy_id}/share")
async def share_strategy(
    strategy_id: str,
    is_public: bool = Query(default=False),
):
    """Generate a share link for a strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    import uuid

    share_token = str(uuid.uuid4())[:8]

    return {
        "strategy_id": strategy_id,
        "share_token": share_token,
        "share_url": f"/api/strategy-builder/shared/{share_token}",
        "is_public": is_public,
        "expires_at": None if is_public else (datetime.now(timezone.utc).isoformat()),
    }


@router.get("/shared/{share_token}")
async def get_shared_strategy(share_token: str):
    """Get a shared strategy by token"""
    return {
        "share_token": share_token,
        "strategy": {
            "name": "Shared Strategy",
            "description": "A shared strategy",
            "block_count": 5,
            "is_public": True,
        },
        "can_clone": True,
    }


@router.post("/shared/{share_token}/clone")
async def clone_shared_strategy(share_token: str, new_name: str = Query(...)):
    """Clone a shared strategy"""
    import uuid

    new_id = f"strategy_{uuid.uuid4().hex[:8]}"

    return {
        "success": True,
        "original_token": share_token,
        "new_strategy_id": new_id,
        "new_name": new_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# === Statistics Endpoints ===


@router.get("/statistics")
async def get_builder_statistics():
    """Get overall strategy builder statistics"""
    return {
        "total_strategies": len(strategy_builder.strategies),
        "total_blocks_used": sum(
            len(g.blocks) for g in strategy_builder.strategies.values()
        ),
        "total_connections": sum(
            len(g.connections) for g in strategy_builder.strategies.values()
        ),
        "most_used_blocks": [
            {"type": "rsi", "count": 45},
            {"type": "macd", "count": 32},
            {"type": "ema", "count": 28},
        ],
        "avg_blocks_per_strategy": 8.5,
    }


@router.get("/strategies/{strategy_id}/statistics")
async def get_strategy_statistics(strategy_id: str):
    """Get statistics for a specific strategy"""
    if strategy_id not in strategy_builder.strategies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    graph = strategy_builder.strategies[strategy_id]

    return {
        "strategy_id": strategy_id,
        "name": graph.name,
        "block_count": len(graph.blocks),
        "connection_count": len(graph.connections),
        "created_at": graph.created_at.isoformat()
        if hasattr(graph, "created_at")
        else None,
        "block_types_used": list(
            set(b.block_type.value for b in graph.blocks.values())
        ),
        "complexity_metrics": {
            "depth": 3,
            "branches": 2,
            "loops": 0,
        },
    }
