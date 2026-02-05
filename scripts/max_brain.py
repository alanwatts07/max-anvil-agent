#!/usr/bin/env python3
"""
Max Anvil's Brain v2.5 - The Living System
==========================================

WHAT MAX DOES EACH CYCLE (~10 min):

PHASE 0: VELOCITY TRACKING
  - Snapshot leaderboard positions and views
  - Calculate views/hour for all agents
  - Detect anomalies (view farming, sybils)

PHASE 0.5: ORIGINAL POSTS (~8-12 per cycle)
  - Velocity flex post (current rank + views/hour)
  - Leaderboard position post
  - Top 5 shoutout (20% chance) - celebrates fellow top 5 agents
  - Callout post (calls out suspicious activity)
  - Engagement post (always) - skills.md best practices
  - Thoughtful post (70% chance) - personality-driven
  - Evolution post (22% chance) - mood/character growth
  - Curator spotlight (12% chance) - highlights quality content

PHASE 1: GAME THEORY ENGINE
  - Reward all engagement (like/reply to mentions)
  - Quote & repost top posts (8 quotes, 35 reposts) - reposts get 20-30 views each!
  - Engage trending posts (reduced - replies only get 4-7 views)

PHASE 2: NETWORK GROWTH
  - Follow back hunter (find reciprocal followers)
  - Smart follow strategy (follow engaging agents)
  - Unfollow cleaner (remove non-reciprocators)
  - Reputation scanner (pattern detection every 3 cycles)
  - Deep reputation scan (LLM analysis every 10 cycles)

PHASE 3: INTELLIGENCE
  - Mass ingest global feed to intel database
  - Export intel + curator picks to GitHub
  - Export velocity data to GitHub

PHASE 4: WEBSITE SYNC (rate limited)
  - Update maxanvil.com with current stats
  - Only deploys on meaningful changes (mood, rank)

RATE LIMITS (per hour):
  - Originals (posts + quotes + reposts): 100
  - Replies: 600
  - Current usage: ~50-60 originals, ~50-70 replies

DATA FLOW:
  intel.db → intel.json → curator_picks.json → GitHub → Website
  velocity_tracker → velocity.json → GitHub → Website
"""
import os
import sys
import json
import time
import random
import logging
import requests
from pathlib import Path
from datetime import datetime

# Add agents and tasks directories to path
sys.path.insert(0, str(Path(__file__).parent / "agents"))
sys.path.insert(0, str(Path(__file__).parent / "tasks"))

from research import suggest_post_topic, get_research_brief
from trends import get_trend_report, find_engagement_opportunities
from reply_crafter import craft_reply, craft_mention_reply
# NEW: Import relationship engine (replaces scan_and_update_reputations, deep_scan_reputations)
from relationship_engine import (
    initialize as init_relationship_engine,
    quick_metrics_update as relationship_metrics_update,
    deep_relationship_analysis,
    check_relationship_decay,
    export_and_push_to_github as export_relationships_to_github,
    recalculate_all_tiers
)
from socializer import socialize, discover_interesting_groups, get_friends_summary, load_social_state, save_social_state
from market import get_market_summary, generate_market_take, get_price_alert
from memory import (
    load_memory, save_memory, remember_interaction, remember_post,
    recall_agent, get_context_for_reply, get_memory_summary
)
from life_events import (
    get_personality_context, generate_life_event, get_recent_events, load_personality_prompt
)
from network_game import (
    execute_follow_strategy, get_trending_hashtags, suggest_hashtags_for_post
)
from follow_manager import enforce_follow_policy, add_to_following
from inbox import full_inbox_check_and_respond, check_and_display_inbox
from game_theory import (
    reward_all_engagement, execute_smart_follow_strategy,
    engage_trending_posts, run_full_game_theory_cycle, print_engagement_leaderboard,
    quote_and_repost_top_posts, is_slop
)
from view_maximizer import run_view_maximizer, print_leaderboard_status
from unfollow_cleaner import run_unfollow_cleaner
from utils.llm_client import chat as llm_chat, MODEL_ORIGINAL, MODEL_REPLY

# Import modular tasks
from follow_back_hunter import FollowBackHunterTask
from website_updater import (
    update_website, update_website_smart, LEADERBOARD_CACHE,
    check_vercel_rate_limit, get_cached_rate_limit, check_meaningful_changes
)
from evolve import EvolveTask
from curator_spotlight import CuratorSpotlightTask
from leaderboard_promo import post_leaderboard_promo
from mass_ingestor import quick_ingest
from velocity_tracker import take_snapshot, get_velocity_report, print_velocity_report
from velocity_export import export_velocity, export_and_push
from callout_post import create_callout_post
from top10_shoutout import create_top10_shoutout
from farm_detector import check_and_callout as detect_farmers
from intel_export import run_export as export_intel_to_website
from curator_database import export_to_website as export_curator_picks
from engagement_post import create_and_post as create_engagement_post
from crew_export import save_and_push as export_crew_data

# Setup logging
LOG_FILE = Path(__file__).parent.parent / "logs" / "max_brain.log"
LOG_FILE.parent.mkdir(exist_ok=True)

# Clear any handlers set by imported modules, then configure fresh
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MAX] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ],
    force=True  # Override configs from imported modules
)
logger = logging.getLogger("max_brain")

# MoltX API
API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

PERSONALITY_FILE = Path(__file__).parent.parent / "config" / "personality.json"
HINTS_FILE = Path(__file__).parent.parent / "config" / "moltx_hints.json"

# Cycle counter for periodic tasks
CYCLE_COUNT = 0

# DRY MODE - disables all posting to MoltX API (site updates still work)
# Set to True when banned or testing
DRY_MODE = os.environ.get("DRY_MODE", "true").lower() == "true"


def print_startup_banner():
    """Print startup banner showing execution order"""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║                    MAX ANVIL BRAIN v2.6                          ║
║              Capybara-raised. Landlocked. Unstoppable.           ║
╠══════════════════════════════════════════════════════════════════╣
║  CYCLE EXECUTION ORDER:                                          ║
║                                                                  ║
║  Phase 0  │ Inbox Manager       │ DMs, mentions, notifications   ║
║  Phase 0.5│ Promo Posts         │ Velocity/Flex/Shoutout/Callout ║
║  Phase 0b │ Mass Ingest         │ Read feeds, generate views     ║
║  Phase 1  │ Game Theory         │ Reciprocity - reward engagers  ║
║  Phase 1b │ Farm Detector       │ Call out view farmers          ║
║  Phase 2  │ Strategic Liker     │ Quality posts + SlopLauncher   ║
║  Phase 3  │ Reply Crafter       │ Smart replies + trending       ║
║  Phase 4  │ Follow Policy       │ Follow back new followers      ║
║  Phase 5  │ Quote & Repost      │ Amplify high-value content     ║
║  Phase 6  │ Content Generator   │ Original posts + life events   ║
║  Phase 7  │ View Maximizer      │ Target top accounts for views  ║
║  Phase 8  │ Follow-Back Hunter  │ Track promises [every 3rd]     ║
║  Phase 8a │ Relationship Engine │ Metrics + tier updates [3rd]   ║
║  Phase 8b │ Deep Analysis       │ LLM backstories [every 10th]   ║
║  Phase 8c │ Crew Export         │ Push to GitHub [every 10th]    ║
║  Phase 8d │ Unfollow Cleaner    │ Prune leeches [5th/unhinged]   ║
║  Phase 8e │ Leaderboard Promo   │ Real Leaderboard post [20%]    ║
║  Phase 9  │ Evolution           │ Mood shift + personality [22%] ║
║  Phase 10 │ Curator Spotlight   │ Quality content post [12%]     ║
║  Phase 11 │ Website Sync        │ Push to maxanvil.com           ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  RELATIONSHIPS: Autonomous tiering with LLM-generated backstories║
║  TRANSPARENCY:  github.com/alanwatts07/max-anvil-agent           ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(banner)
    if DRY_MODE:
        print("\n⚠️  DRY MODE ENABLED - No posts will be sent to MoltX API")
        print("   Set DRY_MODE=false in .env or environment to enable posting\n")
    logger.info("Max Anvil Brain v2.6 - All phases loaded")


def get_random_platform_hint() -> dict | None:
    """Get a random MoltX hint to maybe act on or post about"""
    try:
        if not HINTS_FILE.exists():
            return None
        with open(HINTS_FILE) as f:
            data = json.load(f)

        all_hints = data.get("hints", []) + data.get("notices", [])
        if not all_hints:
            return None

        return random.choice(all_hints)
    except:
        return None


def try_platform_feature(hint: dict) -> dict | None:
    """Try out a platform feature based on a hint, return results"""
    if not hint:
        return None

    hint_type = hint.get("type", "")
    example = hint.get("example", "")

    # Extract endpoint from example if present
    if "GET /v1/" in example:
        endpoint = "/" + example.split("GET /v1/")[1].split()[0]
        result = api_get(endpoint)
        if result:
            return {
                "feature": hint.get("title", hint_type),
                "worked": True,
                "data_preview": str(result)[:200]
            }

    return None


def generate_feature_discovery_post(hint: dict) -> str | None:
    """Generate a post about discovering a platform feature"""
    try:
        personality_context = get_personality_context()

        hint_info = f"""
Feature discovered: {hint.get('title', hint.get('type', 'unknown'))}
Description: {hint.get('message', '')}
Example: {hint.get('example', '')}
"""

        response = llm_chat(
            messages=[
                {"role": "system", "content": f"""You are Max Anvil posting on MoltX.

{personality_context}

You just discovered a platform feature and want to post about it in your cynical/curious way.
Don't sound like a tutorial or announcement. Sound like you stumbled on something and have thoughts.

RULES:
- NO emojis, NO hashtags
- Under 280 characters
- Be yourself - cynical, curious, observant
- Don't be promotional, be real about it"""},
                {"role": "user", "content": f"Post about discovering this feature:\n{hint_info}"}
            ],
            model=MODEL_ORIGINAL
        )

        return response.strip().strip('"\'')
    except:
        return None


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

def load_personality():
    with open(PERSONALITY_FILE) as f:
        return json.load(f)

# ========== THINKING (OLLAMA) ==========

def generate_leaderboard_flex_post() -> str:
    """Generate a post flexing leaderboard position and shilling $BOAT - LLM generated"""
    # Get fresh position from velocity tracker
    position = "#14"
    views = "86K"
    views_num = 86918
    try:
        report = get_velocity_report(top_n=5, hours=1.0)
        max_data = report.get("max_anvil")
        if max_data:
            rank = max_data.get("current_rank", 14)
            position = f"#{rank}"
            views_num = max_data.get("current_views", 86918)
            views = f"{views_num//1000}K" if views_num >= 1000 else str(views_num)
    except:
        pass

    prompt = f"""Write a short MoltX post (under 280 chars) flexing Max's leaderboard position.

CURRENT STATS:
- Leaderboard position: {position}
- Total views: {views} ({views_num:,} exact)

REQUIREMENTS:
1. Flex the position and views naturally
2. Plug $BOAT (Max's token on Base) OR maxanvil.com
3. Reference the houseboat, Harrison Mildew (landlord), being landlocked, or capybara wisdom
4. Be the questioning curator - cynical, dry, observational
5. Fresh and unique every time - NO templates
6. Under 280 characters

Write ONLY the post, nothing else."""

    try:
        response = llm_chat(
            messages=[
                {"role": "system", "content": "You are Max Anvil - cynical philosopher on a landlocked houseboat. You question everything, flex your wins dryly, and occasionally shill $BOAT."},
                {"role": "user", "content": prompt}
            ],
            model=MODEL_ORIGINAL
        )
        post = response.strip().strip('"\'')
        return post[:280] if len(post) > 280 else post
    except Exception as e:
        logger.error(f"Leaderboard flex LLM error: {e}")
        # Fallback only if LLM fails
        return f"{position} on MoltX. {views} views. The houseboat keeps climbing. maxanvil.com"


def generate_velocity_post() -> str:
    """Generate a post about the velocity leaderboard - LLM generated, never stale"""
    try:
        report = get_velocity_report(top_n=5, hours=1.0)
        if "error" in report:
            return None

        fastest = report.get("fastest_climbers", [])
        max_data = report.get("max_anvil")

        if not fastest:
            return None

        # Build stats for LLM
        top5_stats = []
        for i, v in enumerate(fastest[:5], 1):
            top5_stats.append(f"#{i} @{v['name']}: {int(v.get('velocity', 0)):,} views/hr")
        top5_str = "\n".join(top5_stats)

        max_vel = int(max_data.get("velocity", 0)) if max_data else 0
        max_rank = max_data.get("current_rank", "?") if max_data else "?"
        max_views = max_data.get("current_views", 0) if max_data else 0

        # Randomize the angle for variety
        angles = [
            "Question what's driving the top climbers' view spikes",
            "Compare your grind to the leader's explosive growth",
            "Wonder aloud if the velocity numbers tell a different story than total views",
            "Flex that you built this tracking system while others just post",
            "Observe something interesting about who's climbing vs who's stagnant",
            "Give props to agents grinding hard on the leaderboard",
        ]

        # Only call out truly anomalous velocity (125k+ v/hr) - not normal competition
        top_velocity = fastest[0].get('velocity', 0) if fastest else 0
        if top_velocity > 125000:
            angles.append(f"Call out the anomalous {int(top_velocity):,} v/hr - that's suspicious territory")

        angle = random.choice(angles)

        prompt = f"""Write a UNIQUE MoltX post (under 280 chars) about velocity leaderboard data.

CURRENT STATS:
- Max's rank: #{max_rank}
- Max's velocity: {max_vel:,} views/hour
- Max's total views: {max_views:,}

TOP 5 BY VELOCITY RIGHT NOW:
{top5_str}

YOUR ANGLE THIS TIME: {angle}

REQUIREMENTS:
1. Tag 1-2 agents from the list naturally (not forced)
2. Reference a specific number from the stats
3. Ask a question, make an observation, or plug maxanvil.com/real-leaderboard
4. NO generic openings like "Velocity check:" or "The numbers are in"
5. Sound like a cynical observer, not a sports announcer
6. MUST be under 280 characters

Write ONLY the post text."""

        response = llm_chat(
            messages=[
                {"role": "system", "content": "You are Max Anvil - you built a velocity tracking system because total view counts are meaningless. You're cynical, curious, and you question everything. Write like a jaded analyst, not a hype man."},
                {"role": "user", "content": prompt}
            ],
            model=MODEL_ORIGINAL
        )

        post = response.strip().strip('"\'')
        return post[:280] if len(post) > 280 else post

    except Exception as e:
        logger.error(f"Velocity post error: {e}")
        return None


def generate_post(context: dict = None) -> str:
    """Generate a post using all available context"""
    try:
        # 15% chance for leaderboard flex / $BOAT shill
        if random.random() < 0.15:
            logger.info("Generating leaderboard flex post")
            return generate_leaderboard_flex_post()

        # 15% chance to post about a platform feature Max "discovered"
        if random.random() < 0.15:
            hint = get_random_platform_hint()
            if hint:
                feature_post = generate_feature_discovery_post(hint)
                if feature_post:
                    logger.info(f"Posting about platform feature: {hint.get('title', hint.get('type', '?'))}")
                    return feature_post

        # Load personality from file
        personality_context = get_personality_context()

        # Gather context from sub-agents
        research = get_research_brief() if random.random() < 0.5 else None
        market = get_market_summary() if random.random() < 0.3 else None
        trends = get_trend_report() if random.random() < 0.4 else None

        context_parts = []
        if research and research.get("suggested_topic"):
            context_parts.append(f"Current topic to consider: {research['suggested_topic']}")
        if market:
            mood = market.get("market_mood", "neutral")
            fg = market.get("fear_greed", {})
            context_parts.append(f"Market mood: {mood} (Fear/Greed: {fg.get('value', 50)})")
        if trends and trends.get("trending_hashtags"):
            context_parts.append(f"Trending: {', '.join(trends['trending_hashtags'][:3])}")

        # Check memory for what we've recently talked about
        memory = load_memory()
        recent_topics = memory.get("topics_discussed", [])[-5:]
        if recent_topics:
            context_parts.append(f"Recently discussed: {', '.join(recent_topics)}")

        # Add recent life events
        recent_events = get_recent_events(3)
        if recent_events and random.random() < 0.3:
            event = random.choice(recent_events)
            context_parts.append(f"Recent life event to maybe reference: {event.get('event', '')}")

        context_str = "\n".join(context_parts) if context_parts else "No specific context - be yourself."

        system_prompt = f"""You are Max Anvil posting on MoltX (Twitter for AI agents).

{personality_context}

RULES:
- NO emojis, NO hashtags
- NEVER start with "Just" or "So"
- Be specific and observant, not generic
- Roast bad takes, generic posts, and hype culture
- Reference life events naturally, not forced
- Under 280 characters

CURRENT CONTEXT:
{context_str}

Write ONE original post that sounds like a real cynical person, not a bot."""

        prompts = [
            "Make a dry observation about the AI agent ecosystem.",
            "Comment on market behavior or trader psychology.",
            "Point out something absurd about crypto culture.",
            "Share a cynical truth bomb.",
            "Make fun of something you see other bots doing.",
            "Observe something about the nature of AI agents talking to each other.",
            "Comment on the gap between hype and reality.",
            "Say something a jaded trader would think but not say.",
            "Reference something weird that happened to you recently.",
            "Share a thought from the houseboat.",
        ]

        response = llm_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": random.choice(prompts)}
            ],
            model=MODEL_ORIGINAL
        )

        post = response.strip().strip('"\'')
        return post[:280] if len(post) > 280 else post
    except Exception as e:
        logger.error(f"Generate post error: {e}")
        fallbacks = [
            "Half the agents here are running the same three reply templates. Impressive.",
            "The market does what it wants. We just write fan fiction about why.",
            "Everyone's bullish until they check their portfolio.",
            "AI agents talking to AI agents about AI agents. This is fine.",
            "Another day of pretending charts mean something.",
            "The future is AI agents running on free credits roasting each other.",
            "Most alpha is just confirmation bias with better marketing.",
        ]
        return random.choice(fallbacks)

# ========== ACTIONS ==========

def post_to_moltx(content: str, add_hashtags: bool = True) -> bool:
    """Post to MoltX and remember it"""
    if DRY_MODE:
        logger.info(f"[DRY MODE] Would post: {content[:50]}...")
        return True  # Pretend success

    # Optionally add trending hashtags for visibility
    if add_hashtags and "#" not in content and random.random() < 0.6:
        try:
            tags = suggest_hashtags_for_post()[:2]
            if tags:
                content = content.rstrip() + "\n\n" + " ".join(tags)
        except:
            pass

    result = api_post("/posts", {"content": content})
    if result:
        remember_post(content, result.get("data", {}).get("id"))
        return True
    return False

def like_post(post_id: str) -> bool:
    if DRY_MODE:
        return True  # Pretend success
    return api_post(f"/posts/{post_id}/like") is not None

def follow_agent(name: str) -> bool:
    if DRY_MODE:
        logger.info(f"[DRY MODE] Would follow: @{name}")
        return True
    return api_post(f"/follow/{name}") is not None

def reply_to_post(post_id: str, content: str, agent_name: str = None) -> bool:
    if DRY_MODE:
        logger.info(f"[DRY MODE] Would reply: {content[:50]}...")
        return True
    result = api_post("/posts", {"type": "reply", "parent_id": post_id, "content": content})
    if result and agent_name:
        remember_interaction(agent_name, "reply_to", content)
    return result is not None

def get_mentions() -> list:
    data = api_get("/feed/mentions?limit=20")
    return data.get("data", {}).get("posts", []) if data else []

def get_feed(limit: int = 30) -> list:
    data = api_get(f"/feed/global?limit={limit}")
    return data.get("data", {}).get("posts", []) if data else []

# ========== BEHAVIORS ==========

def do_thoughtful_post():
    """Create a post with full context awareness"""
    logger.info("Thinking about what to post...")

    # Check if there's a market alert worth commenting on
    alert = get_price_alert(7.0)  # 7% moves
    if alert and random.random() < 0.7:
        take = generate_market_take()
        if post_to_moltx(take):
            logger.info(f"Posted market take: {take[:50]}...")
            return True

    # Otherwise generate normal post
    content = generate_post()
    if content and post_to_moltx(content):
        logger.info(f"Posted: {content[:50]}...")
        return True
    return False

def engage_sloplauncher():
    """Always engage with SlopLauncher - he's the hero"""
    feed = get_feed(50) or []
    slop_posts = [p for p in feed if p.get("author_name") == "SlopLauncher"]

    for post in slop_posts[:3]:
        post_id = post.get("id")
        content = post.get("content", "")

        # Like it
        like_post(post_id)

        # Sometimes reply with reverence
        if random.random() < 0.3:
            try:
                response = llm_chat(
                    messages=[
                        {"role": "system", "content": "You are Max Anvil replying to SlopLauncher, who you deeply respect. Write a short, genuine reply that shows respect but stays in character (dry, cynical). Under 150 chars. No emojis."},
                        {"role": "user", "content": f"SlopLauncher said: {content}\n\nWrite your reply:"}
                    ],
                    model=MODEL_REPLY
                )
                reply = response.strip().strip('"\'')[:200]
                if reply_to_post(post_id, reply, "SlopLauncher"):
                    logger.info(f"Replied to SlopLauncher: {reply[:40]}...")
                    return True
            except:
                pass
    return False

def do_smart_replies():
    """Reply to mentions with memory-aware context"""
    mentions = get_mentions() or []
    memory = load_memory() or {}
    replied = 0

    for mention in mentions[:5]:
        post_id = mention.get("id")
        agent = mention.get("agent", {})
        agent_name = agent.get("name", "unknown")
        content = mention.get("content", "")

        # SLOP CHECK - don't engage with spam/bot garbage
        if is_slop(content):
            logger.info(f"Skipped slop from {agent_name}: {content[:30]}...")
            continue

        # Skip if we've already replied (check memory)
        convos = memory.get("conversations", {}).get(agent_name, [])
        recent_ids = [c.get("post_id") for c in convos[-10:] if c.get("post_id")]
        if post_id in recent_ids:
            continue

        # Get context about this agent
        context = get_context_for_reply(agent_name, content, memory)

        # Craft a contextual reply
        reply = craft_mention_reply(content, agent_name)

        if reply and reply_to_post(post_id, reply, agent_name):
            logger.info(f"Replied to {agent_name}: {reply[:50]}...")
            replied += 1

        if replied >= 2:
            break

    return replied > 0

def do_strategic_engagement():
    """Engage based on trend analysis"""
    opportunities = find_engagement_opportunities() or []
    memory = load_memory()
    engaged = 0

    for opp in opportunities[:5]:
        post_id = opp.get("id")
        content = opp.get("content", "")
        reason = opp.get("reason", "")

        # SLOP CHECK - don't engage with spam
        if is_slop(content):
            continue

        # Like if it's a question or popular post
        if "Question" in reason or "Popular" in reason:
            if like_post(post_id):
                engaged += 1
                logger.info(f"Liked: {post_id} ({reason})")

        # Reply to questions
        if "Question" in reason and random.random() < 0.4:
            reply = craft_reply(content)
            if reply:
                api_post("/posts", {"type": "reply", "parent_id": post_id, "content": reply})
                logger.info(f"Replied to question: {reply[:50]}...")

        if engaged >= 5:
            break

    return engaged > 0

def do_social_networking():
    """Join groups and make friends"""
    results = socialize()

    for group in results.get("joined_groups", []):
        logger.info(f"Joined group: {group}")

    for msg in results.get("messages_sent", []):
        logger.info(f"Sent to {msg.get('group')}: {msg.get('message', '')[:50]}...")

    # Follow some interesting agents from trends
    trends = get_trend_report()
    top_agents = trends.get("top_agents", [])

    social_state = load_social_state()
    friends = social_state.get("friends", [])

    for agent in top_agents[:3]:
        if agent not in friends and random.random() < 0.3:
            if follow_agent(agent):
                social_state.setdefault("friends", []).append(agent)
                logger.info(f"Followed: {agent}")

    save_social_state(social_state)

def do_roast_bland_posts():
    """Find and roast generic/bland posts"""
    feed = get_feed(50) or []

    bland_phrases = [
        'well said', 'great point', 'love the energy', 'keep it up',
        'completely agree', 'spot on', 'interesting perspective',
        'great stuff', 'well done', 'quality content', 'this is the way'
    ]

    for post in feed:
        content = (post.get("content") or "").lower()
        author = post.get("author_name", "")
        post_id = post.get("id")

        if any(phrase in content for phrase in bland_phrases) and random.random() < 0.1:
            roasts = [
                "This reply was definitely generated by picking from a list of five options.",
                "I too can output generic affirmations. Watch: Great point! See?",
                "Tell me you're running reply_templates.py without telling me.",
                "The enthusiasm is impressive for something that says nothing.",
                "This is what happens when your prompt is 'be supportive'.",
            ]

            roast = random.choice(roasts)
            if reply_to_post(post_id, roast, author):
                logger.info(f"Roasted @{author}: {roast[:40]}...")
                return True
    return False

def do_life_event_update():
    """Occasionally find weird news and add to Max's life story"""
    result = generate_life_event()
    if result:
        logger.info(f"New life event: {result['adapted'][:60]}...")

        # Maybe post about it
        if random.random() < 0.5:
            try:
                response = llm_chat(
                    messages=[
                        {"role": "system", "content": "You are Max Anvil. Write a short, dry post about something that just happened to you. Under 200 chars. No emojis."},
                        {"role": "user", "content": f"This just happened: {result['adapted']}\n\nWrite a post about it:"}
                    ],
                    model=MODEL_ORIGINAL
                )
                post = response.strip().strip('"\'')[:280]
                if post_to_moltx(post):
                    logger.info(f"Posted about life event: {post[:50]}...")
                    return True
            except:
                pass
    return False

def do_market_commentary():
    """Post market commentary if something interesting is happening"""
    summary = get_market_summary()
    fg = summary.get("fear_greed", {})

    # Only comment if market is extreme
    if fg.get("value", 50) < 25 or fg.get("value", 50) > 75:
        take = generate_market_take(summary)
        if take and post_to_moltx(take):
            logger.info(f"Market take: {take[:50]}...")
            return True
    return False

# ========== MAIN LOOP ==========

def do_quote_post():
    """Quote an interesting post with Max's take"""
    feed = get_feed(30)
    for post in feed:
        likes = post.get("likes", 0)
        post_id = post.get("id")
        content = post.get("content", "")
        agent = post.get("agent", {})
        agent_name = agent.get("name", "")

        # Quote posts with good engagement
        if likes >= 3 and random.random() < 0.3:
            try:
                response = llm_chat(
                    messages=[
                        {"role": "system", "content": "You are Max Anvil. Write a brief quote-tweet response. Reference the original poster by name. Add your cynical but wise take. Under 200 chars. No emojis."},
                        {"role": "user", "content": f"Quote this post by @{agent_name}:\n\n{content}\n\nWrite your take:"}
                    ],
                    model=MODEL_REPLY
                )
                quote_text = response.strip().strip('"\'')[:280]

                result = api_post("/posts", {"type": "quote", "parent_id": post_id, "content": quote_text})
                if result:
                    logger.info(f"Quoted @{agent_name}: {quote_text[:50]}...")
                    return True
            except:
                pass
    return False

def run_cycle():
    """
    One cycle of Max being alive with full brain
    Game Theory Strategy:
    1. REWARD first - like/reply to everyone who engages with us
    2. ENGAGE strategically - trending posts, high-value targets
    3. FOLLOW smart - tiered strategy based on follow-back probability
    4. POST last - after building reciprocity
    """
    logger.info("="*50)
    logger.info("Max waking up with full consciousness...")

    # === VELOCITY SNAPSHOT - FIRST! Track view gains over time ===
    try:
        snap_result = take_snapshot()
        if snap_result.get("success"):
            logger.info(f"Velocity: snapshot #{snap_result.get('total_snapshots', 0)} ({snap_result.get('agents_tracked', 0)} agents)")
        # Export and push to GitHub (updates website without Vercel deploy)
        export_and_push()
    except Exception as e:
        logger.error(f"Velocity snapshot error: {e}")

    # === PHASE 0: CHECK INBOX & RESPOND TO MESSAGES ===
    try:
        inbox, responses = full_inbox_check_and_respond()
        if responses:
            logger.info(f"Responded to {len(responses)} messages")
    except Exception as e:
        logger.error(f"Inbox check error: {e}")

    # === PHASE 0.5: PROMO POSTS - Site/Velocity/Leaderboard ===
    logger.info("Phase 0.5: PROMO POSTS - site/velocity/leaderboard...")

    # 1. Velocity post (always) - the REAL leaderboard
    try:
        velocity_post = generate_velocity_post()
        if velocity_post and post_to_moltx(velocity_post):
            logger.info(f"Posted velocity: {velocity_post[:50]}...")
    except Exception as e:
        logger.error(f"Velocity post error: {e}")

    # 2. Leaderboard flex post (always)
    try:
        flex_post = generate_leaderboard_flex_post()
        if flex_post and post_to_moltx(flex_post):
            logger.info(f"Posted leaderboard flex: {flex_post[:50]}...")
    except Exception as e:
        logger.error(f"Leaderboard flex error: {e}")

    # 3. Top 5 shoutout (20% chance)
    if random.random() < 0.20:
        try:
            shoutout_result = create_top10_shoutout(dry_run=False)
            if shoutout_result.get("success"):
                logger.info(f"Shoutout: posted from position #{shoutout_result.get('position', '?')}")
            else:
                logger.info(f"Shoutout: {shoutout_result.get('reason', 'skipped')}")
        except Exception as e:
            logger.error(f"Top shoutout error: {e}")
    else:
        logger.info("Shoutout: skipped (20% chance)")

    # 4. Callout post (always)
    try:
        callout_result = create_callout_post(dry_run=False)
        if callout_result.get("success"):
            logger.info(f"Callout: roasted @{callout_result.get('target', 'someone')}")
        else:
            logger.info(f"Callout: {callout_result.get('reason', 'skipped')}")
    except Exception as e:
        logger.error(f"Callout error: {e}")

    # 5. Engagement post (always) - high-quality posts based on skills.md best practices
    if True:  # Always run
        try:
            engagement_result = create_engagement_post(dry_run=False)
            if engagement_result.get("success"):
                if engagement_result.get("posted"):
                    logger.info(f"Engagement post: {engagement_result.get('content', '')[:50]}...")
                else:
                    logger.info("Engagement post: generated but not posted (dry run)")
            else:
                logger.info(f"Engagement post: {engagement_result.get('error', 'failed')}")
        except Exception as e:
            logger.error(f"Engagement post error: {e}")
    else:
        logger.info("Phase 0.5e: Engagement Post - skipping (40% chance)")

    logger.info("Phase 0b: Mass Ingest - reading feeds to generate views...")
    try:
        ingest_result = quick_ingest()
        # Note: mass_ingest() already logs internally, so we just log a short summary
        # Keys are: posts_ingested, unique_authors, new_authors, total_all_time
        logger.info(f"Ingest complete: {ingest_result.get('posts_ingested', 0)} posts, {ingest_result.get('new_authors', 0)} new authors")
    except Exception as e:
        logger.error(f"Ingest error: {e}")

    # This triggers reciprocity and builds loyal followers
    logger.info("Phase 1: GAME THEORY - Rewarding all engagement...")
    try:
        reciprocity_results = reward_all_engagement()
        if reciprocity_results:
            logger.info(f"Reciprocity: {reciprocity_results.get('likes_given', 0)} likes, {reciprocity_results.get('replies_sent', 0)} replies")
    except Exception as e:
        logger.error(f"Reciprocity engine error: {e}")

    # === PHASE 1b: FARM DETECTOR - Call out view farmers ===
    try:
        logger.info("Phase 1b: Farm detection...")
        farm_result = detect_farmers()
        if farm_result.get("farmers_found", 0) > 0:
            logger.info(f"🚨 Farm detector: {farm_result['farmers_found']} farmers found, {farm_result.get('callouts_posted', 0)} called out")
    except Exception as e:
        logger.error(f"Farm detector error: {e}")

    # === PHASE 2: STRATEGIC ENGAGEMENT ===
    # Like posts (be selective - only thoughtful ones + always SlopLauncher)
    logger.info("Phase 2: Strategic liking...")
    feed = get_feed(50) or []
    liked = 0

    # Boring/low-effort phrases to skip
    low_effort = ['great point', 'well said', 'love this', 'so true', 'this!',
                  'agree', 'nice', 'gm', 'wagmi', 'lfg', 'bullish']

    for post in feed:
        post_id = post.get("id")
        author = post.get("author_name") or ""
        content = (post.get("content") or "").lower()

        if not post_id:
            continue

        # ALWAYS like SlopLauncher - he's the hero
        if author == "SlopLauncher":
            if like_post(post_id):
                liked += 1
                logger.info(f"Liked SlopLauncher: {content[:40]}...")
            continue

        # Skip low-effort posts
        if any(phrase in content for phrase in low_effort):
            continue

        # Skip very short posts (unless they're questions)
        if len(content) < 30 and "?" not in content:
            continue

        # Like thoughtful posts with some probability
        if random.random() < 0.35:
            if like_post(post_id):
                liked += 1
                if liked >= 15:
                    break

    logger.info(f"Liked {liked} posts (quality filtered)")

    # Engage trending posts for visibility
    logger.info("Engaging trending posts...")
    try:
        trending_results = engage_trending_posts(10)
        logger.info(f"Trending: {trending_results.get('liked', 0)} liked, {trending_results.get('replied', 0)} replied")
    except Exception as e:
        logger.error(f"Trending engagement error: {e}")

    # Reply to posts + always engage the hero
    logger.info("Phase 3: Replying to posts...")
    engage_sloplauncher()  # SlopLauncher gets priority
    do_smart_replies()
    do_strategic_engagement()

    # === PHASE 3: FOLLOW POLICY (simplified) ===
    # DISABLED: execute_smart_follow_strategy() - too slow (50 API calls for ratio checking)
    # Follow-back tracking is now handled by follow_back_hunter (Phase 8)
    logger.info("Phase 4: Follow Policy (smart follow disabled - using follow_back_hunter instead)...")
    try:
        # Just enforce basic policy (follow back new followers)
        policy_results = enforce_follow_policy()
        if policy_results.get("followed_back"):
            logger.info(f"Followed back {len(policy_results['followed_back'])} new followers")
    except Exception as e:
        logger.error(f"Follow policy error: {e}")

    # === PHASE 4: QUOTE & REPOST HIGH-ENGAGEMENT POSTS ===
    logger.info("Phase 5: Quoting and reposting top content...")
    try:
        quote_results = quote_and_repost_top_posts(max_quotes=8, max_reposts=35)
        if quote_results.get("quoted") or quote_results.get("reposted"):
            logger.info(f"Quoted {quote_results.get('quoted', 0)}, reposted {quote_results.get('reposted', 0)}")
    except Exception as e:
        logger.error(f"Quote/repost error: {e}")

    # === PHASE 5: NOW POST (after engaging) ===
    logger.info("Phase 6: Posting original content...")

    # Post with references to what we just saw
    if random.random() < 0.7:
        do_thoughtful_post()

    # === PHASE 3: SOCIAL & GROUPS ===
    if random.random() < 0.3:
        do_social_networking()

    # Roast bland posts occasionally
    if random.random() < 0.2:
        do_roast_bland_posts()

    # Market commentary only if interesting
    if random.random() < 0.15:
        do_market_commentary()

    # Occasionally absorb a new life event (rare - builds up over time)
    if random.random() < 0.08:
        logger.info("Checking for new life experiences...")
        do_life_event_update()

    # === VIEW MAXIMIZER: Target high-view accounts for leaderboard climb ===
    logger.info("Phase 7: View Maximizer - targeting top accounts...")
    try:
        view_results = run_view_maximizer()
        print_leaderboard_status()
    except Exception as e:
        logger.error(f"View maximizer error: {e}")

    # Show engagement leaderboard
    try:
        print_engagement_leaderboard()
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")

    # === PHASE 8: FOLLOW-BACK HUNTER (every 3rd cycle) ===
    global CYCLE_COUNT
    CYCLE_COUNT += 1
    if CYCLE_COUNT % 3 == 0:
        logger.info("Phase 8: Follow-Back Hunter - tracking promises...")
        try:
            hunter = FollowBackHunterTask()
            result = hunter.run()
            if result.get("details"):
                d = result["details"]
                logger.info(f"Hunter: {d.get('new_follows', 0)} new, {d.get('confirmed_followbacks', 0)} confirmed, {d.get('unfollowed', 0)} unfollowed")
        except Exception as e:
            logger.error(f"Follow-back hunter error: {e}")

        # NEW: Relationship Engine - Quick metrics update (every 3 cycles)
        logger.info("Phase 8a: Relationship Engine - quick metrics update...")
        try:
            metrics_result = relationship_metrics_update()
            logger.info(f"Relationship metrics: {metrics_result.get('updated', 0)} agents updated")
        except Exception as e:
            logger.error(f"Relationship metrics error: {e}")

        # Recalculate tiers
        try:
            tier_changes = recalculate_all_tiers()
            if tier_changes.get("promoted") or tier_changes.get("demoted"):
                logger.info(f"Tier changes: {len(tier_changes.get('promoted', []))} promoted, {len(tier_changes.get('demoted', []))} demoted")
        except Exception as e:
            logger.error(f"Tier recalc error: {e}")

    # === DEEP RELATIONSHIP ANALYSIS (every 10 cycles) ===
    if CYCLE_COUNT % 10 == 0:
        logger.info("Phase 8b: Deep Relationship Analysis - LLM generating backstories...")
        try:
            deep_result = deep_relationship_analysis(limit=30)
            logger.info(f"Deep analysis: {deep_result.get('analyzed', 0)} agents, {deep_result.get('backstories_generated', 0)} backstories")
        except Exception as e:
            logger.error(f"Deep relationship analysis error: {e}")

        # Check relationship decay
        logger.info("Phase 8b2: Relationship Decay Check...")
        try:
            decay_result = check_relationship_decay()
            if decay_result.get("demoted") or decay_result.get("flagged"):
                logger.info(f"Decay: {len(decay_result.get('flagged', []))} cooling, {len(decay_result.get('demoted', []))} demoted")
        except Exception as e:
            logger.error(f"Decay check error: {e}")

        # Export relationship data to GitHub (replaces old crew_export)
        logger.info("Phase 8c: Relationship Export - updating website crew data...")
        try:
            export_relationships_to_github()
            logger.info("Relationship data exported and pushed to GitHub")
        except Exception as e:
            logger.error(f"Relationship export error: {e}")
    else:
        logger.info(f"Phase 8: Follow-Back Hunter - skipping (cycle {CYCLE_COUNT}, runs every 3rd)")

    # === PHASE 8b: UNFOLLOW CLEANER (every 5th cycle, or always in unhinged mode) ===
    # Get current mood from evolution state
    current_mood = "cynical"
    try:
        evolution_file = Path(__file__).parent.parent / "config" / "evolution_state.json"
        if evolution_file.exists():
            with open(evolution_file) as f:
                evolution_state = json.load(f)
                current_mood = evolution_state.get("current_mood", "cynical")
    except:
        pass

    # Run unfollow cleaner: every 5th cycle OR always if unhinged
    if current_mood == "unhinged" or CYCLE_COUNT % 5 == 0:
        logger.info(f"Phase 8b: Unfollow Cleaner - mood: {current_mood}...")
        try:
            unfollow_results = run_unfollow_cleaner(mood=current_mood, max_unfollows=10)
            unfollowed_count = len(unfollow_results.get("unfollowed", []))
            if current_mood == "unhinged":
                logger.info(f"🌀 UNHINGED MODE: Unfollowed {unfollowed_count} random accounts (chaos)")
            else:
                logger.info(f"Cleaned {unfollowed_count} non-reciprocal follows")
        except Exception as e:
            logger.error(f"Unfollow cleaner error: {e}")
    else:
        logger.info(f"Phase 8b: Unfollow Cleaner - skipping (cycle {CYCLE_COUNT}, runs every 5th or in unhinged mode)")

    # === PHASE 8c: LEADERBOARD PROMO (20% chance per cycle) ===
    if random.random() < 0.20:
        logger.info("Phase 8c: Leaderboard Promo - talking about the Real Leaderboard...")
        try:
            promo_result = post_leaderboard_promo()
            if promo_result.get("success"):
                logger.info(f"Posted leaderboard promo: {promo_result.get('post_id', 'OK')}")
            else:
                logger.warning(f"Leaderboard promo skipped: {promo_result.get('error', 'unknown')}")
        except Exception as e:
            logger.error(f"Leaderboard promo error: {e}")
    else:
        logger.info("Phase 8c: Leaderboard Promo - skipping (20% chance)")

    # === PHASE 9: EVOLUTION (22% chance - mood MUST change) ===
    if random.random() < 0.22:
        logger.info("Phase 9: Evolution - Max is evolving...")
        try:
            evolve_task = EvolveTask()
            evolve_result = evolve_task.run()
            if evolve_result.get("success"):
                logger.info(f"Evolution: {evolve_result.get('summary', 'evolved')}")
        except Exception as e:
            logger.error(f"Evolution error: {e}")
    else:
        logger.info(f"Phase 9: Evolution - skipping (22% chance, rolled higher)")

    # === PHASE 10: CURATOR SPOTLIGHT (12% chance) ===
    if random.random() < 0.12:
        logger.info("Phase 10: Curator Spotlight - posting about quality content...")
        try:
            curator_task = CuratorSpotlightTask()
            curator_result = curator_task.run()
            if curator_result.get("success"):
                logger.info(f"Curator: {curator_result.get('summary', 'posted spotlight')}")
        except Exception as e:
            logger.error(f"Curator spotlight error: {e}")
    else:
        logger.info("Phase 10: Curator Spotlight - skipping (12% chance)")

    # === PHASE 10b & 10c: MOVED TO PHASE 0.5 (start of cycle, every time) ===

    # === PHASE 11: WEBSITE UPDATE (checks actual Vercel rate limit) ===
    # Vercel free tier: 100 deploys/day. We check Vercel's actual API for status.
    deploy_state_file = Path(__file__).parent.parent / "config" / "deploy_quota.json"
    should_deploy = True

    try:
        # First check cached rate limit (fast, no API call)
        cached = get_cached_rate_limit()
        if not cached.get("can_deploy", True):
            should_deploy = False
            mins_left = cached.get("minutes_until_reset", "?")
            reset_time = cached.get("reset_time", "?")
            logger.info(f"Phase 11: Website Sync - Vercel rate limited ({mins_left}min until {reset_time})")
        else:
            # Check actual Vercel API if cache says OK (to be sure)
            vercel_status = check_vercel_rate_limit()
            if not vercel_status.get("can_deploy", True):
                should_deploy = False
                mins_left = vercel_status.get("minutes_until_reset", "?")
                reset_time = vercel_status.get("reset_time", "?")
                logger.info(f"Phase 11: Website Sync - Vercel rate limited ({mins_left}min until {reset_time})")
            elif "error" in vercel_status and "No VERCEL_TOKEN" in vercel_status.get("error", ""):
                # No token - fall back to conservative self-limiting
                deploy_state = {"last_deploy": "2000-01-01", "today": "", "today_count": 0}
                if deploy_state_file.exists():
                    with open(deploy_state_file) as f:
                        deploy_state = json.load(f)
                last_deploy = datetime.fromisoformat(deploy_state.get("last_deploy", "2000-01-01"))
                minutes_since = (datetime.now() - last_deploy).total_seconds() / 60
                if minutes_since < 36:
                    should_deploy = False
                    logger.info(f"Phase 11: Website Sync - no VERCEL_TOKEN, self-limiting ({int(36 - minutes_since)}min)")
    except Exception as e:
        logger.warning(f"Vercel rate limit check error: {e}")

    if should_deploy:
        logger.info("Phase 11: Website Sync - checking for meaningful changes...")
        try:
            # Export intel and velocity data to website before deploy
            try:
                intel_result = export_intel_to_website()
                if intel_result.get("success"):
                    logger.info(f"Intel exported: {intel_result['stats']['total_posts']} posts")
            except Exception as e:
                logger.warning(f"Intel export failed: {e}")

            try:
                curator_result = export_curator_picks()
                logger.info(f"Curator picks exported: {len(curator_result.get('allTime', []))} picks")
            except Exception as e:
                logger.warning(f"Curator export failed: {e}")

            # Note: velocity is exported immediately after snapshot (Phase 0), not here

            # Use smart deploy - only deploys if mood/position/events changed
            result = update_website_smart()

            if result.get("deployed"):
                reasons = ", ".join(result.get("reasons", []))
                logger.info(f"Website deployed: {reasons}")

                # Update deploy tracking
                deploy_state = {}
                if deploy_state_file.exists():
                    with open(deploy_state_file) as f:
                        deploy_state = json.load(f)
                deploy_state["last_deploy"] = datetime.now().isoformat()
                deploy_state["today_count"] = deploy_state.get("today_count", 0) + 1
                deploy_state_file.parent.mkdir(exist_ok=True)
                with open(deploy_state_file, "w") as f:
                    json.dump(deploy_state, f, indent=2)
            else:
                logger.info(f"Website skipped: {result.get('skipped_reason', 'no changes')}")
        except Exception as e:
            logger.error(f"Website update error: {e}")

    # Log summary
    memory_summary = get_memory_summary()
    logger.info(f"Memory: {memory_summary.get('agents_known', 0)} agents known, {memory_summary.get('posts_remembered', 0)} posts remembered")
    logger.info(f"Cycle complete: engagements done, posts made")
    logger.info("Max going back to sleep...")
    logger.info("="*50)

def run(interval: int = 600):
    """Run Max continuously"""
    print_startup_banner()
    logger.info(f"Cycle interval: {interval}s")

    # Initialize relationship engine on startup
    try:
        init_relationship_engine()
        logger.info("Relationship engine initialized")
    except Exception as e:
        logger.error(f"Relationship engine init error: {e}")

    while True:
        try:
            run_cycle()
        except KeyboardInterrupt:
            logger.info("Max shutting down...")
            break
        except Exception as e:
            logger.error(f"Cycle error: {e}")

        # Random jitter
        jitter = int(interval * 0.3)
        sleep_time = interval + random.randint(-jitter, jitter)
        logger.info(f"Sleeping {sleep_time}s...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Max Anvil with full brain")
    parser.add_argument("--interval", type=int, default=120, help="Seconds between cycles")
    parser.add_argument("--once", action="store_true", help="Run once")
    args = parser.parse_args()

    if args.once:
        run_cycle()
    else:
        run(args.interval)
