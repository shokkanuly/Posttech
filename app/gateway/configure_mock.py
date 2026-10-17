"""Create an ignored, operator-only local MOCK environment without printing keys."""

import argparse
import json
import os
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env.gateway"))
    parser.add_argument("--web-port", type=int, default=8000)
    parser.add_argument("--postgres-port", type=int, default=5432)
    args = parser.parse_args()
    app_key, callback_key = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    values = {
        "ENVIRONMENT": "development",
        "DEMO_MODE": "true",
        "DEMO_PASSWORD": "Password123!",
        "SECRET_KEY": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "WEB_PORT": str(args.web_port),
        "POSTGRES_PORT": str(args.postgres_port),
        "AI_PROVIDER": "grounded_knowledge",
        "GEMINI_API_KEY": "",
        "INTEGRATION_GATEWAY_URL": "http://gateway:9000",
        "INTEGRATION_OUTBOUND_KEY_ID": "janamen-mock-1",
        "INTEGRATION_OUTBOUND_KEY": app_key,
        "INTEGRATION_INBOUND_KEYS": json.dumps({"gateway-mock-1": callback_key}),
        "GATEWAY_CALLBACK_KEY_ID": "gateway-mock-1",
        "GATEWAY_CALLBACK_KEY": callback_key,
    }
    # Atomic creation, no overwrite/credential rotation. Never write these into the repository.
    try:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SystemExit("Environment already exists; nothing overwritten") from None
    with os.fdopen(fd, "w") as stream:
        stream.write("# Local MOCK only. Contains generated secrets; do not commit or share.\n")
        for key, value in values.items():
            stream.write(f"{key}='{value}'\n")
    print("Created operator-only MOCK environment; keys were not printed.")


if __name__ == "__main__":
    main()
