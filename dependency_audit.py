"""Audit exact project pins against OSV; no application data or secrets are sent.

Run: python dependency_audit.py --output docs/evidence/dependency-audit.json
Exit 0: no matches; 1: advisories matched; 2: check could not complete.
"""

import argparse
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import certifi


def locked_packages(path: Path, visited: set[Path] | None = None) -> dict[str, str]:
    visited = visited if visited is not None else set()
    path = path.resolve()
    if path in visited:
        return {}
    visited.add(path)
    packages = {}
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            packages.update(locked_packages(path.parent / line[3:].strip(), visited))
            continue
        match = re.fullmatch(r"([a-zA-Z0-9_.-]+)==([a-zA-Z0-9_.+-]+)", line)
        if not match:
            raise ValueError("Only exact package pins and -r includes are supported")
        packages[match[1].lower().replace("_", "-")] = match[2]
    return packages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        packages = locked_packages(Path(__file__).parent / "requirements-dev.txt")
        queries = [
            {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
            for name, version in sorted(packages.items())
        ]
        endpoint = "https://api.osv.dev/v1/querybatch"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps({"queries": queries}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(
            request, timeout=20, context=ssl.create_default_context(cafile=certifi.where())
        ) as response:
            results = json.load(response)["results"]
        if len(results) != len(queries):
            raise ValueError("Incomplete vulnerability response")
        findings = [
            {
                "package": query["package"]["name"],
                "version": query["version"],
                "advisories": result["vulns"],
            }
            for query, result in zip(queries, results)
            if result.get("vulns")
        ]
        report = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": endpoint,
            "checked_packages": len(queries),
            "packages": packages,
            "findings": findings,
            "scope": "Exact runtime and development pins; advisory matches, not exploitability proof or a guarantee of security",
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Checked {len(queries)} exact pins; {len(findings)} packages have advisory matches.")
        for finding in findings:
            print(
                f"{finding['package']}=={finding['version']}: "
                + ", ".join(v["id"] for v in finding["advisories"])
            )
        return 1 if findings else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Dependency audit incomplete ({type(exc).__name__}); no clean result claimed.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
