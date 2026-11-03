"""Песочница Tinkoff Invest API: обёртка над SandboxClient, ретраи, live-гард.

Единственный доступный контур — SANDBOX: клиент подключается к sandbox-хосту
(`SandboxClient`), боевой контур в модуле не используется нигде.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, TypeVar

from tinkoff.invest.exceptions import InvestError, UnauthenticatedError
from tinkoff.invest.sandbox.client import SandboxClient as SdkSandboxClient
from tinkoff.invest.schemas import InstrumentType, MoneyValue

from .config import Settings
from .render import money_to_float

_log = logging.getLogger(__name__)

T = TypeVar("T")

# Транзиентные статусы gRPC: имеет смысл повторить запрос.
RETRYABLE_CODES = {"UNAVAILABLE", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED", "INTERNAL"}
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 0.5


class SandboxError(RuntimeError):
    """Ошибки уровня tcli (конфигурация, выбор счёта, ввод)."""


class NoAccountsError(SandboxError):
    pass


class AmbiguousAccountError(SandboxError):
    pass


def _code_name(exc: BaseException) -> str:
    """Имя статуса gRPC/SDK из исключения: 'UNAVAILABLE', 'UNAUTHENTICATED'..."""
    code = getattr(exc, "code", None)
    if code is None:
        return ""
    if callable(code):  # grpc.RpcError: .code() — метод
        try:
            code = code()
        except Exception:  # noqa: BLE001 — нечего извлекать
            return ""
    name = getattr(code, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(code, tuple) and len(code) > 1 and isinstance(code[1], str):
        return code[1]
    return str(code)


def is_transient(exc: BaseException) -> bool:
    return _code_name(exc) in RETRYABLE_CODES


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = RETRY_ATTEMPTS,
    base_delay: float = RETRY_BASE_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Повтор транзиентных ошибок с экспоненциальной паузой (0.5, 1.5, 4.5 c)."""
    last: Optional[BaseException] = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if attempt == attempts - 1 or not is_transient(exc):
                raise
            delay = base_delay * (3**attempt)
            _log.warning("транзиентная ошибка %s, повтор через %.1f с", _code_name(exc), delay)
            sleep(delay)
    raise last if last else RuntimeError("with_retries: пустой вызов")  # pragma: no cover


def api_error_text(exc: BaseException) -> str:
    """Человекочитаемое описание ошибки API."""
    if isinstance(exc, UnauthenticatedError):
        return "авторизация: токен недействителен или отозван (40003) — обновите .env"
    if isinstance(exc, InvestError):
        details = getattr(exc, "details", "") or ""
        code = _code_name(exc)
        return f"ошибка API {code}: {details}".strip()
    return f"{type(exc).__name__}: {exc}"


def _enum_name(value: Any) -> str:
    name = getattr(value, "name", None)
    if not isinstance(name, str):
        name = str(value)
    for prefix in (
        "ORDER_DIRECTION_",
        "EXECUTION_REPORT_STATUS_",
        "ACCOUNT_TYPE_",
        "ACCOUNT_STATUS_",
        "INSTRUMENT_TYPE_",
        "ORDER_TYPE_",
    ):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


class Sandbox:
    """Контекстный менеджер песочницы: только sandbox-операции, с ретраями."""

    def __init__(self, settings: Settings, client_factory: Optional[Callable[[str], Any]] = None):
        self._settings = settings
        self._factory = client_factory or (lambda token: SdkSandboxClient(token))
        self._raw: Any = None  # SDK Client (владелец канала)
        self._client: Any = None  # Services из Client.__enter__()
        self._tickers: dict[str, str] = {}

    def __enter__(self) -> Sandbox:
        if not self._settings.enabled:
            raise SandboxError("токен не задан: заполните .env (см. .env.example)")
        self._raw = self._factory(self._settings.invest_token)
        self._client = self._raw.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self._raw is not None:
            return bool(self._raw.__exit__(exc_type, exc, tb))
        return False

    # -- чтение ---------------------------------------------------------

    def accounts(self) -> list[Any]:
        resp = with_retries(lambda: self._client.users.get_accounts())
        return list(resp.accounts)

    def pick_account(self) -> Any:
        accounts = self.accounts()
        if not accounts:
            raise NoAccountsError(
                "нет счетов песочницы — откройте счёт в приложении Т-Банка (Инвестиции → Песочница)"
            )
        name = self._settings.sandbox_account_name
        if name:
            matched = [a for a in accounts if a.name == name]
            if not matched:
                available = ", ".join(a.name or a.id for a in accounts)
                raise NoAccountsError(f"счёт «{name}» не найден; есть: {available}")
            return matched[0]
        if len(accounts) == 1:
            return accounts[0]
        available = ", ".join(a.name or a.id for a in accounts)
        raise AmbiguousAccountError(
            f"несколько счетов — задайте SANDBOX_ACCOUNT_NAME в .env; варианты: {available}"
        )

    def portfolio(self, account_id: str) -> Any:
        return with_retries(lambda: self._client.operations.get_portfolio(account_id=account_id))

    def orders(self, account_id: str) -> list[Any]:
        resp = with_retries(lambda: self._client.orders.get_orders(account_id=account_id))
        return list(resp.orders)

    def ticker(self, figi: str) -> str:
        """Тикер по figi (кэш; при сбое — сам figi)."""
        if not figi:
            return ""
        if figi in self._tickers:
            return self._tickers[figi]
        try:
            resp = with_retries(
                lambda: self._client.instruments.get_instrument_by(
                    id_type=InstrumentType.INSTRUMENT_TYPE_FIGI, id=figi
                )
            )
            ticker = getattr(resp.instrument, "ticker", "") or figi
        except Exception:  # noqa: BLE001 — резолв тикера не критичен
            ticker = figi
        self._tickers[figi] = ticker
        return ticker

    # -- операции песочницы ---------------------------------------------

    def payin(self, account_id: str, amount: float) -> Any:
        if amount <= 0:
            raise SandboxError("сумма должна быть больше 0")
        units = int(amount)
        nano = int(round((amount - units) * 1e9))
        money = MoneyValue(currency="rub", units=units, nano=nano)
        return with_retries(
            lambda: self._client.sandbox.sandbox_pay_in(account_id=account_id, amount=money)
        )

    # -- удобные представления ------------------------------------------

    @staticmethod
    def account_row(account: Any) -> dict:
        return {
            "id": account.id,
            "name": account.name or account.id,
            "type": _enum_name(account.type),
            "status": _enum_name(account.status),
        }

    @staticmethod
    def portfolio_row(account_name: str, portfolio: Any) -> dict:
        cash = money_to_float(portfolio.total_amount_currencies)
        securities = sum(
            money_to_float(getattr(portfolio, field, 0))
            for field in (
                "total_amount_shares",
                "total_amount_bonds",
                "total_amount_etf",
                "total_amount_futures",
                "total_amount_options",
                "total_amount_sp",
            )
        )
        total = getattr(portfolio, "total_amount_portfolio", None)
        total = money_to_float(total) if total is not None else cash + securities
        return {
            "account": account_name,
            "cash": cash,
            "securities": securities,
            "total": total,
            "pnl": money_to_float(portfolio.expected_yield),
        }

    @staticmethod
    def position_row(position: Any) -> dict:
        quantity = money_to_float(position.quantity)
        current = money_to_float(position.current_price)
        return {
            "ticker": getattr(position, "ticker", "") or position.figi,
            "type": _enum_name(position.instrument_type),
            "quantity": position.quantity,
            "avg": position.average_position_price,
            "current": position.current_price,
            "value": quantity * current,
            "pnl": money_to_float(position.expected_yield),
        }

    @staticmethod
    def order_row(order: Any, ticker: str) -> dict:
        price = getattr(order, "initial_order_price", None) or getattr(
            order, "executed_order_price", None
        )
        return {
            "ticker": ticker,
            "direction": _enum_name(order.direction),
            "status": _enum_name(order.execution_report_status),
            "lots": order.lots_executed,
            "price": price,
            "order_id": order.order_id,
        }
