"""Owns the headless browser that holds the signed-in Halo session.

The Halo tokens (TE1TX0FVVEg / TE1TX0NPTlRFWFQ) are non-persistent session
cookies: they die with the browser process and are re-minted by the Halo SPA
after it authenticates. Only ESTSAUTHPERSISTENT survives to disk, and it is
what lets the Microsoft round trip complete without MFA.

Two consequences shape this module:

1. The browser runs as a long-lived daemon. Launching per request would cost a
   full SSO round trip (~9s measured on a Pi 4).
2. Exactly one thread touches Playwright. Callers read plain strings out of
   TokenStore, so the browser object is never shared across threads.
"""

import argparse
import logging
import threading
import time
from typing import Optional, Tuple

from playwright.sync_api import sync_playwright

from .config import Config
from .tokens import State, TokenStore

log = logging.getLogger(__name__)

AUTH_COOKIE = "TE1TX0FVVEg"  # base64 "LMS_AUTH"
CONTEXT_COOKIE = "TE1TX0NPTlRFWFQ"  # base64 "LMS_CONTEXT"

SIGN_IN_TEXT = "SIGN IN WITH MICROSOFT"

# Text Entra shows when it wants a second factor. If any of these are on screen
# the session cannot be recovered unattended.
MFA_MARKERS = (
    "approve sign in request",
    "enter code",
    "verification code",
    "we texted your phone",
    "open your microsoft authenticator",
    "verify your identity",
    "more information required",
    "enter the number shown",
)

LAUNCH_ARGS = ("--no-sandbox", "--disable-dev-shm-usage")


class ReauthRequired(Exception):
    """Raised when only a human with the second factor can recover the session."""


class BrowserSession:
    """Background thread that keeps TokenStore populated."""

    def __init__(self, config: Config, store: TokenStore) -> None:
        self._config = config
        self._store = store
        self._stop = threading.Event()
        self._renew_now = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("session already started")
        self._thread = threading.Thread(target=self._run, name="halo-session", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 30.0) -> None:
        self._stop.set()
        self._renew_now.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def request_renew(self) -> None:
        """Ask the loop to re-mint now. Returns immediately; never blocks a request."""
        self._renew_now.set()

    def _run(self) -> None:
        cfg = self._config
        cfg.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as pw:
                context = pw.chromium.launch_persistent_context(
                    user_data_dir=str(cfg.profile_dir),
                    executable_path=cfg.chromium_path,
                    headless=True,
                    args=list(LAUNCH_ARGS),
                    viewport={"width": 1520, "height": 900},
                )
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    self._loop(context, page)
                finally:
                    context.close()
        except Exception as exc:  # noqa: BLE001 - daemon thread must not die silently
            log.exception("session thread crashed")
            self._store.clear(State.STOPPED, f"{type(exc).__name__}: {exc}")
        else:
            self._store.clear(State.STOPPED)

    def _loop(self, context, page) -> None:
        cfg = self._config
        while not self._stop.is_set():
            try:
                self._store.set_state(State.RENEWING)
                auth, ctx = self._mint(context, page)
                self._store.set_tokens(auth, ctx)
                log.info("tokens minted")
                wait_s = cfg.renew_interval_s
            except ReauthRequired as exc:
                log.error("interactive re-auth required: %s", exc)
                self._store.clear(State.NEEDS_REAUTH, str(exc))
                # Retry slowly; a human has to run `login` to fix this.
                wait_s = max(cfg.renew_interval_s, 300)
            except Exception as exc:  # noqa: BLE001
                log.exception("mint failed")
                self._store.clear(State.STARTING, f"{type(exc).__name__}: {exc}")
                wait_s = 60

            self._renew_now.wait(timeout=wait_s)
            self._renew_now.clear()

    def _mint(self, context, page) -> Tuple[str, str]:
        """Drive the Halo SPA until both session cookies exist."""
        cfg = self._config
        deadline = time.monotonic() + cfg.mint_timeout_s

        page.goto(cfg.halo_url, wait_until="domcontentloaded", timeout=60_000)

        clicked = False
        while time.monotonic() < deadline:
            tokens = read_tokens(context)
            if tokens:
                return tokens

            if _mfa_prompt_visible(page):
                raise ReauthRequired("Microsoft is prompting for a second factor")

            if not clicked:
                # The React app renders after domcontentloaded, so the button
                # may not exist on the first pass.
                button = page.locator(f"text={SIGN_IN_TEXT}")
                try:
                    if button.count():
                        button.first.click()
                        clicked = True
                        log.info("clicked sign-in")
                except Exception as exc:  # noqa: BLE001 - transient during nav
                    log.debug("sign-in click failed, will retry: %s", exc)

            time.sleep(1.5)

        raise ReauthRequired(f"no tokens after {cfg.mint_timeout_s}s")


def read_tokens(context) -> Optional[Tuple[str, str]]:
    """Pull the two Halo tokens from a browser context, or None."""
    jar = {c["name"]: c["value"] for c in context.cookies()}
    auth, ctx = jar.get(AUTH_COOKIE), jar.get(CONTEXT_COOKIE)
    return (auth, ctx) if auth and ctx else None


def _mfa_prompt_visible(page) -> bool:
    if "login.microsoftonline.com" not in page.url:
        return False
    try:
        body = page.inner_text("body").lower()
    except Exception:  # noqa: BLE001 - mid-navigation
        return False
    return any(marker in body for marker in MFA_MARKERS)


def interactive_login(config: Config, wait_s: int = 600) -> bool:
    """Headed login for first-time setup or after MFA invalidates the session.

    Run this on the Pi's display (Raspberry Pi Connect screen sharing) and
    complete the Microsoft prompt by hand. Check "Stay signed in?" so Entra
    issues the persistent cookie the daemon relies on.
    """
    import os

    os.environ.setdefault("WAYLAND_DISPLAY", "wayland-0")
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")

    config.profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(config.profile_dir),
            executable_path=config.chromium_path,
            headless=False,
            args=list(LAUNCH_ARGS),
            viewport={"width": 1520, "height": 900},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(config.halo_url, wait_until="domcontentloaded", timeout=60_000)
            print("Browser open on the Pi's display. Finish the Microsoft login there.")
            print('Check "Stay signed in?" when offered.')
            print(f"Waiting up to {wait_s}s...")

            deadline = time.monotonic() + wait_s
            while time.monotonic() < deadline:
                if read_tokens(context):
                    print("Session established; tokens minted.")
                    return True
                time.sleep(3)
            print("Timed out waiting for tokens.")
            return False
        finally:
            context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Halo session utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)
    login = sub.add_parser("login", help="headed interactive login")
    login.add_argument("--wait", type=int, default=600)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.cmd == "login":
        ok = interactive_login(Config.from_env(), wait_s=args.wait)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
