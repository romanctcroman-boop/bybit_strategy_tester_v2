#!/usr/bin/env python3
"""
Bybit MCP Server - Custom Model Context Protocol server for trading operations.

This server exposes Bybit trading functionality to AI agents via MCP protocol.
Supports backtesting, market data, and strategy management operations.

Usage:
    python bybit_mcp_server.py

Protocol:
    Communicates via stdin/stdout using JSON-RPC 2.0 (synchronous for Windows compatibility)
"""

import json
import sys
from pathlib import Path
from typing import Any

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class BybitMCPServer:
    """MCP Server for Bybit Strategy Tester operations (synchronous version)."""
    
    def __init__(self):
        self.tools = {
            "get_available_symbols": self.get_available_symbols,
            "get_market_data": self.get_market_data,
            "run_backtest": self.run_backtest,
            "get_strategies": self.get_strategies,
            "get_backtest_results": self.get_backtest_results,
            "get_system_status": self.get_system_status,
        }
    
    def handle_request(self, request: dict) -> dict:
        """Handle incoming MCP request (synchronous)."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "initialize":
            return self._create_response(request_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "bybit-mcp-server",
                    "version": "1.0.0"
                }
            })
        
        elif method == "tools/list":
            return self._create_response(request_id, {
                "tools": [
                    {
                        "name": "get_available_symbols",
                        "description": "Get list of available trading symbols from database",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "get_market_data",
                        "description": "Get OHLCV market data for a symbol",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string", "description": "Trading pair (e.g., BTCUSDT)"},
                                "interval": {"type": "string", "description": "Timeframe (e.g., 1h, 4h, 1d)"},
                                "limit": {"type": "integer", "description": "Number of candles", "default": 100}
                            },
                            "required": ["symbol", "interval"]
                        }
                    },
                    {
                        "name": "run_backtest",
                        "description": "Run a backtest with specified parameters",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "strategy": {"type": "string", "description": "Strategy name (RSI, DCA, etc.)"},
                                "symbol": {"type": "string", "description": "Trading pair"},
                                "interval": {"type": "string", "description": "Timeframe"},
                                "params": {"type": "object", "description": "Strategy parameters"}
                            },
                            "required": ["strategy", "symbol", "interval"]
                        }
                    },
                    {
                        "name": "get_strategies",
                        "description": "List all available trading strategies",
                        "inputSchema": {"type": "object", "properties": {}}
                    },
                    {
                        "name": "get_backtest_results",
                        "description": "Get recent backtest results",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "default": 10}
                            }
                        }
                    },
                    {
                        "name": "get_system_status",
                        "description": "Get current system status and health",
                        "inputSchema": {"type": "object", "properties": {}}
                    }
                ]
            })
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name in self.tools:
                try:
                    result = self.tools[tool_name](tool_args)
                    return self._create_response(request_id, {
                        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]
                    })
                except Exception as e:
                    return self._create_error(request_id, -32000, str(e))
            else:
                return self._create_error(request_id, -32601, f"Unknown tool: {tool_name}")
        
        return self._create_error(request_id, -32601, f"Unknown method: {method}")
    
    def _create_response(self, request_id: Any, result: Any) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    
    def _create_error(self, request_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    
    # === Tool Implementations (synchronous) ===
    
    def get_available_symbols(self, args: dict) -> dict:
        """Get available trading symbols from database."""
        # Return common symbols as fallback (database integration can be added later)
        return {
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
            "count": 5,
            "note": "Common trading pairs available"
        }
    
    def get_market_data(self, args: dict) -> dict:
        """Get market data for a symbol."""
        symbol = args.get("symbol", "BTCUSDT")
        interval = args.get("interval", "1h")
        limit = args.get("limit", 100)
        
        return {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "status": "Use backend API /api/v1/market-data for actual data",
            "api_endpoint": f"/api/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        }
    
    def run_backtest(self, args: dict) -> dict:
        """Run a backtest."""
        strategy = args.get("strategy", "RSI")
        symbol = args.get("symbol", "BTCUSDT")
        interval = args.get("interval", "1h")
        params = args.get("params", {})
        
        return {
            "status": "Use backend API /api/v1/backtests for actual backtests",
            "strategy": strategy,
            "symbol": symbol,
            "interval": interval,
            "params": params,
            "api_endpoint": "/api/v1/backtests"
        }
    
    def get_strategies(self, args: dict) -> dict:
        """List available strategies."""
        return {
            "strategies": [
                {"name": "RSI", "description": "RSI-based entry/exit strategy"},
                {"name": "DCA", "description": "Dollar Cost Averaging with safety orders"},
                {"name": "MACD", "description": "MACD crossover strategy"},
                {"name": "BB", "description": "Bollinger Bands breakout strategy"},
                {"name": "EMA_Cross", "description": "EMA crossover strategy"},
                {"name": "Grid", "description": "Grid trading strategy"}
            ]
        }
    
    def get_backtest_results(self, args: dict) -> dict:
        """Get recent backtest results."""
        limit = args.get("limit", 10)
        
        return {
            "status": "Use backend API /api/v1/backtests/results for actual results",
            "limit": limit,
            "api_endpoint": f"/api/v1/backtests/results?limit={limit}"
        }
    
    def get_system_status(self, args: dict) -> dict:
        """Get system status."""
        return {
            "status": "operational",
            "version": "2.12",
            "python": sys.version,
            "project_root": str(PROJECT_ROOT),
            "capabilities": [
                "backtesting",
                "optimization", 
                "market_data",
                "strategy_management"
            ]
        }


def main():
    """Main entry point for MCP server (synchronous stdin/stdout)."""
    server = BybitMCPServer()
    
    # Read from stdin line by line (synchronous for Windows compatibility)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
            
            # Skip notifications (requests without id) - don't send response
            request_id = request.get("id")
            if request_id is None:
                # This is a notification, process but don't respond
                try:
                    server.handle_request(request)
                except Exception:
                    pass
                continue
            
            response = server.handle_request(request)
            
            # Write response to stdout
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            # Invalid JSON - ignore silently
            continue
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
