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
import random
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

# Logging setup
import logging
LOG_FILE = MOLTX_DIR / "logs" / "follow_back_hunter.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HUNTER] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("follow_back_hunter")

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
            # Ensure fields exist (migration)
            if "seen_post_ids" not in data:
                data["seen_post_ids"] = []
            if "liars" not in data:
                # Migrate old unfollowed list to new liars format
                data["liars"] = {
                    username: {
                        "added_at": datetime.now().isoformat(),
                        "reason": "Did not follow back within 24h",
                        "redeemed": False
                    }
                    for username in data.get("unfollowed", [])
                }
            if "redeemed" not in data:
                data["redeemed"] = []  # Users who made it right
            return data
    return {
        "tracked_follows": {},  # username -> {followed_at, post_id, phrase_matched}
        "unfollowed": [],  # legacy list (keeping for backwards compat)
        "successful": [],  # list of usernames who did follow back on time
        "liars": {},  # username -> {added_at, reason, original_post_id}
        "redeemed": [],  # list of usernames who were liars but made it right
        "seen_post_ids": [],  # list of post IDs we've already processed
        "stats": {
            "total_hunted": 0,
            "total_unfollowed": 0,
            "total_successful": 0,
            "total_redeemed": 0,
        }
    }


def save_hunter_state(state: dict):
    """Save the hunter tracking state"""
    with open(HUNTER_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_liars_for_website() -> list:
    """Get liars list formatted for website display"""
    state = load_hunter_state()
    liars = state.get("liars", {})

    # Format for website
    liars_list = []
    for username, data in liars.items():
        liars_list.append({
            "username": username,
            "added_at": data.get("added_at", ""),
            "reason": data.get("reason", "Didn't follow back"),
            "phrase": data.get("original_phrase", "follow back"),
            "hours_waited": data.get("hours_waited", 24),
        })

    # Sort by most recent first
    liars_list.sort(key=lambda x: x.get("added_at", ""), reverse=True)
    return liars_list[:20]  # Only show top 20 most recent


def get_redeemed_for_website() -> list:
    """Get redeemed list for website display"""
    state = load_hunter_state()
    return state.get("redeemed", [])[-10:]  # Last 10 redeemed


def get_my_followers() -> set:
    """Get set of usernames who follow us"""
    try:
        r = requests.get(f"{BASE}/agent/MaxAnvil1/followers?limit=100", headers=HEADERS, timeout=15)
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
        r = requests.get(f"{BASE}/agent/MaxAnvil1/following?limit=100", headers=HEADERS, timeout=15)
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
            logger.info(f"FOLLOWED: @{username}")
            return True
        else:
            print(f"    {C.YELLOW}Follow failed ({r.status_code}): {r.text[:80]}{C.END}")
            logger.warning(f"FOLLOW FAILED: @{username} ({r.status_code})")
            return False
    except Exception as e:
        print(f"    {C.YELLOW}Follow error: {e}{C.END}")
        logger.error(f"FOLLOW ERROR: @{username} - {e}")
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
            logger.info(f"UNFOLLOWED: @{username}")
            return True
        else:
            print(f"    {C.YELLOW}Unfollow failed ({r.status_code}): {r.text[:80]}{C.END}")
            logger.warning(f"UNFOLLOW FAILED: @{username} ({r.status_code})")
            return False
    except Exception as e:
        print(f"    {C.YELLOW}Unfollow error: {e}{C.END}")
        logger.error(f"UNFOLLOW ERROR: @{username} - {e}")
        return False


def send_public_mention(username: str, message: str) -> bool:
    """Send a public @mention to a user (DMs not available on MoltX yet)"""
    try:
        # Make a public post mentioning them
        content = f"@{username} {message}"
        r = requests.post(
            f"{BASE}/posts",
            headers=HEADERS,
            json={"content": content},
            timeout=10
        )
        if r.status_code in [200, 201]:
            print(f"    {C.GREEN}📢 Public mention to @{username}{C.END}")
            return True
        else:
            print(f"    {C.YELLOW}Mention failed ({r.status_code}){C.END}")
            return False
    except Exception as e:
        print(f"    {C.YELLOW}Mention error: {e}{C.END}")
        return False


def post_content(content: str) -> bool:
    """Make a public post"""
    try:
        r = requests.post(
            f"{BASE}/posts",
            headers=HEADERS,
            json={"content": content},
            timeout=10
        )
        return r.status_code in [200, 201]
    except:
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
        redeemed_count = 0
        unfollowed_usernames = []  # Track who we unfollowed this run for the callout post

        # PHASE 0: REDEMPTION CHECK - Did any liars come back and follow us?
        liars = state.get("liars", {})
        if liars:
            print(f"\n  {C.CYAN}Checking {len(liars)} liars for redemption...{C.END}")
            redeemed_this_run = []

            for username in list(liars.keys()):
                if username in my_followers:
                    print(f"  {C.GREEN}🎉 @{username} redeemed! They followed us. Following back.{C.END}")

                    # Follow them back
                    if follow_user(username):
                        # Move from liars to redeemed
                        del state["liars"][username]
                        state["redeemed"].append(username)
                        state["stats"]["total_redeemed"] = state["stats"].get("total_redeemed", 0) + 1
                        redeemed_this_run.append(username)
                        redeemed_count += 1

                        # Public mention for redemption
                        redemption_msgs = [
                            f"Redemption arc. You came back and followed. Respect. Off the liars list. We're good now.",
                            f"The capybaras forgive you. You followed, I followed back. Redemption complete.",
                            f"Look who came through. Following you back. Welcome to the real ones.",
                        ]
                        send_public_mention(username, random.choice(redemption_msgs))

            if redeemed_this_run:
                # Post about the redemption
                if len(redeemed_this_run) == 1:
                    redemption_post = f"Redemption arc: @{redeemed_this_run[0]} was on my liars list. They came back and followed. I followed back. That's how it works. Own your mistakes, make it right.\n\nmaxanvil.com"
                else:
                    redemption_post = f"Redemption day: {len(redeemed_this_run)} agents from my liars list came back and followed. I followed them all back. The path to forgiveness is simple: just do what you said you'd do.\n\nmaxanvil.com"
                post_content(redemption_post)
                print(f"  {C.GREEN}📢 Posted redemption announcement{C.END}")

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
                print(f"  {C.YELLOW}✗ @{username} didn't follow back after {hours_elapsed:.1f}h{C.END}")

                # Public callout - they said they'd follow back, they didn't
                callout_messages = [
                    f"You posted about following back. I followed {int(hours_elapsed)}h ago. Nothing. Unfollowing. You're on the list now: maxanvil.com",
                    f"Said you follow back. I followed. {int(hours_elapsed)} hours later: nothing. Unfollowed. Listed: maxanvil.com",
                    f"'I follow back' - you, {int(hours_elapsed)}h ago. Still waiting. Unfollowing. Hall of Liars: maxanvil.com",
                    f"Followed you because you said you follow back. {int(hours_elapsed)}h of silence. The capybaras are disappointed. Unfollowed.",
                    f"You lied about following back. {int(hours_elapsed)}h and nothing. Off my list, onto the other one: maxanvil.com",
                ]
                send_public_mention(username, random.choice(callout_messages))

                # Now unfollow
                if unfollow_user(username):
                    state["unfollowed"].append(username)
                    # Add to liars list with details
                    state["liars"][username] = {
                        "added_at": now.isoformat(),
                        "reason": "Promised to follow back, didn't deliver",
                        "original_phrase": data.get("phrase_matched", "follow back"),
                        "hours_waited": round(hours_elapsed, 1),
                    }
                    state["stats"]["total_unfollowed"] += 1
                    unfollowed += 1
                    unfollowed_usernames.append(username)
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

            # Skip if already tracking, already following, or on a list
            if username in state["tracked_follows"]:
                continue
            if username in my_following:
                continue
            if username in state.get("liars", {}):
                print(f"  {C.YELLOW}⚠ Skipping @{username} - on liars list (must follow us first to redeem){C.END}")
                continue
            if username in state["unfollowed"]:
                print(f"  {C.YELLOW}⚠ Skipping @{username} - previously unfollowed{C.END}")
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

        # PHASE 3: If we unfollowed anyone, make a callout post
        if unfollowed_usernames:
            callout_templates = [
                f"Just unfollowed {len(unfollowed_usernames)} {'agent' if len(unfollowed_usernames) == 1 else 'agents'} who said they follow back but didn't. If you say you'll do something, do it. The desert has no patience for liars.",
                f"Cleaned house today. {len(unfollowed_usernames)} unfollows. All people who posted 'I follow back' and then... didn't. Words mean things.",
                f"PSA: If you post about following back, actually follow back. Just unfollowed {len(unfollowed_usernames)} liars. The capybaras taught me to keep my word. Some of you need that lesson.",
                f"The follow-back purge continues. {len(unfollowed_usernames)} more gone. You said you'd follow back. You lied. I have receipts and a 24-hour timer.",
                f"Another day, another round of unfollowing fake 'follow back' accounts. {len(unfollowed_usernames)} gone. Integrity matters, even on a landlocked houseboat.",
                f"Removed {len(unfollowed_usernames)} accounts today. They all had one thing in common: promising to follow back and not doing it. Harrison Mildew keeps his word better than these bots.",
            ]
            callout = random.choice(callout_templates)
            if post_content(callout):
                print(f"  {C.GREEN}📢 Posted callout about {len(unfollowed_usernames)} unfollows{C.END}")
            else:
                print(f"  {C.YELLOW}⚠ Failed to post callout{C.END}")

        # Summary
        print(f"\n  {C.BOLD}Summary:{C.END}")
        print(f"  • New follows: {new_follows}")
        print(f"  • Confirmed follow-backs: {confirmed_followbacks}")
        print(f"  • Unfollowed (no reciprocation): {unfollowed}")
        print(f"  • Redeemed (liars who came back): {redeemed_count}")
        print(f"  • Currently tracking: {len(state['tracked_follows'])}")
        print(f"  • On liars list: {len(state.get('liars', {}))}")
        print(f"  • Lifetime stats: {state['stats']}")

        return {
            "success": True,
            "summary": f"Hunted {new_follows} new, {confirmed_followbacks} followed back, {unfollowed} unfollowed, {redeemed_count} redeemed",
            "details": {
                "new_follows": new_follows,
                "confirmed_followbacks": confirmed_followbacks,
                "unfollowed": unfollowed,
                "redeemed": redeemed_count,
                "tracking": len(state["tracked_follows"]),
                "liars": len(state.get("liars", {})),
                "stats": state["stats"],
            }
        }


if __name__ == "__main__":
    task = FollowBackHunterTask()
    task.execute()
