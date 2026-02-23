"""
Position Manager for Live Trading.

Tracks positions, calculates P&L, manages margin and leverage.

Features:
- Real-time position tracking via WebSocket
- Unrealized/Realized P&L calculation
- Position size and exposure monitoring
- Margin utilization tracking
- Multi-symbol portfolio view
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from backend.services.live_trading.bybit_websocket import (
    BybitWebSocketClient,
    WebSocketMessage,
    parse_execution_message,
    parse_position_message,
    parse_wallet_message,
)
from backend.services.live_trading.order_executor import OrderExecutor
from backend.services.trading_engine_interface import PositionSide

logger = logging.getLogger(__name__)


class PositionMode(Enum):
    """Position mode."""

    ONE_WAY = "one_way"
    HEDGE = "hedge"


@dataclass
class PositionSnapshot:
    """Position snapshot with full details."""

    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    realized_pnl: float
    leverage: float
    margin: float
    liquidation_price: float | None
    take_profit: float | None
    stop_loss: float | None
    roe_percent: float = 0.0  # Return on equity
    position_value: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "size": self.size,
            "entry_price": self.entry_price,
            "mark_price": self.mark_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "leverage": self.leverage,
            "margin": self.margin,
            "liquidation_price": self.liquidation_price,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "roe_percent": self.roe_percent,
            "position_value": self.position_value,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class WalletSnapshot:
    """Wallet/balance snapshot."""

    coin: str
    total_balance: float
    available_balance: float
    used_margin: float
    unrealized_pnl: float
    realized_pnl: float
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def equity(self) -> float:
        """Total equity including unrealized P&L."""
        return self.total_balance + self.unrealized_pnl

    @property
    def margin_ratio(self) -> float:
        """Margin utilization ratio."""
        if self.equity <= 0:
            return 0.0
        return self.used_margin / self.equity * 100

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "coin": self.coin,
            "total_balance": self.total_balance,
            "available_balance": self.available_balance,
            "used_margin": self.used_margin,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "equity": self.equity,
            "margin_ratio": self.margin_ratio,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class TradeExecution:
    """Trade execution record."""

    exec_id: str
    order_id: str
    symbol: str
    side: str
    price: float
    qty: float
    value: float
    fee: float
    is_maker: bool
    exec_time: datetime
    pnl: float = 0.0  # Realized PnL for closing trades


class PositionManager:
    """
    Position Manager for real-time position tracking.

    Usage:
        manager = PositionManager(
            api_key="your_key",
            api_secret="your_secret",
            testnet=False
        )

        # Start tracking
        await manager.start()

        # Get current positions
        positions = manager.get_all_positions()

        # Get P&L
        pnl = manager.get_total_pnl()

        # Register callback for position updates
        manager.on_position_update(my_callback)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        quote_currency: str = "USDT",
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.quote_currency = quote_currency

        # WebSocket client
        self._ws_client = BybitWebSocketClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
        )

        # Order executor for closing positions
        self._executor = OrderExecutor(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
        )

        # Position storage
        self._positions: dict[str, PositionSnapshot] = {}

        # Wallet storage
        self._wallets: dict[str, WalletSnapshot] = {}

        # Trade history
        self._executions: list[TradeExecution] = []
        self._max_executions = 1000  # Keep last N executions

        # Callbacks
        self._position_callbacks: list[Callable] = []
        self._wallet_callbacks: list[Callable] = []
        self._execution_callbacks: list[Callable] = []

        # State
        self._running = False
        self._task: asyncio.Task | None = None

        logger.info(
            f"PositionManager initialized (testnet={testnet}, quote={quote_currency})"
        )

    async def start(self):
        """Start position tracking."""
        if self._running:
            return

        self._running = True

        # Connect WebSocket
        connected = await self._ws_client.connect()
        if not connected:
            raise RuntimeError("Failed to connect to WebSocket")

        # Subscribe to private channels
        await self._ws_client.subscribe_positions()
        await self._ws_client.subscribe_wallet()
        await self._ws_client.subscribe_executions()

        # Register callbacks
        self._ws_client.register_callback("position", self._on_position_update)
        self._ws_client.register_callback("wallet", self._on_wallet_update)
        self._ws_client.register_callback("execution", self._on_execution)

        # Load initial state
        await self._load_initial_state()

        # Start message processing
        self._task = asyncio.create_task(self._process_messages())

        logger.info("✅ PositionManager started")

    async def stop(self):
        """Stop position tracking."""
        self._running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        await self._ws_client.disconnect()
        await self._executor.close()

        logger.info("PositionManager stopped")

    async def _load_initial_state(self):
        """Load initial positions and balance."""
        # Load positions
        positions = await self._executor.get_positions()
        for pos_data in positions:
            self._update_position_from_api(pos_data)

        # Load wallet
        wallet = await self._executor.get_wallet_balance()
        self._update_wallet_from_api(wallet)

        logger.info(
            f"Loaded {len(self._positions)} positions, "
            f"{len(self._wallets)} wallet entries"
        )

    async def _process_messages(self):
        """Process incoming WebSocket messages."""
        async for message in self._ws_client.messages():
            if not self._running:
                break

            try:
                if message.topic == "position":
                    await self._on_position_update(message)
                elif message.topic == "wallet":
                    await self._on_wallet_update(message)
                elif message.topic == "execution":
                    await self._on_execution(message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    # ==========================================================================
    # Position Tracking
    # ==========================================================================

    async def _on_position_update(self, message: WebSocketMessage):
        """Handle position update from WebSocket."""
        positions = parse_position_message(message)

        for pos in positions:
            symbol = pos["symbol"]
            size = pos["size"]

            if size == 0:
                # Position closed
                if symbol in self._positions:
                    del self._positions[symbol]
                    logger.info(f"📊 Position closed: {symbol}")
            else:
                # Position opened or updated
                side = PositionSide.LONG if pos["side"] == "buy" else PositionSide.SHORT

                snapshot = PositionSnapshot(
                    symbol=symbol,
                    side=side,
                    size=abs(size),
                    entry_price=pos["entry_price"],
                    mark_price=pos["mark_price"],
                    unrealized_pnl=pos["unrealized_pnl"],
                    realized_pnl=pos["cum_realized_pnl"],
                    leverage=pos["leverage"],
                    margin=pos["position_im"],
                    liquidation_price=pos["liq_price"],
                    take_profit=pos["take_profit"],
                    stop_loss=pos["stop_loss"],
                    position_value=pos["position_value"],
                )

                # Calculate ROE
                if snapshot.margin > 0:
                    snapshot.roe_percent = (
                        snapshot.unrealized_pnl / snapshot.margin * 100
                    )

                self._positions[symbol] = snapshot

                logger.debug(
                    f"📊 Position update: {symbol} {side.value} "
                    f"{size} @ {snapshot.entry_price} "
                    f"(PnL: {snapshot.unrealized_pnl:.2f})"
                )

        # Notify callbacks
        await self._notify_position_callbacks()

    def _update_position_from_api(self, data: dict):
        """Update position from REST API response."""
        symbol = data.get("symbol", "")
        size = float(data.get("size", 0))

        if size == 0:
            if symbol in self._positions:
                del self._positions[symbol]
            return

        side_str = data.get("side", "")
        side = PositionSide.LONG if side_str == "Buy" else PositionSide.SHORT

        snapshot = PositionSnapshot(
            symbol=symbol,
            side=side,
            size=abs(size),
            entry_price=float(data.get("avgPrice", 0) or 0),
            mark_price=float(data.get("markPrice", 0) or 0),
            unrealized_pnl=float(data.get("unrealisedPnl", 0) or 0),
            realized_pnl=float(data.get("cumRealisedPnl", 0) or 0),
            leverage=float(data.get("leverage", 1) or 1),
            margin=float(data.get("positionIM", 0) or 0),
            liquidation_price=float(data.get("liqPrice", 0) or 0)
            if data.get("liqPrice")
            else None,
            take_profit=float(data.get("takeProfit", 0) or 0)
            if data.get("takeProfit")
            else None,
            stop_loss=float(data.get("stopLoss", 0) or 0)
            if data.get("stopLoss")
            else None,
            position_value=float(data.get("positionValue", 0) or 0),
        )

        if snapshot.margin > 0:
            snapshot.roe_percent = snapshot.unrealized_pnl / snapshot.margin * 100

        self._positions[symbol] = snapshot

    # ==========================================================================
    # Wallet Tracking
    # ==========================================================================

    async def _on_wallet_update(self, message: WebSocketMessage):
        """Handle wallet update from WebSocket."""
        wallets = parse_wallet_message(message)

        for wallet in wallets:
            coin = wallet["coin"]

            snapshot = WalletSnapshot(
                coin=coin,
                total_balance=wallet["wallet_balance"],
                available_balance=wallet["available_balance"],
                used_margin=wallet["position_margin"] + wallet["order_margin"],
                unrealized_pnl=wallet["unrealized_pnl"],
                realized_pnl=wallet["cum_realized_pnl"],
            )

            self._wallets[coin] = snapshot

            logger.debug(
                f"💰 Wallet update: {coin} balance={snapshot.total_balance:.2f} "
                f"available={snapshot.available_balance:.2f}"
            )

        # Notify callbacks
        await self._notify_wallet_callbacks()

    def _update_wallet_from_api(self, data: dict):
        """Update wallet from REST API response."""
        account_list = data.get("list", [])

        for account in account_list:
            coins = account.get("coin", [])
            for coin_data in coins:
                coin = coin_data.get("coin", "")

                snapshot = WalletSnapshot(
                    coin=coin,
                    total_balance=float(coin_data.get("walletBalance", 0)),
                    available_balance=float(coin_data.get("availableToWithdraw", 0)),
                    used_margin=float(coin_data.get("totalPositionMM", 0) or 0),
                    unrealized_pnl=float(coin_data.get("unrealisedPnl", 0) or 0),
                    realized_pnl=float(coin_data.get("cumRealisedPnl", 0) or 0),
                )

                self._wallets[coin] = snapshot

    # ==========================================================================
    # Execution Tracking
    # ==========================================================================

    async def _on_execution(self, message: WebSocketMessage):
        """Handle execution/fill from WebSocket."""
        executions = parse_execution_message(message)

        for exec_data in executions:
            execution = TradeExecution(
                exec_id=exec_data["exec_id"],
                order_id=exec_data["order_id"],
                symbol=exec_data["symbol"],
                side=exec_data["side"],
                price=exec_data["exec_price"],
                qty=exec_data["exec_qty"],
                value=exec_data["exec_value"],
                fee=exec_data["exec_fee"],
                is_maker=exec_data["is_maker"],
                exec_time=datetime.fromtimestamp(
                    exec_data["exec_time"] / 1000, tz=UTC
                ),
            )

            self._executions.append(execution)

            # Trim old executions
            if len(self._executions) > self._max_executions:
                self._executions = self._executions[-self._max_executions :]

            logger.info(
                f"⚡ Execution: {execution.symbol} {execution.side} "
                f"{execution.qty} @ {execution.price} "
                f"(fee: {execution.fee:.4f})"
            )

        # Notify callbacks
        await self._notify_execution_callbacks(executions)

    # ==========================================================================
    # Position Operations
    # ==========================================================================

    async def close_position(
        self,
        symbol: str,
        qty: float | None = None,
    ) -> bool:
        """
        Close a position (fully or partially).

        Args:
            symbol: Trading pair
            qty: Quantity to close (None for full close)
        """
        position = self._positions.get(symbol)
        if not position:
            logger.warning(f"No position found for {symbol}")
            return False

        close_qty = qty if qty else position.size

        # Determine side for closing
        from backend.services.trading_engine_interface import OrderSide

        close_side = (
            OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY
        )

        result = await self._executor.place_market_order(
            symbol=symbol,
            side=close_side,
            qty=close_qty,
            reduce_only=True,
        )

        if result.success:
            logger.info(f"✅ Position close initiated: {symbol} {close_qty}")
        else:
            logger.error(f"❌ Failed to close position: {result.error_message}")

        return result.success

    async def close_all_positions(self) -> dict[str, bool]:
        """Close all open positions."""
        results = {}

        for symbol in list(self._positions.keys()):
            results[symbol] = await self.close_position(symbol)

        return results

    async def set_position_sl_tp(
        self,
        symbol: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> bool:
        """Set stop loss and/or take profit for a position."""
        position = self._positions.get(symbol)
        if not position:
            logger.warning(f"No position found for {symbol}")
            return False

        params = {
            "category": "linear",
            "symbol": symbol,
            "positionIdx": 0,  # One-way mode
        }

        if stop_loss is not None:
            params["stopLoss"] = str(stop_loss)
        if take_profit is not None:
            params["takeProfit"] = str(take_profit)

        response = await self._executor._signed_request(
            "POST", "/v5/position/trading-stop", params
        )

        success = response.get("retCode") == 0
        if success:
            logger.info(f"✅ SL/TP set for {symbol}: SL={stop_loss}, TP={take_profit}")
        else:
            logger.error(f"❌ Failed to set SL/TP: {response.get('retMsg')}")

        return success

    # ==========================================================================
    # Getters
    # ==========================================================================

    def get_position(self, symbol: str) -> PositionSnapshot | None:
        """Get position for a symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> list[PositionSnapshot]:
        """Get all open positions."""
        return list(self._positions.values())

    def get_wallet(self, coin: str = "USDT") -> WalletSnapshot | None:
        """Get wallet balance for a coin."""
        return self._wallets.get(coin)

    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L across all positions."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    def get_total_realized_pnl(self) -> float:
        """Get total realized P&L across all positions."""
        return sum(p.realized_pnl for p in self._positions.values())

    def get_total_pnl(self) -> float:
        """Get total P&L (unrealized + realized)."""
        return self.get_total_unrealized_pnl() + self.get_total_realized_pnl()

    def get_total_margin_used(self) -> float:
        """Get total margin used across all positions."""
        return sum(p.margin for p in self._positions.values())

    def get_available_balance(self, coin: str = "USDT") -> float:
        """Get available balance for trading."""
        wallet = self._wallets.get(coin)
        return wallet.available_balance if wallet else 0.0

    def get_equity(self, coin: str = "USDT") -> float:
        """Get total equity (balance + unrealized PnL)."""
        wallet = self._wallets.get(coin)
        return wallet.equity if wallet else 0.0

    def get_margin_ratio(self, coin: str = "USDT") -> float:
        """Get margin utilization ratio."""
        wallet = self._wallets.get(coin)
        return wallet.margin_ratio if wallet else 0.0

    def get_recent_executions(self, limit: int = 50) -> list[TradeExecution]:
        """Get recent trade executions."""
        return self._executions[-limit:]

    def get_position_summary(self) -> dict:
        """Get summary of all positions."""
        positions = self.get_all_positions()
        wallet = self.get_wallet(self.quote_currency)

        return {
            "position_count": len(positions),
            "positions": [p.to_dict() for p in positions],
            "total_unrealized_pnl": self.get_total_unrealized_pnl(),
            "total_realized_pnl": self.get_total_realized_pnl(),
            "total_pnl": self.get_total_pnl(),
            "total_margin_used": self.get_total_margin_used(),
            "wallet": wallet.to_dict() if wallet else None,
            "equity": self.get_equity(),
            "available_balance": self.get_available_balance(),
            "margin_ratio": self.get_margin_ratio(),
        }

    # ==========================================================================
    # Callbacks
    # ==========================================================================

    def on_position_update(self, callback: Callable):
        """Register callback for position updates."""
        self._position_callbacks.append(callback)

    def on_wallet_update(self, callback: Callable):
        """Register callback for wallet updates."""
        self._wallet_callbacks.append(callback)

    def on_execution(self, callback: Callable):
        """Register callback for trade executions."""
        self._execution_callbacks.append(callback)

    async def _notify_position_callbacks(self):
        """Notify all position callbacks."""
        summary = self.get_position_summary()
        for callback in self._position_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(summary)
                else:
                    callback(summary)
            except Exception as e:
                logger.error(f"Position callback error: {e}")

    async def _notify_wallet_callbacks(self):
        """Notify all wallet callbacks."""
        wallet = self.get_wallet(self.quote_currency)
        wallet_dict = wallet.to_dict() if wallet else {}

        for callback in self._wallet_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(wallet_dict)
                else:
                    callback(wallet_dict)
            except Exception as e:
                logger.error(f"Wallet callback error: {e}")

    async def _notify_execution_callbacks(self, executions: list):
        """Notify all execution callbacks."""
        for callback in self._execution_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(executions)
                else:
                    callback(executions)
            except Exception as e:
                logger.error(f"Execution callback error: {e}")
