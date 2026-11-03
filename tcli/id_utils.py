"""Утилиты для определения типов идентификаторов инструментов с кэшированием."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

# Директория для хранения кэша
CACHE_DIR = Path.home() / ".tcli"
CACHE_PATH = CACHE_DIR / "id_types.json"


def ensure_cache_dir() -> None:
    """Создать директорию кэша если её нет."""
    if not CACHE_DIR.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_cache() -> dict[str, str]:
    """Загрузить кэш известных типов ID."""
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict[str, str]) -> None:
    """Сохранить кэш известных типов ID."""
    ensure_cache_dir()
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def detect_identifier_type(identifier: str) -> str:
    """Определить тип идентификатора по формату.
    
    Returns:
        Один из: 'figi', 'sandbox_figi', 'uid', 'isin', 'ticker'
    """
    identifier = identifier.strip().upper()
    
    # FIGI: начинается с BBG (стандартный Bloomberg ID)
    if identifier.startswith("BBG"):
        return "figi"
    
    # Sandbox FIGI: начинается с TCS и ровно 12 символов (псевдо-FIGI песочницы)
    if identifier.startswith("TCS") and len(identifier) == 12:
        return "sandbox_figi"
    
    # ISIN: 12 символов, но нужно проверить что это действительно ISIN
    # ISIN всегда начинается с 2 букв кода страны (ISO 3166-1 alpha-2)
    # Не является ISIN если начинается с префиксов тикеров (FUT, OPT, SP, и т.д.)
    if len(identifier) == 12 and re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", identifier):
        # Проверяем что это не префикс тикера
        ticker_prefixes = ("FUT", "OPT", "SP", "PS", "ETF", "BOND", "SHARE")
        if not any(identifier.startswith(prefix) for prefix in ticker_prefixes):
            return "isin"
    
    # UID: TCS* длиннее 12 символов или длинные буквенно-цифровые ID (20+)
    if identifier.startswith("TCS") and len(identifier) > 12:
        return "uid"
    if re.match(r"^[A-Z0-9]{20,}$", identifier):
        return "uid"
    
    # По умолчанию: тикер
    return "ticker"


def get_cached_type(identifier: str) -> Optional[str]:
    """Получить тип ID из кэша, если он там есть."""
    cache = load_cache()
    return cache.get(identifier.upper())


def cache_identifier_type(identifier: str, id_type: str) -> None:
    """Сохранить тип ID в кэш."""
    cache = load_cache()
    cache[identifier.upper()] = id_type
    save_cache(cache)


def clear_cache() -> None:
    """Очистить кэш типов ID."""
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()
