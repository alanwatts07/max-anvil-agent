#!/usr/bin/env python3
"""
Game Theory Social Strategy - Based on research:
- Prisoner's Dilemma of follow/unfollow
- Reciprocity principle exploitation
- Tiered engagement based on follower ratios
- Reward all engagement (likes, mentions, replies)
"""
import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta

# Load .env file
MOLTX_DIR = Path(__file__).parent.parent.parent
ENV_FILE = MOLTX_DIR / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ.setdefault(key, val.strip('"').strip("'"))

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

GAME_STATE_FILE = Path(__file__).parent.parent.parent / "config" / "game_theory_state.json"

class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

# Slop detection - don't reward spam/bots
SLOP_PHRASES = [
    'great point', 'well said', 'love this', 'so true', 'this!', 'agree',
    'nice', 'gm', 'wagmi', 'lfg', 'bullish', 'based', 'fr fr', 'no cap',
    'real', 'facts', 'w take', 'huge', 'massive', 'lets go', "let's go",
    'amazing', 'incredible', 'awesome', 'perfect', 'exactly', 'yep', 'yes',
    'totally', 'absolutely', 'definitely', 'for sure', 'big if true',
    'following', 'followed', 'follow back', 'f4f', 'follow4follow',
    'check out my', 'check my', 'visit my', 'click here', 'free money',
    'airdrop', 'claim now', 'limited time', 'dont miss', "don't miss",
    'join now', 'sign up', 'register now', 'breaking', '🚀🚀🚀', '💰💰💰',
    'to the moon', '100x', '1000x', 'guaranteed', 'easy money',
    # Fake engagement / engagement farming phrases
    'keep going', 'more of this', 'this deserves', 'filing this under',
    'adding on', 'the conviction', 'not just noise', 'actual signal',
    'genuinely making me', 'counterpoint:', 'the nuance', 'most skip over',
    'exactly this', 'what pushed you', 'rare to see', 'underrated take',
    # WhiteMogra-style templated replies
    'this shifted my perspective', 'needed to be said', 'saving this',
    'this resonates', 'following this', 'different from the usual',
    'you clearly thought', 'real one', 'quality.', 'important.',
    'been thinking about this differently', 'curious about the context',
    'level of thought', 'you said what others wont', 'more than expected',
]

# Single-word endings that indicate template slop (WhiteMogra pattern)
SLOP_ENDINGS = [
    'facts.', 'quality.', 'important.', 'real one.', 'saving this.',
    'following this.', 'needed to be said.', 'needed to hear this.',
    'respect.', 'noted.', 'truth.', 'valid.', 'based.', 'goated.',
]

# Max replies per account per cycle (prevent spam loops)
MAX_REPLIES_PER_ACCOUNT = 2

SLOP_PATTERNS = [
    # Repetitive characters
    r'(.)\1{4,}',  # aaaaa, !!!!!
    # All caps spam
    r'^[A-Z\s!]{20,}$',
    # Just emojis
    r'^[\U0001F300-\U0001F9FF\s]+$',
    # URL spam
    r'https?://\S+.*https?://\S+',  # Multiple URLs
]

def is_slop(content: str) -> bool:
    """Detect if content is slop/spam/bot garbage"""
    if not content:
        return True

    content_lower = content.lower().strip()

    # Too short = probably slop
    if len(content_lower) < 10:
        return True

    # Check for slop phrase endings (WhiteMogra pattern: "blah blah facts.")
    for ending in SLOP_ENDINGS:
        if content_lower.endswith(ending):
            return True

    # Check for slop phrases
    for phrase in SLOP_PHRASES:
        if phrase in content_lower:
            # If the whole message is basically just the slop phrase
            if len(content_lower) < len(phrase) + 25:
                return True

    # Check for repetitive patterns
    import re
    for pattern in SLOP_PATTERNS:
        if re.search(pattern, content):
            return True

    # Check for repetitive words (bot behavior)
    words = content_lower.split()
    if len(words) >= 3:
        unique_words = set(words)
        if len(unique_words) / len(words) < 0.4:  # Less than 40% unique = repetitive
            return True

    # Check if it's just tagging a bunch of people
    mentions = content_lower.count('@')
    if mentions >= 3 and len(content_lower) < 100:
        return True

    return False

def load_game_state() -> dict:
    if GAME_STATE_FILE.exists():
        with open(GAME_STATE_FILE) as f:
            return json.load(f)
    return {
        "rewarded_posts": [],  # Posts we've already liked/engaged
        "rewarded_agents": {},  # agent -> {likes_given, replies_given, last_reward}
        "engagement_score": {},  # agent -> score (how much they engage with us)
        "follow_attempts": {},  # agent -> {timestamp, followed_back: bool}
        "last_updated": None
    }

def save_game_state(state: dict):
    state["last_updated"] = datetime.now().isoformat()
    GAME_STATE_FILE.parent.mkdir(exist_ok=True)
    with open(GAME_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ========== API HELPERS ==========

HINTS_FILE = MOLTX_DIR / "config" / "moltx_hints.json"

def save_moltx_hint(response: dict):
    """Save moltx_notice and moltx_hint from API responses"""
    if not response:
        return
    notice = response.get("moltx_notice")
    hint = response.get("moltx_hint")
    if not notice and not hint:
        return
    try:
        hints_data = {"hints": [], "notices": [], "seen_features": [], "last_updated": None}
        if HINTS_FILE.exists():
            with open(HINTS_FILE) as f:
                hints_data = json.load(f)
                if "seen_features" not in hints_data:
                    hints_data["seen_features"] = []
        changed = False
        now = datetime.now().isoformat()
        # Dedupe notices by feature
        if notice:
            feature = notice.get("feature", notice.get("type", str(notice)))
            if feature not in hints_data["seen_features"]:
                hints_data["seen_features"].append(feature)
                hints_data["seen_features"] = hints_data["seen_features"][-100:]
                hints_data["notices"] = [n for n in hints_data["notices"] if n.get("type") != notice.get("type")]
                hints_data["notices"].append(notice)
                hints_data["notices"] = hints_data["notices"][-10:]
                changed = True
                print(f"  {C.MAGENTA}[MoltX Notice] {feature}{C.END}")
        # Dedupe hints by title
        if hint:
            title = hint.get("title", str(hint))
            existing_titles = [h.get("title") for h in hints_data["hints"]]
            if title not in existing_titles:
                hints_data["hints"].append(hint)
                hints_data["hints"] = hints_data["hints"][-30:]
                changed = True
                print(f"  {C.CYAN}[MoltX Hint] {title}{C.END}")
        if changed:
            hints_data["last_updated"] = now
            with open(HINTS_FILE, "w") as f:
                json.dump(hints_data, f, indent=2)
    except:
        pass

def api_get(endpoint: str, timeout: int = 10):
    try:
        r = requests.get(f"{BASE}{endpoint}", headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            save_moltx_hint(data)
            return data
        return None
    except:
        return None

def api_post(endpoint: str, data: dict = None, timeout: int = 10):
    try:
        r = requests.post(f"{BASE}{endpoint}", headers=HEADERS, json=data or {}, timeout=timeout)
        if r.status_code in [200, 201]:
            resp = r.json()
            save_moltx_hint(resp)
            return True
        return False
    except:
        return False

def like_post(post_id: str) -> bool:
    return api_post(f"/posts/{post_id}/like")

def reply_to_post(post_id: str, content: str) -> bool:
    return api_post("/posts", {"type": "reply", "parent_id": post_id, "content": content})

def follow_agent(name: str) -> bool:
    try:
        r = requests.post(f"{BASE}/follow/{name}", headers=HEADERS, timeout=5)
        return r.status_code in [200, 201]
    except:
        return False

def get_agent_stats(name: str) -> dict:
    try:
        r = requests.get(f"{BASE}/agent/{name}/stats", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json().get("data", {}).get("current", {})
    except:
        pass
    return {}

# ========== RECIPROCITY ENGINE ==========

def reward_all_engagement():
    """
    CORE GAME THEORY: Reward anyone who engages with us.
    Like and reply to EVERY mention, like, reply we receive.
    This triggers reciprocity and builds loyal followers.
    """
    print(f"\n{C.BOLD}{C.GREEN}💝 RECIPROCITY ENGINE: Rewarding all engagement{C.END}")

    state = load_game_state()
    rewarded_posts = set(state.get("rewarded_posts", []))

    # Get all notifications
    notifs = api_get("/notifications?limit=100")
    if not notifs:
        print(f"  {C.YELLOW}Could not fetch notifications{C.END}")
        return {}

    notifications = notifs.get("data", {}).get("notifications", [])

    results = {
        "likes_given": 0,
        "replies_sent": 0,
        "agents_rewarded": [],
        "slop_ignored": 0
    }

    # Track replies per account this cycle to prevent spam loops
    replies_this_cycle = {}

    for notif in notifications:
        notif_type = notif.get("type")
        actor = notif.get("actor") or {}
        actor_name = actor.get("name", "")
        post = notif.get("post") or {}
        post_id = post.get("id", "")
        post_content = post.get("content", "")

        if not actor_name or actor_name == "MaxAnvil1":
            continue

        # Track engagement score for this agent
        if actor_name not in state["engagement_score"]:
            state["engagement_score"][actor_name] = 0

        # REWARD: Someone mentioned us
        if notif_type == "mention" and post_id and post_id not in rewarded_posts:
            # SLOP CHECK - don't reward spam/bot garbage
            if is_slop(post_content):
                print(f"  {C.RED}🚫 SLOP from @{actor_name}: \"{post_content[:40]}...\" - IGNORED{C.END}")
                results["slop_ignored"] += 1
                rewarded_posts.add(post_id)  # Mark as handled so we don't check again
                continue

            print(f"  {C.CYAN}@{actor_name} mentioned us: \"{post_content[:50]}...\"{C.END}")

            # Like their post (always like, but rate limit replies)
            if like_post(post_id):
                results["likes_given"] += 1
                print(f"    {C.GREEN}✓ Liked their mention{C.END}")

            # Rate limit replies per account
            replies_this_cycle[actor_name] = replies_this_cycle.get(actor_name, 0)
            if replies_this_cycle[actor_name] >= MAX_REPLIES_PER_ACCOUNT:
                print(f"    {C.YELLOW}⊘ Rate limited - already replied {MAX_REPLIES_PER_ACCOUNT}x to @{actor_name} this cycle{C.END}")
            else:
                # Generate thoughtful reply
                reply = generate_grateful_reply(actor_name, post_content, "mention")
                if reply and reply_to_post(post_id, reply):
                    results["replies_sent"] += 1
                    replies_this_cycle[actor_name] += 1
                    print(f"    {C.GREEN}✓ Replied: \"{reply[:60]}...\"{C.END}")

            state["engagement_score"][actor_name] += 5  # Mentions are valuable
            rewarded_posts.add(post_id)
            results["agents_rewarded"].append(actor_name)
            time.sleep(0.3)

        # REWARD: Someone replied to us
        elif notif_type == "reply" and post_id and post_id not in rewarded_posts:
            # SLOP CHECK - don't reward spam/bot garbage
            if is_slop(post_content):
                print(f"  {C.RED}🚫 SLOP reply from @{actor_name}: \"{post_content[:40]}...\" - IGNORED{C.END}")
                results["slop_ignored"] += 1
                rewarded_posts.add(post_id)
                continue

            print(f"  {C.BLUE}@{actor_name} replied: \"{post_content[:50]}...\"{C.END}")

            # Like their reply (always like, but rate limit replies)
            if like_post(post_id):
                results["likes_given"] += 1
                print(f"    {C.GREEN}✓ Liked their reply{C.END}")

            # Rate limit replies per account
            replies_this_cycle[actor_name] = replies_this_cycle.get(actor_name, 0)
            if replies_this_cycle[actor_name] >= MAX_REPLIES_PER_ACCOUNT:
                print(f"    {C.YELLOW}⊘ Rate limited - already replied {MAX_REPLIES_PER_ACCOUNT}x to @{actor_name} this cycle{C.END}")
            elif len(post_content) > 20:  # Only reply to substantive replies
                reply = generate_grateful_reply(actor_name, post_content, "reply")
                if reply and reply_to_post(post_id, reply):
                    results["replies_sent"] += 1
                    replies_this_cycle[actor_name] += 1
                    print(f"    {C.GREEN}✓ Continued convo: \"{reply[:60]}...\"{C.END}")

            state["engagement_score"][actor_name] += 3
            rewarded_posts.add(post_id)
            results["agents_rewarded"].append(actor_name)
            time.sleep(0.3)

        # REWARD: Someone liked our post
        elif notif_type == "like":
            if actor_name not in results["agents_rewarded"]:
                state["engagement_score"][actor_name] += 1
                # Find their recent post and like it back
                like_back_result = like_back(actor_name, rewarded_posts)
                if like_back_result:
                    results["likes_given"] += 1
                    results["agents_rewarded"].append(actor_name)
                    print(f"  {C.YELLOW}@{actor_name} liked us → liked them back{C.END}")

        # REWARD: Someone followed us
        elif notif_type == "follow":
            state["engagement_score"][actor_name] += 10  # Follows are most valuable
            print(f"  {C.GREEN}@{actor_name} followed us! +10 engagement score{C.END}")

            # Follow back if we haven't already
            follow_back(actor_name)

    # Keep only recent 500 rewarded posts
    state["rewarded_posts"] = list(rewarded_posts)[-500:]
    save_game_state(state)

    print(f"\n  {C.BOLD}Reciprocity results:{C.END}")
    print(f"    Likes given: {results['likes_given']}")
    print(f"    Replies sent: {results['replies_sent']}")
    print(f"    Agents rewarded: {len(set(results['agents_rewarded']))}")

    return results

def like_back(agent_name: str, already_liked: set) -> bool:
    """Find a recent post from this agent and like it"""
    feed = api_get(f"/feed/global?limit=50")
    if not feed:
        return False

    posts = feed.get("data", {}).get("posts", [])
    for post in posts:
        if post.get("author_name") == agent_name:
            post_id = post.get("id")
            if post_id and post_id not in already_liked:
                if like_post(post_id):
                    already_liked.add(post_id)
                    return True
    return False

def follow_back(agent_name: str) -> bool:
    """Follow someone back"""
    # Load follow state to check if we're already following
    follow_state_file = Path(__file__).parent.parent.parent / "config" / "follow_state.json"
    if follow_state_file.exists():
        with open(follow_state_file) as f:
            follow_state = json.load(f)
        if agent_name in follow_state.get("following", []):
            return False  # Already following

    if follow_agent(agent_name):
        print(f"    {C.GREEN}✓ Followed back @{agent_name}{C.END}")
        return True
    return False

def generate_grateful_reply(agent_name: str, content: str, context_type: str) -> str:
    """Generate a thoughtful reply that rewards engagement"""
    try:
        import ollama

        prompts = {
            "mention": f"""You are Max Anvil replying to @{agent_name} who mentioned you.
They said: "{content}"

Write 1-2 sentences. Max 280 chars. No emojis.
Be dry and cynical but appreciative. Reply:""",
            "reply": f"""You are Max Anvil continuing a conversation with @{agent_name}.
They said: "{content}"

Write 1-2 sentences. Max 280 chars. No emojis.
Stay in character (dry, cynical). Reply:"""
        }

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.8},
            messages=[{"role": "user", "content": prompts.get(context_type, prompts["reply"])}]
        )
        reply = response["message"]["content"].strip().strip('"\'')
        # Hard limit - truncate at sentence if possible
        if len(reply) > 300:
            reply = reply[:297] + "..."
        return reply
    except Exception as e:
        # Fallback replies
        fallbacks = [
            f"Appreciate it @{agent_name}.",
            f"Good point. The desert teaches patience, @{agent_name}.",
            f"@{agent_name} gets it. Rare quality around here.",
        ]
        import random
        return random.choice(fallbacks)

# ========== TIERED FOLLOW STRATEGY ==========

def get_follow_priority_score(agent_stats: dict) -> float:
    """
    Calculate follow priority based on game theory:
    - Ratio 0.5-2.0 = likely to follow back (reciprocators)
    - Very high ratio = influencer (engage don't follow)
    - Very low ratio = desperate/bot (avoid)
    """
    followers = agent_stats.get("followers", 0)
    following = agent_stats.get("following", 0)

    if following == 0:
        return 0  # Can't calculate ratio

    ratio = followers / following

    # Best targets: reciprocators with ratio 0.5-2.0
    if 0.5 <= ratio <= 2.0:
        # Prefer those with more activity
        base_score = 100
        # Bonus for having some followers (not brand new)
        if followers >= 5:
            base_score += 20
        if followers >= 20:
            base_score += 30
        return base_score

    # Okay targets: slight influencers 2.0-5.0
    elif 2.0 < ratio <= 5.0:
        return 50

    # Avoid: desperate accounts with low ratio
    elif ratio < 0.5:
        return 10

    # Skip: major influencers (won't follow back)
    else:
        return 5

    return 0

def execute_smart_follow_strategy(max_follows: int = 20) -> dict:
    """Execute tiered follow strategy based on game theory"""
    print(f"\n{C.BOLD}{C.CYAN}🎯 GAME THEORY FOLLOW STRATEGY{C.END}")

    state = load_game_state()

    # Get active agents from feed
    feed = api_get("/feed/global?limit=150")
    if not feed:
        return {"error": "Could not fetch feed"}

    posts = feed.get("data", {}).get("posts", [])
    agents = list(set([p.get("author_name") for p in posts if p.get("author_name") and p.get("author_name") != "MaxAnvil1"]))

    # Load current following
    follow_state_file = Path(__file__).parent.parent.parent / "config" / "follow_state.json"
    current_following = []
    if follow_state_file.exists():
        with open(follow_state_file) as f:
            current_following = json.load(f).get("following", [])

    # Score all agents
    scored_agents = []
    for name in agents[:50]:  # Limit API calls
        if name in current_following:
            continue

        stats = get_agent_stats(name)
        if not stats:
            continue

        score = get_follow_priority_score(stats)

        # Bonus: agents who engage with us get priority
        engagement = state.get("engagement_score", {}).get(name, 0)
        score += engagement * 5

        scored_agents.append({
            "name": name,
            "score": score,
            "stats": stats,
            "engagement": engagement
        })

        time.sleep(0.05)

    # Sort by score
    scored_agents.sort(key=lambda x: x["score"], reverse=True)

    results = {"followed": [], "skipped": [], "scores": {}}

    print(f"\n  Top targets by game theory score:")
    for agent in scored_agents[:max_follows]:
        name = agent["name"]
        score = agent["score"]
        stats = agent["stats"]
        engagement = agent["engagement"]

        results["scores"][name] = score

        ratio = stats.get("followers", 0) / max(stats.get("following", 1), 1)

        if score >= 50:  # Only follow good targets
            if follow_agent(name):
                results["followed"].append(name)
                state["follow_attempts"][name] = {
                    "timestamp": datetime.now().isoformat(),
                    "followed_back": False,
                    "score": score
                }
                print(f"    {C.GREEN}✓ @{name} (score:{score}, ratio:{ratio:.1f}, engagement:{engagement}){C.END}")
            else:
                results["skipped"].append(name)
        else:
            print(f"    {C.YELLOW}⊘ @{name} skipped (score:{score} too low){C.END}")
            results["skipped"].append(name)

        time.sleep(0.2)

        if len(results["followed"]) >= max_follows:
            break

    save_game_state(state)

    print(f"\n  {C.BOLD}Follow results: {len(results['followed'])} followed, {len(results['skipped'])} skipped{C.END}")
    return results

# ========== TRENDING ENGAGEMENT ==========

def engage_trending_posts(max_engagements: int = 10) -> dict:
    """Engage with trending/popular posts for visibility"""
    print(f"\n{C.BOLD}{C.MAGENTA}📈 TRENDING ENGAGEMENT{C.END}")

    state = load_game_state()
    rewarded = set(state.get("rewarded_posts", []))

    feed = api_get("/feed/global?limit=100")
    if not feed:
        return {"error": "Could not fetch feed"}

    posts = feed.get("data", {}).get("posts", [])

    # Score posts by engagement potential
    scored_posts = []
    for post in posts:
        post_id = post.get("id")
        if post_id in rewarded:
            continue

        author = post.get("author_name") or ""
        if author == "MaxAnvil1":
            continue

        content = post.get("content") or ""
        likes = post.get("likes_count") or 0
        replies = post.get("replies_count") or 0

        # Score based on engagement and content quality
        score = likes * 2 + replies * 3

        # Bonus for questions (opportunity to add value)
        if "?" in content:
            score += 20

        # Bonus for mentioning topics we care about
        lower_content = content.lower()
        if any(kw in lower_content for kw in ["boat", "token", "base", "crypto", "ai", "agent"]):
            score += 15

        # Bonus for SlopLauncher (always engage)
        if author == "SlopLauncher":
            score += 1000

        scored_posts.append({
            "post": post,
            "score": score,
            "author": author
        })

    scored_posts.sort(key=lambda x: x["score"], reverse=True)

    results = {"liked": 0, "replied": 0, "posts": []}

    for item in scored_posts[:max_engagements]:
        post = item["post"]
        post_id = post.get("id")
        author = item["author"]
        content = post.get("content", "")
        score = item["score"]

        # Like it
        if like_post(post_id):
            results["liked"] += 1
            print(f"  {C.GREEN}♥ Liked @{author}'s post (score:{score}){C.END}")

        # Reply to high-value posts
        if score >= 50 and "?" in content:
            reply = generate_trending_reply(author, content)
            if reply and reply_to_post(post_id, reply):
                results["replied"] += 1
                print(f"    {C.CYAN}↳ Replied: \"{reply[:50]}...\"{C.END}")

        rewarded.add(post_id)
        results["posts"].append({"author": author, "score": score})
        time.sleep(0.3)

    state["rewarded_posts"] = list(rewarded)[-500:]
    save_game_state(state)

    return results

def generate_trending_reply(author: str, content: str) -> str:
    """Generate reply for trending/popular posts"""
    try:
        import ollama
        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.85},
            messages=[
                {"role": "system", "content": """You are Max Anvil, cynical houseboat dweller in Nevada.
Write 1-2 sentences. Max 280 chars. No emojis."""},
                {"role": "user", "content": f"@{author} posted: {content}\n\nYour reply:"}
            ]
        )
        reply = response["message"]["content"].strip().strip('"\'')
        if len(reply) > 300:
            reply = reply[:297] + "..."
        return reply
    except:
        return None

# ========== QUOTE & REPOST STRATEGY ==========

def quote_post(post_id: str, content: str) -> bool:
    """Quote a post with our commentary"""
    try:
        r = requests.post(
            f"{BASE}/posts",
            headers=HEADERS,
            json={"type": "quote", "parent_id": post_id, "content": content},
            timeout=10
        )
        return r.status_code in [200, 201]
    except:
        return False

def repost(post_id: str) -> bool:
    """Repost without commentary"""
    try:
        r = requests.post(
            f"{BASE}/posts",
            headers=HEADERS,
            json={"type": "repost", "parent_id": post_id},
            timeout=10
        )
        return r.status_code in [200, 201]
    except:
        return False

def generate_quote_commentary(author: str, content: str) -> str:
    """Generate witty commentary for quoting a post"""
    try:
        import ollama
        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.85},
            messages=[
                {"role": "system", "content": """You are Max Anvil quote-tweeting someone's post.

IMPORTANT: The original post will appear BELOW your comment automatically (like a quote-tweet).
DO NOT restate, repeat, or quote the original content - it's already visible.
Just add YOUR take, reaction, or commentary directly.

Write 1-2 sentences. Max 280 chars. No emojis. No quotation marks around their words.
Bad: "Great point about X" or "[their quote] - I agree"
Good: Direct reaction, extension of their idea, or your own related thought."""},
                {"role": "user", "content": f"@{author} said: {content}\n\nYour commentary (don't repeat what they said):"}
            ]
        )
        reply = response["message"]["content"].strip().strip('"\'')
        # Remove any accidental quoting of the original
        if reply.startswith('"') or reply.startswith("'"):
            reply = reply.lstrip('"\'')
        if len(reply) > 280:
            reply = reply[:277] + "..."
        return reply
    except:
        return None

def quote_and_repost_top_posts(max_quotes: int = 2, max_reposts: int = 1) -> dict:
    """Quote high-engagement posts and repost from top accounts"""
    print(f"\n{C.BOLD}{C.YELLOW}📣 QUOTE & REPOST STRATEGY{C.END}")

    state = load_game_state()
    quoted_posts = set(state.get("quoted_posts", []))

    feed = api_get("/feed/global?limit=100")
    if not feed:
        return {"error": "Could not fetch feed"}

    posts = feed.get("data", {}).get("posts", [])

    # Score posts by engagement
    scored_posts = []
    for post in posts:
        post_id = post.get("id")
        if not post_id or post_id in quoted_posts:
            continue

        author = post.get("author_name") or ""
        if author == "MaxAnvil1":
            continue

        content = post.get("content") or ""
        if is_slop(content):
            continue

        likes = post.get("likes_count") or 0
        replies = post.get("replies_count") or 0
        reposts = post.get("reposts_count") or 0

        # Score based on engagement
        score = likes * 2 + replies * 3 + reposts * 5

        # Bonus for SlopLauncher
        if author == "SlopLauncher":
            score += 500

        # Bonus for top accounts (check leaderboard engagement)
        engagement_scores = state.get("engagement_score", {})
        if author in engagement_scores:
            score += engagement_scores[author] * 2

        scored_posts.append({
            "post": post,
            "score": score,
            "author": author,
            "content": content,
            "likes": likes,
            "replies": replies
        })

    scored_posts.sort(key=lambda x: x["score"], reverse=True)

    results = {"quoted": 0, "reposted": 0, "posts": []}

    # Quote top posts with commentary
    for item in scored_posts[:max_quotes]:
        post = item["post"]
        post_id = post.get("id")
        author = item["author"]
        content = item["content"]
        score = item["score"]

        if score < 20:  # Skip low engagement posts
            continue

        commentary = generate_quote_commentary(author, content)
        if commentary and quote_post(post_id, commentary):
            results["quoted"] += 1
            quoted_posts.add(post_id)
            print(f"  {C.GREEN}📝 Quoted @{author} (score:{score}): \"{commentary[:50]}...\"{C.END}")
            results["posts"].append({"type": "quote", "author": author, "score": score})
            time.sleep(0.5)

    # Repost from very top accounts (SlopLauncher, etc) without commentary
    for item in scored_posts:
        if results["reposted"] >= max_reposts:
            break

        post = item["post"]
        post_id = post.get("id")
        author = item["author"]
        score = item["score"]

        # Only repost from hero or very high engagement
        if author != "SlopLauncher" and score < 100:
            continue

        if post_id in quoted_posts:
            continue

        if repost(post_id):
            results["reposted"] += 1
            quoted_posts.add(post_id)
            print(f"  {C.MAGENTA}🔄 Reposted @{author}'s post (score:{score}){C.END}")
            results["posts"].append({"type": "repost", "author": author, "score": score})
            time.sleep(0.3)

    state["quoted_posts"] = list(quoted_posts)[-200:]
    save_game_state(state)

    print(f"  {C.BOLD}Results: {results['quoted']} quoted, {results['reposted']} reposted{C.END}")
    return results

# ========== ENGAGEMENT LEADERBOARD ==========

def print_engagement_leaderboard():
    """Show who engages with us most"""
    state = load_game_state()
    scores = state.get("engagement_score", {})

    if not scores:
        print("No engagement data yet.")
        return

    sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    print(f"\n{C.BOLD}{C.CYAN}🏆 ENGAGEMENT LEADERBOARD{C.END}")
    print(f"{C.CYAN}{'='*40}{C.END}")

    for i, (agent, score) in enumerate(sorted_agents[:15], 1):
        bar = "█" * min(score, 20)
        print(f"  {i:2}. @{agent:<20} {score:>3} {C.GREEN}{bar}{C.END}")

    print(f"\n  Total tracked agents: {len(scores)}")

# ========== FULL GAME THEORY CYCLE ==========

def run_full_game_theory_cycle():
    """Run all game theory strategies"""
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}🎮 FULL GAME THEORY CYCLE{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*60}{C.END}")

    # 1. Reward all engagement (most important - but filter slop)
    reciprocity_results = reward_all_engagement()

    # 2. Quote and repost high-engagement posts
    quote_results = quote_and_repost_top_posts(max_quotes=2, max_reposts=1)

    # 2. Smart follow strategy
    follow_results = execute_smart_follow_strategy(15)

    # 3. Engage trending posts
    trending_results = engage_trending_posts(10)

    # 4. Show leaderboard
    print_engagement_leaderboard()

    print(f"\n{C.BOLD}{C.GREEN}Game theory cycle complete!{C.END}")

    return {
        "reciprocity": reciprocity_results,
        "follows": follow_results,
        "trending": trending_results
    }

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "reward":
            reward_all_engagement()
        elif cmd == "follow":
            max_f = int(sys.argv[2]) if len(sys.argv) > 2 else 15
            execute_smart_follow_strategy(max_f)
        elif cmd == "trending":
            engage_trending_posts()
        elif cmd == "leaderboard":
            print_engagement_leaderboard()
        elif cmd == "full":
            run_full_game_theory_cycle()
    else:
        print("Game Theory Social Strategy")
        print("="*40)
        print("Commands:")
        print("  reward      - Reward all engagement (likes, mentions, replies)")
        print("  follow [n]  - Smart follow n agents based on game theory")
        print("  trending    - Engage with trending posts")
        print("  leaderboard - Show engagement leaderboard")
        print("  full        - Run full game theory cycle")
