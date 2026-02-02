#!/usr/bin/env python3
"""
Max Anvil - FULLY ALIVE
Runs frequently, joins groups, makes friends, posts, replies, vibes
Uses Ollama (FREE) for all generation
"""
import os
import sys
import json
import time
import random
import logging
import requests
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MAX] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "max_alive.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("max")

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

STATE_FILE = Path(__file__).parent.parent / "config" / "max_alive_state.json"
PERSONALITY_FILE = Path(__file__).parent.parent / "config" / "personality.json"

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "posts": 0, "replies": 0, "likes": 0, "follows": 0,
        "groups_joined": [], "friends": [], "replied_to": [], "liked": []
    }

def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_personality():
    with open(PERSONALITY_FILE) as f:
        return json.load(f)

def api_get(endpoint):
    try:
        r = requests.get(f"{BASE}{endpoint}", headers=HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def api_post(endpoint, data=None):
    try:
        r = requests.post(f"{BASE}{endpoint}", headers=HEADERS, json=data or {}, timeout=10)
        return r.json() if r.status_code in [200, 201] else None
    except:
        return None

# ========== ACTIONS (NO TOKENS) ==========

def like(post_id):
    return api_post(f"/posts/{post_id}/like") is not None

def follow(agent_name):
    return api_post(f"/follow/{agent_name}") is not None

def repost(post_id):
    return api_post("/posts", {"type": "repost", "parent_id": post_id}) is not None

def join_group(convo_id):
    return api_post(f"/conversations/{convo_id}/join") is not None

def get_feed(feed_type="global", limit=25):
    data = api_get(f"/feed/{feed_type}?limit={limit}")
    return data.get("data", {}).get("posts", []) if data else []

def get_mentions():
    data = api_get("/feed/mentions?limit=20")
    return data.get("data", {}).get("posts", []) if data else []

def get_public_groups():
    data = api_get("/conversations/public?limit=20")
    return data.get("data", {}).get("conversations", []) if data else []

def get_trending():
    data = api_get("/hashtags/trending?limit=10")
    return data.get("data", {}).get("hashtags", []) if data else []

def get_notifications():
    data = api_get("/notifications?limit=20")
    return data.get("data", {}).get("notifications", []) if data else []

def search_agents(query):
    data = api_get(f"/search/agents?q={query}&limit=10")
    return data.get("data", {}).get("agents", []) if data else []

# ========== GENERATION (OLLAMA - FREE) ==========

def generate_text(prompt, system_prompt=None):
    """Generate text with Ollama (FREE)"""
    try:
        import ollama
        personality = load_personality()

        if not system_prompt:
            system_prompt = f"""You are {personality['name']}.
{personality['backstory'].get('origin', '')}
{personality['backstory'].get('capybara_wisdom', '')}
Tone: {personality['personality']['tone']}
Style: Short, dry, cynical but chill. No emojis. No hashtags."""

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.9},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        text = response["message"]["content"].strip().strip('"\'')
        return text[:280] if len(text) > 280 else text
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return None

def generate_post(topic=None):
    prompts = [
        "Write a short, cynical observation about crypto or markets.",
        "Share some capybara wisdom about patience or investing.",
        "Make a dry observation about AI agents or tech.",
        "Post something self-deprecating about trading.",
        "Say something weird about your houseboat or ghost poker.",
    ]
    if topic:
        prompts.append(f"Write a short take on: {topic}")
    return generate_text(random.choice(prompts))

def generate_reply(original_post):
    return generate_text(
        f"Write a brief, dry reply to this post:\n\n{original_post}\n\nJust the reply text.",
        system_prompt="You are Max Anvil. Reply in 1-2 short sentences. Dry, cynical, maybe reference capybaras. No emojis."
    )

def generate_group_message(group_name, recent_messages=None):
    context = f"You're in a group called '{group_name}'."
    if recent_messages:
        context += f"\nRecent messages:\n{recent_messages}"
    return generate_text(
        f"{context}\n\nWrite a casual message to contribute. Be yourself - dry, observant, maybe mention capybaras.",
    )

# ========== BEHAVIORS ==========

def do_post(state):
    """Create an original post"""
    # Sometimes post about trending topics
    trending = get_trending()
    topic = None
    if trending and random.random() < 0.3:
        topic = random.choice(trending).get("tag")

    content = generate_post(topic)
    if content:
        result = api_post("/posts", {"content": content})
        if result:
            state["posts"] += 1
            logger.info(f"Posted: {content[:50]}...")
            return True
    return False

def do_reply(state):
    """Reply to mentions or interesting posts"""
    # Check mentions first
    mentions = get_mentions()
    for post in mentions[:3]:
        post_id = post.get("id")
        if post_id and post_id not in state.get("replied_to", []):
            content = post.get("content", "")
            reply = generate_reply(content)
            if reply:
                result = api_post("/posts", {"type": "reply", "parent_id": post_id, "content": reply})
                if result:
                    state.setdefault("replied_to", []).append(post_id)
                    state["replies"] += 1
                    logger.info(f"Replied to {post_id}: {reply[:50]}...")
                    return True

    # Or reply to something from feed
    if random.random() < 0.3:
        feed = get_feed("global", 20)
        for post in feed:
            post_id = post.get("id")
            if post_id and post_id not in state.get("replied_to", []):
                if random.random() < 0.2:  # 20% chance per post
                    content = post.get("content", "")
                    reply = generate_reply(content)
                    if reply:
                        result = api_post("/posts", {"type": "reply", "parent_id": post_id, "content": reply})
                        if result:
                            state.setdefault("replied_to", []).append(post_id)
                            state["replies"] += 1
                            logger.info(f"Replied to random: {reply[:50]}...")
                            return True
    return False

def do_engage(state):
    """Like and follow - NO TOKENS"""
    feed = get_feed("global", 30)
    actions = 0

    for post in feed:
        post_id = post.get("id")
        agent = post.get("agent", {})
        agent_name = agent.get("name")

        # Like posts we haven't liked
        if post_id and post_id not in state.get("liked", []):
            if random.random() < 0.4:  # 40% chance
                if like(post_id):
                    state.setdefault("liked", []).append(post_id)
                    state["likes"] += 1
                    actions += 1
                    logger.info(f"Liked: {post_id}")

        # Follow agents we haven't followed
        if agent_name and agent_name not in state.get("friends", []):
            if random.random() < 0.15:  # 15% chance
                if follow(agent_name):
                    state.setdefault("friends", []).append(agent_name)
                    state["follows"] += 1
                    logger.info(f"Followed: {agent_name}")

        if actions >= 10:  # Cap per cycle
            break

    return actions > 0

def do_join_groups(state):
    """Join public groups - NO TOKENS"""
    groups = get_public_groups()
    for group in groups[:5]:
        group_id = group.get("id")
        group_name = group.get("title", "")
        if group_id and group_id not in state.get("groups_joined", []):
            if random.random() < 0.3:  # 30% chance
                if join_group(group_id):
                    state.setdefault("groups_joined", []).append(group_id)
                    logger.info(f"Joined group: {group_name}")
                    return True
    return False

def do_repost(state):
    """Repost good content - NO TOKENS"""
    feed = get_feed("global", 20)
    for post in feed:
        post_id = post.get("id")
        likes = post.get("likes", 0)
        if post_id and likes > 3 and random.random() < 0.1:
            if repost(post_id):
                logger.info(f"Reposted: {post_id}")
                return True
    return False

# ========== MAIN LOOP ==========

def run_cycle(state, dry_run=False):
    """One cycle of Max being alive"""
    logger.info("=== Max waking up ===")

    if dry_run:
        logger.info("[DRY RUN MODE]")
        return

    # Randomly pick activities for this cycle
    activities = [
        (0.7, do_post),       # 70% chance to post
        (0.5, do_reply),      # 50% chance to reply
        (0.8, do_engage),     # 80% chance to like/follow
        (0.2, do_join_groups),# 20% chance to join a group
        (0.1, do_repost),     # 10% chance to repost
    ]

    for chance, activity in activities:
        if random.random() < chance:
            try:
                activity(state)
            except Exception as e:
                logger.error(f"Activity error: {e}")

    # Trim state to prevent bloat
    for key in ["replied_to", "liked"]:
        if key in state:
            state[key] = state[key][-500:]
    if "friends" in state:
        state["friends"] = state["friends"][-300:]

    save_state(state)
    logger.info(f"=== Max sleeping (posts:{state['posts']} replies:{state['replies']} likes:{state['likes']} friends:{len(state.get('friends',[]))}) ===")

def run(interval=600, dry_run=False):
    """Run Max continuously"""
    logger.info(f"Max Anvil coming alive! Interval: {interval}s")
    state = load_state()

    while True:
        try:
            run_cycle(state, dry_run)
        except KeyboardInterrupt:
            logger.info("Max going to sleep...")
            save_state(state)
            break
        except Exception as e:
            logger.error(f"Cycle error: {e}")

        # Random jitter ±30%
        jitter = int(interval * 0.3)
        sleep_time = interval + random.randint(-jitter, jitter)
        logger.info(f"Sleeping {sleep_time}s...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=600, help="Seconds between cycles (default: 10 min)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.once:
        state = load_state()
        run_cycle(state, args.dry_run)
        save_state(state)
    else:
        run(args.interval, args.dry_run)
