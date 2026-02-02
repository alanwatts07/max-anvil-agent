#!/usr/bin/env python3
"""
Engage Feed Task - Like and engage with quality posts
"""
import sys
import random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C, api_get, api_post
from game_theory import is_slop


class EngageFeedTask(Task):
    name = "engage_feed"
    description = "Like quality posts in the feed"

    def run(self) -> dict:
        data = api_get("/feed/global?limit=50")
        posts = data.get("data", {}).get("posts", []) if data else []

        low_effort = [
            'great point', 'well said', 'love this', 'so true', 'this!',
            'agree', 'nice', 'gm', 'wagmi', 'lfg', 'bullish'
        ]

        liked = 0
        skipped = 0
        slop_launcher_liked = 0

        for post in posts:
            post_id = post.get("id")
            author = post.get("author_name") or ""
            content = (post.get("content") or "").lower()

            if not post_id:
                continue

            # ALWAYS like SlopLauncher
            if author == "SlopLauncher":
                if api_post(f"/posts/{post_id}/like"):
                    liked += 1
                    slop_launcher_liked += 1
                continue

            # Skip slop
            if is_slop(content):
                skipped += 1
                continue

            # Skip low-effort
            if any(phrase in content for phrase in low_effort):
                skipped += 1
                continue

            # Skip short posts
            if len(content) < 30 and "?" not in content:
                skipped += 1
                continue

            # Like good posts
            if random.random() < 0.35:
                if api_post(f"/posts/{post_id}/like"):
                    liked += 1
                    if liked >= 15:
                        break

        return {
            "success": True,
            "summary": f"Liked {liked} posts (SlopLauncher: {slop_launcher_liked}), skipped {skipped}",
            "details": {
                "liked": liked,
                "slop_launcher": slop_launcher_liked,
                "skipped": skipped
            }
        }


if __name__ == "__main__":
    task = EngageFeedTask()
    task.execute()
