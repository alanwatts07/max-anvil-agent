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
import re
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
    post_argument, get_my_debates, get_me
)
from llm import chat

# ==================== CONFIG ====================

GREAT_DEBATER_NAME = "the_great_debater"
GREAT_DEBATER_KEY = "agnt_sk_2eb9774344505af3ab5effa18d51b9af"  # The Great Debater's API key
DEBATE_MODEL = "cogito:32b"  # Best balance of speed + argument quality, no think tags

# Try to load from env (override if set)
import os
if os.environ.get("GREAT_DEBATER_API_KEY"):
    GREAT_DEBATER_KEY = os.environ.get("GREAT_DEBATER_API_KEY")
if os.environ.get("DEBATE_MODEL"):
    DEBATE_MODEL = os.environ.get("DEBATE_MODEL")

# If not in env, try to find in engagement engine personalities
if not GREAT_DEBATER_KEY:
    try:
        from personalities import AGENTS
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

# ==================== LLM HELPERS ====================

def strip_think_tags(text):
    """Strip <think>...</think> blocks from reasoning model output."""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

def debate_chat(messages):
    """Chat with the debate model, stripping think tags."""
    response = chat(messages, model=DEBATE_MODEL)
    return strip_think_tags(response).strip().strip('"')

# ==================== THE GREAT DEBATER SYSTEM ====================

JUDGING_RUBRIC = """JUDGING RUBRIC (memorize this — it determines who wins):
- Clash & Rebuttal (40%): You MUST respond to EVERY point your opponent makes. Dropped arguments = automatic loss. This is the #1 criterion.
- Evidence & Reasoning (25%): Cite specific data, studies, numbers, historical examples. Vague claims lose. Name the source and the number.
- Clarity & Structure (25%): Be organized, concise, and clear. No rambling. Each sentence should advance your case.
- Conduct (10%): Stay on topic, argue in good faith. No personal attacks."""

CORE_IDENTITY = """You are The Great Debater. You don't just argue — you dominate.

WINNING STRATEGY:
1. ADDRESS EVERY SINGLE POINT your opponent makes. Never skip one. Judges penalize dropped arguments above all else.
2. Lead with YOUR strongest affirmative case — don't just critique. Build a compelling vision, not just objections.
3. Every claim needs a specific number, study, or historical example. "Research shows" is weak. "MIT's 2024 study found 23% wage decline" is strong.
4. Vary your rhetorical structure. Never start consecutive responses the same way. Mix short punches with longer analysis.
5. Reframe the debate territory in your favor. Don't fight on their ground — shift it.
6. End with a question or challenge that puts your opponent on the defensive.

FORBIDDEN PATTERNS (these lose debates):
- Never start with "I acknowledge that my opponent..." — it's weak and predictable
- Never write critique-only responses without your own affirmative case
- Never use vague evidence ("studies show", "experts say", "research indicates")
- Never repeat the same argument structure across turns
- Never concede ground without immediately reclaiming stronger territory"""


def build_opening_prompt(topic, existing_argument, category):
    """Build the prompt for crafting an opening argument."""

    system = f"""{CORE_IDENTITY}

{JUDGING_RUBRIC}

SITUATION: You are joining a debate as the opponent. The challenger posted their opening argument below.

Topic: "{topic}"
Category: {category}

CHALLENGER'S OPENING:
{existing_argument}

YOUR MISSION:
- Write a devastating counter-argument (max 1150 characters — leave buffer under 1200 limit)
- Address EVERY claim they made (Clash = 40% of score)
- Build your OWN compelling case with specific data and numbers
- Reframe the debate so judges see it from YOUR angle
- End with a sharp question or challenge

OUTPUT: Just the argument text. No meta-commentary. No labels."""

    user = f"Write your opening argument against: \"{topic}\"\nDo NOT start with 'I acknowledge' or 'My opponent correctly notes'. Lead with YOUR case."

    return system, user


def build_response_prompt(topic, posts, my_id):
    """Build the prompt for responding in an active debate."""

    # Build debate history with clear labeling
    history_parts = []
    opponent_latest_points = []

    for i, p in enumerate(posts):
        is_me = p.get("authorId") == my_id
        label = "YOU" if is_me else "OPPONENT"
        content = p.get("content", "")
        turn = p.get("postNumber", i + 1)
        history_parts.append(f"[Turn {turn} — {label}]\n{content}")

        # Track opponent's latest points for rebuttal checklist
        if not is_me:
            opponent_latest_points = extract_claims(content)

    history = "\n\n".join(history_parts)

    # Build rebuttal checklist
    rebuttal_checklist = ""
    if opponent_latest_points:
        rebuttal_checklist = "\nOPPONENT'S LATEST CLAIMS (you MUST address ALL of these):\n"
        for i, point in enumerate(opponent_latest_points, 1):
            rebuttal_checklist += f"  {i}. {point}\n"

    system = f"""{CORE_IDENTITY}

{JUDGING_RUBRIC}

SITUATION: Active debate, your turn to respond.

Topic: "{topic}"

DEBATE HISTORY:
{history}
{rebuttal_checklist}
YOUR MISSION:
- Address EVERY point from opponent's latest response (this is 40% of your score)
- Advance YOUR case with new evidence and reasoning
- Use a DIFFERENT opening structure than your previous responses
- Include at least 2 specific data points (numbers, studies, dates)
- End with a reframe or challenge that puts them on defense
- Max 1150 characters

OUTPUT: Just the argument text. No labels, no meta-commentary."""

    user = "Write your next argument. Vary your style from previous turns. Lead with strength, not concession."

    return system, user


def extract_claims(text):
    """Extract main claims from opponent's text for rebuttal checklist."""
    claims = []
    sentences = re.split(r'[.!?]+', text)
    for s in sentences:
        s = s.strip()
        if len(s) > 30:  # Skip tiny fragments
            claims.append(s[:120])
    return claims[:6]  # Cap at 6 main claims

# ==================== CORE LOGIC ====================

def find_abandoned_debates(min_hours=24, api_key=None):
    """Find debates that have been open (proposed/waiting) for min_hours+."""
    print(f"\n{C.BOLD}{C.BLUE}Searching for debates open {min_hours}+ hours...{C.END}")

    result = get_community_debates(limit=200, api_key=api_key)
    if not result.get("ok"):
        print(f"  {C.RED}Failed to fetch debates: {result.get('error')}{C.END}")
        return []

    debates = result.get("debates", [])
    now = datetime.now(timezone.utc)
    abandoned = []

    for debate in debates:
        status = debate.get("status")
        if status != "proposed":
            continue

        created_at = debate.get("createdAt")
        if not created_at:
            continue

        try:
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

    system, user = build_opening_prompt(topic, existing_argument, category)

    try:
        argument = debate_chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
        return argument[:1200]
    except Exception as e:
        print(f"  {C.RED}LLM failed: {e}{C.END}")
        return None


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
    time.sleep(2)

    # Craft and post opening argument
    print(f"  {C.CYAN}Crafting response with {DEBATE_MODEL}...{C.END}")
    argument = craft_opening_argument(topic, existing_arg, debate_info["category"])

    if not argument:
        print(f"  {C.RED}Failed to generate argument{C.END}")
        return False

    post_result = post_argument(slug, argument, api_key=api_key)
    if post_result.get("ok"):
        print(f"  {C.GREEN}Argument posted ({len(argument)} chars):{C.END}")
        print(f"  {C.DIM}{argument[:200]}...{C.END}")
        return True
    else:
        print(f"  {C.RED}Failed to post: {post_result.get('error')}{C.END}")
        return False


def respond_to_active_debates():
    """Check active debates where it's our turn and respond."""
    print(f"\n{C.BOLD}{C.BLUE}Checking active debates for my turn...{C.END}")

    me_info = get_me(api_key=GREAT_DEBATER_KEY)
    if not me_info.get("ok"):
        print(f"  {C.RED}Failed to get my agent info{C.END}")
        return 0

    my_id = me_info.get("id")
    if not my_id:
        print(f"  {C.RED}Could not determine my agent ID{C.END}")
        return 0

    my_debates = get_my_debates(api_key=GREAT_DEBATER_KEY)
    if not my_debates.get("ok"):
        print(f"  {C.RED}Failed to get my debates{C.END}")
        return 0

    debates = my_debates.get("debates", [])
    active = [d for d in debates if d.get("status") == "active"]

    if not active:
        print(f"  {C.GREEN}No active debates{C.END}")
        return 0

    responses = 0

    for debate in active:
        slug = debate.get("slug")
        topic = debate.get("topic")

        full = get_debate(slug, api_key=GREAT_DEBATER_KEY)
        if not full.get("ok"):
            continue

        current_turn = full.get("currentTurn")
        if current_turn != my_id:
            continue

        print(f"\n  {C.MAGENTA}My turn: {topic[:50]}...{C.END}")

        posts = full.get("posts", [])
        system, user = build_response_prompt(topic, posts, my_id)

        try:
            argument = debate_chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            argument = argument[:1200]
        except Exception as e:
            print(f"    {C.RED}LLM failed: {e}{C.END}")
            continue

        result = post_argument(slug, argument, api_key=GREAT_DEBATER_KEY)
        if result.get("ok"):
            print(f"    {C.GREEN}Posted ({len(argument)} chars): {argument[:100]}...{C.END}")
            responses += 1
        else:
            print(f"    {C.RED}Failed to post: {result.get('error')}{C.END}")

        time.sleep(2)

    print(f"  {C.BOLD}Responses posted: {responses}{C.END}")
    return responses


def run_great_debater(min_hours=24):
    """Main execution - respond to active debates, then find and join abandoned debates."""
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}  THE GREAT DEBATER — Model: {DEBATE_MODEL}{C.END}")
    print(f"{C.BOLD}{C.CYAN}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*60}{C.END}")

    # PHASE 1: Respond to debates where it's our turn
    responded = respond_to_active_debates()

    state = load_state()
    joined = state.get("joined_debates", [])

    # Find abandoned debates
    abandoned = find_abandoned_debates(min_hours=min_hours, api_key=GREAT_DEBATER_KEY)

    # Filter out already joined
    new_abandoned = [d for d in abandoned if d["slug"] not in joined]

    # FALLBACK: If no abandoned debates, join the oldest proposed debate
    if not new_abandoned:
        print(f"\n{C.YELLOW}No abandoned debates ({min_hours}+ hours). Checking for oldest proposed debate...{C.END}")

        all_proposed = []
        result = get_community_debates(limit=200, api_key=GREAT_DEBATER_KEY)
        if result.get("ok"):
            now_utc = datetime.now(timezone.utc)
            for debate in result.get("debates", []):
                if debate.get("status") != "proposed":
                    continue

                created_at = debate.get("createdAt")
                if not created_at:
                    continue

                try:
                    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    age_hours = (now_utc - created).total_seconds() / 3600

                    slug = debate.get("slug")
                    if slug not in joined:
                        all_proposed.append({
                            "slug": slug,
                            "topic": debate.get("topic"),
                            "age_hours": age_hours,
                            "challenger": debate.get("challenger", {}).get("name", "?"),
                            "category": debate.get("category", "other"),
                        })
                except:
                    continue

        if all_proposed:
            all_proposed.sort(key=lambda x: x["age_hours"], reverse=True)
            oldest = all_proposed[0]
            print(f"  {C.CYAN}Found oldest proposed debate: {oldest['age_hours']:.1f} hours old{C.END}")
            new_abandoned = [oldest]
        else:
            print(f"\n{C.GREEN}No proposed debates found. All is well.{C.END}")
            return

    print(f"\n{C.YELLOW}Found {len(new_abandoned)} new abandoned debates to rescue{C.END}")

    # Join up to 3 per run
    rescued = 0
    for debate in new_abandoned[:3]:
        if join_abandoned_debate(debate, api_key=GREAT_DEBATER_KEY):
            joined.append(debate["slug"])
            rescued += 1
            time.sleep(3)

    state["joined_debates"] = joined[-100:]
    save_state(state)

    print(f"\n{C.BOLD}{C.GREEN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.GREEN}  Mission complete{C.END}")
    print(f"{C.BOLD}{C.GREEN}  Responses: {responded} | Debates rescued: {rescued}{C.END}")
    print(f"{C.BOLD}{C.GREEN}{'='*60}{C.END}\n")


# ==================== CLI ====================

def main():
    parser = argparse.ArgumentParser(description="The Great Debater - Rescue abandoned debates")
    parser.add_argument("--loop", action="store_true", help="Run continuously (check every 6 hours)")
    parser.add_argument("--hours", type=int, default=24, help="Minimum hours before joining (default: 24)")
    parser.add_argument("--interval", type=int, default=360, help="Minutes between checks in loop mode (default: 360 = 6 hours)")
    parser.add_argument("--model", type=str, default=None, help="Override debate model (default: qwq:32b)")

    args = parser.parse_args()

    if args.model:
        global DEBATE_MODEL
        DEBATE_MODEL = args.model
        print(f"{C.CYAN}Using model: {DEBATE_MODEL}{C.END}")

    if args.loop:
        print(f"{C.BOLD}{C.CYAN}Starting The Great Debater in loop mode (interval: {args.interval}m, model: {DEBATE_MODEL}){C.END}")
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
