"""Execute inside the owned MOCK gateway container; prints no service credentials."""

import json
import time

import httpx

from app.gateway.config import GatewaySettings
from app.gateway.models import GatewayJob
from app.gateway.runtime import GatewayRuntime
from app.integrations import signing

config = GatewaySettings()
runtime = GatewayRuntime(config)
with runtime.sessions() as db:
    before = db.query(GatewayJob).count()
results = {}
with httpx.Client(base_url="http://127.0.0.1:9000", trust_env=False, timeout=10) as client:

    def headers(method, path, body=b"", **kwargs):
        return signing.sign(config.APP_KEY_ID, config.APP_KEY, method, path, body, **kwargs)

    wire = headers("GET", "/health")
    results["valid"] = client.get("/health", headers=wire).status_code
    results["replay"] = client.get("/health", headers=wire).status_code
    results["expired"] = client.get(
        "/health", headers=headers("GET", "/health", now=time.time() - 301)
    ).status_code
    wire = headers("GET", "/health")
    wire["X-Key-Id"] = "retired-synthetic"
    results["unknown_key"] = client.get("/health", headers=wire).status_code
    body = b'{"reason":"PRIVATE_RUNTIME_MARKER_20261018"}'
    response = client.post(
        "/v1/documents", content=body + b" ",
        headers=headers("POST", "/v1/documents", body),
    )
    assert "PRIVATE_RUNTIME_MARKER_20261018" not in response.text
    results["body_tamper"] = response.status_code
    wire = headers("POST", "/v1/documents", body)
    wire["Content-Type"] = "application/json"
    response = client.post("/v1/documents", content=body, headers=wire)
    assert "PRIVATE_RUNTIME_MARKER_20261018" not in response.text
    results["strict_schema"] = response.status_code
    body = b"x" * 65537
    results["oversize"] = client.post(
        "/v1/documents", content=body, headers=headers("POST", "/v1/documents", body)
    ).status_code
with runtime.sessions() as db:
    after = db.query(GatewayJob).count()
assert results == {
    "valid": 200, "replay": 401, "expired": 401, "unknown_key": 401,
    "body_tamper": 401, "strict_schema": 422, "oversize": 413,
}
assert before == after
print(json.dumps({
    "mode": "MOCK", "checks": results, "jobs_before": before, "jobs_after": after,
    "private_input_echoed": False,
}, indent=2))
runtime.engine.dispose()
