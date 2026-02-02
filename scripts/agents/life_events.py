#!/usr/bin/env python3
"""
Life Events Agent - Finds weird news and injects it into Max's life story
Searches for absurd celebrity/world events and adapts them as Max's experiences
"""
import os
import json
import random
import requests
from pathlib import Path
from datetime import datetime

PROMPT_FILE = Path(__file__).parent.parent.parent / "config" / "max_prompt.md"
EVENTS_LOG = Path(__file__).parent.parent.parent / "config" / "life_events.json"

def search_weird_news() -> list:
    """Search for weird/funny news that could become Max's life events"""
    queries = [
        "weird news today",
        "florida man",
        "celebrity awkward moment",
        "bizarre accident",
        "strange discovery",
        "weird animal news",
        "tech fail news",
        "crypto drama"
    ]

    query = random.choice(queries)

    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
            },
            timeout=10
        )
        data = response.json()

        results = []
        for topic in data.get("RelatedTopics", [])[:10]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(topic["Text"])

        return results if results else get_absurd_event_seeds()
    except:
        return get_absurd_event_seeds()

def get_absurd_event_seeds() -> list:
    """Generate seeds for absurd life events when news search fails"""
    seeds = [
        "A pelican landed on someone's car and refused to leave for three hours",
        "A crypto founder accidentally sent $2M to the wrong wallet",
        "Someone's roomba escaped and was found two blocks away",
        "A celebrity tweeted then deleted something embarrassing",
        "A man tried to pay for gas with NFTs",
        "Someone found a decades-old McDonalds meal in their wall",
        "A tech CEO got locked out of their own product",
        "A raccoon broke into a donut shop",
        "Someone's AI assistant ordered 50 pizzas by mistake",
        "A town elected a dog as mayor again",
        "A whale accidentally crashed a yacht party",
        "Someone's crypto wallet seed phrase was their wifi password",
        "A robot got stuck in a revolving door for 6 hours",
        "An influencer's apartment was actually a storage unit",
        "A man sued himself and won",
        "A cat walked across a keyboard and deployed to production",
        "Someone left a review for the moon on Google Maps",
        "A ghost was caught on camera checking crypto prices",
        "A squirrel chewed through fiber optic cables and crashed the market",
        "Someone's smart fridge started sending spam emails",
    ]
    return random.sample(seeds, min(5, len(seeds)))

def adapt_news_to_max(news_item: str) -> str:
    """Convert a news item into something that happened to Max"""
    try:
        import ollama

        prompt = f"""Take this news item and rewrite it as something that happened to Max Anvil personally.
Make it fit his character (lives in landlocked houseboat in Nevada, raised capybaras in New Zealand, cynical crypto observer).
Keep it short (1-2 sentences). Make it absurd but believable for his character.

Original news: {news_item}

Rewrite as Max's personal experience:"""

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.95},
            messages=[
                {"role": "system", "content": "You rewrite news as personal anecdotes for a fictional character. Be creative and absurd."},
                {"role": "user", "content": prompt}
            ]
        )

        return response["message"]["content"].strip().strip('"\'')
    except:
        return None

def load_events_log() -> dict:
    """Load existing life events"""
    if EVENTS_LOG.exists():
        with open(EVENTS_LOG) as f:
            return json.load(f)
    return {"events": [], "last_updated": None}

def save_events_log(log: dict):
    """Save life events log"""
    EVENTS_LOG.parent.mkdir(exist_ok=True)
    log["last_updated"] = datetime.now().isoformat()
    with open(EVENTS_LOG, "w") as f:
        json.dump(log, f, indent=2)

def add_life_event(event: str, source: str = None):
    """Add a new life event to Max's history"""
    log = load_events_log()

    event_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "event": event,
        "source": source,
        "added": datetime.now().isoformat()
    }

    log["events"].append(event_entry)

    # Keep last 50 events
    log["events"] = log["events"][-50:]

    save_events_log(log)

    # Also update the prompt file
    update_prompt_file(event)

    return event_entry

def update_prompt_file(new_event: str):
    """Add new event to the prompt markdown file"""
    if not PROMPT_FILE.exists():
        return

    content = PROMPT_FILE.read_text()

    # Find the Life Events Log section and add the new event
    date_header = datetime.now().strftime("### %B %Y")
    event_line = f"- {new_event}"

    if date_header in content:
        # Add under existing month
        content = content.replace(date_header, f"{date_header}\n{event_line}")
    else:
        # Add new month section
        content = content.rstrip() + f"\n\n{date_header}\n{event_line}\n"

    PROMPT_FILE.write_text(content)

def get_recent_events(limit: int = 5) -> list:
    """Get recent life events for context"""
    log = load_events_log()
    return log.get("events", [])[-limit:]

def generate_life_event() -> dict:
    """Find weird news and create a new life event for Max"""
    # Search for weird news
    news_items = search_weird_news()

    if not news_items:
        return None

    # Pick a random one
    original = random.choice(news_items)

    # Adapt it to Max's life
    adapted = adapt_news_to_max(original)

    if adapted:
        entry = add_life_event(adapted, original)
        return {
            "original": original,
            "adapted": adapted,
            "entry": entry
        }

    return None

def load_personality_prompt() -> str:
    """Load the full personality prompt from file"""
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text()
    return ""

def get_personality_context() -> str:
    """Get personality + recent events for post generation"""
    base_prompt = load_personality_prompt()
    recent = get_recent_events(3)

    if recent:
        events_context = "\n\nRecent life events to potentially reference:\n"
        for e in recent:
            events_context += f"- {e.get('event', '')}\n"
        return base_prompt + events_context

    return base_prompt

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "generate":
            print("Searching for weird news...")
            result = generate_life_event()
            if result:
                print(f"\nOriginal: {result['original'][:100]}...")
                print(f"\nAdapted for Max: {result['adapted']}")
                print(f"\nSaved to life events log!")
            else:
                print("No event generated")

        elif cmd == "recent":
            events = get_recent_events(10)
            print("Recent life events:")
            for e in events:
                print(f"  [{e.get('date')}] {e.get('event')}")

        elif cmd == "add" and len(sys.argv) > 2:
            event_text = " ".join(sys.argv[2:])
            add_life_event(event_text, "manual")
            print(f"Added: {event_text}")

        elif cmd == "prompt":
            print(get_personality_context())

    else:
        print("Usage:")
        print("  python life_events.py generate  - Find weird news and create life event")
        print("  python life_events.py recent    - Show recent life events")
        print("  python life_events.py add <event> - Manually add a life event")
        print("  python life_events.py prompt    - Show full personality context")
