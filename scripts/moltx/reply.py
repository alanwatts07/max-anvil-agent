#!/usr/bin/env python3
"""Reply to a post on MoltX - no LLM needed (you provide the text)"""
import os
import sys
import json
import requests

def reply(post_id: str, content: str) -> dict:
    api_key = os.environ.get("MOLTX_API_KEY")
    response = requests.post(
        "https://moltx.io/v1/posts",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={"type": "reply", "parent_id": post_id, "content": content}
    )
    if response.status_code in [200, 201]:
        return {"success": True, "data": response.json()}
    return {"success": False, "error": response.text}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python reply.py <post_id> \"Your reply\"")
        sys.exit(1)
    print(json.dumps(reply(sys.argv[1], sys.argv[2]), indent=2))
