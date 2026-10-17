"""Latency and throughput of key API calls against a running JanaМен server.

    python -m app.benchmark --base-url http://127.0.0.1:8000 --rounds 30

Logs in as the three demo roles (DEMO_PASSWORD from the environment), measures each
endpoint sequentially (p50/p95/max), then a parallel burst for requests per second.
"""

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ACCOUNTS = {
    "employee": "aruzhan@janapost.kz",
    "manager": "timur@janapost.kz",
    "hr_admin": "aigerim@janapost.kz",
}


def login(client: httpx.Client, email: str, password: str) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "Accept-Language": "ru-RU",
    }


def percentile(samples: list[float], share: float) -> float:
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--burst", type=int, default=400, help="requests in the parallel burst")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    password = os.environ.get("DEMO_PASSWORD", "")
    if not password:
        raise SystemExit("Set DEMO_PASSWORD to the demo accounts' password")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        headers = {role: login(client, email, password) for role, email in ACCOUNTS.items()}
        member = client.get("/api/v1/manager/team?limit=1", headers=headers["manager"]).json()[0]
        cases = [
            ("employee", "GET", "/api/v1/me/dashboard", None),
            ("employee", "GET", "/api/v1/requests?limit=100", None),
            ("employee", "GET", "/api/v1/notifications?limit=50", None),
            ("employee", "GET", "/api/v1/courses", None),
            ("employee", "POST", "/api/v1/ai/chat", {"question": "Как оформить отпуск?"}),
            ("manager", "GET", "/api/v1/manager/team?limit=100", None),
            ("manager", "GET", f"/api/v1/manager/team/{member['user_id']}", None),
            ("manager", "GET", "/api/v1/manager/requests?limit=100", None),
            ("hr_admin", "GET", "/api/v1/manager/team?limit=100", None),
            ("hr_admin", "GET", "/api/v1/manager/requests?limit=100", None),
            ("hr_admin", "GET", "/api/v1/admin/audit?limit=100", None),
        ]
        results = []
        for role, method, path, body in cases:
            samples, rows = [], None
            for _ in range(args.rounds):
                started = time.perf_counter()
                response = client.request(method, path, headers=headers[role], json=body)
                samples.append((time.perf_counter() - started) * 1000)
                response.raise_for_status()
                payload = response.json()
                rows = len(payload) if isinstance(payload, list) else None
            results.append(
                {
                    "role": role,
                    "call": f"{method} {path.split('?')[0]}",
                    "rows": rows,
                    "p50_ms": round(statistics.median(samples), 1),
                    "p95_ms": round(percentile(samples, 0.95), 1),
                    "max_ms": round(max(samples), 1),
                }
            )

        def hit(index: int) -> int:
            role, method, path, body = cases[index % len(cases)]
            return client.request(method, path, headers=headers[role], json=body).status_code

        started = time.perf_counter()
        with ThreadPoolExecutor(args.workers) as pool:
            statuses = list(pool.map(hit, range(args.burst)))
        elapsed = time.perf_counter() - started

    burst = {
        "requests": args.burst,
        "workers": args.workers,
        "seconds": round(elapsed, 2),
        "requests_per_second": round(args.burst / elapsed, 1),
        "errors": sum(status >= 400 for status in statuses),
    }
    print(f"{'role':9} {'call':42} {'rows':>5} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    for r in results:
        row_label = "" if r["rows"] is None else str(r["rows"])
        print(
            f"{r['role']:9} {r['call']:42} {row_label:>5} {r['p50_ms']:>8} {r['p95_ms']:>8} {r['max_ms']:>8}"
        )
    print(
        f"\nParallel burst: {burst['requests']} requests, {burst['workers']} workers, "
        f"{burst['seconds']} s → {burst['requests_per_second']} req/s, errors: {burst['errors']}"
    )
    if args.output:
        args.output.write_text(
            json.dumps(
                {
                    "base_url": args.base_url,
                    "rounds": args.rounds,
                    "endpoints": results,
                    "burst": burst,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
