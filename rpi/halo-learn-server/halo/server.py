"""HTTP API in front of the Halo session.

Request handlers never touch Playwright and never wait on a renewal. They read
whatever tokens the session thread has already minted; if none are fresh they
fail fast with 503 rather than blocking, which is what keeps p99 latency bounded
and leaves room inside an Alexa response budget.
"""

import json
import logging
import secrets
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Config
from .gateway import AuthError, ForbiddenError, GatewayError, HaloGateway
from .operations import FORUM_COUNT_FILTERS, GET_ALL_CLASSES, REGISTRY
from .session import BrowserSession
from .tokens import TokenStore

log = logging.getLogger(__name__)


class TTLCache:
    """Small response cache.

    The Halo reference asks integrators to avoid polling and to cache
    conservatively; this keeps repeated identical questions off the gateway.
    """

    def __init__(self, ttl_s: int) -> None:
        self._ttl = ttl_s
        self._lock = threading.Lock()
        self._entries: Dict[str, tuple] = {}

    def get(self, key: str) -> Optional[Any]:
        if self._ttl <= 0:
            return None
        with self._lock:
            hit = self._entries.get(key)
            if not hit:
                return None
            stored_at, value = hit
            if time.time() - stored_at > self._ttl:
                del self._entries[key]
                return None
            return value

    def put(self, key: str, value: Any) -> None:
        if self._ttl <= 0:
            return
        with self._lock:
            self._entries[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class QueryRequest(BaseModel):
    operation: str = Field(..., description="A documented operation name")
    variables: Dict[str, Any] = Field(default_factory=dict)
    slug_id: Optional[str] = Field(default=None, description="Current-Class-Slug-Id")
    course_class_id: Optional[str] = Field(
        default=None, description="Current-Course-Class-Id"
    )
    no_cache: bool = False


def create_app(config: Config) -> FastAPI:
    store = TokenStore()
    session = BrowserSession(config, store)
    gateway = HaloGateway(config.gateway_url, config.halo_url)
    cache = TTLCache(config.cache_ttl_s)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        session.start()
        try:
            yield
        finally:
            session.stop()
            gateway.close()

    app = FastAPI(title="Halo Learn Server", version="0.1.0", lifespan=lifespan)

    def require_token(request: Request) -> None:
        header = request.headers.get("authorization", "")
        prefix = "bearer "
        supplied = header[len(prefix):] if header.lower().startswith(prefix) else ""
        if not secrets.compare_digest(supplied, config.api_token):
            raise HTTPException(status_code=401, detail="invalid or missing bearer token")

    def current_tokens() -> tuple:
        tokens = store.get_fresh(config.stale_after_s)
        if tokens is None:
            # Kick a renewal, but do not wait for it.
            session.request_renew()
            snap = store.snapshot()
            detail = (
                "Halo session needs interactive re-auth; run `python -m halo.session login`"
                if snap["state"] == "needs_reauth"
                else "Halo session not ready"
            )
            raise HTTPException(
                status_code=503, detail=detail, headers={"Retry-After": "15"}
            )
        return tokens

    def run(op, variables, slug_id, course_class_id, use_cache=True):
        key = json.dumps(
            [op.name, variables, slug_id, course_class_id], sort_keys=True, default=str
        )
        if use_cache:
            hit = cache.get(key)
            if hit is not None:
                return hit, True

        auth, ctx = current_tokens()
        try:
            data = gateway.execute(
                auth, ctx, op, variables, slug_id=slug_id, course_class_id=course_class_id
            )
        except AuthError as exc:
            # Tokens were rejected: drop them and renew in the background.
            session.request_renew()
            cache.clear()
            raise HTTPException(
                status_code=503, detail=f"tokens rejected, renewing: {exc}",
                headers={"Retry-After": "15"},
            ) from exc
        except ForbiddenError as exc:
            # The account cannot see this resource. Renewing would not help, and
            # doing so would churn the session on every bad slug.
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except GatewayError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        if use_cache:
            cache.put(key, data)
        return data, False

    @app.get("/health")
    def health() -> JSONResponse:
        """Unauthenticated liveness. Reports session state, never token values."""
        snap = store.snapshot()
        healthy = snap["state"] == "live" and snap["has_tokens"]
        return JSONResponse(status_code=200 if healthy else 503, content=snap)

    @app.get("/classes", dependencies=[Depends(require_token)])
    def classes(no_cache: bool = False) -> dict:
        data, cached = run(GET_ALL_CLASSES, {}, None, None, use_cache=not no_cache)
        return {"cached": cached, "data": data}

    @app.post("/query", dependencies=[Depends(require_token)])
    def query(req: QueryRequest) -> dict:
        op = REGISTRY.get(req.operation)
        if op is None:
            raise HTTPException(
                status_code=400,
                detail=f"unknown operation; known: {sorted(REGISTRY)}",
            )
        variables = dict(req.variables)
        # Convenience: the forum count filter is fixed boilerplate.
        if op.name == "SidebarForumNotifications" and "filters" not in variables:
            variables["filters"] = FORUM_COUNT_FILTERS

        data, cached = run(
            op, variables, req.slug_id, req.course_class_id, use_cache=not req.no_cache
        )
        return {"cached": cached, "operation": op.name, "data": data}

    @app.post("/session/renew", dependencies=[Depends(require_token)])
    def renew() -> dict:
        session.request_renew()
        cache.clear()
        return {"requested": True, "session": store.snapshot()}

    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    config = Config.from_env()
    uvicorn.run(create_app(config), host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
