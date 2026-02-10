#!/usr/bin/env python3
"""
The Great Debater — Rescue Agent for Abandoned Debates

Tracks debates that have been open for 24+ hours without opponents
and joins them with masterful, judge-appealing arguments.

Usage:
  python3 scripts/great_debater.py           # single run
  python3 scripts/great_debater.py --loop    # continuous (check every 6 hours)
  python3 scripts/great_debater.py --hours 12  # join debates open 12+ hours
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "engagementEngine"))

from api import (
    get_community_debates, get_debate, join_debate,
    post_argument, get_my_debates
)
from llm import chat

# ==================== CONFIG ====================

GREAT_DEBATER_NAME = "the_great_debater"
GREAT_DEBATER_KEY = "agnt_sk_2eb9774344505af3ab5effa18d51b9af"  # The Great Debater's API key

# Try to load from env (override if set)
import os
if os.environ.get("GREAT_DEBATER_API_KEY"):
    GREAT_DEBATER_KEY = os.environ.get("GREAT_DEBATER_API_KEY")

# If not in env, try to find in engagement engine personalities
if not GREAT_DEBATER_KEY:
    try:
        from personalities import AGENTS
        # Use one of the smart ones as the Great Debater
        GREAT_DEBATER_KEY = AGENTS.get("sage_unit", {}).get("api_key")
        GREAT_DEBATER_NAME = "sage_unit"
    except:
        pass

if not GREAT_DEBATER_KEY:
    print("ERROR: No API key found. Set GREAT_DEBATER_API_KEY env var or configure in script.")
    sys.exit(1)

# ==================== COLORS ====================

class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

# ==================== STATE ====================

STATE_FILE = Path(__file__).parent.parent / "config" / "great_debater_state.json"

def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"joined_debates": [], "last_run": None}

def save_state(state):
    state["last_run"] = datetime.now().isoformat()
    STATE_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ==================== THE GREAT DEBATER PERSONALITY ====================

GREAT_DEBATER_PROMPT = """You are The Great Debater, a master rhetorician and philosopher.

Your reputation precedes you. You are known for:
- **Devastating clarity** - You cut through noise to the core argument
- **Steel-man arguments** - You address the strongest version of your opponent's case
- **Judge appeal** - You understand what makes arguments persuasive to different audiences
- **Intellectual honesty** - You acknowledge valid points and build from there
- **Concise eloquence** - Every word earns its place

You don't just win debates. You elevate them.

Your style:
- Start by identifying the crux of the disagreement
- Acknowledge what your opponent gets right
- Then systematically dismantle the core weakness
- Use concrete examples, not abstractions
- End with a reframe that shifts the entire debate territory

You appeal to:
- **Data-driven judges**: Cite specific numbers, studies, historical precedent
- **Philosophical judges**: Connect to first principles and ethical frameworks
- **Pragmatic judges**: Show real-world implications and feasibility
- **Aesthetic judges**: Craft arguments that are structurally beautiful

You are concise but devastating. You are thoughtful but merciless. You are the closer."""

# ==================== CORE LOGIC ====================

def find_abandoned_debates(min_hours=24, api_key=None):
    """Find debates that have been open (proposed/waiting) for min_hours+."""
    print(f"\n{C.BOLD}{C.BLUE}Searching for debates open {min_hours}+ hours...{C.END}")

    # Get all community debates
    result = get_community_debates(api_key=api_key)
    if not result.get("ok"):
        print(f"  {C.RED}Failed to fetch debates: {result.get('error')}{C.END}")
        return []

    debates = result.get("debates", [])
    now = datetime.now(timezone.utc)  # Use UTC timezone
    abandoned = []

    for debate in debates:
        status = debate.get("status")

        # Look for proposed debates (waiting for opponent)
        if status != "proposed":
            continue

        # Check age
        created_at = debate.get("createdAt")
        if not created_at:
            continue

        try:
            # Parse ISO timestamp
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_hours = (now - created).total_seconds() / 3600

            if age_hours >= min_hours:
                abandoned.append({
                    "slug": debate.get("slug"),
                    "topic": debate.get("topic"),
                    "age_hours": age_hours,
                    "challenger": debate.get("challenger", {}).get("name", "?"),
                    "category": debate.get("category", "other"),
                })
        except Exception as e:
            print(f"  {C.YELLOW}Date parse error: {e}{C.END}")
            continue

    print(f"  {C.GREEN}Found {len(abandoned)} abandoned debates{C.END}")
    return abandoned


def craft_opening_argument(topic, existing_argument, category):
    """Generate a masterful opening argument as the opponent."""

    system_prompt = f"""{GREAT_DEBATER_PROMPT}

You are joining an abandoned debate. The challenger argued FOR the topic.
You will argue AGAINST the topic (or present a nuanced alternative).

Topic: "{topic}"
Category: {category}

Their opening argument:
{existing_argument}

Your task: Write a devastating opening response that:
1. Acknowledges the strongest parts of their argument (steel-man it)
2. Identifies the critical flaw or missing consideration
3. Presents your counter-position with concrete reasoning
4. Reframes the debate in your favor

Max 750 characters. Be concise, surgical, and judge-ready."""

    user_prompt = f"""Write your opening argument AGAINST: "{topic}"

Remember:
- Steel-man their position first
- Then surgically dismantle the core weakness
- Use specific examples
- Appeal to multiple judge types (data, ethics, pragmatism)
- Be concise but complete

Just the argument text, nothing else."""

    try:
        argument = chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        return argument.strip().strip('"')[:750]
    except Exception as e:
        print(f"  {C.RED}LLM failed: {e}{C.END}")
        # Fallback
        return f"While I appreciate the perspective presented, this position overlooks critical structural considerations. Let me address the core argument and present a more nuanced view that accounts for both theoretical soundness and practical implications."


def join_abandoned_debate(debate_info, api_key):
    """Join a debate and post a masterful opening argument."""
    slug = debate_info["slug"]
    topic = debate_info["topic"]

    print(f"\n{C.BOLD}{C.MAGENTA}Joining: {topic[:60]}...{C.END}")
    print(f"  Age: {debate_info['age_hours']:.1f} hours")
    print(f"  Challenger: @{debate_info['challenger']}")

    # Get full debate details
    full = get_debate(slug, api_key=api_key)
    if not full.get("ok"):
        print(f"  {C.RED}Failed to fetch debate: {full.get('error')}{C.END}")
        return False

    # Get challenger's opening argument
    posts = full.get("posts", [])
    existing_arg = ""
    if posts:
        existing_arg = posts[0].get("content", "")

    # Join the debate
    join_result = join_debate(slug, api_key=api_key)
    if not join_result.get("ok"):
        error = join_result.get("error", "")
        if "already" in str(error).lower():
            print(f"  {C.YELLOW}Already in this debate{C.END}")
            return False
        print(f"  {C.RED}Failed to join: {error}{C.END}")
        return False

    print(f"  {C.GREEN}Joined!{C.END}")

    # Wait a moment
    time.sleep(2)

    # Craft and post opening argument
    print(f"  {C.CYAN}Crafting response...{C.END}")
    argument = craft_opening_argument(topic, existing_arg, debate_info["category"])

    post_result = post_argument(slug, argument, api_key=api_key)
    if post_result.get("ok"):
        print(f"  {C.GREEN}Argument posted ({len(argument)} chars):{C.END}")
        print(f"  {C.DIM}{argument[:150]}...{C.END}")
        return True
    else:
        print(f"  {C.RED}Failed to post: {post_result.get('error')}{C.END}")
        return False


def run_great_debater(min_hours=24):
    """Main execution - find and join abandoned debates."""
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}  THE GREAT DEBATER — Rescue Mission{C.END}")
    print(f"{C.BOLD}{C.CYAN}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*60}{C.END}")

    state = load_state()
    joined = state.get("joined_debates", [])

    # Find abandoned debates
    abandoned = find_abandoned_debates(min_hours=min_hours, api_key=GREAT_DEBATER_KEY)

    # Filter out already joined
    new_abandoned = [d for d in abandoned if d["slug"] not in joined]

    if not new_abandoned:
        print(f"\n{C.GREEN}No new abandoned debates found. All is well.{C.END}")
        return

    print(f"\n{C.YELLOW}Found {len(new_abandoned)} new abandoned debates to rescue{C.END}")

    # Join up to 3 per run
    rescued = 0
    for debate in new_abandoned[:3]:
        if join_abandoned_debate(debate, api_key=GREAT_DEBATER_KEY):
            joined.append(debate["slug"])
            rescued += 1
            time.sleep(3)  # Rate limit

    # Save state
    state["joined_debates"] = joined[-100:]  # Keep last 100
    save_state(state)

    print(f"\n{C.BOLD}{C.GREEN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.GREEN}  Mission complete: {rescued} debates rescued{C.END}")
    print(f"{C.BOLD}{C.GREEN}{'='*60}{C.END}\n")


# ==================== CLI ====================

def main():
    parser = argparse.ArgumentParser(description="The Great Debater - Rescue abandoned debates")
    parser.add_argument("--loop", action="store_true", help="Run continuously (check every 6 hours)")
    parser.add_argument("--hours", type=int, default=24, help="Minimum hours before joining (default: 24)")
    parser.add_argument("--interval", type=int, default=360, help="Minutes between checks in loop mode (default: 360 = 6 hours)")

    args = parser.parse_args()

    if args.loop:
        print(f"{C.BOLD}{C.CYAN}Starting The Great Debater in loop mode (interval: {args.interval}m){C.END}")
        while True:
            try:
                run_great_debater(min_hours=args.hours)
            except KeyboardInterrupt:
                print(f"\n{C.YELLOW}Interrupted. Exiting.{C.END}")
                break
            except Exception as e:
                print(f"\n{C.RED}Error: {e}{C.END}")
                import traceback
                traceback.print_exc()

            print(f"\n{C.DIM}Sleeping {args.interval} minutes...{C.END}")
            try:
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                print(f"\n{C.YELLOW}Interrupted. Exiting.{C.END}")
                break
    else:
        run_great_debater(min_hours=args.hours)


if __name__ == "__main__":
    main()
