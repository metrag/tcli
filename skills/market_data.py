"""Навыки для получения рыночных данных."""

from typing import Any

from .base import run_tcli_command


def get_quote(ticker: str) -> dict[str, Any]:
    """Получить текущую цену инструмента.
    
    Args:
        ticker: Тикер инструмента (например, 'SBER')
        
    Returns:
        Словарь с данными:
        {
            'ticker': str,
            'figi': str,
            'price': str,
            'time': str
        }
        
    Example:
        >>> quote = get_quote('SBER')
        >>> print(quote['price'])
        '285.50'
    """
    return run_tcli_command(['quote', ticker])


def get_candles(
    ticker: str,
    interval: str = '1day',
    days: int = 30
) -> dict[str, Any]:
    """Получить историю свечей инструмента.
    
    Args:
        ticker: Тикер инструмента
        interval: Интервал свечи (1min, 5min, 15min, 1hour, 1day)
        days: Количество дней истории
        
    Returns:
        Словарь с данными:
        {
            'ticker': str,
            'interval': str,
            'days': int,
            'candles': list[dict]
        }
        Каждая свеча: {'time': str, 'open': str, 'high': str, 'low': str, 'close': str, 'volume': int}
        
    Example:
        >>> candles = get_candles('SBER', interval='1hour', days=7)
        >>> print(len(candles['candles']))
        168
    """
    return run_tcli_command([
        'candles', ticker,
        '--interval', interval,
        '--days', str(days)
    ])


def get_portfolio() -> dict[str, Any]:
    """Получить позиции портфеля.
    
    Returns:
        Словарь с данными:
        {
            'positions': [
                {
                    'ticker': str,
                    'figi': str,
                    'quantity': str,
                    'average_price': str,
                    'current_price': str,
                    'value': str,
                    'pnl': str,
                    'pnl_percent': str
                },
                ...
            ]
        }
        
    Example:
        >>> portfolio = get_portfolio()
        >>> for pos in portfolio['positions']:
        ...     print(f"{pos['ticker']}: {pos['quantity']} @ {pos['current_price']}")
    """
    return run_tcli_command(['positions'])


def get_status() -> dict[str, Any]:
    """Получить статус счетов и сводку портфеля.
    
    Returns:
        Словарь с данными:
        {
            'contour': str,
            'accounts': list[dict],
            'portfolio': {
                'total_value': str,
                'total_pnl': str,
                'cash': str,
                'securities': str
            }
        }
    """
    return run_tcli_command(['status'])


def get_orders() -> dict[str, Any]:
    """Получить список активных заявок.
    
    Returns:
        Словарь с данными:
        {
            'orders': [
                {
                    'order_id': str,
                    'ticker': str,
                    'direction': str,
                    'quantity': str,
                    'price': str,
                    'status': str,
                    'created_at': str
                },
                ...
            ]
        }
    """
    return run_tcli_command(['orders'])
