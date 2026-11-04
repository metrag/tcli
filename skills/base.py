"""Базовый модуль для выполнения команд tcli."""

import json
import subprocess
from typing import Any


class TcliError(Exception):
    """Ошибка выполнения команды tcli."""
    
    def __init__(self, message: str, exit_code: int):
        self.message = message
        self.exit_code = exit_code
        super().__init__(f"tcli error (code {exit_code}): {message}")


def run_tcli_command(args: list[str], check: bool = True) -> dict[str, Any]:
    """Выполнить команду tcli и вернуть JSON результат.
    
    Args:
        args: Аргументы команды (например, ['quote', 'SBER'])
        check: Если True, выбрасывает исключение при ошибке
        
    Returns:
        Словарь с результатом команды
        
    Raises:
        TcliError: Если команда завершилась с ошибкой и check=True
    """
    # Всегда используем --json для структурированного вывода
    # Всегда используем --no-prompt для неинтерактивного режима
    cmd = ["tcli"] + args + ["--json", "--no-prompt"]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,  # Таймаут 30 секунд
            cwd="/home/metra/AlgoTreid/tcli"
        )
        
        # Парсим JSON из stdout
        if result.stdout:
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                if check:
                    raise TcliError(f"Failed to parse JSON: {e}", result.returncode) from e
                return {"error": f"JSON parse error: {e}", "raw": result.stdout}
            
            # Проверяем exit code
            if result.returncode != 0 and check:
                error_msg = data.get("error", "Unknown error")
                raise TcliError(error_msg, result.returncode)
            
            return data
        else:
            # Если stdout пустой, возвращаем пустой словарь или ошибку
            if result.returncode != 0 and check:
                raise TcliError(result.stderr or "Command failed", result.returncode)
            return {}
            
    except subprocess.TimeoutExpired:
        if check:
            raise TcliError("Command timeout (30s)", -1) from None
        return {"error": "timeout"}
    except Exception as e:
        if check:
            raise TcliError(str(e), -1) from e
        return {"error": str(e)}
