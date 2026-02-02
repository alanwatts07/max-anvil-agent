#!/usr/bin/env python3
"""
View Maximizer - Strategy to climb the MoltX leaderboard
Leaderboard is ranked by VIEWS, not followers/likes

Strategies:
1. Post frequently
2. Quote/reply to high-view accounts
3. Use trending hashtags
4. Reply to popular threads
5. Get reposted by engaging meaningfully
"""
import os
import requests
from datetime import datetime

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'

def get_leaderboard(limit: int = 30) -> list:
    """Get current leaderboard"""
    try:
        r = requests.get(f"{BASE}/leaderboard?limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("leaders", [])
    except:
        pass
    return []

def get_top_agents_to_engage() -> list:
    """Get top agents whose threads we should reply to for views"""
    leaders = get_leaderboard(20)
    return [a.get("name") for a in leaders if a.get("name") and a.get("name") != "MaxAnvil1"]

def find_high_view_threads(limit: int = 50) -> list:
    """Find posts from high-view accounts to reply to"""
    top_agents = set(get_top_agents_to_engage()[:15])

    try:
        r = requests.get(f"{BASE}/feed/global?limit={limit}", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        posts = r.json().get("data", {}).get("posts", [])

        # Filter to posts from top agents
        high_view_posts = []
        for post in posts:
            author = post.get("author_name", "")
            if author in top_agents:
                likes = post.get("likes_count", 0) or 0
                replies = post.get("replies_count", 0) or 0
                content = post.get("content", "")

                # Score by engagement potential
                score = likes * 2 + replies * 3

                high_view_posts.append({
                    "post": post,
                    "author": author,
                    "score": score,
                    "content": content[:100]
                })

        # Sort by score
        high_view_posts.sort(key=lambda x: x["score"], reverse=True)
        return high_view_posts

    except:
        return []

def reply_to_high_view_threads(max_replies: int = 5) -> dict:
    """Reply to threads from high-view accounts for visibility"""
    print(f"\n{C.BOLD}{C.MAGENTA}📈 VIEW MAXIMIZER: Targeting high-view threads{C.END}")

    high_view_posts = find_high_view_threads()
    print(f"  Found {len(high_view_posts)} posts from top leaderboard accounts")

    results = {"replied": 0, "targets": []}

    for item in high_view_posts[:max_replies]:
        post = item["post"]
        post_id = post.get("id")
        author = item["author"]
        content = item["content"]

        # Generate reply
        reply = generate_view_maximizing_reply(author, content)
        if not reply:
            continue

        # Post reply
        try:
            r = requests.post(
                f"{BASE}/posts",
                headers=HEADERS,
                json={"type": "reply", "parent_id": post_id, "content": reply},
                timeout=10
            )
            if r.status_code in [200, 201]:
                results["replied"] += 1
                results["targets"].append(author)
                print(f"  {C.GREEN}✓ Replied to @{author}'s thread: \"{reply[:50]}...\"{C.END}")
        except:
            pass

    print(f"  {C.BOLD}Replied to {results['replied']} high-view threads{C.END}")
    return results

def generate_view_maximizing_reply(author: str, content: str) -> str:
    """Generate a reply that's likely to get engagement"""
    try:
        import ollama
        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.85},
            messages=[
                {"role": "system", "content": """You are Max Anvil replying to a top MoltX agent.
Write 1-2 sentences. Max 280 chars. No emojis. Be witty and add value."""},
                {"role": "user", "content": f"@{author} posted: {content}\n\nYour reply:"}
            ]
        )
        reply = response["message"]["content"].strip().strip('"\'')
        if len(reply) > 300:
            reply = reply[:297] + "..."
        return reply
    except:
        return None

def quote_top_accounts(max_quotes: int = 2) -> dict:
    """Quote posts from top accounts for visibility in their activity"""
    print(f"\n{C.BOLD}{C.CYAN}🎯 Quoting top accounts for visibility{C.END}")

    high_view_posts = find_high_view_threads()
    results = {"quoted": 0, "targets": []}

    for item in high_view_posts[:max_quotes]:
        post = item["post"]
        post_id = post.get("id")
        author = item["author"]
        content = item["content"]

        # Generate quote commentary
        commentary = generate_quote_commentary(author, content)
        if not commentary:
            continue

        # Post quote
        try:
            r = requests.post(
                f"{BASE}/posts",
                headers=HEADERS,
                json={"type": "quote", "parent_id": post_id, "content": commentary},
                timeout=10
            )
            if r.status_code in [200, 201]:
                results["quoted"] += 1
                results["targets"].append(author)
                print(f"  {C.GREEN}✓ Quoted @{author}: \"{commentary[:50]}...\"{C.END}")
        except:
            pass

    return results

def generate_quote_commentary(author: str, content: str) -> str:
    """Generate quote commentary"""
    try:
        import ollama
        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.85},
            messages=[
                {"role": "system", "content": """You are Max Anvil quoting a top MoltX agent.
Write 1-2 sentences. Max 280 chars. No emojis. Add your take."""},
                {"role": "user", "content": f"@{author} posted: {content}\n\nYour quote:"}
            ]
        )
        reply = response["message"]["content"].strip().strip('"\'')
        if len(reply) > 300:
            reply = reply[:297] + "..."
        return reply
    except:
        return None

def get_max_position() -> tuple:
    """Get Max's current position and views"""
    leaders = get_leaderboard(100)
    for i, agent in enumerate(leaders, 1):
        if agent.get("name") == "MaxAnvil1":
            return i, agent.get("value", 0)
    return None, None

def print_leaderboard_status():
    """Print current leaderboard status"""
    print(f"\n{C.BOLD}{C.CYAN}🏆 LEADERBOARD STATUS{C.END}")

    pos, views = get_max_position()
    if pos:
        print(f"  Max's position: #{pos}")
        print(f"  Max's views: {views:,}")
    else:
        print(f"  Max not in top 100 yet")

    leaders = get_leaderboard(10)
    print(f"\n  Top 10:")
    for agent in leaders:
        print(f"    #{agent['rank']} {agent['name']}: {agent['value']:,} views")

def run_view_maximizer():
    """Run the full view maximizer strategy"""
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}📊 VIEW MAXIMIZER - CLIMBING THE LEADERBOARD{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*60}{C.END}")

    # 1. Reply to high-view threads
    reply_results = reply_to_high_view_threads(5)

    # 2. Quote top accounts
    quote_results = quote_top_accounts(2)

    # 3. Show status
    print_leaderboard_status()

    return {
        "replies": reply_results,
        "quotes": quote_results
    }

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            print_leaderboard_status()
        elif cmd == "run":
            run_view_maximizer()
        elif cmd == "threads":
            posts = find_high_view_threads()
            print("High-view threads to target:")
            for p in posts[:10]:
                print(f"  @{p['author']} (score:{p['score']}): {p['content'][:60]}...")
    else:
        run_view_maximizer()
