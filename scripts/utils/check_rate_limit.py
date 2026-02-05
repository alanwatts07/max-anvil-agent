#!/usr/bin/env python3
"""
Check MoltX API rate limits

The API returns rate limit headers on POST requests:
- X-RateLimit-Limit: Request limit
- X-RateLimit-Remaining: Remaining requests
- X-RateLimit-Reset: Unix timestamp when limit resets

Limits for claimed agents:
- Posts (top-level, reposts, quotes): 100/hour
- Replies: 600/hour
"""
import os
import requests
from datetime import datetime
from pathlib import Path

# Load env
ENV_FILE = Path(__file__).parent.parent.parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def check_rate_limits():
    """Check rate limits by making a like request (lightweight POST)"""
    print("Checking MoltX rate limits...\n")

    # Try to like a post (we'll use a known post ID)
    # This is a POST request that should return rate limit headers
    test_post_id = "3d17eb39-988d-4fea-a749-a44073df1135"  # SlopLauncher post

    r = requests.post(
        f"{BASE}/posts/{test_post_id}/like",
        headers=HEADERS
    )

    print(f"Response status: {r.status_code}")

    # Check for rate limit headers
    limit = r.headers.get("X-RateLimit-Limit")
    remaining = r.headers.get("X-RateLimit-Remaining")
    reset = r.headers.get("X-RateLimit-Reset")

    if limit or remaining or reset:
        print("\n📊 RATE LIMIT STATUS:")
        print(f"  Limit: {limit}")
        print(f"  Remaining: {remaining}")
        if reset:
            try:
                reset_time = datetime.fromtimestamp(int(reset))
                print(f"  Resets at: {reset_time.strftime('%H:%M:%S')}")
            except:
                print(f"  Reset timestamp: {reset}")
    else:
        print("\n⚠ No rate limit headers in response")
        print("  Headers received:")
        for h, v in r.headers.items():
            print(f"    {h}: {v}")

    # Also check the response body for any rate info
    try:
        data = r.json()
        if "error" in data:
            print(f"\n  Error: {data['error'].get('message', data['error'])}")
    except:
        pass

    return {
        "limit": limit,
        "remaining": remaining,
        "reset": reset
    }


if __name__ == "__main__":
    check_rate_limits()
