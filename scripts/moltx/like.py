#!/usr/bin/env python3
"""Like a post on MoltX - no LLM needed"""
import os
import sys
import requests

def like(post_id: str) -> dict:
    api_key = os.environ.get("MOLTX_API_KEY")
    response = requests.post(
        f"https://moltx.io/v1/posts/{post_id}/like",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    return {"success": response.status_code in [200, 201], "post_id": post_id}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python like.py <post_id>")
        sys.exit(1)
    print(like(sys.argv[1]))
