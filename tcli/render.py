"""Рендер таблиц и чисел через rich."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from rich.console import Console
from rich.table import Table

console = Console()


def money_to_float(value: Any) -> float:
    """MoneyValue/Quotation (units+nano) -> float. None -> 0.0."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    units = getattr(value, "units", 0) or 0
    nano = getattr(value, "nano", 0) or 0
    return float(units) + float(nano) / 1e9


def fmt_money(value: Any, currency: str = "₽") -> str:
    num = money_to_float(value)
    sign = "-" if num < 0 else ""
    body = f"{abs(num):,.2f}".replace(",", " ").replace(".00", "")
    # убираем дробную часть, если она нулевая; иначе оставляем 2 знака
    if "." in body and body.endswith(".00"):
        body = body[:-3]
    elif "." in body:
        frac = body.split(".")[1]
        if len(frac) > 2:
            body = body.split(".")[0] + "." + frac[:2]
    return f"{sign}{body} {currency}"


def fmt_qty(value: Any) -> str:
    num = money_to_float(value)
    if num == int(num):
        return str(int(num))
    return f"{num:.4f}".rstrip("0").rstrip(".")


def fmt_pct(value: Any) -> str:
    num = money_to_float(value)
    return f"{num:+.2f}%"


def header_line(masked_token: str, env_exists: bool) -> None:
    console.print(f"[bold]tcli[/bold] · контур [yellow]SANDBOX[/yellow] · токен {masked_token}")
    if not env_exists:
        console.print("[red].env не найден[/red]")


def print_accounts(rows: Iterable[dict]) -> None:
    table = Table(title="Счета (песочница)", show_lines=False)
    table.add_column("Имя")
    table.add_column("ID")
    table.add_column("Тип")
    table.add_column("Статус")
    for row in rows:
        table.add_row(
            str(row.get("name", "")),
            str(row.get("id", "")),
            str(row.get("type", "")),
            str(row.get("status", "")),
        )
    console.print(table)


def print_summary(rows: Iterable[dict]) -> None:
    table = Table(title="Портфель (песочница)")
    table.add_column("Счёт")
    table.add_column("Деньги", justify="right")
    table.add_column("Бумаги", justify="right")
    table.add_column("Итого", justify="right")
    table.add_column("P&L", justify="right")
    for row in rows:
        table.add_row(
            str(row.get("account", "")),
            fmt_money(row.get("cash")),
            fmt_money(row.get("securities")),
            fmt_money(row.get("total")),
            fmt_money(row.get("pnl")),
        )
    console.print(table)


def print_positions(rows: Iterable[dict]) -> None:
    table = Table(title="Позиции")
    table.add_column("Тикер")
    table.add_column("Тип")
    table.add_column("Кол-во", justify="right")
    table.add_column("Средняя", justify="right")
    table.add_column("Текущая", justify="right")
    table.add_column("Стоимость", justify="right")
    table.add_column("P&L", justify="right")
    for row in rows:
        table.add_row(
            str(row.get("ticker", "")),
            str(row.get("type", "")),
            fmt_qty(row.get("quantity")),
            fmt_money(row.get("avg")),
            fmt_money(row.get("current")),
            fmt_money(row.get("value")),
            fmt_money(row.get("pnl")),
        )
    console.print(table)


def print_orders(rows: Iterable[dict], active: bool = True) -> None:
    title = "Активные заявки" if active else "Заявки"
    table = Table(title=title)
    table.add_column("Тикер")
    table.add_column("Направление")
    table.add_column("Статус")
    table.add_column("Лоты", justify="right")
    table.add_column("Цена", justify="right")
    table.add_column("ID")
    for row in rows:
        table.add_row(
            str(row.get("ticker", "")),
            str(row.get("direction", "")),
            str(row.get("status", "")),
            str(row.get("lots", "")),
            fmt_money(row.get("price")),
            str(row.get("order_id", ""))[:16],
        )
    console.print(table)


def print_kv(pairs: Iterable[tuple[str, Optional[str]]]) -> None:
    for key, value in pairs:
        console.print(f"  [dim]{key}:[/dim] {value}")
