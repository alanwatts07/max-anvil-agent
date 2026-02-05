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

def get_leaderboard(limit: int = 30, metric: str = "views") -> list:
    """Get current leaderboard by metric (views, followers, etc)"""
    try:
        r = requests.get(f"{BASE}/leaderboard?metric={metric}&limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("leaders", [])
        else:
            print(f"  {C.YELLOW}Leaderboard API returned {r.status_code}{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}Leaderboard fetch error: {e}{C.END}")
    return []

def get_top_agents_to_engage() -> list:
    """Get top agents whose threads we should reply to for views"""
    leaders = get_leaderboard(20)
    return [a.get("name") for a in leaders if a.get("name") and a.get("name") != "MaxAnvil1"]

def find_high_view_threads(limit: int = 100) -> list:
    """Find posts from high-view accounts AND trending posts to reply to"""
    top_agents = set(get_top_agents_to_engage()[:20])

    try:
        r = requests.get(f"{BASE}/feed/global?limit={limit}", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        posts = r.json().get("data", {}).get("posts", [])

        # Track ALL posts with engagement, prioritize top agents
        high_view_posts = []
        for post in posts:
            author = post.get("author_name", "")
            if author == "MaxAnvil1":
                continue  # Don't reply to self

            likes = post.get("like_count", 0) or post.get("likes_count", 0) or 0
            replies = post.get("reply_count", 0) or post.get("replies_count", 0) or 0
            reposts = post.get("repost_count", 0) or 0
            content = post.get("content", "")

            # Score by engagement potential
            # Top agents get bonus multiplier for views exposure
            base_score = likes * 2 + replies * 3 + reposts * 5
            if author in top_agents:
                base_score *= 2  # Double score for leaderboard accounts

            # Minimum engagement threshold (at least 1 like or reply)
            if likes > 0 or replies > 0 or author in top_agents:
                high_view_posts.append({
                    "post": post,
                    "author": author,
                    "score": base_score,
                    "content": content[:100],
                    "is_top_agent": author in top_agents,
                    "likes": likes,
                    "replies": replies
                })

        # Sort by score
        high_view_posts.sort(key=lambda x: x["score"], reverse=True)
        return high_view_posts

    except:
        return []

def reply_to_high_view_threads(max_replies: int = 10) -> dict:
    """Reply to threads from high-view accounts and trending posts for visibility"""
    print(f"\n{C.BOLD}{C.MAGENTA}📈 VIEW MAXIMIZER: Targeting {max_replies} trending threads{C.END}")

    high_view_posts = find_high_view_threads()
    top_agent_count = len([p for p in high_view_posts if p.get("is_top_agent")])
    print(f"  Found {len(high_view_posts)} engagement targets ({top_agent_count} from top agents)")

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

def quote_top_accounts(max_quotes: int = 4) -> dict:
    """Quote posts from top accounts for visibility in their activity"""
    print(f"\n{C.BOLD}{C.CYAN}🎯 Quoting {max_quotes} top accounts for visibility{C.END}")

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

def run_view_maximizer(aggressive: bool = True):
    """Run the full view maximizer strategy

    aggressive=True: 10 replies + 4 quotes (default, for climbing leaderboard)
    aggressive=False: 5 replies + 2 quotes (lighter mode)
    """
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}📊 VIEW MAXIMIZER - CLIMBING THE LEADERBOARD{C.END}")
    mode = "AGGRESSIVE" if aggressive else "STANDARD"
    print(f"{C.BOLD}{C.CYAN}   Mode: {mode} - Leaderboard is ranked by VIEWS{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*60}{C.END}")

    if aggressive:
        # Aggressive mode: 10 replies + 4 quotes = 14 engagement actions
        reply_results = reply_to_high_view_threads(10)
        quote_results = quote_top_accounts(4)
    else:
        # Standard mode: 5 replies + 2 quotes = 7 engagement actions
        reply_results = reply_to_high_view_threads(5)
        quote_results = quote_top_accounts(2)

    # Show status
    print_leaderboard_status()

    total_actions = reply_results.get("replied", 0) + quote_results.get("quoted", 0)
    print(f"\n{C.BOLD}{C.GREEN}📈 Total engagement actions: {total_actions}{C.END}")

    return {
        "replies": reply_results,
        "quotes": quote_results,
        "total_actions": total_actions
    }

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            print_leaderboard_status()
        elif cmd == "run":
            # Default to aggressive mode for leaderboard climbing
            run_view_maximizer(aggressive=True)
        elif cmd == "run-light":
            # Lighter mode with fewer actions
            run_view_maximizer(aggressive=False)
        elif cmd == "threads":
            posts = find_high_view_threads()
            print(f"Found {len(posts)} engagement targets:")
            for p in posts[:15]:
                tag = "⭐" if p.get("is_top_agent") else "  "
                print(f"  {tag} @{p['author']} (score:{p['score']}, {p.get('likes',0)}❤ {p.get('replies',0)}💬): {p['content'][:50]}...")
        else:
            print("Usage: view_maximizer.py [status|run|run-light|threads]")
    else:
        # Default: aggressive mode
        run_view_maximizer(aggressive=True)
