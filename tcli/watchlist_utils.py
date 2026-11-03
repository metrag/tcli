"""Утилиты для работы с watchlist (избранные инструменты)."""

from __future__ import annotations

import json
from pathlib import Path

# Директория для хранения данных tcli
TCLI_DATA_DIR = Path.home() / ".tcli"
WATCHLIST_PATH = TCLI_DATA_DIR / "watchlist.json"


def ensure_data_dir() -> None:
    """Создать директорию ~/.tcli если её нет."""
    TCLI_DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_watchlist() -> list[str]:
    """Загрузить список тикеров из watchlist.json."""
    if not WATCHLIST_PATH.exists():
        return []
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return list(data.get("tickers", []))
    except (json.JSONDecodeError, KeyError):
        return []


def save_watchlist(tickers: list[str]) -> None:
    """Сохранить список тикеров в watchlist.json."""
    ensure_data_dir()
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump({"tickers": sorted(set(tickers))}, f, indent=2, ensure_ascii=False)


def add_to_watchlist(ticker: str) -> bool:
    """Добавить тикер в watchlist. Возвращает True если добавлен, False если уже был."""
    tickers = load_watchlist()
    if ticker.upper() in [t.upper() for t in tickers]:
        return False
    tickers.append(ticker.upper())
    save_watchlist(tickers)
    return True


def remove_from_watchlist(ticker: str) -> bool:
    """Удалить тикер из watchlist. Возвращает True если удалён, False если не найден."""
    tickers = load_watchlist()
    ticker_upper = ticker.upper()
    filtered = [t for t in tickers if t.upper() != ticker_upper]
    if len(filtered) == len(tickers):
        return False
    save_watchlist(filtered)
    return True


def clear_watchlist() -> None:
    """Очистить watchlist."""
    save_watchlist([])
