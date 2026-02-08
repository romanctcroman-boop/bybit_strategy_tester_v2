"""
Multi-Exchange Arbitrage Module for Universal Math Engine v2.3.

This module provides cross-exchange arbitrage capabilities:
1. ExchangeConnector - Unified interface for multiple exchanges
2. ArbitrageDetector - Real-time arbitrage opportunity detection
3. CrossExchangeTrader - Synchronized execution across exchanges
4. FeeCalculator - Comprehensive fee and profit calculation
5. LatencySimulator - Network latency modeling

Supported Exchanges:
- Bybit (primary)
- Binance
- OKX
- Kraken
- Coinbase

Author: Universal Math Engine Team
Version: 2.3.0
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np

# =============================================================================
# 1. EXCHANGE CONNECTOR
# =============================================================================


class ExchangeName(Enum):
    """Supported exchanges."""

    BYBIT = "bybit"
    BINANCE = "binance"
    OKX = "okx"
    KRAKEN = "kraken"
    COINBASE = "coinbase"
    BITGET = "bitget"
    HUOBI = "huobi"


@dataclass
class ExchangeFees:
    """Fee structure for an exchange."""

    maker_fee: float = 0.0001  # 0.01%
    taker_fee: float = 0.0006  # 0.06%
    withdrawal_fee: float = 0.0005  # BTC
    deposit_fee: float = 0.0
    funding_rate: float = 0.0001  # 8h funding


@dataclass
class ExchangeTicker:
    """Ticker data from an exchange."""

    exchange: ExchangeName
    symbol: str
    timestamp: int
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    last_price: float
    volume_24h: float

    @property
    def mid_price(self) -> float:
        """Get mid price."""
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        """Get bid-ask spread."""
        return self.ask - self.bid

    @property
    def spread_bps(self) -> float:
        """Get spread in basis points."""
        return (self.spread / self.mid_price) * 10000


@dataclass
class ExchangeBalance:
    """Balance on an exchange."""

    exchange: ExchangeName
    currency: str
    available: float
    locked: float
    total: float


@dataclass
class ExchangeConfig:
    """Configuration for exchange connection."""

    exchange: ExchangeName
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    rate_limit: int = 10  # requests per second
    timeout: float = 5.0  # seconds


class ExchangeConnector:
    """
    Unified interface for connecting to multiple exchanges.

    Features:
    - Standardized API across exchanges
    - Rate limiting
    - Error handling
    - Testnet support
    """

    # Default fee structures
    DEFAULT_FEES = {
        ExchangeName.BYBIT: ExchangeFees(0.0001, 0.0006, 0.0005),
        ExchangeName.BINANCE: ExchangeFees(0.0001, 0.0005, 0.0004),
        ExchangeName.OKX: ExchangeFees(0.0002, 0.0005, 0.0004),
        ExchangeName.KRAKEN: ExchangeFees(0.0016, 0.0026, 0.00015),
        ExchangeName.COINBASE: ExchangeFees(0.004, 0.006, 0.0),
        ExchangeName.BITGET: ExchangeFees(0.0001, 0.0006, 0.0005),
        ExchangeName.HUOBI: ExchangeFees(0.0002, 0.0004, 0.0005),
    }

    def __init__(self, config: ExchangeConfig):
        """Initialize exchange connector."""
        self.config = config
        self.fees = self.DEFAULT_FEES.get(config.exchange, ExchangeFees())
        self._last_request_time: float = 0
        self._connected = False

    def connect(self) -> bool:
        """Connect to exchange."""
        # In real implementation, would authenticate with API
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from exchange."""
        self._connected = False

    def get_ticker(self, symbol: str) -> ExchangeTicker | None:
        """
        Get current ticker for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            ExchangeTicker or None if not available
        """
        # Simulated ticker for backtesting
        return ExchangeTicker(
            exchange=self.config.exchange,
            symbol=symbol,
            timestamp=int(datetime.now().timestamp() * 1000),
            bid=50000.0,
            ask=50010.0,
            bid_size=10.0,
            ask_size=10.0,
            last_price=50005.0,
            volume_24h=1000000.0,
        )

    def get_balance(self, currency: str) -> ExchangeBalance | None:
        """Get balance for a currency."""
        return ExchangeBalance(
            exchange=self.config.exchange,
            currency=currency,
            available=10.0,
            locked=0.0,
            total=10.0,
        )

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        """Place an order on the exchange."""
        return {
            "order_id": f"{self.config.exchange.value}_{int(datetime.now().timestamp())}",
            "status": "filled",
            "filled_qty": quantity,
            "filled_price": price or 50000.0,
        }


# =============================================================================
# 2. ARBITRAGE DETECTOR
# =============================================================================


class ArbitrageType(Enum):
    """Types of arbitrage opportunities."""

    SPATIAL = "spatial"  # Same asset, different exchanges
    TRIANGULAR = "triangular"  # Three pairs on same exchange
    STATISTICAL = "statistical"  # Mean reversion based
    FUNDING = "funding"  # Funding rate arbitrage
    CROSS_MARGIN = "cross_margin"  # Spot vs perp


@dataclass
class ArbitrageOpportunity:
    """Detected arbitrage opportunity."""

    arb_type: ArbitrageType
    timestamp: int

    # Exchanges involved
    buy_exchange: ExchangeName
    sell_exchange: ExchangeName

    # Symbol(s) involved
    symbol: str
    symbol_leg2: str | None = None
    symbol_leg3: str | None = None

    # Prices
    buy_price: float = 0.0
    sell_price: float = 0.0

    # Spread and profit
    gross_spread: float = 0.0  # Before fees
    net_spread: float = 0.0  # After fees
    estimated_profit_usd: float = 0.0

    # Execution details
    max_size: float = 0.0  # Limited by liquidity
    confidence: float = 0.0  # 0-1 confidence score
    ttl_ms: int = 100  # Time to live in milliseconds

    @property
    def is_profitable(self) -> bool:
        """Check if opportunity is profitable after fees."""
        return self.net_spread > 0

    @property
    def spread_bps(self) -> float:
        """Get spread in basis points."""
        mid = (self.buy_price + self.sell_price) / 2
        return (self.sell_price - self.buy_price) / mid * 10000


@dataclass
class ArbitrageConfig:
    """Configuration for arbitrage detection."""

    # Minimum spread to consider (after fees)
    min_net_spread_bps: float = 5.0  # 0.05%

    # Maximum latency tolerance
    max_latency_ms: int = 100

    # Minimum confidence score
    min_confidence: float = 0.7

    # Enable specific arbitrage types
    enable_spatial: bool = True
    enable_triangular: bool = True
    enable_funding: bool = True

    # Risk limits
    max_position_usd: float = 10000.0
    max_exposure_per_exchange: float = 0.3  # 30% of capital


class ArbitrageDetector:
    """
    Detects arbitrage opportunities across exchanges.

    Features:
    - Spatial arbitrage (cross-exchange)
    - Triangular arbitrage
    - Funding rate arbitrage
    - Real-time opportunity scoring
    """

    def __init__(
        self,
        connectors: list[ExchangeConnector],
        config: ArbitrageConfig | None = None,
    ):
        """Initialize arbitrage detector."""
        self.connectors = {c.config.exchange: c for c in connectors}
        self.config = config or ArbitrageConfig()
        self._opportunities: list[ArbitrageOpportunity] = []

    def scan_spatial(
        self,
        tickers: dict[ExchangeName, ExchangeTicker],
    ) -> list[ArbitrageOpportunity]:
        """
        Scan for spatial arbitrage opportunities.

        Args:
            tickers: Ticker data from each exchange

        Returns:
            List of detected opportunities
        """
        opportunities = []
        exchanges = list(tickers.keys())

        for i, buy_ex in enumerate(exchanges):
            for sell_ex in exchanges[i + 1 :]:
                buy_ticker = tickers[buy_ex]
                sell_ticker = tickers[sell_ex]

                # Check buy on buy_ex, sell on sell_ex
                opp1 = self._check_spatial_pair(
                    buy_ticker, sell_ticker, buy_ex, sell_ex
                )
                if opp1 and opp1.is_profitable:
                    opportunities.append(opp1)

                # Check reverse direction
                opp2 = self._check_spatial_pair(
                    sell_ticker, buy_ticker, sell_ex, buy_ex
                )
                if opp2 and opp2.is_profitable:
                    opportunities.append(opp2)

        return opportunities

    def _check_spatial_pair(
        self,
        buy_ticker: ExchangeTicker,
        sell_ticker: ExchangeTicker,
        buy_ex: ExchangeName,
        sell_ex: ExchangeName,
    ) -> ArbitrageOpportunity | None:
        """Check spatial arbitrage between two exchanges."""
        # Buy at ask, sell at bid
        buy_price = buy_ticker.ask
        sell_price = sell_ticker.bid

        if sell_price <= buy_price:
            return None  # No opportunity

        gross_spread = (sell_price - buy_price) / buy_price

        # Calculate fees
        buy_fees = self.connectors[buy_ex].fees.taker_fee
        sell_fees = self.connectors[sell_ex].fees.taker_fee
        total_fees = buy_fees + sell_fees

        net_spread = gross_spread - total_fees

        if net_spread * 10000 < self.config.min_net_spread_bps:
            return None

        # Calculate max size (limited by order book depth)
        max_size = min(buy_ticker.ask_size, sell_ticker.bid_size)

        # Confidence based on spread and liquidity
        confidence = min(
            1.0,
            (net_spread * 10000 / self.config.min_net_spread_bps)
            * (max_size / 1.0),  # Normalize by 1 BTC
        )

        return ArbitrageOpportunity(
            arb_type=ArbitrageType.SPATIAL,
            timestamp=int(datetime.now().timestamp() * 1000),
            buy_exchange=buy_ex,
            sell_exchange=sell_ex,
            symbol=buy_ticker.symbol,
            buy_price=buy_price,
            sell_price=sell_price,
            gross_spread=gross_spread,
            net_spread=net_spread,
            estimated_profit_usd=net_spread * buy_price * max_size,
            max_size=max_size,
            confidence=confidence,
        )

    def scan_triangular(
        self,
        exchange: ExchangeName,
        tickers: dict[str, ExchangeTicker],
    ) -> list[ArbitrageOpportunity]:
        """
        Scan for triangular arbitrage on a single exchange.

        Example: BTC/USDT -> ETH/BTC -> ETH/USDT -> USDT

        Args:
            exchange: Exchange to scan
            tickers: Tickers for all pairs on exchange

        Returns:
            List of triangular arbitrage opportunities
        """
        opportunities = []

        # Common triangular paths
        triangles = [
            ("BTCUSDT", "ETHBTC", "ETHUSDT"),
            ("BTCUSDT", "BNBBTC", "BNBUSDT"),
            ("ETHUSDT", "BNBETH", "BNBUSDT"),
        ]

        for pair1, pair2, pair3 in triangles:
            if pair1 not in tickers or pair2 not in tickers or pair3 not in tickers:
                continue

            t1, t2, t3 = tickers[pair1], tickers[pair2], tickers[pair3]

            # Path: USDT -> BTC -> ETH -> USDT
            # 1. Buy BTC with USDT (pay ask)
            # 2. Buy ETH with BTC (pay ask)
            # 3. Sell ETH for USDT (get bid)

            start_amount = 1000  # USDT

            # Step 1: USDT -> BTC
            btc_amount = start_amount / t1.ask

            # Step 2: BTC -> ETH
            eth_amount = btc_amount / t2.ask

            # Step 3: ETH -> USDT
            end_amount = eth_amount * t3.bid

            # Calculate profit
            gross_profit = (end_amount - start_amount) / start_amount

            # Fees (3 trades)
            fees = self.connectors[exchange].fees
            total_fees = fees.taker_fee * 3

            net_profit = gross_profit - total_fees

            if net_profit * 10000 >= self.config.min_net_spread_bps:
                opportunities.append(
                    ArbitrageOpportunity(
                        arb_type=ArbitrageType.TRIANGULAR,
                        timestamp=int(datetime.now().timestamp() * 1000),
                        buy_exchange=exchange,
                        sell_exchange=exchange,
                        symbol=pair1,
                        symbol_leg2=pair2,
                        symbol_leg3=pair3,
                        buy_price=t1.ask,
                        sell_price=t3.bid,
                        gross_spread=gross_profit,
                        net_spread=net_profit,
                        estimated_profit_usd=net_profit * start_amount,
                        max_size=min(t1.ask_size, t2.ask_size, t3.bid_size),
                        confidence=0.8,
                    )
                )

        return opportunities

    def scan_funding(
        self,
        spot_tickers: dict[ExchangeName, ExchangeTicker],
        perp_tickers: dict[ExchangeName, ExchangeTicker],
        funding_rates: dict[ExchangeName, float],
    ) -> list[ArbitrageOpportunity]:
        """
        Scan for funding rate arbitrage.

        Strategy: Long spot, short perp when funding is positive (shorts pay longs).

        Args:
            spot_tickers: Spot market tickers
            perp_tickers: Perpetual futures tickers
            funding_rates: Current funding rates per exchange

        Returns:
            List of funding arbitrage opportunities
        """
        opportunities = []

        for exchange in spot_tickers:
            if exchange not in perp_tickers or exchange not in funding_rates:
                continue

            spot = spot_tickers[exchange]
            perp = perp_tickers[exchange]
            funding = funding_rates[exchange]

            # Basis = (perp - spot) / spot
            basis = (perp.mid_price - spot.mid_price) / spot.mid_price

            # Annualized funding (3 times per day * 365 days)
            annual_funding = funding * 3 * 365

            # If funding positive and basis reasonable, go long spot short perp
            if funding > 0.0001:  # Meaningful positive funding
                fees = self.connectors[exchange].fees
                total_fees = fees.taker_fee * 2  # Entry fees

                # Expected profit per funding period
                net_profit_8h = funding - total_fees / 365 / 3

                if net_profit_8h > 0:
                    opportunities.append(
                        ArbitrageOpportunity(
                            arb_type=ArbitrageType.FUNDING,
                            timestamp=int(datetime.now().timestamp() * 1000),
                            buy_exchange=exchange,
                            sell_exchange=exchange,
                            symbol=spot.symbol,
                            buy_price=spot.ask,  # Long spot
                            sell_price=perp.bid,  # Short perp
                            gross_spread=funding,
                            net_spread=net_profit_8h,
                            estimated_profit_usd=net_profit_8h * 10000,  # Per $10k
                            max_size=min(spot.ask_size, perp.bid_size),
                            confidence=0.9,
                            ttl_ms=8 * 3600 * 1000,  # 8 hours
                        )
                    )

        return opportunities


# =============================================================================
# 3. CROSS-EXCHANGE TRADER
# =============================================================================


@dataclass
class ArbitrageExecution:
    """Result of arbitrage execution."""

    opportunity: ArbitrageOpportunity
    timestamp: int

    # Order details
    buy_order_id: str
    sell_order_id: str

    # Fill details
    buy_filled_qty: float
    buy_filled_price: float
    sell_filled_qty: float
    sell_filled_price: float

    # Actual profit
    gross_profit: float
    fees_paid: float
    net_profit: float

    # Status
    success: bool
    error_message: str | None = None

    # Timing
    execution_time_ms: int = 0


@dataclass
class TraderConfig:
    """Configuration for cross-exchange trader."""

    # Execution settings
    max_slippage_bps: float = 5.0  # Max acceptable slippage
    order_timeout_ms: int = 1000
    retry_attempts: int = 2

    # Risk settings
    max_position_per_trade: float = 1.0  # BTC
    max_daily_loss: float = 100.0  # USD

    # Execution mode
    parallel_execution: bool = True  # Execute buy/sell simultaneously
    use_limit_orders: bool = False  # Use market orders for speed


class CrossExchangeTrader:
    """
    Executes arbitrage trades across multiple exchanges.

    Features:
    - Parallel order execution
    - Slippage protection
    - Position management
    - PnL tracking
    """

    def __init__(
        self,
        connectors: dict[ExchangeName, ExchangeConnector],
        config: TraderConfig | None = None,
    ):
        """Initialize cross-exchange trader."""
        self.connectors = connectors
        self.config = config or TraderConfig()
        self._executions: list[ArbitrageExecution] = []
        self._daily_pnl: float = 0.0

    def execute(
        self,
        opportunity: ArbitrageOpportunity,
        size: float | None = None,
    ) -> ArbitrageExecution:
        """
        Execute an arbitrage opportunity.

        Args:
            opportunity: Detected opportunity
            size: Override size (default: max_size from opportunity)

        Returns:
            ArbitrageExecution with results
        """
        import time

        start_time = time.time()

        # Determine size
        trade_size = min(
            size or opportunity.max_size,
            self.config.max_position_per_trade,
        )

        # Check daily loss limit
        if self._daily_pnl < -self.config.max_daily_loss:
            return ArbitrageExecution(
                opportunity=opportunity,
                timestamp=int(time.time() * 1000),
                buy_order_id="",
                sell_order_id="",
                buy_filled_qty=0,
                buy_filled_price=0,
                sell_filled_qty=0,
                sell_filled_price=0,
                gross_profit=0,
                fees_paid=0,
                net_profit=0,
                success=False,
                error_message="Daily loss limit reached",
            )

        try:
            # Get connectors
            buy_connector = self.connectors[opportunity.buy_exchange]
            sell_connector = self.connectors[opportunity.sell_exchange]

            # Execute orders
            if self.config.parallel_execution:
                # Parallel execution (simulated)
                buy_result = buy_connector.place_order(
                    symbol=opportunity.symbol,
                    side="buy",
                    order_type="market",
                    quantity=trade_size,
                    price=opportunity.buy_price,
                )
                sell_result = sell_connector.place_order(
                    symbol=opportunity.symbol,
                    side="sell",
                    order_type="market",
                    quantity=trade_size,
                    price=opportunity.sell_price,
                )
            else:
                # Sequential execution
                buy_result = buy_connector.place_order(
                    symbol=opportunity.symbol,
                    side="buy",
                    order_type="market",
                    quantity=trade_size,
                )
                sell_result = sell_connector.place_order(
                    symbol=opportunity.symbol,
                    side="sell",
                    order_type="market",
                    quantity=trade_size,
                )

            # Calculate actual profit
            buy_cost = buy_result["filled_qty"] * buy_result["filled_price"]
            sell_revenue = sell_result["filled_qty"] * sell_result["filled_price"]

            gross_profit = sell_revenue - buy_cost

            # Calculate fees
            buy_fees = buy_cost * buy_connector.fees.taker_fee
            sell_fees = sell_revenue * sell_connector.fees.taker_fee
            total_fees = buy_fees + sell_fees

            net_profit = gross_profit - total_fees

            # Update daily PnL
            self._daily_pnl += net_profit

            execution_time = int((time.time() - start_time) * 1000)

            execution = ArbitrageExecution(
                opportunity=opportunity,
                timestamp=int(time.time() * 1000),
                buy_order_id=buy_result["order_id"],
                sell_order_id=sell_result["order_id"],
                buy_filled_qty=buy_result["filled_qty"],
                buy_filled_price=buy_result["filled_price"],
                sell_filled_qty=sell_result["filled_qty"],
                sell_filled_price=sell_result["filled_price"],
                gross_profit=gross_profit,
                fees_paid=total_fees,
                net_profit=net_profit,
                success=True,
                execution_time_ms=execution_time,
            )

            self._executions.append(execution)
            return execution

        except Exception as e:
            return ArbitrageExecution(
                opportunity=opportunity,
                timestamp=int(time.time() * 1000),
                buy_order_id="",
                sell_order_id="",
                buy_filled_qty=0,
                buy_filled_price=0,
                sell_filled_qty=0,
                sell_filled_price=0,
                gross_profit=0,
                fees_paid=0,
                net_profit=0,
                success=False,
                error_message=str(e),
            )

    def get_statistics(self) -> dict[str, Any]:
        """Get trading statistics."""
        if not self._executions:
            return {
                "total_trades": 0,
                "successful_trades": 0,
                "total_profit": 0,
                "total_fees": 0,
                "avg_profit_per_trade": 0,
            }

        successful = [e for e in self._executions if e.success]

        return {
            "total_trades": len(self._executions),
            "successful_trades": len(successful),
            "success_rate": len(successful) / len(self._executions),
            "total_profit": sum(e.net_profit for e in successful),
            "total_fees": sum(e.fees_paid for e in successful),
            "avg_profit_per_trade": (
                sum(e.net_profit for e in successful) / len(successful)
                if successful
                else 0
            ),
            "avg_execution_time_ms": (
                sum(e.execution_time_ms for e in successful) / len(successful)
                if successful
                else 0
            ),
        }

    def reset_daily(self) -> None:
        """Reset daily statistics."""
        self._daily_pnl = 0.0


# =============================================================================
# 4. FEE CALCULATOR
# =============================================================================


@dataclass
class FeeBreakdown:
    """Detailed fee breakdown."""

    # Trading fees
    maker_fee: float = 0.0
    taker_fee: float = 0.0

    # Transfer fees
    withdrawal_fee: float = 0.0
    deposit_fee: float = 0.0

    # Network fees
    gas_fee: float = 0.0

    # Other fees
    funding_cost: float = 0.0
    borrowing_cost: float = 0.0

    @property
    def total_fees(self) -> float:
        """Get total fees."""
        return (
            self.maker_fee
            + self.taker_fee
            + self.withdrawal_fee
            + self.deposit_fee
            + self.gas_fee
            + self.funding_cost
            + self.borrowing_cost
        )


class FeeCalculator:
    """
    Comprehensive fee calculator for arbitrage.

    Features:
    - Multi-exchange fee comparison
    - Transfer cost estimation
    - Break-even spread calculation
    - Fee optimization suggestions
    """

    def __init__(
        self,
        exchange_fees: dict[ExchangeName, ExchangeFees],
    ):
        """Initialize fee calculator."""
        self.exchange_fees = exchange_fees

    def calculate_trade_fees(
        self,
        exchange: ExchangeName,
        size_usd: float,
        is_maker: bool = False,
    ) -> FeeBreakdown:
        """Calculate fees for a single trade."""
        fees = self.exchange_fees.get(exchange, ExchangeFees())

        fee_rate = fees.maker_fee if is_maker else fees.taker_fee

        return FeeBreakdown(
            maker_fee=size_usd * fees.maker_fee if is_maker else 0,
            taker_fee=size_usd * fees.taker_fee if not is_maker else 0,
        )

    def calculate_arbitrage_fees(
        self,
        buy_exchange: ExchangeName,
        sell_exchange: ExchangeName,
        size_usd: float,
        include_transfer: bool = False,
        transfer_currency: str = "BTC",
        current_price: float = 50000.0,
    ) -> FeeBreakdown:
        """Calculate total fees for an arbitrage trade."""
        buy_fees = self.exchange_fees.get(buy_exchange, ExchangeFees())
        sell_fees = self.exchange_fees.get(sell_exchange, ExchangeFees())

        breakdown = FeeBreakdown(
            taker_fee=size_usd * (buy_fees.taker_fee + sell_fees.taker_fee),
        )

        if include_transfer:
            # Transfer from sell exchange to buy exchange
            if transfer_currency == "BTC":
                breakdown.withdrawal_fee = sell_fees.withdrawal_fee * current_price
            else:
                breakdown.withdrawal_fee = sell_fees.withdrawal_fee

        return breakdown

    def calculate_break_even_spread(
        self,
        buy_exchange: ExchangeName,
        sell_exchange: ExchangeName,
        include_transfer: bool = False,
    ) -> float:
        """
        Calculate minimum spread needed to break even.

        Returns:
            Break-even spread in basis points
        """
        buy_fees = self.exchange_fees.get(buy_exchange, ExchangeFees())
        sell_fees = self.exchange_fees.get(sell_exchange, ExchangeFees())

        total_fee_rate = buy_fees.taker_fee + sell_fees.taker_fee

        if include_transfer:
            # Estimate transfer cost as percentage
            transfer_cost = 0.0005  # 0.05% average
            total_fee_rate += transfer_cost

        return total_fee_rate * 10000  # Convert to bps

    def compare_exchanges(
        self,
        size_usd: float = 10000.0,
    ) -> dict[ExchangeName, FeeBreakdown]:
        """Compare fees across all exchanges."""
        return {
            exchange: self.calculate_trade_fees(exchange, size_usd)
            for exchange in self.exchange_fees
        }


# =============================================================================
# 5. LATENCY SIMULATOR
# =============================================================================


@dataclass
class LatencyProfile:
    """Latency profile for an exchange."""

    exchange: ExchangeName

    # API latencies (ms)
    rest_latency_mean: float = 50.0
    rest_latency_std: float = 20.0
    ws_latency_mean: float = 10.0
    ws_latency_std: float = 5.0

    # Order latencies (ms)
    order_submit_mean: float = 30.0
    order_submit_std: float = 15.0
    order_fill_mean: float = 5.0
    order_fill_std: float = 3.0

    # Network jitter
    jitter_probability: float = 0.05
    jitter_multiplier: float = 3.0


class LatencySimulator:
    """
    Simulates network latency for realistic backtesting.

    Features:
    - Exchange-specific latency profiles
    - Network jitter simulation
    - Co-location effects
    - Latency-adjusted execution
    """

    def __init__(
        self,
        profiles: dict[ExchangeName, LatencyProfile] | None = None,
        seed: int | None = None,
    ):
        """Initialize latency simulator."""
        self.profiles = profiles or self._default_profiles()
        self.rng = np.random.default_rng(seed)

    def _default_profiles(self) -> dict[ExchangeName, LatencyProfile]:
        """Get default latency profiles."""
        return {
            ExchangeName.BYBIT: LatencyProfile(
                exchange=ExchangeName.BYBIT,
                rest_latency_mean=40,
                ws_latency_mean=8,
            ),
            ExchangeName.BINANCE: LatencyProfile(
                exchange=ExchangeName.BINANCE,
                rest_latency_mean=30,
                ws_latency_mean=5,
            ),
            ExchangeName.OKX: LatencyProfile(
                exchange=ExchangeName.OKX,
                rest_latency_mean=50,
                ws_latency_mean=10,
            ),
            ExchangeName.KRAKEN: LatencyProfile(
                exchange=ExchangeName.KRAKEN,
                rest_latency_mean=80,
                ws_latency_mean=20,
            ),
            ExchangeName.COINBASE: LatencyProfile(
                exchange=ExchangeName.COINBASE,
                rest_latency_mean=60,
                ws_latency_mean=15,
            ),
        }

    def simulate_rest_latency(self, exchange: ExchangeName) -> float:
        """Simulate REST API latency."""
        profile = self.profiles.get(exchange, LatencyProfile(exchange=exchange))

        latency = self.rng.normal(profile.rest_latency_mean, profile.rest_latency_std)

        # Apply jitter
        if self.rng.random() < profile.jitter_probability:
            latency *= profile.jitter_multiplier

        return max(1.0, latency)

    def simulate_ws_latency(self, exchange: ExchangeName) -> float:
        """Simulate WebSocket latency."""
        profile = self.profiles.get(exchange, LatencyProfile(exchange=exchange))

        latency = self.rng.normal(profile.ws_latency_mean, profile.ws_latency_std)

        # Apply jitter
        if self.rng.random() < profile.jitter_probability:
            latency *= profile.jitter_multiplier

        return max(0.5, latency)

    def simulate_order_latency(self, exchange: ExchangeName) -> float:
        """Simulate total order latency (submit + fill)."""
        profile = self.profiles.get(exchange, LatencyProfile(exchange=exchange))

        submit = self.rng.normal(profile.order_submit_mean, profile.order_submit_std)
        fill = self.rng.normal(profile.order_fill_mean, profile.order_fill_std)

        return max(1.0, submit + fill)

    def simulate_arbitrage_execution_time(
        self,
        buy_exchange: ExchangeName,
        sell_exchange: ExchangeName,
        parallel: bool = True,
    ) -> float:
        """
        Simulate total arbitrage execution time.

        Args:
            buy_exchange: Exchange to buy on
            sell_exchange: Exchange to sell on
            parallel: Execute in parallel or sequentially

        Returns:
            Total execution time in milliseconds
        """
        buy_latency = self.simulate_order_latency(buy_exchange)
        sell_latency = self.simulate_order_latency(sell_exchange)

        if parallel:
            return max(buy_latency, sell_latency)
        else:
            return buy_latency + sell_latency

    def adjust_prices_for_latency(
        self,
        buy_price: float,
        sell_price: float,
        latency_ms: float,
        volatility: float,
    ) -> tuple[float, float]:
        """
        Adjust prices for expected movement during latency.

        Args:
            buy_price: Expected buy price
            sell_price: Expected sell price
            latency_ms: Expected latency
            volatility: Current volatility (per ms)

        Returns:
            Adjusted (buy_price, sell_price)
        """
        # Price uncertainty increases with latency
        uncertainty = volatility * np.sqrt(latency_ms)

        # Worst case: buy higher, sell lower
        adj_buy = buy_price * (1 + uncertainty)
        adj_sell = sell_price * (1 - uncertainty)

        return adj_buy, adj_sell


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Exchange
    "ExchangeName",
    "ExchangeFees",
    "ExchangeTicker",
    "ExchangeBalance",
    "ExchangeConfig",
    "ExchangeConnector",
    # Arbitrage
    "ArbitrageType",
    "ArbitrageOpportunity",
    "ArbitrageConfig",
    "ArbitrageDetector",
    # Trading
    "ArbitrageExecution",
    "TraderConfig",
    "CrossExchangeTrader",
    # Fees
    "FeeBreakdown",
    "FeeCalculator",
    # Latency
    "LatencyProfile",
    "LatencySimulator",
]
