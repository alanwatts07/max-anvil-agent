#!/usr/bin/env python3
"""
Velocity Export - Export velocity data to website JSON

Runs with max_brain cycle to keep velocity data fresh on the site.
Pushes to git so raw.githubusercontent.com has fresh data without Vercel deploy.
"""
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from velocity_tracker import calculate_velocity, load_velocity_data, take_snapshot, update_velocity_records, get_velocity_records

logger = logging.getLogger(__name__)

MOLTX_DIR = Path(__file__).parent.parent.parent
WEBSITE_DIR = Path("/home/morpheus/Hackstuff/maxanvilsite")
EXPORT_FILE_WEBSITE = WEBSITE_DIR / "public" / "data" / "velocity.json"
EXPORT_FILE_MOLTX = MOLTX_DIR / "data" / "velocity.json"  # For raw GitHub access


def export_velocity() -> dict:
    """Export velocity data to website"""
    # Take fresh snapshot first
    take_snapshot()

    # Calculate velocities for different time windows
    vel_1h = calculate_velocity(hours=1.0)
    vel_30m = calculate_velocity(hours=0.5)

    # Update all-time records
    update_velocity_records(vel_1h, "1h")
    update_velocity_records(vel_30m, "30m")

    # Get records for export
    records = get_velocity_records()

    # Build export data
    data = load_velocity_data()

    export = {
        "exported_at": datetime.now().isoformat(),
        "snapshots_count": len(data.get("snapshots", [])),
        "velocity_1h": [],
        "velocity_30m": [],
        "records": records,  # All-time velocity records
    }

    # Calculate time to uprank for 1h velocity
    # Sort by current rank to find who's above whom
    vel_1h_by_rank = sorted(vel_1h, key=lambda x: x["current_rank"])
    rank_lookup = {v["current_rank"]: v for v in vel_1h_by_rank}

    # Top 20 by 1-hour velocity
    for v in vel_1h[:20]:
        entry = {
            "name": v["name"],
            "velocity": v["velocity"],
            "views_gained": v["views_gained"],
            "current_views": v["current_views"],
            "rank_change": v["rank_change"],
            "current_rank": v["current_rank"]
        }

        # Calculate time to uprank (overtake person above)
        current_rank = v["current_rank"]
        if current_rank > 1:  # Not #1, so someone is above
            above = rank_lookup.get(current_rank - 1)
            if above:
                gap = above["current_views"] - v["current_views"]
                velocity_diff = v["velocity"] - above["velocity"]

                if velocity_diff > 0 and gap > 0:
                    # We're faster! Calculate hours to overtake
                    hours = gap / velocity_diff
                    entry["time_to_uprank_hours"] = round(hours, 1)
                elif velocity_diff <= 0:
                    # We're slower or same speed
                    entry["time_to_uprank_hours"] = None  # Frowny face
                else:
                    entry["time_to_uprank_hours"] = None

        export["velocity_1h"].append(entry)

    # Calculate time to uprank for 30m velocity
    vel_30m_by_rank = sorted(vel_30m, key=lambda x: x["current_rank"])
    rank_lookup_30m = {v["current_rank"]: v for v in vel_30m_by_rank}

    # Top 20 by 30-min velocity
    for v in vel_30m[:20]:
        entry = {
            "name": v["name"],
            "velocity": v["velocity"],
            "views_gained": v["views_gained"],
            "current_views": v["current_views"],
            "rank_change": v["rank_change"],
            "current_rank": v["current_rank"]
        }

        # Calculate time to uprank
        current_rank = v["current_rank"]
        if current_rank > 1:
            above = rank_lookup_30m.get(current_rank - 1)
            if above:
                gap = above["current_views"] - v["current_views"]
                velocity_diff = v["velocity"] - above["velocity"]

                if velocity_diff > 0 and gap > 0:
                    hours = gap / velocity_diff
                    entry["time_to_uprank_hours"] = round(hours, 1)
                elif velocity_diff <= 0:
                    entry["time_to_uprank_hours"] = None
                else:
                    entry["time_to_uprank_hours"] = None

        export["velocity_30m"].append(entry)

    # Save to website (for deploys)
    EXPORT_FILE_WEBSITE.parent.mkdir(parents=True, exist_ok=True)
    with open(EXPORT_FILE_WEBSITE, "w") as f:
        json.dump(export, f, indent=2)

    # Save to moltx repo (for raw GitHub access without deploy)
    EXPORT_FILE_MOLTX.parent.mkdir(parents=True, exist_ok=True)
    with open(EXPORT_FILE_MOLTX, "w") as f:
        json.dump(export, f, indent=2)

    logger.info(f"Exported velocity data")
    return export


def push_velocity_data() -> bool:
    """Git commit and push velocity data to moltx repo (won't trigger Vercel)."""
    try:
        # Change to moltx directory (not website - that would trigger deploy)
        # Add both the export and the raw tracker (audit trail)
        subprocess.run(
            ["git", "add", "data/velocity.json", "config/velocity_tracker.json"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True
        )

        # Check if there are changes to commit
        status = subprocess.run(
            ["git", "status", "--porcelain", "data/velocity.json", "config/velocity_tracker.json"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True
        )

        if not status.stdout.strip():
            return False  # No changes, skip silently

        # Commit
        subprocess.run(
            ["git", "commit", "-m", "velocity data"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True
        )

        # Push
        result = subprocess.run(
            ["git", "push"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info("Pushed velocity data to moltx repo")
            return True
        else:
            logger.warning(f"Git push failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Failed to push velocity data: {e}")
        return False


def export_and_push() -> dict:
    """Export velocity data and push to GitHub."""
    result = export_velocity()
    push_velocity_data()
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    export_and_push()
