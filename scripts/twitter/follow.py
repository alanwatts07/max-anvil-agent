#!/usr/bin/env python3
"""
Twitter Follow Script - Saves LLM tokens by handling follows directly
Usage: python follow.py <username>
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

def follow_user(username: str) -> dict:
    """Follow a user by username."""
    try:
        api = get_api()
        # Remove @ if present
        username = username.lstrip("@")
        api.create_friendship(screen_name=username)
        return {"success": True, "username": username, "action": "followed"}
    except tweepy.errors.Forbidden as e:
        return {"success": False, "error": "Already following or forbidden", "details": str(e)}
    except tweepy.errors.NotFound:
        return {"success": False, "error": "User not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python follow.py <username>")
        sys.exit(1)

    result = follow_user(sys.argv[1])
    print(result)
