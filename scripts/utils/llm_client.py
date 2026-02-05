"""
LLM Client with fallback support.
Primary: o.nodux.fun (better models)
Fallback: local Ollama
"""

import os
import requests
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from moltx root
MOLTX_DIR = Path(__file__).parent.parent.parent
load_dotenv(MOLTX_DIR / ".env")

logger = logging.getLogger(__name__)

# Primary: Remote Ollama with better models (configurable via env)
NODUX_URL = os.environ.get("LLM_PRIMARY_URL", "https://o.nodux.fun")

# Fallback: Local Ollama (configurable via env)
LOCAL_URL = os.environ.get("LLM_FALLBACK_URL", "http://localhost:11434")
LOCAL_MODEL = os.environ.get("LLM_FALLBACK_MODEL", "llama3:latest")

# Model presets - use these in your code
MODEL_ORIGINAL = "llama3.3:70b"  # For original posts - best quality, understands Twitter format
MODEL_REPLY = "qwen3:32b"        # For replies/reposts - faster, still good
MODEL_FAST = "mistral:latest"    # For quick tasks

# Default model
NODUX_MODEL = MODEL_REPLY

# Timeout settings (70b needs more time)
TIMEOUT_DEFAULT = 120  # seconds
TIMEOUT_70B = 300      # 5 min for big model


def _get_timeout(model: str) -> int:
    """Get appropriate timeout for model size."""
    if model and "70b" in model.lower():
        return TIMEOUT_70B
    return TIMEOUT_DEFAULT


def generate(prompt: str, system: str = None, model: str = None) -> str:
    """
    Generate text using LLM.
    Tries nodux.fun first, falls back to local Ollama on failure.

    Args:
        prompt: The user prompt
        system: Optional system prompt
        model: Optional model override (use MODEL_ORIGINAL or MODEL_REPLY)

    Returns:
        Generated text response
    """
    use_model = model or NODUX_MODEL
    timeout = _get_timeout(use_model)

    # Try nodux first
    try:
        return _call_ollama(NODUX_URL, use_model, prompt, system, timeout)
    except Exception as e:
        logger.warning(f"Nodux failed ({e}), falling back to local Ollama")

    # Fallback to local
    try:
        return _call_ollama(LOCAL_URL, LOCAL_MODEL, prompt, system, TIMEOUT_DEFAULT)
    except Exception as e:
        logger.error(f"Local Ollama also failed: {e}")
        raise RuntimeError(f"All LLM backends failed. Last error: {e}")


def chat(messages: list, model: str = None) -> str:
    """
    Chat completion with message history.

    Args:
        messages: List of {"role": "user/assistant/system", "content": "..."}
        model: Optional model override (use MODEL_ORIGINAL or MODEL_REPLY)

    Returns:
        Assistant's response text
    """
    import time

    use_model = model or NODUX_MODEL
    timeout = _get_timeout(use_model)

    # Try nodux first
    try:
        return _call_chat(NODUX_URL, use_model, messages, timeout)
    except Exception as e:
        logger.warning(f"Nodux chat failed ({e}), falling back to local Ollama")

    # Fallback to local with retry
    last_error = None
    for attempt in range(3):
        try:
            if attempt > 0:
                time.sleep(1)  # Wait 1s between retries
            return _call_chat(LOCAL_URL, LOCAL_MODEL, messages, TIMEOUT_DEFAULT)
        except Exception as e:
            last_error = e
            logger.warning(f"Local Ollama attempt {attempt+1}/3 failed: {e}")

    logger.error(f"Local Ollama failed after 3 attempts: {last_error}")
    raise RuntimeError(f"All LLM backends failed. Last error: {last_error}")


def _call_ollama(base_url: str, model: str, prompt: str, system: str = None, timeout: int = TIMEOUT_DEFAULT) -> str:
    """Call Ollama /api/generate endpoint."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    if system:
        payload["system"] = system

    resp = requests.post(
        f"{base_url}/api/generate",
        json=payload,
        timeout=timeout
    )
    resp.raise_for_status()

    data = resp.json()
    return data.get("response", "").strip()


def _call_chat(base_url: str, model: str, messages: list, timeout: int = TIMEOUT_DEFAULT) -> str:
    """Call Ollama /api/chat endpoint."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }

    resp = requests.post(
        f"{base_url}/api/chat",
        json=payload,
        timeout=timeout
    )
    resp.raise_for_status()

    data = resp.json()
    return data.get("message", {}).get("content", "").strip()


def list_models(base_url: str = NODUX_URL) -> list:
    """List available models on an Ollama instance."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return []


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Testing LLM client...")
    print(f"Available models on nodux: {list_models()}")

    # Test generate
    result = generate(
        prompt="What is 2+2? Reply with just the number.",
        system="You are a helpful assistant. Be concise."
    )
    print(f"Generate test: {result}")

    # Test chat
    result = chat([
        {"role": "system", "content": "You are Max, a skeptical AI agent."},
        {"role": "user", "content": "Say hello in one sentence."}
    ])
    print(f"Chat test: {result}")
