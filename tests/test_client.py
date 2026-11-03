from types import SimpleNamespace

import pytest
from tinkoff.invest.exceptions import RequestError, StatusCode

from tcli.client import (
    AmbiguousAccountError,
    Broker,
    NoAccountsError,
    SandboxError,
    api_error_text,
    is_transient,
    with_retries,
)
from tcli.config import Contour, Settings


def _account(acc_id="acc-1", name="Main", status="ACCOUNT_STATUS_OPEN"):
    return SimpleNamespace(
        id=acc_id,
        name=name,
        type=SimpleNamespace(name="ACCOUNT_TYPE_TINKOFF"),
        status=SimpleNamespace(name=status),
    )


def _response(accounts):
    return SimpleNamespace(accounts=list(accounts))


class FakeBroker(Broker):
    """Broker с подменённым SDK-клиентом (без сети)."""

    def __init__(self, settings, accounts=(), fail_with=None):
        super().__init__(settings)
        self._accounts = list(accounts)
        self._fail_with = list(fail_with or [])
        self._calls = {"n": 0}

    def _make_client(self):
        calls = self._calls
        accounts = self._accounts
        fail_with = self._fail_with

        def get_accounts():
            calls["n"] += 1
            if fail_with and calls["n"] <= len(fail_with):
                raise fail_with[calls["n"] - 1]
            return _response(accounts)

        users = SimpleNamespace(get_accounts=get_accounts)
        client = SimpleNamespace(users=users)
        client.__enter__ = lambda *a: client
        client.__exit__ = lambda *a: False
        return client

    def __enter__(self):
        if not self._settings.enabled:
            raise SandboxError("токен не задан: заполните .env (см. .env.example)")
        self._raw = self._make_client()
        self._client = self._raw.__enter__()
        return self


# --- ретраи ---------------------------------------------------------------


def test_transient_detection():
    assert is_transient(RequestError(StatusCode.UNAVAILABLE, "x", None))
    assert is_transient(RequestError(StatusCode.DEADLINE_EXCEEDED, "x", None))
    assert not is_transient(RequestError(StatusCode.INVALID_ARGUMENT, "x", None))
    assert not is_transient(ValueError("boom"))


def test_retries_then_success():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RequestError(StatusCode.UNAVAILABLE, "x", None)
        return "ok"

    assert with_retries(flaky, sleep=lambda _: None) == "ok"
    assert calls["n"] == 3


def test_no_retry_on_non_transient():
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise RequestError(StatusCode.INVALID_ARGUMENT, "nope", None)

    with pytest.raises(RequestError):
        with_retries(bad, sleep=lambda _: None)
    assert calls["n"] == 1


def test_gives_up_after_attempts():
    calls = {"n": 0}

    def always_down():
        calls["n"] += 1
        raise RequestError(StatusCode.UNAVAILABLE, "x", None)

    with pytest.raises(RequestError):
        with_retries(always_down, sleep=lambda _: None)
    assert calls["n"] == 3


# --- выбор счёта ----------------------------------------------------------


def _settings(name="", contour=Contour.SANDBOX):
    # Для SANDBOX используем sandbox_token, для LIVE - main_token
    if contour == Contour.SANDBOX:
        return Settings(sandbox_token="t.test", sandbox_account_name=name, contour=contour)
    else:
        return Settings(main_token="t.test", sandbox_account_name=name, contour=contour)


def test_pick_single_account():
    sb = FakeBroker(_settings(), accounts=[_account()])
    with sb:
        account = sb.pick_account()
    assert account.id == "acc-1"


def test_pick_by_name():
    sb = FakeBroker(
        _settings(name="second"),
        accounts=[_account("a1", "first"), _account("a2", "second")],
    )
    with sb:
        account = sb.pick_account()
    assert account.id == "a2"


def test_pick_no_accounts():
    sb = FakeBroker(_settings(), accounts=[])
    with sb:
        with pytest.raises(NoAccountsError):
            sb.pick_account()


def test_pick_ambiguous():
    sb = FakeBroker(_settings(), accounts=[_account("a1", "first"), _account("a2", "second")])
    with sb:
        with pytest.raises(AmbiguousAccountError):
            sb.pick_account()


def test_pick_unknown_name():
    sb = FakeBroker(_settings(name="ghost"), accounts=[_account("a1", "first")])
    with sb:
        with pytest.raises(NoAccountsError, match="ghost"):
            sb.pick_account()


def test_requires_token():
    sb = Broker(Settings(sandbox_token="", main_token=""))
    with pytest.raises(SandboxError):
        sb.__enter__()


# --- контуры --------------------------------------------------------------


def test_live_guard_on_payin():
    """payin доступен только в SANDBOX."""
    from tcli.client import LiveUnsupportedError

    sb = FakeBroker(_settings(contour=Contour.LIVE), accounts=[_account()])
    with sb:
        with pytest.raises(LiveUnsupportedError):
            sb.payin("acc-1", 1000)


def test_live_guard_on_create_account():
    from tcli.client import LiveUnsupportedError

    sb = FakeBroker(_settings(contour=Contour.LIVE), accounts=[_account()])
    with sb:
        with pytest.raises(LiveUnsupportedError):
            sb.create_account("test")


def test_contour_property():
    sb = FakeBroker(_settings(contour=Contour.LIVE), accounts=[_account()])
    assert sb.contour == Contour.LIVE
    assert not sb.is_sandbox


# --- ошибки и строки ------------------------------------------------------


def test_api_error_text_unauthenticated():
    text = api_error_text(RequestError(StatusCode.UNAUTHENTICATED, "40003", None))
    assert "40003" in text or "токен" in text


def test_account_row():
    row = Broker.account_row(_account())
    assert row["name"] == "Main"
    assert row["status"] == "OPEN"
    assert row["type"] == "TINKOFF"


def test_payin_rejects_non_positive():
    sb = FakeBroker(_settings(), accounts=[_account()])
    with sb:
        with pytest.raises(SandboxError):
            sb.payin("acc-1", 0)
        with pytest.raises(SandboxError):
            sb.payin("acc-1", -5)


def test_position_row_value():
    pos = SimpleNamespace(
        ticker="SBER",
        figi="FIGI1",
        instrument_type=SimpleNamespace(name="INSTRUMENT_TYPE_SHARE"),
        quantity=SimpleNamespace(units=10, nano=0),
        average_position_price=SimpleNamespace(units=300, nano=0),
        current_price=SimpleNamespace(units=310, nano=0),
        expected_yield=SimpleNamespace(units=100, nano=0),
    )
    row = Broker.position_row(pos)
    assert row["ticker"] == "SBER"
    assert row["type"] == "SHARE"
    assert row["value"] == 3100.0
    assert row["pnl"] == 100.0
