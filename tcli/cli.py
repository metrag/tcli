"""typer-приложение tcli: команды песочницы Tinkoff Invest API."""

from __future__ import annotations

from functools import wraps
from typing import Any

import typer

from .client import Sandbox, SandboxError, api_error_text
from .config import Settings
from .render import (
    console,
    fmt_money,
    header_line,
    print_accounts,
    print_orders,
    print_positions,
    print_summary,
)
from .ssl import ENV_VAR, cert_status

app = typer.Typer(
    no_args_is_help=True,
    help="tcli — CLI для Tinkoff Invest API. Только песочница (SANDBOX).",
)


def _settings() -> Settings:
    return Settings.load()


def _open_sandbox(settings: Settings) -> Sandbox:
    return Sandbox(settings)


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


@app.command()
@_guard
def check() -> None:
    """Самопроверка: .env, сертификат, доступ к API песочницы."""
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
            with _open_sandbox(settings) as sb:
                accounts = sb.accounts()
            names = ", ".join(a.name or a.id for a in accounts) or "нет счетов"
            console.print(f"[4/4] API (песочница): OK, счетов: {len(accounts)} ({names})")
        except Exception as exc:  # noqa: BLE001
            problems += 1
            console.print(f"[4/4] API (песочница): [red]ПРОВАЛ[/red] — {api_error_text(exc)}")
    else:
        console.print("[4/4] API (песочница): пропущен — нет токена")

    if problems:
        console.print(f"[red]check: ПРОВАЛ ({problems})[/red]")
        raise typer.Exit(1)
    console.print("[green]check: OK — всё готово[/green]")


@app.command()
@_guard
def status() -> None:
    """Счета и сводка портфеля песочницы."""
    settings = _settings()
    header_line(settings.masked(), settings.env_path.exists())
    with _open_sandbox(settings) as sb:
        accounts = sb.accounts()
        if not accounts:
            _fail("нет счетов песочницы — откройте счёт в приложении Т-Банка")
        print_accounts([Sandbox.account_row(a) for a in accounts])
        rows = []
        for account in accounts:
            portfolio = sb.portfolio(account.id)
            rows.append(Sandbox.portfolio_row(account.name or account.id, portfolio))
        print_summary(rows)


@app.command()
@_guard
def positions() -> None:
    """Позиции портфеля песочницы."""
    settings = _settings()
    header_line(settings.masked(), settings.env_path.exists())
    with _open_sandbox(settings) as sb:
        account = sb.pick_account()
        portfolio = sb.portfolio(account.id)
        if not portfolio.positions:
            console.print("позиций нет")
            raise typer.Exit(0)
        print_positions([Sandbox.position_row(p) for p in portfolio.positions])


@app.command()
@_guard
def orders() -> None:
    """Активные заявки песочницы."""
    settings = _settings()
    header_line(settings.masked(), settings.env_path.exists())
    with _open_sandbox(settings) as sb:
        account = sb.pick_account()
        active = sb.orders(account.id)
        if not active:
            console.print("активных заявок нет")
            raise typer.Exit(0)
        rows = [Sandbox.order_row(o, sb.ticker(o.figi)) for o in active]
        print_orders(rows, active=True)


@app.command()
@_guard
def payin(amount: float = typer.Argument(..., help="сумма пополнения в рублях")) -> None:
    """Пополнить счёт песочницы."""
    if amount <= 0:
        _fail("сумма должна быть больше 0", code=2)
    settings = _settings()
    header_line(settings.masked(), settings.env_path.exists())
    with _open_sandbox(settings) as sb:
        account = sb.pick_account()
        sb.payin(account.id, amount)
        portfolio = sb.portfolio(account.id)
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
