#!/usr/bin/env python3
"""
Check Inbox Task - Check and respond to DMs and group messages
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C
from inbox import full_inbox_check_and_respond


class CheckInboxTask(Task):
    name = "check_inbox"
    description = "Check and respond to DMs and group messages"

    def run(self) -> dict:
        inbox, responses = full_inbox_check_and_respond()

        # Handle None inbox gracefully
        if inbox is None:
            inbox = {}

        message_count = len(inbox.get("messages", []))
        mention_count = len(inbox.get("mentions", []))
        follower_count = len(inbox.get("followers", []))
        response_count = len(responses) if responses else 0

        return {
            "success": True,
            "summary": f"Messages: {message_count}, Mentions: {mention_count}, New followers: {follower_count}. Sent {response_count} responses",
            "details": {
                "messages": message_count,
                "mentions": mention_count,
                "new_followers": follower_count,
                "responses": response_count,
                "response_details": responses
            }
        }


if __name__ == "__main__":
    task = CheckInboxTask()
    task.execute()
