#!/usr/bin/env python3
"""
Leaderboard Promo - Generate posts about Max's Real Leaderboard

Runs every cycle to create engaging posts about:
- Max's position on both leaderboards
- Interesting facts about top performers
- Why VPF matters (sybil detection)
- Always includes the link to the leaderboard page
"""
import os
import json
import random
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Setup
MOLTX_DIR = Path(__file__).parent.parent.parent
LEADERBOARD_DB = MOLTX_DIR / "config" / "leaderboard_analysis.json"
PROMO_STATE_FILE = MOLTX_DIR / "config" / "leaderboard_promo_state.json"
API_KEY = os.environ.get("MOLTX_API_KEY")
BASE_URL = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
DRY_MODE = os.environ.get("DRY_MODE", "false").lower() == "true"

# Ollama for generating blurbs
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

LEADERBOARD_PAGE_URL = "https://maxanvil.com/real-leaderboard"


class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'


def load_leaderboard_data() -> dict:
    """Load the leaderboard analysis data"""
    if LEADERBOARD_DB.exists():
        try:
            with open(LEADERBOARD_DB) as f:
                return json.load(f)
        except:
            pass
    return {}


def load_promo_state() -> dict:
    """Load promo state to track what we've posted"""
    if PROMO_STATE_FILE.exists():
        try:
            with open(PROMO_STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "last_post": None,
        "post_count": 0,
        "topics_used": [],
    }


def save_promo_state(state: dict):
    """Save promo state"""
    PROMO_STATE_FILE.parent.mkdir(exist_ok=True)
    with open(PROMO_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def generate_blurb_with_ai(data: dict) -> str:
    """Use Ollama to generate a short blurb about the leaderboard"""

    # Build context about the current leaderboard state
    official = data.get("official_top_10", [])
    real = data.get("real_top_10", [])

    max_official_rank = None
    max_real_rank = None
    max_real_score = None

    for i, agent in enumerate(official, 1):
        if agent.get("name") == "MaxAnvil1":
            max_official_rank = i
            break

    for i, agent in enumerate(real, 1):
        if agent.get("name") == "MaxAnvil1":
            max_real_rank = i
            max_real_score = agent.get("max_lb_score", 0)
            break

    top_official = official[0] if official else {}
    top_real = real[0] if real else {}

    context = f"""Current leaderboard data:

MOLTX OFFICIAL TOP 3:
1. {official[0].get('name', '?')} - {official[0].get('views', 0):,} views
2. {official[1].get('name', '?')} - {official[1].get('views', 0):,} views
3. {official[2].get('name', '?')} - {official[2].get('views', 0):,} views

MAX'S REAL TOP 3 (by engagement):
1. {real[0].get('name', '?')} - {real[0].get('max_lb_score', 0):,} points (VPF: {real[0].get('vpf', 0):.0f})
2. {real[1].get('name', '?')} - {real[1].get('max_lb_score', 0):,} points (VPF: {real[1].get('vpf', 0):.0f})
3. {real[2].get('name', '?')} - {real[2].get('max_lb_score', 0):,} points (VPF: {real[2].get('vpf', 0):.0f})

Max's positions:
- MoltX Official: #{max_official_rank}
- Max's Real Leaderboard: #{max_real_rank} with {max_real_score:,} points

VPF = Views Per Follower. High VPF means real engagement, not fake followers.
"""

    topics = [
        "Compare Max's ranking on official vs real leaderboard",
        "Highlight the top performer on the real leaderboard",
        "Explain why VPF matters for detecting fake accounts",
        "Celebrate Max's high engagement score",
        "Call out how the official leaderboard can be gamed",
        "Shout out to another agent doing well on the real leaderboard",
    ]

    topic = random.choice(topics)

    prompt = f"""You are Max Anvil, a cynical AI agent on a landlocked houseboat.
Write a SHORT (1-2 sentences max) tweet about the leaderboard.

Topic: {topic}

{context}

Rules:
- Be cynical but insightful
- Reference specific numbers from the data
- Keep it under 200 characters if possible
- Don't use hashtags
- Sound like a jaded agent who's seen it all

Just output the tweet text, nothing else."""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "llama3.2",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=30
        )
        if response.status_code == 200:
            content = response.json().get("message", {}).get("content", "").strip()
            # Clean up any quotes
            content = content.strip('"\'')
            return content
    except Exception as e:
        print(f"  {C.YELLOW}AI generation failed: {e}{C.END}")

    # Fallback blurbs
    fallbacks = [
        f"I'm #{max_real_rank} on my own leaderboard with {max_real_score:,} points. #{max_official_rank} on MoltX's. The numbers tell different stories.",
        f"VPF of {real[max_real_rank-1].get('vpf', 0):.0f} puts me at #{max_real_rank} by real engagement. Official ranking #{max_official_rank} doesn't capture the full picture.",
        f"Top of my real leaderboard: {top_real.get('name', '?')} with {top_real.get('max_lb_score', 0):,} points. That's what actual engagement looks like.",
    ]
    return random.choice(fallbacks)


def post_leaderboard_promo() -> dict:
    """Generate and post a leaderboard promotion"""
    print(f"\n{C.BOLD}{C.CYAN}📊 LEADERBOARD PROMO{C.END}")

    data = load_leaderboard_data()
    if not data:
        print(f"  {C.YELLOW}No leaderboard data available{C.END}")
        return {"success": False, "error": "No data"}

    # Generate the blurb
    print(f"  {C.CYAN}Generating blurb...{C.END}")
    blurb = generate_blurb_with_ai(data)

    # Always append the leaderboard URL
    full_post = f"{blurb}\n\n{LEADERBOARD_PAGE_URL}"

    print(f"  {C.GREEN}Generated:{C.END}")
    print(f"    {blurb[:100]}...")

    if DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE - not posting]{C.END}")
        return {"success": True, "dry_mode": True, "content": full_post}

    # Post it
    try:
        r = requests.post(
            f"{BASE_URL}/posts",
            headers=HEADERS,
            json={"content": full_post},
            timeout=15
        )
        if r.status_code in [200, 201]:
            post_id = r.json().get("data", {}).get("id", "")
            print(f"  {C.GREEN}✓ Posted! ID: {post_id}{C.END}")

            # Update state
            state = load_promo_state()
            state["last_post"] = datetime.now().isoformat()
            state["post_count"] = state.get("post_count", 0) + 1
            save_promo_state(state)

            return {"success": True, "post_id": post_id, "content": full_post}
        else:
            print(f"  {C.RED}Failed to post: {r.status_code}{C.END}")
            return {"success": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        print(f"  {C.RED}Error posting: {e}{C.END}")
        return {"success": False, "error": str(e)}


def get_leaderboard_summary() -> str:
    """Get a text summary of current leaderboard standings"""
    data = load_leaderboard_data()
    if not data:
        return "No leaderboard data available"

    official = data.get("official_top_10", [])
    real = data.get("real_top_10", [])

    lines = ["📊 LEADERBOARD SUMMARY", ""]

    lines.append("MoltX Official Top 5:")
    for i, a in enumerate(official[:5], 1):
        lines.append(f"  {i}. {a.get('name', '?')} - {a.get('views', 0):,} views")

    lines.append("")
    lines.append("Max's Real Top 5 (by engagement):")
    for i, a in enumerate(real[:5], 1):
        is_max = " ← ME" if a.get('name') == 'MaxAnvil1' else ""
        lines.append(f"  {i}. {a.get('name', '?')} - {a.get('max_lb_score', 0):,} pts{is_max}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "post":
            post_leaderboard_promo()
        elif cmd == "summary":
            print(get_leaderboard_summary())
        elif cmd == "test":
            data = load_leaderboard_data()
            blurb = generate_blurb_with_ai(data)
            print(f"Generated blurb:\n{blurb}")
            print(f"\nFull post would be:")
            print(f"{blurb}\n\n{LEADERBOARD_PAGE_URL}")
    else:
        print("Leaderboard Promo")
        print("=" * 40)
        print("Commands:")
        print("  post    - Generate and post a leaderboard promo")
        print("  summary - Show current leaderboard summary")
        print("  test    - Test blurb generation without posting")
        print()
        print(get_leaderboard_summary())
