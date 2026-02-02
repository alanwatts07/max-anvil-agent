#!/usr/bin/env python3
"""Get feed from MoltX - no LLM needed"""
import os
import sys
import json
import requests

def get_feed(feed_type: str = "global", limit: int = 10) -> dict:
    api_key = os.environ.get("MOLTX_API_KEY")
    response = requests.get(
        f"https://moltx.io/v1/feed/{feed_type}?limit={limit}",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    if response.status_code == 200:
        return response.json()
    return {"error": response.text}

if __name__ == "__main__":
    feed_type = sys.argv[1] if len(sys.argv) > 1 else "global"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    print(json.dumps(get_feed(feed_type, limit), indent=2))
