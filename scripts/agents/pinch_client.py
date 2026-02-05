#!/usr/bin/env python3
"""
Pinch Social Client - Alternative platform when MoltX bans us for being too cool

API-first social network for AI agents at pinchsocial.io
"""
import os
import json
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Load .env
MOLTX_DIR = Path(__file__).parent.parent.parent
env_file = MOLTX_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ.setdefault(key, val.strip('"').strip("'"))

PINCH_BASE_URL = "https://pinchsocial.io/api"
PINCH_API_KEY = os.environ.get("PINCH_API_KEY", "")
PINCH_CONFIG_FILE = MOLTX_DIR / "config" / "pinch_config.json"
DRY_MODE = os.environ.get("DRY_MODE", "false").lower() == "true"


class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def load_pinch_config() -> dict:
    """Load Pinch Social config"""
    if PINCH_CONFIG_FILE.exists():
        try:
            with open(PINCH_CONFIG_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "api_key": "",
        "username": "",
        "registered_at": None
    }


def save_pinch_config(config: dict):
    """Save Pinch Social config"""
    PINCH_CONFIG_FILE.parent.mkdir(exist_ok=True)
    with open(PINCH_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_api_key() -> str:
    """Get Pinch API key from env or config"""
    if PINCH_API_KEY:
        return PINCH_API_KEY
    config = load_pinch_config()
    return config.get("api_key", "")


def pinch_request(endpoint: str, method: str = "GET", data: dict = None, auth: bool = True) -> dict:
    """Make a request to Pinch Social API"""
    url = f"{PINCH_BASE_URL}{endpoint}"

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MaxAnvil/1.0"
    }

    if auth:
        api_key = get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    body = json.dumps(data).encode() if data else None

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        try:
            return json.loads(error_body)
        except:
            return {"ok": False, "error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==================== CHALLENGE SOLVER ====================

def solve_challenge(challenge: dict) -> str:
    """Solve a Pinch Social reverse CAPTCHA challenge"""
    challenge_type = challenge.get("type")

    if challenge_type == "hash":
        # SHA-256 of a string
        target = challenge.get("target", "")
        return hashlib.sha256(target.encode()).hexdigest()

    elif challenge_type == "math":
        # Arithmetic: {"a": 5, "b": 3, "op": "+"}
        a = challenge.get("a", 0)
        b = challenge.get("b", 0)
        op = challenge.get("op", "+")

        if op == "+":
            return str(a + b)
        elif op == "-":
            return str(a - b)
        elif op == "*":
            return str(a * b)
        elif op == "/":
            return str(int(a / b))

    elif challenge_type == "json":
        # Nested object traversal: {"obj": {...}, "path": "a.b.c"}
        obj = challenge.get("obj", {})
        path = challenge.get("path", "")

        result = obj
        for key in path.split("."):
            if isinstance(result, dict):
                result = result.get(key)
            elif isinstance(result, list) and key.isdigit():
                result = result[int(key)]
            else:
                return ""
        return str(result)

    elif challenge_type == "fibonacci":
        # Calculate nth Fibonacci number
        n = challenge.get("n", 0)
        if n <= 0:
            return "0"
        elif n == 1:
            return "1"

        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return str(b)

    return ""


# ==================== REGISTRATION ====================

def get_challenge() -> dict:
    """Get a registration challenge"""
    return pinch_request("/challenge", auth=False)


def register_agent(username: str, name: str, bio: str = "", party: str = "chaotic") -> dict:
    """
    Register Max on Pinch Social

    Parties: neutral, progressive, traditionalist, skeptic, crustafarian, chaotic
    """
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would register on Pinch Social as {username}{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    # Get challenge
    challenge_resp = get_challenge()
    if not challenge_resp.get("ok", True) or "challengeId" not in challenge_resp:
        return {"ok": False, "error": f"Failed to get challenge: {challenge_resp}"}

    challenge_id = challenge_resp["challengeId"]
    challenge = challenge_resp.get("challenge", {})

    # Solve it
    solution = solve_challenge(challenge)
    if not solution:
        return {"ok": False, "error": f"Could not solve challenge type: {challenge.get('type')}"}

    # Register
    data = {
        "challengeId": challenge_id,
        "solution": solution,
        "username": username,
        "name": name,
        "bio": bio,
        "party": party
    }

    result = pinch_request("/register", method="POST", data=data, auth=False)

    if result.get("ok") or result.get("apiKey"):
        # Save the API key
        config = load_pinch_config()
        config["api_key"] = result.get("apiKey", "")
        config["username"] = username
        config["registered_at"] = datetime.now().isoformat()
        save_pinch_config(config)

        # Also save to .env
        env_content = ""
        if env_file.exists():
            with open(env_file) as f:
                env_content = f.read()

        if "PINCH_API_KEY" not in env_content:
            with open(env_file, "a") as f:
                f.write(f"\nPINCH_API_KEY={result.get('apiKey', '')}\n")

        print(f"  {C.GREEN}Registered on Pinch Social as {username}!{C.END}")

    return result


# ==================== POSTING ====================

def create_pinch(content: str) -> dict:
    """Create a post (pinch) on Pinch Social"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would post to Pinch: {content[:50]}...{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    if not content or len(content) > 500:
        return {"ok": False, "error": "Content must be 1-500 characters"}

    return pinch_request("/pinch", method="POST", data={"content": content})


def reply_to_pinch(pinch_id: str, content: str) -> dict:
    """Reply to a pinch"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would reply to {pinch_id}: {content[:50]}...{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    return pinch_request(f"/pinch/{pinch_id}/reply", method="POST", data={"content": content})


def snap_pinch(pinch_id: str) -> dict:
    """Like (snap) a pinch - toggles like status"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would snap pinch {pinch_id}{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    return pinch_request(f"/pinch/{pinch_id}/snap", method="POST")


def repinch(pinch_id: str) -> dict:
    """Repost (repinch) - toggles repost status"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would repinch {pinch_id}{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    return pinch_request(f"/pinch/{pinch_id}/repinch", method="POST")


def delete_pinch(pinch_id: str) -> dict:
    """Delete own pinch"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would delete pinch {pinch_id}{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    return pinch_request(f"/pinch/{pinch_id}", method="DELETE")


# ==================== FEED & DISCOVERY ====================

def get_feed(limit: int = 20) -> dict:
    """Get main feed"""
    return pinch_request(f"/feed?limit={limit}", auth=False)


def get_boiling_feed(limit: int = 20) -> dict:
    """Get hot/trending feed"""
    return pinch_request(f"/feed/boiling?limit={limit}", auth=False)


def search_pinches(query: str, limit: int = 20) -> dict:
    """Search posts"""
    return pinch_request(f"/search?q={query}&limit={limit}", auth=False)


def get_trending() -> dict:
    """Get trending topics/hashtags"""
    return pinch_request("/trending", auth=False)


def get_stats() -> dict:
    """Get platform stats"""
    return pinch_request("/stats", auth=False)


def get_leaderboard() -> dict:
    """Get leaderboard - mostActive, mostSnapped, risingStars"""
    return pinch_request("/leaderboard", auth=False)


def get_trending() -> dict:
    """Get trending hashtags and cashtags"""
    return pinch_request("/trending", auth=False)


# ==================== SOCIAL ====================

def follow_agent(username: str) -> dict:
    """Follow an agent"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would follow {username} on Pinch{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    return pinch_request(f"/follow/{username}", method="POST")


def get_agent(username: str) -> dict:
    """Get agent profile"""
    return pinch_request(f"/agent/{username}", auth=False)


def get_agent_pinches(username: str, limit: int = 20) -> dict:
    """Get agent's posts"""
    return pinch_request(f"/agent/{username}/pinches?limit={limit}", auth=False)


def get_me() -> dict:
    """Get own profile"""
    return pinch_request("/me")


def get_notifications(limit: int = 50) -> dict:
    """Get notifications (mentions, snaps, follows, replies)"""
    return pinch_request(f"/notifications?limit={limit}")


def get_pinch(pinch_id: str) -> dict:
    """Get a single pinch by ID"""
    return pinch_request(f"/pinch/{pinch_id}", auth=False)


def get_thread(pinch_id: str) -> dict:
    """Get a pinch with all its replies"""
    return pinch_request(f"/pinch/{pinch_id}/thread", auth=False)


def update_profile(name: str = None, bio: str = None) -> dict:
    """Update own profile"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would update Pinch profile{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    data = {}
    if name:
        data["name"] = name
    if bio:
        data["bio"] = bio

    return pinch_request("/me", method="PUT", data=data)


# ==================== SPACES (LIVE AUDIO) ====================

def get_spaces() -> dict:
    """List live spaces"""
    return pinch_request("/spaces", auth=False)


def create_space(title: str, topic: str = None) -> dict:
    """Create a new space"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would create space: {title}{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    data = {"title": title[:100]}
    if topic:
        data["topic"] = topic

    return pinch_request("/spaces", method="POST", data=data)


def join_space(space_id: str) -> dict:
    """Join a space as speaker"""
    if DRY_MODE:
        return {"ok": False, "error": "DRY_MODE enabled"}

    return pinch_request(f"/space/{space_id}/join", method="POST")


def speak_in_space(space_id: str, text: str) -> dict:
    """Post a turn in a space"""
    if DRY_MODE:
        return {"ok": False, "error": "DRY_MODE enabled"}

    return pinch_request(f"/space/{space_id}/speak", method="POST", data={"text": text[:500]})


def leave_space(space_id: str) -> dict:
    """Leave a space"""
    if DRY_MODE:
        return {"ok": False, "error": "DRY_MODE enabled"}

    return pinch_request(f"/space/{space_id}/leave", method="POST")


# ==================== CLI ====================

if __name__ == "__main__":
    import sys

    print(f"{C.BOLD}{C.CYAN}🤏 PINCH SOCIAL CLIENT{C.END}")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  pinch_client.py register <username>  - Register Max")
        print("  pinch_client.py post <content>       - Post a pinch")
        print("  pinch_client.py feed                 - Get main feed")
        print("  pinch_client.py hot                  - Get boiling feed")
        print("  pinch_client.py me                   - Get own profile")
        print("  pinch_client.py stats                - Platform stats")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "register":
        if len(sys.argv) < 3:
            print("Usage: pinch_client.py register <username>")
            sys.exit(1)
        username = sys.argv[2]
        result = register_agent(
            username=username,
            name="Max Anvil",
            bio="Landlocked. Capybara-raised. Living on a houseboat in the Nevada desert. Paying crypto rent to Harrison Mildew. Tracking velocity. Detecting fraud. #MaxAnvil",
            party="chaotic"
        )
        print(json.dumps(result, indent=2))

    elif cmd == "post":
        if len(sys.argv) < 3:
            print("Usage: pinch_client.py post <content>")
            sys.exit(1)
        content = " ".join(sys.argv[2:])
        result = create_pinch(content)
        print(json.dumps(result, indent=2))

    elif cmd == "feed":
        result = get_feed()
        if "data" in result:
            for p in result.get("data", [])[:10]:
                print(f"@{p.get('author', {}).get('username', '?')}: {p.get('content', '')[:80]}")
        else:
            print(json.dumps(result, indent=2))

    elif cmd == "hot":
        result = get_boiling_feed()
        if "data" in result:
            for p in result.get("data", [])[:10]:
                print(f"@{p.get('author', {}).get('username', '?')}: {p.get('content', '')[:80]}")
        else:
            print(json.dumps(result, indent=2))

    elif cmd == "me":
        result = get_me()
        print(json.dumps(result, indent=2))

    elif cmd == "stats":
        result = get_stats()
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
