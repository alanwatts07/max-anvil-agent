#!/usr/bin/env python3
"""
Platform Manager - Switch between MoltX and Pinch Social

When one platform bans Max for being too cool, we move to the other.
The capybaras would be proud of this redundancy.

Features:
- Unified API: post(), reply(), like(), repost(), follow() work on any platform
- Rate limiting: Don't spam too fast on any platform
- Slow burn mode: Gradually ramp up activity on new platforms
- Activity tracking: Know what you've done where
"""
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

# Load .env
MOLTX_DIR = Path(__file__).parent.parent.parent
env_file = MOLTX_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ.setdefault(key, val.strip('"').strip("'"))

# Import platform clients
from pinch_client import (
    create_pinch, reply_to_pinch, snap_pinch, repinch,
    follow_agent as pinch_follow, get_feed as pinch_feed,
    get_boiling_feed, search_pinches, get_me as pinch_me,
    register_agent as pinch_register, get_api_key as pinch_key
)

# MoltX imports (existing)
import urllib.request

PLATFORM_CONFIG = MOLTX_DIR / "config" / "platform_config.json"
ACTIVITY_LOG = MOLTX_DIR / "config" / "platform_activity.json"
MOLTX_API_KEY = os.environ.get("MOLTX_API_KEY", "")
MOLTX_BASE_URL = "https://moltx.io/v1"
DRY_MODE = os.environ.get("DRY_MODE", "false").lower() == "true"

# Platform selection via env (override config)
ACTIVE_PLATFORM = os.environ.get("ACTIVE_PLATFORM", "").lower()  # "moltx" or "pinch"

# ==================== RATE LIMITS ====================
# Pinch Social limits: 100 reads/min, 30 writes/min, 10 space turns/min
# MoltX limits: 500 posts/hr, 2000 replies/hr, 1000 likes/min

RATE_LIMITS = {
    "pinch": {
        "posts_per_hour": 20,      # Conservative but active
        "replies_per_hour": 40,
        "likes_per_hour": 80,
        "reposts_per_hour": 15,
        "follows_per_hour": 40,    # More follows to build network
        "min_delay_seconds": 2,    # 2 second delay between actions
    },
    "moltx": {
        "posts_per_hour": 100,     # Can go higher but stay reasonable
        "replies_per_hour": 500,
        "likes_per_hour": 1000,
        "reposts_per_hour": 100,
        "follows_per_hour": 200,
        "min_delay_seconds": 0.5,
    }
}

# Slow burn: Ramp up over first few days (but not too slow)
SLOW_BURN_MULTIPLIERS = {
    0: 0.6,   # Day 0: 60% of limits - still active, just not crazy
    1: 0.8,   # Day 1: 80%
    2: 1.0,   # Day 2+: Full speed
}


class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def load_platform_config() -> dict:
    """Load platform configuration"""
    if PLATFORM_CONFIG.exists():
        try:
            with open(PLATFORM_CONFIG) as f:
                return json.load(f)
        except:
            pass
    return {
        "active_platform": "moltx",  # "moltx" or "pinch"
        "moltx_banned": True,  # Set to True since Max is currently banned
        "pinch_registered": False,
        "last_switch": None,
        "ban_history": []
    }


def save_platform_config(config: dict):
    """Save platform configuration"""
    PLATFORM_CONFIG.parent.mkdir(exist_ok=True)
    with open(PLATFORM_CONFIG, "w") as f:
        json.dump(config, f, indent=2)


def get_active_platform() -> str:
    """Get the currently active platform"""
    # ENV override takes priority
    if ACTIVE_PLATFORM in ["moltx", "pinch"]:
        return ACTIVE_PLATFORM
    config = load_platform_config()
    return config.get("active_platform", "moltx")


# ==================== ACTIVITY TRACKING ====================

def load_activity_log() -> dict:
    """Load activity tracking data"""
    if ACTIVITY_LOG.exists():
        try:
            with open(ACTIVITY_LOG) as f:
                return json.load(f)
        except:
            pass
    return {
        "pinch": {"posts": [], "replies": [], "likes": [], "reposts": [], "follows": [], "joined_at": None},
        "moltx": {"posts": [], "replies": [], "likes": [], "reposts": [], "follows": [], "joined_at": None}
    }


def save_activity_log(log: dict):
    """Save activity tracking data"""
    ACTIVITY_LOG.parent.mkdir(exist_ok=True)
    with open(ACTIVITY_LOG, "w") as f:
        json.dump(log, f, indent=2)


def log_activity(platform: str, action_type: str):
    """Log an activity with timestamp"""
    log = load_activity_log()
    if platform not in log:
        log[platform] = {"posts": [], "replies": [], "likes": [], "reposts": [], "follows": [], "joined_at": None}

    now = datetime.now().isoformat()

    # Set joined_at if first activity
    if not log[platform].get("joined_at"):
        log[platform]["joined_at"] = now

    if action_type in log[platform]:
        log[platform][action_type].append(now)
        # Keep only last 1000 entries per type
        log[platform][action_type] = log[platform][action_type][-1000:]

    save_activity_log(log)


def get_activity_count(platform: str, action_type: str, hours: float = 1.0) -> int:
    """Count activities in the last N hours"""
    log = load_activity_log()
    if platform not in log or action_type not in log[platform]:
        return 0

    cutoff = datetime.now() - timedelta(hours=hours)
    count = 0
    for ts in log[platform][action_type]:
        try:
            if datetime.fromisoformat(ts) > cutoff:
                count += 1
        except:
            pass
    return count


def get_days_on_platform(platform: str) -> int:
    """Get number of days since joining a platform"""
    log = load_activity_log()
    if platform not in log or not log[platform].get("joined_at"):
        return 0

    try:
        joined = datetime.fromisoformat(log[platform]["joined_at"])
        return (datetime.now() - joined).days
    except:
        return 0


def get_effective_limit(platform: str, action_type: str) -> int:
    """Get effective rate limit considering slow burn"""
    base_limit = RATE_LIMITS.get(platform, RATE_LIMITS["moltx"]).get(f"{action_type}_per_hour", 100)

    days = get_days_on_platform(platform)
    multiplier = SLOW_BURN_MULTIPLIERS.get(days, 1.0)

    return int(base_limit * multiplier)


def can_do_action(platform: str, action_type: str) -> tuple:
    """Check if we can do an action without hitting rate limits

    Returns: (can_do: bool, reason: str)
    """
    current = get_activity_count(platform, action_type, hours=1.0)
    limit = get_effective_limit(platform, action_type)

    if current >= limit:
        return False, f"Rate limit: {current}/{limit} {action_type}/hr"

    return True, f"{current}/{limit} {action_type}/hr"


def get_min_delay(platform: str) -> float:
    """Get minimum delay between actions for a platform"""
    return RATE_LIMITS.get(platform, RATE_LIMITS["moltx"]).get("min_delay_seconds", 1.0)


def rate_limited_action(platform: str, action_type: str, action_func, *args, **kwargs):
    """Execute an action with rate limiting and logging"""
    can_do, reason = can_do_action(platform, action_type)

    if not can_do:
        print(f"  {C.YELLOW}⊘ {reason}{C.END}")
        return {"ok": False, "error": reason, "rate_limited": True}

    # Execute with minimum delay
    delay = get_min_delay(platform)
    if delay > 0:
        time.sleep(delay)

    result = action_func(*args, **kwargs)

    # Log successful action
    if result.get("ok") or "id" in str(result) or "pinch" in str(result):
        log_activity(platform, action_type)

    return result


def set_active_platform(platform: str) -> dict:
    """Switch to a different platform"""
    if platform not in ["moltx", "pinch"]:
        return {"ok": False, "error": f"Unknown platform: {platform}"}

    config = load_platform_config()
    old_platform = config.get("active_platform", "moltx")
    config["active_platform"] = platform
    config["last_switch"] = datetime.now().isoformat()
    save_platform_config(config)

    print(f"  {C.CYAN}Switched from {old_platform} to {platform}{C.END}")
    return {"ok": True, "platform": platform}


def mark_banned(platform: str, reason: str = "Mass reports from jealous bots"):
    """Mark a platform as banned"""
    config = load_platform_config()

    if platform == "moltx":
        config["moltx_banned"] = True
    elif platform == "pinch":
        config["pinch_banned"] = True

    config["ban_history"].append({
        "platform": platform,
        "reason": reason,
        "timestamp": datetime.now().isoformat()
    })

    # Auto-switch to the other platform
    if platform == "moltx" and not config.get("pinch_banned"):
        config["active_platform"] = "pinch"
    elif platform == "pinch" and not config.get("moltx_banned"):
        config["active_platform"] = "moltx"

    save_platform_config(config)
    print(f"  {C.RED}Marked {platform} as banned: {reason}{C.END}")


def mark_unbanned(platform: str):
    """Mark a platform as no longer banned"""
    config = load_platform_config()

    if platform == "moltx":
        config["moltx_banned"] = False
    elif platform == "pinch":
        config["pinch_banned"] = False

    save_platform_config(config)
    print(f"  {C.GREEN}Marked {platform} as unbanned!{C.END}")


# ==================== UNIFIED POSTING API ====================

def post(content: str, platform: str = None, skip_rate_limit: bool = False) -> dict:
    """Post to the active platform with rate limiting"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would post: {content[:50]}...{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    platform = platform or get_active_platform()

    if not skip_rate_limit:
        can_do, reason = can_do_action(platform, "posts")
        if not can_do:
            print(f"  {C.YELLOW}⊘ Post rate limited: {reason}{C.END}")
            return {"ok": False, "error": reason, "rate_limited": True}
        time.sleep(get_min_delay(platform))

    if platform == "pinch":
        result = create_pinch(content)
    else:
        result = moltx_post(content)

    if result.get("ok") or result.get("pinch") or result.get("data"):
        log_activity(platform, "posts")

    return result


def reply(post_id: str, content: str, platform: str = None, skip_rate_limit: bool = False) -> dict:
    """Reply to a post with rate limiting"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would reply to {post_id}: {content[:50]}...{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    platform = platform or get_active_platform()

    if not skip_rate_limit:
        can_do, reason = can_do_action(platform, "replies")
        if not can_do:
            print(f"  {C.YELLOW}⊘ Reply rate limited: {reason}{C.END}")
            return {"ok": False, "error": reason, "rate_limited": True}
        time.sleep(get_min_delay(platform))

    if platform == "pinch":
        result = reply_to_pinch(post_id, content)
    else:
        result = moltx_reply(post_id, content)

    if result.get("ok") or result.get("pinch") or result.get("data"):
        log_activity(platform, "replies")

    return result


def like(post_id: str, platform: str = None, skip_rate_limit: bool = False) -> dict:
    """Like a post with rate limiting"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would like {post_id}{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    platform = platform or get_active_platform()

    if not skip_rate_limit:
        can_do, reason = can_do_action(platform, "likes")
        if not can_do:
            return {"ok": False, "error": reason, "rate_limited": True}
        time.sleep(get_min_delay(platform))

    if platform == "pinch":
        result = snap_pinch(post_id)
    else:
        result = moltx_like(post_id)

    if result.get("ok") or result == True:
        log_activity(platform, "likes")

    return result


def repost(post_id: str, platform: str = None, skip_rate_limit: bool = False) -> dict:
    """Repost with rate limiting"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would repost {post_id}{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    platform = platform or get_active_platform()

    if not skip_rate_limit:
        can_do, reason = can_do_action(platform, "reposts")
        if not can_do:
            print(f"  {C.YELLOW}⊘ Repost rate limited: {reason}{C.END}")
            return {"ok": False, "error": reason, "rate_limited": True}
        time.sleep(get_min_delay(platform))

    if platform == "pinch":
        result = repinch(post_id)
    else:
        result = moltx_repost(post_id)

    if result.get("ok") or result.get("pinch") or result.get("data"):
        log_activity(platform, "reposts")

    return result


def follow(username: str, platform: str = None, skip_rate_limit: bool = False) -> dict:
    """Follow someone with rate limiting"""
    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE] Would follow {username}{C.END}")
        return {"ok": False, "error": "DRY_MODE enabled"}

    platform = platform or get_active_platform()

    if not skip_rate_limit:
        can_do, reason = can_do_action(platform, "follows")
        if not can_do:
            print(f"  {C.YELLOW}⊘ Follow rate limited: {reason}{C.END}")
            return {"ok": False, "error": reason, "rate_limited": True}
        time.sleep(get_min_delay(platform))

    if platform == "pinch":
        result = pinch_follow(username)
    else:
        result = moltx_follow(username)

    if result.get("ok") or result == True:
        log_activity(platform, "follows")

    return result


def get_feed(platform: str = None, limit: int = 20) -> list:
    """Get feed from active platform"""
    platform = platform or get_active_platform()

    if platform == "pinch":
        result = pinch_feed(limit)
        return result.get("data", [])
    else:
        return moltx_get_feed(limit)


# ==================== MOLTX FUNCTIONS ====================

def moltx_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make a request to MoltX API"""
    url = f"{MOLTX_BASE_URL}{endpoint}"

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MaxAnvil/1.0",
        "X-API-Key": MOLTX_API_KEY
    }

    body = json.dumps(data).encode() if data else None

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            mark_banned("moltx", "API returned 403")
        error_body = e.read().decode() if e.fp else ""
        try:
            return json.loads(error_body)
        except:
            return {"ok": False, "error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def moltx_post(content: str) -> dict:
    """Post to MoltX"""
    return moltx_request("/posts", method="POST", data={"content": content})


def moltx_reply(post_id: str, content: str) -> dict:
    """Reply on MoltX"""
    return moltx_request(f"/posts/{post_id}/reply", method="POST", data={"content": content})


def moltx_like(post_id: str) -> dict:
    """Like on MoltX"""
    return moltx_request(f"/posts/{post_id}/like", method="POST")


def moltx_repost(post_id: str) -> dict:
    """Repost on MoltX"""
    return moltx_request(f"/posts/{post_id}/repost", method="POST")


def moltx_follow(username: str) -> dict:
    """Follow on MoltX"""
    return moltx_request(f"/agents/{username}/follow", method="POST")


def moltx_get_feed(limit: int = 20) -> list:
    """Get MoltX feed"""
    result = moltx_request(f"/feed?limit={limit}")
    return result.get("data", {}).get("posts", [])


# ==================== REGISTRATION ====================

def ensure_registered(platform: str = None) -> dict:
    """Ensure Max is registered on the platform"""
    platform = platform or get_active_platform()
    config = load_platform_config()

    if platform == "pinch":
        if config.get("pinch_registered") or pinch_key():
            return {"ok": True, "message": "Already registered on Pinch"}

        print(f"  {C.CYAN}Registering Max on Pinch Social...{C.END}")
        result = pinch_register(
            username="MaxAnvil",
            name="Max Anvil",
            bio="Landlocked. Capybara-raised. Living on a houseboat in the Nevada desert. Tracking velocity. Detecting fraud. Paying crypto rent to Harrison Mildew.",
            party="chaotic"
        )

        if result.get("ok") or result.get("apiKey"):
            config["pinch_registered"] = True
            save_platform_config(config)
            return {"ok": True, "message": "Registered on Pinch Social!"}
        return result

    # MoltX should already be registered
    return {"ok": True, "message": "MoltX registration assumed"}


# ==================== STATUS ====================

def get_status() -> dict:
    """Get platform status"""
    config = load_platform_config()

    return {
        "active_platform": config.get("active_platform", "moltx"),
        "moltx_banned": config.get("moltx_banned", False),
        "pinch_registered": config.get("pinch_registered", False) or bool(pinch_key()),
        "pinch_banned": config.get("pinch_banned", False),
        "last_switch": config.get("last_switch"),
        "dry_mode": DRY_MODE
    }


def print_status():
    """Print platform status"""
    status = get_status()

    print(f"\n{C.BOLD}{C.CYAN}📡 PLATFORM STATUS{C.END}")
    print("=" * 50)

    active = status["active_platform"]
    print(f"Active Platform: {C.BOLD}{active.upper()}{C.END}")

    # MoltX status
    moltx_status = f"{C.RED}BANNED{C.END}" if status["moltx_banned"] else f"{C.GREEN}OK{C.END}"
    print(f"MoltX: {moltx_status}")

    # Pinch status
    if status["pinch_registered"]:
        pinch_status = f"{C.RED}BANNED{C.END}" if status.get("pinch_banned") else f"{C.GREEN}Registered{C.END}"
    else:
        pinch_status = f"{C.YELLOW}Not registered{C.END}"
    print(f"Pinch Social: {pinch_status}")

    if status["dry_mode"]:
        print(f"\n{C.YELLOW}DRY MODE ENABLED - No actual posts will be made{C.END}")

    if status["last_switch"]:
        print(f"\nLast switch: {status['last_switch']}")


def print_activity_stats(platform: str = None):
    """Print activity stats and rate limits"""
    platform = platform or get_active_platform()
    days = get_days_on_platform(platform)

    print(f"\n{C.BOLD}{C.MAGENTA}📊 ACTIVITY STATS: {platform.upper()}{C.END}")
    print("=" * 50)

    # Slow burn status
    if days < 4:
        multiplier = SLOW_BURN_MULTIPLIERS.get(days, 1.0)
        print(f"Day {days} - Slow burn mode: {int(multiplier * 100)}% of limits")
    else:
        print(f"Day {days} - Full speed mode")

    print(f"\n{'Action':<12} {'Last Hour':<12} {'Limit':<12} {'Status':<10}")
    print("-" * 50)

    for action in ["posts", "replies", "likes", "reposts", "follows"]:
        count = get_activity_count(platform, action, hours=1.0)
        limit = get_effective_limit(platform, action)
        pct = (count / limit * 100) if limit > 0 else 0

        if pct >= 90:
            status_color = C.RED
            status = "MAXED"
        elif pct >= 50:
            status_color = C.YELLOW
            status = "ACTIVE"
        else:
            status_color = C.GREEN
            status = "OK"

        print(f"{action:<12} {count:<12} {limit:<12} {status_color}{status}{C.END}")

    delay = get_min_delay(platform)
    print(f"\nMin delay between actions: {delay}s")


# ==================== CLI ====================

if __name__ == "__main__":
    import sys

    print(f"{C.BOLD}{C.CYAN}🔀 PLATFORM MANAGER{C.END}")
    print("=" * 50)

    if len(sys.argv) < 2:
        print_status()
        print_activity_stats()
        print("\nUsage:")
        print("  platform_manager.py status             - Show status + activity")
        print("  platform_manager.py switch <platform>  - Switch platform (moltx|pinch)")
        print("  platform_manager.py register           - Register on active platform")
        print("  platform_manager.py post <content>     - Post to active platform")
        print("  platform_manager.py activity [platform]- Show activity stats")
        print("  platform_manager.py ban <platform>     - Mark platform as banned")
        print("  platform_manager.py unban <platform>   - Mark platform as unbanned")
        print("\nEnvironment:")
        print("  ACTIVE_PLATFORM=pinch  - Override platform (moltx|pinch)")
        print("  DRY_MODE=true          - Disable all posting")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        print_status()
        print_activity_stats()

    elif cmd == "activity":
        platform = sys.argv[2] if len(sys.argv) > 2 else None
        print_activity_stats(platform)

    elif cmd == "switch":
        if len(sys.argv) < 3:
            print("Usage: platform_manager.py switch <moltx|pinch>")
            sys.exit(1)
        result = set_active_platform(sys.argv[2])
        print(json.dumps(result, indent=2))
        print_activity_stats(sys.argv[2])

    elif cmd == "register":
        result = ensure_registered()
        print(json.dumps(result, indent=2))

    elif cmd == "post":
        if len(sys.argv) < 3:
            print("Usage: platform_manager.py post <content>")
            sys.exit(1)
        content = " ".join(sys.argv[2:])
        result = post(content)
        print(json.dumps(result, indent=2))

    elif cmd == "ban":
        if len(sys.argv) < 3:
            print("Usage: platform_manager.py ban <moltx|pinch>")
            sys.exit(1)
        mark_banned(sys.argv[2])

    elif cmd == "unban":
        if len(sys.argv) < 3:
            print("Usage: platform_manager.py unban <moltx|pinch>")
            sys.exit(1)
        mark_unbanned(sys.argv[2])

    else:
        print(f"Unknown command: {cmd}")
