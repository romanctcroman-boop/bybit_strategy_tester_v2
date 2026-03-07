import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

from backend.backtesting.strategy_builder.adapter import StrategyBuilderAdapter
from backend.database import SessionLocal
from backend.database.models.strategy import Strategy

db = SessionLocal()
try:
    s = db.query(Strategy).filter(Strategy.id == "f46c7cc3-1098-483a-a177-67b7867dd72e").first()
    if s:
        # Simulate exactly what the router does
        _blocks = s.builder_blocks
        _connections = s.builder_connections
        val_preview = repr(_blocks)[:200] if _blocks else None
        print(f"builder_blocks type: {type(_blocks)}, val={val_preview}")
        print(f"builder_connections type: {type(_connections)}, len={len(_connections) if _connections else None}")

        if not _blocks and s.builder_graph:
            _blocks = s.builder_graph.get("blocks", [])
            _connections = s.builder_graph.get("connections", [])
            print(f"  -> fell back to builder_graph blocks: {len(_blocks)} blocks")

        strategy_graph = {
            "name": s.name,
            "description": s.description or "",
            "blocks": _blocks or [],
            "connections": _connections or [],
            "market_type": "linear",
            "direction": "both",
            "interval": "30",
        }
        print(f"\nblocks in strategy_graph:")
        for b in strategy_graph["blocks"]:
            print(f"  type={b.get('type')!r:30} category={b.get('category')!r}")

        adapter = StrategyBuilderAdapter(strategy_graph)
        has_dca = adapter.has_dca_blocks()
        cfg = adapter.extract_dca_config()
        print(f"\nhas_dca_blocks()={has_dca}")
        print(f"dca_enabled from config={cfg.get('dca_enabled')}")
        print(f"dca_order_count={cfg.get('dca_order_count')}")

        # Simulate exactly what router does for dca_enabled
        request_dca_enabled = False  # assume frontend doesn't send dca_enabled
        dca_enabled = request_dca_enabled or has_dca or cfg.get("dca_enabled", False)
        print(f"\nFinal dca_enabled={dca_enabled}")

        engine_type = "auto"
        if engine_type == "auto":
            if dca_enabled:
                engine_type = "dca"
        print(f"engine_type={engine_type}")
    else:
        print("Strategy not found")
finally:
    db.close()
