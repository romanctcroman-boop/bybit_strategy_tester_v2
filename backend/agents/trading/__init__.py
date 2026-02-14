"""
Agent Paper Trading — Real-Time Strategy Execution in Simulation Mode.

Provides AI-agent-friendly paper trading that:
- Connects to Bybit WebSocket for live price data
- Executes strategy signals in a virtual portfolio
- Tracks P&L, win rate, and drawdown in real-time
- Stores results in vector memory for learning
- Integrates with the task scheduler for automated sessions

Wraps the existing ``LiveStrategyRunner`` with ``paper_trading=True``.

Added 2026-02-12 per Agent Ecosystem Audit — Additional Directions.
"""
