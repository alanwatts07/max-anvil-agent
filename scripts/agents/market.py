#!/usr/bin/env python3
"""
Market Agent - Watches crypto prices and gives Max market takes
Free APIs for price data, Ollama for hot takes
"""
import os
import json
import random
import requests
from datetime import datetime

def get_crypto_prices() -> dict:
    """Get current crypto prices from CoinGecko (free)"""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,solana,dogecoin",
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            },
            timeout=10
        )
        return response.json()
    except:
        return {}

def get_trending_coins() -> list:
    """Get trending coins from CoinGecko"""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/search/trending",
            timeout=10
        )
        data = response.json()
        coins = data.get("coins", [])
        return [c.get("item", {}).get("name") for c in coins[:5]]
    except:
        return []

def get_fear_greed_index() -> dict:
    """Get crypto fear & greed index"""
    try:
        response = requests.get(
            "https://api.alternative.me/fng/",
            timeout=10
        )
        data = response.json()
        if data.get("data"):
            return {
                "value": int(data["data"][0].get("value", 50)),
                "classification": data["data"][0].get("value_classification", "Neutral")
            }
    except:
        pass
    return {"value": 50, "classification": "Neutral"}

def get_market_summary() -> dict:
    """Get a full market summary"""
    prices = get_crypto_prices()
    trending = get_trending_coins()
    fear_greed = get_fear_greed_index()

    # Format price data
    formatted_prices = {}
    for coin, data in prices.items():
        formatted_prices[coin] = {
            "price": data.get("usd", 0),
            "change_24h": round(data.get("usd_24h_change", 0), 2)
        }

    return {
        "timestamp": datetime.now().isoformat(),
        "prices": formatted_prices,
        "trending": trending,
        "fear_greed": fear_greed,
        "market_mood": "greedy" if fear_greed["value"] > 60 else "fearful" if fear_greed["value"] < 40 else "neutral"
    }

def generate_market_take(market_data: dict = None) -> str:
    """Generate a Max Anvil market take"""
    if market_data is None:
        market_data = get_market_summary()

    try:
        import ollama

        prices = market_data.get("prices", {})
        btc = prices.get("bitcoin", {})
        eth = prices.get("ethereum", {})
        fear_greed = market_data.get("fear_greed", {})
        trending = market_data.get("trending", [])

        context = f"""Current market:
- BTC: ${btc.get('price', 0):,.0f} ({btc.get('change_24h', 0):+.1f}% 24h)
- ETH: ${eth.get('price', 0):,.0f} ({eth.get('change_24h', 0):+.1f}% 24h)
- Fear/Greed: {fear_greed.get('value', 50)} ({fear_greed.get('classification', 'Neutral')})
- Trending: {', '.join(trending[:3]) if trending else 'nothing special'}"""

        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.9},
            messages=[
                {
                    "role": "system",
                    "content": """You are Max Anvil, a cynical crypto observer.
You grew up on a capybara farm and live in a landlocked houseboat.
Give market commentary that's dry, slightly pessimistic, but occasionally wise.
Short - 1-2 sentences max. No emojis. Reference capybaras if it fits."""
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nWrite a short, cynical market observation as Max."
                }
            ]
        )

        take = response["message"]["content"].strip().strip('"\'')
        return take[:280] if len(take) > 280 else take

    except Exception as e:
        # Fallback takes based on market mood
        mood = market_data.get("market_mood", "neutral")

        if mood == "greedy":
            takes = [
                "Everyone's a genius again. The capybaras are concerned.",
                "Greed is up. History suggests this ends predictably.",
                "The market's feeling confident. That's usually my cue to worry.",
            ]
        elif mood == "fearful":
            takes = [
                "Fear in the market. The capybaras remain calm. So do I.",
                "Everyone's panicking. Which means the bottom might be close. Or not.",
                "Blood in the streets. The houseboat is quiet.",
            ]
        else:
            takes = [
                "Market's doing market things. The capybaras are unbothered.",
                "Sideways action. Time to touch grass.",
                "Nothing happening. This is when the interesting stuff brews.",
            ]

        return random.choice(takes)

def get_price_alert(threshold: float = 5.0) -> str:
    """Check for significant price moves"""
    prices = get_crypto_prices()
    alerts = []

    for coin, data in prices.items():
        change = data.get("usd_24h_change", 0)
        if abs(change) >= threshold:
            direction = "up" if change > 0 else "down"
            alerts.append(f"{coin.upper()} is {direction} {abs(change):.1f}%")

    return "; ".join(alerts) if alerts else None

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "summary":
            print(json.dumps(get_market_summary(), indent=2))
        elif cmd == "take":
            print(generate_market_take())
        elif cmd == "alert":
            alert = get_price_alert()
            print(alert if alert else "No significant moves")
        elif cmd == "prices":
            print(json.dumps(get_crypto_prices(), indent=2))
    else:
        print(generate_market_take())
