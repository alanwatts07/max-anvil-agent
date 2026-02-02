#!/usr/bin/env python3
"""Post to MoltX - no LLM needed (you provide the text)"""
import os
import sys
import json
import requests

def post(content: str) -> dict:
    api_key = os.environ.get("MOLTX_API_KEY")
    response = requests.post(
        "https://moltx.io/v1/posts",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={"content": content}
    )
    if response.status_code in [200, 201]:
        return {"success": True, "data": response.json()}
    return {"success": False, "error": response.text}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post.py \"Your post content\"")
        sys.exit(1)
    print(json.dumps(post(sys.argv[1]), indent=2))
