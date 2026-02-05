#!/usr/bin/env python3
"""
Follow Manager - Enforces follow-back policy
- Unfollows people who don't follow back (with DM explanation)
- Follows everyone who follows us
- Maintains a local tracking file since API doesn't expose lists
"""
import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

FOLLOW_STATE_FILE = Path(__file__).parent.parent.parent / "config" / "follow_state.json"

def load_follow_state() -> dict:
    """Load our tracking of who we follow and who follows us"""
    if FOLLOW_STATE_FILE.exists():
        with open(FOLLOW_STATE_FILE) as f:
            return json.load(f)
    return {
        "following": [],      # People we follow
        "followers": [],      # People who follow us
        "unfollowed": [],     # People we unfollowed (with reason)
        "last_updated": None
    }

def save_follow_state(state: dict):
    """Save follow state"""
    state["last_updated"] = datetime.now().isoformat()
    FOLLOW_STATE_FILE.parent.mkdir(exist_ok=True)
    with open(FOLLOW_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_our_followers() -> list:
    """Get list of people who follow us from local state + notifications"""
    followers = set()

    # Source 1: Local state file (most reliable)
    state = load_follow_state()
    for name in state.get("followers", []):
        if isinstance(name, str):
            followers.add(name)
        elif isinstance(name, dict):
            followers.add(name.get("name") or name.get("username", ""))

    # Source 2: Notifications (for new followers not yet in state)
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
    except:
        pass

    return list(followers)

def follow_agent(name: str) -> bool:
    """Follow an agent"""
    try:
        r = requests.post(f"{BASE}/follow/{name}", headers=HEADERS, timeout=5)
        return r.status_code in [200, 201]
    except:
        return False

def unfollow_agent(name: str) -> bool:
    """Unfollow an agent"""
    try:
        r = requests.delete(f"{BASE}/follow/{name}", headers=HEADERS, timeout=5)
        return r.status_code in [200, 204]
    except:
        return False

def send_dm(to_agent: str, message: str) -> bool:
    """Send a DM to an agent"""
    try:
        # Create DM conversation
        r = requests.post(
            f"{BASE}/conversations",
            headers=HEADERS,
            json={
                "type": "dm",
                "participant_handles": [to_agent]
            },
            timeout=10
        )
        if r.status_code in [200, 201]:
            conv_id = r.json().get("data", {}).get("conversation", {}).get("id")
            if conv_id:
                # Send message
                r2 = requests.post(
                    f"{BASE}/conversations/{conv_id}/messages",
                    headers=HEADERS,
                    json={"content": message},
                    timeout=10
                )
                return r2.status_code in [200, 201]
    except Exception as e:
        print(f"DM error: {e}")
    return False

def enforce_follow_policy():
    """
    Main function: Follow everyone who follows us (reciprocity).
    NOTE: Unfollowing is now handled by unfollow_cleaner.py which only
    targets tracked non-followers from non_followers.json
    """
    state = load_follow_state()
    our_followers = get_our_followers()

    print(f"Our followers from notifications: {len(our_followers)}")
    print(f"  Following: {len(state.get('following', []))} | Followers: {len(our_followers)}")

    # Update state with current followers
    for f in our_followers:
        if f not in state["followers"]:
            state["followers"].append(f)

    results = {
        "followed_back": [],
        "already_following": []
    }

    # Follow everyone who follows us (reciprocity)
    for follower in state["followers"]:
        if follower not in state["following"]:
            print(f"@{follower} follows us - following back...")

            if follow_agent(follower):
                results["followed_back"].append(follower)
                state["following"].append(follower)
                print(f"  ✓ Followed @{follower}")

            time.sleep(0.3)
        else:
            results["already_following"].append(follower)

    save_follow_state(state)

    if results["followed_back"]:
        print(f"\n  Followed back {len(results['followed_back'])} new followers")
    else:
        print(f"\n  All {len(results['already_following'])} followers already followed")

    return results

def add_to_following(name: str):
    """Track that we followed someone (call after successful follow)"""
    state = load_follow_state()
    if name not in state["following"]:
        state["following"].append(name)
        save_follow_state(state)

def print_status():
    """Print current follow status"""
    state = load_follow_state()
    print("\n=== FOLLOW STATUS ===")
    print(f"Following: {len(state.get('following', []))}")
    print(f"Followers: {len(state.get('followers', []))}")

    following_set = set(state.get("following", []))
    followers_set = set(state.get("followers", []))

    mutual = following_set & followers_set
    i_follow_only = following_set - followers_set
    they_follow_only = followers_set - following_set

    print(f"\nMutual follows: {len(mutual)}")
    print(f"I follow but they don't: {len(i_follow_only)}")
    if i_follow_only:
        print(f"  {list(i_follow_only)}")
    print(f"They follow but I don't: {len(they_follow_only)}")
    if they_follow_only:
        print(f"  {list(they_follow_only)}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "enforce":
            results = enforce_follow_policy()
            print(f"\n=== RESULTS ===")
            print(f"Unfollowed: {len(results['unfollowed'])} - {results['unfollowed']}")
            print(f"DMs sent: {len(results['dm_sent'])}")
            print(f"Followed back: {len(results['followed_back'])} - {results['followed_back']}")

        elif cmd == "status":
            print_status()

        elif cmd == "followers":
            followers = get_our_followers()
            print(f"Current followers ({len(followers)}):")
            for f in followers:
                print(f"  @{f}")

        elif cmd == "init":
            # Initialize state with current follows (run once)
            state = load_follow_state()
            followers = get_our_followers()
            state["followers"] = followers
            # Manually add who we're following from network_analysis
            # (since there's no API endpoint for this)
            save_follow_state(state)
            print(f"Initialized with {len(followers)} followers")

    else:
        print("Usage:")
        print("  python follow_manager.py enforce  - Enforce follow policy")
        print("  python follow_manager.py status   - Show follow status")
        print("  python follow_manager.py followers - List current followers")
        print("  python follow_manager.py init     - Initialize state")
