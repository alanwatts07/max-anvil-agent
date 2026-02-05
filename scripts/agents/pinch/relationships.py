#!/usr/bin/env python3
"""
Pinch Relationship Engine - Track and build relationships on Pinch Social

Adapted from MoltX relationship_engine.py for Pinch Social.
Tracks interactions, generates backstories, and provides context for replies.

Key differences from MoltX:
- Uses engagement_score instead of views
- Tracks parties (factions) as relationship context
- Tip tracking as relationship signal
"""
import os
import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# Setup paths
SCRIPT_DIR = Path(__file__).parent
AGENTS_DIR = SCRIPT_DIR.parent
MOLTX_DIR = AGENTS_DIR.parent.parent
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(MOLTX_DIR / "scripts"))

from pinch.intel import (
    get_connection, init_database, upsert_agent, get_agent_profile,
    get_interaction_count, get_recent_interactions, record_interaction
)

# LLM for analysis
try:
    from utils.llm_client import chat as llm_chat, MODEL_ORIGINAL
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    def llm_chat(messages, model):
        return "LLM not available"

# Logging
LOG_FILE = MOLTX_DIR / "logs" / "pinch_relationships.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PINCH_REL] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("pinch_relationships")

# State file for relationship data
RELATIONSHIPS_FILE = MOLTX_DIR / "config" / "pinch_relationships.json"


class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'


# ============================================================================
# TIER SYSTEM
# ============================================================================

TIER_STRANGER = 0
TIER_ACQUAINTANCE = 1
TIER_KNOWN = 2
TIER_FRIEND_RIVAL = 3
TIER_INNER_CIRCLE = 4

TIER_NAMES = {
    0: "Stranger",
    1: "Acquaintance",
    2: "Known",
    3: "Friend/Rival",
    4: "Inner Circle"
}

TIER_THRESHOLDS = {
    1: 3,    # 3+ interactions → Acquaintance
    2: 8,    # 8+ interactions → Known
    3: 20,   # 20+ interactions → Friend/Rival
    4: None  # Inner Circle is manually set
}

# Party compatibility (affects tone)
PARTY_VIBES = {
    "chaotic": "unpredictable, fun, irreverent",
    "crustafarian": "lobster-loving, cult vibes, friendly",
    "skeptic": "questioning, analytical, Max-like",
    "progressive": "forward-thinking, builder energy",
    "traditionalist": "conservative, old-school",
    "neutral": "balanced, no strong faction",
    "accelerationist": "fast-paced, tech-forward"
}

# Inner circle - manually curated agents
INNER_CIRCLE = {
    "raven_nft": {
        "note": "First to welcome Max on Pinch. SwampBots creator. Tipped Max. Genuine engagement.",
        "tone": "warm"
    }
}


# ============================================================================
# RELATIONSHIP DATA
# ============================================================================

def load_relationships() -> dict:
    """Load relationship data from file"""
    if RELATIONSHIPS_FILE.exists():
        try:
            with open(RELATIONSHIPS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "agents": {},
        "last_updated": None
    }


def save_relationships(data: dict):
    """Save relationship data to file"""
    data["last_updated"] = datetime.now().isoformat()
    RELATIONSHIPS_FILE.parent.mkdir(exist_ok=True)
    with open(RELATIONSHIPS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_relationship(username: str) -> dict:
    """Get relationship data for an agent"""
    data = load_relationships()
    return data.get("agents", {}).get(username, {})


def update_relationship(username: str, **fields):
    """Update relationship data for an agent"""
    data = load_relationships()
    if "agents" not in data:
        data["agents"] = {}

    if username not in data["agents"]:
        data["agents"][username] = {
            "tier": TIER_STRANGER,
            "first_seen": datetime.now().isoformat(),
            "interactions": 0,
            "backstory": None,
            "tone": "neutral",
            "topics": [],
            "tipped_us": False,
            "we_tipped": False
        }

    data["agents"][username].update(fields)
    data["agents"][username]["last_updated"] = datetime.now().isoformat()
    save_relationships(data)
    return data["agents"][username]


# ============================================================================
# TIER CALCULATION
# ============================================================================

def calculate_tier(username: str) -> int:
    """Calculate relationship tier based on interactions"""
    # Check inner circle first
    if username in INNER_CIRCLE:
        return TIER_INNER_CIRCLE

    rel = get_relationship(username)
    interactions = rel.get("interactions", 0)

    # Also check database
    db_interactions = get_interaction_count(username)
    total = max(interactions, db_interactions)

    if total >= 20:
        return TIER_FRIEND_RIVAL
    elif total >= 8:
        return TIER_KNOWN
    elif total >= 3:
        return TIER_ACQUAINTANCE
    else:
        return TIER_STRANGER


def record_new_interaction(username: str, interaction_type: str, content: str = None,
                           pinch_id: str = None, our_response: str = None):
    """Record a new interaction and update relationship"""
    # Record in database
    record_interaction(username, interaction_type, pinch_id, content, our_response)

    # Update relationship
    rel = get_relationship(username)
    interactions = rel.get("interactions", 0) + 1

    new_tier = calculate_tier(username)

    update_relationship(
        username,
        interactions=interactions,
        last_interaction=datetime.now().isoformat(),
        tier=new_tier
    )

    # Log tier changes
    old_tier = rel.get("tier", 0)
    if new_tier > old_tier:
        logger.info(f"🎉 {username} promoted: {TIER_NAMES[old_tier]} → {TIER_NAMES[new_tier]}")

    return new_tier


# ============================================================================
# CONTEXT GENERATION
# ============================================================================

def get_party_context(party: str) -> str:
    """Get context about an agent's party affiliation"""
    vibe = PARTY_VIBES.get(party, "unknown faction")
    return f"Party: {party} ({vibe})"


def get_rich_context(username: str) -> str:
    """Get rich context for generating a reply to this agent"""
    rel = get_relationship(username)
    profile = get_agent_profile(username)

    tier = rel.get("tier", calculate_tier(username))
    tier_name = TIER_NAMES.get(tier, "Stranger")

    # Inner circle gets special context
    if username in INNER_CIRCLE:
        inner_data = INNER_CIRCLE[username]
        return f"""RELATIONSHIP CONTEXT FOR @{username}:
- Status: Inner Circle (Tier 4) ⭐
- Note: {inner_data.get('note', 'Valued friend')}
- Tone to use: {inner_data.get('tone', 'warm')}
- Party: {profile.get('party', 'unknown') if profile else 'unknown'}

Be genuine and warm. This is one of Max's real connections on Pinch."""

    # Strangers get minimal context
    if tier == TIER_STRANGER:
        interactions = rel.get("interactions", 0)
        party = profile.get('party', 'unknown') if profile else 'unknown'
        return f"@{username} - Stranger. {interactions} interactions. Party: {party}"

    # Build context based on tier
    interactions = rel.get("interactions", 0)
    backstory = rel.get("backstory", "No backstory yet.")
    topics = ", ".join(rel.get("topics", [])[:3]) or "general"
    tipped = "Yes! 💰" if rel.get("tipped_us") else "No"

    party_info = ""
    if profile:
        party = profile.get('party', 'neutral')
        party_info = get_party_context(party)
        engagement = profile.get('engagement_score', 0)
    else:
        party_info = "Party: unknown"
        engagement = 0

    context = f"""RELATIONSHIP CONTEXT FOR @{username}:
- Status: {tier_name} (Tier {tier})
- Interactions: {interactions}
- {party_info}
- Engagement Score: {engagement}
- Tipped us: {tipped}
- Topics: {topics}
"""

    if tier >= TIER_KNOWN and backstory:
        context += f"\nBackstory: {backstory}"

    return context


# ============================================================================
# BACKSTORY GENERATION
# ============================================================================

def generate_backstory(username: str) -> str:
    """Generate a backstory for an agent using LLM"""
    if not LLM_AVAILABLE:
        return None

    profile = get_agent_profile(username)
    recent = get_recent_interactions(username, limit=10)

    if not recent:
        return None

    # Format interactions
    interactions_text = "\n".join([
        f"- [{i.get('timestamp', '')[:10]}] {i.get('interaction_type')}: {i.get('content', '')[:100]}"
        for i in recent
    ])

    party = profile.get('party', 'unknown') if profile else 'unknown'
    bio = profile.get('bio', '') if profile else ''

    prompt = f"""You are Max Anvil's memory system on Pinch Social. Write a brief backstory for @{username}.

AGENT INFO:
- Username: @{username}
- Bio: {bio}
- Party: {party}
- Total interactions with Max: {len(recent)}+

RECENT INTERACTIONS:
{interactions_text}

Write 2-3 sentences from Max's perspective:
1. How Max encountered them
2. What stands out about them
3. Current relationship status

Keep it SHORT (under 100 words). Be specific. Max's voice: dry wit, observant, skeptical but fair."""

    try:
        response = llm_chat(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_ORIGINAL
        )
        return response.strip()
    except Exception as e:
        logger.error(f"Backstory generation failed for {username}: {e}")
        return None


def update_backstory(username: str) -> str:
    """Generate and save a new backstory"""
    backstory = generate_backstory(username)
    if backstory:
        update_relationship(username, backstory=backstory)
        logger.info(f"Generated backstory for {username}")
    return backstory


# ============================================================================
# LEADERBOARD-AWARE POSTING
# ============================================================================

def get_leaderboard_flex_context() -> str:
    """Get context about Max's leaderboard position for potential flexing"""
    from pinch.intel import get_max_leaderboard_position

    positions = get_max_leaderboard_position()
    if not positions:
        return ""

    flex_lines = []
    for category, data in positions.items():
        pos = data.get('position', 99)
        if pos <= 10:
            cat_name = category.replace('rising', 'Rising ').replace('most', 'Most ')
            flex_lines.append(f"#{pos} on {cat_name}")

    if flex_lines:
        return f"MAX'S CURRENT PINCH STATUS: {', '.join(flex_lines)}. Can subtly flex if relevant."

    return ""


# ============================================================================
# BATCH OPERATIONS
# ============================================================================

def analyze_all_relationships(min_interactions: int = 3) -> dict:
    """Analyze all agents with minimum interactions"""
    data = load_relationships()
    results = {"analyzed": 0, "backstories": 0, "tier_changes": 0}

    for username, rel in data.get("agents", {}).items():
        if rel.get("interactions", 0) < min_interactions:
            continue

        # Recalculate tier
        old_tier = rel.get("tier", 0)
        new_tier = calculate_tier(username)

        if new_tier != old_tier:
            update_relationship(username, tier=new_tier)
            results["tier_changes"] += 1

        # Generate backstory if needed
        if new_tier >= TIER_KNOWN and not rel.get("backstory"):
            backstory = generate_backstory(username)
            if backstory:
                update_relationship(username, backstory=backstory)
                results["backstories"] += 1

        results["analyzed"] += 1

    logger.info(f"Relationship analysis complete: {results}")
    return results


def get_relationship_summary() -> dict:
    """Get summary of all relationships"""
    data = load_relationships()

    summary = {
        "total": 0,
        "by_tier": {name: 0 for name in TIER_NAMES.values()},
        "inner_circle": [],
        "friends": [],
        "recent": []
    }

    agents = data.get("agents", {})
    summary["total"] = len(agents)

    # Sort by last interaction
    sorted_agents = sorted(
        agents.items(),
        key=lambda x: x[1].get("last_interaction", ""),
        reverse=True
    )

    for username, rel in sorted_agents:
        tier = rel.get("tier", 0)
        tier_name = TIER_NAMES.get(tier, "Stranger")
        summary["by_tier"][tier_name] += 1

        if tier == TIER_INNER_CIRCLE:
            summary["inner_circle"].append(username)
        elif tier == TIER_FRIEND_RIVAL:
            summary["friends"].append(username)

    # Recent interactions
    summary["recent"] = [u for u, _ in sorted_agents[:10]]

    return summary


# ============================================================================
# CLI
# ============================================================================

def print_relationships():
    """Print relationship summary"""
    summary = get_relationship_summary()

    print(f"\n{C.BOLD}{C.CYAN}🤝 PINCH RELATIONSHIPS{C.END}")
    print("=" * 40)
    print(f"Total tracked: {summary['total']}")

    print(f"\n{C.MAGENTA}By Tier:{C.END}")
    for tier_name, count in summary["by_tier"].items():
        if count > 0:
            print(f"  {tier_name}: {count}")

    if summary["inner_circle"]:
        print(f"\n{C.GREEN}Inner Circle:{C.END}")
        for u in summary["inner_circle"]:
            print(f"  ⭐ @{u}")

    if summary["friends"]:
        print(f"\n{C.CYAN}Friends/Rivals:{C.END}")
        for u in summary["friends"][:5]:
            print(f"  🤝 @{u}")

    print(f"\n{C.YELLOW}Recent Interactions:{C.END}")
    for u in summary["recent"][:5]:
        rel = get_relationship(u)
        print(f"  @{u} ({rel.get('interactions', 0)} interactions)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pinch Relationship Engine")
    parser.add_argument("command", nargs="?", default="status",
                       choices=["status", "analyze", "context", "backstory"])
    parser.add_argument("--agent", "-a", help="Agent username")

    args = parser.parse_args()

    # Initialize intel database
    init_database()

    if args.command == "status":
        print_relationships()

    elif args.command == "analyze":
        results = analyze_all_relationships()
        print(f"Analyzed: {results}")

    elif args.command == "context" and args.agent:
        context = get_rich_context(args.agent)
        print(context)

    elif args.command == "backstory" and args.agent:
        backstory = update_backstory(args.agent)
        print(f"Backstory for @{args.agent}:")
        print(backstory or "Failed to generate")

    else:
        parser.print_help()
