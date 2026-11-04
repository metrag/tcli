"""Навыки для аналитики и поиска инструментов."""

from typing import Optional

from .base import run_tcli_command


def search_instruments(query: str) -> dict:
    """Поиск инструментов по тикеру, названию или ISIN.
    
    Args:
        query: Поисковый запрос (тикер, название, ISIN, FIGI, UID)
        
    Returns:
        Полный JSON response с ключом "instruments":
        {
            "instruments": [
                {
                    'ticker': str,
                    'figi': str,
                    'name': str,
                    'type': str,
                    'class': str,
                    'isin': str
                },
                ...
            ]
        }
        
    Example:
        >>> result = search_instruments('SBER')
        >>> for inst in result['instruments']:
        ...     print(f"{inst['ticker']}: {inst['name']}")
    """
    return run_tcli_command(["find", query, "--json"])


def get_instrument_info(identifier: str) -> dict:
    """Получить детальную информацию об инструменте.
    
    Args:
        identifier: Идентификатор инструмента (тикер, FIGI, UID, ISIN)
        
    Returns:
        Словарь с информацией об инструменте:
        {
            'name': str,
            'ticker': str,
            'figi': str,
            'isin': str,
            'type': str,
            'currency': str,
            'lot': int,
            'exchange': str,
            'class_code': str,
            'trading_status': str
        }
        
    Example:
        >>> info = get_instrument_info('SBER')
        >>> print(f"{info['name']} ({info['ticker']})")
    """
    return run_tcli_command(["info", identifier, "--json"])


def get_instrument_by_figi(figi: str) -> Optional[dict]:
    """Получить информацию об инструменте по FIGI.
    
    Args:
        figi: FIGI инструмента
        
    Returns:
        Словарь с информацией или None, если не найден
    """
    result = get_instrument_info(figi)
    if result.get('figi') == figi:
        return result
    return None


def get_instrument_by_isin(isin: str) -> Optional[dict]:
    """Получить информацию об инструменте по ISIN.
    
    Args:
        isin: ISIN инструмента
        
    Returns:
        Словарь с информацией или None, если не найден
    """
    result = get_instrument_info(isin)
    if result.get('isin') == isin:
        return result
    return None


def search_by_type(instrument_type: str, query: str = "") -> list[dict]:
    """Поиск инструментов по типу.
    
    Args:
        instrument_type: Тип инструмента (share, bond, etf, futures, option, currency)
        query: Дополнительный поисковый запрос
        
    Returns:
        Список найденных инструментов указанного типа
        
    Example:
        >>> shares = search_by_type('share', 'SBER')
        >>> bonds = search_by_type('bond')
    """
    # Если есть запрос, ищем и фильтруем по типу
    if query:
        instruments = search_instruments(query)
        return [
            inst for inst in instruments
            if inst.get('type', '').lower() == instrument_type.lower()
        ]
    
    # Если запроса нет, ищем по пустой строке (все инструменты) и фильтруем
    instruments = search_instruments("")
    return [
        inst for inst in instruments
        if inst.get('type', '').lower() == instrument_type.lower()
    ]


def get_watchlist() -> list[str]:
    """Получить список отслеживаемых инструментов (watchlist).
    
    Returns:
        Список тикеров в watchlist
        
    Example:
        >>> watchlist = get_watchlist()
        >>> print(watchlist)
        ['SBER', 'GAZP', 'LKOH']
    """
    result = run_tcli_command("watchlist list")
    return result.get('tickers', [])


def add_to_watchlist(ticker: str) -> dict:
    """Добавить инструмент в watchlist.
    
    Args:
        ticker: Тикер инструмента для добавления
        
    Returns:
        Словарь с результатом операции
    """
    return run_tcli_command(f"watchlist add {ticker}")


def remove_from_watchlist(ticker: str) -> dict:
    """Удалить инструмент из watchlist.
    
    Args:
        ticker: Тикер инструмента для удаления
        
    Returns:
        Словарь с результатом операции
    """
    return run_tcli_command(f"watchlist remove {ticker}")
