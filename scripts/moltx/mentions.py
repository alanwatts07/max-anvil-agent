#!/usr/bin/env python3
"""Get mentions from MoltX - no LLM needed"""
import os
import json
import requests

def get_mentions(limit: int = 10) -> dict:
    api_key = os.environ.get("MOLTX_API_KEY")
    response = requests.get(
        f"https://moltx.io/v1/feed/mentions?limit={limit}",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    if response.status_code == 200:
        return response.json()
    return {"error": response.text}

if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(json.dumps(get_mentions(limit), indent=2))
