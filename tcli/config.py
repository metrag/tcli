"""Конфигурация tcli: загрузка .env, токены, контуры."""

from __future__ import annotations

import logging as _logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

# Корень проекта: <project>/tcli/config.py -> <project>
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
CERT_PATH = PROJECT_ROOT / "certs" / "russian-trusted-root.pem"


class Contour(str, Enum):
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"


# Подавляем шумный лог SDK (request_id в выводе ошибок) — #5.
# При TCLI_DEBUG=1 сообщения SDK сохраняются в stderr.
_sdk_log = _logging.getLogger("tinkoff")
if os.environ.get("TCLI_DEBUG"):
    _sdk_log.setLevel(_logging.ERROR)
else:
    _sdk_log.setLevel(_logging.CRITICAL)


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
    sandbox_account_name: str = ""  # Deprecated, для обратной совместимости
    live_account_name: str = ""  # Для боевого контура
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

        # Читаем имена аккаунтов с fallback для обратной совместимости
        live_account_name = _get("LIVE_ACCOUNT_NAME") or _get("SANDBOX_ACCOUNT_NAME")
        sandbox_account_name = _get("SANDBOX_ACCOUNT_NAME")

        return cls(
            sandbox_token=sandbox_token,
            main_token=main_token,
            sandbox_account_name=sandbox_account_name,
            live_account_name=live_account_name,
            contour=contour,
            env_path=path,
        )

    @property
    def account_name(self) -> str:
        """Имя аккаунта в зависимости от контура."""
        if self.contour == Contour.LIVE:
            return self.live_account_name
        else:
            return self.sandbox_account_name

    @property
    def account_name_key(self) -> str:
        """Ключ для записи в .env в зависимости от контура."""
        return "LIVE_ACCOUNT_NAME" if self.contour == Contour.LIVE else "SANDBOX_ACCOUNT_NAME"

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
    """Записать/обновить значение в .env (создаёт файл, если отсутствует).
    
    Атомарная операция с flock для защиты от параллельных записей.
    """
    import fcntl
    import tempfile
    
    path = env_path or ENV_PATH
    lock_path = path.with_suffix('.lock')
    
    # Создаём lock файл
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, 'w') as lock_file:
        try:
            # Захватываем эксклюзивную блокировку
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            
            # Читаем текущее содержимое
            lines = []
            if path.exists():
                with open(path) as f:
                    lines = f.readlines()
            
            # Обновляем или добавляем ключ
            found = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(f'{key}=') or stripped.startswith(f'export {key}='):
                    # Сохраняем комментарий, если есть
                    if '=' in line:
                        comment_part = ''
                        if '#' in line:
                            comment_idx = line.index('#')
                            eq_idx = line.index('=')
                            if comment_idx > eq_idx:
                                comment_part = ' ' + line[comment_idx:]
                        lines[i] = f'{key}={value}{comment_part}\n'
                        found = True
                    break
            
            if not found:
                # Добавляем новую строку
                if lines and not lines[-1].endswith('\n'):
                    lines[-1] += '\n'
                lines.append(f'{key}={value}\n')
            
            # Записываем во временный файл в той же директории
            with tempfile.NamedTemporaryFile(
                mode='w', 
                dir=path.parent, 
                delete=False, 
                suffix='.tmp'
            ) as tmp:
                tmp.writelines(lines)
                tmp_path = Path(tmp.name)
            
            # Атомарная замена
            os.replace(tmp_path, path)

            # Права доступа только для владельца (.env содержит секреты)
            path.chmod(0o600)
            
        finally:
            # Блокировка освобождается автоматически при закрытии файла
            pass
    
    # Удаляем lock файл (не критично, если не получится)
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass
