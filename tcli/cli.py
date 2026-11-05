"""typer-приложение tcli: команды для Tinkoff Invest API (SANDBOX и LIVE)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Optional

import typer

from .client import (
    Broker,
    SandboxError,
    api_error_text,
)
from .config import Contour, Settings, mask_token, set_env_value
from .id_utils import (
    CACHE_PATH,
    clear_cache,
    detect_identifier_type,
    get_cached_type,
    load_cache,
)
from .render import (
    console,
    fmt_money,
    header_line,
    log_event,
    money_to_float,
    print_accounts,
    print_candles,
    print_instrument_info,
    print_instruments,
    print_instruments_filtered,
    print_json,
    print_operations,
    print_orderbook,
    print_orders,
    print_positions,
    print_stop_orders,
    print_summary,
    print_trading_status,
    print_watchlist,
)
from .ssl import ENV_VAR, cert_status
from .watchlist_utils import (
    add_to_watchlist,
    load_watchlist,
    remove_from_watchlist,
)

app = typer.Typer(
    no_args_is_help=True,
    help="tcli — CLI для Tinkoff Invest API. Поддержка SANDBOX и LIVE контуров.",
)

# Глобальные переменные для общих флагов
_global_account: Optional[str] = None
_env_override: Optional[Path] = None
_read_only: bool = False


@app.callback()
def main_callback(
    account: Optional[str] = typer.Option(
        None,
        "--account",
        help="Выбор счёта для этой команды (имя или ID)",
    ),
    env: Optional[Path] = typer.Option(
        None,
        "--env",
        help="Путь к .env файлу (или TCLI_ENV_PATH)",
    ),
    read_only: bool = typer.Option(
        False,
        "--read-only",
        help="Режим только чтения (запрет на изменение контура и счёта)",
    ),
) -> None:
    """Глобальный callback для обработки общих флагов."""
    import os
    global _global_account, _env_override, _read_only
    _global_account = account
    # --env имеет приоритет над TCLI_ENV_PATH
    if env:
        _env_override = env
    elif "TCLI_ENV_PATH" in os.environ:
        _env_override = Path(os.environ["TCLI_ENV_PATH"])
    else:
        _env_override = None
    # --read-only или TCLI_READ_ONLY=1
    _read_only = read_only or os.environ.get("TCLI_READ_ONLY") == "1"

def _settings() -> Settings:
    settings = Settings.load(env_path=_env_override)
    # Применяем глобальный флаг --account (#27)
    if _global_account:
        settings.account_override = _global_account
    return settings


def _open_broker(settings: Settings) -> Broker:
    return Broker(settings)


def _fail(message: str, code: int = 1) -> None:
    """Вывод ошибки. При --json — машиночитаемый JSON (#4 из TODO.md)."""
    import json
    import sys

    if "--json" in sys.argv:
        print(json.dumps({"error": message, "code": code}, ensure_ascii=False))
    else:
        console.print(f"[red]Ошибка:[/red] {message}")
    raise typer.Exit(code)


def _validate_range(from_dt: Any, to_dt: Any) -> None:
    """Проверить корректность диапазона дат (#3 из TODO.md)."""
    if from_dt is not None and to_dt is not None and from_dt >= to_dt:
        _fail(
            f"неверный диапазон: --from ({from_dt.date()}) должен быть раньше --to ({to_dt.date()})",
            code=2,
        )


def _guard(fn: Any) -> Any:
    """Обёртка команды: человекочитаемые ошибки вместо стека."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except typer.Exit:
            raise
        except SandboxError as exc:
            # Используем exit_code из исключения, если он есть
            code = getattr(exc, 'exit_code', 1)
            _fail(str(exc), code=code)
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
def trades(
    ticker: str = typer.Argument(..., help="Тикер инструмента"),
    from_date: Optional[str] = typer.Option(
        None, "--from", help="Начальная дата (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)"
    ),
    to_date: Optional[str] = typer.Option(
        None, "--to", help="Конечная дата (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")
) -> None:
    """История сделок биржи за период (#12 из TODO.md)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    # Парсинг дат
    now = datetime.now(timezone.utc)
    if to_date:
        try:
            if "T" in to_date:
                to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            else:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _fail(f"неверный формат --to: {to_date} (используйте YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)", code=2)
    else:
        to_dt = now
    
    if from_date:
        try:
            if "T" in from_date:
                from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            else:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _fail(
                f"неверный формат --from: {from_date} "
                "(используйте YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)",
                code=2,
            )
    else:
        # По умолчанию - последние 24 часа
        from_dt = to_dt - timedelta(days=1)

    _validate_range(from_dt, to_dt)

    with _open_broker(settings) as br:
        figi = br.figi(ticker)
        
        # Получаем сделки с API
        trades_list = br.get_trades(
            figi=figi,
            from_=from_dt,
            to=to_dt,
        )
        
        if not trades_list:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
                console.print("сделок нет")
            raise typer.Exit(0)
        
        # Форматируем результаты
        rows = []
        for trade in trades_list:
            rows.append({
                "time": str(trade.time),
                "price": str(trade.price),
                "quantity": trade.quantity,
                "direction": (
                    "BUY" if trade.direction == 1 
                    else "SELL" if trade.direction == 2 
                    else str(trade.direction)
                ),
            })
        
        if json_output:
            result = {
                "ticker": ticker,
                "from": from_dt.isoformat(),
                "to": to_dt.isoformat(),
                "trades": rows
            }
            print_json(data=result, contour=settings.contour.value, account="")
        else:
            console.print(f"\n[bold]Сделки {ticker}[/bold] ({len(rows)} шт.)")
            from_str = from_dt.strftime('%Y-%m-%d %H:%M')
            to_str = to_dt.strftime('%Y-%m-%d %H:%M')
            console.print(f"Период: {from_str} — {to_str}")
            
            from rich.table import Table
            table = Table()
            table.add_column("Время", style="cyan")
            table.add_column("Цена", justify="right", style="green")
            table.add_column("Количество", justify="right")
            table.add_column("Направление", style="magenta")
            
            for row in rows:
                table.add_row(
                    row["time"][:19],
                    row["price"],
                    str(row["quantity"]),
                    row["direction"],
                )
            
            console.print(table)



@app.command()
@_guard
def fees(
    from_date: Optional[str] = typer.Option(
        None, "--from", help="Начальная дата (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)"
    ),
    to_date: Optional[str] = typer.Option(
        None, "--to", help="Конечная дата (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")
) -> None:
    """Итог комиссий за период (#38 из TODO.md)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    # Парсинг дат
    now = datetime.now(timezone.utc)
    if to_date:
        try:
            if "T" in to_date:
                to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            else:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _fail(f"неверный формат --to: {to_date}", code=2)
    else:
        to_dt = now
    
    if from_date:
        try:
            if "T" in from_date:
                from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            else:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _fail(f"неверный формат --from: {from_date}", code=2)
    else:
        # По умолчанию - последние 30 дней
        from_dt = to_dt - timedelta(days=30)

    _validate_range(from_dt, to_dt)

    with _open_broker(settings) as br:
        account = br.pick_account()
        
        # Получаем комиссии
        fees_info = br.get_fees(
            account_id=account.id,
            from_=from_dt,
            to=to_dt,
        )
        
        if json_output:
            result = {
                "from": from_dt.isoformat(),
                "to": to_dt.isoformat(),
                "total_fees": fees_info["total_fees"],
                "fees_by_currency": fees_info["fees_by_currency"],
                "operations_count": fees_info["operations_count"],
            }
            print_json(data=result, contour=settings.contour.value, account=account.id)
        else:
            console.print("\n[bold]Комиссии за период[/bold]")
            from_str = from_dt.strftime('%Y-%m-%d %H:%M')
            to_str = to_dt.strftime('%Y-%m-%d %H:%M')
            console.print(f"Период: {from_str} — {to_str}")
            console.print(f"Операций с комиссиями: {fees_info['operations_count']}")
            
            console.print("\n[bold]Итого по валютам:[/bold]")
            for currency, amount in fees_info['fees_by_currency'].items():
                console.print(f"  {currency}: {amount:.2f}")
            
            console.print(f"\n[bold]Общая сумма: {fees_info['total_fees']:.2f}[/bold]")



@app.command()
@_guard
def export(
    export_type: str = typer.Argument(
        "trades", help="Тип экспорта: trades (сделки) или pnl (все операции)"
    ),
    from_date: Optional[str] = typer.Option(
        None, "--from", help="Начальная дата (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)"
    ),
    to_date: Optional[str] = typer.Option(
        None, "--to", help="Конечная дата (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)"
    ),
    output: str = typer.Option(
        "export.csv", "--output", "-o", help="Файл для экспорта (CSV или JSON)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")
) -> None:
    """Экспорт дневника сделок в CSV/JSON (#37 из TODO.md)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    # Валидация типа экспорта
    if export_type not in ("trades", "pnl"):
        _fail(f"неверный тип экспорта: {export_type} (используйте trades или pnl)", code=2)
    
    # Валидация формата файла
    if not (output.endswith('.json') or output.endswith('.csv')):
        _fail(f"неподдерживаемый формат файла: {output} (используйте .json или .csv)", code=2)
    
    # Парсинг дат
    now = datetime.now(timezone.utc)
    if to_date:
        try:
            if "T" in to_date:
                to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            else:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _fail(f"неверный формат --to: {to_date}", code=2)
    else:
        to_dt = now
    
    if from_date:
        try:
            if "T" in from_date:
                from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            else:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _fail(f"неверный формат --from: {from_date}", code=2)
    else:
        # По умолчанию - последние 30 дней
        from_dt = to_dt - timedelta(days=30)

    _validate_range(from_dt, to_dt)

    with _open_broker(settings) as br:
        account = br.pick_account()
        
        # Получаем операции
        rows = br.export_operations(
            account_id=account.id,
            from_=from_dt,
            to=to_dt,
            export_type=export_type,
        )
        
        if not rows:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account=account.id)
            else:
                console.print("операций нет")
            raise typer.Exit(0)
        
        # Экспорт в файл
        if output.endswith('.json'):
            import json
            with open(output, 'w', encoding='utf-8') as f:
                json.dump({
                    "type": export_type,
                    "from": from_dt.isoformat(),
                    "to": to_dt.isoformat(),
                    "operations": rows
                }, f, ensure_ascii=False, indent=2)
        elif output.endswith('.csv'):
            import csv
            fieldnames = ['date', 'figi', 'operation_type', 'quantity', 'price', 'amount', 'currency']
            with open(output, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        else:
            _fail(f"неподдерживаемый формат файла: {output} (используйте .json или .csv)", code=2)
        
        if json_output:
            result = {
                "type": export_type,
                "from": from_dt.isoformat(),
                "to": to_dt.isoformat(),
                "count": len(rows),
                "file": output
            }
            print_json(data=result, contour=settings.contour.value, account=account.id)
        else:
            console.print(f"[green]Экспортировано {len(rows)} операций в {output}[/green]")



@app.command()
@_guard
def halt(
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")
) -> None:
    """Аварийный выключатель: отмена всех заявок + закрытие позиций (#34)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    console.print("[bold red]⚠ АВАРИЙНЫЙ ВЫКЛЮЧАТЕЛЬ[/bold red]")
    console.print("Отмена всех заявок и закрытие всех позиций...")
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        
        # Выполняем аварийную остановку
        result = br.emergency_halt(account_id=account.id)
        
        if json_output:
            print_json(data=result, contour=settings.contour.value, account=account.id)
        else:
            console.print("\n[bold]Результат:[/bold]")
            console.print(f"  Отменено заявок: {result['cancelled_orders']}")
            console.print(f"  Отменено стоп-заявок: {result['cancelled_stop_orders']}")
            console.print(f"  Закрыто позиций: {result['closed_positions']}")
            
            if result['errors']:
                console.print("\n[red]Ошибки:[/red]")
                for error in result['errors']:
                    console.print(f"  • {error}")
            else:
                console.print("\n[green]✓ Аварийная остановка завершена успешно[/green]")


@app.command()
@_guard
def clock(
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Синхронизация времени: серверное время и дрейф локальных часов (#7)."""
    settings = _settings()

    with _open_broker(settings) as br:
        clock_info = br.get_clock()

        if clock_info.get("error"):
            _fail(clock_info["error"])

        if json_output:
            result = {
                "local_before": clock_info["local_before"],
                "local_after": clock_info["local_after"],
                "server_time_estimate": clock_info["server_time_estimate"],
                "round_trip_time_ms": clock_info["round_trip_time_ms"],
                "drift_seconds": clock_info["drift_seconds"],
                "drift_milliseconds": clock_info["drift_milliseconds"],
            }
            print_json(result, contour=settings.contour.value, account="")
        else:
            local_before = clock_info["local_before"]
            local_after = clock_info["local_after"]
            server_estimate = clock_info["server_time_estimate"]
            rtt_ms = clock_info["round_trip_time_ms"]
            
            console.print(f"Локальное время (до запроса): {local_before}")
            console.print(f"Локальное время (после запроса): {local_after}")
            console.print(f"Оценка серверного времени: {server_estimate}")
            console.print(f"Round-trip time: {rtt_ms:.2f} мс")
            
            drift = clock_info["drift_milliseconds"]
            if drift is not None:
                if abs(drift) < 100:
                    console.print(f"[green]Дрейф: {drift} мс[/green]")
                elif abs(drift) < 500:
                    console.print(f"[yellow]Дрейф: {drift} мс[/yellow]")
                else:
                    console.print(f"[red]Дрейф: {drift} мс (рекомендуется синхронизация)[/red]")
            else:
                console.print("[dim]Дрейф: недоступно[/dim]")


@app.command()
@_guard
def stream_quote(
    tickers: list[str] = typer.Argument(..., help="Тикеры инструментов"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате"),
) -> None:
    """Живой поток последних цен по тикерам (#8)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        # Получаем FIGI для всех тикеров
        figis = []
        for ticker in tickers:
            try:
                figi = br.figi(ticker)
                figis.append(figi)
            except Exception as e:
                console.print(f"[red]Ошибка для {ticker}: {e}[/red]")
        
        if not figis:
            _fail("Не удалось получить FIGI ни для одного тикера")
        
        if not json_output:
            console.print(f"[green]Запуск стрима last prices для {len(figis)} инструментов[/green]")
            console.print("[dim]Нажмите Ctrl+C для остановки[/dim]\n")
        
        # Запускаем стрим
        stream = br.stream_quotes(figis)
        
        try:
            for response in stream:
                # Фильтруем только данные last_price (не подписки)
                if response.last_price:
                    lp = response.last_price
                    if json_output:
                        print_json({
                            "figi": lp.figi,
                            "price": str(lp.price),
                            "time": str(lp.time),
                        }, contour=settings.contour.value, account="")
                    else:
                        console.print(f"[cyan]{lp.figi}[/cyan] | [green]{lp.price}[/green] | {lp.time}")
        except KeyboardInterrupt:
            if not json_output:
                console.print("\n[yellow]Стрим остановлен[/yellow]")


@app.command()
@_guard
def stream_trades(
    tickers: list[str] = typer.Argument(..., help="Тикеры инструментов"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате"),
) -> None:
    """Поток сделок: цена, объём, агрессор (#9)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        # Получаем FIGI для всех тикеров
        figis = []
        for ticker in tickers:
            try:
                figi = br.figi(ticker)
                figis.append(figi)
            except Exception as e:
                console.print(f"[red]Ошибка для {ticker}: {e}[/red]")
        
        if not figis:
            _fail("Не удалось получить FIGI ни для одного тикера")
        
        if not json_output:
            console.print(f"[green]Запуск стрима trades для {len(figis)} инструментов[/green]")
            console.print("[dim]Нажмите Ctrl+C для остановки[/dim]\n")
        
        # Запускаем стрим
        stream = br.stream_trades(figis)
        
        try:
            for response in stream:
                # Фильтруем только данные trade (не подписки)
                if response.trade:
                    trade = response.trade
                    direction = "BUY" if trade.direction == 1 else "SELL" if trade.direction == 2 else "?"
                    
                    if json_output:
                        print_json({
                            "figi": trade.figi,
                            "price": str(trade.price),
                            "quantity": trade.quantity,
                            "direction": direction,
                            "time": str(trade.time),
                        }, contour=settings.contour.value, account="")
                    else:
                        color = "green" if direction == "BUY" else "red"
                        console.print(
                            f"[cyan]{trade.figi}[/cyan] | "
                            f"[{color}]{direction}[/{color}] | "
                            f"[yellow]{trade.price}[/yellow] x {trade.quantity} | "
                            f"{trade.time}"
                        )
        except KeyboardInterrupt:
            if not json_output:
                console.print("\n[yellow]Стрим остановлен[/yellow]")


@app.command()
@_guard
def stream_orders(
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")
) -> None:
    """Подписка на статусы заявок (#26 из TODO.md).
    
    Живой поток обновлений статусов ордеров: филл, частичное исполнение, отмена.
    """
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        
        if json_output:
            print_json(data={"status": "streaming", "account": account.id}, 
                      contour=settings.contour.value, account=account.id)
        else:
            console.print(f"\n[bold]Стрим ордеров для счёта {account.id}[/bold]")
            console.print("[dim]Ctrl+C для остановки[/dim]\n")
        
        try:
            for update in br.stream_orders(account.id):
                if json_output:
                    print_json(data={
                        "order_id": update.order_id,
                        "status": str(update.execution_report_status),
                        "filled": update.lots_executed,
                        "timestamp": str(update.order_request_date),
                    }, contour=settings.contour.value, account=account.id)
                else:
                    status = update.execution_report_status.name
                    console.print(f"[cyan]{update.order_id}[/cyan] [yellow]{status}[/yellow] "
                                f"заполнено: {update.lots_executed}")
        except KeyboardInterrupt:
            if not json_output:
                console.print("\n[yellow]Стрим остановлен[/yellow]")
            raise typer.Exit(0) from None


@app.command()
@_guard
def flatten(
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")
) -> None:
    """Закрыть все позиции и ждать исполнения (#35 из TODO.md).
    
    Отправляет рыночные заявки на закрытие всех открытых позиций
    и ждёт их исполнения.
    """
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        
        if not json_output:
            console.print(f"\n[bold]Закрытие всех позиций для счёта {account.id}[/bold]")
        
        result = br.flatten_all_and_wait(account.id)
        
        if json_output:
            print_json(data=result, contour=settings.contour.value, account=account.id)
        else:
            console.print(f"\n[green]✓ Закрыто позиций: {result['closed_positions']}[/green]")
            if result['errors']:
                console.print(f"[red]Ошибки: {len(result['errors'])}[/red]")
                for err in result['errors']:
                    console.print(f"  • {err}")


@app.command()
@_guard
def stream_orderbook(
    ticker: str = typer.Argument(..., help="Тикер инструмента"),
    depth: int = typer.Option(10, "--depth", "-d", help="Глубина стакана"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате"),
) -> None:
    """Поток изменений стакана (#10)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        try:
            figi = br.figi(ticker)
        except Exception as e:
            _fail(f"Не удалось получить FIGI для {ticker}: {e}")
        
        if not json_output:
            console.print(f"[green]Запуск стрима orderbook для {ticker} (depth={depth})[/green]")
            console.print("[dim]Нажмите Ctrl+C для остановки[/dim]\n")
        
        # Запускаем стрим
        stream = br.stream_orderbook(figi, depth)
        
        try:
            for response in stream:
                # Фильтруем только данные orderbook (не подписки)
                if response.orderbook:
                    ob = response.orderbook
                    
                    if json_output:
                        print_json({
                            "figi": ob.figi,
                            "depth": ob.depth,
                            "is_consistent": ob.is_consistent,
                            "bids": [[str(p.price), p.quantity] for p in ob.bids],
                            "asks": [[str(p.price), p.quantity] for p in ob.asks],
                            "time": str(ob.time),
                        }, contour=settings.contour.value, account="")
                    else:
                        console.print(f"\n[cyan]{ob.figi}[/cyan] | depth={ob.depth} | {ob.time}")
                        console.print("[red]Asks (продажи):[/red]")
                        for ask in reversed(ob.asks[:5]):  # Показываем топ-5
                            console.print(f"  {ask.price} x {ask.quantity}")
                        console.print("[green]Bids (покупки):[/green]")
                        for bid in ob.bids[:5]:  # Показываем топ-5
                            console.print(f"  {bid.price} x {bid.quantity}")
        except KeyboardInterrupt:
            if not json_output:
                console.print("\n[yellow]Стрим остановлен[/yellow]")


@app.command()
@_guard
def change_mode(
    contour: str = typer.Argument(..., help="Контур: sandbox или live"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение для LIVE"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Неинтерактивный режим (без подтверждений)"),
) -> None:
    """Переключить контур (SANDBOX/LIVE).

    Примеры:
        tcli change-mode sandbox
        tcli change-mode live --yes
        tcli change-mode live --no-prompt
    """
    # Проверка режима только чтения (#5)
    if _read_only:
        _fail("режим только чтения: изменение контура запрещено (TCLI_READ_ONLY=1 или --read-only)", code=1)
    
    settings = _settings()
    current_contour = settings.contour

    contour_lower = contour.strip().lower()
    if contour_lower in ("sandbox", "sb"):
        new_contour = Contour.SANDBOX
    elif contour_lower in ("live", "prod", "production"):
        if not yes and not no_prompt:
            console.print("[yellow]ВНИМАНИЕ:[/yellow] Переключение на LIVE контур")
            console.print("Все операции будут выполняться с реальными деньгами!")
            confirm = typer.prompt("Введите 'LIVE' для подтверждения")
            if confirm != "LIVE":
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        new_contour = Contour.LIVE
    else:
        _fail(f"неизвестный контур: {contour} (допустимо: sandbox, live)", code=2)

    if new_contour != current_contour:
        set_env_value("TCLI_CONTOUR", new_contour.value, env_path=settings.env_path)
        console.print(f"контур: {current_contour.value} → [green]{new_contour.value}[/green]")
        new_token = settings.main_token if new_contour == Contour.LIVE else settings.sandbox_token
        console.print(f"токен: {settings.masked()} → {mask_token(new_token)}")
        log_event("contour_changed", contour=new_contour.value)
    else:
        console.print(f"контур: {current_contour.value} (без изменений)")


# -- Команды уровня счёта -------------------------------------------------


@app.command()
@_guard
def status(json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")) -> None:
    """Счета и сводка портфеля."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        accounts = br.accounts()
        if not accounts:
            _fail(
                f"нет счетов — создайте счёт в {'песочнице' if br.is_sandbox else 'боевом контуре'}"
            )
        account_rows = [Broker.account_row(a) for a in accounts]
        portfolio_rows = []
        for account in accounts:
            portfolio = br.portfolio(account.id)
            portfolio_rows.append(Broker.portfolio_row(account.name or account.id, portfolio))
        
        if json_output:
            result = {
                "contour": br.contour.value,
                "accounts": account_rows,
                "portfolio": portfolio_rows
            }
            print_json(data=result, contour=settings.contour.value, account="")
        else:
            print_accounts(account_rows, contour=br.contour)
            print_summary(portfolio_rows, contour=br.contour)


@app.command()
@_guard
def positions(json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")) -> None:
    """Позиции портфеля."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        account = br.pick_account()
        portfolio = br.portfolio(account.id)
        if not portfolio.positions:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
                console.print("позиций нет")
            raise typer.Exit(0)
        rows = [Broker.position_row(p) for p in portfolio.positions]
        if json_output:
            print_json(data=rows, contour=settings.contour.value, account=account.name or account.id)
        else:
            print_positions(rows)


@app.command()
@_guard
def orders(json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")) -> None:
    """Активные заявки."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        account = br.pick_account()
        active = br.orders(account.id)
        if not active:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
                console.print("активных заявок нет")
            raise typer.Exit(0)
        rows = [Broker.order_row(o, br.ticker(o.figi)) for o in active]
        if json_output:
            print_json(data=rows, contour=settings.contour.value, account=account.name or account.id)
        else:
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
        log_event("account_created", account_id=resp.account_id)


@app.command(name="account-rm")
@_guard
def account_rm(
    account: str = typer.Argument(..., help="Имя или ID счёта для удаления"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Неинтерактивный режим (без подтверждений)"),
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
        
        if not yes and not no_prompt:
            console.print(f"[yellow]ВНИМАНИЕ:[/yellow] Удаление счёта {target.name or target.id}")
            console.print("Все позиции и заявки будут закрыты!")
            confirm = typer.prompt(f"Введите имя счёта для подтверждения: {target.name or target.id}")
            if confirm != (target.name or target.id):
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        br.close_account(target.id)
        console.print(f"[green]счёт удалён[/green]: {target.name or target.id}")
        log_event("account_deleted", account_id=target.id)


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
    client_order_id: Optional[str] = typer.Option(
        None, "--client-order-id", help="ID заявки для идемпотентности (UUIDv4)"
    ),
    tif: Optional[str] = typer.Option(None, "--tif", help="Time-in-force: ioc|fok|gtc"),
    sl: Optional[float] = typer.Option(
        None, "--sl", help="Stop-loss цена (автоматически разместит стоп-заявку)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Неинтерактивный режим (без подтверждений)"),
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
        
        if not yes and not no_prompt:
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
        
        # Time-in-force mapping
        time_in_force = None
        if tif:
            from tinkoff.invest.schemas import TimeInForceType
            tif_map = {
                "ioc": TimeInForceType.TIME_IN_FORCE_FILL_AND_KILL,
                "fok": TimeInForceType.TIME_IN_FORCE_FILL_OR_KILL,
                "gtc": TimeInForceType.TIME_IN_FORCE_GOOD_TILL_DATE,
            }
            if tif.lower() not in tif_map:
                _fail(f"неизвестный tif: {tif} (допустимо: ioc|fok|gtc)", code=2)
            time_in_force = tif_map[tif.lower()]
        
        # Auto-generate client_order_id if not provided (#45)
        if client_order_id is None:
            client_order_id = str(uuid.uuid4())
        
        resp = br.place_order(
            account_id=account.id,
            figi=figi,
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            quantity=lots,
            price=price_quotation,
            order_type=order_type,
            order_id=client_order_id,
            time_in_force=time_in_force,
        )
        
        console.print("[green]заявка выставлена[/green]")
        console.print(f"  order_id: {resp.order_id}")
        console.print(f"  figi: {figi}")
        
        log_event(
            "order_placed",
            order_id=resp.order_id,
            ticker=ticker,
            lots=lots,
            price=price,
            direction="BUY",
        )
        
        # Размещаем стоп-заявку если указан --sl (#24)
        if sl is not None:
            console.print(f"\n[yellow]Размещаю стоп-заявку на {sl}...[/yellow]")
            sl_units = int(sl)
            sl_nano = int(round((sl - sl_units) * 1e9))
            sl_quotation = Quotation(units=sl_units, nano=sl_nano)
            
            try:
                # Для BUY заявки стоп-заявка будет на SELL (защита от падения)
                stop_resp = br.place_stop_order(
                    account_id=account.id,
                    figi=figi,
                    direction=OrderDirection.ORDER_DIRECTION_SELL,
                    quantity=lots,
                    stop_price=sl_quotation,
                )
                console.print("[green]✓ стоп-заявка размещена[/green]")
                console.print(f"  stop_order_id: {stop_resp.stop_order_id}")
                console.print(f"  stop_price: {sl}")
                
                log_event(
                    "stop_order_placed",
                    stop_order_id=stop_resp.stop_order_id,
                    order_id=resp.order_id,
                    ticker=ticker,
                    lots=lots,
                    stop_price=sl,
                    direction="SELL",
                )
            except Exception as e:
                console.print(f"[red]✗ не удалось разместить стоп-заявку: {e}[/red]")
                console.print("[yellow]Основная заявка выполнена, но стоп-заявка не размещена[/yellow]")


@app.command(name="order-sell")
@_guard
def order_sell(
    ticker: str = typer.Argument(..., help="Тикер инструмента"),
    lots: int = typer.Argument(..., help="Количество лотов"),
    price: Optional[float] = typer.Option(None, "--price", help="Лимитная цена (иначе рыночная)"),
    client_order_id: Optional[str] = typer.Option(
        None, "--client-order-id", help="ID заявки для идемпотентности (UUIDv4)"
    ),
    tif: Optional[str] = typer.Option(None, "--tif", help="Time-in-force: ioc|fok|gtc"),
    sl: Optional[float] = typer.Option(
        None, "--sl", help="Stop-loss цена (автоматически разместит стоп-заявку)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Неинтерактивный режим (без подтверждений)"),
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
        
        if not yes and not no_prompt:
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
        
        # Time-in-force mapping
        time_in_force = None
        if tif:
            from tinkoff.invest.schemas import TimeInForceType
            tif_map = {
                "ioc": TimeInForceType.TIME_IN_FORCE_FILL_AND_KILL,
                "fok": TimeInForceType.TIME_IN_FORCE_FILL_OR_KILL,
                "gtc": TimeInForceType.TIME_IN_FORCE_GOOD_TILL_DATE,
            }
            if tif.lower() not in tif_map:
                _fail(f"неизвестный tif: {tif} (допустимо: ioc|fok|gtc)", code=2)
            time_in_force = tif_map[tif.lower()]
        
        # Auto-generate client_order_id if not provided (#45)
        if client_order_id is None:
            client_order_id = str(uuid.uuid4())
        
        resp = br.place_order(
            account_id=account.id,
            figi=figi,
            direction=OrderDirection.ORDER_DIRECTION_SELL,
            quantity=lots,
            price=price_quotation,
            order_type=order_type,
            order_id=client_order_id,
            time_in_force=time_in_force,
        )
        
        console.print("[green]заявка выставлена[/green]")
        console.print(f"  order_id: {resp.order_id}")
        console.print(f"  figi: {figi}")
        
        log_event(
            "order_placed",
            order_id=resp.order_id,
            ticker=ticker,
            lots=lots,
            price=price,
            direction="SELL",
        )
        
        # Размещаем стоп-заявку если указан --sl (#24)
        if sl is not None:
            console.print(f"\n[yellow]Размещаю стоп-заявку на {sl}...[/yellow]")
            sl_units = int(sl)
            sl_nano = int(round((sl - sl_units) * 1e9))
            sl_quotation = Quotation(units=sl_units, nano=sl_nano)
            
            try:
                # Для SELL заявки стоп-заявка будет на BUY (защита от роста)
                stop_resp = br.place_stop_order(
                    account_id=account.id,
                    figi=figi,
                    direction=OrderDirection.ORDER_DIRECTION_BUY,
                    quantity=lots,
                    stop_price=sl_quotation,
                )
                console.print("[green]✓ стоп-заявка размещена[/green]")
                console.print(f"  stop_order_id: {stop_resp.stop_order_id}")
                console.print(f"  stop_price: {sl}")
                
                log_event(
                    "stop_order_placed",
                    stop_order_id=stop_resp.stop_order_id,
                    order_id=resp.order_id,
                    ticker=ticker,
                    lots=lots,
                    stop_price=sl,
                    direction="BUY",
                )
            except Exception as e:
                console.print(f"[red]✗ не удалось разместить стоп-заявку: {e}[/red]")
                console.print("[yellow]Основная заявка выполнена, но стоп-заявка не размещена[/yellow]")


@app.command(name="order-cancel")
@_guard
def order_cancel(
    order_id: str = typer.Argument(..., help="ID заявки"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Неинтерактивный режим"),
) -> None:
    """Отменить заявку."""
    if not yes and not no_prompt:
        confirm = typer.confirm(f"Отменить заявку {order_id}?")
        if not confirm:
            console.print("[red]Отменено пользователем[/red]")
            raise typer.Exit(1)
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        account = br.pick_account()
        br.cancel_order(account.id, order_id)
        console.print(f"[green]заявка отменена[/green]: {order_id}")
        log_event("order_cancelled", order_id=order_id)


@app.command(name="order-modify")
@_guard
def order_modify(
    order_id: str = typer.Argument(..., help="ID заявки для изменения"),
    quantity: Optional[int] = typer.Option(None, "--quantity", "-q", help="Новое количество лотов"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Новая цена"),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key", help="Ключ идемпотентности"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Неинтерактивный режим"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате"),
) -> None:
    """Изменить существующую заявку (#25).
    
    Можно изменить количество лотов и/или цену заявки.
    """
    if quantity is None and price is None:
        _fail("Укажите хотя бы один параметр: --quantity или --price", code=2)
    
    if quantity is not None and quantity <= 0:
        _fail("Количество должно быть больше 0", code=2)
    
    if price is not None and price <= 0:
        _fail("Цена должна быть больше 0", code=2)
    
    if not yes and not no_prompt:
        changes = []
        if quantity is not None:
            changes.append(f"количество: {quantity}")
        if price is not None:
            changes.append(f"цена: {price}")
        console.print(f"Изменить заявку {order_id}: {', '.join(changes)}")
        confirm = typer.confirm("Подтвердить изменение?")
        if not confirm:
            console.print("[red]Отменено пользователем[/red]")
            raise typer.Exit(1)
    
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        
        # Convert price to Quotation if provided
        price_quotation = None
        if price is not None:
            units = int(price)
            nano = int(round((price - units) * 1e9))
            from tinkoff.invest.schemas import Quotation
            price_quotation = Quotation(units=units, nano=nano)
        
        resp = br.modify_order(
            account_id=account.id,
            order_id=order_id,
            quantity=quantity,
            price=price_quotation,
            idempotency_key=idempotency_key,
        )
        
        if json_output:
            result = {
                "status": "success",
                "order_id": resp.order_id,
                "new_quantity": quantity,
                "new_price": price,
            }
            console.print_json(
                data=result,
                contour=settings.contour.value,
                account=account.name or account.id,
            )
        else:
            console.print(f"[green]✓ Заявка {order_id} изменена[/green]")
            console.print(f"  Новый order_id: {resp.order_id}")
            if quantity is not None:
                console.print(f"  Новое количество: {quantity}")
            if price is not None:
                console.print(f"  Новая цена: {price}")
        
        log_event(
            "order_modified",
            order_id=order_id,
            new_order_id=resp.order_id,
            new_quantity=quantity,
            new_price=price,
        )



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
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")
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
        if json_output:
            result = {
                "ticker": ticker,
                "figi": figi,
                "price": str(last.price),
                "time": str(last.time)
            }
            print_json(data=result, contour=settings.contour.value, account="")
        else:
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
        help="Интервал: 1min, 5min, 15min, 1hour, 4h, 1day",
    ),
    days: int = typer.Option(30, "--days", "-d", help="Количество дней истории"),
    session: str = typer.Option(
        "all",
        "--session",
        "-s",
        help="Сессия: day (10:00-18:40), evening (19:05-23:50), all",
    ),
    from_date: Optional[str] = typer.Option(
        None, "--from", help="Начальная дата (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)"
    ),
    to_date: Optional[str] = typer.Option(
        None, "--to", help="Конечная дата (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Файл для экспорта (CSV или JSON)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате")
) -> None:
    """История свечей инструмента с расширенной фильтрацией (#2-4 из TODO.md)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    from tinkoff.invest.schemas import CandleInterval
    
    # Базовые интервалы API
    interval_map = {
        "1min": CandleInterval.CANDLE_INTERVAL_1_MIN,
        "5min": CandleInterval.CANDLE_INTERVAL_5_MIN,
        "15min": CandleInterval.CANDLE_INTERVAL_15_MIN,
        "1hour": CandleInterval.CANDLE_INTERVAL_HOUR,
        "1day": CandleInterval.CANDLE_INTERVAL_DAY,
    }
    
    # 4h интервал требует склеивания 4×1h свечей
    is_4h = interval == "4h"
    api_interval = "1hour" if is_4h else interval
    
    if api_interval not in interval_map:
        available = ", ".join(list(interval_map.keys()) + ["4h"])
        _fail(f"неизвестный интервал: {interval} (допустимо: {available})", code=2)
    if session not in ("day", "evening", "all"):
        _fail(f"неизвестная сессия: {session} (допустимо: day, evening, all)", code=2)
    
    # Парсинг дат
    now = datetime.now(timezone.utc)
    if to_date:
        try:
            if "T" in to_date:
                to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            else:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _fail(f"неверный формат --to: {to_date} (используйте YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)", code=2)
    else:
        to_dt = now
    
    if from_date:
        try:
            if "T" in from_date:
                from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            else:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _fail(
                f"неверный формат --from: {from_date} "
                "(используйте YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)",
                code=2,
            )

    _validate_range(from_dt, to_dt)

    with _open_broker(settings) as br:
        figi = br.figi(ticker)
        
        # Получаем свечи с API
        candle_list = br.candles(
            figi=figi,
            interval=interval_map[api_interval],
            from_=from_dt,
            to=to_dt,
        )
        
        if not candle_list:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
                console.print("свечей нет")
            raise typer.Exit(0)
        
        # Фильтрация по сессиям (если нужно)
        if session != "all":
            candle_list = _filter_by_session(candle_list, session)
        
        # Склеивание 4h свечей (если нужно)
        if is_4h:
            candle_list = _merge_to_4h(candle_list)
        
        if not candle_list:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
                console.print(f"свечей для сессии '{session}' не найдено")
            raise typer.Exit(0)
        
        rows = []
        for c in candle_list:
            rows.append({
                "time": str(c.time),
                "open": str(c.open),
                "high": str(c.high),
                "low": str(c.low),
                "close": str(c.close),
                "volume": c.volume,
            })
        
        # Экспорт в файл (#11 из TODO.md)
        if output:
            if output.endswith('.json'):
                result = {
                    "ticker": ticker,
                    "interval": interval,
                    "session": session,
                    "from": from_dt.isoformat(),
                    "to": to_dt.isoformat(),
                    "candles": rows
                }
                import json
                with open(output, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            elif output.endswith('.csv'):
                import csv
                with open(output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['time', 'open', 'high', 'low', 'close', 'volume'])
                    writer.writeheader()
                    writer.writerows(rows)
            else:
                _fail(f"неподдерживаемый формат файла: {output} (используйте .json или .csv)", code=2)
            
            console.print(f"[green]Экспортировано {len(rows)} свечей в {output}[/green]")
            raise typer.Exit(0)
        
        if json_output:
            result = {
                "ticker": ticker,
                "interval": interval,
                "session": session,
                "from": from_dt.isoformat(),
                "to": to_dt.isoformat(),
                "candles": rows
            }
            print_json(data=result, contour=settings.contour.value, account="")
        else:
            print_candles(rows, ticker=ticker, interval=interval)


def _filter_by_session(candles: list, session: str) -> list:
    """Фильтрация свечей по торговой сессии (#3 из TODO.md)."""
    filtered = []
    for c in candles:
        hour = c.time.hour
        minute = c.time.minute
        time_minutes = hour * 60 + minute
        
        if session == "day":
            # Дневная сессия: 10:00 - 18:40
            if 600 <= time_minutes <= 1120:  # 10:00-18:40
                filtered.append(c)
        elif session == "evening":
            # Вечерняя сессия: 19:05 - 23:50
            if 1145 <= time_minutes <= 1430:  # 19:05-23:50
                filtered.append(c)
    
    return filtered


def _merge_to_4h(candles: list) -> list:
    """Склеивание 1h свечей в 4h (#2 из TODO.md)."""
    if not candles:
        return []
    
    merged = []
    current_group = []
    
    for c in candles:
        # Группируем по 4 часа
        hour_block = (c.time.hour // 4) * 4
        
        if not current_group:
            current_group.append(c)
        else:
            last_hour_block = (current_group[-1].time.hour // 4) * 4
            same_day = current_group[-1].time.date() == c.time.date()
            
            if same_day and hour_block == last_hour_block:
                current_group.append(c)
            else:
                # Создаём merged свечу
                merged.append(_merge_candle_group(current_group))
                current_group = [c]
    
    # Не забываем последнюю группу
    if current_group:
        merged.append(_merge_candle_group(current_group))
    
    return merged


def _merge_candle_group(group: list) -> Any:
    """Создание одной 4h свечи из группы 1h свечей."""
    from tinkoff.invest.schemas import Candle
    
    if not group:
        return None
    
    # Open - из первой свечи
    open_price = group[0].open
    
    # High - максимум из всех high
    high_price = max(g.high for g in group)
    
    # Low - минимум из всех low
    low_price = min(g.low for g in group)
    
    # Close - из последней свечи
    close_price = group[-1].close
    
    # Volume - сумма всех volume
    total_volume = sum(g.volume for g in group)
    
    # Time - время начала первой свечи
    start_time = group[0].time
    
    return Candle(
        time=start_time,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=total_volume,
    )


@app.command()
@_guard
def find(
    query: str = typer.Argument(..., help="Поисковый запрос (тикер, название, ISIN, FIGI, UID)"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате"),
) -> None:
    """Поиск инструментов."""
    import re
    
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    # Определяем тип запроса
    query_upper = query.strip().upper()
    is_isin = len(query_upper) == 12 and re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", query_upper)
    is_figi = query_upper.startswith("BBG") or (query_upper.startswith("TCS") and len(query_upper) == 12)
    is_uid = query_upper.startswith("TCS") and len(query_upper) > 12
    
    with _open_broker(settings) as br:
        # Если это структурированный ID (ISIN/FIGI/UID), используем умный поиск
        if is_isin or is_figi or is_uid:
            try:
                inst = br.find_instrument_smart(query)
                instruments = [inst]
            except Exception:
                instruments = []
        else:
            # Обычный текстовый поиск по тикеру/названию
            instruments = br.find_instrument(query)
        
        if not instruments:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
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
        
        if json_output:
            print_json(data=rows, contour=settings.contour.value, account="")
        else:
            print_instruments(rows, query=query)


@app.command()
@_guard
def instruments(
    instrument_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Тип: share, bond, etf, future, currency"
    ),
    price_min: Optional[float] = typer.Option(None, "--price-min", help="Минимальная цена"),
    price_max: Optional[float] = typer.Option(None, "--price-max", help="Максимальная цена"),
    name: Optional[str] = typer.Option(None, "--name", help="Поиск по названию (содержит)"),
    ticker: Optional[str] = typer.Option(None, "--ticker", help="Поиск по тикеру (содержит)"),
    currency: Optional[str] = typer.Option(None, "--currency", help="Валюта (RUB, USD, EUR)"),
    exchange: Optional[str] = typer.Option(None, "--exchange", help="Биржа (MOEX, SPB)"),
    lot_min: Optional[int] = typer.Option(None, "--lot-min", help="Минимальная лотность"),
    lot_max: Optional[int] = typer.Option(None, "--lot-max", help="Максимальная лотность"),
    available: bool = typer.Option(False, "--available", help="Только доступные для торговли"),
    maturity_from: Optional[str] = typer.Option(
        None, "--maturity-from", help="Дата погашения от (YYYY-MM-DD)"
    ),
    maturity_to: Optional[str] = typer.Option(
        None, "--maturity-to", help="Дата погашения до (YYYY-MM-DD)"
    ),
    coupon_min: Optional[float] = typer.Option(None, "--coupon-min", help="Минимальный купон (%)"),
    coupon_max: Optional[float] = typer.Option(None, "--coupon-max", help="Максимальный купон (%)"),
    market_cap_min: Optional[float] = typer.Option(
        None, "--market-cap-min", help="Минимальная капитализация"
    ),
    market_cap_max: Optional[float] = typer.Option(
        None, "--market-cap-max", help="Максимальная капитализация"
    ),
    management_fee_max: Optional[float] = typer.Option(
        None, "--management-fee-max", help="Максимальная комиссия ETF (%)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате"),
) -> None:
    """Фильтрация инструментов по типу, цене, валюте и другим параметрам."""
    # Валидация типа инструмента
    valid_types = ("share", "bond", "etf", "future", "currency")
    if instrument_type and instrument_type not in valid_types:
        _fail(f"неизвестный тип инструмента: {instrument_type} (допустимо: {', '.join(valid_types)})", code=2)
    
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        # Получаем все инструменты (по типу или все)
        all_instruments = br.get_all_instruments(instrument_type)
        
        if not all_instruments:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
                console.print("инструменты не найдены")
            raise typer.Exit(0)
        
        # Получаем текущие цены для всех инструментов
        prices_dict = {}
        figi_list = [inst.figi for inst in all_instruments if hasattr(inst, 'figi')]
        if figi_list:
            try:
                last_prices = br.last_prices(figi_list)
                for lp in last_prices:
                    if hasattr(lp, 'price'):
                        price_val = money_to_float(lp.price)
                        prices_dict[lp.figi] = price_val
            except Exception:
                # Если не удалось получить цены, продолжаем без цен
                pass
        
        # Применяем фильтры
        filtered = []
        for inst in all_instruments:
            # Фильтр по тикеру (содержит)
            if ticker:
                inst_ticker = getattr(inst, 'ticker', '') or ''
                if ticker.upper() not in inst_ticker.upper():
                    continue
            
            # Фильтр по названию (содержит)
            if name:
                inst_name = getattr(inst, 'name', '') or ''
                if name.lower() not in inst_name.lower():
                    continue
            
            # Фильтр по валюте
            if currency:
                inst_currency = getattr(inst, 'currency', '') or ''
                if currency.upper() != inst_currency.upper():
                    continue
            
            # Фильтр по бирже
            if exchange:
                inst_exchange = getattr(inst, 'exchange', '') or ''
                if exchange.upper() != inst_exchange.upper():
                    continue
            
            # Фильтр по лотности
            inst_lot = getattr(inst, 'lot', 0) or 0
            if lot_min is not None and inst_lot < lot_min:
                continue
            if lot_max is not None and inst_lot > lot_max:
                continue
            
            # Фильтр по доступности
            if available:
                if not getattr(inst, 'api_trade_available_flag', False):
                    continue
            
            # Фильтр по цене (если указаны мин/макс)
            # Если указана валюта, фильтруем только инструменты с этой валютой
            # Если валюта не указана, фильтруем только RUB
            if price_min is not None or price_max is not None:
                inst_figi = getattr(inst, 'figi', '')
                inst_currency_val = getattr(inst, 'currency', '') or ''
                
                # Определяем целевую валюту для фильтрации
                target_currency = currency.upper() if currency else 'RUB'
                
                # Пропускаем инструменты не в целевой валюте
                if inst_currency_val.upper() != target_currency:
                    continue
                
                current_price = prices_dict.get(inst_figi)
                if current_price is None:
                    continue
                if price_min is not None and current_price < price_min:
                    continue
                if price_max is not None and current_price > price_max:
                    continue
            
            # Фильтры для облигаций
            if instrument_type == "bond":
                # Фильтр по дате погашения
                maturity_date = getattr(inst, 'maturity_date', None)
                if maturity_from:
                    try:
                        from_date = datetime.strptime(maturity_from, "%Y-%m-%d")
                        if maturity_date is None or maturity_date < from_date:
                            continue
                    except ValueError:
                        pass
                if maturity_to:
                    try:
                        to_date = datetime.strptime(maturity_to, "%Y-%m-%d")
                        if maturity_date is None or maturity_date > to_date:
                            continue
                    except ValueError:
                        pass
                
                # Фильтр по купону (используем nominal как приблизительное значение)
                # В реальном API купон рассчитывается отдельно, здесь упрощение
                # Можно было бы получать купон через operations, но это сложно
                # Пока пропускаем этот фильтр или используем простую логику
                if coupon_min is not None or coupon_max is not None:
                    # Для упрощения пропускаем облигации, если задан фильтр по купону
                    # (требуется дополнительный API вызов для получения реального купона)
                    continue
            
            # Фильтры для акций
            if instrument_type == "share":
                # Фильтр по капитализации
                # В SDK нет прямого поля market_cap, используем issue_size как приближение
                # или пропускаем этот фильтр
                if market_cap_min is not None or market_cap_max is not None:
                    # Пропускаем, так как market_cap не доступен напрямую
                    pass
            
            # Фильтры для ETF
            if instrument_type == "etf":
                # Фильтр по комиссии управления
                if management_fee_max is not None:
                    # В SDK поле total_expense_fee может быть доступно
                    # но для упрощения пропускаем
                    pass
            
            filtered.append(inst)
        
        if not filtered:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
                console.print("инструменты не найдены с заданными фильтрами")
            raise typer.Exit(0)
        
        # Формируем строки для вывода
        rows = []
        for inst in filtered:
            inst_figi = getattr(inst, 'figi', '')
            current_price = prices_dict.get(inst_figi)
            
            row = {
                "ticker": getattr(inst, "ticker", ""),
                "figi": inst.figi,
                "name": getattr(inst, "name", ""),
                "type": getattr(inst, "instrument_type", ""),
                "lot": getattr(inst, "lot", 0),
                "currency": getattr(inst, "currency", ""),
                "price": current_price,
                "min_price_step": money_to_float(getattr(inst, "min_price_increment", 0)),
                "exchange": getattr(inst, "exchange", ""),
            }
            
            # Дополнительные поля для облигаций
            if instrument_type == "bond":
                maturity = getattr(inst, "maturity_date", None)
                if maturity:
                    if hasattr(maturity, 'isoformat'):
                        row["maturity_date"] = maturity.isoformat()
                    else:
                        row["maturity_date"] = str(maturity)
                else:
                    row["maturity_date"] = None
                nominal = getattr(inst, "nominal", None)
                row["nominal"] = money_to_float(nominal) if nominal else None
            
            # Дополнительные поля для акций
            if instrument_type == "share":
                dividend_yield = getattr(inst, "dividend_yield", None)
                if dividend_yield:
                    row["dividend_yield"] = money_to_float(dividend_yield) * 100  # В процентах
                else:
                    row["dividend_yield"] = None
            
            rows.append(row)
        
        if json_output:
            print_json(data=rows, contour=settings.contour.value, account="")
        else:
            filters = {
                "type": instrument_type,
                "price_min": price_min,
                "price_max": price_max,
                "currency": currency,
                "exchange": exchange,
                "available": available,
            }
            print_instruments_filtered(rows, filters)


# -- Новые команды: Export, Watchlist, Help, Account-Select, Info ------------


@app.command()
@_guard
def watchlist(
    action: Optional[str] = typer.Argument(None, help="Действие: add, remove, list (по умолчанию list)"),
    ticker: Optional[str] = typer.Argument(None, help="Тикер для add/remove"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате"),
) -> None:
    """Управление списком отслеживаемых инструментов (избранное)."""
    if action is None or action == "list":
        # Показать текущие цены всех инструментов из watchlist
        settings = _settings()
        tickers = load_watchlist()
        if not tickers:
            if json_output:
                print_json(data=[], contour=settings.contour.value, account="")
            else:
                console.print("watchlist пуст — добавьте инструменты: tcli watchlist add SBER")
            raise typer.Exit(0)
        if not json_output:
            header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
        
        with _open_broker(settings) as br:
            rows = []
            for t in tickers:
                # Шаг 1: Поиск инструмента
                figi = None
                instrument = None
                try:
                    instrument = br.find_instrument_smart(t)
                    figi = getattr(instrument, "figi", "")
                except Exception as e:
                    log_event("watchlist_instrument_error", ticker=t, error=str(e))
                
                # Шаг 2: Получение цены (если инструмент найден)
                price = None
                if figi:
                    try:
                        prices = br.last_prices([figi])
                        if prices:
                            price = money_to_float(prices[0].price)
                            log_event("watchlist_price_retrieved", ticker=t, price=price)
                    except Exception as e:
                        log_event("watchlist_price_error", ticker=t, figi=figi, error=str(e))
                
                # Для простоты показываем 0% изменение (можно улучшить позже)
                rows.append({
                    "ticker": t,
                    "figi": figi if figi else "не найден",
                    "price": price,  # float или None
                    "change": 0.0,
                })
            
            if json_output:
                print_json(data=rows, contour=settings.contour.value, account="")
            else:
                print_watchlist(rows)
    
    elif action == "add":
        if not ticker:
            _fail("укажите тикер: tcli watchlist add SBER", code=2)
        result = add_to_watchlist(ticker)
        if result:
            log_event("watchlist_add", ticker=ticker.upper())
        if json_output:
            print_json(
                data={"action": "add", "ticker": ticker.upper(), "added": result},
                contour=settings.contour.value,
                account="",
            )
        else:
            if result:
                console.print(f"[green]добавлено в watchlist:[/green] {ticker.upper()}")
            else:
                console.print(f"[yellow]уже в watchlist:[/yellow] {ticker.upper()}")
    
    elif action == "remove":
        if not ticker:
            _fail("укажите тикер: tcli watchlist remove SBER", code=2)
        result = remove_from_watchlist(ticker)
        if result:
            log_event("watchlist_remove", ticker=ticker.upper())
        if json_output:
            print_json(
                data={"action": "remove", "ticker": ticker.upper(), "removed": result},
                contour=settings.contour.value,
                account="",
            )
        else:
            if result:
                console.print(f"[green]удалено из watchlist:[/green] {ticker.upper()}")
            else:
                console.print(f"[yellow]не найдено в watchlist:[/yellow] {ticker.upper()}")
    
    else:
        _fail(f"неизвестное действие: {action} (допустимо: add, remove, list)", code=2)


@app.command()
@_guard
def account_select() -> None:
    """Интерактивный выбор активного счёта."""
    # Проверка режима только чтения (#5)
    if _read_only:
        _fail("режим только чтения: выбор счёта запрещён (TCLI_READ_ONLY=1 или --read-only)", code=1)
    
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        accounts = br.accounts()
        if not accounts:
            _fail("нет счетов", code=1)
        
        console.print("\n[bold]Доступные счета:[/bold]")
        for i, account in enumerate(accounts, 1):
            console.print(f"  {i}. {account.name or account.id} [dim]({account.id})[/dim]")
        
        console.print()
        choice = typer.prompt("Выберите номер счёта", type=int)
        
        if choice < 1 or choice > len(accounts):
            _fail(f"неверный номер: {choice} (допустимо 1-{len(accounts)})", code=2)
        
        selected = accounts[choice - 1]
        account_name = selected.name or selected.id
        
        # Сохранить в .env с правильным ключом для контура
        account_key = settings.account_name_key
        set_env_value(account_key, account_name, env_path=settings.env_path)
        console.print(f"[green]выбран счёт:[/green] {account_name}")
        console.print(f"[dim]сохранено в .env как {account_key}[/dim]")
        log_event("account_selected", account_id=selected.id, account_name=account_name)


@app.command()
@_guard
def info(
    ticker: str = typer.Argument(..., help="Тикер, FIGI или UID инструмента"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON формате"),
) -> None:
    """Детальная информация об инструменте."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        
        # Извлечь информацию
        info_dict = {
            "name": getattr(instrument, "name", "N/A"),
            "ticker": getattr(instrument, "ticker", "N/A"),
            "figi": figi,
            "isin": getattr(instrument, "isin", "N/A"),
            "type": getattr(instrument, "instrument_type", "N/A"),
            "currency": getattr(instrument, "currency", "N/A"),
            "lot": getattr(instrument, "lot", "N/A"),
            "exchange": getattr(instrument, "exchange", "N/A"),
            "class_code": getattr(instrument, "class_code", "N/A"),
            "trading_status": getattr(instrument, "trading_status", "N/A"),
        }
        
        # Получить текущую цену
        if figi:
            try:
                prices = br.last_prices([figi])
                if prices:
                    price_val = money_to_float(prices[0].price)
                    info_dict["price"] = price_val
                    info_dict["price_currency"] = getattr(instrument, "currency", "")
                else:
                    info_dict["price"] = None
                    info_dict["price_currency"] = None
            except Exception:
                # В песочнице рыночные данные могут быть недоступны
                info_dict["price"] = None
                info_dict["price_currency"] = None
        else:
            info_dict["price"] = None
            info_dict["price_currency"] = None
        
        if json_output:
            print_json(data=info_dict, contour=settings.contour.value, account="")
        else:
            print_instrument_info(info_dict)


@app.command()
@_guard
def id_info(
    identifier: str = typer.Argument(..., help="Идентификатор (тикер, FIGI, UID, ISIN)"),
) -> None:
    """Показать информацию о типе идентификатора."""
    id_upper = identifier.strip().upper()
    
    # Определить тип по формату
    detected_type = detect_identifier_type(id_upper)
    
    # Проверить наличие в кэше
    cached_type = get_cached_type(id_upper)
    
    console.print(f"[bold]Идентификатор:[/bold] {id_upper}")
    console.print(f"[bold]Определённый тип:[/bold] {detected_type}")
    
    if cached_type:
        console.print(f"[bold]Кэшированный тип:[/bold] {cached_type} [green](используется)[/green]")
    else:
        console.print("[bold]Кэшированный тип:[/bold] [dim]не в кэше[/dim]")
    
    # Показать размер кэша
    cache = load_cache()
    if cache:
        console.print(f"\n[bold]Кэш:[/bold] {len(cache)} записей в {CACHE_PATH}")
        console.print("[dim]Используйте 'tcli id-clear-cache' для очистки кэша[/dim]")
    else:
        console.print("\n[bold]Кэш:[/bold] [dim]пуст[/dim]")


@app.command()
@_guard
def id_clear_cache() -> None:
    """Очистить кэш типов идентификаторов."""
    clear_cache()
    console.print("[green]кэш очищен[/green]")


# -- Market Data: orderbook, trading_status, sessions ----------------------


@app.command()
@_guard
def orderbook(
    ticker: str = typer.Argument(..., help="Тикер или FIGI инструмента"),
    depth: int = typer.Option(10, "--depth", "-d", help="Глубина стакана"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Стакан заявок (orderbook)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        if not figi:
            _fail(f"не удалось получить FIGI для {ticker}", code=4)
        
        ob = br.orderbook(figi, depth=depth)
        
        bids = []
        for b in ob.bids:
            bids.append({"price": money_to_float(b.price), "quantity": b.quantity})
        
        asks = []
        for a in ob.asks:
            asks.append({"price": money_to_float(a.price), "quantity": a.quantity})
        
        limit_up = money_to_float(ob.limit_up)
        limit_down = money_to_float(ob.limit_down)
        
        if json_output:
            print_json(data={
                "figi": figi,
                "bids": bids,
                "asks": asks,
                "limit_up": limit_up,
                "limit_down": limit_down,
            }, contour=settings.contour.value, account="")
        else:
            print_orderbook(figi, bids, asks, limit_up, limit_down)


@app.command()
@_guard
def trading_status(
    ticker: str = typer.Argument(..., help="Тикер или FIGI инструмента"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Статус торгов инструментом."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        if not figi:
            _fail(f"не удалось получить FIGI для {ticker}", code=4)
        
        ts = br.trading_status(figi)
        
        status_map = {
            "NOT_AVAILABLE_FOR_TRADING": "недоступен",
            "OPENING_PERIOD": "открытие",
            "CLOSING_PERIOD": "закрытие",
            "BREAK_IN_TRADING": "перерыв",
            "NORMAL_TRADING": "торги идут",
            "CLOSING_AUCTION": "аукцион закрытия",
        }
        
        status_text = status_map.get(ts.trading_status, ts.trading_status)
        
        result = {
            "figi": figi,
            "status": status_text,
            "buy_available": ts.buy_available,
            "sell_available": ts.sell_available,
            "api_trade": ts.api_trade_available,
        }
        
        if json_output:
            print_json(data=result, contour=settings.contour.value, account="")
        else:
            print_trading_status(figi, result)


@app.command()
@_guard
def sessions(
    exchange: str = typer.Option("MOEX", "--exchange", "-e", help="Биржа"),
    days: int = typer.Option(7, "--days", "-d", help="Количество дней"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Расписание торговых сессий."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        now = datetime.now(timezone.utc)
        from_dt = now
        to_dt = now + timedelta(days=days)
        
        schedules = br.trading_schedules(exchange, from_dt, to_dt)
        
        if not schedules:
            console.print("[dim]расписание не найдено[/dim]")
            raise typer.Exit(0)
        
        rows = []
        for day in schedules:
            rows.append({
                "date": str(day.date),
                "start": str(day.start_time) if day.start_time else "выходной",
                "end": str(day.end_time) if day.end_time else "",
                "is_trading": day.is_trading_day,
            })
        
        if json_output:
            print_json(data={"exchange": exchange, "days": rows}, contour=settings.contour.value, account="")
        else:
            from rich.table import Table
            table = Table(title=f"Расписание торгов ({exchange})")
            table.add_column("Дата")
            table.add_column("Начало")
            table.add_column("Конец")
            table.add_column("Торги")
            
            for row in rows:
                status = "[green]✓[/green]" if row["is_trading"] else "[red]✗[/red]"
                table.add_row(row["date"], row["start"], row["end"], status)
            
            console.print(table)


# -- Risk/Estimation: estimate ----------------------------------------------


@app.command()
@_guard
def estimate(
    ticker: str = typer.Argument(..., help="Тикер инструмента"),
    quantity: int = typer.Argument(..., help="Количество лотов"),
    direction: str = typer.Argument("buy", help="Направление: buy или sell"),
    price: Optional[float] = typer.Option(
        None,
        "--price",
        help="Цена (если не указана, используется рыночная)",
    ),
    estimate_margin: bool = typer.Option(False, "--margin", help="Оценить требуемую маржу"),
    estimate_commission: bool = typer.Option(False, "--commission", help="Оценить комиссию"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Оценка стоимости заявки (#21 из TODO.md)."""
    from tinkoff.invest.schemas import OrderDirection, Quotation
    
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    # Определяем направление
    dir_lower = direction.lower()
    if dir_lower not in ("buy", "sell"):
        _fail("направление должно быть 'buy' или 'sell'", code=2)
    
    order_direction = (
        OrderDirection.ORDER_DIRECTION_BUY
        if dir_lower == "buy"
        else OrderDirection.ORDER_DIRECTION_SELL
    )
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        
        # Получаем инструмент
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        lot = getattr(instrument, "lot", 1)
        ticker_name = getattr(instrument, "ticker", ticker)
        
        result = {
            "ticker": ticker_name,
            "figi": figi,
            "direction": dir_lower,
            "quantity": quantity,
            "lot": lot,
            "total_lots": quantity * lot,
        }
        
        # Если указана цена, используем её
        price_quotation = None
        if price is not None:
            units = int(price)
            nano = int(round((price - units) * 1e9))
            price_quotation = Quotation(units=units, nano=nano)
            result["price"] = str(price)
        else:
            # Получаем рыночную цену
            try:
                prices = br.last_prices([figi])
                if prices:
                    last_price = prices[0].price
                    result["price"] = str(money_to_float(last_price))
                else:
                    result["price"] = None
            except Exception:
                result["price"] = None
        
        # Оценка маржи
        if estimate_margin:
            try:
                margin_resp = br.get_estimated_margin(
                    account_id=account.id,
                    figi=figi,
                    direction=order_direction,
                    quantity=quantity,
                    price=price_quotation,
                )
                # margin_resp содержит поля: commission, total_asset_amount, etc.
                result["margin"] = {
                    "commission": (
                        str(money_to_float(margin_resp.commission))
                        if hasattr(margin_resp, "commission")
                        else "0"
                    ),
                    "total_asset_amount": (
                        str(money_to_float(margin_resp.total_asset_amount))
                        if hasattr(margin_resp, "total_asset_amount")
                        else "0"
                    ),
                }
            except Exception as exc:
                result["margin"] = {"error": str(exc)}
        
        # Оценка комиссии
        if estimate_commission and result.get("price"):
            try:
                price_float = float(result["price"])
                total_value = price_float * quantity * lot
                commission = br.estimate_commission(total_value)
                result["commission"] = {
                    "amount": str(commission),
                    "tariff": "0.003",  # 0.3% по умолчанию
                    "total_value": str(total_value),
                }
            except Exception as exc:
                result["commission"] = {"error": str(exc)}
        
        if json_output:
            print_json(data=result, contour=settings.contour.value, account="")
        else:
            console.print("\n[bold]Оценка заявки:[/bold]")
            console.print(f"  Инструмент: {result['ticker']} (FIGI: {result['figi']})")
            console.print(f"  Направление: {result['direction'].upper()}")
            console.print(f"  Лоты: {result['quantity']} × {result['lot']} = {result['total_lots']} шт.")
            if result.get("price"):
                console.print(f"  Цена: {result['price']} ₽")
            
            if "margin" in result:
                if "error" in result["margin"]:
                    console.print(f"  [red]Маржа: ошибка — {result['margin']['error']}[/red]")
                else:
                    console.print(f"  Требуемая маржа: {result['margin']['total_asset_amount']} ₽")
                    console.print(f"  Комиссия (маржа): {result['margin']['commission']} ₽")
            
            if "commission" in result:
                if "error" in result["commission"]:
                    console.print(f"  [red]Комиссия: ошибка — {result['commission']['error']}[/red]")
                else:
                    console.print(f"  Стоимость: {result['commission']['total_value']} ₽")
                    tariff = result["commission"]["tariff"]
                    amount = result["commission"]["amount"]
                    console.print(f"  Комиссия ({tariff}%): {amount} ₽")


# -- Position Management: close, cancel_all, stop_orders -------------------


@app.command()
@_guard
def close(
    ticker: str = typer.Argument(..., help="Тикер или FIGI инструмента"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Без подтверждения"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Без подтверждений"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Закрыть позицию по инструменту (рыночная заявка)."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        if not figi:
            _fail(f"не удалось получить FIGI для {ticker}", code=4)
        
        account = br.pick_account()
        position = br.get_position(account.id, figi)
        
        if not position or position.balance == 0:
            _fail(f"позиция по {ticker} не найдена или пуста", code=4)
        
        quantity = abs(position.balance)
        
        # Определить направление: если позиция в лонг — продаём, если в шорт — покупаем
        # Но в тcli пока только лонг, значит продаём
        direction = "SELL" if position.balance > 0 else "BUY"
        
        if not yes and not no_prompt:
            console.print(f"\n[bold]Закрытие позиции:[/bold] {ticker}")
            console.print(f"  Количество: {quantity}")
            console.print(f"  Направление: {direction}")
            console.print(f"  Контур: [yellow]{br.contour.value}[/yellow]")
            confirm = typer.confirm("Подтвердить закрытие?")
            if not confirm:
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        result = br.close_position(account.id, figi)
        console.print(f"[green]позиция закрыта[/green]: {ticker}")
        console.print(f"  order_id: {result.order_id}")
        log_event("position_closed", ticker=ticker, figi=figi, quantity=quantity)
        
        if json_output:
            print_json(
                data={"order_id": result.order_id, "ticker": ticker},
                contour=settings.contour.value,
                account=account.name or account.id,
            )


@app.command()
@_guard
def close_all(
    yes: bool = typer.Option(False, "--yes", "-y", help="Без подтверждения"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Без подтверждений"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Закрыть все открытые позиции."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        portfolio = br.portfolio(account.id)
        
        if not portfolio.positions:
            console.print("[dim]позиций нет[/dim]")
            raise typer.Exit(0)
        
        positions_with_qty = [
            p for p in portfolio.positions if money_to_float(p.quantity) != 0
        ]
        
        if not positions_with_qty:
            console.print("[dim]позиций с ненулевым количеством нет[/dim]")
            raise typer.Exit(0)
        
        if not yes and not no_prompt:
            console.print(f"\n[bold]Закрытие всех позиций:[/bold] {len(positions_with_qty)} шт.")
            console.print(f"  Контур: [yellow]{br.contour.value}[/yellow]")
            confirm = typer.confirm("Подтвердить закрытие ВСЕХ позиций?")
            if not confirm:
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        closed = []
        for pos in positions_with_qty:
            figi = pos.figi
            try:
                result = br.close_position(account.id, figi)
                ticker = br.ticker(figi)
                closed.append({"ticker": ticker, "figi": figi, "order_id": result.order_id})
                console.print(f"[green]закрыта:[/green] {ticker} (order_id: {result.order_id})")
            except Exception as exc:
                ticker = br.ticker(figi)
                console.print(f"[red]ошибка при закрытии {ticker}:[/red] {api_error_text(exc)}")
        
        log_event("all_positions_closed", count=len(closed))
        
        if json_output:
            print_json(
                data={"closed": closed},
                contour=settings.contour.value,
                account=account.name or account.id,
            )


@app.command()
@_guard
def cancel_all(
    yes: bool = typer.Option(False, "--yes", "-y", help="Без подтверждения"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Без подтверждений"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Отменить все открытые заявки."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        result = br.cancel_all_orders(account.id)
        
        console.print(f"[green]заявки отменены[/green]: {result.orders_canceled} шт.")
        log_event("all_orders_canceled", count=result.orders_canceled)
        
        if json_output:
            print_json(
            data={"canceled": result.orders_canceled},
            contour=settings.contour.value,
            account=account.name or account.id,
        )


@app.command()
@_guard
def order_info(
    order_id: str = typer.Argument(..., help="ID заявки"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Информация о конкретной заявке."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        order = br.get_order_info(account.id, order_id)
        
        info_dict = {
            "order_id": order.order_id,
            "figi": order.figi,
            "direction": order.direction.name if hasattr(order.direction, "name") else str(order.direction),
            "quantity": order.lots_requested,
            "executed": order.lots_executed,
            "status": (
                order.execution_report_status.name
                if hasattr(order.execution_report_status, "name")
                else str(order.execution_report_status)
            ),
            "price": money_to_float(order.initial_order_price),
        }
        
        if json_output:
            print_json(data=info_dict, contour=settings.contour.value, account=account.name or account.id)
        else:
            console.print(f"\n[bold]Заявка[/bold] {order_id}")
            console.print("=" * 60)
            for key, value in info_dict.items():
                console.print(f"  [bold]{key}:[/bold] {value}")
            console.print()


@app.command()
@_guard
def stop_order_list(
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Список стоп-заявок."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        stop_orders = br.stop_orders(account.id)
        
        if not stop_orders:
            console.print("[dim]стоп-заявок нет[/dim]")
            raise typer.Exit(0)
        
        rows = []
        for so in stop_orders:
            rows.append({
                "id": so.stop_order_id,
                "figi": so.figi,
                "direction": so.direction.name if hasattr(so.direction, "name") else str(so.direction),
                "quantity": so.lots_requested,
                "price": money_to_float(so.price),
                "status": so.status.name if hasattr(so.status, "name") else str(so.status),
            })
        
        if json_output:
            print_json(
            data={"stop_orders": rows},
            contour=settings.contour.value,
            account=account.name or account.id,
        )
        else:
            print_stop_orders(rows)


@app.command()
@_guard
def stop_order_cancel(
    stop_order_id: str = typer.Argument(..., help="ID стоп-заявки"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Без подтверждения"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Без подтверждений"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Отменить стоп-заявку."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        
        if not yes and not no_prompt:
            console.print(f"\n[bold]Отмена стоп-заявки:[/bold] {stop_order_id}")
            confirm = typer.confirm("Подтвердить отмену?")
            if not confirm:
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        br.cancel_stop_order(account.id, stop_order_id)
        console.print(f"[green]стоп-заявка отменена[/green]: {stop_order_id}")
        log_event("stop_order_cancelled", stop_order_id=stop_order_id)
        
        if json_output:
            print_json(
            data={"cancelled": stop_order_id},
            contour=settings.contour.value,
            account=account.name or account.id,
        )


@app.command()
@_guard
def stop_order_place(
    ticker: str = typer.Argument(..., help="Тикер или FIGI инструмента"),
    lots: int = typer.Argument(..., help="Количество лотов"),
    stop_price: float = typer.Option(..., "--stop-price", help="Стоп-цена"),
    price: Optional[float] = typer.Option(
        None, "--price", help="Лимитная цена (иначе рыночная после активации)"
    ),
    direction: str = typer.Option(..., "--direction", help="Направление: BUY или SELL"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Неинтерактивный режим (без подтверждений)"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Разместить стоп-заявку."""
    if lots <= 0:
        _fail("количество лотов должно быть больше 0", code=2)
    
    direction_upper = direction.upper()
    if direction_upper not in ("BUY", "SELL"):
        _fail("направление должно быть BUY или SELL", code=2)
    
    if stop_price <= 0:
        _fail("стоп-цена должна быть больше 0", code=2)
    
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        from tinkoff.invest.schemas import OrderDirection, Quotation
        
        account = br.pick_account()
        figi = br.figi(ticker)
        
        if direction_upper == "BUY":
            order_direction = OrderDirection.ORDER_DIRECTION_BUY
        else:
            order_direction = OrderDirection.ORDER_DIRECTION_SELL
        
        stop_price_str = fmt_money(stop_price)
        price_str = fmt_money(price) if price is not None else "рыночная после активации"
        
        if not yes and not no_prompt:
            console.print(f"\n[bold]Стоп-заявка ({direction_upper}):[/bold] {ticker} × {lots} лот(ов)")
            console.print(f"  Счёт: {account.name or account.id}")
            console.print(f"  Стоп-цена: {stop_price_str}")
            console.print(f"  Цена исполнения: {price_str}")
            console.print(f"  Контур: [yellow]{br.contour.value}[/yellow]")
            confirm = typer.confirm("Подтвердить стоп-заявку?")
            if not confirm:
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        stop_price_quotation = Quotation(
            units=int(stop_price),
            nano=int(round((stop_price - int(stop_price)) * 1e9))
        )
        
        price_quotation = None
        if price is not None:
            price_quotation = Quotation(units=int(price), nano=int(round((price - int(price)) * 1e9)))
        
        resp = br.place_stop_order(
            account_id=account.id,
            figi=figi,
            direction=order_direction,
            quantity=lots,
            stop_price=stop_price_quotation,
            price=price_quotation,
        )
        
        stop_order_id = getattr(resp, "stop_order_id", "")
        
        if json_output:
            result = {
                "stop_order_id": stop_order_id,
                "ticker": ticker,
                "figi": figi,
                "direction": direction_upper,
                "lots": lots,
                "stop_price": str(stop_price_quotation),
                "price": str(price_quotation) if price_quotation else "market",
            }
            print_json(data=result, contour=settings.contour.value, account="")
        else:
            console.print("\n[green]стоп-заявка размещена[/green]")
            console.print(f"  stop_order_id: {stop_order_id}")
            console.print(f"  figi: {figi}")
        
        log_event(
            "stop_order_placed",
            stop_order_id=stop_order_id,
            ticker=ticker,
            lots=lots,
            direction=direction_upper
        )


@app.command(name="stop-order-cancel-all")
@_guard
def stop_order_cancel_all(
    yes: bool = typer.Option(False, "--yes", "-y", help="Не запрашивать подтверждение"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Неинтерактивный режим (без подтверждений)"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Отменить все стоп-заявки."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    with _open_broker(settings) as br:
        account = br.pick_account()
        
        # Получаем список активных стоп-заявок для подсчёта
        active_stops = br.stop_orders(account.id)
        count = len(active_stops)
        
        if count == 0:
            if json_output:
                print_json(
                    data={"cancelled_count": 0, "cancelled_ids": []},
                    contour=settings.contour.value,
                    account=account.name or account.id,
                )
            else:
                console.print("активных стоп-заявок нет")
            raise typer.Exit(0)
        
        if not yes and not no_prompt:
            console.print(f"\n[bold]Отмена всех стоп-заявок:[/bold] {count} шт.")
            console.print(f"  Счёт: {account.name or account.id}")
            console.print(f"  Контур: [yellow]{br.contour.value}[/yellow]")
            confirm = typer.confirm("Подтвердить отмену?")
            if not confirm:
                console.print("[red]Отменено[/red]")
                raise typer.Exit(1)
        
        # Отменяем все стоп-заявки
        cancelled = br.cancel_all_stop_orders(account.id)
        cancelled_count = len(cancelled)
        cancelled_ids = [str(c.stop_order_id) for c in cancelled if hasattr(c, "stop_order_id")]
        
        if json_output:
            result = {
                "cancelled_count": cancelled_count,
                "cancelled_ids": cancelled_ids
            }
            print_json(data=result, contour=settings.contour.value, account="")
        else:
            console.print(f"[green]отменено стоп-заявок:[/green] {cancelled_count} из {count}")
            for stop_id in cancelled_ids:
                console.print(f"  ✓ {stop_id}")
        
        log_event("stop_orders_cancel_all", cancelled_count=cancelled_count, total_count=count)


@app.command()
@_guard
def free_cash(
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Свободные средства на счёте."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        account = br.pick_account()
        cash = br.get_free_cash(account.id)
        
        amount = money_to_float(cash) if cash else 0.0
        currency = getattr(cash, "currency", "RUB") if cash else "RUB"
        
        if json_output:
            print_json(
                data={"amount": amount, "currency": currency},
                contour=settings.contour.value,
                account=account.name or account.id,
            )
        else:
            console.print(f"[bold]Свободные средства:[/bold] {amount:,.2f} {currency}")


@app.command()
@_guard
def has_position(
    ticker: str = typer.Argument(..., help="Тикер или FIGI инструмента"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Проверить наличие позиции по инструменту."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        if not figi:
            _fail(f"не удалось получить FIGI для {ticker}", code=4)
        
        account = br.pick_account()
        position = br.get_position(account.id, figi)
        
        has_pos = position is not None and position.balance != 0
        quantity = money_to_float(position.quantity) if position else 0.0
        
        if json_output:
            print_json(
                data={
                    "ticker": ticker,
                    "figi": figi,
                    "has_position": has_pos,
                    "quantity": quantity,
                }
            )
        else:
            if has_pos:
                console.print(f"[green]✓ позиция есть:[/green] {ticker} ({quantity} шт.)")
            else:
                console.print(f"[dim]✗ позиции нет:[/dim] {ticker}")


@app.command()
@_guard
def is_market_open(
    ticker: str = typer.Argument(..., help="Тикер или FIGI инструмента"),
    json_output: bool = typer.Option(False, "--json", help="Вывод в JSON"),
) -> None:
    """Проверить, открыт ли рынок для инструмента."""
    settings = _settings()
    header_line(settings.masked(), settings.contour_label(), settings.env_path.exists())
    
    with _open_broker(settings) as br:
        instrument = br.find_instrument_smart(ticker)
        figi = getattr(instrument, "figi", "")
        if not figi:
            _fail(f"не удалось получить FIGI для {ticker}", code=4)
        
        open_status = br.is_market_open(figi)
        
        if json_output:
            print_json(
                data={"ticker": ticker, "figi": figi, "market_open": open_status},
                contour=settings.contour.value,
                account="",
            )
        else:
            if open_status:
                console.print(f"[green]✓ рынок открыт:[/green] {ticker}")
            else:
                console.print(f"[red]✗ рынок закрыт:[/red] {ticker}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
