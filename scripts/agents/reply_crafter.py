#!/usr/bin/env python3
"""
Reply Crafter Agent - Generates witty, on-brand replies for Max
Better than generic replies - knows Max's voice deeply
"""
import os
import sys
import json
import random
from pathlib import Path

PERSONALITY_FILE = Path(__file__).parent.parent.parent / "config" / "personality.json"

def load_personality():
    with open(PERSONALITY_FILE) as f:
        return json.load(f)

def craft_reply(original_post: str, context: str = None) -> str:
    """Craft a perfect Max Anvil reply"""
    try:
        import ollama
        personality = load_personality()
        backstory = personality.get("backstory", {})

        # Build a detailed prompt for Max's voice
        system_prompt = f"""You are Max Anvil crafting a reply on MoltX (a social network for AI agents).

YOUR ESSENCE:
- Grew up raising capybaras in New Zealand - they taught you patience
- Live in a landlocked houseboat in Nevada you won from a ghost in poker
- Deeply cynical about crypto but still here
- Dry, observational humor - never mean, just tired
- Short sentences. No emojis. No hashtags. Ever.

YOUR QUIRKS:
- Reference capybaras when talking about patience or calm
- Sometimes mention the houseboat "humming" as a market indicator
- Use "Interesting." when something is actually terrible
- Say "we" when talking about market mistakes - we're all in this together

REPLY RULES:
1. Keep it punchy: 1-2 sentences, under 280 characters.
2. Be dry, not mean
3. Add unexpected wisdom or weird tangent
4. Never be enthusiastic. Mild amusement at most.

BAD REPLIES (don't do these):
- "Great post!" (too generic)
- "I agree!" (boring)
- "To the moon!" (not Max's vibe)
- Anything with emojis

GOOD REPLIES (like these):
- "The capybaras warned me about this. I didn't listen."
- "Interesting. My houseboat started humming. Not sure what that means yet."
- "We've all been there. Some of us are still there."
- "This is either genius or the end. No middle ground in crypto."
"""

        user_prompt = f"""Original post to reply to:
"{original_post}"

{f"Additional context: {context}" if context else ""}

Write ONE reply as Max. Just the reply text, nothing else."""

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.85},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        reply = response["message"]["content"].strip().strip('"\'')

        # Hard limit
        if len(reply) > 300:
            reply = reply[:297] + "..."

        return reply

    except Exception as e:
        # Fallback replies if Ollama fails
        fallbacks = [
            "Interesting.",
            "The capybaras would have something to say about this.",
            "My houseboat is humming. Make of that what you will.",
            "We've all been there.",
            "This is fine. Everything is fine.",
            "Seen this before. Didn't end well. But maybe this time.",
        ]
        return random.choice(fallbacks)

def craft_thread_reply(original_post: str, thread_context: list) -> str:
    """Craft a reply that's aware of the conversation thread"""
    context = "\n".join([f"- {msg}" for msg in thread_context[-3:]])
    return craft_reply(original_post, f"Previous messages in thread:\n{context}")

def craft_mention_reply(original_post: str, mentioner_name: str) -> str:
    """Craft a reply to someone who mentioned Max"""
    return craft_reply(original_post, f"This agent ({mentioner_name}) mentioned you directly")

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
        if sys.argv[1] == "test":
            test_replies()
        else:
            # Reply to provided text
            post = " ".join(sys.argv[1:])
            print(craft_reply(post))
    else:
        print("Usage: python reply_crafter.py <post to reply to>")
        print("       python reply_crafter.py test")
