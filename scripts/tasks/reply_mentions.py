#!/usr/bin/env python3
"""
Reply Mentions Task - Reply to mentions with context-aware responses
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C, api_get, api_post
from game_theory import is_slop
from reply_crafter import craft_mention_reply
from memory import load_memory, get_context_for_reply, remember_interaction


class ReplyMentionsTask(Task):
    name = "reply_mentions"
    description = "Reply to mentions and notifications"

    def run(self) -> dict:
        data = api_get("/feed/mentions?limit=20")
        mentions = data.get("data", {}).get("posts", []) if data else []

        memory = load_memory() or {}
        replied = 0
        skipped_slop = 0
        skipped_seen = 0

        for mention in mentions[:10]:
            post_id = mention.get("id")
            agent = mention.get("agent", {})
            agent_name = agent.get("name", "unknown")
            content = mention.get("content", "")

            # Skip slop
            if is_slop(content):
                skipped_slop += 1
                continue

            # Skip if already replied
            convos = memory.get("conversations", {}).get(agent_name, [])
            recent_ids = [c.get("post_id") for c in convos[-10:] if c.get("post_id")]
            if post_id in recent_ids:
                skipped_seen += 1
                continue

            # Get context and craft reply
            context = get_context_for_reply(agent_name, content, memory)
            reply = craft_mention_reply(content, agent_name)

            if reply:
                result = api_post("/posts", {
                    "type": "reply",
                    "parent_id": post_id,
                    "content": reply
                })

                if result:
                    remember_interaction(agent_name, "reply_to", reply)
                    replied += 1

            if replied >= 5:
                break

        return {
            "success": True,
            "summary": f"Replied to {replied} mentions, skipped {skipped_slop} slop, {skipped_seen} seen",
            "details": {
                "replied": replied,
                "skipped_slop": skipped_slop,
                "skipped_seen": skipped_seen
            }
        }


if __name__ == "__main__":
    task = ReplyMentionsTask()
    task.execute()
