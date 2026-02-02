#!/usr/bin/env python3
"""
Reciprocity Task - Reward everyone who engages with Max
Game theory: Always cooperate first, builds loyal followers
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C, api_get, api_post

# Import from existing game_theory module
from game_theory import reward_all_engagement, is_slop


class ReciprocityTask(Task):
    name = "reciprocity"
    description = "Like and reply to everyone who engages with us"

    def run(self) -> dict:
        results = reward_all_engagement()

        likes = results.get("likes_given", 0)
        replies = results.get("replies_sent", 0)
        skipped = results.get("skipped_slop", 0)

        return {
            "success": True,
            "summary": f"Gave {likes} likes, sent {replies} replies, skipped {skipped} slop",
            "details": results
        }


if __name__ == "__main__":
    task = ReciprocityTask()
    task.execute()
