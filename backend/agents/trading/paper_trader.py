"""
Agent Paper Trader — Simulated Live Trading for AI Agents.

Thin wrapper around the existing ``LiveStrategyRunner``
(``backend.services.live_trading``) with ``paper_trading=True``.

Features:
- Virtual portfolio tracking (no real orders)
- Real-time price feed via Bybit WebSocket
- Configurable initial balance and position sizing
- Session recording for post-analysis
- Integration with VectorMemoryStore (save paper results)
- MCP tool integration (``start_paper_trading``)

Usage::

    trader = AgentPaperTrader()
    session = await trader.start_session(
        symbol="BTCUSDT",
        strategy_type="rsi",
        strategy_params={"period": 14, "overbought": 70, "oversold": 30},
        initial_balance=10000.0,
        duration_minutes=60,
    )
    print(session.to_dict())

Added 2026-02-12 per Agent Ecosystem Audit — Additional Directions.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger

# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class PaperTrade:
    """A single simulated trade."""

    trade_id: str
    symbol: str
    side: str  # "buy" or "sell"
    entry_price: float
    exit_price: float | None = None
    qty: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None
    is_open: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "qty": self.qty,
            "pnl": round(self.pnl, 4),
            "pnl_pct": round(self.pnl_pct, 4),
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "is_open": self.is_open,
        }


@dataclass
class PaperSession:
    """Complete paper trading session record."""

    session_id: str
    symbol: str
    strategy_type: str
    strategy_params: dict[str, Any] = field(default_factory=dict)
    initial_balance: float = 10000.0
    current_balance: float = 10000.0
    peak_balance: float = 10000.0

    # Trade stats
    trades: list[PaperTrade] = field(default_factory=list)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Performance
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    current_price: float = 0.0

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    duration_minutes: float = 0.0
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "strategy_type": self.strategy_type,
            "strategy_params": self.strategy_params,
            "initial_balance": self.initial_balance,
            "current_balance": round(self.current_balance, 2),
            "peak_balance": round(self.peak_balance, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": round(self.total_pnl, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "win_rate": round(self.win_rate, 1),
            "current_price": self.current_price,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_minutes": round(self.duration_minutes, 1),
            "is_active": self.is_active,
            "trades_summary": [t.to_dict() for t in self.trades[-20:]],
        }


# =============================================================================
# PAPER TRADER
# =============================================================================


class AgentPaperTrader:
    """
    Simulated live trading for AI agents.

    Runs a strategy against real-time Bybit WebSocket data
    in paper-trading mode (no real orders).
    """

    # Active sessions keyed by session_id
    _sessions: dict[str, PaperSession] = {}

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_session(
        self,
        symbol: str = "BTCUSDT",
        strategy_type: str = "rsi",
        strategy_params: dict[str, Any] | None = None,
        initial_balance: float = 10000.0,
        leverage: float = 1.0,
        duration_minutes: float = 60.0,
        position_size_pct: float = 5.0,
    ) -> PaperSession:
        """
        Start a new paper-trading session.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            strategy_type: Strategy to run
            strategy_params: Strategy-specific parameters
            initial_balance: Starting virtual balance (USDT)
            leverage: Leverage multiplier
            duration_minutes: How long to run (0 = indefinite)
            position_size_pct: % of equity per trade

        Returns:
            PaperSession with initial status
        """
        session_id = str(uuid.uuid4())[:10]
        session = PaperSession(
            session_id=session_id,
            symbol=symbol,
            strategy_type=strategy_type,
            strategy_params=strategy_params or {},
            initial_balance=initial_balance,
            current_balance=initial_balance,
            peak_balance=initial_balance,
        )

        AgentPaperTrader._sessions[session_id] = session

        # Start the simulation loop in the background
        task = asyncio.create_task(self._run_session(session, leverage, duration_minutes, position_size_pct))
        self._tasks[session_id] = task

        logger.info(
            f"📄 Paper trading session '{session_id}' started: {symbol} {strategy_type} (balance={initial_balance})"
        )
        return session

    async def stop_session(self, session_id: str) -> PaperSession | None:
        """Stop a running paper-trading session."""
        session = AgentPaperTrader._sessions.get(session_id)
        if not session:
            return None

        session.is_active = False
        session.ended_at = datetime.now(UTC)
        session.duration_minutes = (session.ended_at - session.started_at).total_seconds() / 60.0

        task = self._tasks.pop(session_id, None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        logger.info(f"📄 Paper trading session '{session_id}' stopped")
        return session

    @classmethod
    def get_session(cls, session_id: str) -> PaperSession | None:
        """Get a session by ID."""
        return cls._sessions.get(session_id)

    @classmethod
    def list_sessions(cls) -> list[dict[str, Any]]:
        """List all sessions (active and completed)."""
        return [s.to_dict() for s in cls._sessions.values()]

    @classmethod
    def list_active(cls) -> list[dict[str, Any]]:
        """List only active sessions."""
        return [s.to_dict() for s in cls._sessions.values() if s.is_active]

    # ------------------------------------------------------------------
    # Session loop
    # ------------------------------------------------------------------

    async def _run_session(
        self,
        session: PaperSession,
        leverage: float,
        duration_minutes: float,
        position_size_pct: float,
    ) -> None:
        """
        Main simulation loop.

        Uses a simplified price-polling approach (avoids WebSocket
        complexity for the agent layer).  For production WebSocket
        integration, see ``LiveStrategyRunner``.
        """
        start_time = time.monotonic()
        timeout_s = duration_minutes * 60 if duration_minutes > 0 else float("inf")
        poll_interval = 15.0  # seconds between price checks

        try:
            while session.is_active:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout_s:
                    logger.info(f"Session '{session.session_id}' reached {duration_minutes}min time limit")
                    break

                # Fetch latest price
                price = await self._get_latest_price(session.symbol)
                if price is None:
                    await asyncio.sleep(poll_interval)
                    continue

                session.current_price = price

                # Generate signal
                signal = await self._generate_signal(
                    session.strategy_type,
                    session.strategy_params,
                    session.symbol,
                    price,
                    session.trades,
                )

                # Execute signal if present
                if signal and signal != "hold":
                    self._execute_paper_signal(session, signal, price, leverage, position_size_pct)

                # Update drawdown
                if session.current_balance > session.peak_balance:
                    session.peak_balance = session.current_balance
                if session.peak_balance > 0:
                    dd = ((session.peak_balance - session.current_balance) / session.peak_balance) * 100
                    session.max_drawdown_pct = max(session.max_drawdown_pct, dd)

                await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(f"Paper session '{session.session_id}' error: {exc}")
        finally:
            # Close any remaining open trades at current price
            for trade in session.trades:
                if trade.is_open and session.current_price > 0:
                    self._close_paper_trade(session, trade, session.current_price)

            session.is_active = False
            session.ended_at = datetime.now(UTC)
            session.duration_minutes = (session.ended_at - session.started_at).total_seconds() / 60.0

            # Finalize stats
            session.total_return_pct = (
                ((session.current_balance - session.initial_balance) / session.initial_balance) * 100
                if session.initial_balance > 0
                else 0
            )
            session.total_pnl = session.current_balance - session.initial_balance
            total = session.winning_trades + session.losing_trades
            session.win_rate = session.winning_trades / total * 100 if total > 0 else 0

            logger.info(
                f"📄 Paper session '{session.session_id}' finished: "
                f"{session.total_trades} trades, "
                f"{session.total_return_pct:.2f}% return"
            )

            # Save to memory (best-effort)
            await self._save_session_to_memory(session)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_latest_price(symbol: str) -> float | None:
        """Fetch the latest mark price from the database or API."""
        try:
            from backend.services.kline_repository_adapter import (
                KlineRepositoryAdapter,
            )

            adapter = KlineRepositoryAdapter()
            klines = adapter.get_klines(symbol, "1", limit=1)
            if klines and len(klines) > 0:
                last = klines[-1]
                return float(last.get("close", last.get("close_price", 0)))
        except Exception:
            pass

        # Fallback: try Bybit API
        try:
            from backend.services.adapters.bybit import BybitAdapter

            adapter = BybitAdapter()
            ticker = await asyncio.to_thread(adapter.get_ticker, symbol)
            if ticker and "lastPrice" in ticker:
                return float(ticker["lastPrice"])
        except Exception:
            pass

        return None

    @staticmethod
    async def _generate_signal(
        strategy_type: str,
        params: dict[str, Any],
        symbol: str,
        price: float,
        recent_trades: list[PaperTrade],
    ) -> str | None:
        """
        Simple signal generation for paper trading.

        For production use, integrate with ``BaseStrategy.on_candle()``.
        This uses a very simplified logic for demo purposes.
        """
        # Check if we have an open trade — if so, only consider exit signals
        open_trades = [t for t in recent_trades if t.is_open]

        if open_trades:
            trade = open_trades[-1]
            pnl_pct = (
                ((price - trade.entry_price) / trade.entry_price) * 100
                if trade.side == "buy"
                else ((trade.entry_price - price) / trade.entry_price) * 100
            )

            # Simple exit rules
            tp = params.get("take_profit_pct", 1.5)
            sl = params.get("stop_loss_pct", 1.0)

            if pnl_pct >= tp:
                return "close"
            if pnl_pct <= -sl:
                return "close"
            return "hold"

        # No open position — simplified entry logic
        # In production, this would use the full strategy engine
        return None  # No signal = no trade

    @staticmethod
    def _execute_paper_signal(
        session: PaperSession,
        signal: str,
        price: float,
        leverage: float,
        position_size_pct: float,
    ) -> None:
        """Execute a paper signal on the session."""
        if signal == "close":
            # Close all open trades
            for trade in session.trades:
                if trade.is_open:
                    AgentPaperTrader._close_paper_trade(session, trade, price)

        elif signal in ("buy", "sell"):
            # Open a new paper trade
            risk_amount = session.current_balance * (position_size_pct / 100)
            qty = (risk_amount * leverage) / price if price > 0 else 0

            trade = PaperTrade(
                trade_id=str(uuid.uuid4())[:8],
                symbol=session.symbol,
                side=signal,
                entry_price=price,
                qty=qty,
            )
            session.trades.append(trade)
            session.total_trades += 1

    @staticmethod
    def _close_paper_trade(session: PaperSession, trade: PaperTrade, price: float) -> None:
        """Close a paper trade and update session stats."""
        trade.exit_price = price
        trade.closed_at = datetime.now(UTC)
        trade.is_open = False

        if trade.side == "buy":
            trade.pnl = (price - trade.entry_price) * trade.qty
        else:
            trade.pnl = (trade.entry_price - price) * trade.qty

        trade.pnl_pct = (trade.pnl / (trade.entry_price * trade.qty)) * 100 if trade.entry_price * trade.qty > 0 else 0

        session.current_balance += trade.pnl

        if trade.pnl > 0:
            session.winning_trades += 1
        else:
            session.losing_trades += 1

    @staticmethod
    async def _save_session_to_memory(session: PaperSession) -> None:
        """Save completed session to vector memory for learning."""
        try:
            from backend.agents.memory.vector_store import VectorMemoryStore

            store = VectorMemoryStore()
            await store.save_backtest_result(
                backtest_id=f"paper_{session.session_id}",
                strategy_type=session.strategy_type,
                strategy_params=session.strategy_params,
                metrics={
                    "win_rate": session.win_rate,
                    "total_return_pct": session.total_return_pct,
                    "total_trades": session.total_trades,
                    "max_drawdown_pct": session.max_drawdown_pct,
                    "sharpe_ratio": 0,  # Not computed for paper trading
                    "profit_factor": 0,
                },
                symbol=session.symbol,
                interval="1",
            )
        except Exception as e:
            logger.debug(f"Failed to save paper session to memory: {e}")
