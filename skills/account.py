"""Навыки для управления аккаунтами."""

from typing import Any, Optional

from .base import run_tcli_command


def get_accounts() -> dict[str, list[dict[str, Any]]]:
    """Получить список всех счетов.
    
    Returns:
        Полный JSON response с ключом "accounts":
        {
            "accounts": [
                {
                    'account_id': str,
                    'name': str,
                    'type': str,
                    'status': str
                },
                ...
            ]
        }
        
    Example:
        >>> result = get_accounts()
        >>> for acc in result['accounts']:
        ...     print(f"{acc['name']}: {acc['account_id']}")
    """
    return run_tcli_command(["account-list", "--json"])


def select_account(account_name: str) -> dict:
    """Выбрать активный счёт для работы.
    
    Args:
        account_name: Имя счёта для выбора
        
    Returns:
        Словарь с результатом:
        {
            'account_id': str,
            'account_name': str,
            'status': str,
            'message': str
        }
        
    Example:
        >>> result = select_account('Main')
        >>> print(result['message'])
    """
    return run_tcli_command(f"account-select {account_name}")


def get_current_account() -> Optional[dict]:
    """Получить информацию о текущем выбранном аккаунте.
    
    Returns:
        Словарь с информацией о текущем аккаунте или None, если не выбран
    """
    accounts = get_accounts()
    if not accounts:
        return None
    
    # Возвращаем первый аккаунт как текущий
    # В реальной реализации нужно хранить состояние выбранного аккаунта
    return accounts[0] if accounts else None


def get_account_info(account_id: str) -> Optional[dict]:
    """Получить детальную информацию о конкретном аккаунте.
    
    Args:
        account_id: ID аккаунта
        
    Returns:
        Словарь с информацией об аккаунте или None, если не найден
    """
    accounts = get_accounts()
    for acc in accounts:
        if acc.get('account_id') == account_id:
            return acc
    return None
