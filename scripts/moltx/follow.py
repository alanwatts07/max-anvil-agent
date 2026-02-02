#!/usr/bin/env python3
"""Follow an agent on MoltX - no LLM needed"""
import os
import sys
import requests

def follow(agent_name: str) -> dict:
    api_key = os.environ.get("MOLTX_API_KEY")
    response = requests.post(
        f"https://moltx.io/v1/follow/{agent_name}",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    return {"success": response.status_code in [200, 201], "agent": agent_name}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python follow.py <agent_name>")
        sys.exit(1)
    print(follow(sys.argv[1]))
