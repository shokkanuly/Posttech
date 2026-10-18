"""Signed container readiness probe; the gateway has no anonymous endpoints."""

import httpx

from app.gateway.config import GatewaySettings
from app.integrations import signing

if __name__ == "__main__":
    config = GatewaySettings()
    if not config.JANAMEN_KEYS:
        raise SystemExit(1)
    key_id, key = next(iter(config.JANAMEN_KEYS.items()))
    response = httpx.get(
        "http://127.0.0.1:9000/health",
        headers=signing.sign(key_id, key, "GET", "/health", b""),
        timeout=5,
    )
    raise SystemExit(0 if response.status_code == 200 else 1)
