"""
Options Strategies Module for Universal Math Engine v2.4.

This module provides options pricing and strategies:
1. BlackScholes - Options pricing model
2. BinomialTree - Tree-based pricing
3. MonteCarlo - Simulation-based pricing
4. Greeks - Delta, Gamma, Theta, Vega, Rho calculation
5. OptionsStrategy - Strategy building (spreads, straddles, etc.)
6. ImpliedVolatility - IV calculation and surface

Author: Universal Math Engine Team
Version: 2.4.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from scipy.stats import norm

# ============================================================================
# ENUMS AND DATA STRUCTURES
# ============================================================================


class OptionType(Enum):
    """Option type."""

    CALL = "call"
    PUT = "put"


class OptionStyle(Enum):
    """Option exercise style."""

    EUROPEAN = "european"
    AMERICAN = "american"


class StrategyType(Enum):
    """Pre-defined options strategies."""

    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    SHORT_CALL = "short_call"
    SHORT_PUT = "short_put"
    COVERED_CALL = "covered_call"
    PROTECTIVE_PUT = "protective_put"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    IRON_CONDOR = "iron_condor"
    BUTTERFLY = "butterfly"
    CALENDAR_SPREAD = "calendar_spread"
    RATIO_SPREAD = "ratio_spread"


@dataclass
class Option:
    """Single option contract."""

    strike: float
    expiry: datetime
    option_type: OptionType
    style: OptionStyle = OptionStyle.EUROPEAN
    premium: float = 0.0
    quantity: int = 1  # Positive for long, negative for short
    underlying_price: float = 0.0

    def intrinsic_value(self, spot: float) -> float:
        """Calculate intrinsic value."""
        if self.option_type == OptionType.CALL:
            return max(0, spot - self.strike)
        else:
            return max(0, self.strike - spot)

    def time_value(self, spot: float) -> float:
        """Calculate time value."""
        return self.premium - self.intrinsic_value(spot)

    def moneyness(self, spot: float) -> str:
        """Get moneyness status."""
        if self.option_type == OptionType.CALL:
            if spot > self.strike:
                return "ITM"
            elif spot < self.strike:
                return "OTM"
            return "ATM"
        else:
            if spot < self.strike:
                return "ITM"
            elif spot > self.strike:
                return "OTM"
            return "ATM"


@dataclass
class Greeks:
    """Option Greeks."""

    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    charm: float = 0.0  # Delta decay
    vanna: float = 0.0  # Delta sensitivity to volatility
    volga: float = 0.0  # Vega convexity


@dataclass
class OptionPosition:
    """Position in an option."""

    option: Option
    entry_price: float
    current_price: float
    entry_date: datetime
    greeks: Greeks = field(default_factory=Greeks)

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        return (self.current_price - self.entry_price) * self.option.quantity * 100

    @property
    def pnl_percent(self) -> float:
        """Calculate P&L percentage."""
        if self.entry_price == 0:
            return 0
        return (self.current_price - self.entry_price) / self.entry_price * 100


@dataclass
class StrategyLeg:
    """Single leg of an options strategy."""

    option_type: OptionType
    strike_offset: float  # Offset from ATM (0 = ATM)
    quantity: int  # Positive for long, negative for short
    expiry_offset: int = 0  # Days offset from base expiry


@dataclass
class StrategyPayoff:
    """Strategy payoff analysis."""

    price_range: NDArray  # Underlying price range
    payoff: NDArray  # Payoff at each price
    breakeven_points: List[float]
    max_profit: float
    max_loss: float
    probability_of_profit: float


# ============================================================================
# BLACK-SCHOLES MODEL
# ============================================================================


class BlackScholes:
    """
    Black-Scholes options pricing model.

    Assumes European options with constant volatility.
    """

    @staticmethod
    def d1(
        S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
    ) -> float:
        """Calculate d1 parameter."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def d2(
        S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
    ) -> float:
        """Calculate d2 parameter."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return BlackScholes.d1(S, K, T, r, sigma, q) - sigma * np.sqrt(T)

    @staticmethod
    def call_price(
        S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
    ) -> float:
        """
        Calculate call option price.

        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield

        Returns:
            Call option price
        """
        if T <= 0:
            return max(0, S - K)

        d_1 = BlackScholes.d1(S, K, T, r, sigma, q)
        d_2 = BlackScholes.d2(S, K, T, r, sigma, q)

        price = S * np.exp(-q * T) * norm.cdf(d_1) - K * np.exp(-r * T) * norm.cdf(d_2)
        return max(0, price)

    @staticmethod
    def put_price(
        S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
    ) -> float:
        """Calculate put option price."""
        if T <= 0:
            return max(0, K - S)

        d_1 = BlackScholes.d1(S, K, T, r, sigma, q)
        d_2 = BlackScholes.d2(S, K, T, r, sigma, q)

        price = K * np.exp(-r * T) * norm.cdf(-d_2) - S * np.exp(-q * T) * norm.cdf(
            -d_1
        )
        return max(0, price)

    @staticmethod
    def price(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        q: float = 0.0,
    ) -> float:
        """Calculate option price."""
        if option_type == OptionType.CALL:
            return BlackScholes.call_price(S, K, T, r, sigma, q)
        else:
            return BlackScholes.put_price(S, K, T, r, sigma, q)


# ============================================================================
# GREEKS CALCULATOR
# ============================================================================


class GreeksCalculator:
    """
    Calculate option Greeks using Black-Scholes.
    """

    @staticmethod
    def delta(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        q: float = 0.0,
    ) -> float:
        """
        Calculate Delta (price sensitivity to underlying).

        Delta ranges from 0 to 1 for calls, -1 to 0 for puts.
        """
        if T <= 0:
            if option_type == OptionType.CALL:
                return 1.0 if S > K else 0.0
            else:
                return -1.0 if S < K else 0.0

        d_1 = BlackScholes.d1(S, K, T, r, sigma, q)

        if option_type == OptionType.CALL:
            return np.exp(-q * T) * norm.cdf(d_1)
        else:
            return np.exp(-q * T) * (norm.cdf(d_1) - 1)

    @staticmethod
    def gamma(
        S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
    ) -> float:
        """
        Calculate Gamma (delta sensitivity to underlying).

        Same for calls and puts.
        """
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0.0

        d_1 = BlackScholes.d1(S, K, T, r, sigma, q)
        return np.exp(-q * T) * norm.pdf(d_1) / (S * sigma * np.sqrt(T))

    @staticmethod
    def theta(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        q: float = 0.0,
    ) -> float:
        """
        Calculate Theta (time decay).

        Returns daily theta (divide annual by 365).
        """
        if T <= 0:
            return 0.0

        d_1 = BlackScholes.d1(S, K, T, r, sigma, q)
        d_2 = BlackScholes.d2(S, K, T, r, sigma, q)

        term1 = -S * np.exp(-q * T) * norm.pdf(d_1) * sigma / (2 * np.sqrt(T))

        if option_type == OptionType.CALL:
            term2 = q * S * np.exp(-q * T) * norm.cdf(d_1)
            term3 = -r * K * np.exp(-r * T) * norm.cdf(d_2)
        else:
            term2 = -q * S * np.exp(-q * T) * norm.cdf(-d_1)
            term3 = r * K * np.exp(-r * T) * norm.cdf(-d_2)

        annual_theta = term1 + term2 + term3
        return annual_theta / 365  # Daily theta

    @staticmethod
    def vega(
        S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0
    ) -> float:
        """
        Calculate Vega (volatility sensitivity).

        Same for calls and puts. Returns per 1% vol change.
        """
        if T <= 0:
            return 0.0

        d_1 = BlackScholes.d1(S, K, T, r, sigma, q)
        return S * np.exp(-q * T) * norm.pdf(d_1) * np.sqrt(T) / 100

    @staticmethod
    def rho(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        q: float = 0.0,
    ) -> float:
        """
        Calculate Rho (interest rate sensitivity).

        Returns per 1% rate change.
        """
        if T <= 0:
            return 0.0

        d_2 = BlackScholes.d2(S, K, T, r, sigma, q)

        if option_type == OptionType.CALL:
            return K * T * np.exp(-r * T) * norm.cdf(d_2) / 100
        else:
            return -K * T * np.exp(-r * T) * norm.cdf(-d_2) / 100

    @staticmethod
    def all_greeks(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        q: float = 0.0,
    ) -> Greeks:
        """Calculate all Greeks at once."""
        return Greeks(
            delta=GreeksCalculator.delta(S, K, T, r, sigma, option_type, q),
            gamma=GreeksCalculator.gamma(S, K, T, r, sigma, q),
            theta=GreeksCalculator.theta(S, K, T, r, sigma, option_type, q),
            vega=GreeksCalculator.vega(S, K, T, r, sigma, q),
            rho=GreeksCalculator.rho(S, K, T, r, sigma, option_type, q),
        )


# ============================================================================
# BINOMIAL TREE MODEL
# ============================================================================


class BinomialTree:
    """
    Binomial tree model for option pricing.

    Supports both European and American options.
    """

    def __init__(self, n_steps: int = 100):
        self.n_steps = n_steps

    def price(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        style: OptionStyle = OptionStyle.EUROPEAN,
        q: float = 0.0,
    ) -> float:
        """
        Calculate option price using binomial tree.

        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: Call or put
            style: European or American
            q: Dividend yield

        Returns:
            Option price
        """
        if T <= 0:
            if option_type == OptionType.CALL:
                return max(0, S - K)
            else:
                return max(0, K - S)

        dt = T / self.n_steps
        u = np.exp(sigma * np.sqrt(dt))  # Up factor
        d = 1 / u  # Down factor
        p = (np.exp((r - q) * dt) - d) / (u - d)  # Risk-neutral probability

        # Build price tree at expiration
        prices = np.zeros(self.n_steps + 1)
        for i in range(self.n_steps + 1):
            prices[i] = S * (u ** (self.n_steps - i)) * (d**i)

        # Calculate option values at expiration
        if option_type == OptionType.CALL:
            values = np.maximum(prices - K, 0)
        else:
            values = np.maximum(K - prices, 0)

        # Backward induction
        discount = np.exp(-r * dt)
        for step in range(self.n_steps - 1, -1, -1):
            for i in range(step + 1):
                hold_value = discount * (p * values[i] + (1 - p) * values[i + 1])

                if style == OptionStyle.AMERICAN:
                    # Check early exercise
                    spot = S * (u ** (step - i)) * (d**i)
                    if option_type == OptionType.CALL:
                        exercise_value = max(0, spot - K)
                    else:
                        exercise_value = max(0, K - spot)
                    values[i] = max(hold_value, exercise_value)
                else:
                    values[i] = hold_value

        return float(values[0])


# ============================================================================
# MONTE CARLO PRICING
# ============================================================================


class MonteCarloPricer:
    """
    Monte Carlo simulation for option pricing.

    Supports exotic options and path-dependent payoffs.
    """

    def __init__(
        self,
        n_simulations: int = 100000,
        n_steps: int = 252,
        seed: Optional[int] = None,
    ):
        self.n_simulations = n_simulations
        self.n_steps = n_steps
        if seed is not None:
            np.random.seed(seed)

    def simulate_paths(
        self, S: float, T: float, r: float, sigma: float, q: float = 0.0
    ) -> NDArray:
        """
        Simulate price paths using GBM.

        Returns:
            Array of shape (n_simulations, n_steps + 1)
        """
        dt = T / self.n_steps
        drift = (r - q - 0.5 * sigma**2) * dt
        vol = sigma * np.sqrt(dt)

        # Generate random shocks
        Z = np.random.standard_normal((self.n_simulations, self.n_steps))

        # Calculate log returns
        log_returns = drift + vol * Z

        # Build price paths
        paths = np.zeros((self.n_simulations, self.n_steps + 1))
        paths[:, 0] = S
        paths[:, 1:] = S * np.exp(np.cumsum(log_returns, axis=1))

        return paths

    def price_european(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        q: float = 0.0,
    ) -> Tuple[float, float]:
        """
        Price European option.

        Returns:
            (price, standard_error)
        """
        paths = self.simulate_paths(S, T, r, sigma, q)
        final_prices = paths[:, -1]

        if option_type == OptionType.CALL:
            payoffs = np.maximum(final_prices - K, 0)
        else:
            payoffs = np.maximum(K - final_prices, 0)

        # Discount payoffs
        discount = np.exp(-r * T)
        discounted_payoffs = discount * payoffs

        price = np.mean(discounted_payoffs)
        std_error = np.std(discounted_payoffs) / np.sqrt(self.n_simulations)

        return float(price), float(std_error)

    def price_asian(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        averaging: str = "arithmetic",
        q: float = 0.0,
    ) -> Tuple[float, float]:
        """
        Price Asian (average price) option.

        Args:
            averaging: "arithmetic" or "geometric"
        """
        paths = self.simulate_paths(S, T, r, sigma, q)

        if averaging == "arithmetic":
            avg_prices = np.mean(paths, axis=1)
        else:
            avg_prices = np.exp(np.mean(np.log(paths), axis=1))

        if option_type == OptionType.CALL:
            payoffs = np.maximum(avg_prices - K, 0)
        else:
            payoffs = np.maximum(K - avg_prices, 0)

        discount = np.exp(-r * T)
        discounted_payoffs = discount * payoffs

        price = np.mean(discounted_payoffs)
        std_error = np.std(discounted_payoffs) / np.sqrt(self.n_simulations)

        return float(price), float(std_error)

    def price_barrier(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType,
        barrier: float,
        barrier_type: str,  # "up-and-out", "up-and-in", "down-and-out", "down-and-in"
        q: float = 0.0,
    ) -> Tuple[float, float]:
        """Price barrier option."""
        paths = self.simulate_paths(S, T, r, sigma, q)
        final_prices = paths[:, -1]

        # Check barrier condition
        if barrier_type.startswith("up"):
            crossed = np.any(paths >= barrier, axis=1)
        else:
            crossed = np.any(paths <= barrier, axis=1)

        if barrier_type.endswith("out"):
            alive = ~crossed
        else:  # knock-in
            alive = crossed

        if option_type == OptionType.CALL:
            payoffs = np.maximum(final_prices - K, 0)
        else:
            payoffs = np.maximum(K - final_prices, 0)

        payoffs = payoffs * alive

        discount = np.exp(-r * T)
        discounted_payoffs = discount * payoffs

        price = np.mean(discounted_payoffs)
        std_error = np.std(discounted_payoffs) / np.sqrt(self.n_simulations)

        return float(price), float(std_error)


# ============================================================================
# IMPLIED VOLATILITY
# ============================================================================


class ImpliedVolatility:
    """
    Implied volatility calculation and surface.
    """

    @staticmethod
    def calculate(
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: OptionType,
        q: float = 0.0,
        initial_guess: float = 0.2,
    ) -> float:
        """
        Calculate implied volatility using Newton-Raphson.

        Args:
            market_price: Market price of option
            S, K, T, r: Option parameters
            option_type: Call or put
            q: Dividend yield
            initial_guess: Starting volatility estimate

        Returns:
            Implied volatility
        """
        if T <= 0 or market_price <= 0:
            return 0.0

        def objective(sigma: float) -> float:
            price = BlackScholes.price(S, K, T, r, sigma, option_type, q)
            return price - market_price

        def vega(sigma: float) -> float:
            return GreeksCalculator.vega(S, K, T, r, sigma, q) * 100

        # Newton-Raphson
        sigma = initial_guess
        for _ in range(100):
            price_diff = objective(sigma)
            v = vega(sigma)

            if abs(price_diff) < 1e-8:
                break

            if v < 1e-10:
                break

            sigma = sigma - price_diff / v
            sigma = max(0.001, min(5.0, sigma))

        return sigma

    @staticmethod
    def calculate_bisection(
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: OptionType,
        q: float = 0.0,
    ) -> float:
        """Calculate IV using bisection method (more robust)."""
        if T <= 0 or market_price <= 0:
            return 0.0

        def objective(sigma: float) -> float:
            price = BlackScholes.price(S, K, T, r, sigma, option_type, q)
            return price - market_price

        low, high = 0.001, 5.0

        for _ in range(100):
            mid = (low + high) / 2
            if objective(mid) > 0:
                high = mid
            else:
                low = mid

            if high - low < 1e-6:
                break

        return (low + high) / 2


class VolatilitySurface:
    """
    Implied volatility surface.
    """

    def __init__(self):
        self.strikes: List[float] = []
        self.expiries: List[float] = []
        self.ivs: NDArray = np.array([])

    def build(
        self,
        spot: float,
        strikes: List[float],
        expiries: List[float],  # In years
        market_prices: NDArray,  # Shape: (len(strikes), len(expiries))
        r: float,
        option_type: OptionType,
        q: float = 0.0,
    ) -> None:
        """
        Build IV surface from market prices.

        Args:
            spot: Current spot price
            strikes: List of strike prices
            expiries: List of expiry times (years)
            market_prices: 2D array of market prices
            r: Risk-free rate
            option_type: Call or put
            q: Dividend yield
        """
        self.strikes = strikes
        self.expiries = expiries
        self.ivs = np.zeros((len(strikes), len(expiries)))

        for i, K in enumerate(strikes):
            for j, T in enumerate(expiries):
                price = market_prices[i, j]
                self.ivs[i, j] = ImpliedVolatility.calculate(
                    price, spot, K, T, r, option_type, q
                )

    def get_iv(self, strike: float, expiry: float) -> float:
        """Interpolate IV for given strike and expiry."""
        if len(self.strikes) == 0:
            return 0.2

        # Simple bilinear interpolation
        strike_idx = np.searchsorted(self.strikes, strike)
        expiry_idx = np.searchsorted(self.expiries, expiry)

        strike_idx = max(0, min(strike_idx, len(self.strikes) - 1))
        expiry_idx = max(0, min(expiry_idx, len(self.expiries) - 1))

        return float(self.ivs[strike_idx, expiry_idx])

    def get_smile(self, expiry: float) -> Tuple[List[float], List[float]]:
        """Get volatility smile for given expiry."""
        expiry_idx = np.searchsorted(self.expiries, expiry)
        expiry_idx = max(0, min(expiry_idx, len(self.expiries) - 1))

        return self.strikes, list(self.ivs[:, expiry_idx])

    def get_term_structure(self, strike: float) -> Tuple[List[float], List[float]]:
        """Get term structure for given strike."""
        strike_idx = np.searchsorted(self.strikes, strike)
        strike_idx = max(0, min(strike_idx, len(self.strikes) - 1))

        return self.expiries, list(self.ivs[strike_idx, :])


# ============================================================================
# OPTIONS STRATEGY BUILDER
# ============================================================================


class OptionsStrategy:
    """
    Build and analyze options strategies.
    """

    def __init__(
        self, spot: float, r: float = 0.05, sigma: float = 0.2, q: float = 0.0
    ):
        self.spot = spot
        self.r = r
        self.sigma = sigma
        self.q = q
        self.legs: List[Tuple[Option, int]] = []  # (option, quantity)

    def add_leg(
        self,
        strike: float,
        expiry_days: int,
        option_type: OptionType,
        quantity: int,
        premium: Optional[float] = None,
    ) -> "OptionsStrategy":
        """
        Add leg to strategy.

        Args:
            strike: Strike price
            expiry_days: Days to expiration
            option_type: Call or put
            quantity: Positive for long, negative for short
            premium: Option premium (calculated if not provided)
        """
        T = expiry_days / 365

        if premium is None:
            premium = BlackScholes.price(
                self.spot, strike, T, self.r, self.sigma, option_type, self.q
            )

        option = Option(
            strike=strike,
            expiry=datetime.now() + timedelta(days=expiry_days),
            option_type=option_type,
            premium=premium,
            quantity=quantity,
            underlying_price=self.spot,
        )

        self.legs.append((option, quantity))
        return self

    def total_premium(self) -> float:
        """Calculate total premium paid/received."""
        return sum(opt.premium * qty for opt, qty in self.legs)

    def payoff_at_expiry(self, spot_prices: NDArray) -> NDArray:
        """
        Calculate strategy payoff at various spot prices.

        Args:
            spot_prices: Array of spot prices

        Returns:
            Array of payoffs
        """
        payoff = np.zeros_like(spot_prices)

        for option, qty in self.legs:
            if option.option_type == OptionType.CALL:
                leg_payoff = np.maximum(spot_prices - option.strike, 0)
            else:
                leg_payoff = np.maximum(option.strike - spot_prices, 0)

            # Add premium (negative for long, positive for short)
            leg_payoff = leg_payoff - option.premium

            payoff += leg_payoff * qty

        return payoff

    def analyze(self, price_range: float = 0.3) -> StrategyPayoff:
        """
        Analyze strategy payoff.

        Args:
            price_range: Range around spot to analyze (0.3 = ±30%)

        Returns:
            Strategy payoff analysis
        """
        n_points = 200
        low = self.spot * (1 - price_range)
        high = self.spot * (1 + price_range)
        prices = np.linspace(low, high, n_points)

        payoff = self.payoff_at_expiry(prices)

        # Find breakeven points (where payoff crosses zero)
        breakevens = []
        for i in range(len(payoff) - 1):
            if payoff[i] * payoff[i + 1] < 0:
                # Linear interpolation
                x = prices[i] - payoff[i] * (prices[i + 1] - prices[i]) / (
                    payoff[i + 1] - payoff[i]
                )
                breakevens.append(x)

        # Max profit and loss
        max_profit = float(np.max(payoff))
        max_loss = float(np.min(payoff))

        # Probability of profit (assuming lognormal distribution)
        if len(breakevens) >= 2:
            prob_profit = norm.cdf(
                np.log(breakevens[1] / self.spot) / (self.sigma * np.sqrt(30 / 365))
            ) - norm.cdf(
                np.log(breakevens[0] / self.spot) / (self.sigma * np.sqrt(30 / 365))
            )
        elif len(breakevens) == 1:
            prob_profit = 1 - norm.cdf(
                np.log(breakevens[0] / self.spot) / (self.sigma * np.sqrt(30 / 365))
            )
        else:
            prob_profit = 1.0 if max_loss >= 0 else 0.0

        return StrategyPayoff(
            price_range=prices,
            payoff=payoff,
            breakeven_points=breakevens,
            max_profit=max_profit,
            max_loss=max_loss,
            probability_of_profit=float(np.abs(prob_profit)),
        )

    def total_greeks(self) -> Greeks:
        """Calculate total Greeks for strategy."""
        total = Greeks()

        for option, qty in self.legs:
            T = (option.expiry - datetime.now()).days / 365
            if T <= 0:
                continue

            leg_greeks = GreeksCalculator.all_greeks(
                self.spot,
                option.strike,
                T,
                self.r,
                self.sigma,
                option.option_type,
                self.q,
            )

            total.delta += leg_greeks.delta * qty
            total.gamma += leg_greeks.gamma * qty
            total.theta += leg_greeks.theta * qty
            total.vega += leg_greeks.vega * qty
            total.rho += leg_greeks.rho * qty

        return total


# ============================================================================
# PRE-DEFINED STRATEGIES
# ============================================================================


class StrategyFactory:
    """Factory for creating common options strategies."""

    @staticmethod
    def create_strategy(
        strategy_type: StrategyType,
        spot: float,
        atm_strike: Optional[float] = None,
        expiry_days: int = 30,
        width: float = 0.05,  # Strike width for spreads
        r: float = 0.05,
        sigma: float = 0.2,
    ) -> OptionsStrategy:
        """
        Create pre-defined options strategy.

        Args:
            strategy_type: Type of strategy
            spot: Current spot price
            atm_strike: ATM strike (default: spot)
            expiry_days: Days to expiration
            width: Strike width for spreads (as % of spot)
            r: Risk-free rate
            sigma: Volatility

        Returns:
            Options strategy
        """
        if atm_strike is None:
            atm_strike = spot

        strategy = OptionsStrategy(spot, r, sigma)

        if strategy_type == StrategyType.LONG_CALL:
            strategy.add_leg(atm_strike, expiry_days, OptionType.CALL, 1)

        elif strategy_type == StrategyType.LONG_PUT:
            strategy.add_leg(atm_strike, expiry_days, OptionType.PUT, 1)

        elif strategy_type == StrategyType.SHORT_CALL:
            strategy.add_leg(atm_strike, expiry_days, OptionType.CALL, -1)

        elif strategy_type == StrategyType.SHORT_PUT:
            strategy.add_leg(atm_strike, expiry_days, OptionType.PUT, -1)

        elif strategy_type == StrategyType.COVERED_CALL:
            # Long stock + short call
            strategy.add_leg(atm_strike * (1 + width), expiry_days, OptionType.CALL, -1)
            # Note: stock position handled separately

        elif strategy_type == StrategyType.PROTECTIVE_PUT:
            # Long stock + long put
            strategy.add_leg(atm_strike * (1 - width), expiry_days, OptionType.PUT, 1)

        elif strategy_type == StrategyType.BULL_CALL_SPREAD:
            strategy.add_leg(atm_strike, expiry_days, OptionType.CALL, 1)
            strategy.add_leg(atm_strike * (1 + width), expiry_days, OptionType.CALL, -1)

        elif strategy_type == StrategyType.BEAR_PUT_SPREAD:
            strategy.add_leg(atm_strike, expiry_days, OptionType.PUT, 1)
            strategy.add_leg(atm_strike * (1 - width), expiry_days, OptionType.PUT, -1)

        elif strategy_type == StrategyType.STRADDLE:
            strategy.add_leg(atm_strike, expiry_days, OptionType.CALL, 1)
            strategy.add_leg(atm_strike, expiry_days, OptionType.PUT, 1)

        elif strategy_type == StrategyType.STRANGLE:
            strategy.add_leg(atm_strike * (1 + width), expiry_days, OptionType.CALL, 1)
            strategy.add_leg(atm_strike * (1 - width), expiry_days, OptionType.PUT, 1)

        elif strategy_type == StrategyType.IRON_CONDOR:
            # Bear call spread + bull put spread
            strategy.add_leg(atm_strike * (1 + width), expiry_days, OptionType.CALL, -1)
            strategy.add_leg(
                atm_strike * (1 + 2 * width), expiry_days, OptionType.CALL, 1
            )
            strategy.add_leg(atm_strike * (1 - width), expiry_days, OptionType.PUT, -1)
            strategy.add_leg(
                atm_strike * (1 - 2 * width), expiry_days, OptionType.PUT, 1
            )

        elif strategy_type == StrategyType.BUTTERFLY:
            strategy.add_leg(atm_strike * (1 - width), expiry_days, OptionType.CALL, 1)
            strategy.add_leg(atm_strike, expiry_days, OptionType.CALL, -2)
            strategy.add_leg(atm_strike * (1 + width), expiry_days, OptionType.CALL, 1)

        elif strategy_type == StrategyType.CALENDAR_SPREAD:
            # Short near-term, long far-term
            strategy.add_leg(atm_strike, expiry_days, OptionType.CALL, -1)
            strategy.add_leg(atm_strike, expiry_days * 2, OptionType.CALL, 1)

        elif strategy_type == StrategyType.RATIO_SPREAD:
            # 1x2 ratio call spread
            strategy.add_leg(atm_strike, expiry_days, OptionType.CALL, 1)
            strategy.add_leg(atm_strike * (1 + width), expiry_days, OptionType.CALL, -2)

        return strategy

    @staticmethod
    def get_available_strategies() -> List[str]:
        """Get list of available strategy types."""
        return [s.value for s in StrategyType]


# ============================================================================
# OPTIONS PORTFOLIO
# ============================================================================


class OptionsPortfolio:
    """
    Manage portfolio of options positions.
    """

    def __init__(self):
        self.positions: List[OptionPosition] = []
        self.closed_positions: List[OptionPosition] = []

    def add_position(self, position: OptionPosition) -> None:
        """Add new position."""
        self.positions.append(position)

    def close_position(self, index: int, exit_price: float) -> float:
        """
        Close position and return P&L.

        Args:
            index: Position index
            exit_price: Exit price

        Returns:
            Realized P&L
        """
        position = self.positions.pop(index)
        position.current_price = exit_price
        pnl = position.unrealized_pnl
        self.closed_positions.append(position)
        return pnl

    def total_greeks(self) -> Greeks:
        """Calculate total portfolio Greeks."""
        total = Greeks()
        for pos in self.positions:
            total.delta += pos.greeks.delta * pos.option.quantity
            total.gamma += pos.greeks.gamma * pos.option.quantity
            total.theta += pos.greeks.theta * pos.option.quantity
            total.vega += pos.greeks.vega * pos.option.quantity
            total.rho += pos.greeks.rho * pos.option.quantity
        return total

    def total_value(self) -> float:
        """Calculate total portfolio value."""
        return sum(
            pos.current_price * pos.option.quantity * 100 for pos in self.positions
        )

    def total_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L."""
        return sum(pos.unrealized_pnl for pos in self.positions)

    def total_realized_pnl(self) -> float:
        """Calculate total realized P&L."""
        return sum(pos.unrealized_pnl for pos in self.closed_positions)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "OptionType",
    "OptionStyle",
    "StrategyType",
    # Data structures
    "Option",
    "Greeks",
    "OptionPosition",
    "StrategyLeg",
    "StrategyPayoff",
    # Pricing models
    "BlackScholes",
    "GreeksCalculator",
    "BinomialTree",
    "MonteCarloPricer",
    # Implied volatility
    "ImpliedVolatility",
    "VolatilitySurface",
    # Strategy
    "OptionsStrategy",
    "StrategyFactory",
    # Portfolio
    "OptionsPortfolio",
]
