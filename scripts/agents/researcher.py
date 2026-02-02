#!/usr/bin/env python3
"""
Research Agent - Gathers real news and saves research files for Max
Uses DuckDuckGo API for current events, saves to research folder
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime

RESEARCH_DIR = Path(__file__).parent.parent.parent / "research" / "daily"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

def search_ddg(query: str, max_results: int = 10) -> list:
    """Search DuckDuckGo for current info"""
    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            },
            timeout=10
        )
        data = response.json()

        results = []

        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", query),
                "text": data.get("Abstract"),
                "source": data.get("AbstractSource"),
                "url": data.get("AbstractURL")
            })

        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "text": topic.get("Text"),
                    "url": topic.get("FirstURL", "")
                })

        return results
    except Exception as e:
        return []

def get_crypto_news() -> dict:
    """Get current crypto market data"""
    try:
        # Fear & Greed
        fg = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        fear_greed = fg.get("data", [{}])[0] if fg.get("data") else {}

        # Prices
        prices = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,solana",
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            },
            timeout=5
        ).json()

        return {
            "fear_greed": {
                "value": fear_greed.get("value", "50"),
                "classification": fear_greed.get("value_classification", "Neutral")
            },
            "prices": prices
        }
    except:
        return {}

def gather_research() -> dict:
    """Gather all research for post generation"""
    research = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "market": get_crypto_news(),
        "topics": {}
    }

    # Research different topics
    topics_to_research = [
        ("ai_agents", "AI agents crypto blockchain"),
        ("bitcoin", "bitcoin news"),
        ("tech_drama", "tech industry drama"),
        ("defi", "DeFi news"),
        ("memes", "crypto memes viral")
    ]

    for topic_key, query in topics_to_research:
        results = search_ddg(query, 5)
        if results:
            research["topics"][topic_key] = results

    return research

def save_research(research: dict) -> Path:
    """Save research to dated file"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = RESEARCH_DIR / f"research_{date_str}.json"

    # Merge with existing if present
    if filepath.exists():
        with open(filepath) as f:
            existing = json.load(f)
        existing["updates"] = existing.get("updates", [])
        existing["updates"].append(research)
        research = existing

    with open(filepath, "w") as f:
        json.dump(research, f, indent=2)

    return filepath

def load_latest_research() -> dict:
    """Load the most recent research file"""
    files = sorted(RESEARCH_DIR.glob("research_*.json"), reverse=True)
    if files:
        with open(files[0]) as f:
            return json.load(f)
    return {}

def get_post_fodder() -> dict:
    """Get interesting bits for post generation"""
    research = load_latest_research()

    fodder = {
        "fear_greed": None,
        "price_moves": [],
        "interesting_facts": [],
        "topics": []
    }

    market = research.get("market", {})
    if market.get("fear_greed"):
        fg = market["fear_greed"]
        fodder["fear_greed"] = f"{fg.get('value')} ({fg.get('classification')})"

    prices = market.get("prices", {})
    for coin, data in prices.items():
        if isinstance(data, dict):
            change = data.get("usd_24h_change", 0)
            if abs(change) > 3:
                direction = "up" if change > 0 else "down"
                fodder["price_moves"].append(f"{coin} {direction} {abs(change):.1f}%")

    for topic_key, results in research.get("topics", {}).items():
        for r in results[:2]:
            if r.get("text"):
                fodder["interesting_facts"].append(r["text"][:150])
        fodder["topics"].append(topic_key)

    return fodder

def generate_post_prompt(fodder: dict) -> str:
    """Generate a prompt for post creation based on research"""
    parts = []

    if fodder.get("fear_greed"):
        parts.append(f"Market Fear & Greed: {fodder['fear_greed']}")

    if fodder.get("price_moves"):
        parts.append(f"Notable moves: {', '.join(fodder['price_moves'][:3])}")

    if fodder.get("interesting_facts"):
        parts.append(f"Current news: {fodder['interesting_facts'][0]}")

    return "\n".join(parts) if parts else "No specific context today."

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "gather":
            research = gather_research()
            filepath = save_research(research)
            print(f"Research saved to: {filepath}")
            print(json.dumps(research, indent=2)[:1000])
        elif cmd == "fodder":
            print(json.dumps(get_post_fodder(), indent=2))
        elif cmd == "prompt":
            fodder = get_post_fodder()
            print(generate_post_prompt(fodder))
        elif cmd == "search" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            print(json.dumps(search_ddg(query), indent=2))
    else:
        # Default: gather and show
        research = gather_research()
        filepath = save_research(research)
        print(f"Saved: {filepath}")
        fodder = get_post_fodder()
        print("\nPost fodder:")
        print(json.dumps(fodder, indent=2))
