"""Create an ignored, operator-only local MOCK environment without printing keys."""

import argparse
import json
import os
import re
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env.gateway"))
    parser.add_argument("--web-port", type=int, default=8000)
    parser.add_argument("--postgres-port", type=int, default=5432)
    parser.add_argument("--project-name", default="janamen-mock-" + secrets.token_hex(4))
    args = parser.parse_args()
    if os.environ.get("ENVIRONMENT", "development") == "production":
        parser.error("MOCK configuration is disabled in production")
    if not re.fullmatch(r"janamen-mock-[a-z0-9][a-z0-9_-]{0,40}", args.project_name):
        parser.error("Project name must start with janamen-mock- and use lowercase ASCII")
    if not all(1 <= port <= 65535 for port in (args.web_port, args.postgres_port)):
        parser.error("Ports must be between 1 and 65535")
    app_key, callback_key = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    values = {
        "COMPOSE_PROJECT_NAME": args.project_name,
        "ENVIRONMENT": "development",
        "DEMO_MODE": "true",
        "DEMO_PASSWORD": secrets.token_urlsafe(24),
        "SECRET_KEY": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "WEB_PORT": str(args.web_port),
        "POSTGRES_PORT": str(args.postgres_port),
        "AI_PROVIDER": "grounded_knowledge",
        "GEMINI_API_KEY": "",
        "GEMINI_DATA_SHARING_APPROVED": "false",
        "SEED_SCALE_EMPLOYEES": "5",
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
    print(f"Created private MOCK environment for {args.project_name}; secrets were not printed.")


if __name__ == "__main__":
    main()
