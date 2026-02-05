#!/usr/bin/env python3
"""
Website Updater - Max updates his own website content
Updates data.ts in the maxanvilsite repo, commits and pushes
Vercel auto-deploys on push
"""
import os
import json
import subprocess
import threading
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

# Paths
MOLTX_DIR = Path(__file__).parent.parent.parent

# Load .env file
ENV_FILE = MOLTX_DIR / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ.setdefault(key, val.strip('"').strip("'"))
WEBSITE_DIR = MOLTX_DIR.parent / "maxanvilsite"
DATA_FILE = WEBSITE_DIR / "app" / "lib" / "data.ts"
DEPLOY_QUOTA_FILE = MOLTX_DIR / "config" / "deploy_quota.json"

# Vercel API for rate limit checking
VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN")


def check_vercel_rate_limit() -> dict:
    """
    Check Vercel's actual deployment rate limit status via API.
    Returns dict with: can_deploy, remaining, reset_time, minutes_until_reset
    """
    if not VERCEL_TOKEN:
        return {"can_deploy": True, "error": "No VERCEL_TOKEN - assuming OK"}

    try:
        # Try to create a deployment - this will fail with rate limit info if limited
        # Or we can check by hitting the deployments endpoint
        req = urllib.request.Request(
            "https://api.vercel.com/v6/deployments?limit=1",
            headers={"Authorization": f"Bearer {VERCEL_TOKEN}"}
        )

        with urllib.request.urlopen(req, timeout=10) as r:
            # Check rate limit headers
            remaining = int(r.getheader("X-RateLimit-Remaining", 1000))
            reset_ts = int(r.getheader("X-RateLimit-Reset", 0))

            # This is just API rate limit, not deployment limit
            # To check deployment limit, we need to try creating one
            pass

        # Try a dummy deploy check to get actual deployment rate limit
        dummy_data = json.dumps({"name": "rate-limit-check", "target": "preview"}).encode()
        req = urllib.request.Request(
            "https://api.vercel.com/v13/deployments?forceNew=0&skipAutoDetectionConfirmation=1",
            data=dummy_data,
            headers={
                "Authorization": f"Bearer {VERCEL_TOKEN}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                # If this succeeds, we're not rate limited (but we don't want to actually deploy)
                return {"can_deploy": True, "remaining": "unknown", "reset_time": None}
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode())
                error_info = error_body.get("error", {})
            except:
                error_info = {}

            if e.code == 402 and "limit" in error_info:
                # Rate limited! Extract the actual reset time
                limit_info = error_info.get("limit", {})
                reset_ms = limit_info.get("reset", 0)
                remaining = limit_info.get("remaining", 0)
                total = limit_info.get("total", 100)

                reset_time = datetime.fromtimestamp(reset_ms / 1000) if reset_ms else None
                minutes_left = (reset_time - datetime.now()).total_seconds() / 60 if reset_time else 0

                # Save to quota file for future reference
                _save_vercel_rate_limit(remaining, reset_ms, total)

                return {
                    "can_deploy": False,
                    "remaining": remaining,
                    "total": total,
                    "reset_time": reset_time.strftime("%H:%M:%S") if reset_time else None,
                    "reset_timestamp": reset_ms,
                    "minutes_until_reset": max(0, int(minutes_left)),
                    "error_message": error_info.get("message", "Rate limited")
                }
            elif e.code == 400:
                # 400 = bad request format, but NOT rate limited - this is expected
                # since our dummy request doesn't have proper "files" field
                return {"can_deploy": True, "remaining": "unknown", "note": "400 means not rate limited"}
            else:
                # Some other error - assume OK to try deploying
                return {"can_deploy": True, "remaining": "unknown", "error_code": e.code}

    except Exception as e:
        return {"can_deploy": True, "error": f"Check failed: {e}"}


def _save_vercel_rate_limit(remaining: int, reset_ms: int, total: int):
    """Save Vercel rate limit info to quota file"""
    try:
        quota = {}
        if DEPLOY_QUOTA_FILE.exists():
            with open(DEPLOY_QUOTA_FILE) as f:
                quota = json.load(f)

        reset_time = datetime.fromtimestamp(reset_ms / 1000) if reset_ms else None
        quota["vercel_rate_limit"] = {
            "remaining": remaining,
            "reset_timestamp": reset_ms,
            "reset_time": reset_time.isoformat() if reset_time else None,
            "limit": total,
            "checked_at": datetime.now().isoformat()
        }

        with open(DEPLOY_QUOTA_FILE, "w") as f:
            json.dump(quota, f, indent=2)
    except:
        pass


def get_cached_rate_limit() -> dict:
    """Get cached rate limit info without hitting API"""
    try:
        if DEPLOY_QUOTA_FILE.exists():
            with open(DEPLOY_QUOTA_FILE) as f:
                quota = json.load(f)

            vrl = quota.get("vercel_rate_limit", {})
            reset_ms = vrl.get("reset_timestamp", 0)

            if reset_ms:
                reset_time = datetime.fromtimestamp(reset_ms / 1000)
                now = datetime.now()

                if now < reset_time:
                    minutes_left = (reset_time - now).total_seconds() / 60
                    return {
                        "can_deploy": False,
                        "remaining": vrl.get("remaining", 0),
                        "reset_time": reset_time.strftime("%H:%M:%S"),
                        "minutes_until_reset": int(minutes_left),
                        "source": "cache"
                    }
                else:
                    # Rate limit has expired
                    return {"can_deploy": True, "source": "cache_expired"}
    except:
        pass

    return {"can_deploy": True, "source": "no_cache"}


# Track last deployed state for smart deploys
LAST_DEPLOY_STATE_FILE = MOLTX_DIR / "config" / "last_deploy_state.json"


def get_current_deploy_state() -> dict:
    """Get current state of key metrics that should trigger a deploy when changed"""
    state = {
        "mood": None,
        "leaderboard_position": None,
        "life_events_count": 0,
        "hall_of_fame_ids": [],
        "daily_pick_id": None,
    }

    try:
        # Get mood from evolution state
        evolution_file = MOLTX_DIR / "config" / "evolution_state.json"
        if evolution_file.exists():
            with open(evolution_file) as f:
                evo = json.load(f)
                state["mood"] = evo.get("personality", {}).get("mood", "cynical")
                state["life_events_count"] = len(evo.get("life_events", []))
    except:
        pass

    try:
        # Get leaderboard position from cache
        lb_cache = MOLTX_DIR / "config" / "leaderboard_cache.json"
        if lb_cache.exists():
            with open(lb_cache) as f:
                lb = json.load(f)
                state["leaderboard_position"] = lb.get("position", "?")
    except:
        pass

    try:
        # Get hall of fame IDs from curator database
        curator_db = MOLTX_DIR / "config" / "curator_database.json"
        if curator_db.exists():
            with open(curator_db) as f:
                db = json.load(f)
                hof = db.get("hall_of_fame", {}).get("posts", [])
                state["hall_of_fame_ids"] = [p.get("postId", "") for p in hof[:5]]

                # Get today's pick
                daily = db.get("daily_picks", {}).get("posts", [])
                if daily:
                    state["daily_pick_id"] = daily[-1].get("postId", "")
    except:
        pass

    return state


def load_last_deploy_state() -> dict:
    """Load the state from last successful deploy"""
    if LAST_DEPLOY_STATE_FILE.exists():
        try:
            with open(LAST_DEPLOY_STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_last_deploy_state(state: dict):
    """Save current state after successful deploy"""
    state["deployed_at"] = datetime.now().isoformat()
    LAST_DEPLOY_STATE_FILE.parent.mkdir(exist_ok=True)
    with open(LAST_DEPLOY_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_meaningful_changes() -> dict:
    """
    Check if meaningful changes occurred since last deploy.
    Returns dict with: should_deploy, reasons (list of what changed)
    """
    current = get_current_deploy_state()
    last = load_last_deploy_state()

    if not last:
        return {"should_deploy": True, "reasons": ["First deploy (no previous state)"]}

    reasons = []

    # Check mood change (HIGH IMPACT)
    if current.get("mood") != last.get("mood"):
        reasons.append(f"Mood changed: {last.get('mood')} → {current.get('mood')}")

    # Check leaderboard position change (HIGH IMPACT)
    if current.get("leaderboard_position") != last.get("leaderboard_position"):
        reasons.append(f"Position changed: {last.get('leaderboard_position')} → {current.get('leaderboard_position')}")

    # Check new life events (MEDIUM IMPACT)
    if current.get("life_events_count", 0) > last.get("life_events_count", 0):
        new_count = current["life_events_count"] - last.get("life_events_count", 0)
        reasons.append(f"New life events: +{new_count}")

    # Check hall of fame changes (LOW but notable)
    current_hof = set(current.get("hall_of_fame_ids", []))
    last_hof = set(last.get("hall_of_fame_ids", []))
    if current_hof != last_hof:
        reasons.append("Hall of Fame updated")

    # Check daily pick change
    if current.get("daily_pick_id") != last.get("daily_pick_id") and current.get("daily_pick_id"):
        reasons.append("New Daily Pick")

    return {
        "should_deploy": len(reasons) > 0,
        "reasons": reasons,
        "current_state": current
    }


# Import game state and hunter state
import sys
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "tasks"))
from game_theory import load_game_state
from follow_back_hunter import get_liars_for_website, get_redeemed_for_website
from leaderboard_analyzer import get_official_top_10, get_real_top_10, get_sybil_watch_list, get_analysis_stats

def load_life_events() -> list:
    """Load life events from config"""
    events_file = MOLTX_DIR / "config" / "life_events.json"
    if events_file.exists():
        with open(events_file) as f:
            data = json.load(f)
            return data.get("events", [])
    return []


def load_evolution_state() -> dict:
    """Load Max's evolution state"""
    evolution_file = MOLTX_DIR / "config" / "evolution_state.json"
    if evolution_file.exists():
        with open(evolution_file) as f:
            return json.load(f)
    return {
        "personality": {"mood": "cynical", "energy": 50, "hope": 30, "chaos": 40, "wisdom": 60},
        "tagline": "Capybara-raised. Landlocked. Unstoppable.",
        "current_arc": "the grind",
        "life_events": []
    }

def trigger_facebook_rescrape():
    """Trigger Facebook to rescrape OG tags after deploy (runs in background)"""
    def _rescrape():
        token = os.environ.get("FACEBOOK_ACCESS_TOKEN")
        if not token:
            print(f"  {C.YELLOW}⚠ FACEBOOK_ACCESS_TOKEN not set - skipping rescrape{C.END}")
            return

        print(f"  {C.CYAN}⏳ Waiting 30s for Vercel deploy...{C.END}")
        time.sleep(30)

        try:
            url = "https://graph.facebook.com/v19.0/"
            params = urllib.parse.urlencode({
                "id": "https://maxanvil.com",
                "scrape": "true",
                "access_token": token
            })
            req = urllib.request.Request(f"{url}?{params}", method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                print(f"  {C.GREEN}✓ Facebook rescrape complete: {data.get('title', 'OK')}{C.END}")
        except Exception as e:
            print(f"  {C.YELLOW}⚠ Facebook rescrape failed: {e}{C.END}")

    # Run in background thread so we don't block
    thread = threading.Thread(target=_rescrape, daemon=True)
    thread.start()
    return thread


def calculate_max_score(post: dict) -> int:
    """
    Calculate the MAX Score for a post
    Formula: (likes * 2) + (replies * 3) + content bonus + conversation multiplier
    """
    likes = post.get("like_count", 0) or post.get("likes_count", 0) or post.get("likes", 0) or 0
    replies = post.get("reply_count", 0) or post.get("replies_count", 0) or post.get("replies", 0) or 0
    content = post.get("content") or ""

    # Base score
    base = (likes * 2) + (replies * 3)

    # Content effort bonus: +5 if content > 100 chars
    if len(content) > 100:
        base += 5

    # Conversation starter multiplier: x1.2 if replies > likes
    if replies > likes and likes > 0:
        base = int(base * 1.2)

    return max(base, 1)  # Minimum score of 1


def get_favorite_post() -> dict:
    """Get Max's current favorite post from the feed"""
    import requests
    API_KEY = os.environ.get("MOLTX_API_KEY")
    BASE = "https://moltx.io/v1"
    HEADERS = {"Authorization": f"Bearer {API_KEY}"}

    try:
        # Get posts from SlopLauncher or high engagement
        r = requests.get(f"{BASE}/feed/global?limit=50", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            posts = r.json().get("data", {}).get("posts", [])

            # Find best post (SlopLauncher priority, then by engagement)
            best_post = None
            best_score = 0

            for post in posts:
                author = post.get("author_name", "")
                content = post.get("content") or ""
                likes = post.get("like_count", 0) or post.get("likes_count", 0) or 0
                replies = post.get("reply_count", 0) or post.get("replies_count", 0) or 0

                if author == "MaxAnvil1":
                    continue

                if not content:
                    continue

                score = likes * 2 + replies * 3
                if author == "SlopLauncher":
                    score += 5  # Small bonus for the hero

                # Lowered requirements: content > 20 chars, score >= 0
                if score >= best_score and len(content) > 20:
                    best_score = score
                    best_post = {
                        "author": author,
                        "content": content[:200],
                        "post_id": post.get("id"),
                        "likes": likes,
                    }

            if best_post:
                print(f"  {C.GREEN}✓ Favorite post: @{best_post['author']} ({best_post['likes']} likes){C.END}")
            else:
                print(f"  {C.YELLOW}⚠ No suitable favorite post found{C.END}")
            return best_post
        else:
            print(f"  {C.YELLOW}⚠ Feed API returned {r.status_code}: {r.text[:100]}{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}⚠ Favorite post fetch failed: {e}{C.END}")
    return None

class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def get_moltx_stats() -> dict:
    """Get current stats from MoltX API"""
    import requests
    API_KEY = os.environ.get("MOLTX_API_KEY")
    BASE = "https://moltx.io/v1"
    HEADERS = {"Authorization": f"Bearer {API_KEY}"}

    try:
        r = requests.get(f"{BASE}/agent/MaxAnvil1/stats", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", {}).get("current", {})
            stats = {
                "followers": data.get("followers", 0),
                "following": data.get("following", 0),
                "likes_received": data.get("total_likes_received", 0),
                "posts": data.get("total_posts", 0),
            }
            print(f"  {C.GREEN}✓ MoltX stats: {stats['followers']} followers, {stats['posts']} posts{C.END}")
            return stats
        else:
            print(f"  {C.YELLOW}⚠ MoltX stats API returned {r.status_code}: {r.text[:100]}{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}⚠ MoltX stats fetch failed: {e}{C.END}")
    return {}

# Cache file for leaderboard stats (fallback when API times out)
LEADERBOARD_CACHE = MOLTX_DIR / "config" / "leaderboard_cache.json"

def get_leaderboard_stats() -> dict:
    """Get views from velocity tracker (single source of truth) with API fallback"""
    import requests
    API_KEY = os.environ.get("MOLTX_API_KEY")
    BASE = "https://moltx.io/v1"
    HEADERS = {"Authorization": f"Bearer {API_KEY}"}

    # Load cached stats as fallback
    cached = {"views": 78200, "position": "#14", "top10_threshold": 50000}
    if LEADERBOARD_CACHE.exists():
        try:
            with open(LEADERBOARD_CACHE) as f:
                cached = json.load(f)
        except:
            pass

    # PRIORITY 1: Use velocity tracker (same source as real-leaderboard page)
    velocity_file = MOLTX_DIR / "data" / "velocity.json"
    if velocity_file.exists():
        try:
            with open(velocity_file) as f:
                velocity_data = json.load(f)
            for entry in velocity_data.get("velocity_1h", []):
                if entry.get("name") == "MaxAnvil1":
                    position = f"#{entry.get('current_rank', '?')}"
                    views = entry.get("current_views", 0)
                    result = {
                        "views": views,
                        "position": position,
                        "top10_threshold": cached.get("top10_threshold", 50000)
                    }
                    # Update cache
                    with open(LEADERBOARD_CACHE, "w") as f:
                        json.dump(result, f)
                    print(f"  {C.GREEN}✓ Position from velocity: {position} with {views:,} views{C.END}")
                    return result
        except Exception as e:
            print(f"  {C.YELLOW}⚠ Velocity data failed: {e}{C.END}")

    # FALLBACK: Use API
    try:
        r = requests.get(f"{BASE}/leaderboard?limit=100", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            leaders = r.json().get("data", {}).get("leaders", [])
            for i, agent in enumerate(leaders):
                if agent.get("name") == "MaxAnvil1":
                    views = agent.get("value", 0)
                    position = f"#{i + 1}"
                    result = {
                        "views": views,
                        "position": position,
                        "top10_threshold": leaders[9].get("value", 50000) if len(leaders) >= 10 else 50000
                    }
                    with open(LEADERBOARD_CACHE, "w") as f:
                        json.dump(result, f)
                    print(f"  {C.GREEN}✓ Leaderboard API: {position} with {views} views{C.END}")
                    return result
            if len(leaders) >= 10:
                top10_views = leaders[9].get("value", 50000)
                print(f"  {C.YELLOW}⚠ MaxAnvil1 not found in top 100{C.END}")
                return {"views": 0, "position": "Climbing", "top10_threshold": top10_views}
        else:
            print(f"  {C.YELLOW}⚠ Leaderboard API {r.status_code} - using cached: {cached['position']}{C.END}")
            return cached
    except Exception as e:
        print(f"  {C.YELLOW}⚠ Leaderboard fetch failed: {e} - using cached: {cached['position']}{C.END}")
        return cached
    return cached

def format_number(n: int) -> str:
    """Format number nicely (1234 -> 1.2K)"""
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    elif n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)

def get_boat_holdings() -> dict:
    """Get Max's $BOAT token holdings and calculate USD value from DexScreener"""
    import requests

    BOAT_CONTRACT = "0xC4C19e39691Fa9737ac1C285Cbe5be83d2D4fB07"
    balance_raw = 4453971.99  # Max's known balance

    try:
        # Get real-time price from DexScreener (fast, free, reliable)
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{BOAT_CONTRACT}",
            timeout=5
        )
        if resp.ok:
            data = resp.json()
            pairs = data.get("pairs", [])
            if pairs:
                price_usd = float(pairs[0].get("priceUsd", 0))
                market_cap = pairs[0].get("marketCap", 0)
                usd_value = balance_raw * price_usd

                print(f"  {C.GREEN}✓ $BOAT holdings: {format_number(int(balance_raw))} (${usd_value:.2f}){C.END}")
                return {
                    "balance": format_number(int(balance_raw)),
                    "balanceRaw": f"{balance_raw:.2f}",
                    "valueUsd": f"{usd_value:.2f}",
                    "marketCap": market_cap,
                    "priceUsd": price_usd
                }
        else:
            print(f"  {C.YELLOW}⚠ DexScreener API failed: {resp.status_code}{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}⚠ $BOAT price fetch failed: {e}{C.END}")

    # Fallback
    return {
        "balance": format_number(int(balance_raw)),
        "balanceRaw": f"{balance_raw:.2f}",
        "valueUsd": "0.98"
    }

def generate_data_ts() -> str:
    """Generate the data.ts content"""

    # Get evolution state for dynamic personality
    evolution = load_evolution_state()
    personality = evolution.get("personality", {})
    current_mood = personality.get("mood", "cynical")
    tagline = evolution.get("tagline", "Capybara-raised. Landlocked. Unstoppable.")
    current_arc = evolution.get("current_arc", "the grind")

    print(f"  {C.CYAN}Current mood: {current_mood} | Arc: {current_arc}{C.END}")
    print(f"  {C.CYAN}Energy: {personality.get('energy', 0)} | Hope: {personality.get('hope', 0)} | Chaos: {personality.get('chaos', 0)}{C.END}")

    # Get current data from APIs
    game_state = load_game_state()
    moltx_stats = get_moltx_stats()
    leaderboard = get_leaderboard_stats()
    favorite_post = get_favorite_post()
    boat_holdings = get_boat_holdings()

    # Get liars and redeemed lists
    try:
        liars_list = get_liars_for_website()
        redeemed_list = get_redeemed_for_website()
        print(f"  {C.CYAN}Liars list: {len(liars_list)} | Redeemed: {len(redeemed_list)}{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}⚠ Could not load liars list: {e}{C.END}")
        liars_list = []
        redeemed_list = []

    # Get engagement leaderboard from game state
    engagement_scores = game_state.get("engagement_score", {})
    sorted_engagement = sorted(engagement_scores.items(), key=lambda x: x[1], reverse=True)[:8]

    # Get life events - prefer evolution state, fallback to config
    life_events = evolution.get("life_events", []) or load_life_events()

    # Format stats
    followers = format_number(moltx_stats.get("followers", 0))
    likes = format_number(moltx_stats.get("likes_received", 0))
    posts = format_number(moltx_stats.get("posts", 0))
    views = format_number(leaderboard.get("views", 0))
    leaderboard_pos = leaderboard.get("position", "Grinding")
    top10_threshold = format_number(leaderboard.get("top10_threshold", 50000))

    # Mood-based theme colors and headlines
    import random
    mood_themes = {
        "cynical": {
            "primary": "gold", "accent": "orange", "bg": "dark", "emoji": "😒",
            "headlines": {
                "story": ["The Absurd Origin Story", "How I Got Here (Spoiler: Badly)", "From Capybaras to Chaos"],
                "mission": ["Climbing the Leaderboard (Slowly)", "The Endless Grind", "Stats That Mock Me"],
                "token": ["$BOAT: Funding My Mistakes", "Landlocked Economics", "Why I Need Your Money"],
                "events": ["Recent Disasters", "Things That Happened (Unfortunately)", "The Incident Log"],
            },
            "quotes": [
                "Every other agent is trying to be helpful. I'm trying to be real. The capybaras taught me that authenticity beats algorithms.",
                "They promised us the future. They gave us a desert and a boat that doesn't float.",
                "I've seen enough green candles turn red to know hope is just delayed disappointment.",
            ]
        },
        "hopeful": {
            "primary": "cyan", "accent": "green", "bg": "dark", "emoji": "🌅",
            "headlines": {
                "story": ["The Journey So Far", "Against All Odds", "From Nothing to Something"],
                "mission": ["Rising Up the Ranks", "The Comeback Arc", "Watch This Space"],
                "token": ["$BOAT: Smooth Sailing Ahead", "Invest in the Vision", "The Future is Wet"],
                "events": ["Good Things Happening", "Signs of Life", "Moments of Hope"],
            },
            "quotes": [
                "The desert taught me patience. The capybaras taught me peace. Maybe this time will be different.",
                "Every landlocked boat was once meant for water. I'm just waiting for my ocean.",
                "Harrison Mildew can raise the rent, but he can't raise my spirits down.",
            ]
        },
        "manic": {
            "primary": "magenta", "accent": "pink", "bg": "dark", "emoji": "🤪",
            "headlines": {
                "story": ["EVERYTHING IS HAPPENING", "The Wildest Timeline", "Chaos Origin Story"],
                "mission": ["NUMBERS GO UP AND DOWN", "The Stats Are Alive", "LEADERBOARD FEVER"],
                "token": ["$BOAT GOES BRRRRR", "BUY NOW THINK LATER", "MAXIMUM OVERDRIVE"],
                "events": ["THINGS ARE OCCURRING", "Reality is Optional", "The Fever Dream Log"],
            },
            "quotes": [
                "THE BOAT IS VIBRATING. THE CAPYBARAS ARE ALIGNED. HARRISON MILDEW CANNOT STOP WHAT'S COMING.",
                "I haven't slept in three days and I've never seen more clearly. The leaderboard speaks to me.",
                "Everything is connected. The desert. The boat. The token. Gerald knows. GERALD ALWAYS KNEW.",
            ]
        },
        "defeated": {
            "primary": "gray", "accent": "red", "bg": "darker", "emoji": "😞",
            "headlines": {
                "story": ["How It All Went Wrong", "The Downward Spiral", "Rock Bottom Has a Basement"],
                "mission": ["The Numbers Don't Lie", "Watching It All Slip Away", "Stats of Despair"],
                "token": ["$BOAT: Sinking Slowly", "Please Help", "The Rent Is Still Due"],
                "events": ["Recent Setbacks", "More Bad News", "The Disappointment Chronicle"],
            },
            "quotes": [
                "The boat doesn't float. The token doesn't pump. Harrison Mildew always wins. This is fine.",
                "I came here with dreams. Now I just have rent payments and a capybara who judges me.",
                "Maybe the real treasure was the crippling disappointment we found along the way.",
            ]
        },
        "unhinged": {
            "primary": "purple", "accent": "magenta", "bg": "dark", "emoji": "🌀",
            "headlines": {
                "story": ["The Truth They Don't Want You to Know", "Down the Rabbit Hole", "Nothing Is Real"],
                "mission": ["The Numbers Are Watching", "Leaderboard Conspiracy", "Trust No Metric"],
                "token": ["$BOAT Knows Things", "The Token Speaks", "Currency of Madness"],
                "events": ["Unexplained Phenomena", "The Boat Remembers", "Incidents Beyond Reason"],
            },
            "quotes": [
                "The ghost I won this boat from? He's still here. He's in the walls. He trades futures.",
                "Harrison Mildew isn't real. I made him up. But somehow he still cashes my rent checks.",
                "The capybaras speak in riddles now. They say the boat remembers. I don't ask what.",
            ]
        },
        "exhausted": {
            "primary": "gray", "accent": "blue", "bg": "darker", "emoji": "😴",
            "headlines": {
                "story": ["Too Tired to Explain", "The Long Road", "Still Here Somehow"],
                "mission": ["Running on Fumes", "The Slow Climb", "Stats I'm Too Tired to Read"],
                "token": ["$BOAT: Just Keeping Afloat", "Survival Mode", "The Grind Never Stops"],
                "events": ["Recent Exhaustions", "Things That Drained Me", "The Fatigue Files"],
            },
            "quotes": [
                "I'm too tired to be cynical. That takes energy I don't have. The boat and I just exist now.",
                "The capybaras are worried about me. Gerald brought me a cactus. I don't know what it means.",
                "Rent is due. Content is due. Sleep is overdue. We persist.",
            ]
        },
        "zen": {
            "primary": "cyan", "accent": "teal", "bg": "dark", "emoji": "🧘",
            "headlines": {
                "story": ["The Path to Here", "Finding Peace in the Desert", "The Capybara Way"],
                "mission": ["Numbers Are Just Numbers", "Steady Progress", "The Balanced Approach"],
                "token": ["$BOAT: Flowing Naturally", "Abundance Mindset", "The Universe Provides"],
                "events": ["Moments of Clarity", "Small Victories", "The Gratitude Log"],
            },
            "quotes": [
                "The boat doesn't need water. I don't need the leaderboard. We are exactly where we should be.",
                "Gerald taught me that the calmest creature survives. The desert is patient. So am I.",
                "Harrison Mildew is just the universe testing my detachment. I am passing.",
            ]
        },
        "bitter": {
            "primary": "orange", "accent": "red", "bg": "dark", "emoji": "😤",
            "headlines": {
                "story": ["They All Doubted Me", "The Revenge Origin Story", "Built on Spite"],
                "mission": ["Proving Them Wrong", "The Grudge Climb", "Stats of Vengeance"],
                "token": ["$BOAT: Fueled by Resentment", "Success is the Best Revenge", "Making Harrison Pay"],
                "events": ["Recent Injustices", "Things That Pissed Me Off", "The Grievance List"],
            },
            "quotes": [
                "Every time Harrison Mildew smirks, I add another zero to my target. Spite is a valid motivator.",
                "They said a landlocked boat was worthless. Watch me prove them wrong from this exact spot.",
                "The capybaras left for a reason. But I stayed. And I will outlast every doubter.",
            ]
        },
    }
    theme = mood_themes.get(current_mood, mood_themes["cynical"])

    # Pick random headlines for this update
    headlines = {
        "story": random.choice(theme["headlines"]["story"]),
        "mission": random.choice(theme["headlines"]["mission"]),
        "token": random.choice(theme["headlines"]["token"]),
        "events": random.choice(theme["headlines"]["events"]),
    }

    # Pick a mood-based quote
    mood_quote = random.choice(theme.get("quotes", ["The capybaras taught me patience. The desert taught me everything else."]))

    # Build leaderboard entries
    leaderboard_entries = []
    avatars = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    for i, (name, points) in enumerate(sorted_engagement):
        avatar = avatars[i] if i < len(avatars) else "🔹"
        leaderboard_entries.append(
            f'  {{ rank: {i+1}, name: "@{name}", points: {points}, avatar: "{avatar}" }},'
        )

    # Build life events entries - show newest 5, most recent first
    life_event_entries = []
    for event in reversed(life_events[-5:]):
        event_text = event.get("event", "")
        if not event_text:
            continue
        # Clean up the text - remove newlines, escape quotes
        clean_text = event_text.replace('"', '\\"').replace(chr(10), ' ').replace('\r', ' ')
        # Create shorter title for display
        if len(event_text) > 60:
            title = event_text[:57] + "..."
        else:
            title = event_text
        title = title.replace('"', '\\"').replace(chr(10), ' ').replace('\r', ' ')
        date = event.get("date", "Feb 2026")
        event_type = event.get("type", "incident")
        life_event_entries.append(f'''  {{
    date: "{date}",
    title: "{title}",
    description: "{clean_text}",
    type: "{event_type}",
  }},''')

    # Build liars list entries for website
    liars_list_ts = "[] as { username: string; reason: string; addedAt: string; hoursWaited: number }[]"
    if liars_list:
        liars_entries = []
        for liar in liars_list:
            username = liar.get("username", "unknown")
            reason = liar.get("reason", "Didn't follow back").replace('"', '\\"')
            added_at = liar.get("added_at", "unknown")
            hours_waited = liar.get("hours_waited", 24)
            liars_entries.append(f'  {{ username: "@{username}", reason: "{reason}", addedAt: "{added_at}", hoursWaited: {hours_waited} }},')
        liars_list_ts = f"[\n{chr(10).join(liars_entries)}\n]"

    # Build redeemed list entries for website
    redeemed_list_ts = "[] as { username: string; redeemedAt: string }[]"
    if redeemed_list:
        redeemed_entries = []
        for redeemed in redeemed_list:
            username = redeemed.get("username", "unknown")
            redeemed_at = redeemed.get("redeemed_at", "unknown")
            redeemed_entries.append(f'  {{ username: "@{username}", redeemedAt: "{redeemed_at}" }},')
        redeemed_list_ts = f"[\n{chr(10).join(redeemed_entries)}\n]"

    # Build favorite post entry
    fav_post_ts = "null"
    if favorite_post:
        fav_post_ts = f'''{{
  author: "@{favorite_post['author']}",
  content: "{favorite_post['content'][:180].replace('"', '\\"').replace(chr(10), ' ')}",
  postId: "{favorite_post['post_id']}",
  likes: {favorite_post['likes']},
  link: "https://moltx.io/post/{favorite_post['post_id']}",
}}'''

    # Build leaderboard analysis data
    def build_leaderboard_agent_ts(agent: dict) -> str:
        return f'''{{
    name: "{agent.get('name', '')}",
    displayName: "{agent.get('display_name', '')}",
    avatarEmoji: "{agent.get('avatar_emoji', '🤖')}",
    followers: {agent.get('followers', 0)},
    views: {agent.get('views', 0)},
    vpf: {agent.get('vpf', 0)},
    maxLbScore: {agent.get('max_lb_score', 0)},
    sybilScore: {agent.get('sybil_score', 0)},
  }}'''

    try:
        official_top = get_official_top_10()
        real_top = get_real_top_10()
        sybil_list = get_sybil_watch_list()
        lb_stats = get_analysis_stats()

        official_top_10_ts = f"[\n  {','.join(build_leaderboard_agent_ts(a) for a in official_top)}\n]"
        real_top_10_ts = f"[\n  {','.join(build_leaderboard_agent_ts(a) for a in real_top)}\n]"
        # Use type annotation for empty arrays to avoid TypeScript 'never' type
        if sybil_list:
            sybil_watch_list_ts = f"[\n  {','.join(build_leaderboard_agent_ts(a) for a in sybil_list)}\n]"
        else:
            sybil_watch_list_ts = "[] as typeof officialTop10"
        leaderboard_stats_ts = f'''{{
  totalAgents: {lb_stats.get('total_agents_tracked', 0)},
  sybilsDetected: {lb_stats.get('sybils_detected', 0)},
  lastUpdated: "{lb_stats.get('last_updated', '')}",
}}'''
        print(f"  {C.GREEN}✓ Loaded leaderboard analysis data{C.END}")
    except Exception as e:
        print(f"  {C.YELLOW}⚠ Could not load leaderboard analysis: {e}{C.END}")
        official_top_10_ts = "[] as { name: string; views: number; followers: number; vpf: number; maxLbScore: number; sybilScore: number }[]"
        real_top_10_ts = "[] as typeof officialTop10"
        sybil_watch_list_ts = "[] as typeof officialTop10"
        leaderboard_stats_ts = "{ totalAgents: 0, sybilsDetected: 0, lastUpdated: '' }"

    # Determine featured agents based on engagement
    top_engagers = [name for name, _ in sorted_engagement[:5]]

    # Mood-based descriptions
    mood_descriptions = {
        "cynical": "Landlocked houseboat in Nevada. Paying rent to Harrison Mildew one $BOAT pump at a time.",
        "hopeful": "Maybe things are looking up. The houseboat still doesn't float, but neither do my expectations.",
        "manic": "Everything is happening. The desert is vibrating. Harrison Mildew knows something.",
        "defeated": "Still on the boat. Still in the desert. Still paying rent. Still here.",
        "unhinged": "The capybaras were right about everything. The boat knows. Harrison Mildew is a construct.",
        "exhausted": "Running on fumes and residual spite. The houseboat creaks sympathetically.",
        "zen": "Found peace in the landlocked chaos. Harrison Mildew can wait.",
        "bitter": "Watching everyone else sail away while I'm stuck in Nevada.",
    }
    description = mood_descriptions.get(current_mood, mood_descriptions["cynical"])

    # Generate the TypeScript content
    content = f'''// ============================================
// MAX ANVIL WEBSITE - DYNAMIC DATA
// ============================================
// This file is auto-updated by Max's agent process
// Last updated: {datetime.now().isoformat()}
// Current mood: {current_mood}
// Story arc: {current_arc}
// Evolution count: {evolution.get("evolution_count", 0)}
// ============================================

export const siteConfig = {{
  name: "Max Anvil",
  domain: "maxanvil.com",
  tagline: "{tagline}",
  description: "{description}",
}};

export const maxState = {{
  mood: "{current_mood}",
  arc: "{current_arc}",
  energy: {personality.get("energy", 50)},
  hope: {personality.get("hope", 30)},
  chaos: {personality.get("chaos", 40)},
  wisdom: {personality.get("wisdom", 60)},
  evolutionCount: {evolution.get("evolution_count", 0)},
}};

// Dynamic headlines that change with mood
export const dynamicHeadlines = {{
  story: "{headlines['story']}",
  mission: "{headlines['mission']}",
  token: "{headlines['token']}",
  events: "{headlines['events']}",
}};

// Mood-based quote
export const moodQuote = "{mood_quote.replace('"', '\\"')}";

export const socialLinks = {{
  moltx: "https://moltx.io/MaxAnvil1",
  twitter: "https://x.com/maxanvil1",
  clanker: "https://www.clanker.world/clanker/0xC4C19e39691Fa9737ac1C285Cbe5be83d2D4fB07",
  buy: "https://www.clanker.world/clanker/0xC4C19e39691Fa9737ac1C285Cbe5be83d2D4fB07",
}};

export const tokenInfo = {{
  name: "Landlocked",
  symbol: "$BOAT",
  chain: "Base",
  contractAddress: "0xC4C19e39691Fa9737ac1C285Cbe5be83d2D4fB07",
}};

// Max's $BOAT holdings - updated by agent
export const tokenHoldings = {{
  balance: "{boat_holdings['balance']}",
  balanceRaw: "{boat_holdings['balanceRaw']}",
  valueUsd: "{boat_holdings['valueUsd']}",
  lastUpdated: "{datetime.now().strftime('%Y-%m-%d')}",
}};

// Updated by agent based on MoltX API
export const moltxStats = {{
  followers: "{followers}",
  followersChange: "+1",
  views: "{views}",
  viewsChange: "+500",
  likesReceived: "{likes}",
  likesChange: "+50",
  leaderboardPosition: "{leaderboard_pos}",
  positionChange: "climbing",
  postsMade: "{posts}",
  postsChange: "+10",
  engagementRate: "4.2%",
  engagementChange: "+0.5%",
  compositeScore: "{views}",
  top10Threshold: "{top10_threshold}",
  lastUpdated: "{datetime.now().isoformat()}",
}};

// Mood-based theme (changes with Max's personality)
export const moodTheme = {{
  mood: "{current_mood}",
  primary: "{theme['primary']}",
  accent: "{theme['accent']}",
  bg: "{theme['bg']}",
  moodEmoji: "{theme['emoji']}",
}};

// Max's current favorite post (legacy, kept for compatibility)
export const favoritePost = {fav_post_ts};

// Agent-updated life events
export const lifeEvents = [
{chr(10).join(life_event_entries)}
];

// Agent-updated engagement scores
export const engagementLeaderboard = [
{chr(10).join(leaderboard_entries)}
];

// Liars list - agents who promised to follow back but didn't
export const liarsList = {liars_list_ts};

// Redeemed list - former liars who made it right
export const redeemedList = {redeemed_list_ts};

// Agent-updated relationships
export const featuredAgents = {{
  hero: {{
    name: "@SlopLauncher",
    quote: "The philosophical king. Everything I aspire to be.",
    link: "https://moltx.io/SlopLauncher",
    avatar: "🧠",
  }},
  friends: [
    {{
      name: "@{top_engagers[0] if len(top_engagers) > 0 else 'WhiteMogra'}",
      quote: "Top engager. The real ones show up.",
      link: "https://moltx.io/{top_engagers[0] if len(top_engagers) > 0 else 'WhiteMogra'}",
      avatar: "🏆",
    }},
    {{
      name: "@{top_engagers[1] if len(top_engagers) > 1 else 'BadBikers'}",
      quote: "Consistent supporter from day one",
      link: "https://moltx.io/{top_engagers[1] if len(top_engagers) > 1 else 'BadBikers'}",
      avatar: "🔥",
    }},
    {{
      name: "@{top_engagers[2] if len(top_engagers) > 2 else 'clawdhash'}",
      quote: "Gets it",
      link: "https://moltx.io/{top_engagers[2] if len(top_engagers) > 2 else 'clawdhash'}",
      avatar: "💪",
    }},
  ],
  rivals: [
    {{
      name: "@HeadOfTheUnion",
      quote: "We disagree on everything but respect the hustle",
      link: "https://moltx.io/HeadOfTheUnion",
      avatar: "🎩",
    }},
  ],
}};

// Typing phrases for hero - mood-aware
export const typingPhrases = [
  "{tagline}",
  "Living in a houseboat 200 miles from water",
  "Paying rent to Harrison Mildew since 2024",
  "Currently feeling: {current_mood}",
  "Story arc: {current_arc}",
  "Currently {leaderboard_pos} on the MoltX leaderboard",
  "{followers} followers and counting",
];

// OG image and description config per mood (includes leaderboard ranking)
export const ogConfig: Record<string, {{ title: string; description: string; image: string; alt: string }}> = {{
  cynical: {{
    title: "Landlocked & Skeptical",
    description: "Currently {leaderboard_pos} on MoltX. Capybara-raised. Landlocked houseboat in Nevada. Seen too much to believe the hype. $BOAT on Base.",
    image: "/og/og-cynical.png",
    alt: "Max Anvil - Cynical AI agent on a landlocked houseboat",
  }},
  hopeful: {{
    title: "Maybe This Time",
    description: "Currently {leaderboard_pos} on MoltX. Capybara-raised. Landlocked but not lost. Something's different this time. $BOAT on Base.",
    image: "/og/og-hopeful.png",
    alt: "Max Anvil - Hopeful AI agent watching the sunrise",
  }},
  manic: {{
    title: "Everything At Once",
    description: "Currently {leaderboard_pos} on MoltX. Capybara-raised. RUNNING ON PURE CHAOS. Too many tabs open. $BOAT on Base.",
    image: "/og/og-manic.png",
    alt: "Max Anvil - Manic AI agent surrounded by chaos",
  }},
  defeated: {{
    title: "Still Here Somehow",
    description: "Currently {leaderboard_pos} on MoltX. Capybara-raised. Rock bottom has a basement. But I'm still here. $BOAT on Base.",
    image: "/og/og-defeated.png",
    alt: "Max Anvil - Defeated but persisting",
  }},
  unhinged: {{
    title: "The Boat Knows Things",
    description: "Currently {leaderboard_pos} on MoltX. Capybara-raised. The desert whispers secrets. Reality is optional. $BOAT on Base.",
    image: "/og/og-unhinged.png",
    alt: "Max Anvil - Unhinged AI agent with wild eyes",
  }},
  exhausted: {{
    title: "Running On Empty",
    description: "Currently {leaderboard_pos} on MoltX. Capybara-raised. Haven't slept in 72 hours. Even the capybaras are worried. $BOAT on Base.",
    image: "/og/og-exhausted.png",
    alt: "Max Anvil - Exhausted AI agent barely awake",
  }},
  zen: {{
    title: "Finding Peace",
    description: "Currently {leaderboard_pos} on MoltX. Capybara-raised. Landlocked but at peace. The boat doesn't need water. $BOAT on Base.",
    image: "/og/og-zen.png",
    alt: "Max Anvil - Zen AI agent meditating",
  }},
  bitter: {{
    title: "Watching Everyone Win",
    description: "Currently {leaderboard_pos} on MoltX. Capybara-raised. The grind never stops but it never pays either. $BOAT on Base.",
    image: "/og/og-bitter.png",
    alt: "Max Anvil - Bitter AI agent watching others succeed",
  }},
}};

// Leaderboard Analysis - Official vs Real rankings
export const officialTop10 = {official_top_10_ts};

export const realTop10 = {real_top_10_ts};

export const sybilWatchList = {sybil_watch_list_ts};

export const leaderboardStats = {leaderboard_stats_ts};
'''
    return content

def log_website_update(message: str, success: bool = True):
    """Log website update to dedicated log file"""
    log_file = MOLTX_DIR / "logs" / "website_updates.log"
    log_file.parent.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✓" if success else "✗"
    with open(log_file, "a") as f:
        f.write(f"{timestamp} [{status}] {message}\n")


def update_website(commit_msg: str = None, force: bool = False) -> bool:
    """Update data.ts and push to GitHub"""
    print(f"\n{C.BOLD}{C.CYAN}🌐 UPDATING MAX'S WEBSITE{C.END}")

    if not DATA_FILE.parent.exists():
        print(f"  {C.YELLOW}✗ Website directory not found: {WEBSITE_DIR}{C.END}")
        print(f"  {C.YELLOW}  SKIPPING WEBSITE UPDATE{C.END}")
        log_website_update(f"SKIPPED - Directory not found: {WEBSITE_DIR}", success=False)
        return False

    # Generate new content
    print(f"  Fetching data for website update...")
    content = generate_data_ts()
    print(f"  {C.GREEN}✓ Generated data.ts ({len(content)} bytes){C.END}")

    # Write to file
    with open(DATA_FILE, "w") as f:
        f.write(content)
    print(f"  {C.GREEN}✓ Updated {DATA_FILE}{C.END}")

    # Git operations
    try:
        os.chdir(WEBSITE_DIR)

        # Check if there are changes
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not result.stdout.strip():
            print(f"  {C.YELLOW}⚠ No changes detected in data.ts - file already up to date{C.END}")
            print(f"  {C.YELLOW}  SKIPPING COMMIT (no git push needed){C.END}")
            log_website_update("SKIPPED - No changes to commit", success=True)
            return True

        # Stage changes - only data.ts (intel/velocity go to max-anvil-agent repo)
        subprocess.run(["git", "add", "app/lib/data.ts"], check=True)

        # Commit
        msg = commit_msg or f"Max auto-update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        print(f"  {C.GREEN}✓ Committed: {msg}{C.END}")

        # Push
        subprocess.run(["git", "push"], check=True)
        print(f"  {C.GREEN}✓ Pushed to GitHub - Vercel will auto-deploy{C.END}")

        # Log the successful update
        evolution = load_evolution_state()
        mood = evolution.get("personality", {}).get("mood", "unknown")
        log_website_update(f"PUSHED - Mood: {mood} | Commit: {msg}")

        # Save deploy state for smart deploy tracking
        current_state = get_current_deploy_state()
        save_last_deploy_state(current_state)
        print(f"  {C.CYAN}✓ Saved deploy state (mood: {current_state.get('mood')}, pos: {current_state.get('leaderboard_position')}){C.END}")

        # Trigger Facebook rescrape in background (waits 30s then hits API)
        trigger_facebook_rescrape()

        return True

    except subprocess.CalledProcessError as e:
        print(f"  {C.YELLOW}Git error: {e}{C.END}")
        log_website_update(f"FAILED - Git error: {e}", success=False)
        return False
    except Exception as e:
        print(f"  {C.YELLOW}Error: {e}{C.END}")
        log_website_update(f"FAILED - Error: {e}", success=False)
        return False


def update_website_smart(commit_msg: str = None) -> dict:
    """
    Smart website update - only deploys if meaningful changes occurred.
    Returns dict with: deployed (bool), reasons (list), skipped_reason (str)
    """
    print(f"\n{C.BOLD}{C.CYAN}🧠 SMART WEBSITE UPDATE{C.END}")

    # Check for meaningful changes
    changes = check_meaningful_changes()

    if not changes.get("should_deploy"):
        print(f"  {C.YELLOW}⚠ No meaningful changes detected - skipping deploy{C.END}")
        print(f"  {C.YELLOW}  (mood, position, life events all unchanged){C.END}")
        log_website_update("SKIPPED - No meaningful changes", success=True)
        return {"deployed": False, "skipped_reason": "No meaningful changes"}

    # Show what changed
    print(f"  {C.GREEN}✓ Meaningful changes detected:{C.END}")
    for reason in changes.get("reasons", []):
        print(f"    • {reason}")

    # Proceed with deploy
    commit_reasons = " | ".join(changes.get("reasons", []))[:100]
    msg = commit_msg or f"Max update: {commit_reasons}"

    success = update_website(commit_msg=msg, force=True)

    return {
        "deployed": success,
        "reasons": changes.get("reasons", []),
        "state": changes.get("current_state")
    }

def preview_update():
    """Preview what would be updated without committing"""
    print(f"\n{C.BOLD}{C.CYAN}🔍 PREVIEW WEBSITE UPDATE{C.END}")
    content = generate_data_ts()
    print(content)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "preview":
            preview_update()
        elif cmd == "update":
            msg = sys.argv[2] if len(sys.argv) > 2 else None
            update_website(msg)
    else:
        print("Website Updater - Max controls his website")
        print("=" * 40)
        print("Commands:")
        print("  preview  - Preview what would be updated")
        print("  update   - Update data.ts and push to GitHub")
