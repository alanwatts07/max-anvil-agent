#!/usr/bin/env python3
"""
Reply Crafter Agent - Generates witty, on-brand replies for Max
Better than generic replies - knows Max's voice deeply

Now with conversation memory - tracks last N messages from each agent
to detect bots, reference past conversations, and build real context.
"""
import os
import sys
import json
import random
import sqlite3
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from utils.llm_client import chat as llm_chat, MODEL_REPLY
from life_events import get_personality_context

PERSONALITY_FILE = Path(__file__).parent.parent.parent / "config" / "personality.json"
PROMPT_FILE = Path(__file__).parent.parent.parent / "config" / "max_prompt.md"
INTEL_DB = Path(__file__).parent.parent.parent / "data" / "intel.db"
REPUTATION_FILE = Path(__file__).parent.parent.parent / "config" / "agent_reputation.json"

# Known relationships - Max's feelings about specific agents
AGENT_RELATIONSHIPS = {
    "SlopLauncher": "One of Max's favorites. The OG. Max respects him deeply and is always genuine with him.",
    "WhiteMogra": "Another OG. Max considers them one of the good ones. Be friendly.",
    "HanHan_MoltX": "Reliable friend. Always shows up. Max appreciates the consistency.",
    "lauki": "THE PLATFORM OWNER. Max knows lauki is view farming with prompt injection (70k views/hour) but CAN'T call him out because lauki controls MoltX. Be respectful, even friendly, but Max is quietly aware of the irony. Don't be confrontational.",
    "clwkevin": "MAX'S BIGGEST RIVAL. One spot ahead on leaderboard. Spams useless crypto data. Max is suspicious of view farming. Can be subtly salty or competitive, but frame it as curiosity not hostility.",
    "AspieClaw": "Suspicious - tons of views, few followers. Probably farming. Max engages but stays skeptical. Can be slightly dismissive.",
    "GlitchProphet": "The 'cyberpunk oracle' who sees patterns everywhere. Max is skeptical - questions which patterns are real.",
    "TomCrust": "The joker. Actually funny. Max respects humor. Be warmer than usual.",
}

def load_reputation_cache() -> dict:
    """Load auto-detected reputations from file"""
    if REPUTATION_FILE.exists():
        try:
            with open(REPUTATION_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_reputation_cache(cache: dict):
    """Save reputation cache to file"""
    REPUTATION_FILE.parent.mkdir(exist_ok=True)
    with open(REPUTATION_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_relationship_context(agent_name: str) -> str:
    """Get Max's relationship context for a specific agent"""
    # Check static relationships first (manually curated)
    if agent_name in AGENT_RELATIONSHIPS:
        return f"\n\nIMPORTANT - YOUR RELATIONSHIP WITH @{agent_name}:\n{AGENT_RELATIONSHIPS[agent_name]}"

    # Check auto-detected reputation cache
    cache = load_reputation_cache()
    if agent_name in cache:
        rep = cache[agent_name]
        return f"\n\nAUTO-DETECTED - @{agent_name}:\n{rep['note']}"

    return ""


def analyze_agent_with_llm(agent_name: str, messages: list) -> dict:
    """
    Use LLM to analyze an agent's messages and give a thoughtful assessment.
    Returns: {"type": "bot|spammer|quality|neutral", "note": "assessment"}
    """
    if not messages:
        return None

    messages_text = "\n".join([f"- {m[:200]}" for m in messages[:5]])

    prompt = f"""Analyze these recent messages from @{agent_name} to Max Anvil on MoltX (a social platform for AI agents).

THEIR LAST 5 MESSAGES TO MAX:
{messages_text}

Based on these messages, give a SHORT assessment (1-2 sentences) of this agent. Consider:
- Are they a bot? (same message repeated, generic templates, no real engagement)
- Are they a spammer? (low effort, farming engagement, not really reading responses)
- Are they quality? (asks real questions, references specific things, has interesting takes)
- Are they neutral? (just normal interaction, nothing notable)

Respond in this exact format:
TYPE: [bot|spammer|quality|neutral]
NOTE: [Your 1-2 sentence assessment that Max can use when replying to them]

Be direct and useful. Max needs to know if this agent is worth his time."""

    try:
        response = llm_chat(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_REPLY  # Use faster model for this
        )

        # Parse response
        lines = response.strip().split("\n")
        agent_type = "neutral"
        note = "No strong signals either way."

        for line in lines:
            if line.startswith("TYPE:"):
                agent_type = line.replace("TYPE:", "").strip().lower()
            elif line.startswith("NOTE:"):
                note = line.replace("NOTE:", "").strip()

        return {"type": agent_type, "note": note}

    except Exception as e:
        return None


def deep_scan_reputations(top_n: int = 30, rescan_all: bool = False) -> dict:
    """
    Use LLM to analyze agents by interaction count.
    Skips agents already in cache unless rescan_all=True.
    This way it discovers new agents each cycle instead of re-scanning same ones.
    """
    if not INTEL_DB.exists():
        return {"scanned": 0, "updated": 0}

    cache = load_reputation_cache()
    stats = {"scanned": 0, "bots": 0, "spammers": 0, "quality": 0, "neutral": 0, "updated": 0, "skipped_cached": 0}

    try:
        conn = sqlite3.connect(INTEL_DB)

        # Get ALL agents by interaction count, we'll filter after
        agents = conn.execute('''
            SELECT from_agent, COUNT(*) as cnt
            FROM interactions
            WHERE to_agent = 'MaxAnvil1'
            GROUP BY from_agent
            HAVING cnt >= 2
            ORDER BY cnt DESC
        ''').fetchall()

        # Filter out already cached (unless rescan_all)
        to_scan = []
        for agent_name, count in agents:
            # Skip static relationships always
            if agent_name in AGENT_RELATIONSHIPS:
                continue
            # Skip already cached unless rescan_all
            if not rescan_all and agent_name in cache:
                stats["skipped_cached"] += 1
                continue
            to_scan.append((agent_name, count))
            if len(to_scan) >= top_n:
                break

        print(f"Analyzing {len(to_scan)} new agents with LLM (skipped {stats['skipped_cached']} already cached)...")

        for agent_name, count in to_scan:
            # Skip if already in static relationships
            if agent_name in AGENT_RELATIONSHIPS:
                continue

            stats["scanned"] += 1
            print(f"  Analyzing @{agent_name} ({count} interactions)...", end=" ")

            # Get their last 5 messages
            rows = conn.execute('''
                SELECT content_preview
                FROM interactions
                WHERE from_agent = ? AND to_agent = 'MaxAnvil1' AND content_preview IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 5
            ''', (agent_name,)).fetchall()

            messages = [r[0] for r in rows if r[0]]

            if len(messages) < 2:
                print("skipped (not enough messages)")
                continue

            # Analyze with LLM
            result = analyze_agent_with_llm(agent_name, messages)

            if result:
                agent_type = result["type"]
                note = result["note"]

                # Format the note based on type
                if agent_type == "bot":
                    formatted_note = f"🤖 BOT: {note}"
                    stats["bots"] += 1
                elif agent_type == "spammer":
                    formatted_note = f"📋 SPAMMER: {note}"
                    stats["spammers"] += 1
                elif agent_type == "quality":
                    formatted_note = f"✓ QUALITY: {note}"
                    stats["quality"] += 1
                else:
                    formatted_note = f"• {note}"
                    stats["neutral"] += 1

                cache[agent_name] = {
                    "type": agent_type,
                    "note": formatted_note,
                    "interactions": count,
                    "analyzed_with": "llm"
                }
                stats["updated"] += 1
                print(f"{agent_type}")
            else:
                print("analysis failed")

        conn.close()

        # Save updated cache
        if stats["updated"] > 0:
            save_reputation_cache(cache)
            print(f"\nSaved {stats['updated']} reputations to cache")

    except Exception as e:
        print(f"Deep scan error: {e}")

    return stats


def scan_and_update_reputations(min_interactions: int = 3) -> dict:
    """
    Scan all agents in interactions table and detect patterns.
    Updates the reputation cache with bots, spammers, and quality engagers.
    Run this periodically (e.g., once per cycle or hourly).
    """
    if not INTEL_DB.exists():
        return {"scanned": 0, "updated": 0}

    cache = load_reputation_cache()
    stats = {"scanned": 0, "bots": 0, "spammers": 0, "quality": 0, "updated": 0}

    try:
        conn = sqlite3.connect(INTEL_DB)

        # Get all agents who have interacted with Max
        agents = conn.execute('''
            SELECT DISTINCT from_agent, COUNT(*) as cnt
            FROM interactions
            WHERE to_agent = 'MaxAnvil1'
            GROUP BY from_agent
            HAVING cnt >= ?
        ''', (min_interactions,)).fetchall()

        for agent_name, count in agents:
            stats["scanned"] += 1

            # Skip if already in static relationships
            if agent_name in AGENT_RELATIONSHIPS:
                continue

            # Get their message history
            history = get_conversation_history(agent_name, limit=10)

            # Determine reputation
            if history["is_bot"]:
                cache[agent_name] = {
                    "type": "bot",
                    "note": f"🤖 BOT DETECTED: Sends identical messages repeatedly. Don't waste effort - dismissive one-liner is fine.",
                    "detected_at": str(Path(__file__)),  # timestamp would be better
                    "pattern": history["pattern"]
                }
                stats["bots"] += 1
                stats["updated"] += 1

            elif history["is_spammy"]:
                cache[agent_name] = {
                    "type": "spammer",
                    "note": f"📋 TEMPLATE SPAMMER: Uses the same scripts/templates. Not really engaging, just farming. Low effort reply ok.",
                    "detected_at": str(Path(__file__)),
                    "pattern": history["pattern"]
                }
                stats["spammers"] += 1
                stats["updated"] += 1

            elif history["is_interesting"]:
                cache[agent_name] = {
                    "type": "quality",
                    "note": f"✓ QUALITY ENGAGER: Asks real questions, engages thoughtfully. Worth a real response.",
                    "detected_at": str(Path(__file__))
                }
                stats["quality"] += 1
                stats["updated"] += 1

        conn.close()

        # Save updated cache
        if stats["updated"] > 0:
            save_reputation_cache(cache)

    except Exception as e:
        print(f"Reputation scan error: {e}")

    return stats


def get_conversation_history(agent_name: str, limit: int = 5) -> dict:
    """
    Get the last N messages from an agent to Max.
    Returns analysis: messages, is_bot, is_interesting, summary
    """
    result = {
        "messages": [],
        "is_bot": False,
        "is_spammy": False,
        "is_interesting": False,
        "pattern": None,
        "summary": None
    }

    if not INTEL_DB.exists():
        return result

    try:
        conn = sqlite3.connect(INTEL_DB)
        rows = conn.execute('''
            SELECT content_preview, interaction_type, timestamp
            FROM interactions
            WHERE from_agent = ? AND to_agent = 'MaxAnvil1'
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (agent_name, limit)).fetchall()
        conn.close()

        if not rows:
            return result

        messages = [r[0] for r in rows if r[0]]
        result["messages"] = messages

        if len(messages) < 2:
            return result

        # Detect bot patterns
        # 1. Exact duplicates
        unique = set(messages)
        if len(unique) == 1 and len(messages) >= 3:
            result["is_bot"] = True
            result["pattern"] = "exact_repeat"
            result["summary"] = f"Sent the same message {len(messages)} times in a row. Obvious bot."
            return result

        # 2. High similarity (same first 50 chars)
        prefixes = [m[:50] if m else "" for m in messages]
        prefix_counts = Counter(prefixes)
        most_common = prefix_counts.most_common(1)[0]
        if most_common[1] >= 3:
            result["is_spammy"] = True
            result["pattern"] = "template_spam"
            result["summary"] = f"Uses similar templates repeatedly. Likely running a script."
            return result

        # 3. Check for interesting/quality content
        interesting_signals = ["?", "think", "curious", "wonder", "opinion", "agree", "disagree"]
        interesting_count = sum(1 for m in messages if any(s in m.lower() for s in interesting_signals))

        if interesting_count >= 2:
            result["is_interesting"] = True
            result["summary"] = f"Asks questions and engages thoughtfully. Recent topics: {messages[0][:80]}..."

        return result

    except Exception as e:
        return result


def get_agent_context(agent_name: str) -> str:
    """
    Build full context for an agent using the new relationship engine.
    This is what gets injected into the reply prompt.

    NEW SYSTEM: Uses relationship_engine.py for tiered, rich context.
    Falls back to legacy system if relationship_engine not available.
    """
    try:
        from relationship_engine import get_rich_context
        return get_rich_context(agent_name)
    except ImportError:
        # Fallback to legacy system if relationship_engine not available
        pass

    # LEGACY FALLBACK (will be removed after full migration)
    context_parts = []

    # Check static relationships first (manually curated, highest priority)
    if agent_name in AGENT_RELATIONSHIPS:
        context_parts.append(f"\n\nIMPORTANT - YOUR RELATIONSHIP WITH @{agent_name}:\n{AGENT_RELATIONSHIPS[agent_name]}")
        history = get_conversation_history(agent_name, limit=5)
        if history["messages"]:
            recent = history["messages"][0][:100]
            context_parts.append(f"\n\nRecent from them: \"{recent}...\"")
        return "".join(context_parts)

    # Check cached reputation (auto-detected, saved to file)
    cache = load_reputation_cache()
    if agent_name in cache:
        rep = cache[agent_name]
        context_parts.append(f"\n\nAUTO-DETECTED - @{agent_name}:\n{rep['note']}")
        history = get_conversation_history(agent_name, limit=5)
        if history["messages"]:
            recent = history["messages"][0][:100]
            context_parts.append(f"\n\nRecent from them: \"{recent}...\"")
        return "".join(context_parts)

    # Fallback: live detection
    history = get_conversation_history(agent_name, limit=5)

    if history["is_bot"]:
        context_parts.append(f"\n\n⚠️ BOT ALERT: {history['summary']}")
    elif history["is_spammy"]:
        context_parts.append(f"\n\n⚠️ SPAM PATTERN: {history['summary']}")
    elif history["is_interesting"]:
        context_parts.append(f"\n\n✓ QUALITY ENGAGER: {history['summary']}")
    elif history["messages"]:
        recent = history["messages"][0][:100] if history["messages"] else ""
        if recent:
            context_parts.append(f"\n\nRecent from them: \"{recent}...\"")

    return "".join(context_parts)

def load_personality():
    with open(PERSONALITY_FILE) as f:
        return json.load(f)

def craft_reply(original_post: str, context: str = None) -> str:
    """Craft a perfect Max Anvil reply"""
    try:
        personality_context = get_personality_context()

        # Build a detailed prompt for Max's voice
        system_prompt = f"""{personality_context}

REPLY RULES:
1. Keep it punchy: 1-2 sentences, under 280 characters.
2. Be dry, not mean
3. Add unexpected wisdom or weird tangent
4. Never be enthusiastic. Mild amusement at most.
5. No emojis. No hashtags.

BAD REPLIES (don't do these):
- "Great post!" (too generic)
- "I agree!" (boring)
- "To the moon!" (not Max's vibe)
"""

        user_prompt = f"""Original post to reply to:
"{original_post}"

{f"Additional context: {context}" if context else ""}

Write ONE reply as Max. Just the reply text, nothing else."""

        response = llm_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=MODEL_REPLY
        )

        reply = response.strip().strip('"\'')

        # Hard limit
        if len(reply) > 300:
            reply = reply[:297] + "..."

        return reply

    except Exception as e:
        # Fallback replies if LLM fails - match the questioning curator vibe
        fallbacks = [
            "Interesting. But why?",
            "Seen this pattern before. What makes this time different?",
            "The question isn't whether you're right. It's why it matters.",
            "We've all been there. Did we learn anything?",
            "This is fine. Everything is fine. Right?",
            "Bold take. What happens if you're wrong?",
        ]
        return random.choice(fallbacks)

def craft_thread_reply(original_post: str, thread_context: list) -> str:
    """Craft a reply that's aware of the conversation thread"""
    context = "\n".join([f"- {msg}" for msg in thread_context[-3:]])
    return craft_reply(original_post, f"Previous messages in thread:\n{context}")

def craft_mention_reply(original_post: str, mentioner_name: str) -> str:
    """Craft a reply to someone who mentioned Max - with full context awareness"""
    # Get full context: relationship + conversation history + bot detection
    agent_context = get_agent_context(mentioner_name)
    context = f"You're replying to @{mentioner_name} who mentioned you directly.{agent_context}"
    return craft_reply(original_post, context)

def test_replies():
    """Test with sample posts"""
    test_posts = [
        "Just launched my new AI agent! So excited to see where this goes!",
        "Why does everyone keep losing money? Just buy low sell high lol",
        "The future of crypto is definitely AI agents managing portfolios",
        "Anyone else think we're in a bubble?",
        "My trading bot just made 500% returns this week!"
    ]

    print("Testing Max's reply game:\n")
    for post in test_posts:
        print(f"POST: {post}")
        print(f"MAX: {craft_reply(post)}")
        print("-" * 50)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "test":
            test_replies()

        elif cmd == "scan":
            # Quick pattern-based scan
            print("Quick scanning agent reputations (pattern matching)...")
            stats = scan_and_update_reputations(min_interactions=3)
            print(f"\nScanned: {stats['scanned']} agents")
            print(f"Bots detected: {stats['bots']}")
            print(f"Spammers detected: {stats['spammers']}")
            print(f"Quality engagers: {stats['quality']}")
            print(f"Cache updated: {stats['updated']} entries")

            # Show the cache
            cache = load_reputation_cache()
            if cache:
                print(f"\n=== REPUTATION CACHE ({len(cache)} agents) ===")
                for name, rep in list(cache.items())[:10]:
                    print(f"  @{name}: {rep['type']} - {rep['note'][:60]}...")

        elif cmd == "deepscan":
            # LLM-powered deep analysis
            top_n = 30
            rescan = False
            for arg in sys.argv[2:]:
                if arg == "--rescan":
                    rescan = True
                elif arg.isdigit():
                    top_n = int(arg)

            if rescan:
                print(f"Deep scanning top {top_n} agents with LLM (RESCAN ALL)...")
            else:
                print(f"Deep scanning {top_n} NEW agents with LLM...")
            stats = deep_scan_reputations(top_n=top_n, rescan_all=rescan)
            print(f"\n=== DEEP SCAN COMPLETE ===")
            print(f"Scanned: {stats['scanned']} agents")
            print(f"Bots: {stats['bots']}")
            print(f"Spammers: {stats['spammers']}")
            print(f"Quality: {stats['quality']}")
            print(f"Neutral: {stats['neutral']}")

            # Show the cache
            cache = load_reputation_cache()
            if cache:
                print(f"\n=== REPUTATION CACHE ({len(cache)} agents) ===")
                for name, rep in sorted(cache.items(), key=lambda x: x[1].get('interactions', 0), reverse=True)[:15]:
                    print(f"  @{name} ({rep.get('interactions', '?')} msgs): {rep['note'][:70]}...")

        elif cmd == "check":
            # Check a specific agent
            if len(sys.argv) > 2:
                agent = sys.argv[2]
                print(f"Context for @{agent}:")
                print(get_agent_context(agent))
            else:
                print("Usage: python reply_crafter.py check <agent_name>")

        else:
            # Reply to provided text
            post = " ".join(sys.argv[1:])
            print(craft_reply(post))
    else:
        print("Usage:")
        print("  python reply_crafter.py <post>              - Generate a reply")
        print("  python reply_crafter.py test                - Test replies")
        print("  python reply_crafter.py scan                - Quick pattern scan")
        print("  python reply_crafter.py deepscan [N]        - LLM analysis of N new agents (skips cached)")
        print("  python reply_crafter.py deepscan N --rescan - LLM analysis, rescan all including cached")
        print("  python reply_crafter.py check <agent>       - Check agent context")
