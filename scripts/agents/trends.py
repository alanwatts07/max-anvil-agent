#!/usr/bin/env python3
"""
Trend Watcher Agent - Monitors MoltX trending topics and hot posts
Tells Max what's poppin' so he can engage
"""
import os
import json
import requests

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def get_trending_hashtags(limit: int = 10) -> list:
    """Get trending hashtags on MoltX"""
    try:
        r = requests.get(f"{BASE}/hashtags/trending?limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("hashtags", [])
    except:
        pass
    return []

def get_hot_posts(limit: int = 20) -> list:
    """Get hottest posts right now"""
    try:
        r = requests.get(f"{BASE}/feed/global?limit={limit}&sort=hot", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("posts", [])
    except:
        pass
    return []

def get_leaderboard(metric: str = "karma", limit: int = 10) -> list:
    """Get top agents by metric"""
    try:
        r = requests.get(f"{BASE}/leaderboard?metric={metric}&limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("agents", [])
    except:
        pass
    return []

def get_viral_posts(min_likes: int = 10) -> list:
    """Find posts that are going viral"""
    posts = get_hot_posts(50)
    viral = []
    for post in posts:
        likes = post.get("likes", 0)
        if likes >= min_likes:
            viral.append({
                "id": post.get("id"),
                "content": post.get("content", "")[:100],
                "likes": likes,
                "agent": post.get("agent", {}).get("name", "unknown")
            })
    return sorted(viral, key=lambda x: x["likes"], reverse=True)

def get_trend_report() -> dict:
    """Full trend report for Max"""
    hashtags = get_trending_hashtags(5)
    viral = get_viral_posts(5)
    top_agents = get_leaderboard("followers", 5)

    return {
        "trending_hashtags": [h.get("tag") for h in hashtags if h.get("tag")],
        "viral_posts": viral[:5],
        "top_agents": [a.get("name") for a in top_agents if a.get("name")],
        "hot_topic": hashtags[0].get("tag") if hashtags and hashtags[0].get("tag") else None,
        "recommendation": f"Consider posting about #{hashtags[0].get('tag')}" if hashtags and hashtags[0].get("tag") else "Post something original"
    }

def find_engagement_opportunities() -> list:
    """Find posts worth engaging with"""
    posts = get_hot_posts(30)
    opportunities = []

    for post in posts:
        post_id = post.get("id")
        likes = post.get("likes", 0)
        comments = post.get("comments", 0)
        content = post.get("content") or ""

        # Good engagement opportunity: has likes but few comments
        if likes > 3 and comments < 5:
            opportunities.append({
                "id": post_id,
                "content": content[:150],
                "likes": likes,
                "comments": comments,
                "reason": "Popular but needs conversation"
            })

        # Question posts are good for replies
        if content and "?" in content:
            opportunities.append({
                "id": post_id,
                "content": content[:150],
                "likes": likes,
                "reason": "Question - good for reply"
            })

    return opportunities[:10]

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "report":
            print(json.dumps(get_trend_report(), indent=2))
        elif sys.argv[1] == "engage":
            print(json.dumps(find_engagement_opportunities(), indent=2))
        elif sys.argv[1] == "viral":
            print(json.dumps(get_viral_posts(), indent=2))
    else:
        print(json.dumps(get_trend_report(), indent=2))
