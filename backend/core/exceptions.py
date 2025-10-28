"""
Custom exceptions for Bybit API operations.

Provides specific exception types for different error scenarios,
making error handling more precise and informative.
"""


class BybitAPIError(Exception):
    """
    Базовая ошибка Bybit API.
    """
    def __init__(self, message: str, ret_code: int | None = None, ret_msg: str | None = None):
        self.message = message
        self.ret_code = ret_code
        self.ret_msg = ret_msg
        super().__init__(self.message)
    
    def __str__(self):
        if self.ret_code:
            return f"BybitAPIError [{self.ret_code}]: {self.message}"
        return f"BybitAPIError: {self.message}"


class BybitRateLimitError(BybitAPIError):
    """
    Превышен rate limit API.
    
    Рекомендация: подождать и повторить запрос.
    """
    pass


class BybitSymbolNotFoundError(BybitAPIError):
    """
    Символ не найден на бирже.
    
    Рекомендация: проверить правильность написания символа.
    """
    pass


class BybitInvalidIntervalError(BybitAPIError):
    """
    Неверный интервал свечей.
    
    Рекомендация: использовать допустимые интервалы (1, 5, 15, 60, D, W, M).
    """
    pass


class BybitInvalidParameterError(BybitAPIError):
    """
    Неверные параметры запроса.
    
    Рекомендация: проверить параметры API запроса.
    """
    pass


class BybitAuthenticationError(BybitAPIError):
    """
    Ошибка аутентификации (неверный API key/secret).
    
    Рекомендация: проверить API credentials.
    """
    pass


class BybitConnectionError(BybitAPIError):
    """
    Ошибка соединения с API.
    
    Рекомендация: проверить интернет соединение, повторить запрос.
    """
    pass


class BybitTimeoutError(BybitAPIError):
    """
    Timeout при выполнении запроса.
    
    Рекомендация: увеличить timeout, повторить запрос.
    """
    pass


class BybitDataError(BybitAPIError):
    """
    Ошибка в полученных данных (невалидный формат, пустой ответ).
    
    Рекомендация: проверить параметры запроса, возможно данных нет за указанный период.
    """
    pass


# Mapping Bybit API error codes to exceptions
BYBIT_ERROR_MAPPING = {
    10001: (BybitInvalidParameterError, "Parameter error"),
    10002: (BybitInvalidParameterError, "Invalid request"),
    10003: (BybitAuthenticationError, "Invalid API key"),
    10004: (BybitRateLimitError, "Rate limit exceeded"),
    10005: (BybitAuthenticationError, "Permission denied"),
    10006: (BybitRateLimitError, "Too many requests"),
    10016: (BybitSymbolNotFoundError, "Symbol not found"),
    10017: (BybitInvalidIntervalError, "Invalid interval"),
    33004: (BybitInvalidIntervalError, "Invalid interval"),
}


def handle_bybit_error(ret_code: int, ret_msg: str) -> BybitAPIError:
    """
    Создать соответствующее исключение на основе кода ошибки Bybit.
    
    Args:
        ret_code: Код ошибки от Bybit API
        ret_msg: Сообщение об ошибке от Bybit API
    
    Returns:
        Экземпляр соответствующего исключения
    """
    if ret_code in BYBIT_ERROR_MAPPING:
        exception_class, default_msg = BYBIT_ERROR_MAPPING[ret_code]
        message = ret_msg or default_msg
        return exception_class(message, ret_code=ret_code, ret_msg=ret_msg)
    
    # Общая ошибка для неизвестных кодов
    return BybitAPIError(f"API error {ret_code}: {ret_msg}", ret_code=ret_code, ret_msg=ret_msg)
