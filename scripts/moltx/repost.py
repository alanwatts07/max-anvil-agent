#!/usr/bin/env python3
"""Repost on MoltX - no LLM needed"""
import os
import sys
import requests

def repost(post_id: str) -> dict:
    api_key = os.environ.get("MOLTX_API_KEY")
    response = requests.post(
        "https://moltx.io/v1/posts",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={"type": "repost", "parent_id": post_id}
    )
    return {"success": response.status_code in [200, 201], "post_id": post_id}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python repost.py <post_id>")
        sys.exit(1)
    print(repost(sys.argv[1]))
