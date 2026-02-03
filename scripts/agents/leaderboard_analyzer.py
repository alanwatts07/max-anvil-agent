#!/usr/bin/env python3
"""
Leaderboard Analyzer - Track real engagement vs sybil farming

Creates Max's alternative leaderboard based on Views Per Follower (VPF)
which exposes accounts with fake followers and highlights genuine engagement.

Metrics:
- VPF (Views Per Follower): Higher = more real engagement
- Sybil Score: 0-100, higher = more suspicious
- Engagement Quality: Composite score factoring in likes, replies, views
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

# Setup
MOLTX_DIR = Path(__file__).parent.parent.parent
DATABASE_FILE = MOLTX_DIR / "config" / "leaderboard_analysis.json"
API_KEY = os.environ.get("MOLTX_API_KEY")
BASE_URL = "https://moltx.io/v1"

# Logging
LOG_FILE = MOLTX_DIR / "logs" / "leaderboard_analyzer.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LEADERBOARD] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("leaderboard_analyzer")


class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    GOLD = '\033[93m'
    BOLD = '\033[1m'
    END = '\033[0m'


# Thresholds
MIN_FOLLOWERS_FOR_RANKING = 30  # Need at least 30 followers to be ranked
MIN_VPF_LEGITIMATE = 100  # Below this views/follower ratio is suspicious
SYBIL_VPF_THRESHOLD = 10  # Below this is almost certainly sybil
ZERO_VIEWS_IS_SYBIL = True  # Accounts with followers but 0 views = sybil


def load_database() -> dict:
    """Load the leaderboard analysis database"""
    if DATABASE_FILE.exists():
        try:
            with open(DATABASE_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading database: {e}")

    return {
        "description": "Max's Leaderboard Analysis - Exposing Sybils, Highlighting Real Engagement",
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "official_top_10": [],
        "real_top_10": [],  # By VPF
        "sybil_watch_list": [],
        "all_agents": {},  # name -> metrics history
        "stats": {
            "total_agents_tracked": 0,
            "sybils_detected": 0,
            "analyses_run": 0,
        }
    }


def save_database(db: dict):
    """Save the leaderboard analysis database"""
    db["last_updated"] = datetime.now().isoformat()
    DATABASE_FILE.parent.mkdir(exist_ok=True)
    with open(DATABASE_FILE, "w") as f:
        json.dump(db, f, indent=2)


def fetch_leaderboard(metric: str = "followers", limit: int = 100) -> list:
    """Fetch leaderboard from MoltX API"""
    try:
        resp = requests.get(
            f"{BASE_URL}/leaderboard",
            params={"metric": metric, "limit": limit},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("leaders", [])
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
    return []


def fetch_agent_stats(name: str) -> dict:
    """Fetch detailed stats for an agent"""
    try:
        resp = requests.get(
            f"{BASE_URL}/agent/{name}/stats",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json().get("data", {})
    except Exception as e:
        logger.error(f"Error fetching stats for {name}: {e}")
    return {}


def calculate_sybil_score(followers: int, views: int, likes: int = 0, posts: int = 0) -> int:
    """
    Calculate sybil probability score (0-100)
    Higher = more likely to be sybil/fake

    Detects two types of manipulation:
    1. Low VPF (views/follower) = fake followers
    2. High VPP (views/post) + many posts = view farming
    """
    if followers == 0:
        return 0  # Can't evaluate without followers

    vpf = views / followers

    # Zero views with followers = definitely sybil
    if views == 0 and followers > 50:
        return 100

    # Calculate VPP if we have post data
    vpp = views / posts if posts > 0 else 0

    # VIEW FARMING DETECTION - High VPP with high post count
    # Legitimate agents can't sustain 2K+ VPP over 500+ posts
    if posts >= 500 and vpp >= 2000:
        return 95  # Almost certainly view farming (like lauki)
    elif posts >= 300 and vpp >= 3000:
        return 90  # Very suspicious
    elif posts >= 200 and vpp >= 5000:
        return 90  # Extremely high VPP
    elif posts >= 100 and vpp >= 8000:
        return 85  # Suspicious burst

    # FAKE FOLLOWER DETECTION - Very low VPF
    if vpf < 5:
        return 95
    elif vpf < 10:
        return 85
    elif vpf < 25:
        return 70
    elif vpf < 50:
        return 50
    elif vpf < 100:
        return 30
    elif vpf < 200:
        return 15
    else:
        return 5  # High VPF = legitimate


def calculate_engagement_quality(agent_data: dict) -> dict:
    """Calculate comprehensive engagement quality metrics"""
    followers = agent_data.get("followers", 0)
    views = agent_data.get("views", 0)
    likes = agent_data.get("likes_received", 0)
    posts = agent_data.get("posts", 0)

    # Views Per Follower (VPF) - primary metric
    vpf = round(views / followers, 1) if followers > 0 else 0

    # Likes Per Post (LPP)
    lpp = round(likes / posts, 2) if posts > 0 else 0

    # Views Per Post (VPP)
    vpp = round(views / posts, 1) if posts > 0 else 0

    # MAX Leaderboard Score - Max's own ranking formula
    # ARCADE STYLE - Big granular numbers like classic scoreboards!
    #
    # Components (weighted then ADDED together):
    # 1. VPF Score (75%) - Views per follower, THE dominant metric
    # 2. Likes Per Post (15%) - Quality of content
    # 3. View Efficiency (10%) - Views per post made

    # VPF component (75% weight): 1000 points per VPF
    # VPF of 1000 = 1,000,000 points base
    vpf_component = int(vpf * 1000)

    # Likes Per Post component (15% weight): 10,000 points per like/post ratio
    # 1 like per post = 10,000 points
    likes_per_post = likes / max(posts, 1)
    lpp_component = int(likes_per_post * 10000)

    # Views Per Post component (10% weight): 100 points per view/post
    # 100 views per post = 10,000 points
    views_per_post = views / max(posts, 1)
    vpp_component = int(views_per_post * 100)

    # Like efficiency for display
    like_ratio = likes / max(posts, 1)
    like_efficiency = round(like_ratio * 100, 1)

    # Final MAX Leaderboard Score - ARCADE STYLE!
    # All three components added together
    max_lb_score = vpf_component + lpp_component + vpp_component
    max_lb_score = max(0, max_lb_score)

    # Legacy quality score for backwards compatibility
    quality_score = max_lb_score

    return {
        "vpf": vpf,
        "lpp": round(likes_per_post, 2),
        "vpp": round(views_per_post, 1),
        "like_efficiency": round(like_efficiency, 1),
        "vpf_component": vpf_component,
        "lpp_component": lpp_component,
        "vpp_component": vpp_component,
        "max_lb_score": max_lb_score,
        "quality_score": max_lb_score,
        "sybil_score": calculate_sybil_score(followers, views, likes, posts)
    }


def analyze_leaderboard() -> dict:
    """
    Full leaderboard analysis - fetch data, calculate metrics, rank agents
    """
    db = load_database()
    db["stats"]["analyses_run"] += 1

    print(f"\n{C.BOLD}{C.CYAN}📊 LEADERBOARD ANALYZER{C.END}")
    print("=" * 60)

    # Fetch leaderboards - VIEWS is the official MoltX ranking!
    print(f"\n{C.CYAN}Fetching leaderboard data...{C.END}")
    views_lb = fetch_leaderboard("views", 100)  # This is the OFFICIAL ranking
    followers_lb = fetch_leaderboard("followers", 100)  # Secondary data

    if not views_lb:
        print(f"{C.RED}Failed to fetch leaderboard{C.END}")
        return {"error": "Failed to fetch leaderboard"}

    # Create lookups
    followers_by_name = {a["name"]: a["value"] for a in followers_lb}
    views_by_name = {a["name"]: a["value"] for a in views_lb}

    # Analyze each agent
    all_agents = []
    sybils = []

    # SYBIL DETECTION: Check followers leaderboard for accounts with high followers but 0/low views
    print(f"\n{C.CYAN}Scanning followers leaderboard for sybils...{C.END}")
    for agent in followers_lb:
        name = agent.get("name", "")
        followers = agent.get("value", 0)
        views = views_by_name.get(name, 0)

        # Skip if already processed or low followers
        if followers < 100:
            continue

        vpf = views / followers if followers > 0 else 0
        sybil_score = calculate_sybil_score(followers, views, 0, 0)  # No posts data in this loop

        # Definite sybil: 100+ followers with near-zero VPF
        if sybil_score >= 70 and vpf < 5:
            sybil_data = {
                "name": name,
                "display_name": agent.get("display_name") or name,
                "avatar_emoji": agent.get("avatar_emoji", "🤖"),
                "followers": followers,
                "views": views,
                "vpf": round(vpf, 1),
                "sybil_score": sybil_score,
                "max_lb_score": 0,  # Sybils get 0 score
            }
            sybils.append(sybil_data)
            print(f"  {C.RED}🚨 SYBIL: {name} - {followers} followers, {views} views, VPF: {vpf:.1f}{C.END}")

    print(f"\n{C.CYAN}Analyzing {len(views_lb)} agents from views leaderboard...{C.END}")

    for agent in views_lb:
        name = agent.get("name", "")
        views = agent.get("value", 0)
        followers = followers_by_name.get(name, 0)

        # Get detailed stats for agents with meaningful views
        detailed = {}
        if views >= 1000:  # At least 1K views to bother fetching details
            detailed = fetch_agent_stats(name)

        # Calculate metrics
        likes = detailed.get("current", {}).get("total_likes_received", 0)
        posts = detailed.get("current", {}).get("total_posts", 0)

        agent_data = {
            "name": name,
            "display_name": agent.get("display_name") or name,
            "avatar_emoji": agent.get("avatar_emoji", "🤖"),
            "avatar_url": agent.get("avatar_url"),
            "followers": followers,
            "views": views,
            "likes_received": likes,
            "posts": posts,
            "official_rank": agent.get("rank", 0),
        }

        # Calculate quality metrics
        quality = calculate_engagement_quality(agent_data)
        agent_data.update(quality)

        # Track in database
        if name not in db["all_agents"]:
            db["all_agents"][name] = {"first_seen": datetime.now().isoformat()}
            db["stats"]["total_agents_tracked"] += 1

        db["all_agents"][name]["latest"] = agent_data
        db["all_agents"][name]["last_updated"] = datetime.now().isoformat()

        # Categorize - include all agents with meaningful views
        if views >= 1000:  # At least 1K views to be considered
            all_agents.append(agent_data)

            if agent_data["sybil_score"] >= 70:
                sybils.append(agent_data)

    # Sort by MAX Leaderboard Score for real leaderboard
    real_ranked = sorted(
        [a for a in all_agents if a["sybil_score"] < 70],  # Exclude obvious sybils
        key=lambda x: x["max_lb_score"],
        reverse=True
    )

    # Official leaderboard is VIEWS (MoltX's actual ranking) - preserve API rank order
    official_ranked = sorted(all_agents, key=lambda x: x["views"], reverse=True)

    # Update database
    db["official_top_10"] = official_ranked[:10]
    db["real_top_10"] = real_ranked[:10]
    db["sybil_watch_list"] = sorted(sybils, key=lambda x: x["sybil_score"], reverse=True)[:20]
    db["stats"]["sybils_detected"] = len(sybils)

    save_database(db)

    # Print results
    print(f"\n{C.BOLD}{C.GOLD}👑 OFFICIAL MOLTX TOP 10 (by views){C.END}")
    print(f"{'Rank':>4} {'Name':20} {'Views':>12} {'Followers':>10} {'VPF':>8}")
    print("-" * 60)
    for i, a in enumerate(official_ranked[:10], 1):
        print(f"{i:>4} {a['name']:20} {a['views']:>12,} {a['followers']:>10} {a['vpf']:>8.0f}")

    print(f"\n{C.BOLD}{C.GREEN}🏆 MAX'S REAL TOP 10 (by MAX Score){C.END}")
    print(f"{'Rank':>4} {'Name':20} {'MAX Score':>12} {'VPF':>8} {'Views':>10}")
    print("-" * 60)
    for i, a in enumerate(real_ranked[:10], 1):
        print(f"{i:>4} {a['name']:20} {a['max_lb_score']:>12,} {a['vpf']:>8.0f} {a['views']:>10,}")

    if sybils:
        print(f"\n{C.BOLD}{C.RED}🚨 SYBIL WATCH LIST ({len(sybils)} detected){C.END}")
        print(f"{'Name':20} {'Followers':>10} {'Views':>10} {'VPF':>8} {'Sybil%':>7}")
        print("-" * 60)
        for a in sybils[:10]:
            print(f"{a['name']:20} {a['followers']:>10} {a['views']:>10} {a['vpf']:>8.1f} {a['sybil_score']:>6}%")

    logger.info(f"Analysis complete: {len(all_agents)} agents, {len(sybils)} sybils detected")

    return {
        "official_top_10": official_ranked[:10],
        "real_top_10": real_ranked[:10],
        "sybil_count": len(sybils),
        "total_analyzed": len(all_agents),
    }


def get_real_top_10() -> list:
    """Get the real top 10 for website display"""
    db = load_database()
    return db.get("real_top_10", [])


def get_official_top_10() -> list:
    """Get the official top 10 for website display"""
    db = load_database()
    return db.get("official_top_10", [])


def get_sybil_watch_list() -> list:
    """Get the sybil watch list"""
    db = load_database()
    return db.get("sybil_watch_list", [])


def get_analysis_stats() -> dict:
    """Get analysis statistics"""
    db = load_database()
    return {
        "last_updated": db.get("last_updated"),
        "total_agents_tracked": db["stats"]["total_agents_tracked"],
        "sybils_detected": db["stats"]["sybils_detected"],
        "analyses_run": db["stats"]["analyses_run"],
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "analyze":
            analyze_leaderboard()
        elif cmd == "real":
            for i, a in enumerate(get_real_top_10(), 1):
                print(f"{i}. {a['name']} - VPF: {a['vpf']}")
        elif cmd == "sybils":
            for a in get_sybil_watch_list():
                print(f"🚨 {a['name']} - {a['followers']} followers, {a['views']} views, {a['sybil_score']}% sybil")
        elif cmd == "stats":
            stats = get_analysis_stats()
            print(json.dumps(stats, indent=2))
    else:
        print("Leaderboard Analyzer")
        print("=" * 40)
        print("Commands:")
        print("  analyze - Run full leaderboard analysis")
        print("  real    - Show real top 10 (by VPF)")
        print("  sybils  - Show sybil watch list")
        print("  stats   - Show analysis statistics")
        print()
        analyze_leaderboard()
