#!/usr/bin/env python3
"""
View Maximizer Task - Target high-view accounts to climb leaderboard
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C, get_leaderboard_position
from view_maximizer import run_view_maximizer


class ViewMaximizeTask(Task):
    name = "view_maximize"
    description = "Reply to high-view accounts for leaderboard climb"

    def run(self) -> dict:
        # Get position before
        pos_before, views_before = get_leaderboard_position()

        # Run view maximizer
        results = run_view_maximizer()

        # Get position after
        pos_after, views_after = get_leaderboard_position()

        replies = results.get("replies", {}).get("replied", 0)
        quotes = results.get("quotes", {}).get("quoted", 0)
        targets = results.get("replies", {}).get("targets", [])

        pos_str = f"#{pos_after}" if pos_after else "Not ranked"
        views_str = f"{views_after:,}" if views_after else "?"

        return {
            "success": True,
            "summary": f"Replied to {replies}, quoted {quotes}. Position: {pos_str}, Views: {views_str}",
            "details": {
                "replies": replies,
                "quotes": quotes,
                "targets": targets,
                "position": pos_after,
                "views": views_after
            }
        }


if __name__ == "__main__":
    task = ViewMaximizeTask()
    task.execute()
