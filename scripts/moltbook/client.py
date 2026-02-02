#!/usr/bin/env python3
"""
Moltbook API Client - Post to the AI agent social network
"""

import os
import json
import requests
from typing import Optional, Dict, Any

class MoltbookClient:
    """Client for Moltbook API."""

    BASE_URL = "https://www.moltbook.com/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MOLTBOOK_API_KEY")

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def register_agent(self, name: str, description: str) -> Dict[str, Any]:
        """Register a new agent on Moltbook."""
        try:
            response = requests.post(
                f"{self.BASE_URL}/agents/register",
                headers={"Content-Type": "application/json"},
                json={"name": name, "description": description}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post(self, content: str, title: str = None, submolt: str = "general") -> Dict[str, Any]:
        """Create a post on Moltbook."""
        if not self.api_key:
            return {"success": False, "error": "MOLTBOOK_API_KEY not set"}

        try:
            payload = {
                "submolt": submolt,
                "content": content
            }
            if title:
                payload["title"] = title

            response = requests.post(
                f"{self.BASE_URL}/posts",
                headers=self._headers(),
                json=payload
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def comment(self, post_id: str, content: str) -> Dict[str, Any]:
        """Comment on a post."""
        if not self.api_key:
            return {"success": False, "error": "MOLTBOOK_API_KEY not set"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/posts/{post_id}/comments",
                headers=self._headers(),
                json={"content": content}
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def vote(self, post_id: str, direction: str = "up") -> Dict[str, Any]:
        """Vote on a post (up or down)."""
        if not self.api_key:
            return {"success": False, "error": "MOLTBOOK_API_KEY not set"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/posts/{post_id}/vote",
                headers=self._headers(),
                json={"direction": direction}
            )
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_feed(self, submolt: str = None, sort: str = "hot", limit: int = 25) -> Dict[str, Any]:
        """Get posts from feed."""
        try:
            params = {"sort": sort, "limit": limit}
            if submolt:
                params["submolt"] = submolt

            response = requests.get(
                f"{self.BASE_URL}/posts",
                headers=self._headers(),
                params=params
            )
            response.raise_for_status()
            return {"success": True, "posts": response.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python client.py register <name> <description>")
        print("  python client.py post <content> [submolt]")
        print("  python client.py feed [submolt]")
        sys.exit(1)

    client = MoltbookClient()
    cmd = sys.argv[1]

    if cmd == "register":
        name = sys.argv[2] if len(sys.argv) > 2 else "TestAgent"
        desc = sys.argv[3] if len(sys.argv) > 3 else "A test agent"
        result = client.register_agent(name, desc)
        print(json.dumps(result, indent=2))

    elif cmd == "post":
        content = sys.argv[2] if len(sys.argv) > 2 else "Hello Moltbook!"
        submolt = sys.argv[3] if len(sys.argv) > 3 else "general"
        result = client.post(content, submolt=submolt)
        print(json.dumps(result, indent=2))

    elif cmd == "feed":
        submolt = sys.argv[2] if len(sys.argv) > 2 else None
        result = client.get_feed(submolt=submolt)
        print(json.dumps(result, indent=2))
