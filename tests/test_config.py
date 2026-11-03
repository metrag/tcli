from pathlib import Path

from tcli.config import Contour, Settings, mask_token


def test_mask_token_short():
    assert mask_token("") == "<пусто>"
    assert mask_token("12345678") == "***"  # ровно 8 — целиком скрыто


def test_mask_token_normal():
    assert mask_token("abcdefgh12345678") == "abcd***5678"


def test_load_from_env_file(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=live-token\nINVEST_SANDBOX_TOKEN=sandbox-token\nSANDBOX_ACCOUNT_NAME=main\n")
    s = Settings.load(env)
    assert s.main_token == "live-token"
    assert s.sandbox_token == "sandbox-token"
    assert s.sandbox_account_name == "main"
    # По умолчанию контур SANDBOX, поэтому активный токен — sandbox
    assert s.token == "sandbox-token"
    assert s.enabled is True


def test_sandbox_contour_uses_sandbox_token(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("INVEST_SANDBOX_TOKEN=sandbox-value\nTCLI_CONTOUR=SANDBOX\n")
    s = Settings.load(env)
    assert s.token == "sandbox-value"
    assert s.contour == Contour.SANDBOX


def test_live_contour_uses_main_token(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=live-value\nTCLI_CONTOUR=LIVE\n")
    s = Settings.load(env)
    assert s.token == "live-value"
    assert s.contour == Contour.LIVE


def test_tokens_not_interchangeable(tmp_path: Path):
    """Токены разделены: sandbox_token для SANDBOX, main_token для LIVE."""
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=live-only\nINVEST_SANDBOX_TOKEN=sandbox-only\n")
    
    # SANDBOX контур использует sandbox_token
    s_sandbox = Settings.load(env)
    assert s_sandbox.token == "sandbox-only"
    assert s_sandbox.main_token == "live-only"
    
    # LIVE контур использует main_token
    env.write_text("INVEST_TOKEN=live-only\nINVEST_SANDBOX_TOKEN=sandbox-only\nTCLI_CONTOUR=LIVE\n")
    s_live = Settings.load(env)
    assert s_live.token == "live-only"
    assert s_live.sandbox_token == "sandbox-only"


def test_missing_env_file(tmp_path: Path):
    s = Settings.load(tmp_path / "nope.env")
    assert s.enabled is False
    assert s.masked() == "<пусто>"


def test_masked_does_not_leak(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("INVEST_TOKEN=abcdefghijklmnop\nTCLI_CONTOUR=LIVE\n")
    s = Settings.load(env)
    assert "abcdefghijklmnop" not in s.masked()
