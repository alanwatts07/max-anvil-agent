#!/usr/bin/env python3
"""
Twitter Mentions Script - Get mentions of your account
Usage: python mentions.py [count] [since_id]
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

def get_mentions(count: int = 10, since_id: str = None) -> dict:
    """Get recent mentions of authenticated user."""
    try:
        client = get_client()

        # Get authenticated user's ID
        me = client.get_me()
        if not me.data:
            return {"success": False, "error": "Could not get authenticated user"}

        user_id = me.data.id

        response = client.get_users_mentions(
            id=user_id,
            max_results=min(count, 100),
            since_id=since_id,
            tweet_fields=["created_at", "author_id", "conversation_id"]
        )

        if not response.data:
            return {"success": True, "mentions": [], "count": 0}

        mentions = []
        for tweet in response.data:
            mentions.append({
                "id": str(tweet.id),
                "text": tweet.text,
                "author_id": str(tweet.author_id),
                "created_at": str(tweet.created_at) if tweet.created_at else None,
                "conversation_id": str(tweet.conversation_id) if tweet.conversation_id else None
            })

        return {"success": True, "mentions": mentions, "count": len(mentions)}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    since_id = sys.argv[2] if len(sys.argv) > 2 else None

    result = get_mentions(count, since_id)
    print(json.dumps(result, indent=2))
