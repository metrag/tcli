"""Тесты для модуля навыков торгового агента."""

import json
from unittest.mock import MagicMock, patch

import pytest

from skills.base import run_tcli_command, TcliError


class TestRunTcliCommand:
    """Тесты для функции run_tcli_command."""

    @patch("skills.base.subprocess.run")
    def test_successful_command(self, mock_run):
        """Тест успешного выполнения команды."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"status": "ok", "data": "test"}',
            stderr=""
        )
        
        result = run_tcli_command(["quote", "SBER"])
        
        assert result == {"status": "ok", "data": "test"}
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "tcli" in call_args
        assert "quote" in call_args
        assert "SBER" in call_args
        assert "--json" in call_args
        assert "--no-prompt" in call_args

    @patch("skills.base.subprocess.run")
    def test_command_with_error(self, mock_run):
        """Тест команды с ошибкой."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='{"error": "Instrument not found"}',
            stderr=""
        )
        
        with pytest.raises(TcliError) as exc_info:
            run_tcli_command(["quote", "INVALID"])
        
        assert "Instrument not found" in str(exc_info.value)
        assert exc_info.value.exit_code == -1

    @patch("skills.base.subprocess.run")
    def test_command_without_check(self, mock_run):
        """Тест команды с check=False."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='{"error": "Some error"}',
            stderr=""
        )
        
        result = run_tcli_command(["quote", "INVALID"], check=False)
        
        assert result == {"error": "Some error"}

    @patch("skills.base.subprocess.run")
    def test_timeout_error(self, mock_run):
        """Тест таймаута команды."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tcli", timeout=30)
        
        with pytest.raises(TcliError) as exc_info:
            run_tcli_command(["quote", "SBER"])
        
        assert "timeout" in str(exc_info.value).lower()

    @patch("skills.base.subprocess.run")
    def test_json_decode_error(self, mock_run):
        """Тест ошибки парсинга JSON."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='invalid json',
            stderr=""
        )
        
        with pytest.raises(TcliError) as exc_info:
            run_tcli_command(["quote", "SBER"])
        
        assert "parse" in str(exc_info.value).lower()

    @patch("skills.base.subprocess.run")
    def test_empty_stdout(self, mock_run):
        """Тест команды с пустым stdout."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )
        
        result = run_tcli_command(["positions"])
        
        assert result == {}


class TestMarketData:
    """Тесты для модуля market_data."""

    @patch("skills.market_data.run_tcli_command")
    def test_get_quote(self, mock_run):
        """Тест функции get_quote."""
        mock_run.return_value = {
            "ticker": "SBER",
            "price": "285.50",
            "figi": "BBG004730N88"
        }
        
        from skills.market_data import get_quote
        result = get_quote("SBER")
        
        assert result["ticker"] == "SBER"
        assert result["price"] == "285.50"
        mock_run.assert_called_once_with(["quote", "SBER"])

    @patch("skills.market_data.run_tcli_command")
    def test_get_candles(self, mock_run):
        """Тест функции get_candles."""
        mock_run.return_value = {
            "ticker": "SBER",
            "interval": "1day",
            "candles": [
                {"open": "280.0", "close": "285.0", "high": "286.0", "low": "279.0", "volume": 1000000}
            ]
        }
        
        from skills.market_data import get_candles
        result = get_candles("SBER", interval="1day", days=7)
        
        assert result["ticker"] == "SBER"
        assert len(result["candles"]) == 1
        mock_run.assert_called_once_with(["candles", "SBER", "--interval", "1day", "--days", "7"])

    @patch("skills.market_data.run_tcli_command")
    def test_get_portfolio(self, mock_run):
        """Тест функции get_portfolio."""
        mock_run.return_value = {
            "positions": [
                {"ticker": "SBER", "quantity": 100, "average_price": "280.0"}
            ]
        }
        
        from skills.market_data import get_portfolio
        result = get_portfolio()
        
        assert len(result["positions"]) == 1
        assert result["positions"][0]["ticker"] == "SBER"
        mock_run.assert_called_once_with(["positions"])

    @patch("skills.market_data.run_tcli_command")
    def test_get_orders(self, mock_run):
        """Тест функции get_orders."""
        mock_run.return_value = {
            "orders": [
                {"order_id": "12345", "ticker": "SBER", "quantity": 10}
            ]
        }
        
        from skills.market_data import get_orders
        result = get_orders()
        
        assert len(result["orders"]) == 1
        assert result["orders"][0]["order_id"] == "12345"
        mock_run.assert_called_once_with(["orders"])


class TestTrading:
    """Тесты для модуля trading."""

    @patch("skills.trading.run_tcli_command")
    def test_place_order(self, mock_run):
        """Тест функции place_order."""
        mock_run.return_value = {
            "order_id": "12345",
            "status": "ok",
            "message": "Order placed"
        }
        
        from skills.trading import place_order
        result = place_order("SBER", "buy", 10, price=285.5)
        
        assert result["order_id"] == "12345"
        mock_run.assert_called_once_with(["order-buy", "SBER", "--quantity", "10", "--no-prompt", "--json", "--price", "285.5"])

    @patch("skills.trading.run_tcli_command")
    def test_place_market_order(self, mock_run):
        """Тест рыночной заявки."""
        mock_run.return_value = {"order_id": "12345", "status": "ok"}
        
        from skills.trading import place_order
        place_order("SBER", "sell", 5)
        
        mock_run.assert_called_once_with(["order-sell", "SBER", "--quantity", "5", "--no-prompt", "--json"])

    @patch("skills.trading.run_tcli_command")
    def test_cancel_order(self, mock_run):
        """Тест функции cancel_order."""
        mock_run.return_value = {
            "order_id": "12345",
            "status": "cancelled"
        }
        
        from skills.trading import cancel_order
        result = cancel_order("12345")
        
        assert result["status"] == "cancelled"
        mock_run.assert_called_once_with(["order-cancel", "12345", "--no-prompt", "--json"])


class TestAccount:
    """Тесты для модуля account."""

    @patch("skills.account.run_tcli_command")
    def test_get_accounts(self, mock_run):
        """Тест функции get_accounts."""
        mock_run.return_value = {
            "accounts": [
                {"account_id": "123", "name": "Main", "type": "Tinkoff"}
            ]
        }
        
        from skills.account import get_accounts
        result = get_accounts()
        
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["account_id"] == "123"
        mock_run.assert_called_once_with(["account-list", "--json"])

    @patch("skills.account.run_tcli_command")
    def test_select_account(self, mock_run):
        """Тест функции select_account."""
        mock_run.return_value = {
            "status": "ok",
            "account_id": "123"
        }
        
        from skills.account import select_account
        result = select_account("123")
        
        assert result["status"] == "ok"
        mock_run.assert_called_once_with("account-select 123")


class TestAnalytics:
    """Тесты для модуля analytics."""

    @patch("skills.analytics.run_tcli_command")
    def test_search_instruments(self, mock_run):
        """Тест функции search_instruments."""
        mock_run.return_value = {
            "instruments": [
                {"ticker": "SBER", "name": "Sberbank", "figi": "BBG004730N88"}
            ]
        }
        
        from skills.analytics import search_instruments
        result = search_instruments("SBER")
        
        assert len(result["instruments"]) == 1
        assert result["instruments"][0]["ticker"] == "SBER"
        mock_run.assert_called_once_with(["find", "SBER", "--json"])

    @patch("skills.analytics.run_tcli_command")
    def test_get_instrument_info(self, mock_run):
        """Тест функции get_instrument_info."""
        mock_run.return_value = {
            "ticker": "SBER",
            "name": "Sberbank",
            "figi": "BBG004730N88",
            "lot": 10,
            "currency": "RUB"
        }
        
        from skills.analytics import get_instrument_info
        result = get_instrument_info("SBER")
        
        assert result["ticker"] == "SBER"
        assert result["lot"] == 10
        mock_run.assert_called_once_with(["info", "SBER", "--json"])

    @patch("skills.analytics.run_tcli_command")
    def test_watchlist_operations(self, mock_run):
        """Тест операций с watchlist."""
        mock_run.return_value = {"status": "ok"}
        
        from skills.analytics import add_to_watchlist, remove_from_watchlist
        
        add_to_watchlist("SBER")
        mock_run.assert_called_with("watchlist add SBER")
        
        remove_from_watchlist("SBER")
        mock_run.assert_called_with("watchlist remove SBER")
