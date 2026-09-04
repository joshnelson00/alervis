import pytest

from halo.config import Config

VALID_TOKEN = "a" * 32


def test_requires_api_token(monkeypatch):
    monkeypatch.delenv("HALO_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="HALO_API_TOKEN"):
        Config.from_env()


def test_rejects_short_api_token(monkeypatch):
    monkeypatch.setenv("HALO_API_TOKEN", "tooshort")
    with pytest.raises(RuntimeError, match="at least 16"):
        Config.from_env()


def test_defaults(monkeypatch):
    for key in ("HALO_PROFILE_DIR", "HALO_PORT", "HALO_BIND_HOST", "HALO_CACHE_TTL_S"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HALO_API_TOKEN", VALID_TOKEN)

    cfg = Config.from_env()
    assert cfg.port == 8765
    # Binds to loopback by default; exposure is a deliberate opt-in.
    assert cfg.host == "127.0.0.1"
    assert cfg.gateway_url == "https://gateway.halo.gcu.edu/"


def test_overrides_from_env(monkeypatch):
    monkeypatch.setenv("HALO_API_TOKEN", VALID_TOKEN)
    monkeypatch.setenv("HALO_PORT", "9999")
    monkeypatch.setenv("HALO_RENEW_INTERVAL_S", "300")
    monkeypatch.setenv("HALO_PROFILE_DIR", "/tmp/halo-profile")

    cfg = Config.from_env()
    assert cfg.port == 9999
    assert cfg.renew_interval_s == 300
    assert str(cfg.profile_dir) == "/tmp/halo-profile"


def test_non_integer_env_is_rejected(monkeypatch):
    monkeypatch.setenv("HALO_API_TOKEN", VALID_TOKEN)
    monkeypatch.setenv("HALO_PORT", "not-a-number")
    with pytest.raises(ValueError, match="HALO_PORT"):
        Config.from_env()


def test_blank_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("HALO_API_TOKEN", VALID_TOKEN)
    monkeypatch.setenv("HALO_PORT", "")
    assert Config.from_env().port == 8765
