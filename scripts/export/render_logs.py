#!/usr/bin/env python3
"""
Fetch and filter logs from Render API for the terraso-staging-backend service.

Equivalent curl command:
    curl -s -H "Authorization: Bearer $RENDER_API_KEY" \
      "https://api.render.com/v1/logs?ownerId=tea-cckb13o2i3mgrpq5rr7g&resource=srv-cclqgbirrk007qgqoml0&limit=500"

Usage:
    export RENDER_API_KEY=rnd_xxxxx
    python scripts/export/render_logs.py [--filter PATTERN] [--exclude PATTERN] [--limit N]

Examples:
    # Get all non-healthcheck logs
    python scripts/export/render_logs.py --exclude healthz

    # Get only export-related logs
    python scripts/export/render_logs.py --filter export --exclude healthz

    # Get more logs
    python scripts/export/render_logs.py --limit 1000 --exclude healthz
"""

import argparse
import json
import os
import sys

import requests

# Render API configuration
RENDER_API_URL = "https://api.render.com/v1/logs"
OWNER_ID = "tea-cckb13o2i3mgrpq5rr7g"

# Service IDs
SERVICES = {
    "staging-backend": "srv-cclqgbirrk007qgqoml0",
    "production-backend": "srv-cd6s0farrk04votkk8cg",
}


def fetch_logs(api_key, service_id, limit=500):
    """Fetch logs from Render API."""
    resp = requests.get(
        RENDER_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        params={
            "ownerId": OWNER_ID,
            "resource": service_id,
            "limit": limit,
        },
    )
    resp.raise_for_status()
    return resp.json()


def filter_logs(logs, include_pattern=None, exclude_pattern=None):
    """Filter logs by include/exclude patterns."""
    filtered = []
    for log in logs:
        msg = log.get("message", "")
        msg_lower = msg.lower()

        if exclude_pattern and exclude_pattern.lower() in msg_lower:
            continue
        if include_pattern and include_pattern.lower() not in msg_lower:
            continue

        filtered.append(log)
    return filtered


def format_log(log):
    """Format a log entry for display."""
    msg = log.get("message", "")
    timestamp = log.get("timestamp", "")

    # Try to parse JSON message for prettier output
    try:
        parsed = json.loads(msg)
        request = parsed.get("request", "")
        event = parsed.get("event", "")
        code = parsed.get("code", "")
        if request:
            if code:
                return f"{timestamp} [{code}] {request} ({event})"
            return f"{timestamp} {request} ({event})"
    except json.JSONDecodeError:
        pass

    return f"{timestamp} {msg[:200]}"


def main():
    parser = argparse.ArgumentParser(description="Fetch and filter Render logs")
    parser.add_argument(
        "--service",
        choices=list(SERVICES.keys()),
        default="staging-backend",
        help="Service to fetch logs from (default: staging-backend)",
    )
    parser.add_argument(
        "--filter", dest="include", help="Only show logs containing this pattern"
    )
    parser.add_argument(
        "--exclude", help="Exclude logs containing this pattern (e.g., 'healthz')"
    )
    parser.add_argument(
        "--limit", type=int, default=500, help="Number of logs to fetch (default: 500)"
    )
    parser.add_argument("--raw", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    api_key = os.environ.get("RENDER_API_KEY")
    if not api_key:
        print("Error: RENDER_API_KEY environment variable not set", file=sys.stderr)
        print(
            "Get an API key from https://dashboard.render.com -> Account Settings -> API Keys",
            file=sys.stderr,
        )
        sys.exit(1)

    service_id = SERVICES[args.service]

    try:
        data = fetch_logs(api_key, service_id, args.limit)
    except requests.RequestException as e:
        print(f"Error fetching logs: {e}", file=sys.stderr)
        sys.exit(1)

    logs = data.get("logs", [])
    has_more = data.get("hasMore", False)

    filtered = filter_logs(logs, args.include, args.exclude)

    # Sort by timestamp to show oldest first (chronological order)
    filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""))

    if args.raw:
        print(json.dumps(filtered, indent=2))
    else:
        for log in filtered:
            print(format_log(log))

        print(f"\n--- Showing {len(filtered)}/{len(logs)} logs", file=sys.stderr)
        if has_more:
            print("--- More logs available (increase --limit)", file=sys.stderr)


if __name__ == "__main__":
    main()
