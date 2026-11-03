from pathlib import Path

from tcli.ssl import ENV_VAR, cert_status, ensure_ssl


def test_ensure_ssl_sets_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    cert = tmp_path / "root.pem"
    cert.write_text("dummy")
    result = ensure_ssl(cert)
    assert result == cert
    import os

    assert os.environ[ENV_VAR] == str(cert)


def test_ensure_ssl_missing_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    result = ensure_ssl(tmp_path / "absent.pem")
    assert result is None
    import os

    assert ENV_VAR not in os.environ


def test_ensure_ssl_does_not_override(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(ENV_VAR, "/existing/path")
    cert = tmp_path / "root.pem"
    cert.write_text("dummy")
    ensure_ssl(cert)
    import os

    assert os.environ[ENV_VAR] == "/existing/path"


def test_cert_status(tmp_path: Path):
    cert = tmp_path / "root.pem"
    cert.write_text("12345")
    status = cert_status(cert)
    assert status["exists"] is True
    assert status["size"] == 5

    missing = cert_status(tmp_path / "absent.pem")
    assert missing["exists"] is False
    assert missing["size"] == 0
