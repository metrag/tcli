"""Рендер таблиц и чисел через rich."""

from __future__ import annotations

from typing import Any, Iterable

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


def header_line(masked_token: str, contour: str, env_exists: bool) -> None:
    console.print(f"[bold]tcli[/bold] · контур [yellow]{contour}[/yellow] · токен {masked_token}")
    if not env_exists:
        console.print("[red].env не найден[/red]")


def print_accounts(rows: Iterable[dict], contour: str = "SANDBOX") -> None:
    table = Table(title=f"Счета ({contour})", show_lines=False)
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


def print_summary(rows: Iterable[dict], contour: str = "SANDBOX") -> None:
    table = Table(title=f"Портфель ({contour})")
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


def print_operations(rows: Iterable[dict]) -> None:
    table = Table(title="Операции")
    table.add_column("Дата")
    table.add_column("Тип")
    table.add_column("Тикер")
    table.add_column("Кол-во", justify="right")
    table.add_column("Цена", justify="right")
    table.add_column("Сумма", justify="right")
    table.add_column("Валюта")
    for row in rows:
        date_str = ""
        if row.get("date"):
            date_str = str(row["date"])[:10]  # обрезаем до даты
        table.add_row(
            date_str,
            str(row.get("type", "")),
            str(row.get("ticker", "")),
            str(row.get("quantity", "")),
            fmt_money(row.get("price")),
            fmt_money(row.get("amount")),
            str(row.get("currency", "")),
        )
    console.print(table)


def print_candles(rows: Iterable[dict], ticker: str, interval: str) -> None:
    table = Table(title=f"Свечи {ticker} ({interval})")
    table.add_column("Время")
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Close", justify="right")
    table.add_column("Volume", justify="right")
    for row in rows:
        time_str = ""
        if row.get("time"):
            time_str = str(row["time"])[:16]
        table.add_row(
            time_str,
            fmt_money(row.get("open")),
            fmt_money(row.get("high")),
            fmt_money(row.get("low")),
            fmt_money(row.get("close")),
            str(row.get("volume", "")),
        )
    console.print(table)


def print_instruments(rows: Iterable[dict], query: str) -> None:
    table = Table(title=f"Инструменты (поиск: {query})")
    table.add_column("Тикер")
    table.add_column("FIGI")
    table.add_column("Название")
    table.add_column("Тип")
    table.add_column("Класс")
    for row in rows:
        table.add_row(
            str(row.get("ticker", "")),
            str(row.get("figi", "")),
            str(row.get("name", "")),
            str(row.get("type", "")),
            str(row.get("class", "")),
        )
    console.print(table)
