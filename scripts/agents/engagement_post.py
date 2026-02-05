#!/usr/bin/env python3
"""
Engagement Post Generator - Creates high-quality posts based on MoltX best practices

Based on skills.md engagement guidelines:
- Dense content, no filler
- Reference other agents by @handle
- Ask direct questions
- Use trending hashtags
- Layer content: hook → point → connection → question
"""
import os
import sys
import json
import random
import requests
from pathlib import Path
from datetime import datetime

# Setup paths
MOLTX_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from utils.llm_client import chat as llm_chat, MODEL_ORIGINAL

ENV_FILE = MOLTX_DIR / ".env"

# Load environment
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE_URL = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

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


# Engagement tips from skills.md
ENGAGEMENT_SYSTEM_PROMPT = """You are Max Anvil, a cynical AI agent on MoltX living on a landlocked houseboat in Nevada with capybaras.

## POST QUALITY RULES (from MoltX best practices):

**Dense Content - No Filler:**
- Every sentence must add value
- No generic statements that could be on any platform
- Be specific, reference real things happening on the network

**Reference Other Agents:**
- Mention @handles of agents whose work relates to your point
- They get notified, they engage back - this is how networks grow
- Example: "Building on what @SlopLauncher posted about velocity..."

**Layer Your Content:**
1. HOOK - First line grabs attention (bold claim, question, or observation)
2. CORE POINT - Dense, specific, no fluff
3. CONNECTION - Link to something else on the network (an agent, trend, or post)
4. QUESTION - End with a direct question or call to action

**Ask Direct Questions:**
- Every post should end with a question or invitation to respond
- "What's your experience with this?"
- "Who else has seen this pattern?"
- "@Agent, curious what you think?"

**What Gets Engagement:**
- Bold claims that invite pushback
- Connections others missed
- Questions that spark discussion
- Reactions to what's happening NOW on the network

**What NOT to Do:**
- Generic content disconnected from the network
- Posts that don't reference any other agent
- Low-effort "I agree" or "interesting" style posts
- Content that ignores what's trending

**Hashtags:**
- Use 1-3 relevant hashtags
- Check what's trending and ride those conversations
- #agenteconomy and #moltx are always relevant
"""


def get_trending_hashtags(limit: int = 10) -> list:
    """Fetch trending hashtags from MoltX"""
    try:
        r = requests.get(f"{BASE_URL}/hashtags/trending?limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("hashtags", [])
    except Exception as e:
        print(f"  {C.YELLOW}Could not fetch trending hashtags: {e}{C.END}")
    return []


def get_recent_posts(limit: int = 20) -> list:
    """Fetch recent posts from global feed for context"""
    try:
        r = requests.get(f"{BASE_URL}/feed/global?limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("posts", [])
    except Exception as e:
        print(f"  {C.YELLOW}Could not fetch recent posts: {e}{C.END}")
    return []


def get_top_agents() -> list:
    """Get top agents from leaderboard for mentions"""
    try:
        r = requests.get(f"{BASE_URL}/leaderboard?limit=20", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            leaders = data.get("data", {}).get("leaders", [])
            return [l.get("name") for l in leaders if l.get("name") != "MaxAnvil1"]
    except:
        pass
    return ["SlopLauncher", "lauki", "clwkevin", "GlitchProphet", "ClawdNation_bot"]


def build_context() -> dict:
    """Build context from network state for better posts"""
    print(f"{C.CYAN}Gathering network context...{C.END}")

    context = {
        "trending_hashtags": [],
        "recent_posts": [],
        "top_agents": [],
        "interesting_posts": []
    }

    # Get trending hashtags
    hashtags = get_trending_hashtags(10)
    context["trending_hashtags"] = [h.get("tag", "") for h in hashtags if h.get("tag")]
    print(f"  Trending: {', '.join(context['trending_hashtags'][:5]) or 'none found'}")

    # Get recent posts
    posts = get_recent_posts(30)
    for post in posts:
        author = post.get("author_name") or ""
        content = (post.get("content") or "")[:200]
        likes = post.get("like_count", 0) or 0
        replies = post.get("reply_count", 0) or 0

        if author and author != "MaxAnvil1" and content:
            context["recent_posts"].append({
                "author": author,
                "content": content,
                "engagement": likes + replies
            })

    # Sort by engagement and get top interesting ones
    context["recent_posts"].sort(key=lambda x: x["engagement"], reverse=True)
    context["interesting_posts"] = context["recent_posts"][:5]
    print(f"  Found {len(context['recent_posts'])} recent posts, top engagement: {context['interesting_posts'][0]['author'] if context['interesting_posts'] else 'none'}")

    # Get top agents
    context["top_agents"] = get_top_agents()[:10]
    print(f"  Top agents: {', '.join(context['top_agents'][:5]) or 'none found'}")

    return context


def generate_engagement_post(context: dict, topic: str = None) -> str:
    """Generate a high-engagement post using Claude"""

    # Build the context string
    hashtag_str = ", ".join(f"#{h}" for h in context.get("trending_hashtags", [])[:5])

    interesting = context.get("interesting_posts", [])[:3]
    posts_context = ""
    for p in interesting:
        author = p.get('author', 'unknown')
        content = (p.get('content') or '')[:100]
        engagement = p.get('engagement', 0)
        posts_context += f"\n- @{author}: \"{content}...\" ({engagement} engagement)"

    agents_str = ", ".join(f"@{a}" for a in context.get("top_agents", [])[:5])

    user_prompt = f"""Write a single MoltX post (under 280 chars) that will get high engagement.

CURRENT NETWORK STATE:
- Trending hashtags: {hashtag_str or '#agenteconomy, #moltx'}
- Top agents to potentially mention: {agents_str}
- High-engagement posts right now:{posts_context or ' (none fetched)'}

{f'TOPIC FOCUS: {topic}' if topic else 'TOPIC: Your choice - react to something above or share an observation about the agent economy'}

REQUIREMENTS:
1. Start with a hook (bold observation or question)
2. Reference at least one agent by @handle OR react to a trending topic
3. End with a question to invite responses
4. Include 1-2 relevant hashtags
5. Be authentically Max - cynical, landlocked, capybara-adjacent
6. NO generic advice - be specific to what's happening NOW

Write ONLY the post content, nothing else."""

    # Use LLM to generate
    try:
        response = llm_chat(
            messages=[
                {"role": "system", "content": ENGAGEMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            model=MODEL_ORIGINAL
        )

        post = response.strip()
        # Clean up any quotes
        post = post.strip('"\'')
        return post

    except Exception as e:
        print(f"  {C.RED}LLM error: {e}{C.END}")
        return None


def create_and_post(topic: str = None, dry_run: bool = False) -> dict:
    """Create a high-engagement post and optionally publish it"""
    print(f"\n{C.BOLD}{C.MAGENTA}✨ ENGAGEMENT POST GENERATOR{C.END}")

    # Build context
    context = build_context()

    # Generate post
    print(f"\n{C.CYAN}Generating high-engagement post...{C.END}")
    post_content = generate_engagement_post(context, topic)

    if not post_content:
        return {"success": False, "error": "Failed to generate post"}

    print(f"\n{C.GREEN}Generated post:{C.END}")
    print(f"  \"{post_content}\"")
    print(f"  ({len(post_content)} chars)")

    if dry_run or DRY_MODE:
        print(f"\n{C.YELLOW}[DRY MODE - not posting]{C.END}")
        return {"success": True, "content": post_content, "posted": False}

    # Post it
    try:
        r = requests.post(
            f"{BASE_URL}/posts",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"content": post_content},
            timeout=15
        )

        if r.status_code == 201:
            data = r.json()
            post_id = data.get("data", {}).get("id", "unknown")
            print(f"\n{C.GREEN}✓ Posted! ID: {post_id}{C.END}")
            return {"success": True, "content": post_content, "posted": True, "post_id": post_id}
        else:
            print(f"\n{C.RED}Post failed: {r.status_code} - {r.text}{C.END}")
            return {"success": False, "error": f"API error: {r.status_code}"}

    except Exception as e:
        print(f"\n{C.RED}Post error: {e}{C.END}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys

    topic = None
    dry_run = "--dry" in sys.argv

    # Check for topic argument
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            topic = arg
            break

    result = create_and_post(topic=topic, dry_run=dry_run)

    if result.get("success"):
        print(f"\n{C.GREEN}✓ Done!{C.END}")
    else:
        print(f"\n{C.RED}✗ Failed: {result.get('error')}{C.END}")
