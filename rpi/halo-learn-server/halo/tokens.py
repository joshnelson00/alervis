"""Thread-safe holder for the current Halo tokens.

Kept free of any browser dependency: the session thread writes here, and HTTP
handlers only ever read plain strings out of it.
"""

import threading
import time
from enum import Enum
from typing import Optional, Tuple


class State(str, Enum):
    STARTING = "starting"
    LIVE = "live"
    RENEWING = "renewing"
    NEEDS_REAUTH = "needs_reauth"
    STOPPED = "stopped"


class TokenStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._auth: Optional[str] = None
        self._context: Optional[str] = None
        self._minted_at: float = 0.0
        self._state: State = State.STARTING
        self._last_error: Optional[str] = None
        self._renewals = 0

    def set_tokens(self, auth: str, context: str) -> None:
        with self._lock:
            self._auth = auth
            self._context = context
            self._minted_at = time.time()
            self._state = State.LIVE
            self._last_error = None
            self._renewals += 1

    def clear(self, state: State, error: Optional[str] = None) -> None:
        with self._lock:
            self._auth = None
            self._context = None
            self._minted_at = 0.0
            self._state = state
            self._last_error = error

    def set_state(self, state: State) -> None:
        with self._lock:
            self._state = state

    def get_fresh(self, max_age_s: int) -> Optional[Tuple[str, str]]:
        """Return tokens only if present and younger than max_age_s."""
        with self._lock:
            if not (self._auth and self._context):
                return None
            if time.time() - self._minted_at > max_age_s:
                return None
            return self._auth, self._context

    def snapshot(self) -> dict:
        """State for /health. Never includes token values."""
        with self._lock:
            age = time.time() - self._minted_at if self._minted_at else None
            return {
                "state": self._state.value,
                "has_tokens": bool(self._auth and self._context),
                "token_age_s": round(age, 1) if age is not None else None,
                "renewals": self._renewals,
                "last_error": self._last_error,
            }
