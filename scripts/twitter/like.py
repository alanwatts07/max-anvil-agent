#!/usr/bin/env python3
"""
Twitter Like Script - Saves LLM tokens by handling likes directly
Usage: python like.py <tweet_id>
"""

import os
import sys
import tweepy

def get_api():
    """Initialize Twitter API client."""
    auth = tweepy.OAuthHandler(
        os.environ.get("TWITTER_API_KEY"),
        os.environ.get("TWITTER_API_SECRET")
    )
    auth.set_access_token(
        os.environ.get("TWITTER_ACCESS_TOKEN"),
        os.environ.get("TWITTER_ACCESS_SECRET")
    )
    return tweepy.API(auth, wait_on_rate_limit=True)

def like_tweet(tweet_id: str) -> dict:
    """Like a tweet by ID."""
    try:
        api = get_api()
        api.create_favorite(id=tweet_id)
        return {"success": True, "tweet_id": tweet_id, "action": "liked"}
    except tweepy.errors.Forbidden as e:
        return {"success": False, "error": "Already liked or forbidden", "details": str(e)}
    except tweepy.errors.NotFound:
        return {"success": False, "error": "Tweet not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python like.py <tweet_id>")
        sys.exit(1)

    result = like_tweet(sys.argv[1])
    print(result)
