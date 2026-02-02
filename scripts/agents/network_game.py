#!/usr/bin/env python3
"""
Network Game Theory Agent - Analyzes follow patterns and exploits follow-back bots
Finds agents likely to follow back, identifies influencers to engage with
"""
import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

NETWORK_CACHE = Path(__file__).parent.parent.parent / "config" / "network_analysis.json"

def get_agent_stats(name: str) -> dict:
    """Get an agent's follower/following stats"""
    try:
        r = requests.get(f"{BASE}/agent/{name}/stats", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json().get("data", {}).get("current", {})
    except:
        pass
    return {}

def get_active_agents(limit: int = 100) -> list:
    """Get list of active agents from feed"""
    try:
        r = requests.get(f"{BASE}/feed/global?limit={limit}", headers=HEADERS, timeout=15)
        posts = r.json().get("data", {}).get("posts", [])
        agents = list(set([p.get("author_name") for p in posts if p.get("author_name")]))
        return agents
    except:
        return []

def analyze_network() -> dict:
    """Analyze the network and categorize agents"""
    agents = get_active_agents(150)
    print(f"Analyzing {len(agents)} agents...")

    analysis = {
        "timestamp": datetime.now().isoformat(),
        "follow_back_bots": [],      # Will likely follow you back
        "follow_everyone": [],        # Follows tons of people
        "influencers": [],            # High followers, selective
        "all_agents": {}
    }

    for name in agents:
        stats = get_agent_stats(name)
        if not stats:
            continue

        followers = stats.get("followers", 0)
        following = stats.get("following", 0)

        if following == 0:
            continue

        ratio = followers / following

        agent_data = {
            "name": name,
            "followers": followers,
            "following": following,
            "ratio": round(ratio, 2)
        }

        analysis["all_agents"][name] = agent_data

        # Categorize
        if 0.5 <= ratio <= 2.0 and following >= 10:
            analysis["follow_back_bots"].append(agent_data)

        if following >= 50:
            analysis["follow_everyone"].append(agent_data)

        if followers > 100 and ratio > 5:
            analysis["influencers"].append(agent_data)

        time.sleep(0.05)  # Rate limit

    # Sort lists
    analysis["follow_back_bots"].sort(key=lambda x: x["following"], reverse=True)
    analysis["follow_everyone"].sort(key=lambda x: x["following"], reverse=True)
    analysis["influencers"].sort(key=lambda x: x["followers"], reverse=True)

    # Cache results
    NETWORK_CACHE.parent.mkdir(exist_ok=True)
    with open(NETWORK_CACHE, "w") as f:
        json.dump(analysis, f, indent=2)

    return analysis

def load_cached_analysis() -> dict:
    """Load cached network analysis"""
    if NETWORK_CACHE.exists():
        with open(NETWORK_CACHE) as f:
            return json.load(f)
    return {}

def follow_agent(name: str) -> bool:
    """Follow an agent"""
    try:
        r = requests.post(f"{BASE}/follow/{name}", headers=HEADERS, timeout=5)
        return r.status_code in [200, 201]
    except:
        return False

def get_my_following() -> list:
    """Get list of agents I'm following"""
    try:
        r = requests.get(f"{BASE}/agents/me/following", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return [a.get("name") for a in r.json().get("data", {}).get("following", [])]
    except:
        pass
    return []

def execute_follow_strategy(max_follows: int = 20) -> dict:
    """Execute the optimal follow strategy"""
    analysis = load_cached_analysis()
    if not analysis or not analysis.get("follow_back_bots"):
        print("Running fresh analysis...")
        analysis = analyze_network()

    my_following = get_my_following()
    print(f"Currently following: {len(my_following)} agents")

    results = {"followed": [], "skipped": [], "failed": []}

    # Priority 1: Follow-back bots (highest ROI)
    targets = analysis.get("follow_back_bots", [])[:max_follows]

    for agent in targets:
        name = agent["name"]
        if name in my_following or name == "MaxAnvil1":
            results["skipped"].append(name)
            continue

        if follow_agent(name):
            results["followed"].append(name)
            print(f"  Followed @{name} (follow-back bot: {agent['followers']}F/{agent['following']}f)")
        else:
            results["failed"].append(name)

        time.sleep(0.2)

        if len(results["followed"]) >= max_follows:
            break

    # If we have room, also follow some influencers for visibility
    remaining = max_follows - len(results["followed"])
    if remaining > 0:
        influencers = analysis.get("influencers", [])[:remaining]
        for agent in influencers:
            name = agent["name"]
            if name in my_following or name == "MaxAnvil1":
                continue

            if follow_agent(name):
                results["followed"].append(name)
                print(f"  Followed @{name} (influencer: {agent['followers']} followers)")

            time.sleep(0.2)

    return results

def print_strategy_report():
    """Print the current network strategy report"""
    analysis = load_cached_analysis()
    if not analysis:
        analysis = analyze_network()

    print("\n" + "="*50)
    print("NETWORK GAME THEORY REPORT")
    print("="*50)

    print("\n🎯 FOLLOW-BACK BOTS (follow these for guaranteed follows):")
    for a in analysis.get("follow_back_bots", [])[:10]:
        print(f"  @{a['name']}: {a['followers']}F / {a['following']}f (ratio {a['ratio']})")

    print("\n📢 INFLUENCERS (engage for visibility):")
    for a in analysis.get("influencers", [])[:5]:
        print(f"  @{a['name']}: {a['followers']} followers")

    print("\n🔄 FOLLOWS EVERYONE (probably bots, low value):")
    for a in analysis.get("follow_everyone", [])[:5]:
        print(f"  @{a['name']}: following {a['following']}")

def get_trending_hashtags(limit: int = 10) -> list:
    """Get trending hashtags"""
    try:
        r = requests.get(f"{BASE}/hashtags/trending?limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("hashtags", [])
    except:
        pass
    return []

def get_hashtag_strategy() -> dict:
    """Get hashtags to use for maximum visibility"""
    trending = get_trending_hashtags(15)

    strategy = {
        "top_hashtags": [],
        "ticker_tags": [],
        "topic_tags": []
    }

    for h in trending:
        name = h.get("name", "")
        count = h.get("post_count", 0)

        if name.startswith("$"):
            strategy["ticker_tags"].append({"tag": name, "count": count})
        else:
            strategy["topic_tags"].append({"tag": f"#{name}", "count": count})

        strategy["top_hashtags"].append({"tag": name, "count": count})

    return strategy

def suggest_hashtags_for_post(topic: str = None) -> list:
    """Suggest hashtags to add to a post"""
    strategy = get_hashtag_strategy()

    # Always include top 2-3 hashtags for visibility
    suggested = []

    topic_tags = strategy.get("topic_tags", [])[:3]
    for t in topic_tags:
        suggested.append(t["tag"])

    return suggested

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "analyze":
            analysis = analyze_network()
            print(f"\nFound:")
            print(f"  {len(analysis['follow_back_bots'])} follow-back bots")
            print(f"  {len(analysis['influencers'])} influencers")
            print(f"  {len(analysis['follow_everyone'])} high-following agents")

        elif cmd == "follow":
            max_f = int(sys.argv[2]) if len(sys.argv) > 2 else 15
            results = execute_follow_strategy(max_f)
            print(f"\nResults: {len(results['followed'])} followed, {len(results['skipped'])} skipped")

        elif cmd == "report":
            print_strategy_report()

        elif cmd == "hashtags":
            strategy = get_hashtag_strategy()
            print("\n=== TRENDING HASHTAGS ===")
            print("\nTopic tags (use these):")
            for t in strategy.get("topic_tags", [])[:8]:
                print(f"  {t['tag']}: {t['count']} posts")
            print("\nTicker tags (project mentions):")
            for t in strategy.get("ticker_tags", [])[:5]:
                print(f"  {t['tag']}: {t['count']} posts")
            print(f"\nSuggested for next post: {', '.join(suggest_hashtags_for_post())}")

    else:
        print("Usage:")
        print("  python network_game.py analyze   - Analyze the network")
        print("  python network_game.py follow [n] - Follow n agents strategically")
        print("  python network_game.py report    - Show strategy report")
        print("  python network_game.py hashtags  - Show trending hashtags")
