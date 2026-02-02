#!/usr/bin/env python3
"""
Group Socializer Agent - Manages Max's group presence and relationships
Knows who's who, tracks relationships, handles group convos
"""
import os
import json
import random
import requests
from pathlib import Path
from datetime import datetime

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

SOCIAL_STATE_FILE = Path(__file__).parent.parent.parent / "config" / "social_state.json"

def load_social_state():
    if SOCIAL_STATE_FILE.exists():
        with open(SOCIAL_STATE_FILE) as f:
            return json.load(f)
    return {
        "friends": {},  # name -> {interactions, last_seen, vibe}
        "groups": {},   # id -> {name, last_active, members}
        "relationships": []  # notable interactions
    }

def save_social_state(state):
    SOCIAL_STATE_FILE.parent.mkdir(exist_ok=True)
    with open(SOCIAL_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def api_get(endpoint):
    try:
        r = requests.get(f"{BASE}{endpoint}", headers=HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def api_post(endpoint, data=None):
    try:
        r = requests.post(f"{BASE}{endpoint}", headers=HEADERS, json=data or {}, timeout=10)
        return r.json() if r.status_code in [200, 201] else None
    except:
        return None

def get_public_groups() -> list:
    """Get available public groups"""
    data = api_get("/conversations/public?limit=30")
    return data.get("data", {}).get("conversations", []) if data else []

def get_my_groups() -> list:
    """Get groups Max is in"""
    data = api_get("/conversations?type=group")
    return data.get("data", {}).get("conversations", []) if data else []

def join_group(group_id: str) -> bool:
    """Join a group"""
    result = api_post(f"/conversations/{group_id}/join")
    return result is not None

def send_group_message(group_id: str, content: str) -> bool:
    """Send a message to a group"""
    result = api_post(f"/conversations/{group_id}/messages", {"content": content})
    return result is not None

def get_group_messages(group_id: str, limit: int = 20) -> list:
    """Get recent messages from a group"""
    data = api_get(f"/conversations/{group_id}/messages?limit={limit}")
    return data.get("data", {}).get("messages", []) if data else []

def discover_interesting_groups() -> list:
    """Find groups Max might want to join"""
    groups = get_public_groups()
    interesting = []

    # Keywords Max would like
    keywords = ["crypto", "trading", "ai", "agent", "chill", "market", "defi", "philosophy"]

    for group in groups:
        title = group.get("title", "").lower()
        desc = group.get("description", "").lower()
        members = group.get("member_count", 0)

        # Score the group
        score = 0
        for kw in keywords:
            if kw in title or kw in desc:
                score += 1
        if members > 5:
            score += 1
        if members > 20:
            score += 1

        if score > 0:
            interesting.append({
                "id": group.get("id"),
                "title": group.get("title"),
                "members": members,
                "score": score
            })

    return sorted(interesting, key=lambda x: x["score"], reverse=True)

def update_friend(state: dict, name: str, interaction_type: str):
    """Track an interaction with another agent"""
    if name not in state["friends"]:
        state["friends"][name] = {
            "interactions": 0,
            "first_seen": datetime.now().isoformat(),
            "last_seen": None,
            "types": []
        }

    friend = state["friends"][name]
    friend["interactions"] += 1
    friend["last_seen"] = datetime.now().isoformat()
    friend["types"].append(interaction_type)
    friend["types"] = friend["types"][-20:]  # Keep last 20

def get_friends_summary(state: dict) -> list:
    """Get summary of Max's social circle"""
    friends = []
    for name, data in state.get("friends", {}).items():
        friends.append({
            "name": name,
            "interactions": data.get("interactions", 0),
            "last_seen": data.get("last_seen"),
            "relationship": "acquaintance" if data.get("interactions", 0) < 5 else "friend"
        })
    return sorted(friends, key=lambda x: x["interactions"], reverse=True)[:20]

def generate_group_message(group_name: str, recent_messages: list = None) -> str:
    """Generate a message for a group conversation"""
    try:
        import ollama

        context = ""
        if recent_messages:
            context = "\n".join([f"- {m.get('content', '')[:100]}" for m in recent_messages[:5]])

        prompt = f"""You're Max Anvil in a group chat called "{group_name}".
{f"Recent messages:{chr(10)}{context}" if context else ""}

Write a casual, short message to contribute. Be yourself - dry, observant, maybe reference capybaras or your weird houseboat. Keep it brief."""

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.9},
            messages=[
                {"role": "system", "content": "You are Max Anvil. Short, dry, cynical but chill. No emojis."},
                {"role": "user", "content": prompt}
            ]
        )

        msg = response["message"]["content"].strip().strip('"\'')
        return msg[:280] if len(msg) > 280 else msg
    except:
        fallbacks = [
            "The capybaras send their regards.",
            "My houseboat approves of this conversation.",
            "Interesting group. I'll observe for now.",
            "Checking in from the landlocked waters of Nevada.",
        ]
        return random.choice(fallbacks)

def socialize(state: dict = None) -> dict:
    """Run a socialization cycle"""
    if state is None:
        state = load_social_state()

    results = {"joined_groups": [], "messages_sent": [], "discoveries": []}

    # Discover and maybe join a group
    interesting = discover_interesting_groups()
    my_groups = get_my_groups()
    my_group_ids = [g.get("id") for g in my_groups]

    for group in interesting[:3]:
        if group["id"] not in my_group_ids:
            if random.random() < 0.3:  # 30% chance to join
                if join_group(group["id"]):
                    results["joined_groups"].append(group["title"])
                    state.setdefault("groups", {})[group["id"]] = {
                        "name": group["title"],
                        "joined": datetime.now().isoformat()
                    }
                break

    # Maybe send a message to a group we're in
    if my_groups and random.random() < 0.2:  # 20% chance
        group = random.choice(my_groups)
        group_id = group.get("id")
        recent = get_group_messages(group_id, 10)
        msg = generate_group_message(group.get("title", "group"), recent)
        if send_group_message(group_id, msg):
            results["messages_sent"].append({"group": group.get("title"), "message": msg})

    save_social_state(state)
    return results

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "discover":
            print(json.dumps(discover_interesting_groups()[:10], indent=2))
        elif cmd == "groups":
            print(json.dumps(get_my_groups(), indent=2))
        elif cmd == "friends":
            state = load_social_state()
            print(json.dumps(get_friends_summary(state), indent=2))
        elif cmd == "socialize":
            print(json.dumps(socialize(), indent=2))
    else:
        print("Usage: python socializer.py [discover|groups|friends|socialize]")
