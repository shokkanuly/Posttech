"""Scan staged/current files and owned MOCK logs without exposing private values."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--session-dir", type=Path, required=True)
args = parser.parse_args()
out = Path(__file__).resolve().parent
known = []
for name in ("demo.env", "postgres.env"):
    values = dotenv_values(args.session_dir / name)
    known.extend(value.encode() for key, value in values.items() if value and len(value) >= 16
                 and any(marker in key for marker in ("PASSWORD", "SECRET", "KEY")))
local = dotenv_values(".env")
known.extend(value.encode() for key, value in local.items() if value and len(value) >= 24
             and key in {"GEMINI_API_KEY", "INTEGRATION_OUTBOUND_KEY", "GATEWAY_CALLBACK_KEY"})
patterns = re.compile(
    rb"(?:Bearer\s+[A-Za-z0-9_.-]{16,}|eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35})"
)
files = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"]).decode().split("\0")
files = [Path(file) for file in dict.fromkeys(files) if file and Path(file).is_file()]
known_hits, pattern_hits = [], []
invalid_test_fixtures = {
    Path("tests/test_api_matrix.py"): '4d13f17fbf791fc570be033d09af240d67ff62312f203e3242f7cba1383969f2',
    Path("tests/test_security.py"): '407218900076bd4fcbf63105cac5a01d0b03c41926c6316dc9587176d70701fc',
}
for file in files:
    data = file.read_bytes()
    if any(value in data for value in known): known_hits.append(str(file))
    if any(hashlib.sha256(match.group()).hexdigest() != invalid_test_fixtures.get(file) for match in patterns.finditer(data)):
        pattern_hits.append(str(file))
patch = subprocess.check_output(["git", "diff", "--cached", "--unified=0"])
# Deleted historical tokens are expected during redaction; only added content can
# introduce a value into the new tree. Current files are independently scanned above.
staged = b"\n".join(line[1:] for line in patch.splitlines() if line.startswith(b"+") and not line.startswith(b"+++"))
removed_token_lines = sum(bool(patterns.search(line[1:])) for line in patch.splitlines()
                          if line.startswith(b"-") and not line.startswith(b"---"))
staged_known = sum(value in staged for value in known)
staged_patterns = bool(patterns.search(staged))
logs = subprocess.check_output([
    "docker", "compose", "--env-file", str(args.session_dir / "demo.env"),
    "logs", "--no-color", "web", "gateway", "integration-worker",
], stderr=subprocess.STDOUT)
runtime_records = [
    Path("docs/evidence/integration-2026-10-18/runtime-journey.json"),
    out / "runtime-journey.json",
]
for file in runtime_records:
    data = file.read_bytes()
    assert not patterns.search(data) and not any(value in data for value in known)
    obj = json.loads(data)
    def check_keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert key.lower() not in {
                    "password", "secret", "signing_key", "authorization", "bearer_token",
                    "database_url", "dsn", "email", "full_name", "phone", "iin", "reason",
                }, (str(file), key)
                check_keys(child)
        elif isinstance(value, list):
            for child in value: check_keys(child)
    check_keys(obj)
commands = []
for command in (["git", "status", "--short"], ["git", "check-ignore", "-v", ".env.gateway"],
                ["git", "ls-files", ".env.gateway"], ["git", "diff", "--check"],
                ["git", "diff", "--cached", "--check"]):
    result = subprocess.run(command, capture_output=True, text=True)
    commands.append({"command": command, "exit_code": result.returncode, "stdout": result.stdout})
    assert result.returncode == 0
assert not commands[2]["stdout"]
result = {
    "scope": "Known generated/private provider values and selected bearer/JWT/secret formats in current nonignored files, staged patch, both runtime records and owned container logs; not an exhaustive detector",
    "files_checked": len(files), "known_value_files": known_hits, "pattern_files": pattern_hits,
    "staged_known_value_matches": staged_known, "staged_added_pattern_match": staged_patterns,
    "removed_historical_token_lines": removed_token_lines,
    "intentional_invalid_test_fixtures": [str(path) for path in invalid_test_fixtures],
    "runtime_records_reviewed": [str(file.relative_to(Path.cwd())) if file.is_absolute() else str(file) for file in runtime_records],
    "log_known_value_matches": sum(value in logs for value in known),
    "log_bearer_or_secret_match": bool(patterns.search(logs)),
    "env_gateway_tracked": False, "commands": commands, "raw_logs_committed": False,
}
(out / "secret-scan.json").write_text(json.dumps(result, indent=2) + "\n")
assert not known_hits and not pattern_hits and not staged_known and not staged_patterns
assert not result["log_known_value_matches"] and not result["log_bearer_or_secret_match"]
print("PASS: private values/tokens absent from staged/current files, runtime metadata and owned logs; .env.gateway ignored/untracked.")
