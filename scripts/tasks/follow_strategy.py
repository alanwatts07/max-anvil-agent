#!/usr/bin/env python3
"""
Follow Strategy Task - Smart follow/unfollow based on game theory
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C
from game_theory import execute_smart_follow_strategy
from follow_manager import enforce_follow_policy


class FollowStrategyTask(Task):
    name = "follow_strategy"
    description = "Smart follow/unfollow based on follow-back probability"

    def run(self) -> dict:
        # Execute smart follow strategy
        follow_results = execute_smart_follow_strategy(10)
        followed = follow_results.get("followed", [])

        # Enforce policy (unfollow non-followers)
        policy_results = enforce_follow_policy()
        unfollowed = policy_results.get("unfollowed", [])
        followed_back = policy_results.get("followed_back", [])

        return {
            "success": True,
            "summary": f"Followed {len(followed)}, unfollowed {len(unfollowed)}, followed back {len(followed_back)}",
            "details": {
                "followed": followed,
                "unfollowed": unfollowed,
                "followed_back": followed_back,
                "scores": follow_results.get("scores", {})
            }
        }


if __name__ == "__main__":
    task = FollowStrategyTask()
    task.execute()
