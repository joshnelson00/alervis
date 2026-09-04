# Halo Learn Server

Runs on the Raspberry Pi. Holds a signed-in Halo session and proxies read-only
GraphQL operations to `gateway.halo.gcu.edu`, so callers (an Alexa Lambda, a
desktop widget, a script) get JSON without dealing with browsers or Microsoft
sign-in.

## Why a browser is involved at all

Halo's gateway takes two bearer tokens that the web app keeps in cookies
(`TE1TX0FVVEg` / `TE1TX0NPTlRFWFQ`). Measured behaviour on this account:

- **The tokens are JWEs, not JWTs** — five segments, and the payload is
  encrypted. Expiry cannot be read locally, so renewal is time-based plus
  reactive, never claims-based.
- **They are non-persistent session cookies.** They die with the browser
  process. Only `ESTSAUTHPERSISTENT` survives to disk.
- **Silent SSO works.** With `ESTSAUTHPERSISTENT` present, clicking "Sign in
  with Microsoft" completes with no MFA prompt (~9s on a Pi 4).

So the service keeps one long-lived headless Chromium alive and re-mints tokens
on a schedule. Launching a browser per request would cost that full SSO round
trip every time.

## Design

```
 session thread                     HTTP handlers
 ──────────────                     ─────────────
 Playwright + Chromium              read plain strings
   │  mints tokens                    │  call gateway via requests
   └──────────► TokenStore ◄──────────┘
                (lock-protected)
```

Exactly one thread ever touches Playwright, so the browser is never shared
across threads. Two rules follow from that:

- **Renewal never happens on the request path.** If no fresh token exists, the
  request gets a fast `503` with `Retry-After` instead of blocking behind a
  browser. That bounds p99 latency, which is what keeps a voice-assistant
  response budget viable.
- **Auth failures renew in the background.** A rejected token triggers a
  renewal and returns `503`; it does not stall the caller.

## Install (on the Pi)

```bash
sudo apt install -y chromium            # Playwright has no reliable arm64 build
git clone <repo> ~/alervis
cp -r ~/alervis/rpi/halo-learn-server ~/halo-learn-server
cd ~/halo-learn-server
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Create `~/.config/halo-learn-server.env` (mode `600`, never in the repo):

```bash
HALO_API_TOKEN=<long random string>
```

Generate one with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`.

## First login

Needs a display. Use Raspberry Pi Connect screen sharing:

```bash
set -a; . ~/.config/halo-learn-server.env; set +a
./.venv/bin/python -m halo.session login
```

Sign in on the Pi's display and **check "Stay signed in?"** — that is what
issues the persistent cookie everything else depends on. Repeat this only when
`/health` reports `needs_reauth`.

## Run

```bash
mkdir -p ~/.config/systemd/user
cp systemd/halo-learn-server.service ~/.config/systemd/user/
loginctl enable-linger $USER
systemctl --user daemon-reload
systemctl --user enable --now halo-learn-server
journalctl --user -u halo-learn-server -f
```

## API

`GET /health` is unauthenticated and reports state only — never token values.
Everything else needs `Authorization: Bearer $HALO_API_TOKEN`.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Session state, token age, renewal count. `503` when not live |
| `GET /classes` | `GetAllClasses` |
| `POST /query` | Any documented operation |
| `POST /session/renew` | Force a renewal and drop the cache |

```bash
TOKEN=$(grep HALO_API_TOKEN ~/.config/halo-learn-server.env | cut -d= -f2)

curl -s localhost:8765/health

curl -s localhost:8765/classes -H "Authorization: Bearer $TOKEN"

curl -s localhost:8765/query -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"operation":"UpcomingAssignments",
       "variables":{"slugId":"<slug>"},
       "slug_id":"<slug>","course_class_id":"<courseClassId>"}'
```

Get `slugId` and `courseClassId` from `/classes` first; they are not
interchangeable. Course-context headers are sent only for the operations whose
reference page documents them.

Responses are cached for `HALO_CACHE_TTL_S` (default 60s) — the Halo reference
asks integrators not to poll. Pass `no_cache` to bypass.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `HALO_API_TOKEN` | — | Required, min 16 chars |
| `HALO_BIND_HOST` | `127.0.0.1` | Loopback by default; exposure is opt-in |
| `HALO_PORT` | `8765` | |
| `HALO_PROFILE_DIR` | `~/.local/share/halo-learn-server/profile` | Holds the live session |
| `HALO_CHROMIUM` | `/usr/bin/chromium` | |
| `HALO_RENEW_INTERVAL_S` | `900` | A guess — token lifetime is unreadable |
| `HALO_STALE_AFTER_S` | `1800` | Older tokens are refused, not served |
| `HALO_MINT_TIMEOUT_S` | `120` | One mint attempt, including silent SSO |
| `HALO_CACHE_TTL_S` | `60` | `0` disables caching |

## Reaching it from outside the Pi

It binds to loopback. To reach it from a laptop, prefer the existing Tailscale
tailnet (`HALO_BIND_HOST=0.0.0.0` plus tailnet ACLs) over any port forward. For
AWS Lambda, a Cloudflare Tunnel avoids inbound ports entirely. Do not expose
this to the public internet: the profile directory holds a live session to a
real student account.

## Security notes

- The profile directory is a credential. Back it up only encrypted, if at all.
- Tokens are never logged, never returned by `/health`, and never persisted by
  this service.
- Single-user by design. It authenticates as one account and has no concept of
  callers with different identities.
