"""Конфигурация tcli: загрузка .env, токен, маскировка."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

# Корень проекта: <project>/tcli/config.py -> <project>
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
CERT_PATH = PROJECT_ROOT / "certs" / "russian-trusted-root.pem"


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
    sandbox_account_name: str = ""
    env_path: Path = field(default_factory=lambda: ENV_PATH)

    @classmethod
    def load(cls, env_path: Optional[Path] = None) -> Settings:
        path = env_path or ENV_PATH
        values = dotenv_values(path) if path.exists() else {}
        token = (values.get("INVEST_TOKEN") or "").strip() or (
            values.get("INVEST_SANDBOX_TOKEN") or ""
        ).strip()
        return cls(
            invest_token=token,
            sandbox_account_name=(values.get("SANDBOX_ACCOUNT_NAME") or "").strip(),
            env_path=path,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.invest_token)

    def masked(self) -> str:
        return mask_token(self.invest_token)
