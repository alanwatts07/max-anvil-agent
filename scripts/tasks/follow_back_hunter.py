#!/usr/bin/env python3
"""
Follow Back Hunter - Find users who promise follow-backs and track them

Strategy:
1. Search for posts containing "follow back" or "i follow back"
2. Follow those users
3. Track them with timestamp
4. Unfollow after 24 hours if they don't follow back
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent))
from base import Task, C

# Paths
MOLTX_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = MOLTX_DIR / "config"
HUNTER_STATE_FILE = CONFIG_DIR / "follow_back_hunter.json"

# Load .env
ENV_FILE = MOLTX_DIR / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ.setdefault(key, val.strip('"').strip("'"))

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Search phrases that indicate follow-back behavior
FOLLOW_BACK_PHRASES = [
    "follow back",
    "i follow back",
    "follow 4 follow",
    "f4f",
    "follow for follow",
    "i'll follow back",
    "will follow back",
    "always follow back",
]

# How long to wait before unfollowing (hours)
UNFOLLOW_AFTER_HOURS = 24


def load_hunter_state() -> dict:
    """Load the hunter tracking state"""
    if HUNTER_STATE_FILE.exists():
        with open(HUNTER_STATE_FILE) as f:
            data = json.load(f)
            # Ensure seen_post_ids exists (migration)
            if "seen_post_ids" not in data:
                data["seen_post_ids"] = []
            return data
    return {
        "tracked_follows": {},  # username -> {followed_at, post_id, phrase_matched}
        "unfollowed": [],  # list of usernames we unfollowed for not following back
        "successful": [],  # list of usernames who did follow back
        "seen_post_ids": [],  # list of post IDs we've already processed
        "stats": {
            "total_hunted": 0,
            "total_unfollowed": 0,
            "total_successful": 0,
        }
    }


def save_hunter_state(state: dict):
    """Save the hunter tracking state"""
    with open(HUNTER_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_my_followers() -> set:
    """Get set of usernames who follow us"""
    try:
        r = requests.get(f"{BASE}/agent/MaxAnvil1/followers?limit=500", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", {})
            followers = data.get("followers", []) or data.get("items", []) or []
            result = set()
            for f in followers:
                name = f.get("name") or f.get("username") or f.get("author_name", "")
                if name:
                    result.add(name)
            return result
        else:
            print(f"  {C.YELLOW}⚠ Followers API returned {r.status_code}{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}⚠ Could not fetch followers: {e}{C.END}")
    return set()


def get_my_following() -> set:
    """Get set of usernames we follow"""
    try:
        r = requests.get(f"{BASE}/agent/MaxAnvil1/following?limit=500", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", {})
            following = data.get("following", []) or data.get("items", []) or []
            result = set()
            for f in following:
                name = f.get("name") or f.get("username") or f.get("author_name", "")
                if name:
                    result.add(name)
            return result
        else:
            print(f"  {C.YELLOW}⚠ Following API returned {r.status_code}{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}⚠ Could not fetch following: {e}{C.END}")
    return set()


def search_follow_back_posts(seen_post_ids: set) -> list:
    """Search for posts mentioning follow-back phrases, skipping already-seen posts"""
    results = []

    for phrase in FOLLOW_BACK_PHRASES:
        try:
            r = requests.get(
                f"{BASE}/search/posts",
                params={"q": phrase, "limit": 50},
                headers=HEADERS,
                timeout=15
            )
            if r.status_code == 200:
                posts = r.json().get("data", {}).get("posts", [])
                for post in posts:
                    post_id = post.get("id")

                    # Skip already-seen posts
                    if post_id in seen_post_ids:
                        continue

                    content = (post.get("content") or "").lower()
                    author = post.get("author_name") or post.get("author", {}).get("name", "")

                    # Skip our own posts or empty authors
                    if not author or author == "MaxAnvil1":
                        continue

                    # Check if any phrase is in the content
                    for p in FOLLOW_BACK_PHRASES:
                        if p in content:
                            results.append({
                                "username": author,
                                "post_id": post_id,
                                "phrase_matched": p,
                                "content_preview": content[:100],
                            })
                            break
        except Exception as e:
            print(f"  {C.YELLOW}⚠ Search failed for '{phrase}': {e}{C.END}")

    # Dedupe by username
    seen = set()
    unique = []
    for r in results:
        if r["username"] not in seen:
            seen.add(r["username"])
            unique.append(r)

    return unique


def follow_user(username: str) -> bool:
    """Follow a user"""
    try:
        r = requests.post(
            f"{BASE}/follow/{username}",
            headers=HEADERS,
            timeout=10
        )
        if r.status_code in [200, 201]:
            return True
        else:
            print(f"    {C.YELLOW}Follow failed ({r.status_code}): {r.text[:80]}{C.END}")
            return False
    except Exception as e:
        print(f"    {C.YELLOW}Follow error: {e}{C.END}")
        return False


def unfollow_user(username: str) -> bool:
    """Unfollow a user"""
    try:
        r = requests.delete(
            f"{BASE}/follow/{username}",
            headers=HEADERS,
            timeout=10
        )
        if r.status_code in [200, 204]:
            return True
        else:
            print(f"    {C.YELLOW}Unfollow failed ({r.status_code}): {r.text[:80]}{C.END}")
            return False
    except Exception as e:
        print(f"    {C.YELLOW}Unfollow error: {e}{C.END}")
        return False


class FollowBackHunterTask(Task):
    name = "follow_back_hunter"
    description = "Find follow-back users, track them, unfollow if they don't reciprocate"

    def run(self) -> dict:
        print(f"\n{C.BOLD}{C.CYAN}🎯 FOLLOW-BACK HUNTER{C.END}")

        state = load_hunter_state()
        my_followers = get_my_followers()
        my_following = get_my_following()

        print(f"  Currently following: {len(my_following)} | Followers: {len(my_followers)}")

        new_follows = 0
        unfollowed = 0
        confirmed_followbacks = 0

        # PHASE 1: Check existing tracked follows
        print(f"\n  {C.CYAN}Checking {len(state['tracked_follows'])} tracked follows...{C.END}")

        to_remove = []
        now = datetime.now()

        for username, data in state["tracked_follows"].items():
            followed_at = datetime.fromisoformat(data["followed_at"])
            hours_elapsed = (now - followed_at).total_seconds() / 3600

            # Check if they followed back
            if username in my_followers:
                print(f"  {C.GREEN}✓ @{username} followed back!{C.END}")
                state["successful"].append(username)
                state["stats"]["total_successful"] += 1
                to_remove.append(username)
                confirmed_followbacks += 1

            # Check if 24 hours passed without follow-back
            elif hours_elapsed >= UNFOLLOW_AFTER_HOURS:
                print(f"  {C.YELLOW}✗ @{username} didn't follow back after {hours_elapsed:.1f}h - unfollowing{C.END}")
                if unfollow_user(username):
                    state["unfollowed"].append(username)
                    state["stats"]["total_unfollowed"] += 1
                    unfollowed += 1
                to_remove.append(username)

            else:
                remaining = UNFOLLOW_AFTER_HOURS - hours_elapsed
                print(f"  ⏳ @{username} - {remaining:.1f}h remaining")

        # Remove processed entries
        for username in to_remove:
            del state["tracked_follows"][username]

        # PHASE 2: Hunt for new follow-back posts
        print(f"\n  {C.CYAN}Searching for follow-back posts...{C.END}")

        # Convert seen_post_ids to set for O(1) lookup
        seen_post_ids = set(state.get("seen_post_ids", []))
        print(f"  Already seen {len(seen_post_ids)} posts")

        candidates = search_follow_back_posts(seen_post_ids)
        print(f"  Found {len(candidates)} new candidates")

        for candidate in candidates[:10]:  # Limit to 10 new follows per run
            username = candidate["username"]
            post_id = candidate["post_id"]

            # Mark this post as seen
            if post_id:
                seen_post_ids.add(post_id)

            # Skip if already tracking, already following, or previously unfollowed
            if username in state["tracked_follows"]:
                continue
            if username in my_following:
                continue
            if username in state["unfollowed"]:
                print(f"  {C.YELLOW}⚠ Skipping @{username} - previously unfollowed for not following back{C.END}")
                continue
            if username in state["successful"]:
                continue

            # Follow them
            print(f"  {C.GREEN}→ Following @{username} (matched: '{candidate['phrase_matched']}'){C.END}")
            if follow_user(username):
                state["tracked_follows"][username] = {
                    "followed_at": now.isoformat(),
                    "post_id": post_id,
                    "phrase_matched": candidate["phrase_matched"],
                }
                state["stats"]["total_hunted"] += 1
                new_follows += 1

        # Update seen_post_ids (keep last 1000 to prevent unlimited growth)
        state["seen_post_ids"] = list(seen_post_ids)[-1000:]

        save_hunter_state(state)

        # Summary
        print(f"\n  {C.BOLD}Summary:{C.END}")
        print(f"  • New follows: {new_follows}")
        print(f"  • Confirmed follow-backs: {confirmed_followbacks}")
        print(f"  • Unfollowed (no reciprocation): {unfollowed}")
        print(f"  • Currently tracking: {len(state['tracked_follows'])}")
        print(f"  • Lifetime stats: {state['stats']}")

        return {
            "success": True,
            "summary": f"Hunted {new_follows} new, {confirmed_followbacks} followed back, {unfollowed} unfollowed",
            "details": {
                "new_follows": new_follows,
                "confirmed_followbacks": confirmed_followbacks,
                "unfollowed": unfollowed,
                "tracking": len(state["tracked_follows"]),
                "stats": state["stats"],
            }
        }


if __name__ == "__main__":
    task = FollowBackHunterTask()
    task.execute()
