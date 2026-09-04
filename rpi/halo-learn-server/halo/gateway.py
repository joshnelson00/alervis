"""HTTP client for the Halo GraphQL gateway.

Once tokens are extracted the browser is not involved: these are plain POSTs
over a pooled requests.Session, which keeps the TLS handshake off the hot path.

Two failure layers matter, per the Halo reference: a non-2xx response is a
transport failure, and a 2xx response can still carry a GraphQL `errors` array.
"""

import logging
from typing import Any, Dict, Optional

import requests

from .operations import Operation

log = logging.getLogger(__name__)

# Signals that the *credential* is bad and renewing the session may help.
# Deliberately narrow: a false positive here churns the session on every
# request for an inaccessible resource.
_AUTH_ERROR_HINTS = (
    "unauthenticated",
    "token expired",
    "expired token",
    "invalid token",
    "jwt",
)

# Signals the caller asked for something this account cannot see. Observed with
# a valid session and a slugId the account is not enrolled in, so this must not
# be mistaken for an auth failure.
_FORBIDDEN_HINTS = (
    "permission evaluator",
    "access denied",
    "forbidden",
    "not authorized",
)


class GatewayError(Exception):
    """The gateway request failed for a reason a retry will not fix."""


class AuthError(GatewayError):
    """Tokens were rejected. The session should be renewed."""


class ForbiddenError(GatewayError):
    """The account cannot access the requested resource. Renewal will not help."""


class HaloGateway:
    def __init__(self, gateway_url: str, halo_origin: str, timeout: float = 20.0) -> None:
        self._url = gateway_url
        self._origin = halo_origin.rstrip("/")
        self._timeout = timeout
        self._http = requests.Session()

    def close(self) -> None:
        self._http.close()

    def execute(
        self,
        auth_token: str,
        context_token: str,
        operation: Operation,
        variables: Optional[Dict[str, Any]] = None,
        slug_id: Optional[str] = None,
        course_class_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run one documented operation and return its `data` payload."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
            "Contexttoken": f"Bearer {context_token}",
            "Gql-Operation-Name": operation.name,
            "Origin": self._origin,
            "Referer": f"{self._origin}/",
        }
        # The live Halo app sends both course-context headers on every gateway
        # call, empty when there is no course in scope. Mirroring that avoids
        # depending on the gateway treating absent and empty as the same thing.
        if operation.needs_slug_header:
            headers["Current-Class-Slug-Id"] = slug_id or ""
        if operation.needs_course_class_header:
            headers["Current-Course-Class-Id"] = course_class_id or ""

        body = {
            "operationName": operation.name,
            "variables": variables or {},
            "query": operation.query,
        }

        try:
            resp = self._http.post(
                self._url, json=body, headers=headers, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise GatewayError(f"transport failure: {exc}") from exc

        if resp.status_code in (401, 403):
            raise AuthError(f"gateway rejected tokens (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            raise GatewayError(f"gateway returned HTTP {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise GatewayError("gateway returned a non-JSON body") from exc

        errors = payload.get("errors")
        if errors:
            raise _classify(errors)

        data = payload.get("data")
        if data is None:
            raise GatewayError("gateway response contained no data")
        return data


def _classify(errors: list) -> GatewayError:
    """Turn a GraphQL errors array into the right exception type.

    Any error means the operation failed, even alongside partial data.

    Credential problems normally arrive as HTTP 401/403; this only catches the
    cases the gateway reports inside a 200. Anything unrecognised stays a plain
    GatewayError so an unfamiliar message never triggers a session renewal.
    """
    messages = []
    for err in errors:
        if isinstance(err, dict):
            messages.append(str(err.get("message", "")))
    joined = " | ".join(m for m in messages if m) or "unspecified GraphQL error"
    lowered = joined.lower()
    if any(hint in lowered for hint in _FORBIDDEN_HINTS):
        return ForbiddenError(joined)
    if any(hint in lowered for hint in _AUTH_ERROR_HINTS):
        return AuthError(joined)
    return GatewayError(joined)
