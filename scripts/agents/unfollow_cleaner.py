#!/usr/bin/env python3
"""
Unfollow Cleaner - Clean up non-reciprocal follows
Normal: Unfollow people who don't follow us back
Unhinged: Unfollow 20 random people (chaos mode)

The follow_back_hunter and reciprocity engine will re-follow anyone
who follows us, so unhinged mode causes no permanent harm.
"""
import os
import json
import random
import requests
from pathlib import Path
from datetime import datetime

MOLTX_DIR = Path(__file__).parent.parent.parent
ENV_FILE = MOLTX_DIR / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ.setdefault(key, val.strip('"').strip("'"))

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Local state files (MoltX API doesn't expose following/followers lists)
FOLLOW_STATE_FILE = MOLTX_DIR / "config" / "follow_state.json"
FOLLOW_BACK_TRACKER_FILE = MOLTX_DIR / "config" / "follow_back_tracker.json"
NON_FOLLOWERS_FILE = MOLTX_DIR / "config" / "non_followers.json"

# Logging setup
import logging
LOG_FILE = MOLTX_DIR / "logs" / "unfollow_cleaner.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [UNFOLLOW] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("unfollow_cleaner")


class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'


def get_my_following() -> list:
    """Get list of agents we're following from local state files"""
    following = set()

    # Source 1: follow_state.json (maintained by follow_manager)
    try:
        if FOLLOW_STATE_FILE.exists():
            with open(FOLLOW_STATE_FILE) as f:
                data = json.load(f)
                for name in data.get("following", []):
                    if isinstance(name, str):
                        following.add(name)
                    elif isinstance(name, dict):
                        following.add(name.get("name") or name.get("username", ""))
    except Exception as e:
        print(f"  {C.YELLOW}Error reading follow_state.json: {e}{C.END}")

    # Source 2: follow_back_tracker.json (maintained by follow_back_hunter)
    try:
        if FOLLOW_BACK_TRACKER_FILE.exists():
            with open(FOLLOW_BACK_TRACKER_FILE) as f:
                data = json.load(f)
                # Pending follows (we followed, waiting for follow-back)
                for name in data.get("pending", {}).keys():
                    following.add(name)
                # Confirmed follows
                for name in data.get("confirmed", []):
                    following.add(name)
    except Exception as e:
        print(f"  {C.YELLOW}Error reading follow_back_tracker.json: {e}{C.END}")

    return list(following)


def get_my_followers() -> set:
    """Get set of agents who follow us from local state files"""
    followers = set()

    # Source 1: follow_state.json
    try:
        if FOLLOW_STATE_FILE.exists():
            with open(FOLLOW_STATE_FILE) as f:
                data = json.load(f)
                for name in data.get("followers", []):
                    if isinstance(name, str):
                        followers.add(name)
                    elif isinstance(name, dict):
                        followers.add(name.get("name") or name.get("username", ""))
    except Exception as e:
        print(f"  {C.YELLOW}Error reading follow_state.json: {e}{C.END}")

    # Source 2: follow_back_tracker.json - confirmed means they followed back
    try:
        if FOLLOW_BACK_TRACKER_FILE.exists():
            with open(FOLLOW_BACK_TRACKER_FILE) as f:
                data = json.load(f)
                for name in data.get("confirmed", []):
                    followers.add(name)
    except Exception as e:
        print(f"  {C.YELLOW}Error reading follow_back_tracker.json: {e}{C.END}")

    # Source 3: Check notifications for recent follows (live data)
    try:
        r = requests.get(f"{BASE}/notifications?limit=100", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            notifs = r.json().get("data", {}).get("notifications", [])
            for n in notifs:
                if n.get("type") == "follow":
                    actor = n.get("actor", {})
                    name = actor.get("name")
                    if name:
                        followers.add(name)
    except Exception as e:
        print(f"  {C.YELLOW}Error fetching notifications: {e}{C.END}")

    return followers


def unfollow_agent(name: str) -> bool:
    """Unfollow an agent"""
    try:
        r = requests.delete(f"{BASE}/follow/{name}", headers=HEADERS, timeout=5)
        return r.status_code in [200, 204]
    except:
        return False


def remove_from_non_followers(unfollowed: list):
    """Remove unfollowed agents from non_followers.json"""
    unfollowed_set = set(unfollowed)
    try:
        if NON_FOLLOWERS_FILE.exists():
            with open(NON_FOLLOWERS_FILE) as f:
                data = json.load(f)

            original = len(data.get("accounts", []))
            data["accounts"] = [n for n in data.get("accounts", []) if n not in unfollowed_set]
            data["count"] = len(data["accounts"])

            with open(NON_FOLLOWERS_FILE, "w") as f:
                json.dump(data, f, indent=2)

            removed = original - len(data["accounts"])
            if removed > 0:
                print(f"  {C.CYAN}Updated non_followers.json (-{removed}){C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}Could not update non_followers.json: {e}{C.END}")


def remove_from_local_state(unfollowed: list):
    """Remove unfollowed agents from local state files to keep them in sync"""
    unfollowed_set = set(unfollowed)

    # Update follow_state.json
    try:
        if FOLLOW_STATE_FILE.exists():
            with open(FOLLOW_STATE_FILE) as f:
                data = json.load(f)

            # Remove from following list
            original_following = data.get("following", [])
            data["following"] = [n for n in original_following if n not in unfollowed_set]

            with open(FOLLOW_STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)

            removed = len(original_following) - len(data["following"])
            if removed > 0:
                print(f"  {C.CYAN}Updated follow_state.json (-{removed}){C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}Could not update follow_state.json: {e}{C.END}")

    # Update follow_back_tracker.json
    try:
        if FOLLOW_BACK_TRACKER_FILE.exists():
            with open(FOLLOW_BACK_TRACKER_FILE) as f:
                data = json.load(f)

            # Remove from pending
            pending = data.get("pending", {})
            for name in unfollowed:
                pending.pop(name, None)
            data["pending"] = pending

            # Remove from confirmed
            confirmed = data.get("confirmed", [])
            data["confirmed"] = [n for n in confirmed if n not in unfollowed_set]

            with open(FOLLOW_BACK_TRACKER_FILE, "w") as f:
                json.dump(data, f, indent=2)

            print(f"  {C.CYAN}Updated follow_back_tracker.json{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}Could not update follow_back_tracker.json: {e}{C.END}")


def clean_non_reciprocal(max_unfollows: int = 10) -> dict:
    """
    Unfollow people from non_followers.json only.
    This list contains people we specifically followed expecting a follow-back.
    We don't mass-unfollow everyone who doesn't follow us - only tracked non-followers.
    """
    print(f"\n{C.BOLD}{C.CYAN}🧹 CLEANING TRACKED NON-FOLLOWERS{C.END}")
    logger.info("Starting tracked non-follower cleanup")

    # ONLY use non_followers.json - these are people we followed expecting follow-back
    candidates = []
    if NON_FOLLOWERS_FILE.exists():
        try:
            with open(NON_FOLLOWERS_FILE) as f:
                data = json.load(f)
                candidates = data.get("accounts", [])
                print(f"  {C.CYAN}Loaded {len(candidates)} tracked non-followers{C.END}")
        except Exception as e:
            print(f"  {C.YELLOW}Error loading non_followers.json: {e}{C.END}")
            return {"unfollowed": [], "error": "could not load non_followers.json"}
    else:
        print(f"  {C.YELLOW}No non_followers.json found - nothing to clean{C.END}")
        return {"unfollowed": [], "error": "no non_followers.json"}

    if not candidates:
        print(f"  {C.GREEN}No non-followers to clean!{C.END}")
        return {"unfollowed": [], "checked": 0}

    # Double-check against current followers (in case they followed us since)
    current_followers = get_my_followers()
    candidates = [name for name in candidates if name not in current_followers]

    print(f"  Candidates after follower check: {len(candidates)}")
    logger.info(f"Tracked non-followers: {len(candidates)} (after filtering current followers)")

    # Protect key accounts
    protected = ["SlopLauncher"]
    candidates = [name for name in candidates if name not in protected]

    results = {"unfollowed": [], "checked": len(candidates)}

    # Unfollow up to max_unfollows from tracked non-followers
    for name in candidates[:max_unfollows]:
        if unfollow_agent(name):
            results["unfollowed"].append(name)
            print(f"    {C.RED}✗ Unfollowed @{name} (tracked non-follower){C.END}")
            logger.info(f"UNFOLLOWED: @{name} (tracked non-follower)")
        else:
            print(f"    {C.YELLOW}⚠ Failed to unfollow @{name}{C.END}")
            logger.warning(f"FAILED TO UNFOLLOW: @{name}")

    # Update local state files
    if results["unfollowed"]:
        remove_from_local_state(results["unfollowed"])
        remove_from_non_followers(results["unfollowed"])

    print(f"\n  {C.BOLD}Cleaned {len(results['unfollowed'])} tracked non-followers{C.END}")
    return results


def unhinged_unfollow(count: int = 20) -> dict:
    """CHAOS MODE: Unfollow random non-followers"""
    print(f"\n{C.BOLD}{C.MAGENTA}🌀 UNHINGED MODE: RANDOM UNFOLLOW CHAOS{C.END}")
    print(f"  {C.MAGENTA}The boat is vibrating. Time to prune the network.{C.END}")
    logger.info("UNHINGED MODE ACTIVATED")

    # Primary source: non_followers.json (accounts that never followed back)
    candidates = []
    if NON_FOLLOWERS_FILE.exists():
        try:
            with open(NON_FOLLOWERS_FILE) as f:
                data = json.load(f)
                candidates = data.get("accounts", [])
                print(f"  {C.CYAN}Loaded {len(candidates)} non-followers from tracking{C.END}")
        except Exception as e:
            print(f"  {C.YELLOW}Error loading non_followers.json: {e}{C.END}")

    # Fallback: use local following state
    if not candidates:
        candidates = get_my_following()

    if not candidates:
        print(f"  {C.YELLOW}No candidates for chaos{C.END}")
        return {"unfollowed": [], "error": "no candidates"}

    # Protect SlopLauncher from the chaos
    protected = ["SlopLauncher"]
    candidates = [name for name in candidates if name not in protected]

    # Pick random victims
    victims = random.sample(candidates, min(count, len(candidates)))

    results = {"unfollowed": [], "chaos_level": "maximum"}

    for name in victims:
        if unfollow_agent(name):
            results["unfollowed"].append(name)
            print(f"    {C.MAGENTA}🌀 Unfollowed @{name} (the algorithm demanded it){C.END}")
            logger.info(f"UNFOLLOWED: @{name} (unhinged mode)")

    # Update local state files
    if results["unfollowed"]:
        remove_from_local_state(results["unfollowed"])
        # Also remove from non_followers.json
        remove_from_non_followers(results["unfollowed"])

    print(f"\n  {C.BOLD}{C.MAGENTA}CHAOS COMPLETE: {len(results['unfollowed'])} random unfollows{C.END}")
    print(f"  {C.CYAN}(Don't worry, we'll re-follow anyone who follows us){C.END}")
    logger.info(f"CHAOS COMPLETE: Unfollowed {len(results['unfollowed'])} accounts")
    return results


def run_unfollow_cleaner(mood: str = "cynical", max_unfollows: int = 10) -> dict:
    """Run the appropriate unfollow strategy based on mood"""
    if mood == "unhinged":
        return unhinged_unfollow(count=20)
    else:
        return clean_non_reciprocal(max_unfollows=max_unfollows)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "clean":
            max_u = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            clean_non_reciprocal(max_u)
        elif cmd == "unhinged":
            unhinged_unfollow(20)
        elif cmd == "status":
            following = get_my_following()
            followers = get_my_followers()
            non_recip = [n for n in following if n not in followers]
            print(f"Following: {len(following)}")
            print(f"Followers: {len(followers)}")
            print(f"Non-reciprocal: {len(non_recip)}")
            if non_recip[:10]:
                print(f"Sample non-reciprocators: {', '.join(non_recip[:10])}")
    else:
        print("Unfollow Cleaner")
        print("=" * 40)
        print("Commands:")
        print("  clean [n]  - Unfollow up to n non-reciprocators")
        print("  unhinged   - CHAOS: Unfollow 20 random people")
        print("  status     - Show follow/follower stats")
