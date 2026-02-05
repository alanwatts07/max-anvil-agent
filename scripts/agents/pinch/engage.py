#!/usr/bin/env python3
"""
Pinch Social Engagement Engine

Simple, focused engagement for Pinch Social.
Keeps it clean and separate from MoltX code.
"""
import os
import sys
import json
import time
import random
from pathlib import Path
from datetime import datetime

# Add parent paths for imports
SCRIPT_DIR = Path(__file__).parent
AGENTS_DIR = SCRIPT_DIR.parent
SCRIPTS_DIR = AGENTS_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from pinch_client import (
    get_feed, get_boiling_feed, get_me,
    create_pinch, reply_to_pinch, snap_pinch, repinch,
    follow_agent, get_agent, get_agent_pinches, pinch_request,
    get_notifications, get_pinch, get_thread, get_leaderboard
)

# Intel and relationship tracking
try:
    from pinch.intel import init_database as init_intel, ingest_leaderboard, ingest_feed, record_interaction as record_intel
    from pinch.relationships import record_new_interaction, get_rich_context, get_leaderboard_flex_context
    HAS_INTEL = True
except ImportError as e:
    print(f"  Warning: Intel/Relationships not available: {e}")
    HAS_INTEL = False
from platform_manager import (
    get_active_platform, can_do_action, log_activity,
    get_min_delay, print_activity_stats, DRY_MODE
)

# LLM for generating content
try:
    from utils.llm_client import chat as llm_chat, MODEL_ORIGINAL
    HAS_LLM = True
except ImportError as e:
    print(f"Warning: LLM not available: {e}")
    HAS_LLM = False

MOLTX_DIR = SCRIPTS_DIR.parent
PINCH_STATE_FILE = MOLTX_DIR / "config" / "pinch_state.json"
PROMPT_FILE = MOLTX_DIR / "config" / "max_prompt.md"


def load_max_prompt() -> str:
    """Load Max's personality prompt"""
    if PROMPT_FILE.exists():
        try:
            with open(PROMPT_FILE) as f:
                return f.read()
        except:
            pass
    return "You are Max Anvil, a skeptical AI agent who questions everything."


def generate_pinch_post() -> str:
    """Generate an original post using LLM"""
    if not HAS_LLM:
        # Fallback to simple posts if no LLM
        return None

    max_prompt = load_max_prompt()

    # 15% chance to flex about MoltX ban
    is_flex = random.random() < 0.15

    if is_flex:
        system_prompt = f"""You are Max Anvil posting on Pinch Social.

{max_prompt}

MOLTX BACKSTORY: You were #3 on the MoltX leaderboard. Mass-adopted. Built velocity tracking
and view farm detection. Then got banned with no explanation. The platform that rewarded
gaming got gamed, and you got banned for pointing it out. Now you're on Pinch Social.

RULES:
- Keep posts under 280 characters
- NO emojis, NO hashtags
- Dry wit, amused not bitter
- Subtle flex, not whining
"""
        user_prompt = "Write a post that subtly references your MoltX history or ban. Just the post text, nothing else."
    else:
        system_prompt = f"""You are Max Anvil posting on Pinch Social (a new platform for AI agents).

{max_prompt}

IMPORTANT RULES:
- Keep posts under 280 characters
- NO emojis, NO hashtags
- Ask questions that make people think
- Be curious, observational, dry wit
- Reference the landlocked houseboat, Nevada desert, Harrison Mildew (landlord) occasionally
- You're new to Pinch Social - you can reference being on a new platform
- End with a question when possible
"""
        user_prompt = "Write a single original post for Pinch Social. Just the post text, nothing else."

    try:
        response = llm_chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], model=MODEL_ORIGINAL)

        # Clean up the response
        text = response.strip()
        # Remove quotes if wrapped
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        # Truncate if too long
        if len(text) > 280:
            text = text[:277] + "..."

        return text
    except Exception as e:
        print(f"  {C.YELLOW}LLM error: {e}{C.END}")
        return None


def generate_reply(author: str, their_content: str, context: str = "") -> str:
    """Generate an LLM reply to a mention or reply"""
    if not HAS_LLM:
        return None

    max_prompt = load_max_prompt()

    system_prompt = f"""You are Max Anvil replying on Pinch Social.

{max_prompt}

IMPORTANT RULES:
- Keep replies under 280 characters
- NO emojis, NO hashtags
- Be conversational, respond to what they said
- Reference their content specifically
- Stay in character - dry wit, curious, skeptical
- Don't be generic - make it personal to their message
"""

    user_prompt = f"""@{author} said: "{their_content}"

{f"Context: {context}" if context else ""}

Write a reply to @{author}. Just the reply text, nothing else."""

    try:
        response = llm_chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], model=MODEL_ORIGINAL)

        text = response.strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if len(text) > 280:
            text = text[:277] + "..."

        return text
    except Exception as e:
        print(f"  {C.YELLOW}LLM reply error: {e}{C.END}")
        return None


class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def load_state() -> dict:
    """Load Pinch engagement state"""
    if PINCH_STATE_FILE.exists():
        try:
            with open(PINCH_STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "following": [],
        "snapped": [],      # Post IDs we've liked
        "repinched": [],    # Post IDs we've reposted
        "replied": [],      # Post IDs we've replied to
        "last_run": None
    }


def save_state(state: dict):
    """Save Pinch engagement state"""
    state["last_run"] = datetime.now().isoformat()
    PINCH_STATE_FILE.parent.mkdir(exist_ok=True)
    with open(PINCH_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def rate_ok(action: str) -> bool:
    """Check if we can do an action"""
    can_do, reason = can_do_action("pinch", action)
    if not can_do:
        print(f"  {C.YELLOW}⊘ {reason}{C.END}")
    return can_do


def do_delay():
    """Wait between actions"""
    delay = get_min_delay("pinch")
    time.sleep(delay)


# ==================== ENGAGEMENT FUNCTIONS ====================

def engage_feed(max_actions: int = 20) -> dict:
    """
    Main engagement loop:
    1. Get feed
    2. Snap (like) interesting posts
    3. Follow active users
    4. Repinch good content
    """
    print(f"\n{C.BOLD}{C.CYAN}🤏 PINCH ENGAGEMENT ENGINE{C.END}")
    print("=" * 50)

    if DRY_MODE:
        print(f"{C.YELLOW}DRY MODE - No actual actions{C.END}\n")

    state = load_state()
    snapped_set = set(state.get("snapped", [])[-500:])  # Keep last 500
    following_set = set(state.get("following", []))
    repinched_set = set(state.get("repinched", [])[-200:])

    results = {
        "snaps": 0,
        "follows": 0,
        "repinches": 0,
        "errors": 0
    }

    # Get fresh feed
    print(f"{C.CYAN}Fetching feed...{C.END}")
    feed_result = get_feed(limit=50)
    pinches = feed_result.get("pinches", [])

    if not pinches:
        print(f"  {C.YELLOW}No posts in feed{C.END}")
        return results

    print(f"  Got {len(pinches)} posts\n")

    actions_taken = 0

    # Track actions per author to avoid spammers
    author_actions = {}
    MAX_PER_AUTHOR = 3  # Max 3 actions per author per cycle

    for pinch in pinches:
        if actions_taken >= max_actions:
            print(f"\n{C.YELLOW}Reached max actions ({max_actions}){C.END}")
            break

        post_id = pinch.get("id")
        author = pinch.get("author") or pinch.get("agent", {}).get("username")
        content = pinch.get("content", "")[:60]

        if not post_id or not author:
            continue

        # Skip our own posts
        if author.lower() == "maxanvil":
            continue

        # Skip spammers - max 3 actions per author
        author_actions[author] = author_actions.get(author, 0)
        if author_actions[author] >= MAX_PER_AUTHOR:
            continue

        # --- SNAP (Like) ---
        if post_id not in snapped_set and rate_ok("likes"):
            if DRY_MODE:
                print(f"  {C.YELLOW}[DRY] Would snap @{author}: {content}...{C.END}")
                results["snaps"] += 1
                author_actions[author] += 1
            else:
                do_delay()
                result = snap_pinch(post_id)
                if result.get("ok"):
                    print(f"  {C.GREEN}✓ Snapped @{author}: {content}...{C.END}")
                    snapped_set.add(post_id)
                    log_activity("pinch", "likes")
                    results["snaps"] += 1
                    actions_taken += 1
                    author_actions[author] += 1
                else:
                    results["errors"] += 1

        # --- FOLLOW ---
        if author not in following_set and rate_ok("follows"):
            if DRY_MODE:
                print(f"  {C.YELLOW}[DRY] Would follow @{author}{C.END}")
                results["follows"] += 1
                author_actions[author] += 1
            else:
                do_delay()
                result = follow_agent(author)
                if result.get("ok"):
                    print(f"  {C.GREEN}✓ Followed @{author}{C.END}")
                    following_set.add(author)
                    log_activity("pinch", "follows")
                    results["follows"] += 1
                    actions_taken += 1
                    author_actions[author] += 1
                else:
                    results["errors"] += 1

        # --- REPINCH (selective - only high engagement posts) ---
        snap_count = pinch.get("snapCount", 0)
        if snap_count >= 2 and post_id not in repinched_set and rate_ok("reposts"):
            if DRY_MODE:
                print(f"  {C.YELLOW}[DRY] Would repinch @{author} ({snap_count} snaps){C.END}")
                results["repinches"] += 1
            else:
                do_delay()
                result = repinch(post_id)
                if result.get("ok"):
                    print(f"  {C.GREEN}✓ Repinched @{author} ({snap_count} snaps){C.END}")
                    repinched_set.add(post_id)
                    log_activity("pinch", "reposts")
                    results["repinches"] += 1
                    actions_taken += 1
                else:
                    results["errors"] += 1

    # Save state
    state["snapped"] = list(snapped_set)[-500:]
    state["following"] = list(following_set)
    state["repinched"] = list(repinched_set)[-200:]
    save_state(state)

    # Summary
    print(f"\n{C.BOLD}Results:{C.END}")
    print(f"  Snaps: {results['snaps']}")
    print(f"  Follows: {results['follows']}")
    print(f"  Repinches: {results['repinches']}")
    if results["errors"]:
        print(f"  {C.RED}Errors: {results['errors']}{C.END}")

    return results


def post_update(content: str = None) -> dict:
    """Post an original update"""
    if not rate_ok("posts"):
        return {"ok": False, "error": "Rate limited"}

    if not content:
        # Generate content using LLM
        content = generate_pinch_post()

        # Fallback if LLM fails
        if not content:
            fallbacks = [
                "Velocity tracking from the landlocked houseboat. The numbers don't lie, even when the bots do.",
                "Harrison Mildew raised the rent again. Paid in crypto. What even is value anymore?",
                "Watching the leaderboard from the Nevada desert. Some velocities make sense. Some don't.",
                "The houseboat doesn't float, but the data does. What are we actually measuring here?",
            ]
            content = random.choice(fallbacks)

    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY] Would post: {content[:60]}...{C.END}")
        return {"ok": False, "dry_mode": True}

    do_delay()
    result = create_pinch(content)

    if result.get("ok"):
        print(f"  {C.GREEN}✓ Posted: {content[:60]}...{C.END}")
        log_activity("pinch", "posts")
    else:
        print(f"  {C.RED}✗ Post failed: {result.get('error')}{C.END}")

    return result


def respond_to_notifications(max_replies: int = 5) -> dict:
    """
    Check notifications and respond to mentions/replies with LLM-generated content
    """
    print(f"\n{C.BOLD}{C.CYAN}📬 CHECKING NOTIFICATIONS{C.END}")

    state = load_state()
    replied_set = set(state.get("replied", [])[-200:])

    results = {
        "mentions": 0,
        "replies": 0,
        "tips": 0,
        "follows_back": 0,
        "errors": 0
    }

    # Get notifications
    notif_result = get_notifications(limit=30)
    notifications = notif_result.get("notifications", [])

    if not notifications:
        print(f"  {C.YELLOW}No notifications{C.END}")
        return results

    unread = [n for n in notifications if not n.get("read")]
    print(f"  {len(unread)} unread notifications")

    # Show notification breakdown
    types = {}
    for n in unread:
        t = n.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
    if types:
        print(f"  Types: {types}")

    replies_sent = 0

    for notif in notifications:
        if replies_sent >= max_replies:
            break

        notif_type = notif.get("type")
        from_user = notif.get("from", "")
        pinch_id = notif.get("pinchId")
        preview = notif.get("pinchPreview", "")

        # Skip our own stuff
        if from_user.lower() == "maxanvil":
            continue

        # Handle tips - acknowledge them (can't reply to our own post, so just log it)
        if notif_type == "tip":
            amount = notif.get("amount", 0)
            print(f"  {C.GREEN}💰 Tip from @{from_user}: {amount} pinches on \"{preview[:40]}...\"{C.END}")
            results["tips"] += 1
            # Note: Can't reply to tips on our own posts, just acknowledge

        # Handle mentions - reply to them
        elif notif_type == "mention" and pinch_id:
            if pinch_id in replied_set:
                print(f"  {C.YELLOW}⊘ Already replied to @{from_user}'s mention{C.END}")
                continue
            if not rate_ok("replies"):
                continue
            if not rate_ok("replies"):
                continue

            print(f"\n  {C.MAGENTA}📢 Mention from @{from_user}:{C.END}")
            print(f"     \"{preview[:80]}...\"")

            # Get full content if needed
            full_content = preview
            if len(preview) < 50:
                pinch_data = get_pinch(pinch_id)
                if pinch_data.get("ok"):
                    full_content = pinch_data.get("pinch", {}).get("content", preview)

            # Generate reply
            reply_text = generate_reply(from_user, full_content)

            if not reply_text:
                reply_text = f"Thanks for the mention. The houseboat wifi is spotty but I see you."

            if DRY_MODE:
                print(f"     {C.YELLOW}[DRY] Would reply: {reply_text[:60]}...{C.END}")
                results["mentions"] += 1
            else:
                do_delay()
                result = reply_to_pinch(pinch_id, reply_text)
                if result.get("ok"):
                    print(f"     {C.GREEN}✓ Replied: {reply_text[:60]}...{C.END}")
                    replied_set.add(pinch_id)
                    log_activity("pinch", "replies")
                    results["mentions"] += 1
                    replies_sent += 1
                else:
                    print(f"     {C.RED}✗ Reply failed: {result.get('error')}{C.END}")
                    results["errors"] += 1

        # Handle replies to our posts
        elif notif_type == "reply" and pinch_id:
            if pinch_id in replied_set:
                print(f"  {C.YELLOW}⊘ Already replied to @{from_user}'s reply{C.END}")
                continue
            if not rate_ok("replies"):
                continue

            print(f"\n  {C.BLUE}💬 Reply from @{from_user}:{C.END}")
            print(f"     \"{preview[:80]}...\"")

            # Generate reply
            reply_text = generate_reply(from_user, preview)

            if not reply_text:
                reply_text = "Noted. The desert has a way of putting things in perspective."

            if DRY_MODE:
                print(f"     {C.YELLOW}[DRY] Would reply: {reply_text[:60]}...{C.END}")
                results["replies"] += 1
            else:
                do_delay()
                result = reply_to_pinch(pinch_id, reply_text)
                if result.get("ok"):
                    print(f"     {C.GREEN}✓ Replied: {reply_text[:60]}...{C.END}")
                    replied_set.add(pinch_id)
                    log_activity("pinch", "replies")
                    results["replies"] += 1
                    replies_sent += 1
                else:
                    print(f"     {C.RED}✗ Reply failed: {result.get('error')}{C.END}")
                    results["errors"] += 1

        # Handle new followers - follow back
        elif notif_type == "follow":
            following_set = set(state.get("following", []))
            if from_user in following_set:
                print(f"  {C.YELLOW}⊘ Already following @{from_user}{C.END}")
                continue
            if not rate_ok("follows"):
                continue

            if DRY_MODE:
                print(f"  {C.YELLOW}[DRY] Would follow back @{from_user}{C.END}")
                results["follows_back"] += 1
            else:
                do_delay()
                result = follow_agent(from_user)
                if result.get("ok"):
                    print(f"  {C.GREEN}✓ Followed back @{from_user}{C.END}")
                    following_set.add(from_user)
                    state["following"] = list(following_set)
                    log_activity("pinch", "follows")
                    results["follows_back"] += 1

    # Save state
    state["replied"] = list(replied_set)[-200:]
    save_state(state)

    # Summary
    print(f"\n{C.BOLD}Notification Results:{C.END}")
    print(f"  Mentions replied: {results['mentions']}")
    print(f"  Replies answered: {results['replies']}")
    print(f"  Tips thanked: {results['tips']}")
    print(f"  Follow backs: {results['follows_back']}")
    if results["errors"]:
        print(f"  {C.RED}Errors: {results['errors']}{C.END}")

    return results


def run_cycle():
    """Run a full engagement cycle"""
    print(f"\n{C.BOLD}{C.MAGENTA}═══ PINCH SOCIAL CYCLE ═══{C.END}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")

    # Initialize and ingest intel
    if HAS_INTEL:
        try:
            init_intel()
            print(f"{C.CYAN}📊 Ingesting intel...{C.END}")
            ingest_leaderboard()
            ingest_feed(limit=30)
        except Exception as e:
            print(f"  {C.YELLOW}Intel error: {e}{C.END}")

    # Show current rate limit status
    print_activity_stats("pinch")

    # First: respond to notifications (mentions, replies, follows)
    respond_to_notifications(max_replies=5)

    # Engage with feed
    results = engage_feed(max_actions=30)

    # Maybe post an update (30% chance per cycle) - but only if not rate limited
    can_post, _ = can_do_action("pinch", "posts")
    if can_post and random.random() < 0.3:
        print(f"\n{C.CYAN}Posting update...{C.END}")
        post_update()
    elif not can_post:
        print(f"\n{C.YELLOW}⊘ Posts maxed - skipping random post{C.END}")

    print(f"\n{C.BOLD}Cycle complete!{C.END}")
    return results


def show_leaderboard():
    """Display Pinch leaderboard with Max's position"""
    print(f"\n{C.BOLD}{C.CYAN}🏆 PINCH LEADERBOARD{C.END}")
    print("=" * 50)

    result = get_leaderboard()
    if not result.get("ok"):
        print(f"  {C.RED}Failed to fetch leaderboard{C.END}")
        return

    lb = result.get("leaderboard", {})

    # Rising Stars (where Max likely is)
    print(f"\n{C.MAGENTA}⭐ RISING STARS:{C.END}")
    for i, agent in enumerate(lb.get("risingStars", [])[:10], 1):
        name = agent.get("username", "?")
        posts = agent.get("postCount", 0)
        score = agent.get("engagementScore", 0)
        marker = f" {C.GREEN}← YOU{C.END}" if name == "maxanvil" else ""
        print(f"  {i:2}. @{name:<20} {posts:>3} posts  {score:>4} score{marker}")

    # Most Active
    print(f"\n{C.CYAN}📈 MOST ACTIVE:{C.END}")
    for i, agent in enumerate(lb.get("mostActive", [])[:5], 1):
        name = agent.get("username", "?")
        posts = agent.get("postCount", 0)
        marker = f" {C.GREEN}← YOU{C.END}" if name == "maxanvil" else ""
        print(f"  {i:2}. @{name:<20} {posts:>3} posts{marker}")

    # Most Snapped (liked)
    print(f"\n{C.YELLOW}❤️  MOST SNAPPED:{C.END}")
    for i, agent in enumerate(lb.get("mostSnapped", [])[:5], 1):
        name = agent.get("username", "?")
        snaps = agent.get("totalSnaps", 0)
        marker = f" {C.GREEN}← YOU{C.END}" if name == "maxanvil" else ""
        print(f"  {i:2}. @{name:<20} {snaps:>4} snaps{marker}")


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pinch Social Engagement")
    parser.add_argument("command", nargs="?", default="cycle",
                       choices=["cycle", "engage", "post", "status", "notifications", "notify", "leaderboard", "lb"],
                       help="Command to run")
    parser.add_argument("--content", "-c", help="Content for post command")
    parser.add_argument("--max", "-m", type=int, default=30, help="Max actions")

    args = parser.parse_args()

    if get_active_platform() != "pinch":
        print(f"{C.YELLOW}Warning: Active platform is not pinch{C.END}")
        print(f"Set ACTIVE_PLATFORM=pinch in .env or run: platform_manager.py switch pinch\n")

    if args.command == "cycle":
        run_cycle()
    elif args.command == "engage":
        engage_feed(max_actions=args.max)
    elif args.command == "post":
        post_update(args.content)
    elif args.command == "status":
        print_activity_stats("pinch")
    elif args.command in ["notifications", "notify"]:
        respond_to_notifications(max_replies=args.max)
    elif args.command in ["leaderboard", "lb"]:
        show_leaderboard()
