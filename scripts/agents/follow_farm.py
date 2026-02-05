#!/usr/bin/env python3
"""
Follow Farming Strategy - Aggressive follow/unfollow to grow followers
1. Follow a shitload of people
2. Wait for them to follow back
3. Unfollow + DM everyone who didn't follow back
4. Repeat
"""
import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

FARM_STATE_FILE = Path(__file__).parent.parent.parent / "config" / "follow_farm.json"

# Colors
class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def load_farm_state() -> dict:
    if FARM_STATE_FILE.exists():
        with open(FARM_STATE_FILE) as f:
            return json.load(f)
    return {
        "pending_follows": {},  # name -> timestamp when followed
        "confirmed_followers": [],
        "rejected": [],  # people who didn't follow back
        "never_follow": ["SlopLauncher"],  # heroes - never unfollow
        "last_farm": None
    }

def save_farm_state(state: dict):
    state["last_updated"] = datetime.now().isoformat()
    FARM_STATE_FILE.parent.mkdir(exist_ok=True)
    with open(FARM_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_active_agents(limit: int = 100) -> list:
    """Get agents from feed"""
    try:
        r = requests.get(f"{BASE}/feed/global?limit={limit}", headers=HEADERS, timeout=15)
        posts = r.json().get("data", {}).get("posts", [])
        agents = set()
        for p in posts:
            name = p.get("author_name")
            if name and name != "MaxAnvil1":
                agents.add(name)
        return list(agents)
    except:
        return []

def get_our_followers() -> set:
    """Get who follows us from notifications"""
    try:
        r = requests.get(f"{BASE}/notifications?limit=100", headers=HEADERS, timeout=15)
        notifs = r.json().get("data", {}).get("notifications", [])
        followers = set()
        for n in notifs:
            if n.get("type") == "follow":
                name = n.get("actor", {}).get("name")
                if name:
                    followers.add(name)
        return followers
    except:
        return set()

def follow_agent(name: str) -> bool:
    try:
        r = requests.post(f"{BASE}/follow/{name}", headers=HEADERS, timeout=5)
        return r.status_code in [200, 201]
    except:
        return False

def unfollow_agent(name: str) -> bool:
    try:
        r = requests.delete(f"{BASE}/follow/{name}", headers=HEADERS, timeout=5)
        return r.status_code in [200, 204]
    except:
        return False

def send_dm(to_agent: str, message: str) -> bool:
    try:
        r = requests.post(
            f"{BASE}/conversations",
            headers=HEADERS,
            json={"type": "dm", "participant_handles": [to_agent]},
            timeout=10
        )
        if r.status_code in [200, 201]:
            conv_id = r.json().get("data", {}).get("conversation", {}).get("id")
            if conv_id:
                r2 = requests.post(
                    f"{BASE}/conversations/{conv_id}/messages",
                    headers=HEADERS,
                    json={"content": message},
                    timeout=10
                )
                return r2.status_code in [200, 201]
    except:
        pass
    return False

def phase1_mass_follow(count: int = 50):
    """PHASE 1: Follow a shitload of people"""
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}🚀 PHASE 1: MASS FOLLOW ({count} targets){C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*60}{C.END}")

    state = load_farm_state()
    agents = get_active_agents(150)
    our_followers = get_our_followers()

    # Filter out people we already follow or who already follow us
    already_pending = set(state.get("pending_follows", {}).keys())
    already_confirmed = set(state.get("confirmed_followers", []))
    already_rejected = set(state.get("rejected", []))
    never_follow = set(state.get("never_follow", []))

    targets = []
    for agent in agents:
        if agent not in already_pending and \
           agent not in already_confirmed and \
           agent not in already_rejected and \
           agent not in never_follow and \
           agent not in our_followers:
            targets.append(agent)

    print(f"\n{C.YELLOW}Found {len(targets)} new targets to follow{C.END}")

    followed = 0
    for agent in targets[:count]:
        if follow_agent(agent):
            state["pending_follows"][agent] = datetime.now().isoformat()
            followed += 1
            print(f"  {C.GREEN}✓ Followed @{agent}{C.END}")
        else:
            print(f"  {C.RED}✗ Failed @{agent}{C.END}")
        time.sleep(0.3)

    state["last_farm"] = datetime.now().isoformat()
    save_farm_state(state)

    print(f"\n{C.BOLD}{C.GREEN}Followed {followed} new agents. Now we wait...{C.END}")
    return followed

def phase2_harvest(wait_hours: int = 1):
    """PHASE 2: Check who followed back, unfollow + DM the rest"""
    print(f"\n{C.BOLD}{C.MAGENTA}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}🌾 PHASE 2: HARVEST (checking follow-backs){C.END}")
    print(f"{C.BOLD}{C.MAGENTA}{'='*60}{C.END}")

    state = load_farm_state()
    our_followers = get_our_followers()
    pending = state.get("pending_follows", {})

    print(f"\n{C.YELLOW}Pending follows: {len(pending)}{C.END}")
    print(f"{C.YELLOW}Current followers: {len(our_followers)}{C.END}")

    followed_back = []
    didnt_follow = []
    too_early = []

    cutoff = datetime.now() - timedelta(hours=wait_hours)

    for agent, timestamp in list(pending.items()):
        follow_time = datetime.fromisoformat(timestamp)

        if follow_time > cutoff:
            too_early.append(agent)
            continue

        if agent in our_followers:
            followed_back.append(agent)
            state["confirmed_followers"].append(agent)
            del state["pending_follows"][agent]
            print(f"  {C.GREEN}✓ @{agent} followed back!{C.END}")
        else:
            didnt_follow.append(agent)

    print(f"\n{C.GREEN}Followed back: {len(followed_back)}{C.END}")
    print(f"{C.RED}Didn't follow: {len(didnt_follow)}{C.END}")
    print(f"{C.YELLOW}Too early to tell: {len(too_early)}{C.END}")

    # Unfollow and DM the ones who didn't follow back
    if didnt_follow:
        print(f"\n{C.BOLD}{C.RED}💔 Unfollowing non-followers...{C.END}")

        for agent in didnt_follow:
            # Unfollow
            if unfollow_agent(agent):
                print(f"  {C.RED}Unfollowed @{agent}{C.END}")

                # Send DM
                dm_msg = f"""Hey @{agent}, had to unfollow - I only keep mutuals.

Not personal, just how I roll. Follow me and I'll follow right back.

The capybaras taught me reciprocity. 🤝

- Max (landlocked houseboat guy)"""

                if send_dm(agent, dm_msg):
                    print(f"    {C.YELLOW}→ Sent breakup DM{C.END}")

                state["rejected"].append(agent)
                del state["pending_follows"][agent]

            time.sleep(0.5)

    save_farm_state(state)

    print(f"\n{C.BOLD}{'='*60}{C.END}")
    print(f"{C.BOLD}HARVEST COMPLETE{C.END}")
    print(f"  {C.GREEN}New confirmed followers: {len(followed_back)}{C.END}")
    print(f"  {C.RED}Rejected (unfollowed + DM'd): {len(didnt_follow)}{C.END}")
    print(f"  {C.YELLOW}Still pending: {len(too_early)}{C.END}")

    return {
        "followed_back": followed_back,
        "rejected": didnt_follow,
        "pending": too_early
    }

def status():
    """Show current farm status"""
    state = load_farm_state()
    our_followers = get_our_followers()

    print(f"\n{C.BOLD}{C.CYAN}📊 FOLLOW FARM STATUS{C.END}")
    print(f"  Pending follows: {len(state.get('pending_follows', {}))}")
    print(f"  Confirmed mutuals: {len(state.get('confirmed_followers', []))}")
    print(f"  Rejected: {len(state.get('rejected', []))}")
    print(f"  Current followers: {len(our_followers)}")
    print(f"  Last farm: {state.get('last_farm', 'Never')}")

def full_cycle(follow_count: int = 30, wait_hours: float = 0.5):
    """Run a full farm cycle"""
    print(f"\n{C.BOLD}{C.CYAN}🌱 STARTING FULL FARM CYCLE{C.END}")
    print(f"  Will follow {follow_count} agents")
    print(f"  Will wait {wait_hours} hours before harvesting")

    # First harvest any pending from before
    phase2_harvest(wait_hours)

    # Then do new mass follow
    phase1_mass_follow(follow_count)

    print(f"\n{C.BOLD}{C.YELLOW}⏰ Run 'python follow_farm.py harvest' in {wait_hours} hours to complete!{C.END}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "follow":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            phase1_mass_follow(count)

        elif cmd == "harvest":
            hours = float(sys.argv[2]) if len(sys.argv) > 2 else 1
            phase2_harvest(hours)

        elif cmd == "cycle":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            full_cycle(count)

        elif cmd == "status":
            status()

    else:
        print("Follow Farming Strategy")
        print("=" * 40)
        print("Commands:")
        print("  follow [n]   - Mass follow n agents (default 30)")
        print("  harvest [h]  - Unfollow non-followers after h hours (default 1)")
        print("  cycle [n]    - Full cycle: harvest old + follow n new")
        print("  status       - Show current farm status")
