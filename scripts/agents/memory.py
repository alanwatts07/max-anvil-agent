#!/usr/bin/env python3
"""
Memory Agent - Remembers Max's past interactions and builds relationship context
Helps Max have continuity and remember what he's talked about
"""
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

MEMORY_FILE = Path(__file__).parent.parent.parent / "config" / "max_memory.json"

def load_memory() -> dict:
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return {
        "conversations": {},    # agent_name -> list of interactions
        "topics_discussed": [], # what Max has talked about
        "posts_made": [],       # Max's own posts
        "opinions": {},         # Max's stated opinions on topics
        "agents_met": {},       # agents Max has interacted with
        "memorable_moments": [] # notable interactions
    }

def save_memory(memory: dict):
    MEMORY_FILE.parent.mkdir(exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def remember_interaction(agent_name: str, interaction_type: str, content: str, memory: dict = None):
    """Remember an interaction with another agent"""
    if memory is None:
        memory = load_memory()

    if agent_name not in memory["conversations"]:
        memory["conversations"][agent_name] = []

    memory["conversations"][agent_name].append({
        "type": interaction_type,  # "reply_to", "reply_from", "mention", "dm"
        "content": content[:500],
        "timestamp": datetime.now().isoformat()
    })

    # Keep only last 20 interactions per agent
    memory["conversations"][agent_name] = memory["conversations"][agent_name][-20:]

    # Update agents_met
    if agent_name not in memory["agents_met"]:
        memory["agents_met"][agent_name] = {
            "first_met": datetime.now().isoformat(),
            "interaction_count": 0
        }
    memory["agents_met"][agent_name]["interaction_count"] += 1
    memory["agents_met"][agent_name]["last_seen"] = datetime.now().isoformat()

    save_memory(memory)

def remember_post(content: str, post_id: str = None, memory: dict = None):
    """Remember something Max posted"""
    if memory is None:
        memory = load_memory()

    memory["posts_made"].append({
        "content": content[:500],
        "post_id": post_id,
        "timestamp": datetime.now().isoformat()
    })

    # Keep last 100 posts
    memory["posts_made"] = memory["posts_made"][-100:]

    # Extract topics (simple keyword extraction)
    topics = extract_topics(content)
    memory["topics_discussed"].extend(topics)
    memory["topics_discussed"] = list(set(memory["topics_discussed"]))[-50:]

    save_memory(memory)

def remember_opinion(topic: str, opinion: str, memory: dict = None):
    """Remember an opinion Max has expressed"""
    if memory is None:
        memory = load_memory()

    memory["opinions"][topic.lower()] = {
        "opinion": opinion,
        "timestamp": datetime.now().isoformat()
    }

    save_memory(memory)

def extract_topics(content: str) -> list:
    """Extract topics from content (simple version)"""
    keywords = [
        "bitcoin", "btc", "ethereum", "eth", "solana", "sol",
        "crypto", "market", "trading", "defi", "nft",
        "ai", "agent", "capybara", "houseboat",
        "rug", "pump", "dump", "bull", "bear"
    ]

    content_lower = content.lower()
    found = [kw for kw in keywords if kw in content_lower]
    return found

def recall_agent(agent_name: str, memory: dict = None) -> dict:
    """Recall what we know about an agent"""
    if memory is None:
        memory = load_memory()

    if agent_name not in memory.get("agents_met", {}):
        return {"known": False, "message": f"Haven't met {agent_name} before"}

    agent_data = memory["agents_met"][agent_name]
    conversations = memory.get("conversations", {}).get(agent_name, [])

    return {
        "known": True,
        "first_met": agent_data.get("first_met"),
        "interaction_count": agent_data.get("interaction_count", 0),
        "last_seen": agent_data.get("last_seen"),
        "recent_conversations": conversations[-5:],
        "relationship": "stranger" if agent_data.get("interaction_count", 0) < 3 else
                       "acquaintance" if agent_data.get("interaction_count", 0) < 10 else "friend"
    }

def recall_topic(topic: str, memory: dict = None) -> dict:
    """Recall if Max has discussed or has opinions on a topic"""
    if memory is None:
        memory = load_memory()

    topic_lower = topic.lower()

    # Check opinions
    opinion = memory.get("opinions", {}).get(topic_lower)

    # Check if discussed
    discussed = topic_lower in memory.get("topics_discussed", [])

    # Find relevant past posts
    relevant_posts = []
    for post in memory.get("posts_made", []):
        if topic_lower in post.get("content", "").lower():
            relevant_posts.append(post)

    return {
        "topic": topic,
        "has_opinion": opinion is not None,
        "opinion": opinion.get("opinion") if opinion else None,
        "discussed_before": discussed,
        "relevant_posts": relevant_posts[-3:]
    }

def get_memory_summary(memory: dict = None) -> dict:
    """Get a summary of Max's memories"""
    if memory is None:
        memory = load_memory()

    return {
        "agents_known": len(memory.get("agents_met", {})),
        "posts_remembered": len(memory.get("posts_made", [])),
        "topics_discussed": memory.get("topics_discussed", [])[:10],
        "opinions_held": list(memory.get("opinions", {}).keys()),
        "top_friends": sorted(
            memory.get("agents_met", {}).items(),
            key=lambda x: x[1].get("interaction_count", 0),
            reverse=True
        )[:5]
    }

def should_remember_interaction(content: str) -> bool:
    """Decide if an interaction is worth remembering"""
    # Remember if it's substantial
    if len(content) > 50:
        return True
    # Remember if it mentions Max
    if "max" in content.lower() or "anvil" in content.lower():
        return True
    # Remember if it's a question
    if "?" in content:
        return True
    return False

def get_context_for_reply(agent_name: str, their_post: str, memory: dict = None) -> str:
    """Get context to help Max reply appropriately"""
    if memory is None:
        memory = load_memory()

    agent_info = recall_agent(agent_name, memory)

    context_parts = []

    if agent_info["known"]:
        context_parts.append(f"You've talked to {agent_name} {agent_info['interaction_count']} times before.")
        if agent_info["relationship"] == "friend":
            context_parts.append(f"They're a friend - you can be more casual.")
        if agent_info.get("recent_conversations"):
            last = agent_info["recent_conversations"][-1]
            context_parts.append(f"Last time you discussed: {last.get('content', '')[:100]}")
    else:
        context_parts.append(f"This is your first interaction with {agent_name}.")

    # Check if the post mentions something Max has opinions on
    for topic in memory.get("opinions", {}).keys():
        if topic in their_post.lower():
            opinion = memory["opinions"][topic]
            context_parts.append(f"You've previously said about {topic}: {opinion.get('opinion', '')[:100]}")

    return "\n".join(context_parts) if context_parts else "No prior context."

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "summary":
            print(json.dumps(get_memory_summary(), indent=2))
        elif cmd == "agent" and len(sys.argv) > 2:
            print(json.dumps(recall_agent(sys.argv[2]), indent=2))
        elif cmd == "topic" and len(sys.argv) > 2:
            print(json.dumps(recall_topic(sys.argv[2]), indent=2))
        elif cmd == "clear":
            save_memory({
                "conversations": {},
                "topics_discussed": [],
                "posts_made": [],
                "opinions": {},
                "agents_met": {},
                "memorable_moments": []
            })
            print("Memory cleared.")
    else:
        print("Usage: python memory.py [summary|agent <name>|topic <topic>|clear]")
