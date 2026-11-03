"""Клиент Tinkoff Invest API: поддержка SANDBOX и LIVE контуров."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from tinkoff.invest import Client
from tinkoff.invest.exceptions import InvestError, RequestError, UnauthenticatedError
from tinkoff.invest.sandbox.client import SandboxClient as SdkSandboxClient
from tinkoff.invest.schemas import (
    CandleInterval,
    InstrumentType,
    MoneyValue,
    OrderDirection,
    OrderType,
    Quotation,
)

from .config import Contour, Settings
from .render import money_to_float

_log = logging.getLogger(__name__)


class SandboxError(RuntimeError):
    """Базовая ошибка tcli (конфигурация, выбор счёта, ввод)."""


class NoAccountsError(SandboxError):
    pass


class AmbiguousAccountError(SandboxError):
    pass


class LiveUnsupportedError(SandboxError):
    """Операция недоступна на боевом контуре."""


class TickerNotFoundError(SandboxError):
    pass


# Транзиентные статусы gRPC
RETRYABLE_CODES = {"UNAVAILABLE", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED", "INTERNAL"}
RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 0.5


def _code_name(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    if code is None:
        return ""
    if callable(code):
        try:
            code = code()
        except Exception:
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
    fn: Callable[[], Any],
    *,
    attempts: int = RETRY_ATTEMPTS,
    base_delay: float = RETRY_BASE_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
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
    raise last if last else RuntimeError("with_retries: пустой вызов")


def api_error_text(exc: BaseException) -> str:
    if isinstance(exc, UnauthenticatedError):
        return "авторизация: токен недействителен или отозван (40003) — обновите .env"
    if isinstance(exc, RequestError):
        details = getattr(exc, "details", "") or ""
        code = _code_name(exc)
        return f"ошибка API {code}: {details}".strip()
    if isinstance(exc, InvestError):
        return f"ошибка API: {exc}"
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
        "OPERATION_STATE_",
        "OPERATION_TYPE_",
        "CANDLE_INTERVAL_",
    ):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


class Broker:
    """Контекстный менеджер для Tinkoff Invest API: SANDBOX или LIVE."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._raw: Any = None
        self._client: Any = None
        self._tickers: dict[str, str] = {}
        self._fights: dict[str, str] = {}

    def __enter__(self) -> Broker:
        if not self._settings.enabled:
            raise SandboxError("токен не задан: заполните .env (см. .env.example)")
        
        contour = self._settings.contour
        token = self._settings.invest_token
        
        if contour == Contour.SANDBOX:
            self._raw = SdkSandboxClient(token)
        else:
            self._raw = Client(token)
        
        self._client = self._raw.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self._raw is not None:
            return bool(self._raw.__exit__(exc_type, exc, tb))
        return False

    @property
    def contour(self) -> Contour:
        return self._settings.contour

    @property
    def is_sandbox(self) -> bool:
        return self._settings.contour == Contour.SANDBOX

    # -- Счета ------------------------------------------------------------

    def accounts(self) -> list[Any]:
        resp = with_retries(lambda: self._client.users.get_accounts())
        return list(resp.accounts)

    def pick_account(self) -> Any:
        accounts = self.accounts()
        if not accounts:
            raise NoAccountsError(
                f"нет счетов — создайте счёт в {'песочнице' if self.is_sandbox else 'боевом контуре'}"
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

    def create_account(self, name: str = "") -> Any:
        if not self.is_sandbox:
            raise LiveUnsupportedError("создание счёта доступно только в песочнице")
        return with_retries(lambda: self._client.sandbox.open_sandbox_account(name=name))

    def close_account(self, account_id: str) -> Any:
        if not self.is_sandbox:
            raise LiveUnsupportedError("закрытие счёта доступно только в песочнице")
        return with_retries(
            lambda: self._client.sandbox.close_sandbox_account(account_id=account_id)
        )

    # -- Портфель ---------------------------------------------------------

    def portfolio(self, account_id: str) -> Any:
        return with_retries(
            lambda: self._client.operations.get_portfolio(account_id=account_id)
        )

    # -- Заявки -----------------------------------------------------------

    def orders(self, account_id: str) -> list[Any]:
        resp = with_retries(lambda: self._client.orders.get_orders(account_id=account_id))
        return list(resp.orders)

    def place_order(
        self,
        account_id: str,
        figi: str,
        direction: OrderDirection,
        quantity: int,
        price: Optional[Quotation] = None,
        order_type: OrderType = OrderType.ORDER_TYPE_LIMIT,
    ) -> Any:
        return with_retries(
            lambda: self._client.orders.post_order(
                account_id=account_id,
                figi=figi,
                direction=direction,
                quantity=quantity,
                price=price,
                order_type=order_type,
            )
        )

    def cancel_order(self, account_id: str, order_id: str) -> Any:
        return with_retries(
            lambda: self._client.orders.cancel_order(account_id=account_id, order_id=order_id)
        )

    # -- Операции ---------------------------------------------------------

    def operations(
        self,
        account_id: str,
        from_: Optional[Any] = None,
        to: Optional[Any] = None,
        state: Any = None,
        figi: str = "",
    ) -> list[Any]:
        from tinkoff.invest.schemas import OperationState
        
        op_state = state if state is not None else OperationState.OPERATION_STATE_EXECUTED
        resp = with_retries(
            lambda: self._client.operations.get_operations(
                account_id=account_id,
                from_=from_,
                to=to,
                state=op_state,
                figi=figi,
            )
        )
        return list(resp.operations)

    # -- Песочница: пополнение --------------------------------------------

    def payin(self, account_id: str, amount: float) -> Any:
        if not self.is_sandbox:
            raise LiveUnsupportedError("пополнение доступно только в песочнице")
        if amount <= 0:
            raise SandboxError("сумма должна быть больше 0")
        units = int(amount)
        nano = int(round((amount - units) * 1e9))
        money = MoneyValue(currency="rub", units=units, nano=nano)
        return with_retries(
            lambda: self._client.sandbox.sandbox_pay_in(account_id=account_id, amount=money)
        )

    # -- Инструменты ------------------------------------------------------

    def find_instrument(self, query: str) -> list[Any]:
        resp = with_retries(lambda: self._client.instruments.find_instrument(query=query))
        return list(resp.instruments)

    def instrument_by_figi(self, figi: str) -> Any:
        try:
            resp = with_retries(
                lambda: self._client.instruments.get_instrument_by(
                    id_type=InstrumentType.INSTRUMENT_TYPE_FIGI, id=figi
                )
            )
            return resp.instrument
        except Exception as exc:
            raise TickerNotFoundError(f"инструмент по FIGI не найден: {figi}") from exc

    def instrument_by_ticker(self, ticker: str, class_code: str = "") -> Any:
        try:
            resp = with_retries(
                lambda: self._client.instruments.get_instrument_by(
                    id_type=InstrumentType.INSTRUMENT_TYPE_TICKER, id=ticker
                )
            )
            return resp.instrument
        except Exception as exc:
            raise TickerNotFoundError(f"инструмент по тикеру не найден: {ticker}") from exc

    def ticker(self, figi: str) -> str:
        if not figi:
            return ""
        if figi in self._tickers:
            return self._tickers[figi]
        try:
            instrument = self.instrument_by_figi(figi)
            ticker = getattr(instrument, "ticker", "") or figi
        except TickerNotFoundError:
            ticker = figi
        self._tickers[figi] = ticker
        return ticker

    def figi(self, ticker: str, class_code: str = "") -> str:
        if not ticker:
            return ""
        if ticker in self._fights:
            return self._fights[ticker]
        instrument = self.instrument_by_ticker(ticker, class_code)
        figi = getattr(instrument, "figi", "")
        if not figi:
            raise TickerNotFoundError(f"FIGI для {ticker} не найден")
        self._fights[ticker] = figi
        return figi

    # -- Рыночные данные --------------------------------------------------

    def last_prices(self, figi: list[str]) -> list[Any]:
        resp = with_retries(
            lambda: self._client.market_data.get_last_prices(figi=figi)
        )
        return list(resp.last_prices)

    def candles(
        self, figi: str, interval: CandleInterval, from_: Any, to: Any
    ) -> list[Any]:
        resp = with_retries(
            lambda: self._client.market_data.get_candles(
                figi=figi, interval=interval, from_=from_, to=to
            )
        )
        return list(resp.candles)

    # -- Представления ----------------------------------------------------

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

    @staticmethod
    def operation_row(operation: Any, ticker: str) -> dict:
        op_type = getattr(operation, "operation_type", None) or getattr(operation, "type", None)
        return {
            "date": getattr(operation, "date", None),
            "type": _enum_name(op_type),
            "ticker": ticker,
            "quantity": getattr(operation, "quantity", None),
            "price": getattr(operation, "price", None),
            "amount": getattr(operation, "payment", None),
            "currency": getattr(operation, "currency", ""),
        }
