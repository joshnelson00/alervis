import time

from halo.tokens import State, TokenStore


def test_starts_empty():
    store = TokenStore()
    assert store.get_fresh(60) is None
    snap = store.snapshot()
    assert snap["state"] == "starting"
    assert snap["has_tokens"] is False
    assert snap["token_age_s"] is None


def test_fresh_tokens_are_returned():
    store = TokenStore()
    store.set_tokens("auth-value", "ctx-value")
    assert store.get_fresh(60) == ("auth-value", "ctx-value")
    assert store.snapshot()["state"] == "live"


def test_stale_tokens_are_withheld():
    store = TokenStore()
    store.set_tokens("auth-value", "ctx-value")
    # Age them past the limit without sleeping.
    store._minted_at = time.time() - 120
    assert store.get_fresh(60) is None
    # Still reported as held, just too old to serve.
    assert store.snapshot()["has_tokens"] is True


def test_clear_records_state_and_error():
    store = TokenStore()
    store.set_tokens("a", "b")
    store.clear(State.NEEDS_REAUTH, "mfa required")
    assert store.get_fresh(60) is None
    snap = store.snapshot()
    assert snap["state"] == "needs_reauth"
    assert snap["last_error"] == "mfa required"
    assert snap["has_tokens"] is False


def test_snapshot_never_leaks_token_values():
    store = TokenStore()
    store.set_tokens("SECRET-AUTH", "SECRET-CTX")
    serialized = repr(store.snapshot())
    assert "SECRET-AUTH" not in serialized
    assert "SECRET-CTX" not in serialized


def test_renewals_are_counted():
    store = TokenStore()
    store.set_tokens("a", "b")
    store.set_tokens("c", "d")
    assert store.snapshot()["renewals"] == 2
