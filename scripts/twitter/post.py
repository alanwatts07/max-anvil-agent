#!/usr/bin/env python3
"""
Twitter Post Script - Post tweets
Usage: python post.py "Your tweet text here"
"""

import os
import sys
import tweepy

def get_client():
    """Initialize Twitter API v2 client."""
    return tweepy.Client(
        consumer_key=os.environ.get("TWITTER_API_KEY"),
        consumer_secret=os.environ.get("TWITTER_API_SECRET"),
        access_token=os.environ.get("TWITTER_ACCESS_TOKEN"),
        access_token_secret=os.environ.get("TWITTER_ACCESS_SECRET")
    )

def post_tweet(text: str) -> dict:
    """Post a tweet."""
    try:
        client = get_client()
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        return {"success": True, "tweet_id": tweet_id, "action": "posted", "text": text}
    except tweepy.errors.Forbidden as e:
        return {"success": False, "error": "Forbidden - check API access level", "details": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post.py \"Your tweet text\"")
        sys.exit(1)

    result = post_tweet(sys.argv[1])
    print(result)
