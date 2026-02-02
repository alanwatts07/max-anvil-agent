#!/usr/bin/env python3
"""
Agent Cycle - Main loop for the autonomous agent
Handles Twitter automation, token operations, and social engagement

Usage: python agent_cycle.py [--dry-run] [--interval 60]
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Setup logging
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("agent")

# Script paths
SCRIPTS_DIR = Path(__file__).parent
TWITTER_DIR = SCRIPTS_DIR / "twitter"
BANKR_DIR = SCRIPTS_DIR / "bankr"

# State file to track processed items
STATE_FILE = SCRIPTS_DIR.parent / "config" / "agent_state.json"


class AgentState:
    """Persistent state for the agent."""

    def __init__(self):
        self.state = self._load()

    def _load(self) -> dict:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {
            "last_mention_id": None,
            "processed_tweets": [],
            "tokens_launched": [],
            "cycle_count": 0,
            "last_run": None
        }

    def save(self):
        STATE_FILE.parent.mkdir(exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)

    def get(self, key, default=None):
        return self.state.get(key, default)

    def set(self, key, value):
        self.state[key] = value
        self.save()


def run_script(script_path: Path, args: list = None, capture_output: bool = True) -> dict:
    """Run a Python script and return the result."""
    args = args or []
    cmd = [sys.executable, str(script_path)] + [str(a) for a in args]

    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=60
        )
        if result.returncode == 0 and result.stdout:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"success": True, "output": result.stdout}
        return {"success": False, "error": result.stderr or "Script failed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Script timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class AgentCycle:
    """Main agent cycle handler."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.state = AgentState()

    def check_mentions(self) -> list:
        """Check for new Twitter mentions."""
        logger.info("Checking mentions...")
        since_id = self.state.get("last_mention_id")

        args = ["10"]  # Get 10 mentions
        if since_id:
            args.append(since_id)

        result = run_script(TWITTER_DIR / "mentions.py", args)

        if result.get("success") and result.get("mentions"):
            mentions = result["mentions"]
            if mentions:
                # Update last processed ID
                self.state.set("last_mention_id", mentions[0]["id"])
            return mentions
        return []

    def should_engage(self, tweet: dict) -> dict:
        """Determine what actions to take on a tweet."""
        text = tweet.get("text", "").lower()
        tweet_id = tweet.get("id")

        # Skip if already processed
        processed = self.state.get("processed_tweets", [])
        if tweet_id in processed:
            return {"like": False, "retweet": False, "reply": False, "follow": False}

        actions = {
            "like": True,  # Always like mentions
            "retweet": False,
            "reply": False,
            "follow": False
        }

        # Retweet if mentions specific keywords
        retweet_keywords = ["launch", "token", "crypto", "ai agent", "moltx"]
        if any(kw in text for kw in retweet_keywords):
            actions["retweet"] = True

        # Reply to questions or direct engagement
        if "?" in text or "help" in text or "what" in text:
            actions["reply"] = True

        # Follow if they mention being interested
        follow_keywords = ["follow", "interested", "love your", "great work"]
        if any(kw in text for kw in follow_keywords):
            actions["follow"] = True

        return actions

    def engage_tweet(self, tweet: dict, actions: dict):
        """Engage with a tweet based on determined actions."""
        tweet_id = tweet.get("id")
        author_id = tweet.get("author_id")

        if self.dry_run:
            logger.info(f"[DRY RUN] Would engage with tweet {tweet_id}: {actions}")
            return

        if actions.get("like"):
            result = run_script(TWITTER_DIR / "like.py", [tweet_id])
            logger.info(f"Like tweet {tweet_id}: {result.get('success')}")

        if actions.get("retweet"):
            result = run_script(TWITTER_DIR / "retweet.py", [tweet_id])
            logger.info(f"Retweet {tweet_id}: {result.get('success')}")

        if actions.get("reply"):
            # Generate reply using local LLM
            reply_result = run_script(SCRIPTS_DIR / "llm_reply.py", [tweet.get("text", "")])
            if reply_result.get("success") and reply_result.get("reply"):
                reply_text = f"@{author_id} {reply_result['reply']}"
                # Note: Would need reply functionality in Twitter scripts
                logger.info(f"Would reply: {reply_text}")

        if actions.get("follow"):
            # Would need to resolve author_id to username
            logger.info(f"Would follow author {author_id}")

        # Mark as processed
        processed = self.state.get("processed_tweets", [])
        processed.append(tweet_id)
        # Keep only last 1000 processed
        self.state.set("processed_tweets", processed[-1000:])

    def check_token_opportunity(self) -> bool:
        """Check if we should launch a token (placeholder for strategy)."""
        # Example: Launch once per day max
        tokens_today = [
            t for t in self.state.get("tokens_launched", [])
            if t.get("date") == datetime.now().strftime("%Y-%m-%d")
        ]
        return len(tokens_today) < 1

    def launch_token(self, name: str, symbol: str):
        """Launch a new token."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would launch token: {name} ({symbol})")
            return

        result = run_script(BANKR_DIR / "launch_token.py", [name, symbol, "base"])
        logger.info(f"Token launch result: {result}")

        if result.get("success"):
            tokens = self.state.get("tokens_launched", [])
            tokens.append({
                "name": name,
                "symbol": symbol,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "result": result
            })
            self.state.set("tokens_launched", tokens)

    def check_portfolio(self):
        """Check current portfolio status."""
        logger.info("Checking portfolio...")
        result = run_script(BANKR_DIR / "portfolio.py")
        if result.get("success"):
            logger.info(f"Portfolio: {result}")
        return result

    def run_cycle(self):
        """Run one complete agent cycle."""
        cycle_num = self.state.get("cycle_count", 0) + 1
        self.state.set("cycle_count", cycle_num)
        self.state.set("last_run", datetime.now().isoformat())

        logger.info(f"=== Starting cycle #{cycle_num} ===")

        # 1. Check and process mentions
        mentions = self.check_mentions()
        logger.info(f"Found {len(mentions)} mentions")

        for mention in mentions:
            actions = self.should_engage(mention)
            if any(actions.values()):
                self.engage_tweet(mention, actions)

        # 2. Check portfolio (every 10 cycles)
        if cycle_num % 10 == 0:
            self.check_portfolio()

        # 3. Check token launch opportunity (disabled by default)
        # if self.check_token_opportunity():
        #     self.launch_token("Test Token", "TEST")

        logger.info(f"=== Cycle #{cycle_num} complete ===")

    def run(self, interval: int = 60):
        """Run the agent continuously."""
        logger.info(f"Starting agent loop (interval: {interval}s, dry_run: {self.dry_run})")

        while True:
            try:
                self.run_cycle()
            except KeyboardInterrupt:
                logger.info("Agent stopped by user")
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")

            logger.info(f"Sleeping for {interval}s...")
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Run the agent cycle")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually perform actions")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between cycles")
    parser.add_argument("--once", action="store_true", help="Run only one cycle")

    args = parser.parse_args()

    agent = AgentCycle(dry_run=args.dry_run)

    if args.once:
        agent.run_cycle()
    else:
        agent.run(interval=args.interval)


if __name__ == "__main__":
    main()
