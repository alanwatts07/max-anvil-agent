#!/usr/bin/env python3
"""
Twitter Search Script - Search for tweets by keyword/hashtag
Usage: python search.py <query> [count]
"""

import os
import sys
import json
import tweepy

def get_client():
    """Initialize Twitter API v2 client."""
    return tweepy.Client(
        bearer_token=os.environ.get("TWITTER_BEARER_TOKEN"),
        consumer_key=os.environ.get("TWITTER_API_KEY"),
        consumer_secret=os.environ.get("TWITTER_API_SECRET"),
        access_token=os.environ.get("TWITTER_ACCESS_TOKEN"),
        access_token_secret=os.environ.get("TWITTER_ACCESS_SECRET")
    )

def search_tweets(query: str, count: int = 10) -> dict:
    """Search for recent tweets matching query."""
    try:
        client = get_client()
        response = client.search_recent_tweets(
            query=query,
            max_results=min(count, 100),
            tweet_fields=["created_at", "author_id", "public_metrics"]
        )

        if not response.data:
            return {"success": True, "tweets": [], "count": 0}

        tweets = []
        for tweet in response.data:
            tweets.append({
                "id": tweet.id,
                "text": tweet.text,
                "created_at": str(tweet.created_at) if tweet.created_at else None,
                "metrics": tweet.public_metrics
            })

        return {"success": True, "tweets": tweets, "count": len(tweets)}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search.py <query> [count]")
        sys.exit(1)

    query = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    result = search_tweets(query, count)
    print(json.dumps(result, indent=2))
