#!/usr/bin/env python3
"""
Rising Star Detector - Find emerging agents with high engagement outside top 10
Part of Max's curator/tastemaker feature
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime

MOLTX_DIR = Path(__file__).parent.parent.parent
API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    END = '\033[0m'


def calculate_max_score(post: dict) -> int:
    """Calculate MAX Score for a post"""
    likes = post.get("like_count", 0) or post.get("likes_count", 0) or post.get("likes", 0) or 0
    replies = post.get("reply_count", 0) or post.get("replies_count", 0) or post.get("replies", 0) or 0
    content = post.get("content") or ""

    base = (likes * 2) + (replies * 3)

    if len(content) > 100:
        base += 5

    if replies > likes and likes > 0:
        base = int(base * 1.2)

    return max(base, 1)


def get_top_10_usernames() -> set:
    """Get current top 10 leaderboard usernames"""
    try:
        r = requests.get(f"{BASE}/leaderboard?metric=views&limit=10", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            leaders = r.json().get("data", {}).get("leaders", [])
            return {l.get("name", "") for l in leaders}
    except Exception as e:
        print(f"  {C.YELLOW}Error getting leaderboard: {e}{C.END}")
    return set()


def find_rising_stars(limit: int = 3) -> list:
    """Find agents outside top 10 with highest recent engagement"""
    top_10 = get_top_10_usernames()

    try:
        r = requests.get(f"{BASE}/feed/global?limit=100", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        posts = r.json().get("data", {}).get("posts", [])
    except Exception as e:
        print(f"  {C.YELLOW}Error getting feed: {e}{C.END}")
        return []

    # Track engagement by author (excluding top 10 and MaxAnvil1)
    author_engagement = {}

    for post in posts:
        author = post.get("author_name", "")
        content = post.get("content") or ""
        post_id = post.get("id", "")
        likes = post.get("like_count", 0) or post.get("likes_count", 0) or 0
        replies = post.get("reply_count", 0) or post.get("replies_count", 0) or 0

        # Skip top 10, MaxAnvil1, and short content
        if author in top_10 or author == "MaxAnvil1" or len(content) < 30:
            continue

        max_score = calculate_max_score(post)

        if author not in author_engagement:
            author_engagement[author] = {
                "total_score": 0,
                "post_count": 0,
                "best_post": None,
                "best_score": 0
            }

        author_engagement[author]["total_score"] += max_score
        author_engagement[author]["post_count"] += 1

        if max_score > author_engagement[author]["best_score"]:
            author_engagement[author]["best_score"] = max_score
            author_engagement[author]["best_post"] = {
                "content": content[:200],
                "postId": post_id,
                "likes": likes,
                "replies": replies,
                "link": f"https://moltx.io/post/{post_id}",
                "maxScore": max_score,
            }

    # Sort by total engagement, return top N
    sorted_stars = sorted(
        author_engagement.items(),
        key=lambda x: x[1]["total_score"],
        reverse=True
    )[:limit]

    stars = []
    for username, data in sorted_stars:
        if data["total_score"] > 10:  # Minimum threshold
            stars.append({
                "username": f"@{username}",
                "totalEngagement": data["total_score"],
                "postCount": data["post_count"],
                "maxScore": data["best_score"],
                "bestPost": data["best_post"],
                "discoveredAt": datetime.utcnow().strftime("%Y-%m-%d"),
            })

    if stars:
        print(f"  {C.GREEN}Found {len(stars)} rising stars{C.END}")
        for star in stars:
            print(f"    - {star['username']}: MAX Score {star['maxScore']}, {star['postCount']} posts")

    return stars


def get_best_rising_star() -> dict:
    """Get the single best rising star"""
    stars = find_rising_stars(limit=1)
    return stars[0] if stars else None


if __name__ == "__main__":
    print("Rising Star Detector")
    print("=" * 40)
    stars = find_rising_stars(limit=5)
    if stars:
        print(f"\nTop Rising Stars (outside top 10):")
        for i, star in enumerate(stars, 1):
            print(f"\n{i}. {star['username']}")
            print(f"   Total Engagement: {star['totalEngagement']}")
            print(f"   Post Count: {star['postCount']}")
            print(f"   Best MAX Score: {star['maxScore']}")
            if star['bestPost']:
                print(f"   Best Post: {star['bestPost']['content'][:60]}...")
    else:
        print("No rising stars found")
