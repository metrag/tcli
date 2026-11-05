"""Коды ошибок tcli для структурированного вывода."""

from enum import Enum


class ErrorCode(str, Enum):
    """Коды ошибок для JSON-вывода."""
    
    # Общие ошибки
    OK = "OK"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    
    # Ошибки конфигурации
    TOKEN_INVALID = "TOKEN_INVALID"
    CONTOUR_MISMATCH = "CONTOUR_MISMATCH"
    ENV_NOT_FOUND = "ENV_NOT_FOUND"
    
    # Ошибки инструмента
    INSTRUMENT_NOT_FOUND = "INSTRUMENT_NOT_FOUND"
    INVALID_TICKER = "INVALID_TICKER"
    INVALID_FIGI = "INVALID_FIGI"
    
    # Ошибки счёта
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    NO_ACCOUNTS = "NO_ACCOUNTS"
    MULTIPLE_ACCOUNTS = "MULTIPLE_ACCOUNTS"
    
    # Ошибки заявок
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    ORDER_REJECTED = "ORDER_REJECTED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_PRICE = "INVALID_PRICE"
    
    # Ошибки стопов
    STOP_ORDER_NOT_FOUND = "STOP_ORDER_NOT_FOUND"
    STOP_ORDER_REJECTED = "STOP_ORDER_REJECTED"
    
    # Ошибки рынка
    MARKET_CLOSED = "MARKET_CLOSED"
    TRADING_NOT_AVAILABLE = "TRADING_NOT_AVAILABLE"
    
    # Ошибки API
    RATE_LIMITED = "RATE_LIMITED"
    API_ERROR = "API_ERROR"
    TIMEOUT = "TIMEOUT"
    
    # Ошибки позиций
    POSITION_NOT_FOUND = "POSITION_NOT_FOUND"
    NO_POSITIONS = "NO_POSITIONS"


def get_exit_code(error: ErrorCode) -> int:
    """Получить код выхода для ошибки."""
    exit_codes = {
        ErrorCode.OK: 0,
        ErrorCode.UNKNOWN_ERROR: 1,
        ErrorCode.VALIDATION_ERROR: 2,
        ErrorCode.TOKEN_INVALID: 3,
        ErrorCode.INSTRUMENT_NOT_FOUND: 4,
        ErrorCode.INVALID_TICKER: 4,
        ErrorCode.INVALID_FIGI: 4,
        ErrorCode.NO_ACCOUNTS: 7,
        ErrorCode.MULTIPLE_ACCOUNTS: 8,
        ErrorCode.MARKET_CLOSED: 10,
        ErrorCode.TRADING_NOT_AVAILABLE: 11,
        ErrorCode.INSUFFICIENT_FUNDS: 12,
        ErrorCode.ORDER_NOT_FOUND: 13,
        ErrorCode.ORDER_REJECTED: 14,
        ErrorCode.STOP_ORDER_NOT_FOUND: 15,
        ErrorCode.STOP_ORDER_REJECTED: 16,
        ErrorCode.INVALID_QUANTITY: 17,
        ErrorCode.INVALID_PRICE: 18,
        ErrorCode.CONTOUR_MISMATCH: 19,
        ErrorCode.RATE_LIMITED: 20,
        ErrorCode.API_ERROR: 21,
        ErrorCode.TIMEOUT: 22,
        ErrorCode.POSITION_NOT_FOUND: 23,
        ErrorCode.NO_POSITIONS: 24,
        ErrorCode.ENV_NOT_FOUND: 25,
        ErrorCode.ACCOUNT_NOT_FOUND: 26,
    }
    return exit_codes.get(error, 1)
