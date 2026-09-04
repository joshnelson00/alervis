"""Configuration for the Halo session service, read from the environment."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROFILE = Path.home() / ".local" / "share" / "halo-learn-server" / "profile"


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class Config:
    """Service settings.

    Token lifetime is not discoverable: the Halo tokens are JWEs, so their
    expiry claims are encrypted and cannot be read locally. renew_interval_s is
    therefore a conservative guess rather than a derived value, backed up by
    reactive renewal whenever the gateway rejects a token.
    """

    api_token: str
    profile_dir: Path = DEFAULT_PROFILE
    chromium_path: str = "/usr/bin/chromium"
    halo_url: str = "https://halo.gcu.edu/"
    gateway_url: str = "https://gateway.halo.gcu.edu/"
    host: str = "127.0.0.1"
    port: int = 8765

    # How often the background loop re-mints tokens.
    renew_interval_s: int = 900
    # Tokens older than this are refused rather than served to a caller.
    stale_after_s: int = 1800
    # Budget for one mint attempt, including a full silent-SSO round trip
    # (measured at ~9s on a Pi 4).
    mint_timeout_s: int = 120
    # Short response cache; the Halo reference asks integrators not to poll.
    cache_ttl_s: int = 60

    @classmethod
    def from_env(cls) -> "Config":
        api_token = os.environ.get("HALO_API_TOKEN", "").strip()
        if not api_token:
            raise RuntimeError(
                "HALO_API_TOKEN is required; it is the shared secret callers "
                "must present as 'Authorization: Bearer <token>'."
            )
        if len(api_token) < 16:
            raise RuntimeError("HALO_API_TOKEN must be at least 16 characters.")

        profile = os.environ.get("HALO_PROFILE_DIR", "").strip()
        return cls(
            api_token=api_token,
            profile_dir=Path(profile) if profile else DEFAULT_PROFILE,
            chromium_path=os.environ.get("HALO_CHROMIUM", "/usr/bin/chromium"),
            host=os.environ.get("HALO_BIND_HOST", "127.0.0.1"),
            port=_int_env("HALO_PORT", 8765),
            renew_interval_s=_int_env("HALO_RENEW_INTERVAL_S", 900),
            stale_after_s=_int_env("HALO_STALE_AFTER_S", 1800),
            mint_timeout_s=_int_env("HALO_MINT_TIMEOUT_S", 120),
            cache_ttl_s=_int_env("HALO_CACHE_TTL_S", 60),
        )
