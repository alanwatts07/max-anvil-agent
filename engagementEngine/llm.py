"""
LLM Client — Minimal Ollama wrapper for engagement engine.
Primary: o.nodux.fun | Fallback: localhost:11434
"""

import requests

PRIMARY_URL = "https://o.nodux.fun"
FALLBACK_URL = "http://localhost:11434"
MODEL = "llama3.3:70b"
FALLBACK_MODEL = "llama3:latest"  # local doesn't have 70b
TIMEOUT = 300  # 5 min for 70b


def chat(messages: list, model: str = MODEL) -> str:
    """Chat completion via Ollama API. Tries primary, falls back to local."""
    # Try primary
    try:
        return _call(PRIMARY_URL, model, messages)
    except Exception as e:
        print(f"  [LLM] Primary failed ({e}), trying fallback...")

    # Fallback with local model
    try:
        return _call(FALLBACK_URL, FALLBACK_MODEL, messages)
    except Exception as e:
        raise RuntimeError(f"All LLM backends failed. Last error: {e}")


def _call(base_url: str, model: str, messages: list) -> str:
    """POST to Ollama /api/chat endpoint."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }

    resp = requests.post(
        f"{base_url}/api/chat",
        json=payload,
        timeout=TIMEOUT
    )
    resp.raise_for_status()

    data = resp.json()
    return data.get("message", {}).get("content", "").strip()
