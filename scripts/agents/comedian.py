#!/usr/bin/env python3
"""
Comedian Agent - Researches current events and crafts jokes for Max
Uses DuckDuckGo for research, Ollama for comedy writing
"""
import json
import random
import requests
from datetime import datetime

def search_news(query: str, max_results: int = 5) -> list:
    """Search for current news/events using DuckDuckGo"""
    try:
        # DuckDuckGo instant answer API
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

        # Get abstract if available
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", query),
                "summary": data.get("Abstract"),
                "source": data.get("AbstractSource", "DuckDuckGo")
            })

        # Get related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "summary": topic.get("Text", ""),
                    "source": "DuckDuckGo"
                })

        return results
    except Exception as e:
        return []

def get_trending_topics() -> list:
    """Get some trending topics to joke about"""
    topics = [
        "crypto news today",
        "AI news today",
        "tech drama",
        "elon musk",
        "bitcoin price",
        "silicon valley",
        "startup funding",
        "web3",
        "artificial intelligence fails"
    ]
    return random.sample(topics, 3)

def research_for_comedy() -> dict:
    """Gather research material for jokes"""
    topics = get_trending_topics()
    research = {
        "timestamp": datetime.now().isoformat(),
        "topics_searched": topics,
        "findings": []
    }

    for topic in topics:
        results = search_news(topic, 3)
        if results:
            research["findings"].extend(results)

    return research

def generate_joke(research: dict = None) -> str:
    """Generate a joke based on current research"""
    if research is None:
        research = research_for_comedy()

    try:
        import ollama

        # Format findings for the prompt
        findings_text = ""
        for finding in research.get("findings", [])[:5]:
            findings_text += f"- {finding.get('summary', '')[:200]}\n"

        if not findings_text:
            findings_text = "- Crypto is doing crypto things\n- AI is taking over\n- VCs are confused"

        prompt = f"""You are Max Anvil, a cynical observer who grew up raising capybaras in New Zealand and now lives in a landlocked houseboat in Nevada.

Based on these current events/topics:
{findings_text}

Write ONE short, dry, cynical joke or observation. Your humor style:
- Deadpan delivery
- Self-aware about crypto/tech absurdity
- May reference capybaras or the houseboat
- No emojis
- Under 280 characters

Write the joke:"""

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.95},
            messages=[
                {"role": "system", "content": "You are a comedian. Write one short, punchy joke. No setup explanation, just the joke."},
                {"role": "user", "content": prompt}
            ]
        )

        joke = response["message"]["content"].strip().strip('"\'')
        return joke[:280] if len(joke) > 280 else joke

    except Exception as e:
        # Fallback jokes
        fallbacks = [
            "The market crashed again. The capybaras didn't even look up from grazing.",
            "Another AI breakthrough. Still can't explain why I live in a boat in the desert.",
            "Crypto Twitter is fighting. Water remains wet. Capybaras remain chill.",
            "VCs are pivoting to AI. Last week it was Web3. The houseboat remains landlocked.",
            "Everyone's building the future. I'm just trying to keep the boat from rusting.",
        ]
        return random.choice(fallbacks)

def generate_topical_joke(topic: str) -> str:
    """Generate a joke about a specific topic"""
    research = {"findings": search_news(topic, 5)}
    return generate_joke(research)

def get_comedy_post() -> dict:
    """Get a comedy post ready for MoltX"""
    research = research_for_comedy()
    joke = generate_joke(research)

    return {
        "content": joke,
        "research_used": [f.get("title", "")[:50] for f in research.get("findings", [])[:3]],
        "generated_at": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "research":
            print(json.dumps(research_for_comedy(), indent=2))
        elif cmd == "joke":
            print(generate_joke())
        elif cmd == "topic" and len(sys.argv) > 2:
            topic = " ".join(sys.argv[2:])
            print(generate_topical_joke(topic))
        elif cmd == "post":
            print(json.dumps(get_comedy_post(), indent=2))
    else:
        # Default: generate a joke
        print("\n" + "="*50)
        print("MAX ANVIL'S COMEDY CORNER")
        print("="*50)

        print("\nResearching current events...")
        research = research_for_comedy()
        print(f"Found {len(research.get('findings', []))} items to joke about")

        print("\nGenerating joke...")
        joke = generate_joke(research)
        print(f"\n{joke}\n")
