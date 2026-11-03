"""Тесты для новых функций: export, watchlist, info, account-select."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from tcli.cli import app
from tcli.config import Contour, Settings
from tcli.watchlist_utils import (
    add_to_watchlist,
    clear_watchlist,
    load_watchlist,
    remove_from_watchlist,
)

runner = CliRunner()


# --- Watchlist utils tests ---


def test_watchlist_add_and_load(tmp_path, monkeypatch):
    """Тест добавления и загрузки watchlist."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    # Добавляем тикеры
    assert add_to_watchlist("SBER") is True
    assert add_to_watchlist("GAZP") is True
    assert add_to_watchlist("sber") is False  # дубликат (без учёта регистра)
    
    # Загружаем
    tickers = load_watchlist()
    assert "SBER" in tickers
    assert "GAZP" in tickers
    assert len(tickers) == 2


def test_watchlist_remove(tmp_path, monkeypatch):
    """Тест удаления из watchlist."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    add_to_watchlist("SBER")
    add_to_watchlist("GAZP")
    
    assert remove_from_watchlist("SBER") is True
    assert remove_from_watchlist("YNDX") is False  # не существует
    
    tickers = load_watchlist()
    assert "SBER" not in tickers
    assert "GAZP" in tickers


def test_watchlist_clear(tmp_path, monkeypatch):
    """Тест очистки watchlist."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    add_to_watchlist("SBER")
    add_to_watchlist("GAZP")
    clear_watchlist()
    
    tickers = load_watchlist()
    assert len(tickers) == 0


def test_watchlist_empty_file(tmp_path, monkeypatch):
    """Тест загрузки из несуществующего файла."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    tickers = load_watchlist()
    assert tickers == []


# --- CLI commands tests ---


def test_watchlist_cli_empty(tmp_path, monkeypatch):
    """Тест CLI команды watchlist list когда watchlist пуст."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    result = runner.invoke(app, ["watchlist", "list"])
    assert result.exit_code == 0
    assert "watchlist пуст" in result.output


def test_watchlist_cli_add(tmp_path, monkeypatch):
    """Тест CLI команды watchlist add."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    result = runner.invoke(app, ["watchlist", "add", "SBER"])
    assert result.exit_code == 0
    assert "добавлено в watchlist" in result.output
    
    tickers = load_watchlist()
    assert "SBER" in tickers


def test_watchlist_cli_add_duplicate(tmp_path, monkeypatch):
    """Тест CLI команды watchlist add с дубликатом."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    add_to_watchlist("SBER")
    result = runner.invoke(app, ["watchlist", "add", "SBER"])
    assert result.exit_code == 0
    assert "уже в watchlist" in result.output


def test_watchlist_cli_remove(tmp_path, monkeypatch):
    """Тест CLI команды watchlist remove."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    add_to_watchlist("SBER")
    result = runner.invoke(app, ["watchlist", "remove", "SBER"])
    assert result.exit_code == 0
    assert "удалено из watchlist" in result.output
    
    tickers = load_watchlist()
    assert "SBER" not in tickers


def test_watchlist_cli_remove_not_found(tmp_path, monkeypatch):
    """Тест CLI команды watchlist remove для несуществующего тикера."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    result = runner.invoke(app, ["watchlist", "remove", "YNDX"])
    assert result.exit_code == 0
    assert "не найдено в watchlist" in result.output


def test_watchlist_cli_invalid_action(tmp_path, monkeypatch):
    """Тест CLI команды watchlist с неверным действием."""
    test_path = tmp_path / "watchlist.json"
    monkeypatch.setattr("tcli.watchlist_utils.WATCHLIST_PATH", test_path)
    
    result = runner.invoke(app, ["watchlist", "invalid"])
    assert result.exit_code == 2
    assert "неизвестное действие" in result.output


def test_info_command_no_token():
    """Тест команды info без токена."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("")
        
        with patch("tcli.cli._settings") as mock_settings:
            mock_settings.return_value = Settings(
                sandbox_token="",
                main_token="",
                contour=Contour.SANDBOX,
                env_path=env_path,
            )
            
            result = runner.invoke(app, ["info", "SBER"])
            # Должна вернуться ошибка о отсутствующем токене
            assert result.exit_code == 1


def test_export_invalid_data_type():
    """Тест команды export с неверным типом данных."""
    result = runner.invoke(app, ["export", "invalid"])
    assert result.exit_code == 2
    assert "неизвестный тип данных" in result.output


def test_export_invalid_format():
    """Тест команды export с неверным форматом."""
    result = runner.invoke(app, ["export", "positions", "--format", "xml"])
    assert result.exit_code == 2
    assert "неизвестный формат" in result.output


def test_help_includes_new_commands():
    """Тест что help включает новые команды."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "export" in result.output
    assert "watchlist" in result.output
    assert "account-select" in result.output
    assert "info" in result.output
