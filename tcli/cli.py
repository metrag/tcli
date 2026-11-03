"""typer-приложение tcli: команды для Tinkoff Invest API (SANDBOX и LIVE)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Optional

import typer

from .client import (
    Broker,
    SandboxError,
    api_error_text,
)
from .config import Contour, Settings, TokenMode, set_env_value
from .render import (
    console,
    fmt_money,
    header_line,
    print_accounts,
    print_candles,
    print_instruments,
    print_operations,
    print_orders,
    print_positions,
    print_summary,
)
from .ssl import ENV_VAR, cert_status

app = typer.Typer(
    no_args_is_help=True,
    help="tcli — CLI для Tinkoff Invest API. Поддержка SANDBOX и LIVE контуров.",
)


def _settings() -> Settings:
    return Settings.load()


def _open_broker(settings: Settings) -> Broker:
    return Broker(settings)


def _fail(message: str, code: int = 1) -> None:
    console.print(f"[red]Ошибка:[/red] {message}")
    raise typer.Exit(code)


def _guard(fn: Any) -> Any:
    """Обёртка команды: человекочитаемые ошибки вместо стека."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except typer.Exit:
            raise
        except SandboxError as exc:
            _fail(str(exc))
        except Exception as exc:  # noqa: BLE001 — верхний уровень CLI
            _fail(api_error_text(exc))

    return wraps(fn)(wrapper)


# -- Команды уровня приложения --------------------------------------------


@app.command()
@_guard
def check() -> None:
    """Самопроверка: .env, сертификат, доступ к API."""
    import os

    settings = _settings()
    problems = 0

    env_exists = settings.env_path.exists()
    env_ok = env_exists and settings.enabled
    if not env_ok:
        problems += 1
    token_line = settings.masked() if settings.enabled else "НЕ ЗАДАН"
    console.print(
        f"[1/4] .env ({settings.env_path}): "
        + (f"токен {token_line}" if env_ok else "не найден или токен не задан")
    )

    cert = cert_status()
    cert_ok = cert["exists"] and cert["size"] > 0
    if not cert_ok:
        problems += 1
    console.print(
        f"[2/4] сертификат: {cert['path']} "
        + (f"({cert['size']} байт)" if cert_ok else "— НЕ НАЙДЕН")
    )

    grpc_env = os.environ.get(ENV_VAR, "")
    if not grpc_env:
        problems += 1
    console.print(f"[3/4] {ENV_VAR}: {grpc_env or 'не задана'}")

    if settings.enabled:
        try:
            with _open_broker(settings) as br:
                accounts = br.accounts()
            names = ", ".join(a.name or a.id for a in accounts) or "нет счетов"
            console.print(
                f"[4/4] API ({settings.contour.value}): OK, счетов: {len(accounts)} ({names})"
            )
        except Exception as exc:  # noqa: BLE001
            problems += 1
            console.print(
                f"[4/4] API ({settings.contour.value}): [red]ПРОВАЛ[/red] — {api_error_text(exc)}"
            )
    else:
        console.print(f"[4/4] API ({settings.contour.value}): пропущен — нет токена")

    if problems:
        console.print(f"[red]check: ПРОВАЛ ({problems})[/red]")
        raise typer.Exit(1)
    console.print("[green]check: OK — всё готово[/green]")


@app.command()
@_guard
def change_mode(
    contour: Optional[str] = typer.Argument(None, help="Контур: sandbox или live"),
    token: Optional[str] = typer.Option(None, "--token", help="Режим токена: main или sandbox"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение для LIVE"),
) -> None:
    """Переключить контур и/или режим токена.

    Примеры:
        tcli change_mode sandbox
        tcli change_mode live --yes
        tcli change_mode token sandbox
    """
    settings = _settings()
    current_contour = settings.contour
    current_token_mode = settings.token_mode

    new_contour = current_contour
    new_token_mode = current_token_mode

    # Переключение контура
    if contour:
        contour_lower = contour.strip().lower()
        if contour_lower in ("sandbox", "sb"):
            new_contour = Contour.SANDBOX
        elif contour_lower in ("live", "prod", "production"):
            if not yes:
                console.print("[yellow]ВНИМАНИЕ:[/yellow] Переключение на LIVE контур")
                console.print("Все операции будут выполняться с реальными деньгами!")
                confirm = typer.prompt("Введите 'LIVE' для подтверждения")
                if confirm != "LIVE":
                    console.print("[red]Отменено[/red]")
                    raise typer.Exit(1)
            new_contour = Contour.LIVE
        else:
            _fail(f"неизвестный контур: {contour} (допустимо: sandbox, live)", code=2)

    # Переключение режима токена
    if token:
        token_lower = token.strip().lower()
        if token_lower in ("main", "primary"):
            new_token_mode = TokenMode.MAIN
        elif token_lower in ("sandbox", "sb"):
            new_token_mode = TokenMode.SANDBOX
        else:
            _fail(f"неизвестный режим токена: {token} (допустимо: main, sandbox)", code=2)

    # Запись изменений
    changed = False
    if new_contour != current_contour:
        set_env_value("TCLI_CONTOUR", new_contour.value)
        console.print(f"контур: {current_contour.value} → [green]{new_contour.value}[/green]")
        changed = True
    else:
        console.print(f"контур: {current_contour.value} (без изменений)")

    if new_token_mode != current_token_mode:
        set_env_value("TCLI_TOKEN", new_token_mode.value)
        console.print(
            f"режим токена: {current_token_mode.value} → [green]{new_token_mode.value}[/green]"
        )
        changed = True
    else:
        console.print(f"режим токена: {current_token_mode.value} (без изменений)")

    if not changed:
        console.print("[dim]ничего не изменилось[/dim]")


# -- Команды уровня счёта -------------------------------------------------


@app.command()
@_guard
def status() -> None:
    """Счета и сводка портфеля."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        accounts = br.accounts()
        if not accounts:
            _fail(
                f"нет счетов — создайте счёт в {'песочнице' if br.is_sandbox else 'боевом контуре'}"
            )
        print_accounts([Broker.account_row(a) for a in accounts], contour=br.contour)
        rows = []
        for account in accounts:
            portfolio = br.portfolio(account.id)
            rows.append(Broker.portfolio_row(account.name or account.id, portfolio))
        print_summary(rows, contour=br.contour)


@app.command()
@_guard
def positions() -> None:
    """Позиции портфеля."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        account = br.pick_account()
        portfolio = br.portfolio(account.id)
        if not portfolio.positions:
            console.print("позиций нет")
            raise typer.Exit(0)
        print_positions([Broker.position_row(p) for p in portfolio.positions])


@app.command()
@_guard
def orders() -> None:
    """Активные заявки."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        account = br.pick_account()
        active = br.orders(account.id)
        if not active:
            console.print("активных заявок нет")
            raise typer.Exit(0)
        rows = [Broker.order_row(o, br.ticker(o.figi)) for o in active]
        print_orders(rows, active=True)


@app.command()
@_guard
def payin(amount: float = typer.Argument(..., help="сумма пополнения в рублях")) -> None:
    """Пополнить счёт (только песочница)."""
    if amount <= 0:
        _fail("сумма должна быть больше 0", code=2)
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        account = br.pick_account()
        br.payin(account.id, amount)
        portfolio = br.portfolio(account.id)
        console.print(
            f"[green]пополнено на {fmt_money(amount)}[/green] · "
            f"счёт {account.name or account.id} · "
            f"денег теперь: {fmt_money(portfolio.total_amount_currencies)}"
        )


@app.command()
@_guard
def reset() -> None:
    """Сбросить песочницу."""
    _fail(
        "метод reset отсутствует в tinkoff-investments 0.2.0-beta117 — "
        "обновите SDK или закройте/откройте счёт в приложении Т-Банка",
        code=1,
    )


# -- Команды управления счетами -------------------------------------------


@app.command(name="account-list")
@_guard
def account_list() -> None:
    """Список всех счетов."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        accounts = br.accounts()
        if not accounts:
            console.print("счетов нет")
            raise typer.Exit(0)
        print_accounts([Broker.account_row(a) for a in accounts], contour=br.contour)


@app.command(name="account-new")
@_guard
def account_new(
    name: str = typer.Argument("", help="Имя нового счёта (опционально)"),
) -> None:
    """Создать новый счёт (только песочница)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        resp = br.create_account(name=name)
        console.print(f"[green]счёт создан[/green]: {resp.account_id}")


@app.command(name="account-rm")
@_guard
def account_rm(
    account: str = typer.Argument(..., help="Имя или ID счёта для удаления"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
) -> None:
    """Удалить счёт (только песочница)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        # Найти счёт по имени или ID
        accounts = br.accounts()
        matched = [a for a in accounts if a.name == account or a.id == account]
        if not matched:
            _fail(f"счёт не найден: {account}", code=2)
        if len(matched) > 1:
            _fail(f"найдено несколько счетов: {account}", code=2)
        
        target = matched[0]
        
        if not yes:
            console.print(f"[yellow]ВНИМАНИЕ:[/yellow] Удаление счёта {target.name or target.id}")
            console.print("Все позиции и заявки будут закрыты!")
            confirm = typer.prompt(f"Введите имя счёта для подтверждения: {target.name or target.id}")
            if confirm != (target.name or target.id):
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        br.close_account(target.id)
        console.print(f"[green]счёт удалён[/green]: {target.name or target.id}")


@app.command(name="account-show")
@_guard
def account_show(
    account: str = typer.Argument(..., help="Имя или ID счёта"),
) -> None:
    """Показать детали счёта."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        # Найти счёт по имени или ID
        accounts = br.accounts()
        matched = [a for a in accounts if a.name == account or a.id == account]
        if not matched:
            _fail(f"счёт не найден: {account}", code=2)
        if len(matched) > 1:
            _fail(f"найдено несколько счетов: {account}", code=2)
        
        target = matched[0]
        
        # Детали счёта
        console.print(f"\n[bold]Счёт:[/bold] {target.name or target.id}")
        console.print(f"  ID: {target.id}")
        console.print(f"  Тип: {Broker.account_row(target)['type']}")
        console.print(f"  Статус: {Broker.account_row(target)['status']}")
        
        # Портфель
        portfolio = br.portfolio(target.id)
        row = Broker.portfolio_row(target.name or target.id, portfolio)
        console.print("\n[bold]Портфель:[/bold]")
        console.print(f"  Деньги: {fmt_money(row['cash'])}")
        console.print(f"  Бумаги: {fmt_money(row['securities'])}")
        console.print(f"  Итого: {fmt_money(row['total'])}")
        console.print(f"  P&L: {fmt_money(row['pnl'])}")
        
        # Позиции
        if portfolio.positions:
            console.print(f"\n[bold]Позиции ({len(portfolio.positions)}):[/bold]")
            print_positions([Broker.position_row(p) for p in portfolio.positions])
        else:
            console.print("\n[dim]позиций нет[/dim]")


# -- Команды заявок -------------------------------------------------------


@app.command(name="order-buy")
@_guard
def order_buy(
    ticker: str = typer.Argument(..., help="Тикер инструмента"),
    lots: int = typer.Argument(..., help="Количество лотов"),
    price: Optional[float] = typer.Option(None, "--price", help="Лимитная цена (иначе рыночная)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
) -> None:
    """Купить инструмент."""
    if lots <= 0:
        _fail("количество лотов должно быть больше 0", code=2)
    
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        from tinkoff.invest.schemas import OrderDirection, OrderType, Quotation
        
        account = br.pick_account()
        figi = br.figi(ticker)
        
        # Подтверждение
        order_type = OrderType.ORDER_TYPE_LIMIT if price is not None else OrderType.ORDER_TYPE_MARKET
        price_str = fmt_money(price) if price is not None else "рыночная"
        
        if not yes:
            console.print(f"\n[bold]Покупка:[/bold] {ticker} × {lots} лот(ов)")
            console.print(f"  Счёт: {account.name or account.id}")
            console.print(f"  Цена: {price_str}")
            console.print(f"  Контур: [yellow]{br.contour.value}[/yellow]")
            confirm = typer.confirm("Подтвердить заявку?")
            if not confirm:
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        price_quotation = None
        if price is not None:
            units = int(price)
            nano = int(round((price - units) * 1e9))
            price_quotation = Quotation(units=units, nano=nano)
        
        from tinkoff.invest.schemas import OrderType
        
        resp = br.place_order(
            account_id=account.id,
            figi=figi,
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            quantity=lots,
            price=price_quotation,
            order_type=order_type,
        )
        
        console.print("[green]заявка выставлена[/green]")
        console.print(f"  order_id: {resp.order_id}")
        console.print(f"  figi: {figi}")


@app.command(name="order-sell")
@_guard
def order_sell(
    ticker: str = typer.Argument(..., help="Тикер инструмента"),
    lots: int = typer.Argument(..., help="Количество лотов"),
    price: Optional[float] = typer.Option(None, "--price", help="Лимитная цена (иначе рыночная)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
) -> None:
    """Продать инструмент."""
    if lots <= 0:
        _fail("количество лотов должно быть больше 0", code=2)
    
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        from tinkoff.invest.schemas import OrderDirection, OrderType, Quotation
        
        account = br.pick_account()
        figi = br.figi(ticker)
        
        # Подтверждение
        order_type = OrderType.ORDER_TYPE_LIMIT if price is not None else OrderType.ORDER_TYPE_MARKET
        price_str = fmt_money(price) if price is not None else "рыночная"
        
        if not yes:
            console.print(f"\n[bold]Продажа:[/bold] {ticker} × {lots} лот(ов)")
            console.print(f"  Счёт: {account.name or account.id}")
            console.print(f"  Цена: {price_str}")
            console.print(f"  Контур: [yellow]{br.contour.value}[/yellow]")
            confirm = typer.confirm("Подтвердить заявку?")
            if not confirm:
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        price_quotation = None
        if price is not None:
            units = int(price)
            nano = int(round((price - units) * 1e9))
            price_quotation = Quotation(units=units, nano=nano)
        
        resp = br.place_order(
            account_id=account.id,
            figi=figi,
            direction=OrderDirection.ORDER_DIRECTION_SELL,
            quantity=lots,
            price=price_quotation,
            order_type=order_type,
        )
        
        console.print("[green]заявка выставлена[/green]")
        console.print(f"  order_id: {resp.order_id}")
        console.print(f"  figi: {figi}")


@app.command(name="order-cancel")
@_guard
def order_cancel(
    order_id: str = typer.Argument(..., help="ID заявки"),
) -> None:
    """Отменить заявку."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        account = br.pick_account()
        br.cancel_order(account.id, order_id)
        console.print(f"[green]заявка отменена[/green]: {order_id}")


# -- Команды истории и рынка ----------------------------------------------


@app.command()
@_guard
def ops(
    from_date: Optional[str] = typer.Option(None, "--from", help="Дата начала (YYYY-MM-DD)"),
    to_date: Optional[str] = typer.Option(None, "--to", help="Дата окончания (YYYY-MM-DD)"),
    ticker: Optional[str] = typer.Option(None, "--ticker", help="Фильтр по тикеру"),
) -> None:
    """История операций."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    # Парсинг дат
    from_dt = None
    to_dt = None
    if from_date:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if to_date:
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        
        figi = ""
        if ticker:
            figi = br.figi(ticker)
        
        operations = br.operations(
            account_id=account.id,
            from_=from_dt,
            to=to_dt,
            figi=figi,
        )
        
        if not operations:
            console.print("операций нет")
            raise typer.Exit(0)
        
        rows = []
        for op in operations:
            op_ticker = ""
            if op.figi:
                op_ticker = br.ticker(op.figi)
            rows.append(Broker.operation_row(op, op_ticker))
        
        print_operations(rows)


@app.command()
@_guard
def quote(
    ticker: str = typer.Argument(..., help="Тикер инструмента"),
) -> None:
    """Последние цены инструмента."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        figi = br.figi(ticker)
        prices = br.last_prices([figi])
        
        if not prices:
            _fail(f"цены не найдены для {ticker}", code=1)
        
        last = prices[0]
        console.print(f"\n[bold]{ticker}[/bold] (FIGI: {figi})")
        console.print(f"  Последняя цена: {fmt_money(last.price)}")
        console.print(f"  Время: {last.time}")


@app.command()
@_guard
def candles(
    ticker: str = typer.Argument(..., help="Тикер инструмента"),
    interval: str = typer.Option(
        "1day",
        "--interval",
        "-i",
        help="Интервал: 1min, 5min, 15min, 1hour, 1day",
    ),
    days: int = typer.Option(30, "--days", "-d", help="Количество дней истории"),
) -> None:
    """История свечей инструмента."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    from tinkoff.invest.schemas import CandleInterval
    
    interval_map = {
        "1min": CandleInterval.CANDLE_INTERVAL_1_MIN,
        "5min": CandleInterval.CANDLE_INTERVAL_5_MIN,
        "15min": CandleInterval.CANDLE_INTERVAL_15_MIN,
        "1hour": CandleInterval.CANDLE_INTERVAL_HOUR,
        "1day": CandleInterval.CANDLE_INTERVAL_DAY,
    }
    
    if interval not in interval_map:
        _fail(f"неизвестный интервал: {interval} (допустимо: {', '.join(interval_map.keys())})", code=2)
    
    with _open_broker(settings) as br:
        figi = br.figi(ticker)
        
        now = datetime.now(timezone.utc)
        from_dt = now - timedelta(days=days)
        
        candle_list = br.candles(
            figi=figi,
            interval=interval_map[interval],
            from_=from_dt,
            to=now,
        )
        
        if not candle_list:
            console.print("свечей нет")
            raise typer.Exit(0)
        
        rows = []
        for c in candle_list:
            rows.append({
                "time": c.time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            })
        
        print_candles(rows, ticker=ticker, interval=interval)


@app.command()
@_guard
def find(
    query: str = typer.Argument(..., help="Поисковый запрос (тикер, название, ISIN)"),
) -> None:
    """Поиск инструментов."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        instruments = br.find_instrument(query)
        
        if not instruments:
            console.print("инструменты не найдены")
            raise typer.Exit(0)
        
        rows = []
        for inst in instruments:
            rows.append({
                "ticker": getattr(inst, "ticker", ""),
                "figi": inst.figi,
                "name": getattr(inst, "name", ""),
                "type": getattr(inst, "instrument_type", ""),
                "class": getattr(inst, "class_code", ""),
            })
        
        print_instruments(rows, query=query)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
