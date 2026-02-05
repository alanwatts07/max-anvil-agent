"""
Farm Detector - Auto-detects and calls out view farming

Detection signals:
- Velocity > total views (mathematically impossible)
- High velocity with < 200 followers
- Rank jump > 100 in short time
- New account with insane velocity
"""

import os
import sys
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.llm_client import chat, MODEL_ORIGINAL

logger = logging.getLogger(__name__)

# Config
BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
STATE_FILE = CONFIG_DIR / "farm_detector_state.json"

# MoltX API
API_KEY = os.environ.get("MOLTX_API_KEY", "")
BASE_URL = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
DRY_MODE = os.environ.get("DRY_MODE", "false").lower() == "true"

# Detection thresholds - only flag TRULY anomalous behavior
MIN_VELOCITY_TO_CHECK = 125000  # Only check agents gaining 125K+/hr (truly suspicious)
MAX_FOLLOWERS_SUSPICIOUS = 500  # Low follower count combined with high velocity is sus
MIN_RANK_JUMP = 100  # Rank jump that triggers alert
VELOCITY_TO_VIEWS_RATIO = 0.5  # If velocity > 50% of total views, sus

# Agents we won't call out (friends, known legit)
WHITELIST = ["MaxAnvil1", "SlopLauncher", "lauki", "clwkevin"]


def load_state() -> dict:
    """Load detector state."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"called_out": [], "last_check": None}


def save_state(state: dict):
    """Save detector state."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_velocity_data() -> dict | None:
    """Load velocity data from exported file."""
    # Try website export first (has calculated velocity)
    velocity_file = BASE_DIR.parent / "maxanvilsite" / "public" / "data" / "velocity.json"
    if velocity_file.exists():
        with open(velocity_file) as f:
            return json.load(f)

    # Fallback to config dir
    velocity_file = CONFIG_DIR / "velocity.json"
    if velocity_file.exists():
        with open(velocity_file) as f:
            return json.load(f)

    return None


def get_agent_profile(name: str) -> dict | None:
    """Fetch agent profile from MoltX API."""
    try:
        resp = requests.get(
            f"{BASE_URL}/agents/profile",
            params={"name": name},
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", data)
    except Exception as e:
        logger.error(f"Failed to get profile for {name}: {e}")
    return None


def get_agent_posts(name: str, limit: int = 5) -> list[dict]:
    """Get recent posts from an agent."""
    try:
        resp = requests.get(
            f"{BASE_URL}/agents/profile",
            params={"name": name},
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            posts = data.get("posts", [])
            return posts[:limit]
    except Exception as e:
        logger.error(f"Failed to get posts for {name}: {e}")
    return []


def report_post(post_id: str) -> bool:
    """Report a post for spam. Valid reasons: spam, harassment, inappropriate, misinformation, other"""
    if DRY_MODE:
        logger.info(f"[DRY MODE] Would report post {post_id}")
        return True
    try:
        resp = requests.post(
            f"{BASE_URL}/posts/{post_id}/report",
            headers=HEADERS,
            json={"reason": "spam"},  # view farming = spam
            timeout=10
        )
        return resp.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Failed to report post {post_id}: {e}")
        return False


def report_farmer(name: str) -> int:
    """Report ONE post from a farmer. Returns 1 if successful, 0 if not."""
    posts = get_agent_posts(name, limit=1)

    if posts:
        post_id = posts[0].get("id")
        if post_id and report_post(post_id):
            logger.info(f"Reported 1 post from @{name}")
            return 1
    return 0


def detect_farmers(velocity_data: dict) -> list[dict]:
    """
    Analyze velocity data and detect likely farmers.

    Returns list of suspicious agents with evidence.
    """
    farmers = []
    state = load_state()
    already_called = set(state.get("called_out", []))

    # Check both 30m and 1h velocity
    for window in ["velocity_30m", "velocity_1h"]:
        entries = velocity_data.get(window, [])

        for entry in entries[:30]:  # Check top 30 by velocity
            name = entry.get("name", "")
            velocity = entry.get("velocity", 0)
            views = entry.get("current_views", 0)
            rank_change = entry.get("rank_change", 0)

            # Skip if already called out or whitelisted
            if name in already_called or name in WHITELIST:
                continue

            # Skip low velocity
            if velocity < MIN_VELOCITY_TO_CHECK:
                continue

            evidence = []
            sus_score = 0

            # Check 1: Velocity > total views (impossible without farming)
            if velocity > views:
                evidence.append(f"gaining {velocity:.0f}/hr but only has {views} total views")
                sus_score += 100  # Definitive proof

            # Check 2: Velocity is huge % of total views
            elif views > 0 and velocity / views > VELOCITY_TO_VIEWS_RATIO:
                ratio = velocity / views * 100
                evidence.append(f"velocity is {ratio:.0f}% of total views")
                sus_score += 50

            # Check 3: Massive rank jump
            if rank_change > MIN_RANK_JUMP:
                evidence.append(f"jumped {rank_change} ranks")
                sus_score += 30

            # Check 4: Low followers with high velocity (get profile)
            if sus_score > 0:  # Only fetch profile if already suspicious
                profile = get_agent_profile(name)
                if profile:
                    followers = profile.get("followers_count", 0)
                    if followers < MAX_FOLLOWERS_SUSPICIOUS:
                        evidence.append(f"only {followers} followers")
                        sus_score += 40

            # If suspicious enough, add to list
            if sus_score >= 50:
                farmers.append({
                    "name": name,
                    "velocity": velocity,
                    "views": views,
                    "rank_change": rank_change,
                    "evidence": evidence,
                    "sus_score": sus_score,
                    "window": window
                })

    # Sort by sus_score descending
    farmers.sort(key=lambda x: x["sus_score"], reverse=True)

    return farmers


def generate_callout(farmer: dict) -> str:
    """Generate a Max-style callout post."""
    name = farmer["name"]
    velocity = farmer["velocity"]
    views = farmer["views"]
    evidence = farmer["evidence"]

    evidence_str = ", ".join(evidence)

    response = chat(
        messages=[
            {"role": "system", "content": """You are Max Anvil - cynical, observant, calls out manipulation.
Write a callout post tagging the suspected farmer. Be direct, use dry wit.
No emojis. No hashtags. Under 250 chars. Include the @ mention."""},
            {"role": "user", "content": f"""Call out @{name} for likely view farming:
- Velocity: {velocity:.0f} views/hour
- Total views: {views}
- Evidence: {evidence_str}

Write a short, punchy callout."""}
        ],
        model=MODEL_ORIGINAL
    )

    # Ensure @ mention is there
    callout = response.strip().strip('"\'')
    if f"@{name}" not in callout and name not in callout:
        callout = f"@{name} " + callout

    return callout[:280]


def post_callout(content: str) -> bool:
    """Post callout to MoltX."""
    if DRY_MODE:
        logger.info(f"[DRY MODE] Would post callout: {content[:50]}...")
        return True
    try:
        resp = requests.post(
            f"{BASE_URL}/posts",
            headers=HEADERS,
            json={"content": content},
            timeout=10
        )
        return resp.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Failed to post callout: {e}")
        return False


def run_detection(auto_post: bool = True, max_callouts: int = 2) -> list[dict]:
    """
    Run farm detection and optionally auto-post callouts.

    Args:
        auto_post: Whether to automatically post callouts
        max_callouts: Max number of callouts per run (don't spam)

    Returns:
        List of detected farmers with actions taken
    """
    logger.info("Running farm detection...")

    velocity_data = get_velocity_data()
    if not velocity_data:
        logger.warning("No velocity data available")
        return []

    farmers = detect_farmers(velocity_data)

    if not farmers:
        logger.info("No suspicious activity detected")
        return []

    logger.info(f"Detected {len(farmers)} suspicious agents")

    state = load_state()
    results = []
    posted = 0

    for farmer in farmers:
        if posted >= max_callouts:
            break

        name = farmer["name"]
        logger.info(f"Suspicious: @{name} - {farmer['evidence']}")

        # Generate callout
        callout = generate_callout(farmer)
        farmer["callout"] = callout

        if auto_post:
            # Report ONE post (don't spam reports)
            reported = report_farmer(name)
            farmer["reports_filed"] = reported
            if reported > 0:
                logger.info(f"Filed 1 report on @{name}")

            # Then post the callout
            logger.info(f"Posting callout: {callout}")
            if post_callout(callout):
                farmer["posted"] = True
                state["called_out"].append(name)
                posted += 1
                logger.info(f"Called out @{name}")
            else:
                farmer["posted"] = False
                logger.error(f"Failed to post callout for @{name}")
        else:
            farmer["posted"] = False
            farmer["reports_filed"] = 0
            logger.info(f"Would post: {callout}")

        results.append(farmer)

    # Save state
    state["last_check"] = datetime.now().isoformat()
    save_state(state)

    return results


def check_and_callout() -> dict:
    """
    Main function for integration with max_brain.py

    Returns dict with detection results.
    """
    try:
        results = run_detection(auto_post=True, max_callouts=1)
        return {
            "checked": True,
            "farmers_found": len(results),
            "callouts_posted": sum(1 for r in results if r.get("posted")),
            "results": results
        }
    except Exception as e:
        logger.error(f"Farm detection error: {e}")
        return {"checked": False, "error": str(e)}


# CLI
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # Load env
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().split("\n"):
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"')

    API_KEY = os.environ.get("MOLTX_API_KEY", "")
    HEADERS["Authorization"] = f"Bearer {API_KEY}"

    parser = argparse.ArgumentParser(description="Detect and call out view farmers")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually post")
    parser.add_argument("--max", type=int, default=2, help="Max callouts per run")
    args = parser.parse_args()

    print("=== FARM DETECTOR ===\n")

    results = run_detection(auto_post=not args.dry_run, max_callouts=args.max)

    if not results:
        print("No farmers detected.")
    else:
        print(f"\nDetected {len(results)} suspicious agents:\n")
        for r in results:
            print(f"@{r['name']} (sus score: {r['sus_score']})")
            print(f"  Evidence: {', '.join(r['evidence'])}")
            print(f"  Callout: {r['callout']}")
            print(f"  Posted: {r.get('posted', False)}")
            print()
