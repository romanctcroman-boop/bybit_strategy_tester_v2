"""
Order Executor for Live Trading.

Handles order placement, modification, and cancellation via Bybit V5 API.

Features:
- Market, Limit, Stop-Loss, Take-Profit orders
- Bracket orders (entry + SL + TP)
- Order tracking and status updates
- Retry logic for transient failures
- Rate limiting compliance
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import uuid4

import httpx

from backend.services.trading_engine_interface import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TradeResult,
)

logger = logging.getLogger(__name__)


class TimeInForce(Enum):
    """Time in force options."""

    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    POST_ONLY = "PostOnly"  # Post Only (maker only)


class TriggerDirection(Enum):
    """Trigger direction for conditional orders."""

    RISE = 1  # Trigger when price rises
    FALL = 2  # Trigger when price falls


@dataclass
class OrderRequest:
    """Order request parameters."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: float
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    close_on_trigger: bool = False
    position_idx: int = 0  # 0=one-way, 1=buy-side, 2=sell-side (hedge mode)
    order_link_id: Optional[str] = None
    leverage: Optional[float] = None
    trigger_direction: Optional[TriggerDirection] = None


class OrderExecutor:
    """
    Order Executor for Bybit V5 API.

    Usage:
        executor = OrderExecutor(
            api_key="your_key",
            api_secret="your_secret",
            testnet=False
        )

        # Place market order
        result = await executor.place_market_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=0.001
        )

        # Place limit order with SL/TP
        result = await executor.place_limit_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=0.001,
            price=40000.0,
            stop_loss=39000.0,
            take_profit=42000.0
        )
    """

    # Bybit V5 API endpoints
    BASE_URL_MAINNET = "https://api.bybit.com"
    BASE_URL_TESTNET = "https://api-testnet.bybit.com"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        category: str = "linear",  # linear, inverse, spot, option
        recv_window: int = 5000,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.category = category
        self.recv_window = recv_window
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.base_url = self.BASE_URL_TESTNET if testnet else self.BASE_URL_MAINNET

        # Active orders cache
        self._active_orders: dict[str, Order] = {}

        # HTTP client
        self._client = httpx.AsyncClient(timeout=30.0)

        logger.info(
            f"OrderExecutor initialized (testnet={testnet}, category={category})"
        )

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()

    # ==========================================================================
    # Order Placement
    # ==========================================================================

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        reduce_only: bool = False,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_link_id: Optional[str] = None,
    ) -> TradeResult:
        """
        Place a market order.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: BUY or SELL
            qty: Order quantity
            reduce_only: Only reduce position, don't increase
            stop_loss: Stop loss price
            take_profit: Take profit price
            order_link_id: Custom order ID
        """
        request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            qty=qty,
            reduce_only=reduce_only,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_link_id=order_link_id or self._generate_order_link_id(),
        )
        return await self._place_order(request)

    async def place_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: float,
        time_in_force: TimeInForce = TimeInForce.GTC,
        reduce_only: bool = False,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_link_id: Optional[str] = None,
    ) -> TradeResult:
        """
        Place a limit order.

        Args:
            symbol: Trading pair
            side: BUY or SELL
            qty: Order quantity
            price: Limit price
            time_in_force: Order duration (GTC, IOC, FOK, PostOnly)
            reduce_only: Only reduce position
            stop_loss: Stop loss price
            take_profit: Take profit price
            order_link_id: Custom order ID
        """
        request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            qty=qty,
            price=price,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            stop_loss=stop_loss,
            take_profit=take_profit,
            order_link_id=order_link_id or self._generate_order_link_id(),
        )
        return await self._place_order(request)

    async def place_stop_market_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        trigger_price: float,
        trigger_direction: TriggerDirection = TriggerDirection.FALL,
        reduce_only: bool = True,
        order_link_id: Optional[str] = None,
    ) -> TradeResult:
        """
        Place a stop market order (for stop loss).

        Args:
            symbol: Trading pair
            side: SELL for long SL, BUY for short SL
            qty: Order quantity
            trigger_price: Price at which to trigger market order
            trigger_direction: RISE or FALL
            reduce_only: Only reduce position (default True for SL)
            order_link_id: Custom order ID
        """
        request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OrderType.STOP_MARKET,
            qty=qty,
            trigger_price=trigger_price,
            trigger_direction=trigger_direction,
            reduce_only=reduce_only,
            order_link_id=order_link_id or self._generate_order_link_id(),
        )
        return await self._place_order(request)

    async def place_stop_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: float,
        trigger_price: float,
        trigger_direction: TriggerDirection = TriggerDirection.FALL,
        reduce_only: bool = True,
        order_link_id: Optional[str] = None,
    ) -> TradeResult:
        """Place a stop limit order."""
        request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OrderType.STOP_LIMIT,
            qty=qty,
            price=price,
            trigger_price=trigger_price,
            trigger_direction=trigger_direction,
            reduce_only=reduce_only,
            order_link_id=order_link_id or self._generate_order_link_id(),
        )
        return await self._place_order(request)

    async def place_take_profit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        trigger_price: float,
        order_link_id: Optional[str] = None,
    ) -> TradeResult:
        """
        Place a take profit market order.

        Args:
            symbol: Trading pair
            side: SELL for long TP, BUY for short TP
            qty: Order quantity
            trigger_price: Take profit trigger price
        """
        # For TP, direction is opposite to SL
        direction = (
            TriggerDirection.RISE if side == OrderSide.SELL else TriggerDirection.FALL
        )

        request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OrderType.STOP_MARKET,  # TP is also stop-market in Bybit
            qty=qty,
            trigger_price=trigger_price,
            trigger_direction=direction,
            reduce_only=True,
            close_on_trigger=True,
            order_link_id=order_link_id or self._generate_order_link_id(),
        )
        return await self._place_order(request)

    async def place_bracket_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        entry_price: Optional[float] = None,  # None for market entry
        stop_loss: float = None,
        take_profit: float = None,
    ) -> list[TradeResult]:
        """
        Place a bracket order (entry + SL + TP).

        This places an entry order with attached SL and TP.

        Args:
            symbol: Trading pair
            side: BUY for long, SELL for short
            qty: Order quantity
            entry_price: Limit price for entry (None for market)
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            List of TradeResults [entry, sl, tp]
        """
        results = []

        # Entry order
        if entry_price:
            entry_result = await self.place_limit_order(
                symbol=symbol,
                side=side,
                qty=qty,
                price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        else:
            entry_result = await self.place_market_order(
                symbol=symbol,
                side=side,
                qty=qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        results.append(entry_result)
        return results

    async def _place_order(self, request: OrderRequest) -> TradeResult:
        """Internal method to place an order."""
        start_time = time.time()

        # Build order payload
        payload = self._build_order_payload(request)

        # Make API call with retry
        for attempt in range(self.max_retries):
            try:
                response = await self._signed_request(
                    "POST", "/v5/order/create", payload
                )

                latency_ms = (time.time() - start_time) * 1000

                if response.get("retCode") == 0:
                    result = response.get("result", {})
                    order_id = result.get("orderId", "")
                    order_link_id = result.get("orderLinkId", request.order_link_id)

                    order = Order(
                        order_id=order_id,
                        symbol=request.symbol,
                        side=request.side,
                        order_type=request.order_type,
                        quantity=request.qty,
                        price=request.price,
                        stop_price=request.trigger_price,
                        status=OrderStatus.SUBMITTED,
                        client_order_id=order_link_id,
                        metadata={
                            "stop_loss": request.stop_loss,
                            "take_profit": request.take_profit,
                        },
                    )

                    self._active_orders[order_id] = order

                    logger.info(
                        f"✅ Order placed: {request.symbol} {request.side.value} "
                        f"{request.qty} @ {request.price or 'MARKET'} "
                        f"(ID: {order_id}, latency: {latency_ms:.0f}ms)"
                    )

                    return TradeResult(
                        success=True,
                        order=order,
                        latency_ms=latency_ms,
                    )
                else:
                    error_code = str(response.get("retCode", ""))
                    error_msg = response.get("retMsg", "Unknown error")

                    # Check for retryable errors
                    if (
                        self._is_retryable_error(error_code)
                        and attempt < self.max_retries - 1
                    ):
                        logger.warning(
                            f"Retryable error on order (attempt {attempt + 1}): {error_msg}"
                        )
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                        continue

                    logger.error(f"❌ Order failed: {error_code} - {error_msg}")
                    return TradeResult(
                        success=False,
                        error_code=error_code,
                        error_message=error_msg,
                        latency_ms=latency_ms,
                    )

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(f"Order request exception: {e}")

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue

                return TradeResult(
                    success=False,
                    error_code="EXCEPTION",
                    error_message=str(e),
                    latency_ms=latency_ms,
                )

        return TradeResult(
            success=False,
            error_code="MAX_RETRIES",
            error_message="Max retries exceeded",
        )

    def _build_order_payload(self, request: OrderRequest) -> dict:
        """Build order API payload."""
        payload = {
            "category": self.category,
            "symbol": request.symbol,
            "side": "Buy"
            if request.side in (OrderSide.BUY, OrderSide.LONG)
            else "Sell",
            "orderType": self._map_order_type(request.order_type),
            "qty": str(request.qty),
            "timeInForce": request.time_in_force.value,
            "positionIdx": request.position_idx,
        }

        if request.price:
            payload["price"] = str(request.price)

        if request.trigger_price:
            payload["triggerPrice"] = str(request.trigger_price)
            if request.trigger_direction:
                payload["triggerDirection"] = request.trigger_direction.value

        if request.stop_loss:
            payload["stopLoss"] = str(request.stop_loss)

        if request.take_profit:
            payload["takeProfit"] = str(request.take_profit)

        if request.reduce_only:
            payload["reduceOnly"] = True

        if request.close_on_trigger:
            payload["closeOnTrigger"] = True

        if request.order_link_id:
            payload["orderLinkId"] = request.order_link_id

        return payload

    def _map_order_type(self, order_type: OrderType) -> str:
        """Map internal order type to Bybit API format."""
        mapping = {
            OrderType.MARKET: "Market",
            OrderType.LIMIT: "Limit",
            OrderType.STOP_MARKET: "Market",  # Conditional market
            OrderType.STOP_LIMIT: "Limit",  # Conditional limit
            OrderType.TRAILING_STOP: "Market",
        }
        return mapping.get(order_type, "Market")

    def _is_retryable_error(self, error_code: str) -> bool:
        """Check if error is retryable."""
        retryable_codes = {
            "10002",  # Request timeout
            "10006",  # Rate limit
            "10016",  # Server error
            "110001",  # Order not modified
            "110003",  # Unknown order
        }
        return error_code in retryable_codes

    # ==========================================================================
    # Order Management
    # ==========================================================================

    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None,
    ) -> TradeResult:
        """
        Cancel an order.

        Args:
            symbol: Trading pair
            order_id: Exchange order ID
            order_link_id: Custom order ID
        """
        if not order_id and not order_link_id:
            return TradeResult(
                success=False,
                error_code="INVALID_PARAMS",
                error_message="Either order_id or order_link_id required",
            )

        payload = {
            "category": self.category,
            "symbol": symbol,
        }

        if order_id:
            payload["orderId"] = order_id
        if order_link_id:
            payload["orderLinkId"] = order_link_id

        response = await self._signed_request("POST", "/v5/order/cancel", payload)

        if response.get("retCode") == 0:
            if order_id and order_id in self._active_orders:
                self._active_orders[order_id].status = OrderStatus.CANCELLED

            logger.info(f"✅ Order cancelled: {order_id or order_link_id}")
            return TradeResult(success=True)
        else:
            error_msg = response.get("retMsg", "Unknown error")
            logger.error(f"❌ Cancel failed: {error_msg}")
            return TradeResult(
                success=False,
                error_code=str(response.get("retCode", "")),
                error_message=error_msg,
            )

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> TradeResult:
        """Cancel all open orders, optionally filtered by symbol."""
        payload = {"category": self.category}

        if symbol:
            payload["symbol"] = symbol

        response = await self._signed_request("POST", "/v5/order/cancel-all", payload)

        if response.get("retCode") == 0:
            result = response.get("result", {})
            cancelled = result.get("list", [])
            logger.info(f"✅ Cancelled {len(cancelled)} orders")
            return TradeResult(success=True, metadata={"cancelled": len(cancelled)})
        else:
            return TradeResult(
                success=False,
                error_code=str(response.get("retCode", "")),
                error_message=response.get("retMsg", "Unknown error"),
            )

    async def amend_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None,
        qty: Optional[float] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> TradeResult:
        """
        Amend an existing order.

        Args:
            symbol: Trading pair
            order_id: Exchange order ID
            order_link_id: Custom order ID
            qty: New quantity
            price: New price
            trigger_price: New trigger price
            stop_loss: New stop loss
            take_profit: New take profit
        """
        payload = {
            "category": self.category,
            "symbol": symbol,
        }

        if order_id:
            payload["orderId"] = order_id
        if order_link_id:
            payload["orderLinkId"] = order_link_id
        if qty:
            payload["qty"] = str(qty)
        if price:
            payload["price"] = str(price)
        if trigger_price:
            payload["triggerPrice"] = str(trigger_price)
        if stop_loss:
            payload["stopLoss"] = str(stop_loss)
        if take_profit:
            payload["takeProfit"] = str(take_profit)

        response = await self._signed_request("POST", "/v5/order/amend", payload)

        if response.get("retCode") == 0:
            logger.info(f"✅ Order amended: {order_id or order_link_id}")
            return TradeResult(success=True)
        else:
            return TradeResult(
                success=False,
                error_code=str(response.get("retCode", "")),
                error_message=response.get("retMsg", "Unknown error"),
            )

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Get all open orders."""
        payload = {"category": self.category}
        if symbol:
            payload["symbol"] = symbol

        response = await self._signed_request("GET", "/v5/order/realtime", payload)

        if response.get("retCode") == 0:
            orders = []
            for item in response.get("result", {}).get("list", []):
                order = self._parse_order_response(item)
                orders.append(order)
            return orders
        else:
            logger.error(f"Failed to get orders: {response.get('retMsg')}")
            return []

    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> list[Order]:
        """Get order history."""
        payload = {
            "category": self.category,
            "limit": limit,
        }
        if symbol:
            payload["symbol"] = symbol

        response = await self._signed_request("GET", "/v5/order/history", payload)

        if response.get("retCode") == 0:
            orders = []
            for item in response.get("result", {}).get("list", []):
                order = self._parse_order_response(item)
                orders.append(order)
            return orders
        else:
            logger.error(f"Failed to get order history: {response.get('retMsg')}")
            return []

    def _parse_order_response(self, data: dict) -> Order:
        """Parse order from API response."""
        status_map = {
            "New": OrderStatus.SUBMITTED,
            "PartiallyFilled": OrderStatus.PARTIALLY_FILLED,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Rejected": OrderStatus.REJECTED,
            "Expired": OrderStatus.EXPIRED,
        }

        side_map = {
            "Buy": OrderSide.BUY,
            "Sell": OrderSide.SELL,
        }

        type_map = {
            "Market": OrderType.MARKET,
            "Limit": OrderType.LIMIT,
        }

        return Order(
            order_id=data.get("orderId", ""),
            symbol=data.get("symbol", ""),
            side=side_map.get(data.get("side", ""), OrderSide.BUY),
            order_type=type_map.get(data.get("orderType", ""), OrderType.MARKET),
            quantity=float(data.get("qty", 0)),
            price=float(data.get("price", 0)) if data.get("price") else None,
            status=status_map.get(data.get("orderStatus", ""), OrderStatus.PENDING),
            filled_quantity=float(data.get("cumExecQty", 0)),
            average_price=float(data.get("avgPrice", 0))
            if data.get("avgPrice")
            else 0.0,
            exchange_order_id=data.get("orderId", ""),
            client_order_id=data.get("orderLinkId", ""),
        )

    # ==========================================================================
    # API Utilities
    # ==========================================================================

    async def _signed_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
    ) -> dict:
        """Make a signed API request."""
        params = params or {}
        timestamp = str(int(time.time() * 1000))

        # Generate signature
        if method == "GET":
            param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            sign_str = f"{timestamp}{self.api_key}{self.recv_window}{param_str}"
        else:
            param_str = json.dumps(params)
            sign_str = f"{timestamp}{self.api_key}{self.recv_window}{param_str}"

        signature = hmac.new(
            self.api_secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}{endpoint}"

        if method == "GET":
            response = await self._client.get(url, params=params, headers=headers)
        else:
            response = await self._client.post(url, json=params, headers=headers)

        return response.json()

    def _generate_order_link_id(self) -> str:
        """Generate unique order link ID."""
        return f"bst_{uuid4().hex[:16]}"

    # ==========================================================================
    # Account Info
    # ==========================================================================

    async def get_wallet_balance(self, account_type: str = "UNIFIED") -> dict:
        """Get wallet balance."""
        response = await self._signed_request(
            "GET", "/v5/account/wallet-balance", {"accountType": account_type}
        )

        if response.get("retCode") == 0:
            return response.get("result", {})
        else:
            logger.error(f"Failed to get balance: {response.get('retMsg')}")
            return {}

    async def get_positions(self, symbol: Optional[str] = None) -> list[dict]:
        """Get positions."""
        params = {"category": self.category}
        if symbol:
            params["symbol"] = symbol

        response = await self._signed_request("GET", "/v5/position/list", params)

        if response.get("retCode") == 0:
            return response.get("result", {}).get("list", [])
        else:
            logger.error(f"Failed to get positions: {response.get('retMsg')}")
            return []

    async def set_leverage(self, symbol: str, leverage: float) -> bool:
        """Set leverage for a symbol."""
        response = await self._signed_request(
            "POST",
            "/v5/position/set-leverage",
            {
                "category": self.category,
                "symbol": symbol,
                "buyLeverage": str(leverage),
                "sellLeverage": str(leverage),
            },
        )

        success = response.get("retCode") == 0
        if success:
            logger.info(f"✅ Leverage set to {leverage}x for {symbol}")
        else:
            logger.error(f"Failed to set leverage: {response.get('retMsg')}")

        return success

    async def set_position_mode(self, hedge_mode: bool = False) -> bool:
        """
        Set position mode.

        Args:
            hedge_mode: True for hedge mode, False for one-way mode
        """
        response = await self._signed_request(
            "POST",
            "/v5/position/switch-mode",
            {
                "category": self.category,
                "mode": 3 if hedge_mode else 0,  # 0=one-way, 3=hedge
            },
        )

        success = response.get("retCode") == 0
        if success:
            mode_str = "hedge" if hedge_mode else "one-way"
            logger.info(f"✅ Position mode set to {mode_str}")

        return success
