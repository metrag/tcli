"""Конфигурация tcli: загрузка .env, токен, маскировка, контуры."""

from __future__ import annotations

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


class TokenMode(str, Enum):
    MAIN = "main"
    SANDBOX = "sandbox"


def mask_token(token: str) -> str:
    """abcd***wxyz — первые 4 и последние 4 символа, середина скрыта."""
    if not token:
        return "<пусто>"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}***{token[-4:]}"


@dataclass
class Settings:
    invest_token: str = ""
    sandbox_token: str = ""
    sandbox_account_name: str = ""
    contour: Contour = Contour.SANDBOX
    token_mode: TokenMode = TokenMode.MAIN
    env_path: Path = field(default_factory=lambda: ENV_PATH)

    @classmethod
    def load(cls, env_path: Optional[Path] = None) -> Settings:
        path = env_path or ENV_PATH
        values = dotenv_values(path) if path.exists() else {}
        main_token = (values.get("INVEST_TOKEN") or "").strip()
        sandbox_token = (values.get("INVEST_SANDBOX_TOKEN") or "").strip()
        
        contour_str = (values.get("TCLI_CONTOUR") or "SANDBOX").strip().upper()
        contour = Contour(contour_str) if contour_str in ("SANDBOX", "LIVE") else Contour.SANDBOX
        
        token_mode_str = (values.get("TCLI_TOKEN") or "main").strip().lower()
        token_mode = TokenMode(token_mode_str) if token_mode_str in ("main", "sandbox") else TokenMode.MAIN
        
        # Активный токен: зависит от режима
        active_token = sandbox_token if token_mode == TokenMode.SANDBOX else main_token
        # Фолбэк: если основной пуст, берём sandbox (и наоборот)
        if not active_token:
            active_token = main_token or sandbox_token
        
        return cls(
            invest_token=active_token,
            sandbox_token=sandbox_token,
            sandbox_account_name=(values.get("SANDBOX_ACCOUNT_NAME") or "").strip(),
            contour=contour,
            token_mode=token_mode,
            env_path=path,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.invest_token)

    def masked(self) -> str:
        return mask_token(self.invest_token)

    def contour_label(self) -> str:
        return self.contour.value

    def token_mode_label(self) -> str:
        return self.token_mode.value


def set_env_value(key: str, value: str, env_path: Optional[Path] = None) -> None:
    """Записать/обновить значение в .env (создаёт файл, если отсутствует)."""
    path = env_path or ENV_PATH
    if not path.exists():
        path.touch()
    set_key(str(path), key, value)
