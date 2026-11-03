"""Корневой сертификат НУЦ Минцифры для gRPC-канала Tinkoff Invest API.

Контуры Tinkoff используют цепочку, подписанную Russian Trusted Root CA
(ГУ «НУЦ Минцифры России»), которой нет в стандартном Mozilla-хранилище.
Без подкладки сертификата gRPC падает с CERTIFICATE_VERIFY_FAILED.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .config import CERT_PATH

ENV_VAR = "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"


def ensure_ssl(cert_path: Optional[Path] = None) -> Optional[Path]:
    """Подложить путь к корневому сертификату в переменную окружения gRPC.

    Вызывать ДО создания gRPC-канала (до импорта/инициализации клиента SDK).
    Существующее значение переменной не затирается.
    """
    path = cert_path or CERT_PATH
    if not path.exists():
        return None
    os.environ.setdefault(ENV_VAR, str(path))
    return path


def cert_status(cert_path: Optional[Path] = None) -> dict:
    """Статус файла сертификата для команды check."""
    path = cert_path or CERT_PATH
    return {
        "path": str(path),
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
    }
