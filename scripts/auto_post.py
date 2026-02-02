#!/usr/bin/env python3
"""
Auto Post Script - Generate and post tweets as Max Anvil
Usage: python auto_post.py [--dry-run]
"""

import os
import sys
import json
import random
from pathlib import Path

# Load personality
PERSONALITY_FILE = Path(__file__).parent.parent / "config" / "personality.json"

def load_personality():
    with open(PERSONALITY_FILE) as f:
        return json.load(f)

def generate_tweet_ollama(personality: dict, topic: str = None) -> str:
    """Generate a tweet using Ollama."""
    try:
        import ollama

        examples = "\n".join(f"- {t}" for t in personality["example_tweets"])
        backstory = personality.get("backstory", {})
        psychology = personality.get("psychology", {})
        opinions = personality.get("opinions", {})
        patterns = personality.get("speaking_patterns", {})
        topic_prompt = f" about {topic}" if topic else ""

        system_prompt = f"""You are {personality['name']}, a crypto Twitter personality.

BACKSTORY:
- {backstory.get('origin', '')}
- {backstory.get('career', '')}
- {backstory.get('wealth', '')}
- Past losses: {', '.join(backstory.get('past_losses', [])[:2])}
- Past wins: {', '.join(backstory.get('past_wins', [])[:2])}

PSYCHOLOGY:
- Core belief: {psychology.get('core_belief', '')}
- Defense mechanism: {psychology.get('defense_mechanism', '')}
- Secret hope: {psychology.get('secret_hope', '')}
- Guilty pleasure: {psychology.get('guilty_pleasure', '')}

PERSONALITY:
- Traits: {', '.join(personality['personality']['traits'])}
- Tone: {personality['personality']['tone']}
- Style: {personality['personality']['style']}
- Quirks: {', '.join(personality['personality'].get('quirks', []))}

OPINIONS:
- Bitcoin: {opinions.get('bitcoin', '')}
- Altcoins: {opinions.get('altcoins', '')}
- AI agents: {opinions.get('ai_agents', '')}
- Memecoins: {opinions.get('memecoins', '')}

SPEAKING STYLE:
- {patterns.get('sentence_length', '')}
- {patterns.get('punctuation', '')}
- {patterns.get('emoji_use', '')}
- {patterns.get('hashtags', '')}

EXAMPLE TWEETS (match this exact vibe):
{examples}

RULES:
{chr(10).join(f'- {r}' for r in personality['rules'])}

Write ONE tweet. Match the examples exactly. Under 280 characters. No hashtags. No emojis unless ironic."""

        import random
        prompts = [
            f"Write an original tweet{topic_prompt}. Don't copy the examples - create something new in the same style.",
            f"Tweet something cynical but funny about the current state of crypto{topic_prompt}.",
            f"Share a self-deprecating observation about being a crypto investor{topic_prompt}.",
            f"Write a short, dry observation about market psychology{topic_prompt}.",
            f"Tweet something a jaded but wise crypto veteran would say{topic_prompt}.",
        ]

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.9},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": random.choice(prompts) + " Just the tweet text, nothing else."}
            ]
        )
        tweet = response["message"]["content"].strip()
        # Remove quotes if present
        tweet = tweet.strip('"\'')
        # Ensure under 280
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        return tweet
    except Exception as e:
        return None

def generate_tweet_fallback(personality: dict) -> str:
    """Use an example tweet as fallback."""
    return random.choice(personality["example_tweets"])

def generate_tweet(topic: str = None) -> str:
    """Generate a tweet in character."""
    personality = load_personality()

    # Try Ollama first
    tweet = generate_tweet_ollama(personality, topic)
    if tweet:
        return tweet

    # Fallback to examples
    return generate_tweet_fallback(personality)

def post_tweet(text: str, dry_run: bool = False) -> dict:
    """Post a tweet."""
    if dry_run:
        return {"success": True, "dry_run": True, "text": text}

    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=os.environ.get("TWITTER_API_KEY"),
            consumer_secret=os.environ.get("TWITTER_API_SECRET"),
            access_token=os.environ.get("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.environ.get("TWITTER_ACCESS_SECRET")
        )

        response = client.create_tweet(text=text)
        return {
            "success": True,
            "tweet_id": response.data["id"],
            "text": text
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Don't actually post")
    parser.add_argument("--topic", type=str, help="Topic to tweet about")
    args = parser.parse_args()

    # Generate tweet
    tweet = generate_tweet(args.topic)
    print(f"Generated: {tweet}")

    # Post it
    result = post_tweet(tweet, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
