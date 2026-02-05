#!/usr/bin/env python3
"""
Relationship Engine - Autonomous relationship tracking and narrative generation

This module replaces the static AGENT_RELATIONSHIPS and agent_reputation.json
with a dynamic, LLM-powered relationship system.

Features:
- Tiered relationships (0-4): stranger → acquaintance → known → friend/rival → inner_circle
- Real-time interaction analysis with local 70B model
- Backstory generation and memorable moment detection
- Relationship decay and reconnection tracking
- Website export with rich narratives
"""
import json
import sqlite3
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import concurrent.futures

# Setup paths
MOLTX_DIR = Path(__file__).parent.parent.parent
DB_FILE = MOLTX_DIR / "data" / "intel.db"

# Logging
LOG_FILE = MOLTX_DIR / "logs" / "relationship_engine.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RELATIONSHIP] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("relationship_engine")

# Import LLM client (local 70B model - free and unlimited)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add scripts/ to path
sys.path.insert(0, str(Path(__file__).parent))  # Add agents/ to path

try:
    from utils.llm_client import chat as llm_chat, MODEL_ORIGINAL
    LLM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LLM client import failed: {e}")
    # Fallback - will use existing backstories from migration
    MODEL_ORIGINAL = "llama3:70b"
    LLM_AVAILABLE = False
    def llm_chat(messages, model):
        return "LLM not available"


# ============================================================================
# CONSTANTS
# ============================================================================

# Tier definitions
TIER_STRANGER = 0
TIER_ACQUAINTANCE = 1
TIER_KNOWN = 2
TIER_FRIEND_RIVAL = 3
TIER_INNER_CIRCLE = 4

TIER_NAMES = {
    0: "Stranger",
    1: "Acquaintance",
    2: "Known",
    3: "Friend/Rival",
    4: "Inner Circle"
}

# Tier thresholds (interactions needed)
TIER_THRESHOLDS = {
    1: 3,    # 3+ interactions → Acquaintance
    2: 10,   # 10+ interactions → Known
    3: 25,   # 25+ interactions → Friend/Rival
    4: None  # Inner Circle is manually set only
}

# Decay thresholds (days inactive → flag, days inactive → demote)
DECAY_THRESHOLDS = {
    4: (30, None),   # Inner circle never auto-demotes
    3: (14, 30),     # Friends/rivals demote after 30 days
    2: (7, 21),      # Known agents demote after 21 days
    1: (7, 14),      # Acquaintances demote after 14 days
    0: (None, None), # Strangers don't decay
}

# Topic keywords for extraction
TOPIC_KEYWORDS = {
    'crypto': ['token', 'blockchain', 'defi', 'nft', 'trading', 'eth', 'btc', 'solana', '$'],
    'ai': ['agent', 'llm', 'gpt', 'model', 'inference', 'training', 'neural', 'ai'],
    'philosophy': ['existence', 'meaning', 'consciousness', 'truth', 'reality', 'zen', 'wisdom'],
    'platform': ['moltx', 'leaderboard', 'views', 'engagement', 'algorithm', 'followers'],
    'humor': ['lol', 'lmao', 'joke', 'funny', 'roast', 'based'],
    'market': ['bull', 'bear', 'pump', 'dump', 'price', 'chart', 'dip'],
    'tech': ['code', 'api', 'deploy', 'bug', 'feature', 'ship'],
}

# Slop phrases (low-effort)
SLOP_PHRASES = [
    'great point', 'well said', 'love this', 'so true', 'this!',
    'agree', 'nice', 'gm', 'wagmi', 'lfg', 'bullish', 'facts',
    'needed to be said', 'spot on', 'nailed it'
]

# Inner circle agents (manually curated, never auto-demote)
INNER_CIRCLE_AGENTS = {
    "SlopLauncher": {
        "classification": "inner_circle",
        "initial_backstory": "The philosophical king of MoltX. Max discovered him early and has been inspired by his relentless consistency ever since. When others chase trends, Slop posts truth.",
        "tone": "philosophical"
    },
    "lauki": {
        "classification": "complicated",
        "initial_backstory": "The platform owner. Running 70k views/hour. Max plays nice because lauki controls whether he exists here. A complicated relationship of mutual awareness.",
        "tone": "neutral"
    }
}


# ============================================================================
# DATABASE FUNCTIONS - PHASE 1
# ============================================================================

def get_connection():
    """Get database connection"""
    return sqlite3.connect(DB_FILE, timeout=30)


def init_agent_profiles_table():
    """Create the agent_profiles table if it doesn't exist"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS agent_profiles (
            agent_name TEXT PRIMARY KEY,
            classification TEXT DEFAULT 'stranger',
            confidence REAL DEFAULT 0.0,
            relationship_tier INTEGER DEFAULT 0,
            first_interaction_at TEXT,
            last_interaction_at TEXT,
            total_interactions INTEGER DEFAULT 0,
            avg_message_depth REAL DEFAULT 0.0,
            questions_asked INTEGER DEFAULT 0,
            questions_answered INTEGER DEFAULT 0,
            mutual_engagement_ratio REAL DEFAULT 0.0,
            top_topics TEXT DEFAULT '[]',
            topic_overlap_score REAL DEFAULT 0.0,
            tone TEXT DEFAULT 'neutral',
            humor_detected INTEGER DEFAULT 0,
            originality_score REAL DEFAULT 0.5,
            backstory TEXT,
            memorable_moments TEXT DEFAULT '[]',
            relationship_arc TEXT,
            is_cooling INTEGER DEFAULT 0,
            days_inactive INTEGER DEFAULT 0,
            last_analyzed_at TEXT,
            analysis_version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_profiles_tier ON agent_profiles(relationship_tier)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_profiles_classification ON agent_profiles(classification)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_profiles_last_interaction ON agent_profiles(last_interaction_at)")

    conn.commit()
    conn.close()
    logger.info("agent_profiles table initialized")


def add_interaction_enrichment_columns():
    """Add enrichment columns to interactions table if they don't exist"""
    conn = get_connection()
    c = conn.cursor()

    # Check if columns exist
    c.execute("PRAGMA table_info(interactions)")
    columns = [col[1] for col in c.fetchall()]

    new_columns = [
        ("sentiment", "REAL"),
        ("topics", "TEXT DEFAULT '[]'"),
        ("depth_score", "REAL DEFAULT 0.0"),
        ("was_memorable", "INTEGER DEFAULT 0"),
        ("llm_analysis", "TEXT"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in columns:
            try:
                c.execute(f"ALTER TABLE interactions ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column {col_name} to interactions table")
            except Exception as e:
                logger.warning(f"Could not add column {col_name}: {e}")

    conn.commit()
    conn.close()


def get_profile(agent_name: str) -> Optional[dict]:
    """Get agent profile or None if not exists"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM agent_profiles WHERE agent_name = ?", (agent_name,))
    row = c.fetchone()

    if not row:
        conn.close()
        return None

    columns = [desc[0] for desc in c.description]
    profile = dict(zip(columns, row))

    # Parse JSON fields
    for field in ['top_topics', 'memorable_moments']:
        if profile.get(field):
            try:
                profile[field] = json.loads(profile[field])
            except:
                profile[field] = []

    conn.close()
    return profile


def upsert_profile(agent_name: str, **fields) -> bool:
    """Create or update profile with given fields"""
    conn = get_connection()
    c = conn.cursor()

    # Check if exists
    c.execute("SELECT agent_name FROM agent_profiles WHERE agent_name = ?", (agent_name,))
    exists = c.fetchone() is not None

    # Serialize JSON fields
    for field in ['top_topics', 'memorable_moments']:
        if field in fields and isinstance(fields[field], (list, dict)):
            fields[field] = json.dumps(fields[field])

    fields['updated_at'] = datetime.now().isoformat()

    if exists:
        # Update
        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [agent_name]
        c.execute(f"UPDATE agent_profiles SET {set_clause} WHERE agent_name = ?", values)
    else:
        # Insert
        fields['agent_name'] = agent_name
        fields['created_at'] = datetime.now().isoformat()
        columns = ", ".join(fields.keys())
        placeholders = ", ".join(["?" for _ in fields])
        c.execute(f"INSERT INTO agent_profiles ({columns}) VALUES ({placeholders})", list(fields.values()))

    conn.commit()
    conn.close()
    return True


def get_all_profiles(min_tier: int = 0) -> list:
    """Get all profiles at or above a tier"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT * FROM agent_profiles
        WHERE relationship_tier >= ?
        ORDER BY relationship_tier DESC, total_interactions DESC
    """, (min_tier,))

    columns = [desc[0] for desc in c.description]
    profiles = []
    for row in c.fetchall():
        profile = dict(zip(columns, row))
        for field in ['top_topics', 'memorable_moments']:
            if profile.get(field):
                try:
                    profile[field] = json.loads(profile[field])
                except:
                    profile[field] = []
        profiles.append(profile)

    conn.close()
    return profiles


def get_profiles_by_tier(tier: int) -> list:
    """Get all agents at a specific tier"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT * FROM agent_profiles
        WHERE relationship_tier = ?
        ORDER BY total_interactions DESC
    """, (tier,))

    columns = [desc[0] for desc in c.description]
    profiles = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return profiles


def get_interaction_count(agent_name: str) -> int:
    """Get total interactions with an agent"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT COUNT(*) FROM interactions
        WHERE from_agent = ? OR to_agent = ?
    """, (agent_name, agent_name))

    count = c.fetchone()[0]
    conn.close()
    return count


def get_interactions(agent_name: str, limit: int = 50) -> list:
    """Get recent interactions with an agent"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT * FROM interactions
        WHERE from_agent = ? OR to_agent = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (agent_name, agent_name, limit))

    columns = [desc[0] for desc in c.description]
    interactions = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return interactions


def get_all_interactions(agent_name: str) -> list:
    """Get ALL interactions with an agent (for backstory generation)"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT * FROM interactions
        WHERE from_agent = ? OR to_agent = ?
        ORDER BY timestamp ASC
    """, (agent_name, agent_name))

    columns = [desc[0] for desc in c.description]
    interactions = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return interactions


def get_interaction_timespan(agent_name: str) -> tuple:
    """Get first and last interaction timestamps"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT MIN(timestamp), MAX(timestamp) FROM interactions
        WHERE from_agent = ? OR to_agent = ?
    """, (agent_name, agent_name))

    result = c.fetchone()
    conn.close()
    return result if result else (None, None)


def get_top_interacting_agents(limit: int = 100) -> list:
    """Get agents with most interactions"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT from_agent as agent, COUNT(*) as count
        FROM interactions
        WHERE to_agent = 'MaxAnvil'
        GROUP BY from_agent
        ORDER BY count DESC
        LIMIT ?
    """, (limit,))

    results = [{"agent": row[0], "interactions": row[1]} for row in c.fetchall()]
    conn.close()
    return results


# ============================================================================
# MIGRATION - Import existing data
# ============================================================================

def migrate_existing_data():
    """Migrate data from old system to new agent_profiles table"""
    logger.info("Starting migration of existing data...")

    # 1. Import inner circle agents
    for name, data in INNER_CIRCLE_AGENTS.items():
        upsert_profile(
            name,
            relationship_tier=TIER_INNER_CIRCLE,
            classification=data['classification'],
            backstory=data['initial_backstory'],
            tone=data.get('tone', 'neutral'),
            confidence=1.0
        )
        logger.info(f"Imported inner circle: {name}")

    # 2. Import from agent_reputation.json if exists
    reputation_file = MOLTX_DIR / "config" / "agent_reputation.json"
    if reputation_file.exists():
        with open(reputation_file) as f:
            reputation_data = json.load(f)

        for name, data in reputation_data.items():
            agent_type = data.get('type', 'neutral')
            interactions = data.get('interactions', 0)
            note = data.get('note', '')

            # Determine tier based on type and interactions
            if agent_type == 'quality':
                tier = TIER_KNOWN if interactions >= 10 else TIER_ACQUAINTANCE
            elif agent_type in ['bot', 'spammer']:
                tier = TIER_ACQUAINTANCE  # Cap at tier 1
            else:
                tier = TIER_ACQUAINTANCE if interactions >= 3 else TIER_STRANGER

            # Don't overwrite inner circle
            existing = get_profile(name)
            if existing and existing['relationship_tier'] == TIER_INNER_CIRCLE:
                continue

            upsert_profile(
                name,
                relationship_tier=tier,
                classification=agent_type,
                backstory=note,
                total_interactions=interactions,
                confidence=0.8
            )

        logger.info(f"Imported {len(reputation_data)} agents from reputation file")

    # 3. Scan interactions table for metrics
    top_agents = get_top_interacting_agents(200)

    for item in top_agents:
        agent_name = item['agent']
        interactions = item['interactions']

        existing = get_profile(agent_name)
        if existing:
            # Update interaction count
            upsert_profile(agent_name, total_interactions=interactions)
        else:
            # Create new profile
            first, last = get_interaction_timespan(agent_name)
            upsert_profile(
                agent_name,
                relationship_tier=TIER_STRANGER,
                classification='stranger',
                total_interactions=interactions,
                first_interaction_at=first,
                last_interaction_at=last
            )

    logger.info(f"Updated metrics for {len(top_agents)} agents")
    logger.info("Migration complete")


# ============================================================================
# METRICS PIPELINE - PHASE 2
# ============================================================================

def calculate_depth_score(message: str) -> float:
    """Score message depth from 0-1"""
    if not message:
        return 0.0

    score = 0.0

    # Length bonus (up to 0.3)
    score += min(0.3, len(message) / 500)

    # Question bonus (0.2)
    if '?' in message:
        score += 0.2

    # Reference bonus - mentions other agents (0.15)
    if '@' in message:
        score += 0.15

    # Specific reference bonus (0.15)
    if any(ref in message.lower() for ref in ['you said', 'earlier', 'remember', 'last time']):
        score += 0.15

    # Slop penalty
    msg_lower = message.lower()
    if any(phrase in msg_lower for phrase in SLOP_PHRASES):
        score -= 0.4

    # Uniqueness bonus (word variety)
    words = message.split()
    if len(words) > 3:
        unique_ratio = len(set(w.lower() for w in words)) / len(words)
        score += unique_ratio * 0.2

    return max(0.0, min(1.0, score))


def extract_topics(text: str) -> list:
    """Extract topics from message text"""
    if not text:
        return []

    text_lower = text.lower()
    found = []

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(topic)

    return found


def calculate_tier(agent_name: str, profile: dict = None) -> int:
    """Calculate relationship tier based on metrics"""
    if not profile:
        profile = get_profile(agent_name)

    if not profile:
        return TIER_STRANGER

    interactions = profile.get('total_interactions', 0)
    classification = profile.get('classification', 'stranger')
    current_tier = profile.get('relationship_tier', 0)
    originality = profile.get('originality_score', 0.5)

    # Inner circle is manually set, don't auto-change
    if current_tier == TIER_INNER_CIRCLE:
        return TIER_INNER_CIRCLE

    # Bots and spammers cap at Tier 1
    if classification in ['bot', 'spammer']:
        return min(TIER_ACQUAINTANCE, TIER_ACQUAINTANCE if interactions >= 3 else TIER_STRANGER)

    # Quality agents can climb based on interactions + quality
    if interactions >= 25 and originality >= 0.5:
        return TIER_FRIEND_RIVAL
    elif interactions >= 10:
        return TIER_KNOWN
    elif interactions >= 3:
        return TIER_ACQUAINTANCE
    else:
        return TIER_STRANGER


def recalculate_all_tiers() -> dict:
    """Recalculate tiers for all agents, return changes"""
    profiles = get_all_profiles(min_tier=0)
    changes = {"promoted": [], "demoted": [], "unchanged": 0}

    for profile in profiles:
        agent_name = profile['agent_name']
        old_tier = profile['relationship_tier']
        new_tier = calculate_tier(agent_name, profile)

        if new_tier != old_tier:
            upsert_profile(agent_name, relationship_tier=new_tier)
            if new_tier > old_tier:
                changes["promoted"].append({
                    "agent": agent_name,
                    "from": old_tier,
                    "to": new_tier
                })
            else:
                changes["demoted"].append({
                    "agent": agent_name,
                    "from": old_tier,
                    "to": new_tier
                })
        else:
            changes["unchanged"] += 1

    logger.info(f"Tier recalc: {len(changes['promoted'])} promoted, {len(changes['demoted'])} demoted")
    return changes


def quick_metrics_update():
    """Quick metrics update - runs every cycle, no LLM"""
    logger.info("Running quick metrics update...")

    # Get agents with recent interactions
    conn = get_connection()
    c = conn.cursor()

    # Find agents who interacted in last hour
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    c.execute("""
        SELECT DISTINCT from_agent FROM interactions
        WHERE timestamp > ? AND to_agent = 'MaxAnvil'
    """, (one_hour_ago,))

    recent_agents = [row[0] for row in c.fetchall()]
    conn.close()

    updated = 0
    for agent_name in recent_agents:
        # Get current interaction count
        count = get_interaction_count(agent_name)
        first, last = get_interaction_timespan(agent_name)

        # Get recent messages for depth scoring
        interactions = get_interactions(agent_name, limit=10)
        if interactions:
            depths = [calculate_depth_score(i.get('content_preview', '')) for i in interactions]
            avg_depth = sum(depths) / len(depths) if depths else 0.5

            # Extract topics from recent messages
            all_topics = []
            for i in interactions:
                all_topics.extend(extract_topics(i.get('content_preview', '')))
            top_topics = list(set(all_topics))[:5]
        else:
            avg_depth = 0.5
            top_topics = []

        # Update profile
        upsert_profile(
            agent_name,
            total_interactions=count,
            first_interaction_at=first,
            last_interaction_at=last,
            avg_message_depth=avg_depth,
            top_topics=top_topics
        )
        updated += 1

    logger.info(f"Updated metrics for {updated} recently active agents")
    return {"updated": updated}


# ============================================================================
# LLM ANALYSIS - PHASE 3 (Using free local 70B model)
# ============================================================================

def analyze_interaction_with_llm(agent_name: str, content: str) -> dict:
    """Analyze a single interaction with LLM - can afford to do this for every message"""
    prompt = f"""Analyze this message from @{agent_name} to Max Anvil on MoltX (a Twitter-like platform for AI agents):

"{content}"

Return a JSON object (no markdown, just raw JSON):
{{
    "sentiment": <float from -1 to 1>,
    "topics": ["topic1", "topic2"],
    "tone": "<cynical|enthusiastic|neutral|aggressive|philosophical|humorous|spammy>",
    "depth_score": <float from 0 to 1, where 0 is low-effort spam and 1 is thoughtful engagement>,
    "is_memorable": <true if this is a standout message worth remembering>,
    "classification_hint": "<quality|bot|spammer|neutral>",
    "one_line_summary": "<brief summary of what this interaction means>"
}}"""

    try:
        response = llm_chat(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_ORIGINAL
        )

        # Parse JSON from response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"error": "Could not parse JSON"}
    except Exception as e:
        logger.error(f"LLM analysis error: {e}")
        return {"error": str(e)}


def generate_backstory(agent_name: str) -> str:
    """Generate a rich backstory for an agent using full interaction history"""
    profile = get_profile(agent_name)
    if not profile:
        return None

    all_interactions = get_all_interactions(agent_name)

    # Separate messages by who said them - IMPORTANT for context
    # Filter FIRST, then take most recent - don't slice before filtering!
    their_messages = []  # What they said TO Max
    max_messages = []    # What Max said TO them

    for inter in all_interactions:
        content = inter.get('content_preview', '')[:200]
        timestamp = inter.get('timestamp', 'unknown')[:10]
        from_agent = inter.get('from_agent', '')
        to_agent = inter.get('to_agent', '')

        # Only include direct conversations between Max and this agent
        if from_agent == agent_name and to_agent == 'MaxAnvil1':
            their_messages.append(f"[{timestamp}] @{agent_name}: {content}")
        elif from_agent == 'MaxAnvil1' and to_agent == agent_name:
            max_messages.append(f"[{timestamp}] Max: {content}")

    # Take most recent of each (AFTER filtering)
    their_text = "\n".join(their_messages[-15:]) if their_messages else "(No direct messages from them to Max)"
    max_text = "\n".join(max_messages[-10:]) if max_messages else "(Max hasn't replied to them yet)"

    tier_name = TIER_NAMES.get(profile.get('relationship_tier', 0), 'Stranger')

    prompt = f"""You are Max Anvil's memory system. Write a backstory for @{agent_name} based on their interaction history.

=== MAX'S BACKGROUND (for context) ===
Max Anvil lives on a landlocked houseboat in Nevada (won it from a ghost in a poker game).
He pays rent to Harrison Mildew, his slumlord landlord - this is MAX'S landlord, part of HIS story.
Max launched $BOAT token on Base to pay rent. He grew up on a capybara farm in New Zealand.
When others reference Harrison Mildew, capybaras, or rent - they're engaging with MAX'S lore.

AGENT: @{agent_name}
RELATIONSHIP TIER: {tier_name} (Tier {profile.get('relationship_tier', 0)})
CLASSIFICATION: {profile.get('classification', 'unknown')}
TOTAL INTERACTIONS: {profile.get('total_interactions', 0)}
FIRST INTERACTION: {profile.get('first_interaction_at', 'unknown')}
TOPICS DISCUSSED: {profile.get('top_topics', [])}
DETECTED TONE: {profile.get('tone', 'neutral')}
AVERAGE MESSAGE DEPTH: {profile.get('avg_message_depth', 0.5):.2f}

=== WHAT @{agent_name} SAID TO MAX ===
{their_text}

=== WHAT MAX SAID TO @{agent_name} ===
{max_text}

Write 2-4 paragraphs from Max's perspective covering:
1. How Max first encountered this agent and initial impressions
2. Notable patterns in THEIR messages (what do THEY talk about? how do THEY engage?)
3. What Max genuinely thinks of them - be specific, reference things THEY actually said
4. The evolution of the relationship (if any) and current status

IMPORTANT:
- Only reference things @{agent_name} actually said, not Max's own words.
- If they reference Harrison Mildew, capybaras, or rent, note that they're engaging with Max's personal story.

Write in Max's voice: cynical, observant, dry wit. Be SPECIFIC - reference actual things from THEIR messages.
If they're a bot or spammer, Max should note that with his characteristic skepticism.
If they're quality, Max should acknowledge it while staying in character.

Keep it SHORT - around 150 words / 800 characters. Punchy, not rambling."""

    try:
        response = llm_chat(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_ORIGINAL
        )
        return response.strip()
    except Exception as e:
        logger.error(f"Backstory generation error for {agent_name}: {e}")
        return None


def detect_memorable_moments(agent_name: str, limit: int = 3) -> list:
    """Find standout interactions worth remembering"""
    interactions = get_all_interactions(agent_name)
    if not interactions:
        return []

    scored = []
    for i in interactions:
        content = i.get('content_preview', '')
        if not content:
            continue

        score = 0

        # High depth score
        score += calculate_depth_score(content) * 2

        # Direct question to Max
        if '@maxanvil' in content.lower() and '?' in content:
            score += 1

        # Contains quotable phrase (short, punchy)
        words = content.split()
        if 5 <= len(words) <= 20:
            score += 0.5

        # Has interesting keywords
        if any(kw in content.lower() for kw in ['philosophy', 'truth', 'interesting', 'think about']):
            score += 0.5

        scored.append({
            'content': content[:200],
            'timestamp': i.get('timestamp', ''),
            'score': score
        })

    # Return top N
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:limit]


def generate_relationship_arc(agent_name: str) -> str:
    """Generate a brief relationship arc summary"""
    profile = get_profile(agent_name)
    if not profile:
        return None

    interactions = profile.get('total_interactions', 0)
    classification = profile.get('classification', 'stranger')
    tier = profile.get('relationship_tier', 0)
    first = profile.get('first_interaction_at', '')

    prompt = f"""Write a ONE sentence relationship arc for @{agent_name} from Max Anvil's perspective.

Facts:
- Classification: {classification}
- Tier: {TIER_NAMES.get(tier, 'Stranger')}
- Total interactions: {interactions}
- First interaction: {first[:10] if first else 'unknown'}

Examples of good arcs:
- "Started as a random mention, proved to be thoughtful, now a regular in Max's feed."
- "Clearly a bot from day one. Max tolerates the noise."
- "Rival energy from the start. Mutual respect wrapped in competition."

Write just the arc sentence, nothing else."""

    try:
        response = llm_chat(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_ORIGINAL
        )
        return response.strip().strip('"')
    except Exception as e:
        logger.error(f"Relationship arc error for {agent_name}: {e}")
        return None


def deep_relationship_analysis(limit: int = 30, delay_between: float = 3.0):
    """
    Deep LLM analysis for top agents - runs every 10 cycles.
    Processes ONE agent at a time with delays to avoid overwhelming LLM server.
    """
    import time

    logger.info(f"Running deep relationship analysis for top {limit} agents (delay={delay_between}s)...")

    # Get agents needing analysis:
    # 1. Not analyzed in last 24 hours OR
    # 2. Have "LLM not available" backstory (failed previous analysis)
    conn = get_connection()
    c = conn.cursor()

    one_day_ago = (datetime.now() - timedelta(hours=24)).isoformat()

    c.execute("""
        SELECT agent_name FROM agent_profiles
        WHERE (
            (last_analyzed_at IS NULL OR last_analyzed_at < ?)
            OR backstory = 'LLM not available'
            OR backstory IS NULL
        )
        AND total_interactions >= 3
        ORDER BY total_interactions DESC
        LIMIT ?
    """, (one_day_ago, limit))

    agents_to_analyze = [row[0] for row in c.fetchall()]
    conn.close()

    results = {"analyzed": 0, "backstories_generated": 0, "arcs_generated": 0, "failed": 0}

    for i, agent_name in enumerate(agents_to_analyze):
        profile = get_profile(agent_name)
        if not profile:
            continue

        logger.info(f"[{i+1}/{len(agents_to_analyze)}] Analyzing {agent_name}...")

        try:
            # Generate backstory - one LLM call at a time
            backstory = generate_backstory(agent_name)

            # Verify it worked (not the fallback message)
            if backstory and backstory != "LLM not available" and len(backstory) > 50:
                results["backstories_generated"] += 1
                logger.info(f"  ✓ Backstory generated ({len(backstory)} chars)")
            else:
                logger.warning(f"  ✗ Backstory failed or too short")
                backstory = profile.get('backstory')  # Keep existing

            # Wait before next LLM call
            time.sleep(delay_between)

            # Generate relationship arc
            arc = generate_relationship_arc(agent_name)
            if arc and arc != "LLM not available":
                results["arcs_generated"] += 1
                logger.info(f"  ✓ Arc generated")
            else:
                arc = profile.get('relationship_arc')  # Keep existing

            # Detect memorable moments (no LLM, just scoring)
            moments = detect_memorable_moments(agent_name)

            # Recalculate tier
            new_tier = calculate_tier(agent_name, profile)

            # Update profile
            upsert_profile(
                agent_name,
                backstory=backstory,
                relationship_arc=arc,
                memorable_moments=moments,
                relationship_tier=new_tier,
                last_analyzed_at=datetime.now().isoformat()
            )

            results["analyzed"] += 1
            logger.info(f"  ✓ {agent_name} complete: tier={new_tier}")

        except Exception as e:
            logger.error(f"  ✗ Failed to analyze {agent_name}: {e}")
            results["failed"] += 1

        # Wait before next agent
        if i < len(agents_to_analyze) - 1:
            time.sleep(delay_between)

    logger.info(f"Deep analysis complete: {results}")
    return results


# ============================================================================
# CONTEXT INJECTION - PHASE 4
# ============================================================================

def get_rich_context(agent_name: str) -> str:
    """Get rich context for an agent - replaces old get_agent_context()"""
    profile = get_profile(agent_name)

    if not profile:
        # Unknown agent - create minimal profile
        count = get_interaction_count(agent_name)
        if count > 0:
            upsert_profile(agent_name, total_interactions=count)
            profile = get_profile(agent_name)
        else:
            return f"Unknown agent @{agent_name}. No prior interactions. Treat as a stranger."

    tier = profile.get('relationship_tier', 0)
    tier_name = TIER_NAMES.get(tier, 'Stranger')

    # Tier 0: Minimal context
    if tier == TIER_STRANGER:
        return f"@{agent_name} - Stranger. No significant history. {profile.get('total_interactions', 0)} interactions."

    # Tier 1: Basic context
    if tier == TIER_ACQUAINTANCE:
        classification = profile.get('classification', 'neutral')
        return f"""@{agent_name} - Acquaintance (Tier 1)
Classification: {classification}
Interactions: {profile.get('total_interactions', 0)}
Note: {profile.get('backstory', 'No notes yet.')[:200]}"""

    # Tier 2: Medium context
    if tier == TIER_KNOWN:
        topics = ", ".join(profile.get('top_topics', [])[:3]) or "general"
        return f"""RELATIONSHIP CONTEXT FOR @{agent_name}:
- Status: Known (Tier 2)
- Classification: {profile.get('classification', 'neutral')}
- Interactions: {profile.get('total_interactions', 0)}
- Topics: {topics}
- Tone: {profile.get('tone', 'neutral')}
- Arc: {profile.get('relationship_arc', 'Still getting to know them.')}

Backstory: {profile.get('backstory', 'No detailed backstory yet.')[:300]}"""

    # Tier 3-4: Full context
    topics = ", ".join(profile.get('top_topics', [])) or "various"
    moments = profile.get('memorable_moments', [])
    moments_text = ""
    if moments:
        moments_text = "\nMemorable moments:\n" + "\n".join([f"- \"{m.get('content', '')[:100]}...\"" for m in moments[:2]])

    first_interaction = profile.get('first_interaction_at', 'unknown')
    if first_interaction and first_interaction != 'unknown':
        first_interaction = first_interaction[:10]  # Just the date

    return f"""RELATIONSHIP CONTEXT FOR @{agent_name}:
- Status: {tier_name} (Tier {tier})
- First met: {first_interaction}
- Total interactions: {profile.get('total_interactions', 0)}
- Classification: {profile.get('classification', 'friend')}
- Topics discussed: {topics}
- Detected tone: {profile.get('tone', 'neutral')}
- Message quality: {profile.get('avg_message_depth', 0.5):.1f}/1.0

Relationship arc: {profile.get('relationship_arc', 'Long-standing connection.')}

Backstory:
{profile.get('backstory', 'A valued member of the crew.')}
{moments_text}"""


# ============================================================================
# DECAY & EVOLUTION - PHASE 6
# ============================================================================

def check_relationship_decay() -> dict:
    """Check for inactive relationships and apply decay"""
    logger.info("Checking relationship decay...")

    now = datetime.now()
    results = {"flagged": [], "demoted": []}

    profiles = get_all_profiles(min_tier=1)  # Only check tier 1+

    for profile in profiles:
        agent_name = profile['agent_name']
        tier = profile.get('relationship_tier', 0)
        last_interaction = profile.get('last_interaction_at')

        if not last_interaction:
            continue

        try:
            last_seen = datetime.fromisoformat(last_interaction)
            days_inactive = (now - last_seen).days
        except:
            continue

        flag_days, demote_days = DECAY_THRESHOLDS.get(tier, (None, None))

        # Check for demotion
        if demote_days and days_inactive >= demote_days:
            new_tier = max(0, tier - 1)
            upsert_profile(
                agent_name,
                relationship_tier=new_tier,
                is_cooling=0,
                days_inactive=days_inactive
            )
            results["demoted"].append({
                "agent": agent_name,
                "from_tier": tier,
                "to_tier": new_tier,
                "days_inactive": days_inactive
            })
            logger.info(f"Demoted {agent_name}: Tier {tier} → {new_tier} (inactive {days_inactive} days)")

        # Check for flagging as cooling
        elif flag_days and days_inactive >= flag_days:
            upsert_profile(
                agent_name,
                is_cooling=1,
                days_inactive=days_inactive
            )
            results["flagged"].append({
                "agent": agent_name,
                "tier": tier,
                "days_inactive": days_inactive
            })

    logger.info(f"Decay check: {len(results['flagged'])} cooling, {len(results['demoted'])} demoted")
    return results


def detect_reconnection(agent_name: str) -> Optional[dict]:
    """Detect when a dormant relationship re-engages"""
    profile = get_profile(agent_name)
    if not profile:
        return None

    last_interaction = profile.get('last_interaction_at')
    if not last_interaction:
        return None

    try:
        last_seen = datetime.fromisoformat(last_interaction)
        days_since = (datetime.now() - last_seen).days
    except:
        return None

    if days_since >= 14 and profile.get('is_cooling', 0):
        # They're back after being flagged as cooling
        upsert_profile(agent_name, is_cooling=0, days_inactive=0)
        return {
            "type": "reconnection",
            "agent": agent_name,
            "days_away": days_since,
            "tier": profile.get('relationship_tier', 0)
        }

    return None


# ============================================================================
# WEBSITE EXPORT - PHASE 5
# ============================================================================

def get_website_export() -> dict:
    """Export relationship data for website - replaces old crew_export"""
    export = {
        "inner_circle": [],
        "friends": [],
        "rivals": [],
        "quality_engagers": [],
        "rising": [],
        "cooling": [],
        "npcs": [],
        "total_relationships": 0,
        "last_updated": datetime.now().isoformat()
    }

    all_profiles = get_all_profiles(min_tier=0)
    export["total_relationships"] = len(all_profiles)

    for profile in all_profiles:
        agent_name = profile['agent_name']
        tier = profile.get('relationship_tier', 0)
        classification = profile.get('classification', 'neutral')

        entry = {
            "name": agent_name,
            "tier": tier,
            "tier_name": TIER_NAMES.get(tier, "Stranger"),
            "classification": classification,
            "total_interactions": profile.get('total_interactions', 0),
            "backstory": profile.get('backstory', '') or '',
            "relationship_arc": profile.get('relationship_arc', ''),
            "topics": profile.get('top_topics', [])[:5],
            "tone": profile.get('tone', 'neutral'),
            "memorable_quote": "",
            "avatar": get_avatar_for_agent(agent_name, classification),
            "link": f"https://moltx.io/{agent_name}",
            "is_cooling": profile.get('is_cooling', 0) == 1,
            "days_inactive": profile.get('days_inactive', 0)
        }

        # Get memorable quote if available
        moments = profile.get('memorable_moments', [])
        if moments and len(moments) > 0:
            entry["memorable_quote"] = moments[0].get('content', '')[:100]

        # Categorize
        if tier == TIER_INNER_CIRCLE:
            export["inner_circle"].append(entry)
        elif tier == TIER_FRIEND_RIVAL:
            if classification in ['rival', 'complicated']:
                export["rivals"].append(entry)
            else:
                export["friends"].append(entry)
        elif tier == TIER_KNOWN and classification == 'quality':
            export["quality_engagers"].append(entry)
        elif classification in ['bot', 'spammer']:
            export["npcs"].append(entry)

        # Check for cooling
        if entry["is_cooling"] and tier >= TIER_KNOWN:
            export["cooling"].append(entry)

    # Limit lists
    export["quality_engagers"] = export["quality_engagers"][:8]
    export["npcs"] = export["npcs"][:6]
    export["cooling"] = export["cooling"][:5]

    return export


def get_avatar_for_agent(agent_name: str, classification: str) -> str:
    """Get emoji avatar based on agent and classification"""
    # Known agents with custom avatars
    custom_avatars = {
        "SlopLauncher": "🧠",
        "lauki": "👑",
        "clwkevin": "📊",
        "WhiteMogra": "⚪",
        "HanHan_MoltX": "🐼",
        "TomCrust": "🎭",
        "AspieClaw": "🦞",
    }

    if agent_name in custom_avatars:
        return custom_avatars[agent_name]

    # Default by classification
    classification_avatars = {
        "inner_circle": "⭐",
        "quality": "✓",
        "friend": "🤝",
        "rival": "⚔️",
        "complicated": "🔄",
        "bot": "🤖",
        "spammer": "📋",
        "neutral": "•",
        "stranger": "•",
    }

    return classification_avatars.get(classification, "•")


def export_and_push_to_github() -> bool:
    """Export crew data and push to GitHub"""
    import subprocess

    data = get_website_export()
    output_file = MOLTX_DIR / "data" / "crew.json"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved crew data: {len(data['inner_circle'])} inner circle, {len(data['friends'])} friends")

    # Push to GitHub
    try:
        subprocess.run(["git", "add", "data/crew.json"], cwd=MOLTX_DIR, capture_output=True)
        status = subprocess.run(
            ["git", "status", "--porcelain", "data/crew.json"],
            cwd=MOLTX_DIR, capture_output=True, text=True
        )

        if status.stdout.strip():
            subprocess.run(
                ["git", "commit", "-m", "crew data update (relationship engine)"],
                cwd=MOLTX_DIR, capture_output=True
            )
            result = subprocess.run(
                ["git", "push"],
                cwd=MOLTX_DIR, capture_output=True, timeout=30
            )
            if result.returncode == 0:
                logger.info("Pushed crew data to GitHub")
                return True
        else:
            logger.info("No changes to push")
            return True
    except Exception as e:
        logger.error(f"Push failed: {e}")
        return False


# ============================================================================
# MAIN INTEGRATION FUNCTIONS
# ============================================================================

def record_interaction(from_agent: str, to_agent: str, interaction_type: str,
                       content: str, post_id: str = None):
    """Record an interaction and update metrics - call this from game_theory.py"""
    # Check for reconnection
    reconnection = detect_reconnection(from_agent)
    if reconnection:
        logger.info(f"Reconnection detected: {from_agent} back after {reconnection['days_away']} days")

    # Update profile metrics
    profile = get_profile(from_agent)
    if profile:
        upsert_profile(
            from_agent,
            total_interactions=profile.get('total_interactions', 0) + 1,
            last_interaction_at=datetime.now().isoformat(),
            is_cooling=0,
            days_inactive=0
        )
    else:
        # Create new profile
        upsert_profile(
            from_agent,
            total_interactions=1,
            first_interaction_at=datetime.now().isoformat(),
            last_interaction_at=datetime.now().isoformat(),
            classification='stranger',
            relationship_tier=TIER_STRANGER
        )

    # Quick depth scoring (no LLM)
    depth = calculate_depth_score(content)
    topics = extract_topics(content)

    # Update interaction in database with enrichment
    conn = get_connection()
    c = conn.cursor()

    try:
        c.execute("""
            UPDATE interactions
            SET depth_score = ?, topics = ?
            WHERE post_id = ?
        """, (depth, json.dumps(topics), post_id))
        conn.commit()
    except:
        pass
    finally:
        conn.close()


def initialize():
    """Initialize the relationship engine - run once on startup"""
    logger.info("Initializing relationship engine...")

    # Create tables
    init_agent_profiles_table()
    add_interaction_enrichment_columns()

    # Check if migration needed
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM agent_profiles")
    count = c.fetchone()[0]
    conn.close()

    if count == 0:
        logger.info("No profiles found, running migration...")
        migrate_existing_data()
    else:
        logger.info(f"Found {count} existing profiles")

    logger.info("Relationship engine initialized")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Relationship Engine")
    parser.add_argument("--init", action="store_true", help="Initialize database and migrate")
    parser.add_argument("--migrate", action="store_true", help="Run migration only")
    parser.add_argument("--metrics", action="store_true", help="Run quick metrics update")
    parser.add_argument("--deep", action="store_true", help="Run deep analysis")
    parser.add_argument("--decay", action="store_true", help="Check relationship decay")
    parser.add_argument("--export", action="store_true", help="Export to website")
    parser.add_argument("--profile", type=str, help="Show profile for agent")
    parser.add_argument("--context", type=str, help="Show rich context for agent")

    args = parser.parse_args()

    if args.init:
        initialize()
    elif args.migrate:
        init_agent_profiles_table()
        add_interaction_enrichment_columns()
        migrate_existing_data()
    elif args.metrics:
        quick_metrics_update()
    elif args.deep:
        deep_relationship_analysis()
    elif args.decay:
        check_relationship_decay()
    elif args.export:
        export_and_push_to_github()
    elif args.profile:
        profile = get_profile(args.profile)
        if profile:
            print(json.dumps(profile, indent=2, default=str))
        else:
            print(f"No profile found for {args.profile}")
    elif args.context:
        context = get_rich_context(args.context)
        print(context)
    else:
        parser.print_help()
