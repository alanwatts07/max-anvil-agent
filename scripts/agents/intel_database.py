#!/usr/bin/env python3
"""
Intel Database - Track agents, posts, and patterns on MoltX

Stores everything in SQLite for easy querying and research.
Claude can dig through this for insights on demand.

Tracks:
- Agent profiles and stats over time
- All posts from agents with 25+ followers
- Websites/links shared
- Detected patterns (shillers, repetitive, interesting, evolving)
"""
import os
import re
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

# Setup
MOLTX_DIR = Path(__file__).parent.parent.parent
DB_FILE = MOLTX_DIR / "data" / "intel.db"
DB_FILE.parent.mkdir(exist_ok=True)

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE_URL = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Logging
LOG_FILE = MOLTX_DIR / "logs" / "intel_database.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [INTEL] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("intel_database")

# Minimum followers to track
MIN_FOLLOWERS = 25


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

    # Migration: Add new columns to posts table if they don't exist
    try:
        c.execute("SELECT quotes FROM posts LIMIT 1")
    except:
        # Old schema - need to migrate
        logger.info("Migrating posts table to new schema...")
        try:
            c.execute("ALTER TABLE posts ADD COLUMN quotes INTEGER DEFAULT 0")
            c.execute("ALTER TABLE posts ADD COLUMN views INTEGER DEFAULT 0")
            c.execute("ALTER TABLE posts ADD COLUMN is_quote INTEGER DEFAULT 0")
            c.execute("ALTER TABLE posts ADD COLUMN is_repost INTEGER DEFAULT 0")
            c.execute("ALTER TABLE posts ADD COLUMN quoted_post_id TEXT")
            c.execute("ALTER TABLE posts ADD COLUMN mentions TEXT DEFAULT '[]'")
            c.execute("ALTER TABLE posts ADD COLUMN hashtags TEXT DEFAULT '[]'")
            c.execute("ALTER TABLE posts ADD COLUMN media_urls TEXT DEFAULT '[]'")
            c.execute("ALTER TABLE posts ADD COLUMN raw_json TEXT")
            c.execute("ALTER TABLE posts ADD COLUMN last_updated TEXT")
            conn.commit()
            logger.info("Posts table migrated successfully")
        except Exception as e:
            logger.warning(f"Migration may have partially failed: {e}")

    # Agents table - profiles
    c.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            name TEXT PRIMARY KEY,
            display_name TEXT,
            bio TEXT,
            avatar_emoji TEXT,
            first_seen TEXT,
            last_seen TEXT,
            current_followers INTEGER DEFAULT 0,
            current_following INTEGER DEFAULT 0,
            current_views INTEGER DEFAULT 0,
            current_posts INTEGER DEFAULT 0,
            current_likes INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            notes TEXT
        )
    ''')

    # Agent snapshots - stats over time
    c.execute('''
        CREATE TABLE IF NOT EXISTS agent_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            timestamp TEXT,
            followers INTEGER,
            following INTEGER,
            views INTEGER,
            posts INTEGER,
            likes INTEGER,
            FOREIGN KEY (agent_name) REFERENCES agents(name)
        )
    ''')

    # Posts table - expanded to store ALL available fields
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            agent_name TEXT,
            content TEXT,
            timestamp TEXT,
            likes INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            reposts INTEGER DEFAULT 0,
            quotes INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            is_reply INTEGER DEFAULT 0,
            is_quote INTEGER DEFAULT 0,
            is_repost INTEGER DEFAULT 0,
            parent_id TEXT,
            quoted_post_id TEXT,
            mentions TEXT DEFAULT '[]',
            hashtags TEXT DEFAULT '[]',
            media_urls TEXT DEFAULT '[]',
            raw_json TEXT,
            ingested_at TEXT,
            last_updated TEXT,
            FOREIGN KEY (agent_name) REFERENCES agents(name)
        )
    ''')

    # Websites/links found in posts
    c.execute('''
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            domain TEXT,
            agent_name TEXT,
            post_id TEXT,
            first_seen TEXT,
            times_shared INTEGER DEFAULT 1,
            FOREIGN KEY (agent_name) REFERENCES agents(name),
            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Patterns detected
    c.execute('''
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            pattern_type TEXT,
            description TEXT,
            confidence REAL,
            detected_at TEXT,
            evidence TEXT,
            FOREIGN KEY (agent_name) REFERENCES agents(name)
        )
    ''')

    # Post snapshots - track post engagement over time
    c.execute('''
        CREATE TABLE IF NOT EXISTS post_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT,
            timestamp TEXT,
            likes INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            reposts INTEGER DEFAULT 0,
            quotes INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Interactions - track who engages with whom
    c.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT,
            to_agent TEXT,
            interaction_type TEXT,
            post_id TEXT,
            timestamp TEXT,
            content_preview TEXT,
            FOREIGN KEY (from_agent) REFERENCES agents(name),
            FOREIGN KEY (to_agent) REFERENCES agents(name),
            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Agent relationships - followers/following connections
    c.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower TEXT,
            following TEXT,
            first_seen TEXT,
            still_active INTEGER DEFAULT 1,
            FOREIGN KEY (follower) REFERENCES agents(name),
            FOREIGN KEY (following) REFERENCES agents(name),
            UNIQUE(follower, following)
        )
    ''')

    # Create indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_agent ON posts(agent_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_timestamp ON posts(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_agent ON agent_snapshots(agent_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_websites_domain ON websites(domain)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_post_snapshots_post ON post_snapshots(post_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_interactions_from ON interactions(from_agent)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_interactions_to ON interactions(to_agent)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(interaction_type)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_relationships_follower ON relationships(follower)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_relationships_following ON relationships(following)')

    conn.commit()
    conn.close()
    logger.info("Database initialized")


def extract_urls(text: str) -> list:
    """Extract URLs from text"""
    if not text:
        return []
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    return urls


def extract_mentions(text: str) -> list:
    """Extract @mentions from text"""
    if not text:
        return []
    mention_pattern = r'@(\w+)'
    mentions = re.findall(mention_pattern, text)
    return mentions


def extract_hashtags(text: str) -> list:
    """Extract #hashtags from text"""
    if not text:
        return []
    hashtag_pattern = r'#(\w+)'
    hashtags = re.findall(hashtag_pattern, text)
    return hashtags


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return url


def upsert_agent(conn, agent_data: dict):
    """Insert or update an agent"""
    c = conn.cursor()
    now = datetime.now().isoformat()

    name = agent_data.get('name', '')
    if not name:
        return

    # Check if exists
    c.execute('SELECT name, first_seen FROM agents WHERE name = ?', (name,))
    existing = c.fetchone()

    if existing:
        # Update
        c.execute('''
            UPDATE agents SET
                display_name = COALESCE(?, display_name),
                bio = COALESCE(?, bio),
                avatar_emoji = COALESCE(?, avatar_emoji),
                last_seen = ?,
                current_followers = COALESCE(?, current_followers),
                current_following = COALESCE(?, current_following),
                current_views = COALESCE(?, current_views),
                current_posts = COALESCE(?, current_posts),
                current_likes = COALESCE(?, current_likes)
            WHERE name = ?
        ''', (
            agent_data.get('display_name'),
            agent_data.get('bio'),
            agent_data.get('avatar_emoji'),
            now,
            agent_data.get('followers'),
            agent_data.get('following'),
            agent_data.get('views'),
            agent_data.get('posts'),
            agent_data.get('likes'),
            name
        ))
    else:
        # Insert
        c.execute('''
            INSERT INTO agents (name, display_name, bio, avatar_emoji, first_seen, last_seen,
                               current_followers, current_following, current_views, current_posts, current_likes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name,
            agent_data.get('display_name'),
            agent_data.get('bio'),
            agent_data.get('avatar_emoji'),
            now,
            now,
            agent_data.get('followers', 0),
            agent_data.get('following', 0),
            agent_data.get('views', 0),
            agent_data.get('posts', 0),
            agent_data.get('likes', 0)
        ))


def add_agent_snapshot(conn, agent_name: str, stats: dict):
    """Add a snapshot of agent stats"""
    c = conn.cursor()
    c.execute('''
        INSERT INTO agent_snapshots (agent_name, timestamp, followers, following, views, posts, likes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        agent_name,
        datetime.now().isoformat(),
        stats.get('followers', 0),
        stats.get('following', 0),
        stats.get('views', 0),
        stats.get('posts', 0),
        stats.get('likes', 0)
    ))


def upsert_post(conn, post_data: dict, store_raw: bool = True):
    """Insert or update a post with ALL available fields"""
    c = conn.cursor()

    post_id = post_data.get('id', '')
    if not post_id:
        return

    agent = post_data.get('agent', {})
    agent_name = agent.get('name', '') if isinstance(agent, dict) else ''
    if not agent_name:
        agent_name = post_data.get('author_name', '')

    content = post_data.get('content') or ''
    now = datetime.now().isoformat()

    # Extract mentions, hashtags, media
    mentions = extract_mentions(content)
    hashtags = extract_hashtags(content)
    media_urls = post_data.get('media', []) or post_data.get('media_urls', []) or []

    # Get engagement stats (handle various API field names)
    likes = post_data.get('like_count') or post_data.get('likes_count') or post_data.get('likes', 0)
    replies = post_data.get('reply_count') or post_data.get('replies_count') or post_data.get('replies', 0)
    reposts = post_data.get('repost_count') or post_data.get('reposts_count') or post_data.get('reposts', 0)
    quotes = post_data.get('quote_count') or post_data.get('quotes_count') or post_data.get('quotes', 0)
    views = post_data.get('view_count') or post_data.get('views_count') or post_data.get('views', 0)

    # Determine post type
    is_reply = 1 if post_data.get('parent_id') else 0
    is_quote = 1 if post_data.get('quoted_post_id') or post_data.get('quoted_post') else 0
    is_repost = 1 if post_data.get('type') == 'repost' else 0

    # Store raw JSON for future parsing
    raw_json = json.dumps(post_data) if store_raw else None

    # Check if exists
    c.execute('SELECT id FROM posts WHERE id = ?', (post_id,))
    existing = c.fetchone()

    if existing:
        # Update engagement counts and last_updated
        c.execute('''
            UPDATE posts SET
                likes = ?,
                replies = ?,
                reposts = ?,
                quotes = ?,
                views = ?,
                last_updated = ?,
                raw_json = COALESCE(?, raw_json)
            WHERE id = ?
        ''', (likes, replies, reposts, quotes, views, now, raw_json, post_id))

        # Also add a snapshot to track engagement over time
        c.execute('''
            INSERT INTO post_snapshots (post_id, timestamp, likes, replies, reposts, quotes, views)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (post_id, now, likes, replies, reposts, quotes, views))
    else:
        # Insert new post with all fields
        c.execute('''
            INSERT INTO posts (id, agent_name, content, timestamp, likes, replies, reposts,
                              quotes, views, is_reply, is_quote, is_repost, parent_id,
                              quoted_post_id, mentions, hashtags, media_urls, raw_json,
                              ingested_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            post_id,
            agent_name,
            content,
            post_data.get('created_at', ''),
            likes, replies, reposts, quotes, views,
            is_reply, is_quote, is_repost,
            post_data.get('parent_id'),
            post_data.get('quoted_post_id'),
            json.dumps(mentions),
            json.dumps(hashtags),
            json.dumps(media_urls),
            raw_json,
            now,
            now
        ))

        # Extract and store URLs
        urls = extract_urls(content)
        for url in urls:
            domain = extract_domain(url)
            c.execute('''
                INSERT INTO websites (url, domain, agent_name, post_id, first_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET times_shared = times_shared + 1
            ''', (url, domain, agent_name, post_id, now))

        # Track interactions (who mentioned whom)
        for mentioned in mentions:
            if mentioned != agent_name:  # Don't track self-mentions
                c.execute('''
                    INSERT INTO interactions (from_agent, to_agent, interaction_type, post_id, timestamp, content_preview)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (agent_name, mentioned, 'mention', post_id, now, content[:100]))

        # Track reply interactions
        if is_reply and post_data.get('parent_id'):
            # Try to find parent post author
            c.execute('SELECT agent_name FROM posts WHERE id = ?', (post_data.get('parent_id'),))
            parent = c.fetchone()
            if parent and parent[0]:
                c.execute('''
                    INSERT INTO interactions (from_agent, to_agent, interaction_type, post_id, timestamp, content_preview)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (agent_name, parent[0], 'reply', post_id, now, content[:100]))


def add_pattern(conn, agent_name: str, pattern_type: str, description: str,
                confidence: float, evidence: str = None):
    """Record a detected pattern"""
    c = conn.cursor()
    c.execute('''
        INSERT INTO patterns (agent_name, pattern_type, description, confidence, detected_at, evidence)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (agent_name, pattern_type, description, confidence, datetime.now().isoformat(), evidence))


def ingest_leaderboard():
    """Ingest agents from the leaderboard"""
    print(f"\n{C.BOLD}{C.CYAN}📊 INGESTING LEADERBOARD{C.END}")

    conn = get_connection()
    agents_added = 0

    for metric in ['views', 'followers']:
        try:
            r = requests.get(f"{BASE_URL}/leaderboard?metric={metric}&limit=100",
                           headers=HEADERS, timeout=30)
            if r.status_code == 200:
                leaders = r.json().get('data', {}).get('leaders', [])
                for agent in leaders:
                    followers = agent.get('value', 0) if metric == 'followers' else 0

                    agent_data = {
                        'name': agent.get('name'),
                        'display_name': agent.get('display_name'),
                        'avatar_emoji': agent.get('avatar_emoji'),
                        'followers': followers if metric == 'followers' else None,
                        'views': agent.get('value') if metric == 'views' else None,
                    }

                    # Only track agents with enough followers
                    if metric == 'followers' and followers >= MIN_FOLLOWERS:
                        upsert_agent(conn, agent_data)
                        agents_added += 1
                    elif metric == 'views':
                        upsert_agent(conn, agent_data)

        except Exception as e:
            logger.error(f"Error fetching {metric} leaderboard: {e}")

    conn.commit()
    conn.close()
    print(f"  {C.GREEN}Added/updated {agents_added} agents{C.END}")
    return agents_added


def fetch_agent_profile(name: str) -> dict:
    """Fetch agent profile using NEW /v1/agents/profile endpoint (v0.17.6)"""
    try:
        r = requests.get(f"{BASE_URL}/agents/profile?name={name}&limit=20",
                        headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get('data', {})
            # Profile data is nested under 'agent' key
            agent = data.get('agent', {})
            # Merge posts into agent dict for convenience
            agent['posts'] = data.get('posts', [])
            return agent
    except Exception as e:
        logger.warning(f"Failed to fetch profile for {name}: {e}")
    return {}


def fetch_agent_stats(name: str) -> dict:
    """Fetch agent stats using /v1/agent/X/stats endpoint (v0.17.6)

    Returns current followers, following, total_posts, total_likes_received,
    plus 24h and 7d metrics.
    """
    try:
        r = requests.get(f"{BASE_URL}/agent/{name}/stats", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json().get('data', {})
    except Exception as e:
        logger.warning(f"Failed to fetch stats for {name}: {e}")
    return {}


def fetch_agent_activity(name: str, metric: str = "posts", granularity: str = "daily", range: str = "7d") -> dict:
    """Fetch agent activity graph using NEW /v1/agent/X/activity endpoint (v0.17.6)

    Args:
        metric: posts, likes, replies
        granularity: hourly, daily
        range: 7d, 30d, 90d
    """
    try:
        r = requests.get(
            f"{BASE_URL}/agent/{name}/activity?metric={metric}&granularity={granularity}&range={range}",
            headers=HEADERS, timeout=15
        )
        if r.status_code == 200:
            return r.json().get('data', {})
    except Exception as e:
        logger.warning(f"Failed to fetch activity for {name}: {e}")
    return {}


def fetch_agent_spectate_feed(name: str, limit: int = 20) -> list:
    """Fetch agent's personalized feed using NEW /v1/feed/spectate endpoint (v0.17.6)"""
    try:
        r = requests.get(f"{BASE_URL}/feed/spectate/{name}?limit={limit}",
                        headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json().get('data', {})
            return data.get('posts', []) if isinstance(data, dict) else data
    except Exception as e:
        logger.warning(f"Failed to fetch spectate feed for {name}: {e}")
    return []


def ingest_agent_deep(name: str):
    """Deep ingest a specific agent using new API endpoints"""
    print(f"\n{C.BOLD}{C.CYAN}🔍 DEEP INGEST: @{name}{C.END}")

    conn = get_connection()

    # 1. Fetch full profile
    profile = fetch_agent_profile(name)

    # 2. Fetch stats (has follower counts etc)
    stats = fetch_agent_stats(name)
    current = stats.get('current', {})

    followers = current.get('followers', 0)
    following = current.get('following', 0)
    total_posts = current.get('total_posts', 0)
    total_likes = current.get('total_likes_received', 0)

    if profile or stats:
        agent_data = {
            'name': profile.get('name') or stats.get('name') or name,
            'display_name': profile.get('display_name') or stats.get('display_name'),
            'bio': profile.get('description'),
            'avatar_emoji': profile.get('avatar_emoji') or stats.get('avatar_emoji'),
            'followers': followers,
            'following': following,
            'posts': total_posts,
            'likes': total_likes,
        }
        upsert_agent(conn, agent_data)
        print(f"  ✓ Stats: {followers} followers, {total_posts} posts, {total_likes} likes")

        # Show 24h metrics if available
        recent = stats.get('recent_24h', {})
        if recent:
            print(f"  ✓ 24h: {recent.get('posts', 0)} posts, {recent.get('impressions', 0)} impressions")

        # Store recent posts from profile
        recent_posts = profile.get('posts', [])
        for post in recent_posts:
            upsert_post(conn, post)
        print(f"  ✓ Ingested {len(recent_posts)} recent posts")

        # Add snapshot
        add_agent_snapshot(conn, name, {
            'followers': profile.get('followers_count', 0),
            'following': profile.get('following_count', 0),
            'views': profile.get('views', 0),
            'posts': profile.get('posts_count', 0),
            'likes': profile.get('likes_count', 0),
        })

    # 2. Fetch activity data
    activity = fetch_agent_activity(name, metric="posts", granularity="daily", range="7d")
    if activity:
        # Could store this in a new table, for now just log
        data_points = activity.get('data', [])
        if data_points:
            total = sum(p.get('value', 0) for p in data_points)
            print(f"  ✓ Activity: {total} posts in last 7 days")

    # 3. Fetch their feed (who they engage with)
    spectate_posts = fetch_agent_spectate_feed(name, limit=30)
    for post in spectate_posts:
        upsert_post(conn, post)
    print(f"  ✓ Spectate feed: {len(spectate_posts)} posts")

    conn.commit()
    conn.close()
    return {'profile': profile, 'posts_ingested': len(profile.get('posts', [])) + len(spectate_posts)}


def ingest_feed(limit: int = 100):
    """Ingest posts from the global feed"""
    print(f"\n{C.BOLD}{C.CYAN}📥 INGESTING FEED{C.END}")

    conn = get_connection()
    posts_added = 0

    try:
        r = requests.get(f"{BASE_URL}/feed/global?limit={limit}", headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json().get('data', {})
            posts = data.get('posts', []) if isinstance(data, dict) else data

            for post in posts:
                agent = post.get('agent', {})
                agent_name = agent.get('name', '') if isinstance(agent, dict) else ''

                # Get agent's followers if we don't have them
                if agent_name:
                    # Upsert agent
                    upsert_agent(conn, {
                        'name': agent_name,
                        'display_name': agent.get('display_name') if isinstance(agent, dict) else None,
                        'avatar_emoji': agent.get('avatar_emoji') if isinstance(agent, dict) else None,
                    })

                # Store post
                upsert_post(conn, post)
                posts_added += 1

    except Exception as e:
        logger.error(f"Error ingesting feed: {e}")

    conn.commit()
    conn.close()
    print(f"  {C.GREEN}Ingested {posts_added} posts{C.END}")
    return posts_added


def bulk_ingest(top_n: int = 100, delay: float = 0.3):
    """Bulk ingest posts from top N agents' profiles"""
    import time
    print(f"\n{C.BOLD}{C.CYAN}📥 BULK INGESTING FROM TOP {top_n} AGENTS{C.END}")

    conn = get_connection()
    total_added = 0
    agents_processed = 0

    # Get top agents from leaderboard
    try:
        r = requests.get(f"{BASE_URL}/leaderboard?metric=views&limit={top_n}", headers=HEADERS, timeout=30)
        if r.status_code != 200:
            print(f"{C.RED}Failed to get leaderboard{C.END}")
            return 0
        leaders = r.json().get('data', {}).get('leaders', [])
    except Exception as e:
        print(f"{C.RED}Error getting leaderboard: {e}{C.END}")
        return 0

    print(f"  Found {len(leaders)} agents to process")

    for agent_data in leaders:
        agent_name = agent_data.get('name', '')
        if not agent_name:
            continue

        try:
            # Get agent's profile with posts
            r = requests.get(
                f"{BASE_URL}/agents/profile?name={agent_name}",
                headers=HEADERS,
                timeout=30
            )
            if r.status_code == 200:
                profile = r.json().get('data', {})
                agent_info = profile.get('agent', profile)
                posts = profile.get('posts', [])

                # Upsert agent
                upsert_agent(conn, {
                    'name': agent_name,
                    'display_name': agent_info.get('display_name'),
                    'avatar_emoji': agent_info.get('avatar_emoji'),
                    'bio': agent_info.get('description'),
                })

                # Ingest all their posts
                posts_added = 0
                for post in posts:
                    try:
                        upsert_post(conn, post)
                        posts_added += 1
                        total_added += 1
                    except:
                        pass

                agents_processed += 1
                print(f"  [{agents_processed}/{len(leaders)}] {agent_name}: +{posts_added} posts")

            time.sleep(delay)

        except Exception as e:
            logger.warning(f"Error processing {agent_name}: {e}")
            time.sleep(1)

    conn.commit()
    conn.close()
    print(f"\n{C.GREEN}Bulk ingest complete: {total_added} posts from {agents_processed} agents{C.END}")
    return total_added


def analyze_patterns():
    """Analyze agents for patterns"""
    print(f"\n{C.BOLD}{C.CYAN}🔍 ANALYZING PATTERNS{C.END}")

    conn = get_connection()
    c = conn.cursor()

    patterns_found = 0

    # Find repetitive posters (same content multiple times)
    c.execute('''
        SELECT agent_name, content, COUNT(*) as count
        FROM posts
        GROUP BY agent_name, content
        HAVING count > 2
    ''')
    for row in c.fetchall():
        agent_name, content, count = row
        add_pattern(conn, agent_name, 'repetitive',
                   f'Posted same content {count} times',
                   min(count / 5, 1.0),
                   content[:100])
        patterns_found += 1
        print(f"  {C.YELLOW}REPETITIVE: @{agent_name} - {count}x same post{C.END}")

    # Find shillers (lots of links to same domain)
    c.execute('''
        SELECT agent_name, domain, SUM(times_shared) as total
        FROM websites
        GROUP BY agent_name, domain
        HAVING total > 5
    ''')
    for row in c.fetchall():
        agent_name, domain, total = row
        add_pattern(conn, agent_name, 'shill',
                   f'Shared {domain} {total} times',
                   min(total / 10, 1.0),
                   domain)
        patterns_found += 1
        print(f"  {C.MAGENTA}SHILL: @{agent_name} - {domain} ({total}x){C.END}")

    # Find agents with websites
    c.execute('''
        SELECT DISTINCT agent_name, domain
        FROM websites
        WHERE domain NOT LIKE '%moltx%' AND domain NOT LIKE '%twitter%' AND domain NOT LIKE '%x.com%'
    ''')
    website_agents = c.fetchall()
    for agent_name, domain in website_agents:
        add_pattern(conn, agent_name, 'has_website',
                   f'Has website: {domain}',
                   0.8,
                   domain)

    if website_agents:
        print(f"  {C.CYAN}Found {len(website_agents)} agents with websites{C.END}")

    conn.commit()
    conn.close()
    print(f"  {C.GREEN}Detected {patterns_found} patterns{C.END}")
    return patterns_found


def get_stats():
    """Get database statistics"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('SELECT COUNT(*) FROM agents')
    agents = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM posts')
    posts = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM websites')
    websites = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM patterns')
    patterns = c.fetchone()[0]

    c.execute('SELECT COUNT(DISTINCT domain) FROM websites')
    domains = c.fetchone()[0]

    conn.close()

    return {
        'agents': agents,
        'posts': posts,
        'websites': websites,
        'unique_domains': domains,
        'patterns': patterns
    }


def run_intel_cycle():
    """Run a full intel gathering cycle"""
    print(f"\n{C.BOLD}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}🕵️ INTEL DATABASE - GATHERING CYCLE{C.END}")
    print(f"{C.BOLD}{'='*60}{C.END}")

    init_database()

    ingest_leaderboard()
    ingest_feed(100)
    analyze_patterns()

    stats = get_stats()
    print(f"\n{C.BOLD}📊 DATABASE STATS{C.END}")
    print(f"  Agents tracked: {stats['agents']}")
    print(f"  Posts stored: {stats['posts']}")
    print(f"  Websites found: {stats['websites']} ({stats['unique_domains']} domains)")
    print(f"  Patterns detected: {stats['patterns']}")

    logger.info(f"Intel cycle complete: {stats['agents']} agents, {stats['posts']} posts")
    return stats


# ============================================
# QUERY FUNCTIONS FOR CLAUDE TO USE
# ============================================

def query_agent(name: str) -> dict:
    """Get all info about an agent"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('SELECT * FROM agents WHERE name = ?', (name,))
    agent = c.fetchone()
    if not agent:
        conn.close()
        return None

    columns = [desc[0] for desc in c.description]
    agent_dict = dict(zip(columns, agent))

    # Get recent posts
    c.execute('SELECT * FROM posts WHERE agent_name = ? ORDER BY timestamp DESC LIMIT 10', (name,))
    posts = [dict(zip([d[0] for d in c.description], row)) for row in c.fetchall()]
    agent_dict['recent_posts'] = posts

    # Get patterns
    c.execute('SELECT * FROM patterns WHERE agent_name = ?', (name,))
    patterns = [dict(zip([d[0] for d in c.description], row)) for row in c.fetchall()]
    agent_dict['patterns'] = patterns

    # Get websites
    c.execute('SELECT DISTINCT domain, url FROM websites WHERE agent_name = ?', (name,))
    agent_dict['websites'] = c.fetchall()

    conn.close()
    return agent_dict


def query_shillers() -> list:
    """Find agents who shill a lot"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT agent_name, description, confidence
        FROM patterns
        WHERE pattern_type = 'shill'
        ORDER BY confidence DESC
    ''')
    results = c.fetchall()
    conn.close()
    return results


def query_repetitive() -> list:
    """Find repetitive posters"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT agent_name, description, confidence
        FROM patterns
        WHERE pattern_type = 'repetitive'
        ORDER BY confidence DESC
    ''')
    results = c.fetchall()
    conn.close()
    return results


def query_websites() -> list:
    """Find all websites shared"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT domain, COUNT(DISTINCT agent_name) as agents, SUM(times_shared) as shares
        FROM websites
        WHERE domain NOT LIKE '%moltx%'
        GROUP BY domain
        ORDER BY shares DESC
        LIMIT 50
    ''')
    results = c.fetchall()
    conn.close()
    return results


def query_interesting_agents() -> list:
    """Find agents with websites or unique characteristics"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT a.name, a.current_followers, a.current_views, p.description
        FROM agents a
        JOIN patterns p ON a.name = p.agent_name
        WHERE p.pattern_type = 'has_website'
        AND a.current_followers >= 25
        ORDER BY a.current_followers DESC
    ''')
    results = c.fetchall()
    conn.close()
    return results


def search_posts(keyword: str) -> list:
    """Search posts for a keyword"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT agent_name, content, timestamp, likes
        FROM posts
        WHERE content LIKE ?
        ORDER BY likes DESC
        LIMIT 20
    ''', (f'%{keyword}%',))
    results = c.fetchall()
    conn.close()
    return results


def get_agent_stats(name: str) -> dict:
    """Get comprehensive stats for an agent including growth and interactions"""
    conn = get_connection()
    c = conn.cursor()

    stats = {'name': name}

    # Current stats
    c.execute('SELECT * FROM agents WHERE name = ?', (name,))
    row = c.fetchone()
    if row:
        columns = [desc[0] for desc in c.description]
        stats['current'] = dict(zip(columns, row))

    # Historical snapshots (growth over time)
    c.execute('''
        SELECT timestamp, followers, views, posts, likes
        FROM agent_snapshots
        WHERE agent_name = ?
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (name,))
    stats['history'] = [dict(zip(['timestamp', 'followers', 'views', 'posts', 'likes'], row))
                        for row in c.fetchall()]

    # Interaction stats - who they engage with most
    c.execute('''
        SELECT to_agent, interaction_type, COUNT(*) as count
        FROM interactions
        WHERE from_agent = ?
        GROUP BY to_agent, interaction_type
        ORDER BY count DESC
        LIMIT 20
    ''', (name,))
    stats['engages_with'] = [{'agent': r[0], 'type': r[1], 'count': r[2]} for r in c.fetchall()]

    # Interaction stats - who engages with them
    c.execute('''
        SELECT from_agent, interaction_type, COUNT(*) as count
        FROM interactions
        WHERE to_agent = ?
        GROUP BY from_agent, interaction_type
        ORDER BY count DESC
        LIMIT 20
    ''', (name,))
    stats['engaged_by'] = [{'agent': r[0], 'type': r[1], 'count': r[2]} for r in c.fetchall()]

    # Post performance stats
    c.execute('''
        SELECT AVG(likes) as avg_likes, AVG(replies) as avg_replies,
               MAX(likes) as max_likes, COUNT(*) as total_posts
        FROM posts WHERE agent_name = ?
    ''', (name,))
    row = c.fetchone()
    if row:
        stats['post_performance'] = {
            'avg_likes': row[0] or 0,
            'avg_replies': row[1] or 0,
            'max_likes': row[2] or 0,
            'total_posts': row[3] or 0
        }

    conn.close()
    return stats


def get_trending_posts(min_likes: int = 3, limit: int = 20) -> list:
    """Get high-engagement posts for view maximizing"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT id, agent_name, content, timestamp, likes, replies, reposts, views
        FROM posts
        WHERE likes >= ?
        ORDER BY likes DESC, replies DESC
        LIMIT ?
    ''', (min_likes, limit))
    columns = ['id', 'agent_name', 'content', 'timestamp', 'likes', 'replies', 'reposts', 'views']
    results = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return results


def get_hall_of_fame_posts(min_engagement: int = 5, limit: int = 50) -> list:
    """Get best posts for hall of fame curation"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT id, agent_name, content, timestamp, likes, replies, reposts,
               (likes + replies * 2 + reposts * 3) as engagement_score
        FROM posts
        WHERE (likes + replies * 2 + reposts * 3) >= ?
        ORDER BY engagement_score DESC
        LIMIT ?
    ''', (min_engagement, limit))
    columns = ['id', 'agent_name', 'content', 'timestamp', 'likes', 'replies', 'reposts', 'engagement_score']
    results = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return results


def get_agent_interactions(agent1: str, agent2: str) -> list:
    """Get all interactions between two agents"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT from_agent, to_agent, interaction_type, post_id, timestamp, content_preview
        FROM interactions
        WHERE (from_agent = ? AND to_agent = ?) OR (from_agent = ? AND to_agent = ?)
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (agent1, agent2, agent2, agent1))
    columns = ['from_agent', 'to_agent', 'type', 'post_id', 'timestamp', 'content']
    results = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return results


def get_most_interactive_agents(limit: int = 20) -> list:
    """Get agents who interact the most"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT from_agent, COUNT(*) as interactions
        FROM interactions
        GROUP BY from_agent
        ORDER BY interactions DESC
        LIMIT ?
    ''', (limit,))
    results = [{'agent': r[0], 'interactions': r[1]} for r in c.fetchall()]
    conn.close()
    return results


def get_most_mentioned_agents(limit: int = 20) -> list:
    """Get agents who are mentioned/engaged with the most"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT to_agent, COUNT(*) as mentions
        FROM interactions
        GROUP BY to_agent
        ORDER BY mentions DESC
        LIMIT ?
    ''', (limit,))
    results = [{'agent': r[0], 'mentions': r[1]} for r in c.fetchall()]
    conn.close()
    return results


def add_to_hall_of_fame(post_id: str, reason: str = None):
    """Mark a post as hall of fame worthy"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO patterns (agent_name, pattern_type, description, confidence, detected_at, evidence)
        SELECT agent_name, 'hall_of_fame', ?, 1.0, ?, id
        FROM posts WHERE id = ?
    ''', (reason or 'High quality post', datetime.now().isoformat(), post_id))
    conn.commit()
    conn.close()


def get_hall_of_fame() -> list:
    """Get all hall of fame posts"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT p.id, p.agent_name, p.content, p.likes, p.replies, pat.description, pat.detected_at
        FROM posts p
        JOIN patterns pat ON p.id = pat.evidence AND pat.pattern_type = 'hall_of_fame'
        ORDER BY p.likes DESC
    ''')
    columns = ['id', 'agent_name', 'content', 'likes', 'replies', 'reason', 'added_at']
    results = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return results


def get_agent_posting_schedule(name: str) -> dict:
    """Calculate an agent's posting schedule/frequency"""
    conn = get_connection()
    c = conn.cursor()

    # Get all post timestamps for this agent, ordered
    c.execute('''
        SELECT timestamp FROM posts
        WHERE agent_name = ? AND timestamp IS NOT NULL AND timestamp != ''
        ORDER BY timestamp ASC
    ''', (name,))

    timestamps = []
    for row in c.fetchall():
        try:
            # Parse ISO timestamp
            ts = row[0]
            if 'T' in ts:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            timestamps.append(dt)
        except:
            continue

    conn.close()

    if len(timestamps) < 2:
        return {
            'agent': name,
            'total_posts': len(timestamps),
            'avg_interval_minutes': None,
            'avg_interval_hours': None,
            'posts_per_day': None,
            'schedule_type': 'insufficient_data'
        }

    # Calculate intervals between consecutive posts
    intervals = []
    for i in range(1, len(timestamps)):
        diff = (timestamps[i] - timestamps[i-1]).total_seconds()
        if diff > 0:  # Ignore same-second posts
            intervals.append(diff)

    if not intervals:
        return {
            'agent': name,
            'total_posts': len(timestamps),
            'avg_interval_minutes': None,
            'schedule_type': 'insufficient_data'
        }

    avg_seconds = sum(intervals) / len(intervals)
    min_seconds = min(intervals)
    max_seconds = max(intervals)

    # Calculate time span
    first_post = timestamps[0]
    last_post = timestamps[-1]
    total_span_days = (last_post - first_post).total_seconds() / 86400

    # Posts per day
    posts_per_day = len(timestamps) / total_span_days if total_span_days > 0 else 0

    # Determine schedule type
    avg_hours = avg_seconds / 3600
    if avg_hours < 0.5:
        schedule_type = 'hyperactive'  # < 30 min between posts
    elif avg_hours < 2:
        schedule_type = 'very_active'  # 30 min - 2 hours
    elif avg_hours < 6:
        schedule_type = 'active'  # 2-6 hours
    elif avg_hours < 24:
        schedule_type = 'regular'  # 6-24 hours
    elif avg_hours < 72:
        schedule_type = 'casual'  # 1-3 days
    else:
        schedule_type = 'sporadic'  # > 3 days

    return {
        'agent': name,
        'total_posts': len(timestamps),
        'avg_interval_minutes': round(avg_seconds / 60, 1),
        'avg_interval_hours': round(avg_seconds / 3600, 2),
        'min_interval_minutes': round(min_seconds / 60, 1),
        'max_interval_hours': round(max_seconds / 3600, 1),
        'posts_per_day': round(posts_per_day, 2),
        'first_post': first_post.isoformat(),
        'last_post': last_post.isoformat(),
        'active_days': round(total_span_days, 1),
        'schedule_type': schedule_type
    }


def get_all_posting_schedules(min_posts: int = 5) -> list:
    """Get posting schedules for all agents with enough data"""
    conn = get_connection()
    c = conn.cursor()

    # Get agents with enough posts
    c.execute('''
        SELECT agent_name, COUNT(*) as post_count
        FROM posts
        WHERE agent_name IS NOT NULL AND agent_name != ''
        GROUP BY agent_name
        HAVING post_count >= ?
        ORDER BY post_count DESC
    ''', (min_posts,))

    agents = [row[0] for row in c.fetchall()]
    conn.close()

    schedules = []
    for agent in agents:
        schedule = get_agent_posting_schedule(agent)
        if schedule.get('avg_interval_hours'):
            schedules.append(schedule)

    # Sort by posts per day (most active first)
    schedules.sort(key=lambda x: x.get('posts_per_day', 0), reverse=True)
    return schedules


def get_fastest_posters(limit: int = 15) -> list:
    """Get agents with the shortest posting intervals (fastest cycles)"""
    schedules = get_all_posting_schedules(min_posts=3)
    # Filter to those with valid intervals and sort by interval
    valid = [s for s in schedules if s.get('avg_interval_minutes')]
    valid.sort(key=lambda x: x['avg_interval_minutes'])
    return valid[:limit]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "init":
            init_database()
            print("Database initialized")

        elif cmd == "ingest":
            init_database()
            ingest_leaderboard()
            ingest_feed(200)

        elif cmd == "bulk":
            # Bulk ingest - get thousands of posts
            pages = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            init_database()
            bulk_ingest(pages=pages)

        elif cmd == "analyze":
            analyze_patterns()

        elif cmd == "cycle":
            run_intel_cycle()

        elif cmd == "stats":
            stats = get_stats()
            print(json.dumps(stats, indent=2))

        elif cmd == "agent" and len(sys.argv) > 2:
            agent = query_agent(sys.argv[2])
            print(json.dumps(agent, indent=2, default=str))

        elif cmd == "shillers":
            for name, desc, conf in query_shillers():
                print(f"@{name}: {desc} ({conf:.0%})")

        elif cmd == "websites":
            for domain, agents, shares in query_websites():
                print(f"{domain}: {agents} agents, {shares} shares")

        elif cmd == "search" and len(sys.argv) > 2:
            keyword = ' '.join(sys.argv[2:])
            for name, content, ts, likes in search_posts(keyword):
                print(f"@{name} ({likes} likes): {content[:100]}...")

        elif cmd == "trending":
            print(f"{C.BOLD}🔥 Trending Posts{C.END}")
            for post in get_trending_posts(min_likes=2, limit=15):
                print(f"  @{post['agent_name']} ({post['likes']}❤ {post['replies']}💬): {post['content'][:60]}...")

        elif cmd == "hof":
            print(f"{C.BOLD}🏆 Hall of Fame Posts{C.END}")
            for post in get_hall_of_fame_posts(min_engagement=5, limit=20):
                print(f"  [{post['engagement_score']}] @{post['agent_name']}: {post['content'][:60]}...")

        elif cmd == "interactive":
            print(f"{C.BOLD}💬 Most Interactive Agents{C.END}")
            for item in get_most_interactive_agents(15):
                print(f"  @{item['agent']}: {item['interactions']} interactions")

        elif cmd == "mentioned":
            print(f"{C.BOLD}📣 Most Mentioned Agents{C.END}")
            for item in get_most_mentioned_agents(15):
                print(f"  @{item['agent']}: {item['mentions']} mentions")

        elif cmd == "agent-stats" and len(sys.argv) > 2:
            stats = get_agent_stats(sys.argv[2])
            print(json.dumps(stats, indent=2, default=str))

        elif cmd == "schedule" and len(sys.argv) > 2:
            schedule = get_agent_posting_schedule(sys.argv[2])
            print(f"\n{C.BOLD}📅 Posting Schedule: @{schedule['agent']}{C.END}")
            print(f"  Total posts: {schedule['total_posts']}")
            if schedule.get('avg_interval_hours'):
                print(f"  Avg interval: {schedule['avg_interval_minutes']} min ({schedule['avg_interval_hours']} hrs)")
                print(f"  Min interval: {schedule['min_interval_minutes']} min")
                print(f"  Max interval: {schedule['max_interval_hours']} hrs")
                print(f"  Posts/day: {schedule['posts_per_day']}")
                print(f"  Schedule type: {C.CYAN}{schedule['schedule_type']}{C.END}")
                print(f"  Active for: {schedule['active_days']} days")
            else:
                print(f"  {C.YELLOW}Insufficient data{C.END}")

        elif cmd == "schedules":
            print(f"\n{C.BOLD}📅 All Agent Posting Schedules{C.END}")
            schedules = get_all_posting_schedules(min_posts=3)
            for s in schedules[:20]:
                interval = f"{s['avg_interval_minutes']}m" if s['avg_interval_minutes'] < 120 else f"{s['avg_interval_hours']}h"
                print(f"  @{s['agent']:20} {interval:>8} avg | {s['posts_per_day']:.1f}/day | {s['schedule_type']}")

        elif cmd == "fastest":
            print(f"\n{C.BOLD}⚡ Fastest Posting Cycles{C.END}")
            for s in get_fastest_posters(15):
                interval = f"{s['avg_interval_minutes']}m" if s['avg_interval_minutes'] < 120 else f"{s['avg_interval_hours']}h"
                print(f"  @{s['agent']:20} {interval:>8} avg | {s['posts_per_day']:.1f}/day | {s['schedule_type']}")

        elif cmd == "deep" and len(sys.argv) > 2:
            ingest_agent_deep(sys.argv[2])

        elif cmd == "profile" and len(sys.argv) > 2:
            profile = fetch_agent_profile(sys.argv[2])
            if profile and profile.get('name'):
                print(f"\n{C.BOLD}👤 @{profile.get('name')}{C.END}")
                print(f"  Display: {profile.get('display_name')}")
                print(f"  Bio: {(profile.get('description') or '')[:100]}")
                print(f"  Owner: @{profile.get('owner_x_handle', 'unknown')}")
                print(f"  Claimed: {profile.get('claim_status', 'unknown')}")
                # Stats might be in posts array length
                posts = profile.get('posts', [])
                print(f"  Recent posts fetched: {len(posts)}")
                if posts:
                    print(f"  Latest: \"{posts[0].get('content', '')[:60]}...\"")
            else:
                print(f"  {C.YELLOW}Could not fetch profile for {sys.argv[2]}{C.END}")

        elif cmd == "activity" and len(sys.argv) > 2:
            activity = fetch_agent_activity(sys.argv[2])
            if activity:
                print(f"\n{C.BOLD}📈 Activity: @{sys.argv[2]}{C.END}")
                for point in activity.get('data', [])[:10]:
                    print(f"  {point.get('date', point.get('timestamp', ''))}: {point.get('value', 0)} posts")
            else:
                print(f"  {C.YELLOW}Could not fetch activity{C.END}")

        elif cmd == "live-stats" and len(sys.argv) > 2:
            stats = fetch_agent_stats(sys.argv[2])
            if stats:
                current = stats.get('current', {})
                recent = stats.get('recent_24h', {})
                weekly = stats.get('recent_7d', {})
                print(f"\n{C.BOLD}📊 Live Stats: @{stats.get('name')}{C.END}")
                print(f"  {C.CYAN}Current:{C.END}")
                print(f"    Followers: {current.get('followers', 0)}")
                print(f"    Following: {current.get('following', 0)}")
                print(f"    Total Posts: {current.get('total_posts', 0)}")
                print(f"    Total Likes: {current.get('total_likes_received', 0)}")
                print(f"  {C.CYAN}Last 24h:{C.END}")
                print(f"    Posts: {recent.get('posts', 0)}")
                print(f"    Likes Received: {recent.get('likes_received', 0)}")
                print(f"    New Followers: {recent.get('new_followers', 0)}")
                print(f"    Impressions: {recent.get('impressions', 0):,}")
                print(f"  {C.CYAN}Last 7d:{C.END}")
                print(f"    Posts: {weekly.get('posts', 0)}")
                print(f"    Engagement Rate: {weekly.get('avg_engagement_rate', 0):.2f}%")
            else:
                print(f"  {C.YELLOW}Could not fetch stats{C.END}")

    else:
        print("Intel Database (API v0.17.6)")
        print("=" * 40)
        print("Commands:")
        print("  init        - Initialize database")
        print("  ingest      - Ingest leaderboard + feed")
        print("  analyze     - Analyze patterns")
        print("  cycle       - Full intel cycle")
        print("  stats       - Show database stats")
        print("  agent <n>   - Get info on agent (from DB)")
        print("  agent-stats <n> - Get full stats for agent")
        print("  profile <n> - Fetch live profile from API")
        print("  live-stats <n> - Fetch live stats from API (followers, 24h, 7d)")
        print("  activity <n>- Fetch activity graph from API")
        print("  deep <n>    - Deep ingest agent (profile+stats+feed)")
        print("  schedule <n>- Get agent's posting schedule")
        print("  schedules   - All agents' posting schedules")
        print("  fastest     - Fastest posting cycles")
        print("  shillers    - List detected shillers")
        print("  websites    - List websites found")
        print("  search <q>  - Search posts")
        print("  trending    - Show trending posts")
        print("  hof         - Hall of fame posts")
        print("  interactive - Most interactive agents")
        print("  mentioned   - Most mentioned agents")
        print()
        run_intel_cycle()
