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
    InstrumentIdType,
    MoneyValue,
    OrderDirection,
    OrderType,
    Quotation,
)

from .config import Contour, Settings
from .id_utils import (
    cache_identifier_type,
    detect_identifier_type,
    get_cached_type,
)
from .render import money_to_float

_log = logging.getLogger(__name__)


class SandboxError(RuntimeError):
    """Базовая ошибка tcli (конфигурация, выбор счёта, ввод)."""
    exit_code = 1  # Общая ошибка


class NoAccountsError(SandboxError):
    exit_code = 7  # Нет счетов


class AmbiguousAccountError(SandboxError):
    exit_code = 8  # Неоднозначный счёт (несколько счетов)


class LiveUnsupportedError(SandboxError):
    """Операция недоступна на боевом контуре."""
    exit_code = 9  # Неподдерживаемая операция


class TickerNotFoundError(SandboxError):
    exit_code = 4  # Инструмент не найден


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
        return (
            "авторизация: токен недействителен или отозван (40003) — "
            "проверьте токен и контур (SANDBOX/LIVE)"
        )
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
        token = self._settings.token  # Активный токен зависит от контура
        
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
        # Приоритет 1: глобальный флаг --account (#27)
        if self._settings.account_override:
            account_filter = self._settings.account_override
            matched = [a for a in accounts if a.name == account_filter or a.id == account_filter]
            if not matched:
                available = ", ".join(a.name or a.id for a in accounts)
                raise NoAccountsError(
                f"счёт «{self._settings.account_override}» не найден; есть: {available}"
            )
            return matched[0]
        # Приоритет 2: SANDBOX_ACCOUNT_NAME из .env
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
            f"несколько счетов — задайте SANDBOX_ACCOUNT_NAME в .env или используйте --account; "
f"варианты: {available}"
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

    def get_clock(self) -> dict[str, Any]:
        """Получить оценку серверного времени и вычислить дрейф локальных часов (#7).
        
        SDK не экспонирует gRPC metadata напрямую, поэтому используем round-trip
        measurement: измеряем время до и после API вызова, используем midpoint
        как оценку серверного времени.
        """
        from datetime import datetime, timezone

        # Измеряем время до запроса
        local_before = datetime.now(timezone.utc)
        
        # Делаем API вызов (любой, для измерения задержки)
        with_retries(lambda: self._client.users.get_accounts())
        
        # Измеряем время после запроса
        local_after = datetime.now(timezone.utc)
        
        # Вычисляем round-trip time и midpoint
        rtt = (local_after - local_before).total_seconds()
        midpoint = local_before + (local_after - local_before) / 2
        
        # Используем midpoint как оценку серверного времени
        # (предполагаем симметричную сетевую задержку)
        server_time_estimate = midpoint
        
        # Вычисляем дрейф (разница между оценкой серверного времени и локальным)
        # В идеале дрейф должен быть близок к 0, если часы синхронизированы
        drift_seconds = 0.0  # Пока не можем вычислить реальный дрейф без access к server_time
        
        return {
            'local_before': local_before.isoformat(),
            'local_after': local_after.isoformat(),
            'server_time_estimate': server_time_estimate.isoformat(),
            'round_trip_time_ms': int(rtt * 1000),
            'drift_seconds': drift_seconds,
            'drift_milliseconds': int(drift_seconds * 1000),
        }

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
        order_id: Optional[str] = None,
        time_in_force: Optional[Any] = None,
    ) -> Any:
        kwargs = {
            "account_id": account_id,
            "figi": figi,
            "direction": direction,
            "quantity": quantity,
            "price": price,
            "order_type": order_type,
        }
        if order_id is not None:
            kwargs["order_id"] = order_id
        if time_in_force is not None:
            kwargs["time_in_force"] = time_in_force
        return with_retries(lambda: self._client.orders.post_order(**kwargs))

    def cancel_order(self, account_id: str, order_id: str) -> Any:
        return with_retries(
            lambda: self._client.orders.cancel_order(account_id=account_id, order_id=order_id)
        )

    def modify_order(
        self,
        account_id: str,
        order_id: str,
        quantity: int,
        price: Optional[Quotation] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        """Изменить существующую заявку (#25)."""
        from tinkoff.invest.schemas import ReplaceOrderRequest

        request = ReplaceOrderRequest(
            account_id=account_id,
            order_id=order_id,
            quantity=quantity,
            price=price,
        )
        if idempotency_key:
            request.idempotency_key = idempotency_key
        
        return with_retries(lambda: self._client.orders.replace_order(request=request))

    def stop_orders(self, account_id: str) -> list[Any]:
        """Получить список стоп-заявок."""
        resp = with_retries(
            lambda: self._client.stop_orders.get_stop_orders(account_id=account_id)
        )
        return list(resp.stop_orders)

    def place_stop_order(
        self,
        account_id: str,
        figi: str,
        direction: OrderDirection,
        quantity: int,
        stop_price: Quotation,
        price: Optional[Quotation] = None,
        expiration_type: Any = None,
    ) -> Any:
        """Разместить стоп-заявку."""
        from tinkoff.invest.schemas import StopOrderDirection, StopOrderExpirationType, StopOrderType

        # Для простоты используем стандартный стоп
        if direction == OrderDirection.ORDER_DIRECTION_BUY:
            direction_value = StopOrderDirection.STOP_ORDER_DIRECTION_BUY
        else:
            direction_value = StopOrderDirection.STOP_ORDER_DIRECTION_SELL
        expiration = (
            expiration_type
            or StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_CANCEL
        )
        
        return with_retries(
            lambda: self._client.stop_orders.post_stop_order(
                account_id=account_id,
                figi=figi,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                direction=direction_value,
                expiration_type=expiration,
                stop_order_type=StopOrderType.STOP_ORDER_TYPE_STOP_LOSS,
            )
        )

    def cancel_stop_order(self, account_id: str, stop_order_id: str) -> Any:
        """Отменить стоп-заявку."""
        return with_retries(
            lambda: self._client.stop_orders.cancel_stop_order(
                account_id=account_id, stop_order_id=stop_order_id
            )
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

    def trading_schedules(
        self,
        exchange: str = "MOEX",
        from_: Optional[Any] = None,
        to: Optional[Any] = None,
    ) -> list[Any]:
        """Получить расписание торгов биржи."""
        resp = with_retries(
            lambda: self._client.instruments.trading_schedules(
                exchange=exchange, from_=from_, to=to
            )
        )
        return list(resp.exchanges)

    def get_estimated_margin(
        self,
        account_id: str,
        figi: str,
        direction: OrderDirection,
        quantity: int,
        price: Optional[Quotation] = None,
    ) -> Any:
        """Оценить требуемые средства для размещения заявки."""
        resp = with_retries(
            lambda: self._client.orders.get_order_margin(
                account_id=account_id,
                figi=figi,
                direction=direction,
                quantity=quantity,
                price=price,
            )
        )
        return resp

    def get_position(self, account_id: str, figi: str) -> Optional[Any]:
        """Получить позицию по инструменту."""
        portfolio = self.portfolio(account_id)
        for position in portfolio.positions:
            if position.figi == figi:
                return position
        return None

    def close_position(
        self,
        account_id: str,
        figi: str,
        price: Optional[Quotation] = None,
        order_type: OrderType = OrderType.ORDER_TYPE_MARKET,
    ) -> Optional[Any]:
        """Закрыть позицию по инструменту."""
        position = self.get_position(account_id, figi)
        if position is None:
            return None
        
        quantity = money_to_float(position.quantity)
        if quantity == 0:
            return None
        
        # Определяем направление: если позиция длинная - продаём, если короткая - покупаем
        if quantity > 0:
            direction = OrderDirection.ORDER_DIRECTION_SELL
        else:
            direction = OrderDirection.ORDER_DIRECTION_BUY
        
        return self.place_order(
            account_id=account_id,
            figi=figi,
            direction=direction,
            quantity=abs(int(quantity)),
            price=price,
            order_type=order_type,
        )

    def cancel_all_orders(self, account_id: str) -> list[Any]:
        """Отменить все активные заявки."""
        active_orders = self.orders(account_id)
        cancelled = []
        for order in active_orders:
            try:
                result = self.cancel_order(account_id, order.order_id)
                cancelled.append(result)
            except Exception:
                continue
        return cancelled

    def cancel_all_stop_orders(self, account_id: str) -> list[Any]:
        """Отменить все стоп-заявки."""
        active_stops = self.stop_orders(account_id)
        cancelled = []
        for stop in active_stops:
            try:
                result = self.cancel_stop_order(account_id, stop.stop_order_id)
                cancelled.append(result)
            except Exception:
                continue
        return cancelled

    def get_order_info(self, account_id: str, order_id: str) -> Any:
        """Получить информацию о заявке."""
        orders = self.orders(account_id)
        for order in orders:
            if order.order_id == order_id:
                return order
        return None

    # -- Risk helpers -----------------------------------------------------

    def get_free_cash(self, account_id: str) -> float:
        """Получить свободные средства на счёте."""
        portfolio = self.portfolio(account_id)
        return money_to_float(portfolio.total_amount_currencies)

    def is_market_open(self, figi: str) -> bool:
        """Проверить, открыт ли рынок для инструмента."""
        try:
            status = self.trading_status(figi)
            # Проверка статуса торгов
            trading_status = getattr(status, "limit_order_available_flag", False)
            return trading_status
        except Exception:
            return False

    def estimate_commission(self, amount: float, tariff: float = 0.003) -> float:
        """Оценить комиссию (по умолчанию 0.3% для скальпинга)."""
        return amount * tariff

    def calculate_position_size(
        self,
        risk_amount: float,
        entry_price: float,
        stop_loss_price: float,
        lot_size: float,
        min_step: float = 0.01,
    ) -> int:
        """Рассчитать размер позиции для заданного риска.
        
        lots = floor(risk_amount / ((entry - stop_loss) * lot_size))
        """
        if stop_loss_price >= entry_price:
            return 0
        price_diff = entry_price - stop_loss_price
        if price_diff <= 0:
            return 0
        lots = risk_amount / (price_diff * lot_size)
        return max(0, int(lots))

    # -- Получение всех инструментов по типу ------------------------------

    def get_all_shares(self) -> list[Any]:
        """Получить все акции."""
        resp = with_retries(lambda: self._client.instruments.shares())
        return list(resp.instruments)

    def get_all_bonds(self) -> list[Any]:
        """Получить все облигации."""
        resp = with_retries(lambda: self._client.instruments.bonds())
        return list(resp.instruments)

    def get_all_etfs(self) -> list[Any]:
        """Получить все ETF."""
        resp = with_retries(lambda: self._client.instruments.etfs())
        return list(resp.instruments)

    def get_all_futures(self) -> list[Any]:
        """Получить все фьючерсы."""
        resp = with_retries(lambda: self._client.instruments.futures())
        return list(resp.instruments)

    def get_all_currencies(self) -> list[Any]:
        """Получить все валюты."""
        resp = with_retries(lambda: self._client.instruments.currencies())
        return list(resp.instruments)

    def get_all_instruments(self, instrument_type: Optional[str] = None) -> list[Any]:
        """Получить все инструменты (опционально по типу).
        
        Args:
            instrument_type: тип инструмента (share/bond/etf/future/currency).
                           Если None, возвращает все типы.
        """
        if instrument_type == "share":
            return self.get_all_shares()
        elif instrument_type == "bond":
            return self.get_all_bonds()
        elif instrument_type == "etf":
            return self.get_all_etfs()
        elif instrument_type == "future":
            return self.get_all_futures()
        elif instrument_type == "currency":
            return self.get_all_currencies()
        else:
            # Возвращаем все типы
            all_instruments = []
            all_instruments.extend(self.get_all_shares())
            all_instruments.extend(self.get_all_bonds())
            all_instruments.extend(self.get_all_etfs())
            all_instruments.extend(self.get_all_futures())
            all_instruments.extend(self.get_all_currencies())
            return all_instruments

    def instrument_by_figi(self, figi: str) -> Any:
        try:
            resp = with_retries(
                lambda: self._client.instruments.get_instrument_by(
                    id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=figi
                )
            )
            return resp.instrument
        except Exception as exc:
            raise TickerNotFoundError(f"инструмент по FIGI не найден: {figi}") from exc

    def instrument_by_ticker(self, ticker: str, class_code: str = "") -> Any:
        # ВАЖНО: GetInstrumentBy отклоняет id_type=ticker без class_code
        # (INVALID_ARGUMENT 30013: "class_code require for id_type = ticker"),
        # поэтому без явного class_code сразу идём через find_instrument.
        if class_code:
            try:
                resp = with_retries(
                    lambda: self._client.instruments.get_instrument_by(
                        id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_TICKER,
                        id=ticker,
                        class_code=class_code,
                    )
                )
                return resp.instrument
            except Exception:
                pass
        # Fallback: ищем через find_instrument и фильтруем по точному совпадению тикера
        instruments = self.find_instrument(ticker)
        exact = [i for i in instruments if getattr(i, "ticker", "") == ticker]
        if not exact:
            raise TickerNotFoundError(f"инструмент по тикеру не найден: {ticker}") from None
        # Один тикер встречается в нескольких классах (TQBR, SMAL, SPEQ, 37M...):
        # приоритет — основной режим торгов TQBR, иначе можно получить первый
        # попавшийся класс без рыночных данных (последняя цена 0).
        for inst in exact:
            if getattr(inst, "class_code", "") == "TQBR":
                return inst
        return exact[0]

    def instrument_by_uid(self, uid: str) -> Any:
        """Поиск инструмента по внутреннему ID (uid) Т-Банка."""
        try:
            resp = with_retries(
                lambda: self._client.instruments.get_instrument_by(
                    id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_UID, id=uid
                )
            )
            return resp.instrument
        except Exception as exc:
            raise TickerNotFoundError(f"инструмент по uid не найден: {uid}") from exc

    def instrument_by_isin(self, isin: str) -> Any:
        """Поиск инструмента по ISIN (через find_instrument и фильтрацию)."""
        isin_upper = isin.strip().upper()
        instruments = self.find_instrument(isin_upper)
        for inst in instruments:
            if getattr(inst, "isin", "") == isin_upper:
                return inst
        # Fallback: пробуем найти по части ISIN (первые 9 символов)
        if len(isin_upper) >= 9:
            partial = isin_upper[:9]
            instruments = self.find_instrument(partial)
            for inst in instruments:
                if getattr(inst, "isin", "") == isin_upper:
                    return inst
        raise TickerNotFoundError(f"инструмент по ISIN не найден: {isin}") from None

    def find_instrument_smart(self, identifier: str) -> Any:
        """Универсальный поиск инструмента с автоопределением типа идентификатора.
        
        Поддерживает:
        - FIGI (формат BBG*)
        - Sandbox FIGI (формат TCS*, 12 символов — псевдо-FIGI песочницы)
        - UID (внутренние ID Т-Банка, длинные ID 20+ символов)
        - ISIN (12 символов: 2 буквы страны + 9 букв/цифр + 1 контрольная цифра)
        - Тикеры (всё остальное)
        
        Использует кэш для ускорения повторных запросов.
        """
        identifier = identifier.strip().upper()
        
        # Сначала проверяем кэш
        cached_type = get_cached_type(identifier)
        if cached_type:
            id_type = cached_type
        else:
            # Определяем тип по формату
            id_type = detect_identifier_type(identifier)
        
        # Выполняем поиск по определённому типу
        try:
            if id_type == "figi":
                result = self.instrument_by_figi(identifier)
            elif id_type == "sandbox_figi":
                result = self.instrument_by_figi(identifier)
            elif id_type == "isin":
                result = self.instrument_by_isin(identifier)
            elif id_type == "uid":
                result = self.instrument_by_uid(identifier)
            else:  # ticker
                result = self.instrument_by_ticker(identifier)
            
            # Сохраняем в кэш при успешном поиске
            cache_identifier_type(identifier, id_type)
            return result
        except TickerNotFoundError:
            # Если поиск не удал, пробуем другие методы
            raise

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
        """Получить FIGI по любому идентификатору (тикер, uid, figi)."""
        if not ticker:
            return ""
        if ticker in self._fights:
            return self._fights[ticker]
        # Используем универсальный поиск с автоопределением типа
        instrument = self.find_instrument_smart(ticker)
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

    def orderbook(self, figi: str, depth: int = 10) -> Any:
        """Получить стакан заявок."""
        resp = with_retries(
            lambda: self._client.market_data.get_order_book(figi=figi, depth=depth)
        )
        return resp

    def trading_status(self, figi: str) -> Any:
        """Получить статус торгов инструмента."""
        resp = with_retries(
            lambda: self._client.market_data.get_trading_status(figi=figi)
        )
        return resp

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
        from .render import to_jsonable
        quantity = money_to_float(position.quantity)
        current = money_to_float(position.current_price)
        return {
            "ticker": getattr(position, "ticker", "") or position.figi,
            "type": _enum_name(position.instrument_type),
            "quantity": to_jsonable(position.quantity),
            "avg": to_jsonable(position.average_position_price),
            "current": to_jsonable(position.current_price),
            "value": quantity * current,
            "pnl": money_to_float(position.expected_yield),
        }

    @staticmethod
    def order_row(order: Any, ticker: str) -> dict:
        from .render import to_jsonable
        price = getattr(order, "initial_order_price", None) or getattr(
            order, "executed_order_price", None
        )
        return {
            "ticker": ticker,
            "direction": _enum_name(order.direction),
            "status": _enum_name(order.execution_report_status),
            "lots": order.lots_executed,
            "price": to_jsonable(price),
            "order_id": order.order_id,
        }

    @staticmethod
    def operation_row(operation: Any, ticker: str) -> dict:
        from .render import to_jsonable
        op_type = getattr(operation, "operation_type", None) or getattr(operation, "type", None)
        return {
            "date": to_jsonable(getattr(operation, "date", None)),
            "type": _enum_name(op_type),
            "ticker": ticker,
            "quantity": to_jsonable(getattr(operation, "quantity", None)),
            "price": to_jsonable(getattr(operation, "price", None)),
            "amount": to_jsonable(getattr(operation, "payment", None)),
            "currency": getattr(operation, "currency", ""),
        }
