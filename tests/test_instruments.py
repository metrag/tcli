"""Тесты для команды instruments с фильтрацией."""

from typer.testing import CliRunner

from tcli.cli import app
from tcli.client import Broker
from tcli.config import Contour, Settings

runner = CliRunner()


def _settings():
    """Создать тестовые настройки."""
    return Settings(
        sandbox_token="test-sandbox-token",
        main_token="test-main-token",
        contour=Contour.SANDBOX,
    )


def _mock_instrument(
    ticker="TEST",
    figi="BBG000000000",
    name="Test Instrument",
    instrument_type="share",
    lot=1,
    currency="RUB",
    min_price_increment=0.01,
    exchange="MOEX",
    api_trade_available_flag=True,
    maturity_date=None,
    nominal=None,
    dividend_yield=None,
):
    """Создать мок инструмента."""
    from types import SimpleNamespace

    return SimpleNamespace(
        ticker=ticker,
        figi=figi,
        name=name,
        instrument_type=instrument_type,
        lot=lot,
        currency=currency,
        min_price_increment=min_price_increment,
        exchange=exchange,
        api_trade_available_flag=api_trade_available_flag,
        maturity_date=maturity_date,
        nominal=nominal,
        dividend_yield=dividend_yield,
    )


class TestInstrumentsCommand:
    """Тесты команды instruments."""

    def test_instruments_invalid_type(self, monkeypatch, tmp_path):
        """Тест невалидного типа инструмента."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        result = runner.invoke(app, ["instruments", "--type", "invalid"])

        assert result.exit_code == 2
        assert "неизвестный тип инструмента" in result.stdout

    def test_instruments_no_instruments(self, monkeypatch, tmp_path):
        """Тест когда инструментов нет."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        # Мок брокера с пустым списком
        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return []

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments"])

        assert result.exit_code == 0
        assert "инструменты не найдены" in result.stdout

    def test_instruments_filter_by_type(self, monkeypatch, tmp_path):
        """Тест фильтрации по типу."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER", instrument_type="share"),
            _mock_instrument(ticker="GAZP", instrument_type="share"),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return [i for i in instruments if i.instrument_type == instrument_type]

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--type", "share"])

        assert result.exit_code == 0
        # Должны быть оба инструмента
        assert "SBER" in result.stdout
        assert "GAZP" in result.stdout

    def test_instruments_filter_by_name(self, monkeypatch, tmp_path):
        """Тест фильтрации по названию."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER", name="Сбербанк"),
            _mock_instrument(ticker="GAZP", name="Газпром"),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--name", "Сбер"])

        assert result.exit_code == 0
        assert "SBER" in result.stdout
        assert "GAZP" not in result.stdout

    def test_instruments_filter_by_ticker(self, monkeypatch, tmp_path):
        """Тест фильтрации по тикеру."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER"),
            _mock_instrument(ticker="SBERP"),
            _mock_instrument(ticker="GAZP"),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--ticker", "SBER"])

        assert result.exit_code == 0
        assert "SBER" in result.stdout
        assert "SBERP" in result.stdout
        assert "GAZP" not in result.stdout

    def test_instruments_filter_by_currency(self, monkeypatch, tmp_path):
        """Тест фильтрации по валюте."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER", currency="RUB"),
            _mock_instrument(ticker="AAPL", currency="USD"),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--currency", "RUB"])

        assert result.exit_code == 0
        assert "SBER" in result.stdout
        assert "AAPL" not in result.stdout

    def test_instruments_filter_by_exchange(self, monkeypatch, tmp_path):
        """Тест фильтрации по бирже."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER", exchange="MOEX"),
            _mock_instrument(ticker="AAPL", exchange="SPB"),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--exchange", "MOEX"])

        assert result.exit_code == 0
        assert "SBER" in result.stdout
        assert "AAPL" not in result.stdout

    def test_instruments_filter_by_lot(self, monkeypatch, tmp_path):
        """Тест фильтрации по лотности."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER", lot=10),
            _mock_instrument(ticker="GAZP", lot=100),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--lot-min", "5", "--lot-max", "50"])

        assert result.exit_code == 0
        assert "SBER" in result.stdout
        assert "GAZP" not in result.stdout

    def test_instruments_filter_by_availability(self, monkeypatch, tmp_path):
        """Тест фильтрации по доступности."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER", api_trade_available_flag=True),
            _mock_instrument(ticker="GAZP", api_trade_available_flag=False),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--available"])

        assert result.exit_code == 0
        assert "SBER" in result.stdout
        assert "GAZP" not in result.stdout

    def test_instruments_json_output(self, monkeypatch, tmp_path):
        """Тест JSON вывода."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER", figi="BBG000000000"),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--json"])

        assert result.exit_code == 0
        assert '"ticker": "SBER"' in result.stdout or '"ticker":"SBER"' in result.stdout
        assert '"figi": "BBG000000000"' in result.stdout or '"figi":"BBG000000000"' in result.stdout

    def test_instruments_combined_filters(self, monkeypatch, tmp_path):
        """Тест комбинации фильтров."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER", name="Сбербанк", currency="RUB", exchange="MOEX"),
            _mock_instrument(ticker="GAZP", name="Газпром", currency="RUB", exchange="MOEX"),
            _mock_instrument(ticker="AAPL", name="Apple", currency="USD", exchange="SPB"),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(
            app, ["instruments", "--name", "Сбер", "--currency", "RUB", "--exchange", "MOEX"]
        )

        assert result.exit_code == 0
        assert "SBER" in result.stdout
        assert "GAZP" not in result.stdout
        assert "AAPL" not in result.stdout

    def test_instruments_no_results_with_filters(self, monkeypatch, tmp_path):
        """Тест когда фильтры не дают результатов."""
        env = tmp_path / ".env"
        env.write_text("INVEST_SANDBOX_TOKEN=test-token\n")
        monkeypatch.setattr("tcli.cli._settings", lambda: _settings())

        instruments = [
            _mock_instrument(ticker="SBER"),
        ]

        class MockBroker(Broker):
            def get_all_instruments(self, instrument_type=None):
                return instruments

        monkeypatch.setattr("tcli.cli._open_broker", lambda settings: MockBroker(settings))

        result = runner.invoke(app, ["instruments", "--name", "Несуществующий"])

        assert result.exit_code == 0
        assert "инструменты не найдены с заданными фильтрами" in result.stdout


class TestBrokerGetAllInstruments:
    """Тесты методов Broker для получения инструментов."""

    def test_get_all_shares(self, monkeypatch):
        """Тест получения всех акций."""
        from types import SimpleNamespace

        class MockInstruments:
            def shares(self):
                return SimpleNamespace(instruments=["share1", "share2"])

        class MockClient:
            def __init__(self):
                self.instruments = MockInstruments()

        broker = Broker(_settings())
        broker._client = MockClient()

        result = broker.get_all_shares()

        assert result == ["share1", "share2"]

    def test_get_all_bonds(self, monkeypatch):
        """Тест получения всех облигаций."""
        from types import SimpleNamespace

        class MockInstruments:
            def bonds(self):
                return SimpleNamespace(instruments=["bond1"])

        class MockClient:
            def __init__(self):
                self.instruments = MockInstruments()

        broker = Broker(_settings())
        broker._client = MockClient()

        result = broker.get_all_bonds()

        assert result == ["bond1"]

    def test_get_all_etfs(self, monkeypatch):
        """Тест получения всех ETF."""
        from types import SimpleNamespace

        class MockInstruments:
            def etfs(self):
                return SimpleNamespace(instruments=["etf1", "etf2", "etf3"])

        class MockClient:
            def __init__(self):
                self.instruments = MockInstruments()

        broker = Broker(_settings())
        broker._client = MockClient()

        result = broker.get_all_etfs()

        assert result == ["etf1", "etf2", "etf3"]

    def test_get_all_futures(self, monkeypatch):
        """Тест получения всех фьючерсов."""
        from types import SimpleNamespace

        class MockInstruments:
            def futures(self):
                return SimpleNamespace(instruments=["future1"])

        class MockClient:
            def __init__(self):
                self.instruments = MockInstruments()

        broker = Broker(_settings())
        broker._client = MockClient()

        result = broker.get_all_futures()

        assert result == ["future1"]

    def test_get_all_currencies(self, monkeypatch):
        """Тест получения всех валют."""
        from types import SimpleNamespace

        class MockInstruments:
            def currencies(self):
                return SimpleNamespace(instruments=["currency1"])

        class MockClient:
            def __init__(self):
                self.instruments = MockInstruments()

        broker = Broker(_settings())
        broker._client = MockClient()

        result = broker.get_all_currencies()

        assert result == ["currency1"]

    def test_get_all_instruments_by_type(self, monkeypatch):
        """Тест получения инструментов по типу."""
        from types import SimpleNamespace

        class MockInstruments:
            def shares(self):
                return SimpleNamespace(instruments=["share1"])

            def bonds(self):
                return SimpleNamespace(instruments=["bond1"])

        class MockClient:
            def __init__(self):
                self.instruments = MockInstruments()

        broker = Broker(_settings())
        broker._client = MockClient()

        result = broker.get_all_instruments("share")

        assert result == ["share1"]

    def test_get_all_instruments_no_type(self, monkeypatch):
        """Тест получения всех инструментов без указания типа."""
        from types import SimpleNamespace

        class MockInstruments:
            def shares(self):
                return SimpleNamespace(instruments=["share1"])

            def bonds(self):
                return SimpleNamespace(instruments=["bond1"])

            def etfs(self):
                return SimpleNamespace(instruments=["etf1"])

            def futures(self):
                return SimpleNamespace(instruments=[])

            def currencies(self):
                return SimpleNamespace(instruments=[])

        class MockClient:
            def __init__(self):
                self.instruments = MockInstruments()

        broker = Broker(_settings())
        broker._client = MockClient()

        result = broker.get_all_instruments()

        assert result == ["share1", "bond1", "etf1"]
