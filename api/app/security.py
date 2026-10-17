"""Shared-secret authorization for mutating and quota-consuming routes.

The app currently runs locally behind a CORS origin of http://localhost:3000, but
CORS is a browser convention — it does not stop a non-browser client. Any route that
mutates data, triggers an external scrape, or spends paid API quota goes through
`require_api_key` so the service is safe the first time it is bound to a non-loopback
interface.

Behaviour is driven by `settings.admin_api_key`:
  - unset (the local default) → open, with a one-time warning at import of the guard
  - set                       → callers must send `X-API-Key: <value>`
"""
from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

_API_KEY_HEADER = "X-API-Key"
_warned = False


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency enforcing the shared secret when one is configured."""
    global _warned

    expected = (settings.admin_api_key or "").strip()
    if not expected:
        if not _warned:
            _warned = True
            logger.warning(
                "ADMIN_API_KEY is not set — admin routes are unauthenticated. "
                "Set it before exposing this service beyond localhost."
            )
        return

    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
            headers={"WWW-Authenticate": _API_KEY_HEADER},
        )
