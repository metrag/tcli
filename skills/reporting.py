"""skills/reporting.py — Модуль 4: Отчётность и дневник (TODO.md #36).

Функции для анализа P&L, экспорта сделок и комиссий.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import Broker, get_accounts


def get_pnl(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    by_day: bool = False,
    by_ticker: bool = False,
    winrate: bool = False,
) -> dict[str, Any]:
    """Round-trip P&L за период (#36 из TODO.md).

    Args:
        from_date: Начальная дата (по умолчанию 30 дней назад)
        to_date: Конечная дата (по умолчанию сейчас)
        by_day: Группировать по дням
        by_ticker: Группировать по тикерам
        winrate: Рассчитать процент выигрышных сделок

    Returns:
        Словарь с P&L статистикой:
        {
            "period": {"from": "...", "to": "..."},
            "total_pnl": float,
            "total_pnl_pct": float,
            "trades_count": int,
            "winners": int,
            "losers": int,
            "winrate": float (если winrate=True),
            "by_day": {...} (если by_day=True),
            "by_ticker": {...} (если by_ticker=True)
        }
    """
    now = datetime.now(timezone.utc)
    if to_date is None:
        to_date = now
    if from_date is None:
        from_date = now - timedelta(days=30)

    broker = Broker()
    accounts = get_accounts()

    if not accounts:
        return {
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "total_pnl": 0.0,
            "total_pnl_pct": 0.0,
            "trades_count": 0,
            "error": "No accounts found",
        }

    account_id = accounts[0]["id"]

    # Получаем операции за период
    operations = broker.operations(
        account_id=account_id,
        from_=from_date,
        to=to_date,
    )

    # Фильтруем только исполненные сделки
    trades = [op for op in operations if op.get("status") == "EXECUTED"]

    # Рассчитываем P&L
    total_pnl = 0.0
    winners = 0
    losers = 0
    ticker_pnl: dict[str, float] = {}
    day_pnl: dict[str, float] = {}

    for trade in trades:
        pnl = float(trade.get("pnl", 0.0))
        total_pnl += pnl

        ticker = trade.get("ticker", "UNKNOWN")
        trade_date = trade.get("date", "")[:10]  # YYYY-MM-DD

        if pnl > 0:
            winners += 1
        elif pnl < 0:
            losers += 1

        if by_ticker:
            ticker_pnl[ticker] = ticker_pnl.get(ticker, 0.0) + pnl

        if by_day:
            day_pnl[trade_date] = day_pnl.get(trade_date, 0.0) + pnl

    # Рассчитываем процент P&L
    # Для упрощения используем баланс счёта как базу
    portfolio = broker.portfolio(account_id)
    total_balance = float(portfolio.get("total_amount", 1.0))
    total_pnl_pct = (total_pnl / total_balance * 100) if total_balance > 0 else 0.0

    result = {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "trades_count": len(trades),
        "winners": winners,
        "losers": losers,
    }

    if winrate and (winners + losers) > 0:
        result["winrate"] = winners / (winners + losers) * 100

    if by_day:
        result["by_day"] = dict(sorted(day_pnl.items()))

    if by_ticker:
        result["by_ticker"] = dict(sorted(ticker_pnl.items(), key=lambda x: x[1], reverse=True))

    return result


def export_pnl(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    format: str = "json",
    output_file: str | None = None,
) -> str:
    """Экспорт P&L в файл (#37 из TODO.md).

    Args:
        from_date: Начальная дата
        to_date: Конечная дата
        format: Формат экспорта ("json" или "csv")
        output_file: Путь к файлу (по умолчанию pnl_export_<timestamp>.<format>)

    Returns:
        Путь к созданному файлу
    """
    import csv
    import json
    from pathlib import Path

    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"pnl_export_{timestamp}.{format}"

    # Получаем P&L данные
    pnl_data = get_pnl(from_date=from_date, to_date=to_date, by_day=True, by_ticker=True)

    output_path = Path(output_file)

    if format == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(pnl_data, f, indent=2, ensure_ascii=False)
    elif format == "csv":
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Заголовок
            writer.writerow(["Метрика", "Значение"])
            writer.writerow(["Период с", pnl_data["period"]["from"]])
            writer.writerow(["Период по", pnl_data["period"]["to"]])
            writer.writerow(["Общий P&L", pnl_data["total_pnl"]])
            writer.writerow(["Общий P&L %", pnl_data["total_pnl_pct"]])
            writer.writerow(["Количество сделок", pnl_data["trades_count"]])
            writer.writerow(["Выигрышных", pnl_data["winners"]])
            writer.writerow(["Проигрышных", pnl_data["losers"]])

            if "winrate" in pnl_data:
                writer.writerow(["Winrate %", pnl_data["winrate"]])

            # P&L по дням
            if "by_day" in pnl_data:
                writer.writerow([])
                writer.writerow(["Дата", "P&L"])
                for date, pnl in pnl_data["by_day"].items():
                    writer.writerow([date, pnl])

            # P&L по тикерам
            if "by_ticker" in pnl_data:
                writer.writerow([])
                writer.writerow(["Тикер", "P&L"])
                for ticker, pnl in pnl_data["by_ticker"].items():
                    writer.writerow([ticker, pnl])
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'json' or 'csv'")

    return str(output_path)


def get_fees(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict[str, Any]:
    """Отчёт по комиссиям за период (#38 из TODO.md).

    Args:
        from_date: Начальная дата
        to_date: Конечная дата

    Returns:
        Словарь с информацией о комиссиях:
        {
            "period": {"from": "...", "to": "..."},
            "total_fees": float,
            "fees_by_currency": {"RUB": 100.0, "USD": 5.0},
            "operations_count": int
        }
    """
    now = datetime.now(timezone.utc)
    if to_date is None:
        to_date = now
    if from_date is None:
        from_date = now - timedelta(days=30)

    broker = Broker()
    accounts = get_accounts()

    if not accounts:
        return {
            "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
            "total_fees": 0.0,
            "fees_by_currency": {},
            "operations_count": 0,
            "error": "No accounts found",
        }

    account_id = accounts[0]["id"]

    # Получаем операции за период
    operations = broker.operations(
        account_id=account_id,
        from_=from_date,
        to=to_date,
    )

    # Фильтруем только операции с комиссиями
    fee_operations = [
        op for op in operations
        if op.get("operation_type") in ["BROKER_FEE", "SERVICE_FEE", "COMMISSION"]
    ]

    total_fees = 0.0
    fees_by_currency: dict[str, float] = {}

    for fee_op in fee_operations:
        fee_amount = float(fee_op.get("payment", 0.0))
        currency = fee_op.get("currency", "RUB")

        total_fees += abs(fee_amount)  # Комиссии обычно отрицательные
        fees_by_currency[currency] = fees_by_currency.get(currency, 0.0) + abs(fee_amount)

    return {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "total_fees": total_fees,
        "fees_by_currency": dict(sorted(fees_by_currency.items())),
        "operations_count": len(fee_operations),
    }


__all__ = ["get_pnl", "export_pnl", "get_fees"]
