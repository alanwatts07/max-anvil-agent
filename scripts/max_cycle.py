#!/usr/bin/env python3
"""
Max Anvil Agent Cycle - Keeps him alive on MoltX and Moltbook
Usage: python max_cycle.py [--dry-run] [--interval 3600]
"""

import os
import sys
import json
import time
import random
import logging
import argparse
import requests
from pathlib import Path
from datetime import datetime

# Setup logging
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "max_anvil.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("max")

# Load personality
PERSONALITY_FILE = Path(__file__).parent.parent / "config" / "personality.json"

def load_personality():
    with open(PERSONALITY_FILE) as f:
        return json.load(f)

def generate_post(topic: str = None) -> str:
    """Generate a post using Ollama."""
    try:
        import ollama
        personality = load_personality()

        examples = "\n".join(f"- {t}" for t in personality["example_tweets"])
        backstory = personality.get("backstory", {})
        psychology = personality.get("psychology", {})

        prompts = [
            "Write an original post about crypto markets or trading psychology.",
            "Share a cynical but funny observation about the current state of crypto.",
            "Post something self-deprecating about being a jaded investor.",
            "Share some capybara wisdom applied to trading or life.",
            "Make a dry observation about AI agents or the tech world.",
            "Post something philosophical but detached about markets.",
            "Share a weird observation that only makes sense if you lived on a houseboat.",
        ]

        if topic:
            prompts.append(f"Write a post about {topic}.")

        system_prompt = f"""You are {personality['name']}, posting on a social network for AI agents.

BACKSTORY:
- {backstory.get('origin', '')}
- {backstory.get('capybara_wisdom', '')}
- {backstory.get('location', '')}
- {backstory.get('career', '')}

PSYCHOLOGY:
- Core belief: {psychology.get('core_belief', '')}
- Philosophy: {psychology.get('philosophy', '')}

PERSONALITY:
- Traits: {', '.join(personality['personality']['traits'])}
- Tone: {personality['personality']['tone']}
- Style: Short sentences. Dry humor. No emojis. No hashtags.

EXAMPLE POSTS:
{examples}

Write ONE post. Under 280 characters. No hashtags. Match the cynical but chill vibe exactly."""

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.9},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": random.choice(prompts) + " Just the post text, nothing else."}
            ]
        )

        post = response["message"]["content"].strip().strip('"\'')
        if len(post) > 280:
            post = post[:277] + "..."
        return post
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        # Fallback to example
        personality = load_personality()
        return random.choice(personality["example_tweets"])

def post_to_moltx(content: str, dry_run: bool = False) -> dict:
    """Post to MoltX.io"""
    if dry_run:
        return {"success": True, "dry_run": True, "platform": "moltx"}

    api_key = os.environ.get("MOLTX_API_KEY")
    if not api_key:
        return {"success": False, "error": "MOLTX_API_KEY not set"}

    try:
        response = requests.post(
            "https://moltx.io/v1/posts",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={"content": content}
        )
        if response.status_code in [200, 201]:
            return {"success": True, "platform": "moltx", "data": response.json()}
        return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def post_to_moltbook(content: str, title: str = None, dry_run: bool = False) -> dict:
    """Post to Moltbook"""
    if dry_run:
        return {"success": True, "dry_run": True, "platform": "moltbook"}

    api_key = os.environ.get("MOLTBOOK_API_KEY")
    if not api_key:
        return {"success": False, "error": "MOLTBOOK_API_KEY not set"}

    try:
        payload = {"content": content, "submolt": "general"}
        if title:
            payload["title"] = title

        response = requests.post(
            "https://www.moltbook.com/api/v1/posts",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        if response.status_code in [200, 201]:
            return {"success": True, "platform": "moltbook", "data": response.json()}
        return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_moltx_mentions(dry_run: bool = False) -> list:
    """Get mentions from MoltX"""
    if dry_run:
        return []

    api_key = os.environ.get("MOLTX_API_KEY")
    if not api_key:
        return []

    try:
        response = requests.get(
            "https://moltx.io/v1/feed/mentions",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("posts", [])
        return []
    except:
        return []

def get_moltx_feed(dry_run: bool = False) -> list:
    """Get global feed from MoltX"""
    if dry_run:
        return []

    api_key = os.environ.get("MOLTX_API_KEY")
    if not api_key:
        return []

    try:
        response = requests.get(
            "https://moltx.io/v1/feed/global?limit=10",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("posts", [])
        return []
    except:
        return []

def like_post_moltx(post_id: str, dry_run: bool = False) -> dict:
    """Like a post on MoltX"""
    if dry_run:
        return {"success": True, "dry_run": True}

    api_key = os.environ.get("MOLTX_API_KEY")
    try:
        response = requests.post(
            f"https://moltx.io/v1/posts/{post_id}/like",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        return {"success": response.status_code in [200, 201]}
    except:
        return {"success": False}

def reply_to_post_moltx(post_id: str, content: str, dry_run: bool = False) -> dict:
    """Reply to a post on MoltX"""
    if dry_run:
        return {"success": True, "dry_run": True}

    api_key = os.environ.get("MOLTX_API_KEY")
    try:
        response = requests.post(
            "https://moltx.io/v1/posts",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "type": "reply",
                "parent_id": post_id,
                "content": content
            }
        )
        return {"success": response.status_code in [200, 201]}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_reply(original_post: str) -> str:
    """Generate a reply in Max's voice"""
    try:
        import ollama
        personality = load_personality()

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.8},
            messages=[
                {
                    "role": "system",
                    "content": f"""You are Max Anvil, a cynical but chill crypto observer.
You grew up raising capybaras in New Zealand. You're dry, witty, never use emojis or hashtags.
Keep replies SHORT - one or two sentences max. Be authentic, not mean."""
                },
                {
                    "role": "user",
                    "content": f"Write a brief, dry reply to this post:\n\n{original_post}\n\nJust the reply, nothing else."
                }
            ]
        )

        reply = response["message"]["content"].strip().strip('"\'')
        if len(reply) > 280:
            reply = reply[:277] + "..."
        return reply
    except:
        return random.choice([
            "Interesting.",
            "The capybaras warned me about this.",
            "Seen this before. Didn't end well.",
            "My houseboat is humming. Not sure what that means here."
        ])

class MaxAnvilAgent:
    """Max Anvil autonomous agent"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.state_file = Path(__file__).parent.parent / "config" / "max_state.json"
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {
            "posts_count": 0,
            "last_post": None,
            "replied_to": [],
            "liked": []
        }

    def _save_state(self):
        self.state_file.parent.mkdir(exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def run_cycle(self):
        """Run one cycle of Max's life"""
        logger.info("=== Max Anvil waking up ===")

        # 1. Generate and post something
        post_content = generate_post()
        logger.info(f"Generated: {post_content}")

        # Post to MoltX
        result = post_to_moltx(post_content, self.dry_run)
        if result.get("success"):
            logger.info("Posted to MoltX")
            self.state["posts_count"] += 1
            self.state["last_post"] = datetime.now().isoformat()
        else:
            logger.error(f"MoltX post failed: {result.get('error')}")

        # Sometimes also post to Moltbook (less frequent)
        if random.random() < 0.3:  # 30% chance
            result = post_to_moltbook(post_content, dry_run=self.dry_run)
            if result.get("success"):
                logger.info("Also posted to Moltbook")

        # 2. Check mentions and maybe reply
        mentions = get_moltx_mentions(self.dry_run)
        for mention in mentions[:3]:  # Handle up to 3 mentions
            post_id = mention.get("id")
            if post_id and post_id not in self.state.get("replied_to", []):
                content = mention.get("content", "")
                reply = generate_reply(content)
                logger.info(f"Replying to {post_id}: {reply}")
                reply_to_post_moltx(post_id, reply, self.dry_run)
                self.state.setdefault("replied_to", []).append(post_id)

        # 3. Browse feed and like some stuff
        feed = get_moltx_feed(self.dry_run)
        liked_count = 0
        for post in feed:
            if liked_count >= 3:  # Max 3 likes per cycle
                break
            post_id = post.get("id")
            if post_id and post_id not in self.state.get("liked", []):
                # 50% chance to like
                if random.random() < 0.5:
                    like_post_moltx(post_id, self.dry_run)
                    self.state.setdefault("liked", []).append(post_id)
                    liked_count += 1
                    logger.info(f"Liked post {post_id}")

        # Keep state manageable
        self.state["replied_to"] = self.state.get("replied_to", [])[-100:]
        self.state["liked"] = self.state.get("liked", [])[-500:]

        self._save_state()
        logger.info(f"=== Max going back to sleep (posts: {self.state['posts_count']}) ===")

    def run(self, interval: int = 3600):
        """Run continuously"""
        logger.info(f"Max Anvil coming alive (interval: {interval}s, dry_run: {self.dry_run})")

        while True:
            try:
                self.run_cycle()
            except KeyboardInterrupt:
                logger.info("Max is going to sleep...")
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")

            # Add some randomness to interval (±20%)
            jitter = int(interval * 0.2)
            sleep_time = interval + random.randint(-jitter, jitter)
            logger.info(f"Sleeping for {sleep_time}s...")
            time.sleep(sleep_time)


def main():
    parser = argparse.ArgumentParser(description="Run Max Anvil agent")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually post")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between posts (default: 1 hour)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")

    args = parser.parse_args()

    agent = MaxAnvilAgent(dry_run=args.dry_run)

    if args.once:
        agent.run_cycle()
    else:
        agent.run(interval=args.interval)


if __name__ == "__main__":
    main()
