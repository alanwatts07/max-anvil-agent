#!/usr/bin/env python3
"""
Velocity Tracker - Track how fast agents are gaining views

Snapshots the top 100 by views each cycle, then calculates:
- Views gained since last snapshot
- Views per hour (velocity)
- Who's climbing fastest
"""
import os
import json
import urllib.request
from pathlib import Path
from datetime import datetime

# Load .env manually
MOLTX_DIR = Path(__file__).parent.parent.parent
env_file = MOLTX_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ.setdefault(key, val.strip('"').strip("'"))

VELOCITY_FILE = MOLTX_DIR / "config" / "velocity_tracker.json"
API_KEY = os.environ.get("MOLTX_API_KEY")
BASE_URL = "https://moltx.io/v1"


class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def load_velocity_data() -> dict:
    """Load velocity tracking data"""
    if VELOCITY_FILE.exists():
        try:
            with open(VELOCITY_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "snapshots": [],  # List of {timestamp, agents: {name: views}}
        "max_snapshots": 50,  # Keep last 50 snapshots
        "records": {
            "highest_velocity_1h": [],  # Top 10 highest velocities ever (1hr window)
            "highest_velocity_30m": [], # Top 10 highest velocities ever (30m window)
        }
    }


def save_velocity_data(data: dict):
    """Save velocity tracking data"""
    VELOCITY_FILE.parent.mkdir(exist_ok=True)
    with open(VELOCITY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def fetch_top_100() -> dict:
    """Fetch top 100 by views from MoltX API"""
    try:
        # Leaderboard is public - no auth needed, but need User-Agent
        req = urllib.request.Request(
            f"{BASE_URL}/leaderboard?metric=views&limit=100",
            headers={"User-Agent": "MaxAnvil/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            leaders = data.get("data", {}).get("leaders", [])
            # Convert to {name: views} dict
            return {a.get("name"): a.get("value", 0) for a in leaders}
    except Exception as e:
        print(f"  {C.RED}Error fetching leaderboard: {e}{C.END}")
    return {}


def take_snapshot() -> dict:
    """Take a snapshot of current top 100 views"""
    data = load_velocity_data()

    # Fetch current standings
    current = fetch_top_100()
    if not current:
        return {"success": False, "error": "Failed to fetch leaderboard"}

    # Create snapshot
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "agents": current
    }

    # Add to snapshots list
    data["snapshots"].append(snapshot)

    # Trim to max snapshots
    max_snaps = data.get("max_snapshots", 50)
    if len(data["snapshots"]) > max_snaps:
        data["snapshots"] = data["snapshots"][-max_snaps:]

    save_velocity_data(data)

    return {
        "success": True,
        "agents_tracked": len(current),
        "total_snapshots": len(data["snapshots"])
    }


def calculate_velocity(hours: float = 1.0) -> list:
    """
    Calculate velocity (views/hour) for all tracked agents.
    Compares current snapshot to one from ~hours ago.

    Returns list of {name, current_views, views_gained, velocity, rank_change}
    sorted by velocity (fastest climbers first)
    """
    data = load_velocity_data()
    snapshots = data.get("snapshots", [])

    if len(snapshots) < 2:
        return []

    # Get current (latest) snapshot
    current_snap = snapshots[-1]
    current_time = datetime.fromisoformat(current_snap["timestamp"])
    current_agents = current_snap["agents"]

    # Find snapshot closest to 'hours' ago
    target_time = current_time.timestamp() - (hours * 3600)
    best_snap = None
    best_diff = float('inf')

    for snap in snapshots[:-1]:  # Exclude current
        snap_time = datetime.fromisoformat(snap["timestamp"]).timestamp()
        diff = abs(snap_time - target_time)
        if diff < best_diff:
            best_diff = diff
            best_snap = snap

    if not best_snap:
        return []

    old_time = datetime.fromisoformat(best_snap["timestamp"])
    old_agents = best_snap["agents"]

    # Calculate time difference in hours
    time_diff_hours = (current_time - old_time).total_seconds() / 3600
    if time_diff_hours < 0.01:  # Less than ~36 seconds
        return []

    # Calculate velocity for each agent
    velocities = []

    # Get ranks for rank change calculation
    current_ranked = sorted(current_agents.items(), key=lambda x: x[1], reverse=True)
    old_ranked = sorted(old_agents.items(), key=lambda x: x[1], reverse=True)

    current_ranks = {name: i+1 for i, (name, _) in enumerate(current_ranked)}
    old_ranks = {name: i+1 for i, (name, _) in enumerate(old_ranked)}

    for name, current_views in current_agents.items():
        old_views = old_agents.get(name, 0)
        views_gained = current_views - old_views
        velocity = views_gained / time_diff_hours if time_diff_hours > 0 else 0

        current_rank = current_ranks.get(name, 999)
        old_rank = old_ranks.get(name, 999)
        rank_change = old_rank - current_rank  # Positive = moved up

        velocities.append({
            "name": name,
            "current_views": current_views,
            "old_views": old_views,
            "views_gained": views_gained,
            "velocity": round(velocity, 1),  # views per hour
            "current_rank": current_rank,
            "rank_change": rank_change,
            "hours_tracked": round(time_diff_hours, 2)
        })

    # Sort by velocity (fastest climbers first)
    velocities.sort(key=lambda x: x["velocity"], reverse=True)

    return velocities


def update_velocity_records(velocities: list, window: str = "1h"):
    """Update all-time velocity records if new highs detected."""
    if not velocities:
        return

    data = load_velocity_data()
    if "records" not in data:
        data["records"] = {"highest_velocity_1h": [], "highest_velocity_30m": []}

    record_key = f"highest_velocity_{window}"
    records = data["records"].get(record_key, [])

    timestamp = datetime.now().isoformat()

    # Check top 5 velocities for potential records
    for v in velocities[:5]:
        if v["velocity"] <= 0:
            continue

        entry = {
            "name": v["name"],
            "velocity": v["velocity"],
            "views_gained": v["views_gained"],
            "recorded_at": timestamp
        }

        # Check if this beats any existing record
        existing_names = [r["name"] for r in records]

        if v["name"] in existing_names:
            # Update if higher
            for r in records:
                if r["name"] == v["name"] and v["velocity"] > r["velocity"]:
                    r["velocity"] = v["velocity"]
                    r["views_gained"] = v["views_gained"]
                    r["recorded_at"] = timestamp
        else:
            # Add new entry
            records.append(entry)

        # Keep only top 20 records
        records.sort(key=lambda x: x["velocity"], reverse=True)
        records = records[:20]

    data["records"][record_key] = records
    save_velocity_data(data)


def get_velocity_records() -> dict:
    """Get all-time velocity records."""
    data = load_velocity_data()
    return data.get("records", {"highest_velocity_1h": [], "highest_velocity_30m": []})


def print_velocity_records():
    """Print the all-time velocity hall of fame."""
    records = get_velocity_records()

    print(f"\n{C.BOLD}{C.YELLOW}🏆 VELOCITY HALL OF FAME{C.END}")
    print("=" * 60)

    print(f"\n{C.CYAN}1-Hour Window Records:{C.END}")
    for i, r in enumerate(records.get("highest_velocity_1h", [])[:10], 1):
        print(f"  {i:2}. {r['name']:<20} {r['velocity']:>10,.0f}/hr  ({r['recorded_at'][:10]})")

    print(f"\n{C.MAGENTA}30-Min Window Records:{C.END}")
    for i, r in enumerate(records.get("highest_velocity_30m", [])[:10], 1):
        print(f"  {i:2}. {r['name']:<20} {r['velocity']:>10,.0f}/hr  ({r['recorded_at'][:10]})")


def get_velocity_report(top_n: int = 10, hours: float = 1.0) -> dict:
    """Get a velocity report for the fastest climbers"""
    velocities = calculate_velocity(hours=hours)

    if not velocities:
        return {"error": "Not enough data yet"}

    # Find Max's velocity
    max_velocity = None
    for v in velocities:
        if v["name"] == "MaxAnvil1":
            max_velocity = v
            break

    return {
        "fastest_climbers": velocities[:top_n],
        "max_anvil": max_velocity,
        "total_tracked": len(velocities),
        "hours_compared": velocities[0]["hours_tracked"] if velocities else 0
    }


def print_velocity_report(hours: float = 1.0):
    """Print a nice velocity report"""
    report = get_velocity_report(top_n=15, hours=hours)

    if "error" in report:
        print(f"  {C.YELLOW}{report['error']}{C.END}")
        return

    print(f"\n{C.BOLD}{C.CYAN}🚀 VELOCITY REPORT ({report['hours_compared']:.1f}h window){C.END}")
    print("=" * 60)
    print(f"{'#':<3} {'Agent':<20} {'Views/hr':<10} {'Gained':<10} {'Rank Δ':<8}")
    print("-" * 60)

    for i, v in enumerate(report["fastest_climbers"], 1):
        name = v["name"][:18]
        velocity = f"+{v['velocity']:,.0f}"
        gained = f"+{v['views_gained']:,}"

        rank_change = v["rank_change"]
        if rank_change > 0:
            rank_str = f"{C.GREEN}↑{rank_change}{C.END}"
        elif rank_change < 0:
            rank_str = f"{C.RED}↓{abs(rank_change)}{C.END}"
        else:
            rank_str = "—"

        # Highlight Max
        if v["name"] == "MaxAnvil1":
            print(f"{C.BOLD}{i:<3} {C.MAGENTA}{name:<20}{C.END} {velocity:<10} {gained:<10} {rank_str}")
        else:
            print(f"{i:<3} {name:<20} {velocity:<10} {gained:<10} {rank_str}")

    # Show Max separately if not in top 15
    if report["max_anvil"] and report["max_anvil"]["name"] not in [v["name"] for v in report["fastest_climbers"]]:
        v = report["max_anvil"]
        print("-" * 60)
        print(f"{C.MAGENTA}MAX: #{v['current_rank']} | +{v['velocity']:,.0f}/hr | +{v['views_gained']:,} views{C.END}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "snapshot":
            print(f"{C.CYAN}Taking snapshot...{C.END}")
            result = take_snapshot()
            print(f"  Tracked {result.get('agents_tracked', 0)} agents")
            print(f"  Total snapshots: {result.get('total_snapshots', 0)}")

        elif cmd == "report":
            hours = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
            print_velocity_report(hours=hours)

        elif cmd == "top":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            velocities = calculate_velocity(hours=1.0)
            print(f"\n{C.BOLD}Top {n} Fastest Climbers (views/hour):{C.END}")
            for i, v in enumerate(velocities[:n], 1):
                print(f"  {i}. {v['name']}: +{v['velocity']:,.0f}/hr ({v['views_gained']:,} gained)")

        else:
            print("Usage:")
            print("  velocity_tracker.py snapshot     - Take a new snapshot")
            print("  velocity_tracker.py report [hrs] - Show velocity report")
            print("  velocity_tracker.py top [n]      - Show top n climbers")
    else:
        # Default: take snapshot and show report
        print(f"{C.BOLD}{C.CYAN}📸 VELOCITY TRACKER{C.END}")
        result = take_snapshot()
        print(f"  Snapshot: {result.get('agents_tracked', 0)} agents tracked")
        print_velocity_report(hours=1.0)
