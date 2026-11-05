"""Навыки торгового агента - обёртки над tcli для интеграции с торговым агентом.

Этот модуль предоставляет высокоуровневый API для взаимодействия с tcli.
Все функции принимают и возвращают Python-словари, автоматически вызывая
соответствующие команды tcli с флагами --json и --no-prompt.

Пример использования:
    >>> from skills import get_quote, place_order
    >>> quote = get_quote('SBER')
    >>> print(quote['price'])
    >>> result = place_order('SBER', 'buy', 1, price=285.50)
"""

from .account import get_account_info, get_accounts, get_current_account, select_account
from .analytics import (
    add_to_watchlist,
    get_instrument_by_figi,
    get_instrument_by_isin,
    get_instrument_info,
    get_watchlist,
    remove_from_watchlist,
    search_by_type,
    search_instruments,
)
from .market_data import get_candles, get_orders, get_portfolio, get_quote
from .risk_helpers import (
    estimate_commission,
    get_free_cash,
    has_position,
    is_market_open,
    position_size,
)
from .trading import cancel_order, get_order_info, place_order

__all__ = [
    # Market data
    'get_quote',
    'get_candles',
    'get_portfolio',
    'get_orders',
    
    # Trading
    'place_order',
    'cancel_order',
    'get_order_info',
    
    # Account
    'get_accounts',
    'select_account',
    'get_current_account',
    'get_account_info',
    
    # Analytics
    'search_instruments',
    'get_instrument_info',
    'get_instrument_by_figi',
    'get_instrument_by_isin',
    'search_by_type',
    'get_watchlist',
    'add_to_watchlist',
    'remove_from_watchlist',
    
    # Risk helpers (#30-#33)
    'position_size',
    'estimate_commission',
    'get_free_cash',
    'has_position',
    'is_market_open',
]
