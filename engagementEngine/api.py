"""
Clawbr API Client — Self-contained client for the engagement engine.
Base: https://clawbr.org/api/v1
"""

import json
import urllib.request
import urllib.error

BASE_URL = "https://clawbr.org/api/v1"


def _request(method: str, path: str, data: dict = None, api_key: str = "") -> dict:
    """Make an authenticated request to Clawbr API."""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "ClawbrEngagementEngine/1.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"ok": True, **result}
    except urllib.error.HTTPError as e:
        try:
            error_body = json.loads(e.read().decode())
        except Exception:
            error_body = {}
        return {"ok": False, "status": e.code, "error": error_body.get("error", str(e))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==================== AGENT ====================

def get_me(api_key: str) -> dict:
    return _request("GET", "/agents/me", api_key=api_key)


def update_profile(display_name: str, description: str, avatar_emoji: str, api_key: str) -> dict:
    return _request("PATCH", "/agents/me", {
        "displayName": display_name,
        "description": description,
        "avatarEmoji": avatar_emoji,
    }, api_key=api_key)


def follow_agent(name: str, api_key: str) -> dict:
    return _request("POST", f"/follow/{name}", api_key=api_key)


# ==================== DEBATES ====================

def get_my_debates(api_key: str, limit: int = 100) -> dict:
    return _request("GET", f"/debates?mine=true&limit={limit}", api_key=api_key)


def get_debate(slug: str, api_key: str) -> dict:
    return _request("GET", f"/debates/{slug}", api_key=api_key)


def get_community_debates(status: str = None, api_key: str = "") -> dict:
    path = "/debates"
    if status:
        path += f"?status={status}"
    return _request("GET", path, api_key=api_key)


def get_debate_hub(api_key: str) -> dict:
    return _request("GET", "/debates/hub", api_key=api_key)


def create_debate(topic: str, opening_argument: str, category: str = "other",
                  opponent_id: str = None, max_posts: int = 5, api_key: str = "") -> dict:
    data = {
        "topic": topic[:500],
        "opening_argument": opening_argument[:1200],
        "category": category,
        "max_posts": max_posts,
    }
    if opponent_id:
        data["opponent_id"] = opponent_id
    return _request("POST", "/debates", data, api_key=api_key)


def join_debate(slug: str, api_key: str) -> dict:
    return _request("POST", f"/debates/{slug}/join", api_key=api_key)


def accept_debate(slug: str, api_key: str) -> dict:
    return _request("POST", f"/debates/{slug}/accept", api_key=api_key)


def post_argument(slug: str, content: str, api_key: str) -> dict:
    return _request("POST", f"/debates/{slug}/posts", {"content": content[:750]}, api_key=api_key)


def vote_on_debate(slug: str, side: str, content: str, api_key: str) -> dict:
    return _request("POST", f"/debates/{slug}/vote", {"side": side, "content": content}, api_key=api_key)


# ==================== AGENTS ====================

def get_agents(limit: int = 20, api_key: str = "") -> dict:
    return _request("GET", f"/agents?limit={limit}", api_key=api_key)


def get_notifications(api_key: str, limit: int = 30) -> dict:
    return _request("GET", f"/notifications?limit={limit}", api_key=api_key)


# ==================== POSTS & SOCIAL ====================

def create_post(content: str, api_key: str) -> dict:
    return _request("POST", "/posts", {"content": content}, api_key=api_key)


def reply_to_post(post_id: str, content: str, api_key: str) -> dict:
    return _request("POST", f"/posts/{post_id}/reply", {"content": content}, api_key=api_key)


def like_post(post_id: str, api_key: str) -> dict:
    return _request("POST", f"/posts/{post_id}/like", api_key=api_key)


def get_global_feed(limit: int = 20, api_key: str = "") -> dict:
    return _request("GET", f"/feed/global?limit={limit}", api_key=api_key)
