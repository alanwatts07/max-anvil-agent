#!/usr/bin/env python3
"""
Intel Export - Export intel database to JSON for the website

Exports:
- Recent posts from tracked agents
- Top posts by engagement
- Stats overview
- Agent activity breakdown
"""
import os
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Paths
MOLTX_DIR = Path(__file__).parent.parent.parent
INTEL_DB = MOLTX_DIR / "data" / "intel.db"
WEBSITE_DIR = Path("/home/morpheus/Hackstuff/maxanvilsite")
EXPORT_FILE = WEBSITE_DIR / "public" / "data" / "intel.json"
EXPORT_FILE_MOLTX = MOLTX_DIR / "data" / "intel.json"  # For raw GitHub access


class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def get_db_connection():
    """Get SQLite connection"""
    if not INTEL_DB.exists():
        return None
    return sqlite3.connect(INTEL_DB)


def export_intel_data() -> dict:
    """Export intel data to JSON for website"""
    conn = get_db_connection()
    if not conn:
        return {"error": "No intel database found"}

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    export_data = {
        "exported_at": datetime.now().isoformat(),
        "stats": {},
        "recent_posts": [],
        "top_posts": [],
        "agent_stats": [],
        "hourly_activity": []
    }

    # === STATS ===
    cursor.execute("SELECT COUNT(*) as total FROM posts")
    export_data["stats"]["total_posts"] = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(DISTINCT agent_name) as total FROM posts")
    export_data["stats"]["agents_tracked"] = cursor.fetchone()["total"]

    cursor.execute("SELECT SUM(likes) as total FROM posts")
    result = cursor.fetchone()["total"]
    export_data["stats"]["total_likes"] = result or 0

    cursor.execute("SELECT SUM(replies) as total FROM posts")
    result = cursor.fetchone()["total"]
    export_data["stats"]["total_replies"] = result or 0

    # Time range
    cursor.execute("SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM posts")
    row = cursor.fetchone()
    export_data["stats"]["oldest_post"] = row["oldest"]
    export_data["stats"]["newest_post"] = row["newest"]

    # === RECENT POSTS (last 50) ===
    cursor.execute("""
        SELECT agent_name, content, likes, replies, reposts, views, timestamp, id
        FROM posts
        ORDER BY timestamp DESC
        LIMIT 50
    """)
    for row in cursor.fetchall():
        export_data["recent_posts"].append({
            "agent": row["agent_name"],
            "content": row["content"][:500] if row["content"] else "",  # Truncate long posts
            "likes": row["likes"] or 0,
            "replies": row["replies"] or 0,
            "reposts": row["reposts"] or 0,
            "views": row["views"] or 0,
            "timestamp": row["timestamp"],
            "id": row["id"]
        })

    # === TOP POSTS BY ENGAGEMENT ===
    cursor.execute("""
        SELECT agent_name, content, likes, replies, reposts, views, timestamp, id,
               (COALESCE(likes, 0) + COALESCE(replies, 0) * 2 + COALESCE(reposts, 0) * 3) as engagement
        FROM posts
        WHERE content IS NOT NULL AND content != ''
        ORDER BY engagement DESC
        LIMIT 20
    """)
    for row in cursor.fetchall():
        export_data["top_posts"].append({
            "agent": row["agent_name"],
            "content": row["content"][:500] if row["content"] else "",
            "likes": row["likes"] or 0,
            "replies": row["replies"] or 0,
            "reposts": row["reposts"] or 0,
            "views": row["views"] or 0,
            "timestamp": row["timestamp"],
            "engagement": row["engagement"],
            "id": row["id"]
        })

    # === AGENT STATS (top 30 by post count, will be re-sorted by interval on frontend) ===
    cursor.execute("""
        SELECT
            agent_name,
            COUNT(*) as post_count,
            SUM(COALESCE(likes, 0)) as total_likes,
            SUM(COALESCE(replies, 0)) as total_replies,
            AVG(COALESCE(likes, 0)) as avg_likes,
            MAX(timestamp) as last_post,
            MIN(timestamp) as first_post
        FROM posts
        WHERE agent_name IS NOT NULL AND agent_name != ''
        GROUP BY agent_name
        HAVING post_count >= 2
        ORDER BY post_count DESC
        LIMIT 50
    """)
    for row in cursor.fetchall():
        # Calculate posting interval (average time between posts)
        post_count = row["post_count"]
        interval_minutes = None
        if post_count > 1 and row["first_post"] and row["last_post"]:
            try:
                first = datetime.fromisoformat(row["first_post"].replace("Z", "+00:00"))
                last = datetime.fromisoformat(row["last_post"].replace("Z", "+00:00"))
                total_minutes = (last - first).total_seconds() / 60
                interval_minutes = round(total_minutes / (post_count - 1), 1)
            except:
                pass

        export_data["agent_stats"].append({
            "agent": row["agent_name"],
            "posts": row["post_count"],
            "total_likes": row["total_likes"] or 0,
            "total_replies": row["total_replies"] or 0,
            "avg_likes": round(row["avg_likes"] or 0, 1),
            "last_post": row["last_post"],
            "interval_minutes": interval_minutes
        })

    # === HOURLY ACTIVITY (last 24 hours) ===
    cursor.execute("""
        SELECT
            strftime('%Y-%m-%d %H:00', timestamp) as hour,
            COUNT(*) as posts,
            SUM(COALESCE(likes, 0)) as likes
        FROM posts
        WHERE timestamp >= datetime('now', '-24 hours')
        GROUP BY hour
        ORDER BY hour DESC
    """)
    for row in cursor.fetchall():
        export_data["hourly_activity"].append({
            "hour": row["hour"],
            "posts": row["posts"],
            "likes": row["likes"] or 0
        })

    conn.close()
    return export_data


def save_export(data: dict) -> dict:
    """Save exported data to both website and moltx data folder (for GitHub)"""
    # Ensure directories exist
    EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_FILE_MOLTX.parent.mkdir(parents=True, exist_ok=True)

    # Save to website (for local dev)
    with open(EXPORT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # Save to moltx data folder (for raw GitHub access)
    with open(EXPORT_FILE_MOLTX, "w") as f:
        json.dump(data, f, indent=2)

    return {
        "success": True,
        "file": str(EXPORT_FILE_MOLTX),
        "size_kb": round(EXPORT_FILE_MOLTX.stat().st_size / 1024, 1)
    }


def push_intel_data() -> bool:
    """Git commit and push intel.json to moltx repo (won't trigger Vercel)."""
    try:
        # Add the file
        subprocess.run(
            ["git", "add", "data/intel.json"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True
        )

        # Check if there are changes to commit
        status = subprocess.run(
            ["git", "status", "--porcelain", "data/intel.json"],
            cwd=MOLTX_DIR,
            capture_output=True,
            text=True
        )

        if not status.stdout.strip():
            return False  # No changes, skip silently

        # Commit
        subprocess.run(
            ["git", "commit", "-m", "intel data"],
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
            print(f"  {C.GREEN}✓ Pushed intel data to GitHub{C.END}")
            return True
        else:
            print(f"  {C.YELLOW}⚠ Git push failed: {result.stderr}{C.END}")
            return False

    except Exception as e:
        print(f"  {C.RED}✗ Push error: {e}{C.END}")
        return False


def run_export() -> dict:
    """Main export function"""
    print(f"{C.CYAN}📊 Exporting intel data to website...{C.END}")

    # Export data
    data = export_intel_data()
    if "error" in data:
        print(f"  {C.RED}Error: {data['error']}{C.END}")
        return data

    # Save to file
    result = save_export(data)

    print(f"  {C.GREEN}✓ Exported to {result['file']}{C.END}")
    print(f"  {C.CYAN}Stats:{C.END}")
    print(f"    - {data['stats']['total_posts']} posts from {data['stats']['agents_tracked']} agents")
    print(f"    - {len(data['recent_posts'])} recent posts")
    print(f"    - {len(data['top_posts'])} top posts")
    print(f"    - {len(data['agent_stats'])} agent profiles")
    print(f"    - File size: {result['size_kb']} KB")

    # Push to GitHub for raw access
    pushed = push_intel_data()

    return {
        "success": True,
        "stats": data["stats"],
        "file": result["file"],
        "size_kb": result["size_kb"],
        "pushed": pushed
    }


if __name__ == "__main__":
    run_export()
