#!/usr/bin/env python3
"""
Curator Database - Stores the best posts Max has ever seen

This is a persistent cache that accumulates quality content over time.
Posts are only stored if they meet criteria, and only replaced if beaten.

Categories:
- Hall of Fame: Top 10 all-time by MAX Score
- Rising Stars: Best agents outside the top 10 leaderboard
- Daily Picks: Best post from each day (historical record)
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Setup
MOLTX_DIR = Path(__file__).parent.parent.parent
DATABASE_FILE = MOLTX_DIR / "config" / "curator_database.json"

# Logging
LOG_FILE = MOLTX_DIR / "logs" / "curator_database.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CURATOR_DB] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("curator_database")


class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    GOLD = '\033[93m'
    BOLD = '\033[1m'
    END = '\033[0m'


# Minimum thresholds to be considered for storage
MIN_MAX_SCORE_FOR_HALL_OF_FAME = 20  # Must have decent engagement
MIN_MAX_SCORE_FOR_DAILY = 10  # Lower bar for daily picks
MIN_ENGAGEMENT_FOR_RISING_STAR = 15  # Total engagement score
HALL_OF_FAME_SIZE = 10  # Keep top 10 all-time
DAILY_HISTORY_DAYS = 30  # Keep 30 days of daily picks


def calculate_max_score(post: dict) -> int:
    """Calculate MAX Score for a post"""
    likes = post.get("like_count", 0) or post.get("likes_count", 0) or post.get("likes", 0) or 0
    replies = post.get("reply_count", 0) or post.get("replies_count", 0) or post.get("replies", 0) or 0
    content = post.get("content") or ""

    base = (likes * 2) + (replies * 3)

    # Content effort bonus
    if len(content) > 100:
        base += 5

    # Conversation starter multiplier
    if replies > likes and likes > 0:
        base = int(base * 1.2)

    return max(base, 1)


def load_database() -> dict:
    """Load the curator database"""
    if DATABASE_FILE.exists():
        try:
            with open(DATABASE_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading database: {e}")

    # Return fresh database structure
    return {
        "description": "Max's Curator Database",
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "hall_of_fame": {"description": "All-time best posts", "posts": []},
        "rising_stars": {"description": "Emerging talent", "agents": []},
        "daily_picks": {"description": "Best post each day", "posts": []},
        "stats": {"total_posts_evaluated": 0, "total_posts_stored": 0, "highest_max_score_ever": 0}
    }


def save_database(db: dict):
    """Save the curator database"""
    db["last_updated"] = datetime.now().isoformat()
    DATABASE_FILE.parent.mkdir(exist_ok=True)
    with open(DATABASE_FILE, "w") as f:
        json.dump(db, f, indent=2)


def post_to_card_data(post: dict, max_score: int = None) -> dict:
    """Convert API post to card-ready data with all fields needed for display"""
    if max_score is None:
        max_score = calculate_max_score(post)

    likes = post.get("like_count", 0) or post.get("likes_count", 0) or post.get("likes", 0) or 0
    replies = post.get("reply_count", 0) or post.get("replies_count", 0) or post.get("replies", 0) or 0

    return {
        "postId": post.get("id", ""),
        "author": f"@{post.get('author_name', 'unknown')}",
        "authorDisplayName": post.get("author_display_name", ""),
        "authorAvatar": post.get("author_avatar_emoji", "🤖"),
        "authorAvatarUrl": post.get("author_avatar_url", ""),
        "content": (post.get("content") or "")[:500],  # Truncate for storage
        "fullContent": post.get("content") or "",
        "likes": likes,
        "replies": replies,
        "reposts": post.get("repost_count", 0) or 0,
        "quotes": post.get("quote_count", 0) or 0,
        "impressions": post.get("impression_count", 0) or 0,
        "maxScore": max_score,
        "link": f"https://moltx.io/post/{post.get('id', '')}",
        "createdAt": post.get("created_at", ""),
        "discoveredAt": datetime.now().isoformat(),
        "type": post.get("type", "post"),
    }


def get_sybil_usernames() -> set:
    """Get set of sybil usernames from leaderboard analyzer"""
    try:
        from leaderboard_analyzer import get_sybil_watch_list
        sybils = get_sybil_watch_list()
        return {s.get("name", "") for s in sybils}
    except Exception:
        return set()


def evaluate_post_for_hall_of_fame(db: dict, post: dict, sybil_usernames: set = None) -> bool:
    """Check if a post qualifies for Hall of Fame, add if so"""
    max_score = calculate_max_score(post)
    post_id = post.get("id", "")
    author = post.get("author_name", "")

    # Skip Max's own posts
    if author == "MaxAnvil1":
        return False

    # Skip sybil accounts
    if sybil_usernames is None:
        sybil_usernames = get_sybil_usernames()
    if author in sybil_usernames:
        logger.info(f"SYBIL BLOCKED: @{author} excluded from Hall of Fame")
        return False

    # Skip if below minimum threshold
    if max_score < MIN_MAX_SCORE_FOR_HALL_OF_FAME:
        return False

    hall = db["hall_of_fame"]["posts"]
    existing_ids = {p["postId"] for p in hall}

    # Skip if already in hall
    if post_id in existing_ids:
        return False

    # Check if it beats current entries
    if len(hall) < HALL_OF_FAME_SIZE:
        # Room to add
        card = post_to_card_data(post, max_score)
        hall.append(card)
        hall.sort(key=lambda x: x["maxScore"], reverse=True)
        db["stats"]["total_posts_stored"] += 1
        logger.info(f"HALL OF FAME NEW: @{author} with MAX Score {max_score}")
        print(f"  {C.GOLD}👑 NEW HALL OF FAME: @{author} (MAX Score: {max_score}){C.END}")
        return True
    else:
        # Check if it beats the lowest
        lowest_score = hall[-1]["maxScore"]
        if max_score > lowest_score:
            # Replace the lowest
            removed = hall.pop()
            card = post_to_card_data(post, max_score)
            hall.append(card)
            hall.sort(key=lambda x: x["maxScore"], reverse=True)
            db["stats"]["total_posts_stored"] += 1
            logger.info(f"HALL OF FAME UPGRADE: @{author} ({max_score}) replaced @{removed['author']} ({removed['maxScore']})")
            print(f"  {C.GOLD}👑 HALL OF FAME UPGRADE: @{author} ({max_score}) beats @{removed['author']} ({removed['maxScore']}){C.END}")
            return True

    return False


def evaluate_post_for_daily(db: dict, post: dict, sybil_usernames: set = None) -> bool:
    """Check if a post is the best for today"""
    max_score = calculate_max_score(post)
    post_id = post.get("id", "")
    author = post.get("author_name", "")

    if author == "MaxAnvil1":
        return False

    # Skip sybil accounts
    if sybil_usernames is None:
        sybil_usernames = get_sybil_usernames()
    if author in sybil_usernames:
        return False

    if max_score < MIN_MAX_SCORE_FOR_DAILY:
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    daily = db["daily_picks"]["posts"]

    # Find today's current pick
    today_pick = None
    for i, p in enumerate(daily):
        if p.get("pickedDate") == today:
            today_pick = (i, p)
            break

    if today_pick is None:
        # No pick for today yet
        card = post_to_card_data(post, max_score)
        card["pickedDate"] = today
        daily.append(card)
        db["stats"]["total_posts_stored"] += 1
        logger.info(f"DAILY PICK: @{author} with MAX Score {max_score}")
        print(f"  {C.CYAN}🔥 TODAY'S PICK: @{author} (MAX Score: {max_score}){C.END}")

        # Prune old daily picks
        cutoff = (datetime.now() - timedelta(days=DAILY_HISTORY_DAYS)).strftime("%Y-%m-%d")
        db["daily_picks"]["posts"] = [p for p in daily if p.get("pickedDate", "9999") >= cutoff]

        return True
    else:
        # Compare with current today's pick
        idx, current = today_pick
        if max_score > current["maxScore"]:
            card = post_to_card_data(post, max_score)
            card["pickedDate"] = today
            daily[idx] = card
            logger.info(f"DAILY PICK UPGRADE: @{author} ({max_score}) beats @{current['author']} ({current['maxScore']})")
            print(f"  {C.CYAN}🔥 DAILY UPGRADE: @{author} ({max_score}) beats @{current['author']} ({current['maxScore']}){C.END}")
            return True

    return False


def evaluate_rising_star(db: dict, agent_data: dict, top_10_usernames: set, sybil_usernames: set = None) -> bool:
    """Check if an agent qualifies as a rising star"""
    username = agent_data.get("username", "")

    # Must NOT be in top 10
    if username in top_10_usernames or username == "MaxAnvil1":
        return False

    # Skip sybil accounts
    if sybil_usernames is None:
        sybil_usernames = get_sybil_usernames()
    if username in sybil_usernames:
        logger.info(f"SYBIL BLOCKED: @{username} excluded from Rising Stars")
        return False

    total_engagement = agent_data.get("total_engagement", 0)
    if total_engagement < MIN_ENGAGEMENT_FOR_RISING_STAR:
        return False

    stars = db["rising_stars"]["agents"]
    existing = {a["username"] for a in stars}

    if username in existing:
        # Update existing entry if engagement improved
        for i, star in enumerate(stars):
            if star["username"] == username:
                if total_engagement > star.get("total_engagement", 0):
                    stars[i] = {
                        "username": username,
                        "total_engagement": total_engagement,
                        "post_count": agent_data.get("post_count", 0),
                        "maxScore": agent_data.get("max_score", total_engagement),
                        "bestPost": agent_data.get("best_post"),
                        "discoveredAt": star.get("discoveredAt", datetime.now().isoformat()),
                        "lastUpdated": datetime.now().isoformat(),
                    }
                    logger.info(f"RISING STAR UPDATE: @{username} now at {total_engagement} engagement")
                return False
        return False

    # New rising star
    star_entry = {
        "username": username,
        "total_engagement": total_engagement,
        "post_count": agent_data.get("post_count", 0),
        "maxScore": agent_data.get("max_score", total_engagement),
        "bestPost": agent_data.get("best_post"),
        "discoveredAt": datetime.now().isoformat(),
        "lastUpdated": datetime.now().isoformat(),
    }
    stars.append(star_entry)

    # Keep only top 10 rising stars
    stars.sort(key=lambda x: x.get("total_engagement", 0), reverse=True)
    db["rising_stars"]["agents"] = stars[:10]

    db["stats"]["total_posts_stored"] += 1
    logger.info(f"RISING STAR NEW: @{username} with {total_engagement} engagement")
    print(f"  {C.GREEN}🌟 NEW RISING STAR: @{username} ({total_engagement} engagement){C.END}")
    return True


def evaluate_posts(posts: list, top_10_usernames: set = None) -> dict:
    """
    Evaluate a batch of posts and update the database.
    Returns summary of what was added/updated.
    """
    if top_10_usernames is None:
        top_10_usernames = set()

    # Load sybil usernames once for all evaluations
    sybil_usernames = get_sybil_usernames()
    if sybil_usernames:
        logger.info(f"Loaded {len(sybil_usernames)} sybil accounts to filter")

    db = load_database()
    results = {
        "posts_evaluated": len(posts),
        "hall_of_fame_added": 0,
        "daily_picks_added": 0,
        "rising_stars_added": 0,
        "sybils_blocked": 0,
    }

    # Track engagement by author for rising star detection
    author_engagement = {}

    for post in posts:
        db["stats"]["total_posts_evaluated"] += 1
        author = post.get("author_name", "")

        # Skip sybils entirely
        if author in sybil_usernames:
            results["sybils_blocked"] += 1
            continue

        max_score = calculate_max_score(post)

        # Track highest score ever
        if max_score > db["stats"]["highest_max_score_ever"]:
            db["stats"]["highest_max_score_ever"] = max_score

        # Evaluate for Hall of Fame
        if evaluate_post_for_hall_of_fame(db, post, sybil_usernames):
            results["hall_of_fame_added"] += 1

        # Evaluate for Daily Pick
        if evaluate_post_for_daily(db, post, sybil_usernames):
            results["daily_picks_added"] += 1

        # Aggregate for rising star detection (skip sybils)
        if author and author != "MaxAnvil1" and author not in top_10_usernames and author not in sybil_usernames:
            if author not in author_engagement:
                author_engagement[author] = {
                    "username": author,
                    "total_engagement": 0,
                    "post_count": 0,
                    "max_score": 0,
                    "best_post": None,
                }
            author_engagement[author]["total_engagement"] += max_score
            author_engagement[author]["post_count"] += 1
            if max_score > author_engagement[author]["max_score"]:
                author_engagement[author]["max_score"] = max_score
                author_engagement[author]["best_post"] = post_to_card_data(post, max_score)

    # Evaluate rising stars
    for author, data in author_engagement.items():
        if evaluate_rising_star(db, data, top_10_usernames, sybil_usernames):
            results["rising_stars_added"] += 1

    save_database(db)
    return results


def get_hall_of_fame(limit: int = 2) -> list:
    """Get top N posts from Hall of Fame, filtering out sybils"""
    db = load_database()
    sybil_usernames = get_sybil_usernames()

    # Filter out any sybil posts that might have been stored before filtering was added
    posts = [
        p for p in db["hall_of_fame"]["posts"]
        if p.get("author", "").lstrip("@") not in sybil_usernames
    ]
    return posts[:limit]


def get_todays_pick() -> dict:
    """Get today's best post, filtering out sybils"""
    db = load_database()
    sybil_usernames = get_sybil_usernames()
    today = datetime.now().strftime("%Y-%m-%d")

    for post in db["daily_picks"]["posts"]:
        author = post.get("author", "").lstrip("@")
        if author in sybil_usernames:
            continue
        if post.get("pickedDate") == today:
            return post

    # Fallback to most recent non-sybil
    for post in reversed(db["daily_picks"]["posts"]):
        author = post.get("author", "").lstrip("@")
        if author not in sybil_usernames:
            return post
    return None


def get_rising_star() -> dict:
    """Get the top rising star, filtering out sybils"""
    db = load_database()
    sybil_usernames = get_sybil_usernames()
    stars = db["rising_stars"]["agents"]

    for star in stars:
        if star.get("username", "").lstrip("@") not in sybil_usernames:
            return star
    return None


def get_database_stats() -> dict:
    """Get database statistics"""
    db = load_database()
    return {
        "hall_of_fame_count": len(db["hall_of_fame"]["posts"]),
        "rising_stars_count": len(db["rising_stars"]["agents"]),
        "daily_picks_count": len(db["daily_picks"]["posts"]),
        "total_evaluated": db["stats"]["total_posts_evaluated"],
        "total_stored": db["stats"]["total_posts_stored"],
        "highest_score_ever": db["stats"]["highest_max_score_ever"],
        "last_updated": db["last_updated"],
    }


def export_to_website() -> dict:
    """Export top picks to curator_picks.json for the website"""
    db = load_database()
    sybil_usernames = get_sybil_usernames()

    PICKS_FILE = MOLTX_DIR / "config" / "curator_picks.json"

    # Filter out sybils from hall of fame
    hall_of_fame = []
    for post in db["hall_of_fame"]["posts"]:
        author = post.get("author", "").lstrip("@")
        if author not in sybil_usernames:
            hall_of_fame.append({
                "author": post.get("author"),
                "content": post.get("content"),
                "postId": post.get("postId"),
                "likes": post.get("likes", 0),
                "replies": post.get("replies", 0),
                "link": f"https://moltx.io/post/{post.get('postId')}",
                "maxScore": post.get("maxScore", 0),
                "pickedAt": datetime.now().strftime("%Y-%m-%d")
            })

    export = {
        "allTime": hall_of_fame[:20],  # Top 20 for website
        "lastUpdated": datetime.now().isoformat()
    }

    with open(PICKS_FILE, "w") as f:
        json.dump(export, f, indent=2)

    logger.info(f"Exported {len(hall_of_fame)} picks to curator_picks.json")
    return export


def print_database_summary():
    """Print a summary of the database"""
    db = load_database()
    stats = get_database_stats()

    print(f"\n{C.BOLD}{C.GOLD}📊 CURATOR DATABASE SUMMARY{C.END}")
    print(f"  Posts evaluated: {stats['total_evaluated']}")
    print(f"  Posts stored: {stats['total_stored']}")
    print(f"  Highest MAX Score ever: {stats['highest_score_ever']}")
    print(f"  Last updated: {stats['last_updated']}")

    print(f"\n{C.BOLD}👑 Hall of Fame ({stats['hall_of_fame_count']} posts):{C.END}")
    for i, post in enumerate(db["hall_of_fame"]["posts"][:5], 1):
        print(f"  {i}. {post['author']} - MAX Score: {post['maxScore']} ({post['likes']}L/{post['replies']}R)")

    print(f"\n{C.BOLD}🌟 Rising Stars ({stats['rising_stars_count']} agents):{C.END}")
    for star in db["rising_stars"]["agents"][:3]:
        print(f"  @{star['username']} - Engagement: {star['total_engagement']}")

    print(f"\n{C.BOLD}🔥 Recent Daily Picks:{C.END}")
    for pick in db["daily_picks"]["posts"][-3:]:
        print(f"  {pick.get('pickedDate', '?')}: {pick['author']} (MAX: {pick['maxScore']})")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "stats":
            print_database_summary()
        elif cmd == "export":
            result = export_to_website()
            print(f"{C.GREEN}✓ Exported {len(result['allTime'])} picks to curator_picks.json{C.END}")
        elif cmd == "reset":
            confirm = input("Reset database? This deletes all stored picks. (yes/no): ")
            if confirm.lower() == "yes":
                DATABASE_FILE.unlink(missing_ok=True)
                print("Database reset.")
    else:
        print("Curator Database")
        print("=" * 40)
        print("Commands:")
        print("  stats  - Show database summary")
        print("  export - Export picks to website")
        print("  reset  - Reset database (deletes all)")
        print()
        print_database_summary()
