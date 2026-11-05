"""Рендер таблиц и чисел через rich."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any, Iterable

from rich.console import Console
from rich.table import Table

console = Console()


def log_event(event: str, level: str = "info", **kwargs: Any) -> None:
    """Вывести структурированное событие в JSON формате в stderr.
    
    Args:
        event: Название события (order_placed, account_created, error, etc.)
        level: Уровень логирования (info, warning, error)
        **kwargs: Дополнительные поля для лога
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "event": event,
        **kwargs,
    }
    import json
    print(json.dumps(log_entry, ensure_ascii=False), file=sys.stderr, flush=True)



def money_to_float(value: Any) -> float:
    """MoneyValue/Quotation (units+nano) -> float. None -> 0.0."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    units = getattr(value, "units", 0) or 0
    nano = getattr(value, "nano", 0) or 0
    return float(units) + float(nano) / 1e9


def to_jsonable(value: Any) -> Any:
    """Рекурсивная конвертация protobuf объектов в JSON-совместимые типы."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    # Проверка на MoneyValue/Quotation (есть units и nano)
    if hasattr(value, "units") and hasattr(value, "nano"):
        return money_to_float(value)
    # Проверка на datetime
    if hasattr(value, "isoformat"):
        return value.isoformat()
    # Проверка на enum
    if hasattr(value, "value") and hasattr(value, "name"):
        return value.name if hasattr(value, "name") else str(value)
    # Общий случай: конвертируем в строку
    return str(value)


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


def print_instruments_filtered(rows: Iterable[dict], filters: dict) -> None:
    """Вывод отфильтрованных инструментов с детальной информацией."""
    # Формируем заголовок на основе применённых фильтров
    filter_parts = []
    if filters.get("type"):
        filter_parts.append(f"тип: {filters['type']}")
    if filters.get("price_min") or filters.get("price_max"):
        price_range = []
        if filters.get("price_min"):
            price_range.append(f"от {filters['price_min']}")
        if filters.get("price_max"):
            price_range.append(f"до {filters['price_max']}")
        filter_parts.append(f"цена {' '.join(price_range)}")
    if filters.get("currency"):
        filter_parts.append(f"валюта: {filters['currency']}")
    if filters.get("exchange"):
        filter_parts.append(f"биржа: {filters['exchange']}")
    if filters.get("available"):
        filter_parts.append("доступные")
    
    title = "Инструменты"
    if filter_parts:
        title += f" ({', '.join(filter_parts)})"
    
    table = Table(title=title)
    table.add_column("Тикер", style="cyan")
    table.add_column("FIGI", style="dim")
    table.add_column("Название")
    table.add_column("Тип")
    table.add_column("Лот", justify="right")
    table.add_column("Цена", justify="right", style="green")
    table.add_column("Валюта")
    table.add_column("Мин. шаг", justify="right")
    table.add_column("Биржа")
    
    # Дополнительные колонки для облигаций
    if filters.get("type") == "bond":
        table.add_column("Дата погаш.", style="yellow")
        table.add_column("Номинал", justify="right", style="green")
    
    # Дополнительные колонки для акций
    if filters.get("type") == "share":
        table.add_column("Див. дох.", justify="right", style="green")
    
    for row in rows:
        # Формируем цену с валютой
        price_val = row.get("price")
        currency_val = row.get("currency", "")
        if price_val is not None:
            # Определяем символ валюты
            currency_symbol = "₽" if currency_val.upper() == "RUB" else currency_val
            price_str = f"{price_val:,.2f} {currency_symbol}".replace(",", " ")
        else:
            price_str = "—"
        
        row_data = [
            str(row.get("ticker", "")),
            str(row.get("figi", "")),
            str(row.get("name", "")),
            str(row.get("type", "")),
            str(row.get("lot", "")),
            price_str,
            str(row.get("currency", "")),
            str(row.get("min_price_step", "")),
            str(row.get("exchange", "")),
        ]
        
        # Дополнительные данные для облигаций
        if filters.get("type") == "bond":
            maturity = row.get("maturity_date")
            if maturity:
                maturity_str = str(maturity)[:10] if not isinstance(maturity, str) else maturity[:10]
            else:
                maturity_str = ""
            nominal = row.get("nominal")
            row_data.extend([maturity_str, fmt_money(nominal) if nominal else ""])
        
        # Дополнительные данные для акций
        if filters.get("type") == "share":
            dividend_yield = row.get("dividend_yield")
            if dividend_yield:
                row_data.append(f"{float(dividend_yield):.2f}%")
            else:
                row_data.append("")
        
        table.add_row(*row_data)
    
    console.print(table)

def print_watchlist(rows: Iterable[dict]) -> None:
    """Вывод списка отслеживаемых инструментов с ценами."""
    table = Table(title="Избранное (Watchlist)")
    table.add_column("Тикер", style="cyan")
    table.add_column("FIGI", style="dim")
    table.add_column("Последняя цена", justify="right")
    table.add_column("Изменение", justify="right")
    for row in rows:
        change = row.get("change", 0)
        change_style = "green" if change >= 0 else "red"
        change_str = f"{change:+.2f}%"
        price = row.get("price")
        price_str = fmt_money(price) if price is not None else "недоступно"
        table.add_row(
            str(row.get("ticker", "")),
            str(row.get("figi", "")),
            price_str,
            f"[{change_style}]{change_str}[/{change_style}]",
        )
    console.print(table)


def print_instrument_info(info: dict) -> None:
    """Вывод детальной информации об инструменте."""
    console.print(f"\n[bold cyan]{info.get('name', 'N/A')}[/bold cyan] ({info.get('ticker', 'N/A')})")
    console.print("=" * 60)
    
    rows = [
        ("FIGI", info.get("figi", "N/A")),
        ("ISIN", info.get("isin", "N/A")),
        ("Тип", info.get("type", "N/A")),
        ("Валюта", info.get("currency", "N/A")),
        ("Лотность", str(info.get("lot", "N/A"))),
        ("Биржа", info.get("exchange", "N/A")),
        ("Класс", info.get("class_code", "N/A")),
        ("Статус торгов", info.get("trading_status", "N/A")),
    ]
    
    for label, value in rows:
        console.print(f"  [bold]{label}:[/bold] {value}")
    
    # Добавить текущую цену, если доступна
    price = info.get("price")
    price_currency = info.get("price_currency")
    if price is not None:
        currency_symbol = "₽" if price_currency == "RUB" else price_currency
        console.print(f"  [bold]Текущая цена:[/bold] {price:,.2f} {currency_symbol}".replace(",", " "))
    else:
        console.print("  [bold]Текущая цена:[/bold] [dim]недоступно[/dim]")
    
    console.print()
