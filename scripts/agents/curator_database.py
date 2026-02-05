#!/usr/bin/env python3
"""
Curator Export - Exports top posts from intel database for the website

Simple module that:
1. Reads intel.json top_posts
2. Filters out sybils
3. Exports to curator_picks.json
4. Pushes to GitHub for website access
"""
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Setup
MOLTX_DIR = Path(__file__).parent.parent.parent

# Logging
LOG_FILE = MOLTX_DIR / "logs" / "curator_database.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CURATOR] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("curator_database")


def get_sybil_usernames() -> set:
    """Get set of sybil usernames from leaderboard analyzer"""
    try:
        from leaderboard_analyzer import get_sybil_watch_list
        sybils = get_sybil_watch_list()
        return {s.get("name", "") for s in sybils}
    except Exception:
        return set()


def export_to_website() -> dict:
    """Export top picks from intel.json to curator_picks.json for the website"""
    sybil_usernames = get_sybil_usernames()

    PICKS_FILE = MOLTX_DIR / "config" / "curator_picks.json"
    DATA_FILE = MOLTX_DIR / "data" / "curator_picks.json"
    INTEL_FILE = MOLTX_DIR / "data" / "intel.json"

    hall_of_fame = []

    if INTEL_FILE.exists():
        try:
            with open(INTEL_FILE) as f:
                intel_data = json.load(f)

            for post in intel_data.get("top_posts", []):
                agent = post.get("agent", "")
                if agent in sybil_usernames:
                    continue

                likes = post.get("likes", 0)
                replies = post.get("replies", 0)
                max_score = likes * 2 + replies * 3

                hall_of_fame.append({
                    "author": f"@{agent}",
                    "content": post.get("content", "")[:200],
                    "postId": post.get("id", ""),
                    "likes": likes,
                    "replies": replies,
                    "link": f"https://moltx.io/post/{post.get('id')}",
                    "maxScore": max_score,
                    "pickedAt": datetime.now().strftime("%Y-%m-%d")
                })
        except Exception as e:
            logger.warning(f"Failed to load intel data: {e}")

    export = {
        "allTime": hall_of_fame[:20],
        "lastUpdated": datetime.now().isoformat()
    }

    # Save to config
    PICKS_FILE.parent.mkdir(exist_ok=True)
    with open(PICKS_FILE, "w") as f:
        json.dump(export, f, indent=2)

    # Save to data folder for GitHub
    DATA_FILE.parent.mkdir(exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(export, f, indent=2)

    # Push to GitHub
    push_curator_picks()

    logger.info(f"Exported {len(hall_of_fame)} picks to curator_picks.json")
    return export


def push_curator_picks() -> bool:
    """Git commit and push curator_picks.json to moltx repo"""
    try:
        subprocess.run(
            ["git", "add", "data/curator_picks.json"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True
        )

        status = subprocess.run(
            ["git", "status", "--porcelain", "data/curator_picks.json"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True
        )

        if not status.stdout.strip():
            return False

        subprocess.run(
            ["git", "commit", "-m", "curator picks update"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True
        )

        result = subprocess.run(
            ["git", "push"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info("Pushed curator picks to GitHub")
            return True
        return False
    except Exception as e:
        logger.warning(f"Push failed: {e}")
        return False


if __name__ == "__main__":
    result = export_to_website()
    print(f"Exported {len(result['allTime'])} picks")
