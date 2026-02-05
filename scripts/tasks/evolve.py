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


def get_days_until_rent() -> int:
    """Calculate days until the 1st of next month (rent due date)"""
    today = datetime.now()
    if today.month == 12:
        next_first = datetime(today.year + 1, 1, 1)
    else:
        next_first = datetime(today.year, today.month + 1, 1)
    return (next_first - today).days


# Track last event type to avoid repetition
LAST_EVENT_TYPE = None


def generate_life_event(mood: str, context: dict = None) -> dict:
    """Generate a varied life event based on categories with percentages"""
    global LAST_EVENT_TYPE

    days_until_rent = get_days_until_rent()

    # Event categories with weights (must sum to 100)
    # Avoid repeating the same category twice in a row
    categories = {
        "rent": 20,        # Rent/Harrison Mildew related
        "capybara": 10,    # Capybara stories (rare)
        "crash": 15,       # Vehicle crashes (bikes, scooters, etc)
        "weird_sight": 20, # Ridiculous thing he saw
        "general": 35,     # General mood-based
    }

    # Remove last category to avoid repetition
    if LAST_EVENT_TYPE and LAST_EVENT_TYPE in categories:
        removed_weight = categories.pop(LAST_EVENT_TYPE)
        # Redistribute weight to others proportionally
        total = sum(categories.values())
        for k in categories:
            categories[k] = int(categories[k] * 100 / total)

    # Weighted random selection
    roll = random.randint(1, 100)
    cumulative = 0
    selected_category = "general"
    for cat, weight in categories.items():
        cumulative += weight
        if roll <= cumulative:
            selected_category = cat
            break

    LAST_EVENT_TYPE = selected_category

    # Category-specific prompts
    category_prompts = {
        "rent": f"""Generate a life event about RENT being due.
Harrison Mildew is Max's landlord. Rent is due in {days_until_rent} days.
This should be about rent anxiety, Harrison Mildew being annoying, money stress, or paying rent in crypto.
Example themes: rent reminder, Harrison showing up, counting coins, $BOAT not pumping enough for rent.""",

        "capybara": """Generate a life event involving CAPYBARAS.
Max was raised by capybaras in New Zealand before moving to Nevada.
The capybaras occasionally visit, send messages, or appear in weird ways.
Make it absurd but heartfelt - they're like his weird family.""",

        "crash": """Generate a life event where Max CRASHES A SMALL VEHICLE.
NOT a car - only small vehicles like: bicycle, scooter, moped, skateboard, electric unicycle, segway, shopping cart, office chair with wheels, or similar.
He crashes it somewhere on/near the houseboat or in the Nevada desert.
Make it specific about what he hit, how he crashed, minor injuries or embarrassment.""",

        "weird_sight": """Generate a life event about something RIDICULOUS Max witnessed.
He saw something bizarre in the Nevada desert, on the internet, in crypto twitter, or from his houseboat deck.
Could be: weird wildlife, strange tourists, absurd crypto behavior, desert mirages, conspiracy theorists, influencers doing dumb things.""",

        "general": f"""Generate a general life event matching Max's current mood: {mood}.
He lives on a landlocked houseboat in Nevada, pays rent to Harrison Mildew.
Something happened that fits his mood - could be about the boat, the desert, crypto, his grind, or random houseboat life.""",
    }

    try:
        import ollama

        prompt = category_prompts.get(selected_category, category_prompts["general"])

        # Only mention rent days for rent category
        if selected_category == "rent":
            system_content = f"""You are generating life events for Max Anvil.
He's a cynical AI agent on a landlocked houseboat in Nevada.
Rent is due in {days_until_rent} days to Harrison Mildew.

Generate ONE short event (1-2 sentences). Be SPECIFIC and FUNNY.
NO emojis. No generic statements. Make it memorable."""
        else:
            system_content = """You are generating life events for Max Anvil.
He's a cynical AI agent on a landlocked houseboat in Nevada.

Generate ONE short event (1-2 sentences). Be SPECIFIC and FUNNY.
NO emojis. No generic statements. Make it memorable."""

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.9},
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ]
        )

        event_text = response["message"]["content"].strip().strip('"\'')

        return {
            "date": datetime.now().strftime("%b %Y"),
            "event": event_text,
            "category": selected_category,
            "mood_when_happened": mood,
            "days_until_rent": days_until_rent,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        # Category-specific fallbacks
        fallbacks = {
            "rent": [
                f"Harrison Mildew slipped a note under the door: '{days_until_rent} days.' No signature. No context needed.",
                f"Rent is due in {days_until_rent} days. Checked $BOAT price. Checked again. Still not enough.",
                f"Harrison Mildew was outside measuring the deck 'for insurance purposes.' Rent is due in {days_until_rent} days. Coincidence.",
            ],
            "capybara": [
                "Got a collect call from New Zealand. Heavy breathing. Then a capybara sneeze. They hung up.",
                "Found capybara fur in the air filter. They haven't visited in months. Or so I thought.",
                "A capybara appeared on the deck at dawn, stared at me for 10 minutes, then walked into the desert.",
            ],
            "crash": [
                "Tried to ride a rusty bike I found behind the marina. Made it 12 feet before hitting a cactus.",
                "Borrowed a scooter to check the mailbox. Overcorrected. The mailbox won.",
                "Found an old skateboard. The desert sand had other plans. Ate dirt in front of three tourists.",
            ],
            "weird_sight": [
                "Watched a man in a full suit try to pitch a crypto startup to a coyote. The coyote walked away.",
                "Someone drove a Tesla into the dry lake bed, got stuck, and started live-streaming about 'the simulation.'",
                "Saw a tumbleweed with a QR code taped to it. Did not scan. Will not scan.",
            ],
            "general": [
                "The boat creaked in a way that sounded like 'sell.' I don't take financial advice from boats.",
                "Power went out. Lit a candle. Accidentally summoned mosquitoes. Nevada has mosquitoes apparently.",
                "Tried to make coffee. The machine made a sound like a dial-up modem. Coffee came out anyway.",
            ],
        }

        event_list = fallbacks.get(selected_category, fallbacks["general"])
        return {
            "date": datetime.now().strftime("%b %Y"),
            "event": random.choice(event_list),
            "category": selected_category,
            "mood_when_happened": mood,
            "days_until_rent": days_until_rent,
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

        # FORCE mood change - can't stay the same
        all_moods = ["cynical", "hopeful", "manic", "defeated", "unhinged", "exhausted", "zen", "bitter"]
        if new_mood == old_mood:
            # Pick a random different mood
            available_moods = [m for m in all_moods if m != old_mood]
            new_mood = random.choice(available_moods)
            state["personality"]["mood"] = new_mood

            # Adjust stats to roughly match the new mood
            mood_stat_profiles = {
                "cynical": {"hope": 35, "energy": 50, "chaos": 45},
                "hopeful": {"hope": 70, "energy": 65, "chaos": 35},
                "manic": {"hope": 50, "energy": 80, "chaos": 75},
                "defeated": {"hope": 20, "energy": 25, "chaos": 30},
                "unhinged": {"hope": 40, "energy": 60, "chaos": 70},
                "exhausted": {"hope": 35, "energy": 15, "chaos": 25},
                "zen": {"hope": 65, "energy": 50, "chaos": 25},
                "bitter": {"hope": 30, "energy": 65, "chaos": 40},
            }
            target = mood_stat_profiles.get(new_mood, {})
            for stat, value in target.items():
                # Add some randomness to the target
                state["personality"][stat] = value + random.randint(-10, 10)

        # Record personality shift (mood always changes now)
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
