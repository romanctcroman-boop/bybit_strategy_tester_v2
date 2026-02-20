"""
Currency Conversion Utilities

TradingView-compatible currency conversion functions.
Equivalent to strategy.convert_to_account() and strategy.convert_to_symbol()

Reference: https://www.tradingview.com/pine-script-reference/v5/#fun_strategy.convert_to_account
"""

from loguru import logger

# Common FX pairs for crypto (base currencies)
CRYPTO_QUOTE_CURRENCIES = ["USDT", "USDC", "BUSD", "USD", "EUR", "BTC", "ETH"]

# Daily rates cache (simplified - in production would use API)
CROSS_RATES_CACHE: dict[str, float] = {
    "USDT/USD": 1.0,
    "USDC/USD": 1.0,
    "BUSD/USD": 1.0,
    "BTC/USD": 42000.0,  # Placeholder
    "ETH/USD": 2500.0,  # Placeholder
    "EUR/USD": 1.10,
    "GBP/USD": 1.27,
    "JPY/USD": 0.0067,
}


def get_quote_currency(symbol: str) -> str:
    """
    Extract quote currency from trading symbol.

    Examples:
        BTCUSDT -> USDT
        ETHBTC -> BTC
        EUR/USD -> USD
    """
    # Check common crypto suffixes
    for suffix in CRYPTO_QUOTE_CURRENCIES:
        if symbol.endswith(suffix):
            return suffix

    # Check for slash notation (FX)
    if "/" in symbol:
        parts = symbol.split("/", 1)
        return parts[1] if len(parts) > 1 and parts[1] else "USDT"

    # Default to USDT for crypto
    return "USDT"


def get_base_currency(symbol: str) -> str:
    """
    Extract base currency from trading symbol.

    Examples:
        BTCUSDT -> BTC
        ETHBTC -> ETH
        EUR/USD -> EUR
    """
    quote = get_quote_currency(symbol)
    if "/" in symbol:
        parts = symbol.split("/", 1)
        return parts[0] if parts[0] else symbol
    return symbol.replace(quote, "")


def get_cross_rate(from_currency: str, to_currency: str) -> float:
    """
    Get cross rate between two currencies.

    TradingView equivalent: request.currency_rate(from, to)

    Args:
        from_currency: Source currency (e.g., "BTC")
        to_currency: Target currency (e.g., "USD")

    Returns:
        Cross rate (1 from_currency = X to_currency)
    """
    if from_currency == to_currency:
        return 1.0

    # Direct rate
    key = f"{from_currency}/{to_currency}"
    if key in CROSS_RATES_CACHE:
        return CROSS_RATES_CACHE[key]

    # Inverse rate
    inverse_key = f"{to_currency}/{from_currency}"
    if inverse_key in CROSS_RATES_CACHE:
        return 1.0 / CROSS_RATES_CACHE[inverse_key]

    # Try through USD
    from_usd_key = f"{from_currency}/USD"
    to_usd_key = f"{to_currency}/USD"

    from_usd = CROSS_RATES_CACHE.get(from_usd_key)
    to_usd = CROSS_RATES_CACHE.get(to_usd_key)

    if from_usd is not None and to_usd is not None:
        return from_usd / to_usd

    # Fallback to 1:1 with warning
    logger.warning(f"Cross rate not found for {from_currency}/{to_currency}, using 1.0")
    return 1.0


def convert_to_account(
    value: float,
    symbol: str,
    account_currency: str = "USDT",
) -> float:
    """
    Convert a value from symbol's currency to account currency.

    TradingView equivalent: strategy.convert_to_account(value)

    Args:
        value: Value in symbol's quote currency
        symbol: Trading symbol (e.g., "BTCUSDT")
        account_currency: Account/strategy currency

    Returns:
        Value in account currency
    """
    symbol_currency = get_quote_currency(symbol)
    rate = get_cross_rate(symbol_currency, account_currency)
    return value * rate


def convert_to_symbol(
    value: float,
    symbol: str,
    account_currency: str = "USDT",
) -> float:
    """
    Convert a value from account currency to symbol's currency.

    TradingView equivalent: strategy.convert_to_symbol(value)

    Args:
        value: Value in account currency
        symbol: Trading symbol (e.g., "BTCUSDT")
        account_currency: Account/strategy currency

    Returns:
        Value in symbol's quote currency
    """
    symbol_currency = get_quote_currency(symbol)
    rate = get_cross_rate(account_currency, symbol_currency)
    return value * rate


def calculate_position_value(
    qty: float,
    price: float,
    symbol: str,
    account_currency: str = "USDT",
) -> float:
    """
    Calculate position value in account currency.

    Args:
        qty: Number of contracts/units
        price: Entry price
        symbol: Trading symbol
        account_currency: Account currency

    Returns:
        Position value in account currency
    """
    value_in_symbol = qty * price
    return convert_to_account(value_in_symbol, symbol, account_currency)


def get_point_value(symbol: str) -> float:
    """
    Get point value for a symbol.

    TradingView equivalent: syminfo.pointvalue

    For crypto perpetuals, this is typically 1.0
    For futures, it varies by contract specification.

    Args:
        symbol: Trading symbol

    Returns:
        Point value (value per 1.0 price movement per contract)
    """
    # For Bybit perpetuals, point value is 1.0
    # (1 contract = 1 unit of base currency)
    return 1.0


def get_min_tick(symbol: str) -> float:
    """
    Get minimum tick size for a symbol.

    TradingView equivalent: syminfo.mintick

    Args:
        symbol: Trading symbol

    Returns:
        Minimum price increment
    """
    # Common tick sizes for Bybit
    TICK_SIZES = {
        "BTCUSDT": 0.01,
        "ETHUSDT": 0.01,
        "SOLUSDT": 0.001,
        "XRPUSDT": 0.0001,
        "DOGEUSDT": 0.00001,
    }
    return TICK_SIZES.get(symbol, 0.01)


def ticks_to_price(ticks: int, symbol: str) -> float:
    """
    Convert ticks to price amount.

    Args:
        ticks: Number of ticks
        symbol: Trading symbol

    Returns:
        Price amount
    """
    return ticks * get_min_tick(symbol)


def price_to_ticks(price: float, symbol: str) -> int:
    """
    Convert price amount to ticks.

    Args:
        price: Price amount
        symbol: Trading symbol

    Returns:
        Number of ticks
    """
    return int(round(price / get_min_tick(symbol)))


# Update cache with actual rates (would use API in production)
def update_cross_rates(rates: dict[str, float]) -> None:
    """
    Update cross rates cache with new values.

    Args:
        rates: Dictionary of currency pairs and rates
    """
    CROSS_RATES_CACHE.update(rates)
