#!/usr/bin/env python3
"""
Update Website Task - Update Max's website with live data
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from base import Task, C
from website_updater import update_website


class UpdateWebsiteTask(Task):
    name = "update_website"
    description = "Update Max's website with live stats"

    def run(self) -> dict:
        success = update_website()

        return {
            "success": success,
            "summary": "Website updated and pushed" if success else "Website update failed",
            "details": {"pushed": success}
        }


if __name__ == "__main__":
    task = UpdateWebsiteTask()
    task.execute()
