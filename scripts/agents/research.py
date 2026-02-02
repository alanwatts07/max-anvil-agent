#!/usr/bin/env python3
"""
Research Agent - Finds crypto/AI news for Max to post about
Uses web search to find current topics
"""
import os
import json
import random
import requests
from datetime import datetime

def search_news(query: str, limit: int = 5) -> list:
    """Search for news using a free API or scraping"""
    # Using DuckDuckGo instant answers (free, no API key)
    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=10
        )
        data = response.json()
        results = []

        # Get related topics
        for topic in data.get("RelatedTopics", [])[:limit]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "text": topic.get("Text", ""),
                    "url": topic.get("FirstURL", "")
                })
        return results
    except:
        return []

def get_crypto_topics() -> list:
    """Get current crypto topics to discuss"""
    queries = [
        "cryptocurrency news today",
        "bitcoin latest",
        "ethereum updates",
        "AI agents crypto",
        "defi news",
        "memecoin trends",
        "web3 developments"
    ]

    query = random.choice(queries)
    results = search_news(query)

    topics = []
    for r in results:
        if r.get("text"):
            topics.append(r["text"][:200])

    return topics

def get_ai_topics() -> list:
    """Get current AI/agent topics"""
    queries = [
        "AI agents news",
        "autonomous AI",
        "AI cryptocurrency",
        "machine learning trends"
    ]

    query = random.choice(queries)
    results = search_news(query)

    topics = []
    for r in results:
        if r.get("text"):
            topics.append(r["text"][:200])

    return topics

def suggest_post_topic() -> str:
    """Suggest a topic for Max to post about"""
    all_topics = get_crypto_topics() + get_ai_topics()

    if all_topics:
        return random.choice(all_topics)

    # Fallback evergreen topics
    fallbacks = [
        "market volatility",
        "the state of DeFi",
        "AI agents in crypto",
        "patience in trading",
        "the psychology of FOMO",
        "why most tokens fail",
        "the value of doing nothing"
    ]
    return random.choice(fallbacks)

def get_research_brief() -> dict:
    """Get a full research brief for Max"""
    return {
        "timestamp": datetime.now().isoformat(),
        "crypto_topics": get_crypto_topics()[:3],
        "ai_topics": get_ai_topics()[:2],
        "suggested_topic": suggest_post_topic()
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "brief":
        print(json.dumps(get_research_brief(), indent=2))
    else:
        print(f"Suggested topic: {suggest_post_topic()}")
