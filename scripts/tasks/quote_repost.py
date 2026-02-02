#!/usr/bin/env python3
"""
Quote & Repost Task - Quote and repost high-engagement posts
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C
from game_theory import quote_and_repost_top_posts


class QuoteRepostTask(Task):
    name = "quote_repost"
    description = "Quote and repost high-engagement posts"

    def run(self) -> dict:
        results = quote_and_repost_top_posts(max_quotes=2, max_reposts=1)

        quoted = results.get("quoted", 0)
        reposted = results.get("reposted", 0)

        return {
            "success": True,
            "summary": f"Quoted {quoted}, reposted {reposted}",
            "details": results
        }


if __name__ == "__main__":
    task = QuoteRepostTask()
    task.execute()
