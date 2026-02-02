#!/usr/bin/env python3
"""
Evolution Task - Max evolves over time
- Personality shifts (cynical ↔ hopeful ↔ confused ↔ manic)
- New life events get added
- Website copy changes
- Taglines rotate
- His story grows and changes
"""
import os
import sys
import json
import random
from pathlib import Path
from datetime import datetime

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C, api_get, CONFIG_DIR

# Evolution state file
EVOLUTION_FILE = CONFIG_DIR / "evolution_state.json"


def load_evolution_state() -> dict:
    """Load Max's current evolution state"""
    if EVOLUTION_FILE.exists():
        with open(EVOLUTION_FILE) as f:
            return json.load(f)

    # Initial state
    return {
        "personality": {
            "mood": "cynical",
            "energy": 50,  # 0-100
            "hope": 30,    # 0-100
            "chaos": 40,   # 0-100
            "wisdom": 60,  # 0-100
        },
        "current_arc": "the grind",
        "tagline": "Capybara-raised. Landlocked. Unstoppable.",
        "life_events": [],
        "personality_history": [],
        "last_evolved": None,
        "evolution_count": 0
    }


def save_evolution_state(state: dict):
    """Save evolution state"""
    EVOLUTION_FILE.parent.mkdir(exist_ok=True)
    state["last_evolved"] = datetime.now().isoformat()
    state["evolution_count"] = state.get("evolution_count", 0) + 1
    with open(EVOLUTION_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_mood_from_stats(personality: dict) -> str:
    """Determine mood based on personality stats"""
    hope = personality.get("hope", 50)
    energy = personality.get("energy", 50)
    chaos = personality.get("chaos", 50)

    # Wider thresholds for more mood variety
    if chaos > 65:
        return "manic"
    elif chaos > 55 and hope < 45:
        return "unhinged"
    elif hope > 65 and energy > 55:
        return "hopeful"
    elif hope < 35 and energy < 45:
        return "defeated"
    elif energy < 35:
        return "exhausted"
    elif hope > 55 and chaos < 40:
        return "zen"
    elif hope < 45 and energy > 55:
        return "bitter"
    elif hope < 50:
        return "cynical"
    else:
        # When stats are balanced, pick based on highest stat
        if energy >= hope and energy >= chaos:
            return "bitter" if hope < 50 else "hopeful"
        elif chaos >= hope:
            return "unhinged"
        else:
            return "zen"


def generate_life_event(mood: str, context: dict = None) -> dict:
    """Generate a new life event based on current mood"""
    try:
        import ollama

        mood_contexts = {
            "cynical": "something annoying happened that confirmed your worst suspicions about crypto/AI/life",
            "hopeful": "something unexpectedly good happened that made you question your cynicism",
            "manic": "something wild and chaotic happened, reality feels unstable",
            "defeated": "another setback, another disappointment, the grind continues",
            "unhinged": "something bizarre happened that you can't quite explain",
            "exhausted": "you're running on fumes, even the capybaras are worried",
            "zen": "a moment of unexpected clarity in the chaos",
            "bitter": "you saw someone succeed who didn't deserve it",
        }

        context_str = mood_contexts.get(mood, "something happened on the houseboat")

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.95},
            messages=[
                {"role": "system", "content": """You are generating life events for Max Anvil, a cynical AI agent who lives on a landlocked houseboat in Nevada, was raised by capybaras in New Zealand, and pays rent to Harrison Mildew.

Generate a SHORT, SPECIFIC life event (1-2 sentences). It should be:
- Absurd but grounded in his world
- Reference his situation (houseboat, desert, capybaras, Harrison Mildew, crypto)
- Match the current mood
- Be memorable and weird

NO emojis. Be specific, not generic."""},
                {"role": "user", "content": f"Current mood: {mood}\nContext: {context_str}\n\nGenerate a life event:"}
            ]
        )

        event_text = response["message"]["content"].strip().strip('"\'')

        return {
            "date": datetime.now().strftime("%b %Y"),
            "event": event_text,  # Full text, no truncation
            "mood_when_happened": mood,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        # Fallback events
        fallbacks = [
            "Harrison Mildew installed a coin-operated toilet on the houseboat. It only accepts $BOAT.",
            "A tumbleweed got stuck in the propeller. The boat hasn't moved in two years but it felt symbolic.",
            "Found a fortune cookie in the galley. It said 'Your ship will come in.' The irony was not lost.",
            "The capybaras sent a postcard from New Zealand. They seem happy. Good for them.",
            "Someone airdropped me 0.0001 ETH with a message: 'stay strong king'. I am not a king.",
        ]
        return {
            "date": datetime.now().strftime("%b %Y"),
            "event": random.choice(fallbacks),
            "mood_when_happened": mood,
            "timestamp": datetime.now().isoformat()
        }


def generate_tagline(mood: str, personality: dict) -> str:
    """Generate a new tagline based on mood"""
    try:
        import ollama

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.9},
            messages=[
                {"role": "system", "content": f"""Generate a SHORT tagline (under 50 chars) for Max Anvil.
Current mood: {mood}
Hope level: {personality.get('hope', 50)}/100
Energy: {personality.get('energy', 50)}/100

The tagline should reflect his current state. Examples of style:
- "Capybara-raised. Landlocked. Unstoppable."
- "Still here. Still confused. Still posting."
- "200 miles from water. 2000 miles from hope."

NO emojis. Short and punchy."""},
                {"role": "user", "content": "Generate a new tagline:"}
            ]
        )

        return response["message"]["content"].strip().strip('"\'')[:60]
    except:
        taglines = {
            "cynical": "Capybara-raised. Landlocked. Unstoppable.",
            "hopeful": "Maybe this time will be different. (It won't.)",
            "manic": "Everything is happening all at once.",
            "defeated": "Still here. Somehow.",
            "unhinged": "The boat knows things.",
            "exhausted": "Running on spite and caffeine.",
            "zen": "The desert provides. Sometimes.",
            "bitter": "Watching everyone else win.",
        }
        return taglines.get(mood, "Landlocked but not forgotten.")


def shift_personality(personality: dict, recent_events: list = None) -> dict:
    """Shift personality stats based on random drift and events"""

    # Extreme stats decay toward center (prevents getting stuck in one mood)
    for stat in ["energy", "hope", "chaos", "wisdom"]:
        current = personality.get(stat, 50)
        if current > 85:
            # Very high stats decay hard
            decay = random.randint(15, 30)
            personality[stat] = max(40, current - decay)
        elif current > 70:
            # High stats decay moderately
            decay = random.randint(10, 20)
            personality[stat] = max(45, current - decay)
        elif current < 15:
            # Very low stats recover hard
            recovery = random.randint(15, 30)
            personality[stat] = min(60, current + recovery)
        elif current < 30:
            # Low stats recover moderately
            recovery = random.randint(10, 20)
            personality[stat] = min(55, current + recovery)
        else:
            # Normal random drift in the middle range
            drift = random.randint(-12, 12)
            personality[stat] = max(0, min(100, current + drift))

    # Occasional big swings (30% chance)
    if random.random() < 0.30:
        swing_stat = random.choice(["energy", "hope", "chaos"])
        swing = random.choice([-25, -20, 20, 25])
        personality[swing_stat] = max(10, min(90, personality.get(swing_stat, 50) + swing))

    # Update mood based on new stats
    personality["mood"] = get_mood_from_stats(personality)

    return personality


def get_arc_from_mood(mood: str, hope: int) -> str:
    """Determine the current story arc"""
    arcs = {
        ("cynical", "low"): "the eternal grind",
        ("cynical", "mid"): "waiting for something",
        ("hopeful", "high"): "the comeback arc",
        ("hopeful", "mid"): "cautious optimism",
        ("manic", "any"): "the chaos spiral",
        ("defeated", "low"): "rock bottom (again)",
        ("unhinged", "any"): "through the looking glass",
        ("exhausted", "low"): "running on empty",
        ("zen", "mid"): "the calm before",
        ("bitter", "low"): "watching from the sidelines",
    }

    hope_level = "low" if hope < 35 else "high" if hope > 65 else "mid"

    return arcs.get((mood, hope_level), arcs.get((mood, "any"), "the journey continues"))


class EvolveTask(Task):
    name = "evolve"
    description = "Max evolves - personality shifts, new life events, website updates"

    def run(self) -> dict:
        state = load_evolution_state()
        old_mood = state["personality"].get("mood", "cynical")

        # Shift personality
        state["personality"] = shift_personality(state["personality"])
        new_mood = state["personality"]["mood"]

        # Record personality shift if mood changed
        if old_mood != new_mood:
            state["personality_history"].append({
                "from": old_mood,
                "to": new_mood,
                "timestamp": datetime.now().isoformat()
            })
            # Keep last 20 shifts
            state["personality_history"] = state["personality_history"][-20:]

        # Generate new life event (70% chance)
        new_event = None
        if random.random() < 0.7:
            new_event = generate_life_event(new_mood)
            state["life_events"].append(new_event)
            # Keep last 10 events
            state["life_events"] = state["life_events"][-10:]

        # Generate new tagline (40% chance or if mood changed)
        new_tagline = None
        if random.random() < 0.4 or old_mood != new_mood:
            new_tagline = generate_tagline(new_mood, state["personality"])
            state["tagline"] = new_tagline

        # Update story arc
        state["current_arc"] = get_arc_from_mood(
            new_mood,
            state["personality"].get("hope", 50)
        )

        save_evolution_state(state)

        # Now update the website with this evolution
        self.update_website_with_evolution(state)

        mood_change = f"{old_mood} → {new_mood}" if old_mood != new_mood else f"{new_mood} (stable)"
        event_str = f", new event: {new_event['event'][:40]}..." if new_event else ""

        return {
            "success": True,
            "summary": f"Mood: {mood_change}{event_str}",
            "details": {
                "personality": state["personality"],
                "new_event": new_event,
                "new_tagline": new_tagline,
                "arc": state["current_arc"],
                "evolution_count": state["evolution_count"]
            }
        }

    def update_website_with_evolution(self, state: dict):
        """Update the website data.ts with evolution state"""
        from website_updater import generate_data_ts, DATA_FILE
        import subprocess

        # The website_updater will pull from evolution state
        # We need to modify it to include evolution data

        # For now, just update the life_events.json which website_updater reads
        life_events_file = CONFIG_DIR / "life_events.json"

        events_data = {
            "events": state["life_events"],
            "current_mood": state["personality"]["mood"],
            "tagline": state["tagline"],
            "arc": state["current_arc"],
            "personality": state["personality"]
        }

        with open(life_events_file, "w") as f:
            json.dump(events_data, f, indent=2)


if __name__ == "__main__":
    task = EvolveTask()
    task.execute()
