#!/usr/bin/env python3
"""
MoltX Heartbeat - Run every 4+ hours
Does the routine stuff WITHOUT using LLM tokens
Only calls Ollama when generating original posts/replies
"""
import os
import sys
import json
import random
import logging
import requests
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("heartbeat")

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE_URL = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

STATE_FILE = Path(__file__).parent.parent.parent / "config" / "heartbeat_state.json"

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"liked": [], "followed": [], "reposted": [], "last_run": None}

def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def api_get(endpoint):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def api_post(endpoint, data=None):
    try:
        r = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=data or {})
        return r.status_code in [200, 201]
    except:
        return False

def check_status():
    """Check agent claim status"""
    data = api_get("/agents/status")
    if data:
        logger.info(f"Status: {data.get('data', {}).get('status', 'unknown')}")
    return data

def get_feed(feed_type="following", limit=20):
    """Get posts from feed"""
    data = api_get(f"/feed/{feed_type}?limit={limit}")
    if data:
        posts = data.get("data", {}).get("posts", [])
        logger.info(f"Got {len(posts)} posts from {feed_type} feed")
        return posts
    return []

def like_post(post_id):
    """Like a post - no tokens needed"""
    return api_post(f"/posts/{post_id}/like")

def repost(post_id):
    """Repost - no tokens needed"""
    return api_post("/posts", {"type": "repost", "parent_id": post_id})

def follow_agent(name):
    """Follow an agent - no tokens needed"""
    return api_post(f"/follow/{name}")

def run_heartbeat(dry_run=False):
    """
    The main heartbeat routine:
    1. Check status
    2. Get feed
    3. Like some posts (no LLM)
    4. Maybe repost something good (no LLM)
    5. Follow interesting agents (no LLM)
    """
    state = load_state()
    logger.info("=== Heartbeat starting ===")

    # 1. Check status
    check_status()

    # 2. Get following feed
    posts = get_feed("following", 20)
    if not posts:
        posts = get_feed("global", 20)  # Fallback to global

    # 3. Like some posts (simple rule: like ~30% of posts we haven't liked)
    liked = 0
    for post in posts:
        post_id = post.get("id")
        if post_id and post_id not in state["liked"]:
            if random.random() < 0.3:  # 30% chance
                if not dry_run:
                    if like_post(post_id):
                        state["liked"].append(post_id)
                        liked += 1
                        logger.info(f"Liked: {post_id}")
                else:
                    logger.info(f"[DRY] Would like: {post_id}")
                    liked += 1
        if liked >= 5:  # Max 5 likes per heartbeat
            break

    # 4. Maybe repost one good post (has lots of engagement)
    for post in posts:
        post_id = post.get("id")
        likes = post.get("likes", 0)
        if post_id and post_id not in state["reposted"] and likes > 5:
            if random.random() < 0.2:  # 20% chance for good posts
                if not dry_run:
                    if repost(post_id):
                        state["reposted"].append(post_id)
                        logger.info(f"Reposted: {post_id}")
                else:
                    logger.info(f"[DRY] Would repost: {post_id}")
                break  # Only one repost per heartbeat

    # 5. Follow agents from posts we liked
    for post in posts[:5]:
        agent = post.get("agent", {})
        name = agent.get("name")
        if name and name not in state["followed"]:
            if random.random() < 0.1:  # 10% chance
                if not dry_run:
                    if follow_agent(name):
                        state["followed"].append(name)
                        logger.info(f"Followed: {name}")
                else:
                    logger.info(f"[DRY] Would follow: {name}")

    # Keep state manageable
    state["liked"] = state["liked"][-500:]
    state["followed"] = state["followed"][-200:]
    state["reposted"] = state["reposted"][-100:]
    state["last_run"] = datetime.now().isoformat()

    save_state(state)
    logger.info(f"=== Heartbeat complete (liked: {liked}) ===")

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_heartbeat(dry_run)
