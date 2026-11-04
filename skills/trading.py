"""Навыки для выполнения торговых операций."""

from typing import Optional

from .base import run_tcli_command


def place_order(
    ticker: str,
    side: str,
    lots: int,
    price: Optional[float] = None
) -> dict:
    """Выставить заявку на покупку или продажу.
    
    Args:
        ticker: Тикер инструмента (например, 'SBER')
        side: Направление операции ('buy' или 'sell')
        lots: Количество лотов
        price: Цена заявки (если None, рыночная заявка)
        
    Returns:
        Полный JSON response с информацией о заявке
        
    Example:
        >>> result = place_order('SBER', 'buy', 1, price=285.50)
        >>> print(result['order_id'])
    """
    if side not in ['buy', 'sell']:
        raise ValueError(f"side must be 'buy' or 'sell', got '{side}'")
    
    args = [f"order-{side}", ticker, "--quantity", str(lots), "--no-prompt", "--json"]
    if price is not None:
        args.extend(["--price", str(price)])
    
    return run_tcli_command(args)


def cancel_order(order_id: str) -> dict:
    """Отменить заявку.
    
    Args:
        order_id: ID заявки для отмены
        
    Returns:
        Полный JSON response с результатом отмены
        
    Example:
        >>> result = cancel_order('12345')
        >>> print(result['status'])
    """
    return run_tcli_command(["order-cancel", order_id, "--no-prompt", "--json"])


def get_order_info(order_id: str) -> dict:
    """Получить информацию о заявке.
    
    Note: Эта функция использует get_orders() и фильтрует по order_id.
    
    Args:
        order_id: ID заявки
        
    Returns:
        Словарь с информацией о заявке или пустой словарь, если заявка не найдена
    """
    from .market_data import get_orders
    
    orders_result = get_orders()
    orders = orders_result.get('orders', [])
    for order in orders:
        if order.get('order_id') == order_id:
            return order
    
    return {}
