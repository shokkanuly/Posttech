"""Scoped known-value scan; keep raw container logs and credentials outside Git."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--env-file", type=Path, required=True)
args = parser.parse_args()
values = dotenv_values(args.env_file)
names = (
    "DEMO_PASSWORD", "SECRET_KEY", "POSTGRES_PASSWORD",
    "INTEGRATION_OUTBOUND_KEY", "GATEWAY_CALLBACK_KEY",
)
known = [values[name].encode() for name in names]
# Inspect local provider secrets without displaying values or enabling that provider.
local = dotenv_values(".env")
known += [value.encode() for key, value in local.items() if value and len(value) >= 24
          and key in {"GEMINI_API_KEY", "INTEGRATION_OUTBOUND_KEY", "GATEWAY_CALLBACK_KEY"}]
paths = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"])
files = [Path(p) for p in dict.fromkeys(paths.decode().split("\0")) if p and Path(p).is_file()]
pattern = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35})"
)
known_files, pattern_files = [], []
for file in files:
    data = file.read_bytes()
    if any(secret in data for secret in known):
        known_files.append(str(file))
    if pattern.search(data):
        pattern_files.append(str(file))
logs = subprocess.check_output([
    "docker", "compose", "-p", "janamen-int-20261018", "--env-file", str(args.env_file),
    "logs", "--no-color", "web", "gateway", "integration-worker",
], stderr=subprocess.STDOUT)
markers = [b"PRIVATE_RUNTIME_MARKER_20261018", b"PRIVATE_CALLBACK_AUDIT_MARKER",
           b'"approved_by_employee_code"', b"X-Signature:", b"Authorization: Bearer "]
result = {
    "scope": "Current nonignored files, known generated/local provider values and owned web/gateway/worker logs; no general history or comprehensive secret detector claimed",
    "files_checked": len(files), "known_private_value_files": known_files,
    "selected_secret_pattern_files": pattern_files,
    "runtime_log_known_secret_matches": sum(secret in logs for secret in known),
    "runtime_log_sensitive_markers": [marker.decode() for marker in markers if marker in logs],
    "raw_logs_committed": False,
}
Path(__file__).with_name("log-and-secret-scan.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
assert not known_files and not pattern_files
assert not result["runtime_log_known_secret_matches"] and not result["runtime_log_sensitive_markers"]
