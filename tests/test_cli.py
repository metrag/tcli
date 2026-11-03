from types import SimpleNamespace

from typer.testing import CliRunner

from tcli.cli import app
from tcli.config import Settings

runner = CliRunner()


class FakeSandbox:
    """Стаб Sandbox для команд CLI (без сети)."""

    def __init__(self, accounts=None):
        self._accounts = accounts if accounts is not None else [_acc()]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def accounts(self):
        return list(self._accounts)


def _acc():
    return SimpleNamespace(
        id="acc-1",
        name="Main",
        type=SimpleNamespace(name="ACCOUNT_TYPE_TINKOFF"),
        status=SimpleNamespace(name="ACCOUNT_STATUS_OPEN"),
    )


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("check", "status", "positions", "orders", "payin", "reset"):
        assert cmd in result.output


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)  # typer: no_args_is_help
    assert "check" in result.output


def test_payin_rejects_zero():
    result = runner.invoke(app, ["payin", "0"])
    assert result.exit_code != 0
    assert "больше 0" in result.output


def test_payin_rejects_negative():
    result = runner.invoke(app, ["payin", "-5"])
    assert result.exit_code != 0


def test_reset_reports_unavailable():
    result = runner.invoke(app, ["reset"])
    assert result.exit_code == 1
    assert "reset" in result.output


def test_check_fails_without_token(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "tcli.cli._settings",
        lambda: Settings(invest_token="", env_path=tmp_path / ".env"),
    )
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "токен не задан" in result.output


def test_check_ok_with_stub(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=stub-token\n")
    monkeypatch.setattr("tcli.cli._settings", lambda: Settings(invest_token="stub-token", env_path=env))
    monkeypatch.setattr("tcli.cli._open_sandbox", lambda settings: FakeSandbox())
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0, result.output
    assert "check: OK" in result.output


def test_check_api_failure(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=stub-token\n")

    class BrokenSandbox(FakeSandbox):
        def accounts(self):
            raise RuntimeError("boom: network down")

    monkeypatch.setattr("tcli.cli._settings", lambda: Settings(invest_token="stub-token", env_path=env))
    monkeypatch.setattr("tcli.cli._open_sandbox", lambda settings: BrokenSandbox())
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "ПРОВАЛ" in result.output
