"""Конфигурация tcli: загрузка .env, токены, контуры."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, set_key

# Корень проекта: <project>/tcli/config.py -> <project>
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
CERT_PATH = PROJECT_ROOT / "certs" / "russian-trusted-root.pem"


class Contour(str, Enum):
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"


def mask_token(token: str) -> str:
    """abcd***wxyz — первые 4 и последние 4 символа, середина скрыта."""
    if not token:
        return "<пусто>"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}***{token[-4:]}"


@dataclass
class Settings:
    sandbox_token: str = ""  # Для песочницы
    main_token: str = ""  # Для боевого контура
    sandbox_account_name: str = ""
    account_override: str = ""  # Глобальный флаг --account (#27)
    contour: Contour = Contour.SANDBOX
    env_path: Path = field(default_factory=lambda: ENV_PATH)

    @classmethod
    def load(cls, env_path: Optional[Path] = None) -> Settings:
        path = env_path or ENV_PATH
        values = dotenv_values(path) if path.exists() else {}

        # Fallback на переменные окружения: env > файл
        def _get(key: str) -> str:
            return (os.environ.get(key) or values.get(key) or "").strip()

        sandbox_token = _get("INVEST_SANDBOX_TOKEN")
        main_token = _get("INVEST_TOKEN")

        contour_str = _get("TCLI_CONTOUR") or "SANDBOX"
        contour = Contour(contour_str) if contour_str in ("SANDBOX", "LIVE") else Contour.SANDBOX

        return cls(
            sandbox_token=sandbox_token,
            main_token=main_token,
            sandbox_account_name=_get("SANDBOX_ACCOUNT_NAME"),
            contour=contour,
            env_path=path,
        )

    @property
    def token(self) -> str:
        """Активный токен в зависимости от контура."""
        return self.sandbox_token if self.contour == Contour.SANDBOX else self.main_token

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def masked(self) -> str:
        return mask_token(self.token)

    def contour_label(self) -> str:
        return self.contour.value


def set_env_value(key: str, value: str, env_path: Optional[Path] = None) -> None:
    """Записать/обновить значение в .env (создаёт файл, если отсутствует)."""
    path = env_path or ENV_PATH
    if not path.exists():
        path.touch()
    set_key(str(path), key, value)
