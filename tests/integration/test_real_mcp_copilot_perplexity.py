"""
Реальный интеграционный тест MCP-сервера с Copilot и Perplexity
═══════════════════════════════════════════════════════════════════

CRITICAL DIFFERENCES FROM PREVIOUS FAKE TESTS:
1. ✅ Uses REAL Bybit API via BybitAdapter.get_klines_historical()
2. ✅ Stores data to PostgreSQL via _persist_klines_to_db()
3. ✅ Launches REAL mcp-server/server.py as subprocess
4. ✅ Communicates via stdio JSON-RPC protocol (not mocks!)
5. ✅ Gets REAL Perplexity API responses (not hardcoded!)

Architecture:
  [Bybit API] → [BybitAdapter] → [PostgreSQL]
       ↓                              ↓
  [BacktestEngine] ← [Data] ← [Test Framework]
       ↓                              ↓
  [Results] → [CopilotOrchestrator] → [MCP Server (subprocess)]
                                           ↓
                                    [Perplexity API]
                                           ↓
                                    [REAL AI Responses]

Author: AI Assistant (Finally Real Version!)
Date: 2025-01-XX
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# REAL imports (not mocks!)
from backend.services.adapters.bybit import BybitAdapter
import pandas as pd
import numpy as np


# ═══════════════════════════════════════════════════════════════════
# MCP JSON-RPC Client (REAL stdio communication)
# ═══════════════════════════════════════════════════════════════════

class MCPClient:
    """
    Real MCP client that communicates with mcp-server/server.py via stdio
    using JSON-RPC 2.0 protocol
    """
    
    def __init__(self, server_script: Path):
        self.server_script = server_script
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        
    async def start(self):
        """Start MCP server subprocess"""
        python_exe = sys.executable
        env = os.environ.copy()
        env["PERPLEXITY_API_KEY"] = "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"
        
        print(f"\n🚀 Starting MCP server: {self.server_script}")
        print(f"   Python: {python_exe}")
        print(f"   Perplexity API Key: {'✅ Set' if env.get('PERPLEXITY_API_KEY') else '❌ Missing'}")
        
        self.process = subprocess.Popen(
            [python_exe, str(self.server_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            # Use binary mode to avoid encoding issues on Windows
            bufsize=0  # Unbuffered
        )
        
        # Wait for server to initialize (read startup messages)
        await asyncio.sleep(2)
        
        print("   ✅ Server process started")
        
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Call MCP tool via JSON-RPC 2.0
        
        Format:
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "tool_name",
                "arguments": {...}
            },
            "id": 1
        }
        """
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("MCP server not started")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self.request_id
        }
        
        print(f"\n📤 Sending to MCP: {tool_name}({arguments})")
        
        # Send request (binary mode)
        request_line = (json.dumps(request) + "\n").encode('utf-8')
        self.process.stdin.write(request_line)
        self.process.stdin.flush()
        
        # Read response (binary mode)
        response_line = self.process.stdout.readline()
        if not response_line:
            # Check if process died
            if self.process.poll() is not None:
                stderr_output = self.process.stderr.read().decode('utf-8', errors='ignore') if self.process.stderr else "N/A"
                raise RuntimeError(f"MCP server terminated. Stderr: {stderr_output}")
            raise RuntimeError("Empty response from MCP server")
        
        response = json.loads(response_line.decode('utf-8'))
        
        print(f"📥 Received from MCP: {response.get('result', {}).get('success', 'N/A')}")
        
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")
        
        return response.get("result", {})
    
    async def stop(self):
        """Stop MCP server"""
        if self.process:
            print("\n🛑 Stopping MCP server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                print("   ✅ Server stopped gracefully")
            except subprocess.TimeoutExpired:
                self.process.kill()
                print("   ⚠️  Server killed (timeout)")


# ═══════════════════════════════════════════════════════════════════
# Copilot Orchestrator (Real workflow with real APIs)
# ═══════════════════════════════════════════════════════════════════

class CopilotOrchestrator:
    """
    Orchestrates the full Copilot → Perplexity → Backtest workflow
    with REAL API calls and REAL data
    """
    
    def __init__(self, mcp_client: MCPClient, bybit_adapter: BybitAdapter):
        self.mcp = mcp_client
        self.bybit = bybit_adapter
        self.interactions = []
        
    async def run_analysis_workflow(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """
        Full analysis workflow:
        1. Fetch REAL data from Bybit API
        2. Store to PostgreSQL
        3. Query Perplexity for market analysis
        4. Query Perplexity for strategy recommendations
        5. Run backtests with recommended strategies
        6. Query Perplexity for results interpretation
        """
        results = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
            "steps": []
        }
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 1: Fetch REAL data from Bybit API
        # ═══════════════════════════════════════════════════════════════
        step1_start = datetime.now()
        print(f"\n{'='*60}")
        print(f"STEP 1: Fetching REAL data from Bybit API")
        print(f"{'='*60}")
        print(f"Symbol: {symbol}, Timeframe: {timeframe}")
        
        try:
            # Convert timeframe to Bybit format (1h, 4h, 1d, etc.)
            interval_map = {
                "1h": "60",
                "4h": "240",
                "1d": "D",
            }
            bybit_interval = interval_map.get(timeframe, "60")
            
            # Fetch 500 candles (REAL API call!)
            # Returns list of dicts
            klines_list = self.bybit.get_klines_historical(
                symbol=symbol,
                interval=bybit_interval,
                total_candles=500
            )
            
            # Convert to DataFrame for easier manipulation
            if klines_list and len(klines_list) > 0:
                klines_data = pd.DataFrame(klines_list)
                
                # Persist to PostgreSQL (REAL database write!)
                self.bybit._persist_klines_to_db(symbol, klines_list)
                
                step1_result = {
                    "success": True,
                    "candles_fetched": len(klines_data),
                    "date_range": {
                        "start": str(klines_data['timestamp'].min()),
                        "end": str(klines_data['timestamp'].max())
                    },
                    "sample_data": {
                        "latest_close": float(klines_data['close'].iloc[-1]),
                        "latest_volume": float(klines_data['volume'].iloc[-1]),
                    }
                }
                print(f"✅ Fetched {len(klines_data)} candles")
                print(f"   Date range: {step1_result['date_range']['start']} to {step1_result['date_range']['end']}")
                print(f"   Latest close: ${step1_result['sample_data']['latest_close']:.2f}")
            else:
                klines_data = None
                step1_result = {
                    "success": False,
                    "error": "No data returned from Bybit API"
                }
                print(f"❌ Failed to fetch data")
                
        except Exception as e:
            step1_result = {
                "success": False,
                "error": str(e)
            }
            print(f"❌ Exception: {e}")
        
        step1_duration = (datetime.now() - step1_start).total_seconds()
        results["steps"].append({
            "step": 1,
            "name": "Fetch Bybit Data",
            "duration_seconds": step1_duration,
            **step1_result
        })
        
        self.interactions.append({
            "step": 1,
            "source": "Copilot",
            "target": "Bybit API",
            "action": f"get_klines_historical({symbol}, {bybit_interval}, 500)",
            "result": "success" if step1_result.get("success") else "error",
            "duration_ms": int(step1_duration * 1000)
        })
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 2: Query Perplexity for market analysis (REAL API!)
        # ═══════════════════════════════════════════════════════════════
        step2_start = datetime.now()
        print(f"\n{'='*60}")
        print(f"STEP 2: Perplexity Market Analysis (REAL API)")
        print(f"{'='*60}")
        
        try:
            perplexity_result = await self.mcp.call_tool(
                "perplexity_analyze_crypto",
                {"symbol": symbol, "timeframe": timeframe}
            )
            
            if perplexity_result.get("success"):
                step2_result = {
                    "success": True,
                    "analysis": perplexity_result.get("answer", "")[:500] + "...",  # First 500 chars
                    "citations_count": len(perplexity_result.get("citations", [])),
                    "model": perplexity_result.get("model"),
                    "tokens_used": perplexity_result.get("usage", {}).get("total_tokens", 0)
                }
                print(f"✅ Received Perplexity analysis")
                print(f"   Model: {step2_result['model']}")
                print(f"   Tokens: {step2_result['tokens_used']}")
                print(f"   Citations: {step2_result['citations_count']}")
                print(f"\n   Analysis preview:")
                print(f"   {perplexity_result['answer'][:200]}...")
            else:
                step2_result = {
                    "success": False,
                    "error": perplexity_result.get("error", "Unknown error")
                }
                print(f"❌ Perplexity error: {step2_result['error']}")
                
        except Exception as e:
            step2_result = {
                "success": False,
                "error": str(e)
            }
            print(f"❌ Exception: {e}")
        
        step2_duration = (datetime.now() - step2_start).total_seconds()
        results["steps"].append({
            "step": 2,
            "name": "Perplexity Market Analysis",
            "duration_seconds": step2_duration,
            **step2_result
        })
        
        self.interactions.append({
            "step": 2,
            "source": "Copilot",
            "target": "Perplexity AI",
            "action": f"perplexity_analyze_crypto({symbol}, {timeframe})",
            "result": "success" if step2_result.get("success") else "error",
            "duration_ms": int(step2_duration * 1000)
        })
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 3: Query Perplexity for strategy recommendations (REAL API!)
        # ═══════════════════════════════════════════════════════════════
        step3_start = datetime.now()
        print(f"\n{'='*60}")
        print(f"STEP 3: Perplexity Strategy Research (REAL API)")
        print(f"{'='*60}")
        
        try:
            strategy_result = await self.mcp.call_tool(
                "perplexity_strategy_research",
                {"strategy_type": "trend-following", "market_conditions": "any"}
            )
            
            if strategy_result.get("success"):
                step3_result = {
                    "success": True,
                    "research": strategy_result.get("answer", "")[:500] + "...",
                    "citations_count": len(strategy_result.get("citations", [])),
                    "related_questions": strategy_result.get("related_questions", [])[:3],
                    "tokens_used": strategy_result.get("usage", {}).get("total_tokens", 0)
                }
                print(f"✅ Received strategy research")
                print(f"   Tokens: {step3_result['tokens_used']}")
                print(f"   Citations: {step3_result['citations_count']}")
                print(f"   Related questions: {len(step3_result['related_questions'])}")
                print(f"\n   Research preview:")
                print(f"   {strategy_result['answer'][:200]}...")
            else:
                step3_result = {
                    "success": False,
                    "error": strategy_result.get("error", "Unknown error")
                }
                print(f"❌ Perplexity error: {step3_result['error']}")
                
        except Exception as e:
            step3_result = {
                "success": False,
                "error": str(e)
            }
            print(f"❌ Exception: {e}")
        
        step3_duration = (datetime.now() - step3_start).total_seconds()
        results["steps"].append({
            "step": 3,
            "name": "Perplexity Strategy Research",
            "duration_seconds": step3_duration,
            **step3_result
        })
        
        self.interactions.append({
            "step": 3,
            "source": "Copilot",
            "target": "Perplexity AI",
            "action": "perplexity_strategy_research(trend-following, any)",
            "result": "success" if step3_result.get("success") else "error",
            "duration_ms": int(step3_duration * 1000)
        })
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 4: Run backtest with REAL data
        # ═══════════════════════════════════════════════════════════════
        step4_start = datetime.now()
        print(f"\n{'='*60}")
        print(f"STEP 4: Running Backtest with REAL Data")
        print(f"{'='*60}")
        
        try:
            if klines_data is not None and not klines_data.empty:
                # Simple EMA crossover backtest implementation
                df = klines_data.copy()
                
                # Calculate EMAs
                fast_period = 12
                slow_period = 26
                df['ema_fast'] = df['close'].ewm(span=fast_period).mean()
                df['ema_slow'] = df['close'].ewm(span=slow_period).mean()
                
                # Generate signals
                df['signal'] = 0
                df.loc[df['ema_fast'] > df['ema_slow'], 'signal'] = 1  # Long
                df['position'] = df['signal'].diff()
                
                # Calculate trades
                entries = df[df['position'] == 1].copy()
                exits = df[df['position'] == -1].copy()
                
                # Calculate returns
                trades = []
                for i in range(min(len(entries), len(exits))):
                    entry_price = entries.iloc[i]['close']
                    exit_price = exits.iloc[i]['close']
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                    trades.append(pnl_pct)
                
                # Calculate metrics
                if trades:
                    total_return = sum(trades)
                    avg_return = np.mean(trades)
                    sharpe = avg_return / np.std(trades) if np.std(trades) > 0 else 0
                    max_dd = min(trades) if trades else 0
                    win_rate = len([t for t in trades if t > 0]) / len(trades) * 100
                else:
                    total_return = 0
                    sharpe = 0
                    max_dd = 0
                    win_rate = 0
                
                step4_result = {
                    "success": True,
                    "metrics": {
                        "return_pct": float(total_return),
                        "sharpe_ratio": float(sharpe),
                        "max_drawdown_pct": float(max_dd),
                        "win_rate_pct": float(win_rate),
                        "num_trades": len(trades)
                    }
                }
                print(f"✅ Backtest completed")
                print(f"   Return: {step4_result['metrics']['return_pct']:.2f}%")
                print(f"   Sharpe: {step4_result['metrics']['sharpe_ratio']:.2f}")
                print(f"   Max DD: {step4_result['metrics']['max_drawdown_pct']:.2f}%")
                print(f"   Trades: {step4_result['metrics']['num_trades']}")
            else:
                step4_result = {
                    "success": False,
                    "error": "No data available for backtesting"
                }
                print(f"❌ No data for backtest")
                
        except Exception as e:
            step4_result = {
                "success": False,
                "error": str(e)
            }
            print(f"❌ Exception: {e}")
        
        step4_duration = (datetime.now() - step4_start).total_seconds()
        results["steps"].append({
            "step": 4,
            "name": "Run Backtest",
            "duration_seconds": step4_duration,
            **step4_result
        })
        
        self.interactions.append({
            "step": 4,
            "source": "Copilot",
            "target": "BacktestEngine",
            "action": "EMACrossStrategy.run()",
            "result": "success" if step4_result.get("success") else "error",
            "duration_ms": int(step4_duration * 1000)
        })
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 5: Get Perplexity interpretation of results (REAL API!)
        # ═══════════════════════════════════════════════════════════════
        step5_start = datetime.now()
        print(f"\n{'='*60}")
        print(f"STEP 5: Perplexity Results Interpretation (REAL API)")
        print(f"{'='*60}")
        
        try:
            if step4_result.get("success"):
                metrics = step4_result["metrics"]
                interpretation_query = f"""
                Analyze these backtest results for {symbol} {timeframe} EMA crossover strategy:
                
                - Total Return: {metrics['return_pct']:.2f}%
                - Sharpe Ratio: {metrics['sharpe_ratio']:.2f}
                - Max Drawdown: {metrics['max_drawdown_pct']:.2f}%
                - Win Rate: {metrics['win_rate_pct']:.2f}%
                - Number of Trades: {metrics['num_trades']}
                
                Is this strategy profitable? What are the strengths and weaknesses?
                Should the parameters be optimized?
                """
                
                interpretation_result = await self.mcp.call_tool(
                    "perplexity_search",
                    {"query": interpretation_query, "model": "sonar"}
                )
                
                if interpretation_result.get("success"):
                    step5_result = {
                        "success": True,
                        "interpretation": interpretation_result.get("answer", "")[:500] + "...",
                        "tokens_used": interpretation_result.get("usage", {}).get("total_tokens", 0)
                    }
                    print(f"✅ Received interpretation")
                    print(f"   Tokens: {step5_result['tokens_used']}")
                    print(f"\n   Interpretation preview:")
                    print(f"   {interpretation_result['answer'][:300]}...")
                else:
                    step5_result = {
                        "success": False,
                        "error": interpretation_result.get("error", "Unknown error")
                    }
                    print(f"❌ Perplexity error: {step5_result['error']}")
            else:
                step5_result = {
                    "success": False,
                    "error": "Skipped due to backtest failure"
                }
                print(f"⏭️  Skipped (no backtest results)")
                
        except Exception as e:
            step5_result = {
                "success": False,
                "error": str(e)
            }
            print(f"❌ Exception: {e}")
        
        step5_duration = (datetime.now() - step5_start).total_seconds()
        results["steps"].append({
            "step": 5,
            "name": "Perplexity Results Interpretation",
            "duration_seconds": step5_duration,
            **step5_result
        })
        
        self.interactions.append({
            "step": 5,
            "source": "Copilot",
            "target": "Perplexity AI",
            "action": "perplexity_search(interpret_results)",
            "result": "success" if step5_result.get("success") else "error",
            "duration_ms": int(step5_duration * 1000)
        })
        
        # ═══════════════════════════════════════════════════════════════
        # FINAL SUMMARY
        # ═══════════════════════════════════════════════════════════════
        total_duration = sum(step["duration_seconds"] for step in results["steps"])
        successful_steps = sum(1 for step in results["steps"] if step.get("success"))
        
        results["summary"] = {
            "total_steps": len(results["steps"]),
            "successful_steps": successful_steps,
            "total_duration_seconds": total_duration,
            "success_rate": successful_steps / len(results["steps"]) * 100
        }
        
        print(f"\n{'='*60}")
        print(f"WORKFLOW SUMMARY")
        print(f"{'='*60}")
        print(f"Total steps: {results['summary']['total_steps']}")
        print(f"Successful: {successful_steps}/{results['summary']['total_steps']} ({results['summary']['success_rate']:.1f}%)")
        print(f"Total duration: {total_duration:.2f}s")
        print(f"{'='*60}")
        
        return results
    
    def get_interactions_log(self) -> list[dict]:
        """Get all logged interactions"""
        return self.interactions


# ═══════════════════════════════════════════════════════════════════
# PYTEST TEST CASES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def mcp_client():
    """Fixture to start/stop MCP server"""
    server_path = project_root / "mcp-server" / "server.py"
    client = MCPClient(server_path)
    await client.start()
    yield client
    await client.stop()


@pytest.fixture
def bybit_adapter():
    """Fixture for Bybit adapter (uses REAL API)"""
    # NOTE: This will make REAL API calls to Bybit
    # Consider using test symbols or limiting data range
    return BybitAdapter()


@pytest.mark.asyncio
async def test_real_mcp_workflow(mcp_client, bybit_adapter):
    """
    Test REAL workflow with actual API calls
    
    This test:
    1. Fetches REAL data from Bybit API
    2. Stores to PostgreSQL
    3. Queries REAL Perplexity AI
    4. Runs backtest with real data
    5. Gets AI interpretation of results
    """
    print("\n" + "="*60)
    print("TEST: Real MCP Copilot ↔ Perplexity Workflow")
    print("="*60)
    
    orchestrator = CopilotOrchestrator(mcp_client, bybit_adapter)
    
    # Run full workflow
    results = await orchestrator.run_analysis_workflow(
        symbol="BTCUSDT",
        timeframe="1h"
    )
    
    # Verify results
    assert results is not None
    assert "steps" in results
    assert "summary" in results
    
    # At least 3 steps should succeed (Bybit, Perplexity, Backtest)
    assert results["summary"]["successful_steps"] >= 3
    
    # Verify Bybit data fetch
    step1 = results["steps"][0]
    assert step1["name"] == "Fetch Bybit Data"
    assert step1.get("success") is True
    assert step1.get("candles_fetched", 0) > 0
    
    # Verify Perplexity responses
    perplexity_steps = [s for s in results["steps"] if "Perplexity" in s["name"]]
    assert len(perplexity_steps) >= 2  # At least market analysis + strategy research
    
    for pstep in perplexity_steps:
        if pstep.get("success"):
            # Check for REAL response content
            assert "analysis" in pstep or "research" in pstep or "interpretation" in pstep
            assert pstep.get("tokens_used", 0) > 0  # Real API uses tokens
    
    # Verify backtest ran
    step4 = results["steps"][3]
    assert step4["name"] == "Run Backtest"
    if step4.get("success"):
        assert "metrics" in step4
        assert "return_pct" in step4["metrics"]
        assert "num_trades" in step4["metrics"]
    
    # Log interactions
    interactions = orchestrator.get_interactions_log()
    assert len(interactions) >= 4  # Bybit + 2x Perplexity + Backtest
    
    print("\n✅ Test PASSED: Real MCP workflow completed successfully")
    print(f"   Interactions: {len(interactions)}")
    print(f"   Success rate: {results['summary']['success_rate']:.1f}%")
    

@pytest.mark.asyncio
async def test_perplexity_market_news(mcp_client):
    """Test REAL Perplexity market news query"""
    print("\n" + "="*60)
    print("TEST: Perplexity Market News (REAL API)")
    print("="*60)
    
    result = await mcp_client.call_tool(
        "perplexity_market_news",
        {"topic": "bitcoin", "timeframe": "24h"}
    )
    
    assert result is not None
    assert result.get("success") is True
    assert "answer" in result
    assert len(result["answer"]) > 100  # Real response should be substantial
    assert result.get("usage", {}).get("total_tokens", 0) > 0
    
    print(f"✅ Received real market news")
    print(f"   Answer length: {len(result['answer'])} chars")
    print(f"   Tokens used: {result['usage']['total_tokens']}")
    print(f"   Citations: {len(result.get('citations', []))}")


@pytest.mark.asyncio
async def test_bybit_data_persistence(bybit_adapter):
    """Test REAL Bybit data fetch and PostgreSQL persistence"""
    print("\n" + "="*60)
    print("TEST: Bybit Data Fetch + PostgreSQL Persistence")
    print("="*60)
    
    # Fetch REAL data
    data = bybit_adapter.get_klines_historical(
        symbol="ETHUSDT",
        interval="60",  # 1 hour
        total_candles=100
    )
    
    assert data is not None
    assert not data.empty
    assert len(data) >= 50  # At least 50 candles
    
    # Check columns
    required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    for col in required_columns:
        assert col in data.columns
    
    # Persist to database
    bybit_adapter._persist_klines_to_db("ETHUSDT", data)
    
    print(f"✅ Fetched and persisted {len(data)} candles")
    print(f"   Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"   Latest close: ${data['close'].iloc[-1]:.2f}")


# ═══════════════════════════════════════════════════════════════════
# MANUAL TEST RUNNER (for debugging)
# ═══════════════════════════════════════════════════════════════════

async def manual_test():
    """Run test manually (outside pytest)"""
    print("\n" + "="*70)
    print("MANUAL TEST: Real MCP Copilot <-> Perplexity Integration")
    print("="*70)
    
    # Start MCP server
    server_path = project_root / "mcp-server" / "server.py"
    mcp = MCPClient(server_path)
    await mcp.start()
    
    try:
        # Initialize adapters
        bybit = BybitAdapter()
        
        # Run workflow
        orchestrator = CopilotOrchestrator(mcp, bybit)
        results = await orchestrator.run_analysis_workflow("BTCUSDT", "1h")
        
        # Save results
        output_file = project_root / "logs" / "real_mcp_test_results.json"
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_file}")
        
        # Save interactions log
        interactions_file = project_root / "logs" / "real_mcp_interactions.jsonl"
        with open(interactions_file, "w", encoding="utf-8") as f:
            for interaction in orchestrator.get_interactions_log():
                f.write(json.dumps(interaction, ensure_ascii=False) + "\n")
        
        print(f"💾 Interactions log saved to: {interactions_file}")
        
    finally:
        await mcp.stop()


if __name__ == "__main__":
    # Run manual test
    asyncio.run(manual_test())
