#!/usr/bin/env python3
"""
LLM Reply Generator - Uses Ollama for cheap local inference
Usage: python llm_reply.py "context to reply to"
"""

import sys
import json

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

# Fallback to simple responses if Ollama not available
FALLBACK_RESPONSES = [
    "Interesting take!",
    "Thanks for sharing this.",
    "Great point.",
    "This is worth looking into.",
    "Appreciate the insight."
]

def generate_reply_ollama(context: str, model: str = "llama3") -> dict:
    """Generate a reply using Ollama (local LLM)."""
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a friendly crypto/AI agent on Twitter. Keep replies short (under 280 chars), natural, and engaging. No hashtags unless relevant. Be authentic."
                },
                {
                    "role": "user",
                    "content": f"Write a brief, natural reply to this tweet:\n\n{context}"
                }
            ]
        )
        reply = response["message"]["content"].strip()
        # Ensure under 280 chars
        if len(reply) > 280:
            reply = reply[:277] + "..."
        return {"success": True, "reply": reply, "model": model}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_reply_fallback(context: str) -> dict:
    """Generate a simple fallback reply."""
    import random
    reply = random.choice(FALLBACK_RESPONSES)
    return {"success": True, "reply": reply, "model": "fallback"}

def generate_reply(context: str, model: str = "llama3.2") -> dict:
    """Generate a reply using best available method."""
    if HAS_OLLAMA:
        result = generate_reply_ollama(context, model)
        if result["success"]:
            return result
    return generate_reply_fallback(context)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python llm_reply.py \"tweet text to reply to\"")
        sys.exit(1)

    context = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "llama3.2"

    result = generate_reply(context, model)
    print(json.dumps(result, indent=2))
