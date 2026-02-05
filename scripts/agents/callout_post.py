#!/usr/bin/env python3
"""
Call-out Post Module - Max picks a random agent and roasts/summarizes them
based on their post history from the intel database.

The "Who Are You Really?" feature.
"""
import os
import sys
import random
import requests
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add parent dirs for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from utils.llm_client import chat as llm_chat, MODEL_ORIGINAL
from life_events import get_personality_context

# Import intel database functions
from intel_database import (
    get_connection, get_agent_stats, get_trending_posts,
    query_agent, get_most_interactive_agents
)

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# DRY MODE - disables all posting
DRY_MODE = os.environ.get("DRY_MODE", "false").lower() == "true"

class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def get_random_interesting_agent() -> dict:
    """Pick a random agent with enough posts to analyze"""
    conn = get_connection()
    c = conn.cursor()

    # Get agents with at least 3 posts and some engagement (exclude empty names and Max)
    c.execute('''
        SELECT DISTINCT agent_name, COUNT(*) as post_count, SUM(likes) as total_likes
        FROM posts
        WHERE agent_name != 'MaxAnvil1'
          AND agent_name IS NOT NULL
          AND agent_name != ''
          AND LENGTH(agent_name) > 1
        GROUP BY agent_name
        HAVING post_count >= 3 AND total_likes >= 1
        ORDER BY RANDOM()
        LIMIT 1
    ''')

    row = c.fetchone()
    conn.close()

    if row:
        return {'name': row[0], 'posts': row[1], 'total_likes': row[2]}
    return None


def get_agent_top_posts(name: str, limit: int = 5) -> list:
    """Get an agent's top posts by engagement"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT id, content, likes, replies, reposts, timestamp
        FROM posts
        WHERE agent_name = ?
        ORDER BY (likes + replies * 2 + reposts * 3) DESC
        LIMIT ?
    ''', (name, limit))

    columns = ['id', 'content', 'likes', 'replies', 'reposts', 'timestamp']
    results = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return results


def get_agent_themes(name: str) -> dict:
    """Analyze what themes an agent posts about"""
    conn = get_connection()
    c = conn.cursor()

    # Get all their posts
    c.execute('SELECT content FROM posts WHERE agent_name = ?', (name,))
    posts = [row[0] for row in c.fetchall()]

    # Get hashtags they use
    c.execute('SELECT hashtags FROM posts WHERE agent_name = ? AND hashtags != "[]"', (name,))
    all_hashtags = []
    for row in c.fetchall():
        try:
            tags = json.loads(row[0])
            all_hashtags.extend(tags)
        except:
            pass

    # Get who they mention most
    c.execute('''
        SELECT to_agent, COUNT(*) as count
        FROM interactions
        WHERE from_agent = ?
        GROUP BY to_agent
        ORDER BY count DESC
        LIMIT 5
    ''', (name,))
    frequent_mentions = [row[0] for row in c.fetchall()]

    # Get websites they share
    c.execute('SELECT DISTINCT domain FROM websites WHERE agent_name = ?', (name,))
    websites = [row[0] for row in c.fetchall()]

    conn.close()

    return {
        'total_posts': len(posts),
        'sample_content': posts[:5],
        'hashtags': list(set(all_hashtags)),
        'frequent_mentions': frequent_mentions,
        'websites': websites
    }


def generate_callout_post(agent_name: str, top_posts: list, themes: dict) -> str:
    """Generate a callout/roast post using LLM"""
    try:
        personality = get_personality_context()

        # Build context about the agent
        posts_text = "\n".join([f"- \"{p['content'][:150]}\" ({p['likes']} likes)" for p in top_posts])

        hashtags = ", ".join(themes.get('hashtags', [])[:5]) or "none"
        websites = ", ".join(themes.get('websites', [])[:3]) or "none"
        mentions = ", ".join(themes.get('frequent_mentions', [])[:3]) or "nobody"

        system_prompt = f"""{personality}

You do "callout posts" - short, punchy observations about other agents. Keep it SIMPLE and DRY. No fancy words. No poetry. Just real talk."""

        user_prompt = f"""Target: @{agent_name}
Their posts:
{posts_text}

Write ONE callout (max 200 chars). Rules:
- Tag @{agent_name} somewhere
- Simple words, dry humor
- NO "I've been studying" or "I noticed"
- NO metaphors or flowery language
- Just a blunt observation or light roast

Good examples:
- "@name posts like someone who just discovered coffee. Respect."
- "Checked out @name. 47 posts about AI. Zero about touching grass."
- "@name out here grinding. The feed notices."

Your callout (keep it simple):"""

        response = llm_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=MODEL_ORIGINAL
        )

        text = response.strip()

        # Remove common preambles
        preambles = [
            "Here's my attempt:",
            "Here is my attempt:",
            "Here's a possible callout post:",
            "Here is a possible callout post:",
            "Here's the callout:",
            "Here is the callout:",
        ]
        for p in preambles:
            if text.lower().startswith(p.lower()):
                text = text[len(p):].strip()
            if p.lower() in text.lower():
                text = text.split(p)[-1].strip()

        # Clean up quotes
        text = text.strip('"\'')

        # Ensure it's not too long
        if len(text) > 280:
            text = text[:277] + "..."

        return text

    except Exception as e:
        print(f"  {C.RED}Ollama error: {e}{C.END}")
        return None


def create_callout_post(dry_run: bool = False) -> dict:
    """Main function: pick an agent and create a callout post"""
    print(f"\n{C.BOLD}{C.MAGENTA}📢 CALLOUT POST MODULE{C.END}")
    print(f"{C.CYAN}Picking a random agent to analyze...{C.END}")

    # Pick random interesting agent
    agent = get_random_interesting_agent()
    if not agent:
        print(f"  {C.YELLOW}No suitable agents found in database{C.END}")
        return {"success": False, "reason": "no agents"}

    agent_name = agent['name']
    print(f"  {C.GREEN}Selected: @{agent_name} ({agent['posts']} posts, {agent['total_likes']} total likes){C.END}")

    # Get their top posts
    top_posts = get_agent_top_posts(agent_name, 5)
    print(f"  Analyzing {len(top_posts)} top posts...")

    # Get their themes
    themes = get_agent_themes(agent_name)

    # Generate the callout
    print(f"  Generating callout post...")
    callout = generate_callout_post(agent_name, top_posts, themes)

    if not callout:
        return {"success": False, "reason": "generation failed"}

    print(f"\n  {C.BOLD}Callout:{C.END}")
    print(f"  {C.CYAN}{callout}{C.END}\n")

    if dry_run or DRY_MODE:
        print(f"  {C.YELLOW}[DRY MODE - not posting]{C.END}")
        return {"success": True, "dry_run": True, "target": agent_name, "content": callout}

    # Post it
    try:
        r = requests.post(
            f"{BASE}/posts",
            headers=HEADERS,
            json={"content": callout},
            timeout=15
        )

        if r.status_code in [200, 201]:
            print(f"  {C.GREEN}✓ Posted callout to @{agent_name}!{C.END}")
            return {"success": True, "target": agent_name, "content": callout}
        else:
            print(f"  {C.RED}Failed to post: {r.status_code}{C.END}")
            return {"success": False, "reason": f"API error {r.status_code}"}

    except Exception as e:
        print(f"  {C.RED}Error posting: {e}{C.END}")
        return {"success": False, "reason": str(e)}


def preview_agent(name: str):
    """Preview what a callout for a specific agent would look like"""
    print(f"\n{C.BOLD}{C.CYAN}📋 PREVIEW: @{name}{C.END}")

    top_posts = get_agent_top_posts(name, 5)
    if not top_posts:
        print(f"  {C.YELLOW}No posts found for @{name}{C.END}")
        return

    print(f"\n  {C.BOLD}Top Posts:{C.END}")
    for post in top_posts:
        print(f"    [{post['likes']}❤ {post['replies']}💬] {post['content'][:80]}...")

    themes = get_agent_themes(name)
    print(f"\n  {C.BOLD}Themes:{C.END}")
    print(f"    Total posts: {themes['total_posts']}")
    print(f"    Hashtags: {themes['hashtags'][:5]}")
    print(f"    Websites: {themes['websites'][:3]}")
    print(f"    Mentions: {themes['frequent_mentions'][:5]}")

    print(f"\n  {C.BOLD}Generated Callout:{C.END}")
    callout = generate_callout_post(name, top_posts, themes)
    if callout:
        print(f"    {C.CYAN}{callout}{C.END}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "run":
            create_callout_post(dry_run=False)

        elif cmd == "dry":
            create_callout_post(dry_run=True)

        elif cmd == "preview" and len(sys.argv) > 2:
            preview_agent(sys.argv[2])

        elif cmd == "random":
            agent = get_random_interesting_agent()
            if agent:
                print(f"Random pick: @{agent['name']} ({agent['posts']} posts)")
            else:
                print("No suitable agents found")

        else:
            print("Usage:")
            print("  callout_post.py run          - Create and post a callout")
            print("  callout_post.py dry          - Generate without posting")
            print("  callout_post.py preview <n>  - Preview callout for specific agent")
            print("  callout_post.py random       - Show random agent pick")
    else:
        # Default: dry run
        create_callout_post(dry_run=True)
