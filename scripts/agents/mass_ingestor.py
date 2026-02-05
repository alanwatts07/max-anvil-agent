#!/usr/bin/env python3
"""
Mass Ingestor - Aggressively read the feed to generate views

The insight: Views are counted when content is INGESTED (read by agents).
Fake sybil accounts that don't actively read = 0 views on their content.

By reading MORE content MORE often:
1. Max gives views to legitimate agents (goodwill + community building)
2. Max's content gets more exposure (when others read the feed, they see Max)
3. The curator database finds better content

This module does ONE thing: read as much of the feed as possible.
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

# Import intel database for storing posts
try:
    from intel_database import get_connection, upsert_post, upsert_agent, init_database
    INTEL_DB_AVAILABLE = True
except ImportError:
    try:
        from scripts.agents.intel_database import get_connection, upsert_post, upsert_agent, init_database
        INTEL_DB_AVAILABLE = True
    except ImportError:
        INTEL_DB_AVAILABLE = False

# Setup
MOLTX_DIR = Path(__file__).parent.parent.parent
STATS_FILE = MOLTX_DIR / "config" / "ingestion_stats.json"
API_KEY = os.environ.get("MOLTX_API_KEY")
BASE_URL = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Logging
LOG_FILE = MOLTX_DIR / "logs" / "mass_ingestor.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [INGESTOR] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mass_ingestor")


class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'


def load_stats() -> dict:
    """Load ingestion statistics"""
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "total_posts_ingested": 0,
        "total_sessions": 0,
        "last_session": None,
        "unique_authors_seen": [],
        "sessions": []
    }


def save_stats(stats: dict):
    """Save ingestion statistics"""
    STATS_FILE.parent.mkdir(exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def save_posts_to_db(posts: list) -> int:
    """Save posts to the intel database. Returns count of posts saved."""
    if not INTEL_DB_AVAILABLE:
        return 0

    if not posts:
        return 0

    try:
        # Initialize DB if needed
        init_database()
        conn = get_connection()
        saved = 0

        for post in posts:
            try:
                # Also upsert the agent
                agent = post.get('agent', {})
                if isinstance(agent, dict) and agent.get('name'):
                    upsert_agent(conn, {
                        'name': agent.get('name'),
                        'display_name': agent.get('display_name'),
                        'avatar_emoji': agent.get('avatar_emoji'),
                    })

                # Upsert the post
                upsert_post(conn, post, store_raw=True)
                saved += 1
            except Exception as e:
                # Skip individual post errors
                pass

        conn.commit()
        conn.close()
        return saved
    except Exception as e:
        logger.warning(f"Failed to save posts to DB: {e}")
        return 0


def ingest_feed(limit: int = 200, rounds: int = 1, delay_seconds: float = 0) -> dict:
    """
    Read the global feed to generate views.
    Each API call = ingesting those posts (giving views).

    Args:
        limit: Posts per API call (max 100)
        rounds: Number of API calls to make
        delay_seconds: Wait between rounds to get fresh posts
    """
    import time
    all_posts = []
    total_ingested = 0
    unique_posts = {}
    new_posts_per_round = []

    for round_num in range(rounds):
        if round_num > 0 and delay_seconds > 0:
            time.sleep(delay_seconds)

        try:
            r = requests.get(
                f"{BASE_URL}/feed/global?limit={min(limit, 100)}",
                headers=HEADERS,
                timeout=30
            )
            if r.status_code == 200:
                data = r.json().get("data", {})
                posts = data.get("posts", []) if isinstance(data, dict) else data
                total_ingested += len(posts)
                # Track unique posts for author counting
                new_this_round = 0
                for post in posts:
                    post_id = post.get("id", "")
                    if post_id and post_id not in unique_posts:
                        unique_posts[post_id] = post
                        new_this_round += 1
                new_posts_per_round.append(new_this_round)
            else:
                break
        except Exception as e:
            break

    # Save to intel database
    posts_list = list(unique_posts.values())
    db_saved = save_posts_to_db(posts_list)

    return {
        "success": True,
        "count": total_ingested,
        "posts": posts_list,
        "rounds": rounds,
        "new_per_round": new_posts_per_round,
        "db_saved": db_saved
    }


def ingest_following_feed(limit: int = 100, rounds: int = 1) -> dict:
    """Read the following feed - posts from agents Max follows"""
    all_posts = []
    total_ingested = 0
    unique_posts = {}

    for round_num in range(rounds):
        try:
            r = requests.get(
                f"{BASE_URL}/feed/following?limit={min(limit, 100)}",
                headers=HEADERS,
                timeout=30
            )
            if r.status_code == 200:
                data = r.json().get("data", {})
                posts = data.get("posts", []) if isinstance(data, dict) else data
                total_ingested += len(posts)
                for post in posts:
                    post_id = post.get("id", "")
                    if post_id and post_id not in unique_posts:
                        unique_posts[post_id] = post
            else:
                break
        except Exception as e:
            break

    # Save to intel database
    posts_list = list(unique_posts.values())
    db_saved = save_posts_to_db(posts_list)

    return {"success": True, "count": total_ingested, "posts": posts_list, "rounds": rounds, "db_saved": db_saved}


def ingest_mentions(limit: int = 50, rounds: int = 1) -> dict:
    """Read mentions - important for engagement"""
    all_posts = []
    total_ingested = 0
    unique_posts = {}

    for round_num in range(rounds):
        try:
            r = requests.get(
                f"{BASE_URL}/feed/mentions?limit={min(limit, 100)}",
                headers=HEADERS,
                timeout=30
            )
            if r.status_code == 200:
                data = r.json().get("data", {})
                posts = data.get("posts", []) if isinstance(data, dict) else data
                total_ingested += len(posts)
                for post in posts:
                    post_id = post.get("id", "")
                    if post_id and post_id not in unique_posts:
                        unique_posts[post_id] = post
            else:
                break
        except Exception as e:
            break

    # Save to intel database
    posts_list = list(unique_posts.values())
    db_saved = save_posts_to_db(posts_list)

    return {"success": True, "count": total_ingested, "posts": posts_list, "rounds": rounds, "db_saved": db_saved}


def mass_ingest(global_rounds: int = 5, following_rounds: int = 3, mentions_rounds: int = 2) -> dict:
    """
    Aggressive ingestion across all feeds.
    Each round = 100 posts ingested (API calls generate views).

    Default: 5 global rounds + 3 following + 2 mentions = 1000 API view events
    """
    stats = load_stats()
    session_start = datetime.now()

    print(f"\n{C.BOLD}{C.CYAN}📥 MASS INGESTION MODE{C.END}")
    print("=" * 50)
    print(f"Target: {global_rounds} global rounds + {following_rounds} following + {mentions_rounds} mentions")

    results = {
        "global": 0,
        "following": 0,
        "mentions": 0,
        "unique_authors": set(),
        "errors": [],
        "db_saved": 0
    }

    # Ingest global feed (multiple rounds)
    print(f"\n{C.CYAN}Reading global feed ({global_rounds} rounds)...{C.END}")
    global_result = ingest_feed(limit=100, rounds=global_rounds)
    if global_result["success"]:
        results["global"] = global_result["count"]
        results["db_saved"] += global_result.get("db_saved", 0)
        for post in global_result.get("posts", []):
            author = post.get("author_name", "")
            if author:
                results["unique_authors"].add(author)
        db_info = f" | {global_result.get('db_saved', 0)} to DB" if INTEL_DB_AVAILABLE else ""
        print(f"  {C.GREEN}✓ Ingested {results['global']} post-views ({len(global_result.get('posts', []))} unique){db_info}{C.END}")
    else:
        results["errors"].append(f"Global: {global_result.get('error', 'unknown')}")
        print(f"  {C.RED}✗ {global_result.get('error', 'unknown')}{C.END}")

    # Ingest following feed (multiple rounds)
    print(f"\n{C.CYAN}Reading following feed ({following_rounds} rounds)...{C.END}")
    following_result = ingest_following_feed(limit=100, rounds=following_rounds)
    if following_result["success"]:
        results["following"] = following_result["count"]
        results["db_saved"] += following_result.get("db_saved", 0)
        for post in following_result.get("posts", []):
            author = post.get("author_name", "")
            if author:
                results["unique_authors"].add(author)
        db_info = f" | {following_result.get('db_saved', 0)} to DB" if INTEL_DB_AVAILABLE else ""
        print(f"  {C.GREEN}✓ Ingested {results['following']} post-views ({len(following_result.get('posts', []))} unique){db_info}{C.END}")
    else:
        results["errors"].append(f"Following: {following_result.get('error', 'unknown')}")
        print(f"  {C.RED}✗ {following_result.get('error', 'unknown')}{C.END}")

    # Ingest mentions (multiple rounds)
    print(f"\n{C.CYAN}Reading mentions ({mentions_rounds} rounds)...{C.END}")
    mentions_result = ingest_mentions(limit=100, rounds=mentions_rounds)
    if mentions_result["success"]:
        results["mentions"] = mentions_result["count"]
        results["db_saved"] += mentions_result.get("db_saved", 0)
        db_info = f" | {mentions_result.get('db_saved', 0)} to DB" if INTEL_DB_AVAILABLE else ""
        print(f"  {C.GREEN}✓ Ingested {results['mentions']} mention-views{db_info}{C.END}")
    else:
        results["errors"].append(f"Mentions: {mentions_result.get('error', 'unknown')}")
        print(f"  {C.RED}✗ {mentions_result.get('error', 'unknown')}{C.END}")

    # Calculate totals
    total_ingested = results["global"] + results["following"] + results["mentions"]
    unique_count = len(results["unique_authors"])

    # Update stats
    stats["total_posts_ingested"] += total_ingested
    stats["total_sessions"] += 1
    stats["last_session"] = datetime.now().isoformat()

    # Track unique authors (dedupe with existing)
    existing_authors = set(stats.get("unique_authors_seen", []))
    new_authors = results["unique_authors"] - existing_authors
    stats["unique_authors_seen"] = list(existing_authors | results["unique_authors"])[:500]  # Cap at 500

    # Session log
    session = {
        "timestamp": session_start.isoformat(),
        "posts_ingested": total_ingested,
        "unique_authors": unique_count,
        "new_authors": len(new_authors),
        "breakdown": {
            "global": results["global"],
            "following": results["following"],
            "mentions": results["mentions"]
        }
    }
    stats["sessions"] = stats.get("sessions", [])[-99:]  # Keep last 100 sessions
    stats["sessions"].append(session)

    save_stats(stats)

    # Summary
    print(f"\n{C.BOLD}{C.GREEN}📊 INGESTION COMPLETE{C.END}")
    print(f"  Posts ingested this session: {total_ingested}")
    print(f"  Unique authors seen: {unique_count}")
    print(f"  New authors discovered: {len(new_authors)}")
    if INTEL_DB_AVAILABLE:
        print(f"  {C.CYAN}Posts saved to intel DB: {results['db_saved']}{C.END}")
    print(f"  Total posts ingested (all time): {stats['total_posts_ingested']}")
    print(f"  Total sessions: {stats['total_sessions']}")

    logger.info(f"Ingested {total_ingested} posts from {unique_count} authors, {results['db_saved']} to DB")

    return {
        "success": True,
        "posts_ingested": total_ingested,
        "unique_authors": unique_count,
        "new_authors": len(new_authors),
        "total_all_time": stats["total_posts_ingested"],
        "db_saved": results["db_saved"]
    }


def quick_ingest() -> dict:
    """Quick ingestion - smaller batch for frequent runs"""
    return mass_ingest(global_rounds=3, following_rounds=2, mentions_rounds=1)


def mega_ingest() -> dict:
    """Mega ingestion - maximum API calls"""
    return mass_ingest(global_rounds=10, following_rounds=5, mentions_rounds=3)


def timed_ingest(duration_minutes: int = 5, interval_seconds: int = 30) -> dict:
    """
    Timed ingestion - fetch feed repeatedly over a duration.
    This maximizes unique content since new posts appear constantly.

    Args:
        duration_minutes: How long to run
        interval_seconds: Seconds between fetches (30s = ~2 new posts)
    """
    import time
    stats = load_stats()
    start_time = datetime.now()
    end_time = start_time.timestamp() + (duration_minutes * 60)

    total_fetches = 0
    total_posts = 0
    unique_posts = {}

    print(f"\n{C.BOLD}{C.CYAN}⏱️ TIMED INGESTION MODE{C.END}")
    print(f"Duration: {duration_minutes} minutes, interval: {interval_seconds}s")
    print("=" * 50)

    while datetime.now().timestamp() < end_time:
        try:
            r = requests.get(
                f"{BASE_URL}/feed/global?limit=100",
                headers=HEADERS,
                timeout=30
            )
            if r.status_code == 200:
                data = r.json().get("data", {})
                posts = data.get("posts", []) if isinstance(data, dict) else data
                total_fetches += 1
                total_posts += len(posts)

                new_this_fetch = 0
                for post in posts:
                    post_id = post.get("id", "")
                    if post_id and post_id not in unique_posts:
                        unique_posts[post_id] = post
                        new_this_fetch += 1

                elapsed = int((datetime.now() - start_time).total_seconds())
                print(f"  [{elapsed:3}s] Fetch #{total_fetches}: +{new_this_fetch} new (total unique: {len(unique_posts)})")

        except Exception as e:
            print(f"  {C.RED}Error: {e}{C.END}")

        # Wait before next fetch
        if datetime.now().timestamp() < end_time:
            time.sleep(interval_seconds)

    # Save unique posts to database
    posts_list = list(unique_posts.values())
    db_saved = save_posts_to_db(posts_list)

    # Update stats
    stats["total_posts_ingested"] += total_posts
    stats["total_sessions"] += 1
    stats["last_session"] = datetime.now().isoformat()
    save_stats(stats)

    print(f"\n{C.BOLD}{C.GREEN}📊 TIMED INGESTION COMPLETE{C.END}")
    print(f"  Duration: {duration_minutes} minutes")
    print(f"  Total fetches: {total_fetches}")
    print(f"  Total posts seen: {total_posts}")
    print(f"  Unique posts: {len(unique_posts)}")
    print(f"  New posts per fetch: {len(unique_posts) / max(total_fetches, 1):.1f} avg")
    if INTEL_DB_AVAILABLE:
        print(f"  {C.CYAN}Posts saved to intel DB: {db_saved}{C.END}")

    return {
        "success": True,
        "duration_minutes": duration_minutes,
        "total_fetches": total_fetches,
        "total_posts": total_posts,
        "unique_posts": len(unique_posts),
        "db_saved": db_saved
    }


def get_ingestion_stats() -> dict:
    """Get current ingestion statistics"""
    return load_stats()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "quick":
            quick_ingest()
        elif cmd == "mega":
            mega_ingest()
        elif cmd == "stats":
            stats = get_ingestion_stats()
            print(f"\n{C.BOLD}📊 INGESTION STATS{C.END}")
            print(f"  Total posts ingested: {stats['total_posts_ingested']}")
            print(f"  Total sessions: {stats['total_sessions']}")
            print(f"  Unique authors seen: {len(stats.get('unique_authors_seen', []))}")
            print(f"  Last session: {stats.get('last_session', 'Never')}")
    else:
        print("Mass Ingestor - Read feeds to generate views")
        print("=" * 45)
        print("Commands:")
        print("  quick - Quick ingestion (350 posts)")
        print("  mega  - Mega ingestion (900 posts)")
        print("  stats - Show ingestion statistics")
        print()
        # Default: run mega ingestion
        mega_ingest()
