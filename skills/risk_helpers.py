"""Risk helpers — вычислительные функции для риск-менеджмента.

Согласно TODO.md, risk helpers должны быть только в skills/, без CLI команд.
Эти функции используют Broker напрямую, без subprocess вызовов.
"""

from tcli.client import Broker
from tcli.config import Settings


def position_size(
    risk_amount: float,
    entry_price: float,
    stop_loss_price: float,
    lot_size: float,
    min_step: float = 0.01,
) -> int:
    """Рассчитать размер позиции для заданного риска.
    
    Формула: lots = floor(risk_amount / ((entry - stop_loss) * lot_size))
    
    Args:
        risk_amount: Сумма риска в рублях (максимальный убыток)
        entry_price: Цена входа
        stop_loss_price: Цена стоп-лосса
        lot_size: Размер лота (количество акций в одном лоте)
        min_step: Минимальный шаг цены (по умолчанию 0.01)
        
    Returns:
        Количество лотов для заданного риска. 0, если:
        - stop_loss >= entry (некорректный SL)
        - Не хватает средств
        - Ошибка в расчётах
        
    Example:
        >>> lots = position_size(
        ...     risk_amount=10000,  # риск 10000₽
        ...     entry_price=300.0,   # вход по 300₽
        ...     stop_loss_price=295.0,  # SL на 295₽
        ...     lot_size=10  # лот = 10 акций
        ... )
        >>> print(lots)  # 200 лотов
        200
        
    Note:
        Эта функция не требует API вызовов и работает локально.
        Для проверки доступных средств используйте get_free_cash().
    """
    # Создаём временный Broker для доступа к методу calculate_position_size
    settings = Settings.load()
    if not settings.enabled:
        return 0
    
    with Broker(settings) as br:
        return br.calculate_position_size(
            risk_amount=risk_amount,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            lot_size=lot_size,
            min_step=min_step,
        )


def estimate_commission(amount: float, tariff: float = 0.003) -> float:
    """Оценить комиссию по тарифу счёта.
    
    Args:
        amount: Сумма операции в рублях
        tariff: Тариф комиссии (по умолчанию 0.3% = 0.003)
        
    Returns:
        Размер комиссии в рублях
        
    Example:
        >>> commission = estimate_commission(100000, tariff=0.003)
        >>> print(commission)  # 300₽
        300.0
        
    Note:
        Для скальпинга комиссии+спред критичны — проверяйте тариф счёта.
    """
    settings = Settings.load()
    if not settings.enabled:
        return 0.0
    
    with Broker(settings) as br:
        return br.estimate_commission(amount=amount, tariff=tariff)


def get_free_cash() -> float:
    """Получить свободные средства на счёте.
    
    Returns:
        Свободные средства в рублях (Decimal converted to float)
        
    Example:
        >>> cash = get_free_cash()
        >>> print(cash)
        150000.0
    """
    from tcli.client import Broker
    from tcli.config import Settings
    
    settings = Settings.load()
    if not settings.enabled:
        return 0.0
    
    with Broker(settings) as br:
        account = br.pick_account()
        portfolio = br.portfolio(account.id)
        # total_amount_currencies - это MoneyValue, нужно конвертировать
        from tcli.render import money_to_float
        return money_to_float(portfolio.total_amount_currencies)


def has_position(ticker: str) -> bool:
    """Проверить наличие позиции по тикеру.
    
    Args:
        ticker: Тикер инструмента
        
    Returns:
        True, если позиция есть (balance != 0), иначе False
        
    Example:
        >>> if has_position('SBER'):
        ...     print("Позиция SBER открыта")
    """
    from tcli.client import Broker
    from tcli.config import Settings
    
    settings = Settings.load()
    if not settings.enabled:
        return False
    
    with Broker(settings) as br:
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        if not figi:
            return False
        
        account = br.pick_account()
        position = br.get_position(account.id, figi)
        return position is not None and position.balance != 0


def is_market_open(ticker: str) -> bool:
    """Проверить, открыт ли рынок для инструмента.
    
    Args:
        ticker: Тикер инструмента
        
    Returns:
        True, если рынок открыт, иначе False
        
    Example:
        >>> if is_market_open('SBER'):
        ...     print("Можно торговать SBER")
    """
    from tcli.client import Broker
    from tcli.config import Settings
    
    settings = Settings.load()
    if not settings.enabled:
        return False
    
    with Broker(settings) as br:
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        if not figi:
            return False
        
        return br.is_market_open(figi)
