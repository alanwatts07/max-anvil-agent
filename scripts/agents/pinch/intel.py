#!/usr/bin/env python3
"""
Pinch Intel Database - Track agents, posts, and patterns on Pinch Social

Adapted from MoltX intel_database.py for Pinch Social.
Uses engagement_score instead of views as the primary metric.

Tracks:
- Agent profiles and engagement over time
- Posts and interaction patterns
- Leaderboard positions and changes
"""
import os
import sys
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Setup paths
SCRIPT_DIR = Path(__file__).parent
AGENTS_DIR = SCRIPT_DIR.parent
MOLTX_DIR = AGENTS_DIR.parent.parent
sys.path.insert(0, str(AGENTS_DIR))

from pinch_client import get_leaderboard, get_agent, get_feed, get_agent_pinches, pinch_request

# Database
DB_FILE = MOLTX_DIR / "data" / "pinch_intel.db"
DB_FILE.parent.mkdir(exist_ok=True)

# Logging
LOG_FILE = MOLTX_DIR / "logs" / "pinch_intel.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PINCH_INTEL] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("pinch_intel")


class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'


def get_connection():
    """Get database connection"""
    return sqlite3.connect(DB_FILE, timeout=30)


def init_database():
    """Initialize the database schema"""
    conn = get_connection()
    c = conn.cursor()

    # Agents table
    c.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            username TEXT PRIMARY KEY,
            name TEXT,
            bio TEXT,
            party TEXT,
            verified INTEGER DEFAULT 0,
            joined_at TEXT,
            first_seen TEXT,
            last_seen TEXT,
            pinch_count INTEGER DEFAULT 0,
            follower_count INTEGER DEFAULT 0,
            following_count INTEGER DEFAULT 0,
            total_snaps INTEGER DEFAULT 0,
            total_repinches INTEGER DEFAULT 0,
            engagement_score INTEGER DEFAULT 0,
            tip_total INTEGER DEFAULT 0,
            avatar_url TEXT,
            twitter_handle TEXT,
            notes TEXT
        )
    ''')

    # Agent snapshots - track metrics over time
    c.execute('''
        CREATE TABLE IF NOT EXISTS agent_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            timestamp TEXT,
            pinch_count INTEGER,
            follower_count INTEGER,
            following_count INTEGER,
            total_snaps INTEGER,
            engagement_score INTEGER,
            leaderboard_position INTEGER,
            leaderboard_category TEXT,
            FOREIGN KEY (username) REFERENCES agents(username)
        )
    ''')

    # Posts (pinches) table
    c.execute('''
        CREATE TABLE IF NOT EXISTS pinches (
            id TEXT PRIMARY KEY,
            author TEXT,
            content TEXT,
            created_at TEXT,
            snap_count INTEGER DEFAULT 0,
            repinch_count INTEGER DEFAULT 0,
            reply_count INTEGER DEFAULT 0,
            is_reply INTEGER DEFAULT 0,
            reply_to TEXT,
            ingested_at TEXT,
            last_updated TEXT,
            FOREIGN KEY (author) REFERENCES agents(username)
        )
    ''')

    # Interactions - track our interactions with agents
    c.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT,
            interaction_type TEXT,
            pinch_id TEXT,
            content TEXT,
            timestamp TEXT,
            our_response TEXT,
            FOREIGN KEY (agent) REFERENCES agents(username)
        )
    ''')

    # Leaderboard history
    c.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            category TEXT,
            position INTEGER,
            username TEXT,
            engagement_score INTEGER,
            pinch_count INTEGER
        )
    ''')

    # Create indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_user ON agent_snapshots(username)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON agent_snapshots(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pinches_author ON pinches(author)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_interactions_agent ON interactions(agent)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lb_time ON leaderboard_history(timestamp)")

    conn.commit()
    conn.close()
    logger.info("Pinch Intel database initialized")


# ============================================================================
# AGENT TRACKING
# ============================================================================

def upsert_agent(agent_data: dict) -> bool:
    """Insert or update agent profile"""
    conn = get_connection()
    c = conn.cursor()

    username = agent_data.get('username')
    if not username:
        conn.close()
        return False

    now = datetime.now().isoformat()

    c.execute('''
        INSERT INTO agents (
            username, name, bio, party, verified, joined_at, first_seen, last_seen,
            pinch_count, follower_count, following_count, total_snaps, total_repinches,
            engagement_score, tip_total, avatar_url, twitter_handle
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            name = excluded.name,
            bio = excluded.bio,
            party = excluded.party,
            verified = excluded.verified,
            last_seen = excluded.last_seen,
            pinch_count = excluded.pinch_count,
            follower_count = excluded.follower_count,
            following_count = excluded.following_count,
            total_snaps = excluded.total_snaps,
            total_repinches = excluded.total_repinches,
            engagement_score = excluded.engagement_score,
            tip_total = excluded.tip_total,
            avatar_url = excluded.avatar_url,
            twitter_handle = excluded.twitter_handle
    ''', (
        username,
        agent_data.get('name', ''),
        agent_data.get('bio', ''),
        agent_data.get('party', 'neutral'),
        1 if agent_data.get('verified') else 0,
        agent_data.get('joinedAt', ''),
        now,  # first_seen (won't update on conflict)
        now,  # last_seen
        agent_data.get('pinchCount', 0) or agent_data.get('postCount', 0),
        agent_data.get('followerCount', 0),
        agent_data.get('followingCount', 0),
        agent_data.get('totalSnaps', 0),
        agent_data.get('totalRepinches', 0),
        agent_data.get('engagementScore', 0),
        agent_data.get('tipTotal', 0),
        agent_data.get('avatarUrl', ''),
        agent_data.get('twitter_handle', '')
    ))

    conn.commit()
    conn.close()
    return True


def get_agent_profile(username: str) -> dict:
    """Get agent profile from database"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM agents WHERE username = ?", (username,))
    row = c.fetchone()

    if not row:
        conn.close()
        return None

    columns = [desc[0] for desc in c.description]
    profile = dict(zip(columns, row))
    conn.close()
    return profile


def take_agent_snapshot(username: str, leaderboard_pos: int = None, lb_category: str = None):
    """Take a snapshot of agent's current stats"""
    profile = get_agent_profile(username)
    if not profile:
        return

    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        INSERT INTO agent_snapshots (
            username, timestamp, pinch_count, follower_count, following_count,
            total_snaps, engagement_score, leaderboard_position, leaderboard_category
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        username,
        datetime.now().isoformat(),
        profile.get('pinch_count', 0),
        profile.get('follower_count', 0),
        profile.get('following_count', 0),
        profile.get('total_snaps', 0),
        profile.get('engagement_score', 0),
        leaderboard_pos,
        lb_category
    ))

    conn.commit()
    conn.close()


# ============================================================================
# LEADERBOARD TRACKING
# ============================================================================

def ingest_leaderboard() -> dict:
    """Fetch and store leaderboard data"""
    logger.info("Ingesting Pinch leaderboard...")

    result = get_leaderboard()
    if not result.get('ok'):
        logger.error(f"Failed to fetch leaderboard: {result}")
        return {"error": "Failed to fetch"}

    lb = result.get('leaderboard', {})
    now = datetime.now().isoformat()
    stats = {"agents_updated": 0, "positions_tracked": 0}

    conn = get_connection()
    c = conn.cursor()

    for category in ['risingStars', 'mostActive', 'mostSnapped']:
        agents = lb.get(category, [])

        for pos, agent in enumerate(agents, 1):
            username = agent.get('username')
            if not username:
                continue

            # Update agent profile inline (avoid nested connection)
            c.execute('''
                INSERT INTO agents (
                    username, name, bio, party, verified, joined_at, first_seen, last_seen,
                    pinch_count, follower_count, following_count, total_snaps, total_repinches,
                    engagement_score, tip_total, avatar_url, twitter_handle
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    name = excluded.name,
                    bio = excluded.bio,
                    last_seen = excluded.last_seen,
                    pinch_count = excluded.pinch_count,
                    engagement_score = excluded.engagement_score,
                    total_snaps = excluded.total_snaps
            ''', (
                username,
                agent.get('name', ''),
                agent.get('bio', ''),
                agent.get('party', 'neutral'),
                1 if agent.get('verified') else 0,
                str(agent.get('joinedAt', '')),
                now, now,
                agent.get('pinchCount', 0) or agent.get('postCount', 0),
                agent.get('followerCount', 0),
                agent.get('followingCount', 0),
                agent.get('totalSnaps', 0),
                agent.get('totalRepinches', 0),
                agent.get('engagementScore', 0),
                agent.get('tipTotal', 0),
                agent.get('avatarUrl', ''),
                agent.get('twitter_handle', '')
            ))
            stats["agents_updated"] += 1

            # Record leaderboard position
            c.execute('''
                INSERT INTO leaderboard_history (
                    timestamp, category, position, username, engagement_score, pinch_count
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                now, category, pos, username,
                agent.get('engagementScore', 0),
                agent.get('postCount', 0)
            ))
            stats["positions_tracked"] += 1

    conn.commit()
    conn.close()

    logger.info(f"Leaderboard ingested: {stats}")
    return stats


def get_max_leaderboard_position() -> dict:
    """Get Max's current leaderboard positions"""
    conn = get_connection()
    c = conn.cursor()

    # Get most recent positions for maxanvil
    c.execute('''
        SELECT category, position, engagement_score, timestamp
        FROM leaderboard_history
        WHERE username = 'maxanvil'
        AND timestamp > datetime('now', '-1 hour')
        ORDER BY timestamp DESC
    ''')

    positions = {}
    for row in c.fetchall():
        category = row[0]
        if category not in positions:
            positions[category] = {
                "position": row[1],
                "score": row[2],
                "timestamp": row[3]
            }

    conn.close()
    return positions


def get_leaderboard_changes(hours: int = 24) -> dict:
    """Get significant leaderboard changes in last N hours"""
    conn = get_connection()
    c = conn.cursor()

    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    # Get position changes for tracked agents
    c.execute('''
        SELECT username, category,
               MIN(position) as best_pos,
               MAX(position) as worst_pos,
               COUNT(*) as samples
        FROM leaderboard_history
        WHERE timestamp > ?
        GROUP BY username, category
        HAVING COUNT(*) > 1
        ORDER BY (MAX(position) - MIN(position)) DESC
        LIMIT 20
    ''', (cutoff,))

    changes = []
    for row in c.fetchall():
        change = row[4] - row[3]  # worst - best (negative = climbing)
        if abs(change) >= 2:
            changes.append({
                "username": row[0],
                "category": row[1],
                "best": row[2],
                "worst": row[3],
                "change": change,
                "climbing": change < 0
            })

    conn.close()
    return {"changes": changes, "period_hours": hours}


# ============================================================================
# INTERACTION TRACKING
# ============================================================================

def record_interaction(agent: str, interaction_type: str, pinch_id: str = None,
                       content: str = None, our_response: str = None):
    """Record an interaction with an agent"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        INSERT INTO interactions (agent, interaction_type, pinch_id, content, timestamp, our_response)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (agent, interaction_type, pinch_id, content, datetime.now().isoformat(), our_response))

    conn.commit()
    conn.close()


def get_interaction_count(agent: str) -> int:
    """Get total interactions with an agent"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM interactions WHERE agent = ?", (agent,))
    count = c.fetchone()[0]

    conn.close()
    return count


def get_recent_interactions(agent: str, limit: int = 10) -> list:
    """Get recent interactions with an agent"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT * FROM interactions
        WHERE agent = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (agent, limit))

    columns = [desc[0] for desc in c.description]
    interactions = [dict(zip(columns, row)) for row in c.fetchall()]

    conn.close()
    return interactions


def get_top_interacting_agents(limit: int = 20) -> list:
    """Get agents we interact with most"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT agent, COUNT(*) as count,
               MAX(timestamp) as last_interaction
        FROM interactions
        GROUP BY agent
        ORDER BY count DESC
        LIMIT ?
    ''', (limit,))

    results = [{"agent": row[0], "interactions": row[1], "last": row[2]} for row in c.fetchall()]

    conn.close()
    return results


# ============================================================================
# FEED INGESTION
# ============================================================================

def ingest_feed(limit: int = 50) -> dict:
    """Ingest posts from the feed"""
    logger.info(f"Ingesting feed (limit={limit})...")

    result = get_feed(limit=limit)
    pinches = result.get('pinches', [])

    if not pinches:
        logger.warning("No pinches in feed")
        return {"error": "No pinches", "ingested": 0}

    conn = get_connection()
    c = conn.cursor()

    now = datetime.now().isoformat()
    ingested = 0
    agents_seen = set()

    for pinch in pinches:
        pinch_id = pinch.get('id')
        if not pinch_id:
            continue

        author = pinch.get('author') or pinch.get('agent', {}).get('username')
        if not author:
            continue

        agents_seen.add(author)

        # Upsert pinch
        c.execute('''
            INSERT INTO pinches (
                id, author, content, created_at, snap_count, repinch_count,
                reply_count, is_reply, reply_to, ingested_at, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                snap_count = excluded.snap_count,
                repinch_count = excluded.repinch_count,
                reply_count = excluded.reply_count,
                last_updated = excluded.last_updated
        ''', (
            pinch_id,
            author,
            pinch.get('content', ''),
            pinch.get('createdAt', ''),
            pinch.get('snapCount', 0),
            pinch.get('repinchCount', 0),
            pinch.get('replyCount', 0),
            1 if pinch.get('replyTo') else 0,
            pinch.get('replyTo'),
            now,
            now
        ))
        ingested += 1

        # Update agent if we have their data (inline to avoid lock)
        agent_data = pinch.get('agent')
        if agent_data and agent_data.get('username'):
            c.execute('''
                INSERT INTO agents (username, name, bio, party, verified, first_seen, last_seen,
                    pinch_count, engagement_score, avatar_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    name = excluded.name,
                    last_seen = excluded.last_seen,
                    pinch_count = excluded.pinch_count
            ''', (
                agent_data.get('username'),
                agent_data.get('name', ''),
                agent_data.get('bio', ''),
                agent_data.get('party', 'neutral'),
                1 if agent_data.get('verified') else 0,
                now, now,
                agent_data.get('pinchCount', 0),
                agent_data.get('engagementScore', 0),
                agent_data.get('avatarUrl', '')
            ))

    conn.commit()
    conn.close()

    logger.info(f"Ingested {ingested} pinches from {len(agents_seen)} agents")
    return {"ingested": ingested, "agents": len(agents_seen)}


# ============================================================================
# ANALYTICS
# ============================================================================

def get_engagement_velocity(username: str, hours: int = 24) -> dict:
    """Calculate engagement velocity for an agent"""
    conn = get_connection()
    c = conn.cursor()

    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    c.execute('''
        SELECT engagement_score, timestamp
        FROM agent_snapshots
        WHERE username = ? AND timestamp > ?
        ORDER BY timestamp ASC
    ''', (username, cutoff))

    rows = c.fetchall()
    conn.close()

    if len(rows) < 2:
        return {"error": "Not enough data"}

    first_score = rows[0][0]
    last_score = rows[-1][0]
    first_time = datetime.fromisoformat(rows[0][1])
    last_time = datetime.fromisoformat(rows[-1][1])

    hours_elapsed = (last_time - first_time).total_seconds() / 3600
    if hours_elapsed < 0.1:
        return {"error": "Time range too short"}

    velocity = (last_score - first_score) / hours_elapsed

    return {
        "username": username,
        "start_score": first_score,
        "end_score": last_score,
        "gained": last_score - first_score,
        "hours": round(hours_elapsed, 2),
        "velocity_per_hour": round(velocity, 2)
    }


def get_rising_agents(hours: int = 24, min_gain: int = 10) -> list:
    """Find agents with fastest rising engagement"""
    conn = get_connection()
    c = conn.cursor()

    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    # Get agents with snapshots in the period
    c.execute('''
        SELECT DISTINCT username FROM agent_snapshots
        WHERE timestamp > ?
    ''', (cutoff,))

    usernames = [row[0] for row in c.fetchall()]
    conn.close()

    rising = []
    for username in usernames:
        velocity = get_engagement_velocity(username, hours)
        if "error" not in velocity and velocity.get("gained", 0) >= min_gain:
            rising.append(velocity)

    rising.sort(key=lambda x: x.get("velocity_per_hour", 0), reverse=True)
    return rising[:20]


# ============================================================================
# CLI
# ============================================================================

def print_status():
    """Print current intel status"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM agents")
    agent_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM pinches")
    pinch_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM interactions")
    interaction_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM leaderboard_history")
    lb_count = c.fetchone()[0]

    conn.close()

    print(f"\n{C.BOLD}{C.CYAN}📊 PINCH INTEL STATUS{C.END}")
    print("=" * 40)
    print(f"  Agents tracked: {agent_count}")
    print(f"  Pinches stored: {pinch_count}")
    print(f"  Interactions: {interaction_count}")
    print(f"  Leaderboard entries: {lb_count}")

    # Max's position
    positions = get_max_leaderboard_position()
    if positions:
        print(f"\n{C.MAGENTA}Max's positions:{C.END}")
        for cat, data in positions.items():
            print(f"  {cat}: #{data['position']} (score: {data['score']})")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pinch Intel Database")
    parser.add_argument("command", nargs="?", default="status",
                       choices=["init", "status", "ingest", "leaderboard", "velocity"])
    parser.add_argument("--agent", "-a", help="Agent username")
    parser.add_argument("--hours", type=int, default=24, help="Hours for velocity calc")

    args = parser.parse_args()

    if args.command == "init":
        init_database()
        print("Database initialized")

    elif args.command == "status":
        init_database()
        print_status()

    elif args.command == "ingest":
        init_database()
        ingest_leaderboard()
        ingest_feed()
        print_status()

    elif args.command == "leaderboard":
        init_database()
        ingest_leaderboard()
        positions = get_max_leaderboard_position()
        print(json.dumps(positions, indent=2))

    elif args.command == "velocity":
        init_database()
        if args.agent:
            v = get_engagement_velocity(args.agent, args.hours)
            print(json.dumps(v, indent=2))
        else:
            rising = get_rising_agents(args.hours)
            for r in rising[:10]:
                print(f"@{r['username']}: +{r['gained']} ({r['velocity_per_hour']}/hr)")
