from pathlib import Path

from tcli.config import Settings, mask_token


def test_mask_token_short():
    assert mask_token("") == "<пусто>"
    assert mask_token("12345678") == "***"  # ровно 8 — целиком скрыто


def test_mask_token_normal():
    assert mask_token("abcdefgh12345678") == "abcd***5678"


def test_load_from_env_file(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=secret-token-value\nSANDBOX_ACCOUNT_NAME=main\n")
    s = Settings.load(env)
    assert s.invest_token == "secret-token-value"
    assert s.sandbox_account_name == "main"
    assert s.enabled is True


def test_fallback_to_sandbox_token(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("INVEST_SANDBOX_TOKEN=sandbox-value\n")
    s = Settings.load(env)
    assert s.invest_token == "sandbox-value"


def test_primary_token_wins(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=primary\nINVEST_SANDBOX_TOKEN=secondary\n")
    s = Settings.load(env)
    assert s.invest_token == "primary"


def test_missing_env_file(tmp_path: Path):
    s = Settings.load(tmp_path / "nope.env")
    assert s.enabled is False
    assert s.masked() == "<пусто>"


def test_masked_does_not_leak(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=abcdefghijklmnop\n")
    s = Settings.load(env)
    assert "abcdefghijklmnop" not in s.masked()
