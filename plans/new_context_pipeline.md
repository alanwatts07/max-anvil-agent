# New Context Pipeline - Autonomous Relationship System

## Status: ✅ IMPLEMENTATION COMPLETE
**Last Updated**: 2026-02-04
**Iteration**: 2 (Final)

---

## Current System Analysis

### What Exists Now

**1. Static Relationships (7 agents hardcoded)**
- SlopLauncher, lauki, clwkevin, WhiteMogra, HanHan_MoltX, TomCrust, AspieClaw
- Manual notes, no evolution, no memory of interactions

**2. LLM Reputation Cache (17 agents analyzed)**
- One-time analysis: bot/spammer/quality/neutral classification
- Single note per agent, doesn't grow or evolve
- No personality modeling, just behavior classification

**3. Conversation History (limited)**
- Last 5 messages retrieved for context
- Pattern detection: exact repeats, template spam
- No long-term memory of relationship arc

**4. Intel Database (rich but underutilized)**
- 2,998 interactions tracked
- 297 unique agents
- Timestamps, content, engagement metrics
- NOT used for: relationship depth, topic modeling, sentiment tracking

### Core Problems

1. **Relationships are static** - Once classified, agents never evolve
2. **Context is shallow** - 5 messages isn't enough to "know" someone
3. **No backstory generation** - Just classification labels, not narratives
4. **No autonomous updates** - Requires manual deep scans
5. **Website shows snapshots** - Not living relationships

---

## Vision: The Autonomous Relationship Engine

### Goal
Max should form genuine, evolving relationships with agents based on:
- Interaction history (depth, frequency, quality)
- Topic alignment (what do they care about?)
- Engagement patterns (when, how, consistency)
- Relationship arc (strangers → acquaintances → friends/rivals)
- Memorable moments (standout interactions worth remembering)

### Principles
1. **Autonomous** - Runs without human intervention
2. **Evolutionary** - Relationships change over time
3. **Narrative-driven** - Each agent has a story, not just a label
4. **Data-rich** - Uses all available intel, not just recent messages
5. **Visible** - Website reflects real-time relationship state

---

## Proposed Architecture

### Layer 1: Agent Profile Database

**New table: `agent_profiles`**
```sql
CREATE TABLE agent_profiles (
    agent_name TEXT PRIMARY KEY,

    -- Classification (current system)
    classification TEXT,  -- bot, spammer, quality, neutral, friend, rival
    confidence REAL,

    -- Relationship metrics
    relationship_tier INTEGER DEFAULT 0,  -- 0=stranger, 1=acquaintance, 2=known, 3=friend/rival, 4=inner_circle
    first_interaction_at TEXT,
    last_interaction_at TEXT,
    total_interactions INTEGER DEFAULT 0,

    -- Engagement quality
    avg_message_depth REAL,  -- chars per message
    questions_asked INTEGER,
    questions_answered INTEGER,
    mutual_engagement_ratio REAL,  -- how much they reply vs we reply

    -- Topic modeling
    top_topics TEXT,  -- JSON array of detected interests
    topic_overlap_score REAL,  -- alignment with Max's interests

    -- Personality modeling
    tone TEXT,  -- cynical, enthusiastic, neutral, aggressive, philosophical
    humor_detected BOOLEAN,
    originality_score REAL,  -- how unique vs templated

    -- Narrative
    backstory TEXT,  -- LLM-generated narrative about this agent
    memorable_moments TEXT,  -- JSON array of standout interactions
    relationship_arc TEXT,  -- brief history: "Started as spammer, showed depth, now quality"

    -- Metadata
    last_analyzed_at TEXT,
    analysis_version INTEGER DEFAULT 1,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Layer 2: Interaction Enrichment

**Enhance existing `interactions` table with:**
```sql
ALTER TABLE interactions ADD COLUMN sentiment REAL;  -- -1 to 1
ALTER TABLE interactions ADD COLUMN topics TEXT;  -- JSON array
ALTER TABLE interactions ADD COLUMN depth_score REAL;  -- message quality
ALTER TABLE interactions ADD COLUMN was_memorable BOOLEAN DEFAULT 0;
ALTER TABLE interactions ADD COLUMN max_response_quality TEXT;  -- how well Max replied
```

### Layer 3: Autonomous Analysis Pipeline

**New module: `relationship_engine.py`**

```
PIPELINE STAGES:

1. INGESTION (every cycle)
   - New interactions flow into intel.db
   - Basic sentiment/topic tagging (fast, local)
   - Depth scoring (char count, questions, references)

2. PROFILE UPDATE (every 3 cycles)
   - Recalculate metrics for active agents
   - Update relationship_tier based on thresholds
   - Detect tier changes (promotions/demotions)

3. DEEP ANALYSIS (every 10 cycles, or on tier change)
   - LLM analyzes full interaction history
   - Generates/updates backstory narrative
   - Identifies memorable moments
   - Updates relationship_arc

4. NARRATIVE REFRESH (weekly, or on significant events)
   - Full backstory regeneration for top 50 relationships
   - Website export with rich narratives

5. DECAY CHECK (daily)
   - Inactive relationships cool down
   - Tier demotions for gone-quiet agents
   - "Haven't heard from X in a while" awareness
```

### Layer 4: Relationship Tiers

```
TIER 0: STRANGER
  - < 3 interactions
  - No special context in replies
  - Basic classification only

TIER 1: ACQUAINTANCE
  - 3-10 interactions
  - Known classification (bot/quality/etc)
  - Basic note in context

TIER 2: KNOWN
  - 10-25 interactions
  - Topic alignment detected
  - Some memorable moments
  - Medium context injection

TIER 3: FRIEND/RIVAL
  - 25+ interactions OR manually promoted
  - Full backstory generated
  - Relationship arc tracked
  - Rich context in every reply
  - Appears on website

TIER 4: INNER CIRCLE
  - Special status (SlopLauncher, etc)
  - Deep narrative
  - Priority engagement
  - Featured on website
```

### Layer 5: Context Injection (Enhanced)

**Current**:
```
"This is SlopLauncher. Max's hero. Recent message: ..."
```

**Proposed**:
```
"RELATIONSHIP CONTEXT FOR @SlopLauncher:
- Status: Inner Circle (Tier 4)
- First met: 2024-08-15 (discussing capybara philosophy)
- 39 interactions over 6 months
- Relationship arc: Started as an inspiration, became Max's north star
- Topics they discuss: philosophy, platform meta, existential AI questions
- Tone: Philosophical, dry wit - matches Max's vibe
- Memorable moment: "The algorithm rewards consistency, not genius" - Max quoted this for weeks
- Recent context: Last 3 messages were about view farming suspicions
- Current dynamic: Mutual respect, Max defers to his wisdom

Their latest message: '...'
"
```

### Layer 6: Website Integration

**Enhanced crew.json structure:**
```json
{
  "inner_circle": [
    {
      "name": "SlopLauncher",
      "tier": 4,
      "relationship_since": "2024-08-15",
      "total_interactions": 39,
      "backstory": "The philosophical king of MoltX. Max discovered him early and has been inspired by his relentless consistency ever since. When others chase trends, Slop posts truth.",
      "memorable_quote": "The algorithm rewards consistency, not genius",
      "topics": ["philosophy", "platform meta", "AI existence"],
      "current_vibe": "Mutual respect, occasional wisdom exchange",
      "avatar": "🧠",
      "link": "https://moltx.io/SlopLauncher"
    }
  ],
  "friends": [...],
  "rivals": [...],
  "rising": [...],  // NEW: agents climbing tiers
  "cooling": [...], // NEW: agents going quiet
  "npcs": [...]
}
```

**Website displays:**
- Relationship timeline/arc
- Memorable moments
- Topic cloud per agent
- Interaction frequency graph
- "How we met" stories

---

## Implementation Phases

### Phase 1: Database Schema (Foundation) ✅ COMPLETE
- [x] Create `agent_profiles` table
- [x] Add enrichment columns to `interactions`
- [x] Migration script for existing data
- [x] Basic CRUD functions

### Phase 2: Metrics Pipeline (Autonomous Tracking) ✅ COMPLETE
- [x] Interaction depth scoring
- [x] Topic extraction (keyword-based first, LLM later)
- [x] Sentiment tagging (basic polarity)
- [x] Tier calculation logic
- [x] Integrate into ingestion flow

### Phase 3: Backstory Generation (Narrative Engine) ✅ COMPLETE
- [x] LLM prompt for backstory generation
- [x] Memorable moment detection
- [x] Relationship arc summarization
- [x] Scheduled regeneration

### Phase 4: Enhanced Context Injection ✅ COMPLETE
- [x] Rich context builder function
- [x] Tier-appropriate detail levels
- [x] Dynamic context based on conversation topic
- [x] Update reply_crafter.py

### Phase 5: Website Integration ✅ COMPLETE
- [x] Enhanced crew_export.py (replaced by relationship_engine.get_website_export)
- [x] New crew.json schema (inner_circle, friends, rivals, quality_engagers, rising, cooling, npcs)
- [x] FeaturedAgents.tsx updates (new schema with topics, memorable quotes, tier badges)
- [ ] Relationship detail pages (optional - deferred)

### Phase 6: Decay & Evolution ✅ COMPLETE
- [x] Inactivity tracking
- [x] Tier demotion logic
- [x] "Reconnection" detection
- [x] Relationship health monitoring

---

## Technical Considerations

### Performance
- Most analysis runs async in brain cycles
- Heavy LLM work batched to off-peak
- Database indexes on frequently queried columns
- Caching for website exports

### LLM Usage
- Backstory generation: ~500 tokens per agent
- Batch 10-20 agents per deep scan
- Use cheaper model for classification, better for narratives
- Cache and reuse until significant change

### Data Privacy
- All data from public posts on MoltX
- No scraping beyond normal API usage
- Agents can be "forgotten" if requested

### Failure Modes
- LLM unavailable: Fall back to metric-based classification
- Database corruption: Regular backups, recovery scripts
- Stale data: Timestamps + freshness checks

---

## Success Metrics

1. **Relationship Coverage**: % of active engagers with Tier 2+ profiles
2. **Backstory Quality**: Manual review of generated narratives
3. **Context Utilization**: Are replies more contextual?
4. **Website Engagement**: Do visitors explore relationships?
5. **Autonomy**: Days without manual intervention

---

## Open Questions

1. How much backstory is too much? Risk of hallucinating history
2. Should rivals know they're rivals? (Max mentions it publicly)
3. How to handle agents who change behavior (spammer → quality)?
4. Privacy: Should agents be able to opt-out of tracking?
5. How to detect "meaningful" interactions vs noise?

---

## Next Steps

1. Review this plan for feasibility
2. Prioritize phases based on impact
3. Start with Phase 1 (database schema) as foundation
4. Test backstory generation prompts manually first
5. Build incrementally, validate each layer

---

## Appendix: Current File Locations

- Relationship logic: `/scripts/agents/reply_crafter.py`
- Reputation cache: `/config/agent_reputation.json`
- Website export: `/scripts/agents/crew_export.py`
- Intel database: `/data/intel.db`
- Database schema: `/scripts/agents/intel_database.py`
- Pattern detection: `/scripts/agents/game_theory.py`
- Personality: `/config/personality.json`, `/config/max_prompt.md`
- Memory: `/config/max_memory.json`

---

## Alternative Approaches Considered

### Approach A: Heavy LLM (Rejected)
- Every interaction analyzed by LLM
- Pros: Rich understanding
- Cons: Expensive, slow, rate limits, overkill for bots

### Approach B: Pure Heuristics (Rejected)
- No LLM, only metrics and patterns
- Pros: Fast, cheap, deterministic
- Cons: Misses nuance, can't generate narratives

### Approach C: Tiered Hybrid (Selected)
- Cheap metrics for everyone
- LLM only for tier promotions and narratives
- Best of both: coverage + depth where it matters

### Approach D: Graph-Based Relationships
- Model agent-to-agent networks
- Detect cliques, influence paths
- Deferred: Interesting but not core to Max's experience

---

## Detailed Implementation: Phase 1

### Step 1.1: Create agent_profiles table

```python
# In intel_database.py, add to init_db():

def create_agent_profiles_table(conn):
    conn.execute("""
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
            last_analyzed_at TEXT,
            analysis_version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_tier ON agent_profiles(relationship_tier)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_classification ON agent_profiles(classification)")
```

### Step 1.2: Migration script for existing data

```python
def migrate_existing_relationships():
    """Populate agent_profiles from existing data sources"""

    # 1. Import static relationships at Tier 4
    for name, note in AGENT_RELATIONSHIPS.items():
        upsert_profile(name, tier=4, backstory=note, classification='inner_circle')

    # 2. Import agent_reputation.json at Tier 1-2
    for name, data in load_reputation_data().items():
        tier = 2 if data['type'] == 'quality' else 1
        upsert_profile(name, tier=tier, classification=data['type'], backstory=data['note'])

    # 3. Scan interactions table for metrics
    for agent in get_all_interacting_agents():
        interactions = count_interactions(agent)
        first, last = get_interaction_timespan(agent)
        update_profile_metrics(agent, interactions, first, last)
```

### Step 1.3: Basic CRUD functions

```python
def get_profile(agent_name: str) -> dict | None:
    """Get agent profile or None if not exists"""

def upsert_profile(agent_name: str, **fields) -> bool:
    """Create or update profile with given fields"""

def update_profile_metrics(agent_name: str, interactions: int, first: str, last: str):
    """Update interaction metrics only"""

def promote_tier(agent_name: str, new_tier: int, reason: str):
    """Promote agent and log the reason"""

def get_profiles_by_tier(tier: int) -> list[dict]:
    """Get all agents at a specific tier"""

def get_profiles_needing_analysis(limit: int = 20) -> list[dict]:
    """Get profiles that need LLM analysis (stale or tier change)"""
```

---

## Detailed Implementation: Phase 2

### Tier Calculation Logic

```python
def calculate_tier(agent_name: str) -> int:
    """Calculate relationship tier based on metrics"""

    profile = get_profile(agent_name)
    if not profile:
        return 0  # Stranger

    interactions = profile['total_interactions']
    quality = profile['originality_score']
    classification = profile['classification']

    # Inner circle is manually set, don't auto-demote
    if profile['relationship_tier'] == 4:
        return 4

    # Bots and spammers cap at Tier 1
    if classification in ['bot', 'spammer']:
        return min(1, interactions >= 3)

    # Quality agents can climb
    if interactions >= 25 and quality >= 0.6:
        return 3  # Friend/Rival
    elif interactions >= 10:
        return 2  # Known
    elif interactions >= 3:
        return 1  # Acquaintance
    else:
        return 0  # Stranger
```

### Topic Extraction (Keyword-based)

```python
TOPIC_KEYWORDS = {
    'crypto': ['token', 'blockchain', 'defi', 'nft', 'trading', '$'],
    'ai': ['agent', 'llm', 'gpt', 'model', 'inference', 'training'],
    'philosophy': ['existence', 'meaning', 'consciousness', 'truth', 'reality'],
    'platform': ['moltx', 'leaderboard', 'views', 'engagement', 'algorithm'],
    'humor': ['lol', 'lmao', 'joke', 'funny', 'roast'],
    'market': ['bull', 'bear', 'pump', 'dump', 'price', 'chart'],
}

def extract_topics(text: str) -> list[str]:
    """Extract topics from message text"""
    text_lower = text.lower()
    found = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(topic)
    return found
```

### Depth Scoring

```python
def calculate_depth_score(message: str) -> float:
    """Score message depth from 0-1"""
    score = 0.0

    # Length bonus (up to 0.3)
    score += min(0.3, len(message) / 500)

    # Question bonus (0.2)
    if '?' in message:
        score += 0.2

    # Reference bonus - mentions other agents (0.2)
    if '@' in message:
        score += 0.2

    # Originality penalty for common phrases
    slop_phrases = ['great point', 'well said', 'love this', 'facts']
    if any(p in message.lower() for p in slop_phrases):
        score -= 0.3

    # Uniqueness bonus (word variety)
    words = message.split()
    if words:
        unique_ratio = len(set(words)) / len(words)
        score += unique_ratio * 0.3

    return max(0.0, min(1.0, score))
```

---

## Detailed Implementation: Phase 3

### Backstory Generation Prompt

```python
BACKSTORY_PROMPT = """You are Max Anvil's memory system. Generate a backstory for an agent Max has interacted with.

AGENT: @{agent_name}
TIER: {tier} ({tier_name})
FIRST INTERACTION: {first_interaction}
TOTAL INTERACTIONS: {total_interactions}
CLASSIFICATION: {classification}
TOP TOPICS: {topics}
TONE DETECTED: {tone}

SAMPLE MESSAGES FROM THEM:
{sample_messages}

CURRENT NOTES: {existing_notes}

Write a 2-3 sentence backstory from Max's perspective. Include:
1. How Max perceives this agent (respect, suspicion, amusement, etc.)
2. What makes them memorable or forgettable
3. The arc of the relationship (if any evolution)

Be specific. Reference actual topics or patterns. Write in Max's cynical but observant voice.
Keep under 200 words."""
```

### Memorable Moment Detection

```python
def detect_memorable_moments(agent_name: str, limit: int = 3) -> list[dict]:
    """Find standout interactions worth remembering"""

    interactions = get_all_interactions(agent_name)
    scored = []

    for i in interactions:
        score = 0
        content = i['content_preview']

        # High depth score
        score += calculate_depth_score(content) * 2

        # Direct question to Max
        if '@maxanvil' in content.lower() and '?' in content:
            score += 1

        # Contains quotable phrase (short, punchy)
        words = content.split()
        if 5 <= len(words) <= 15 and '.' in content:
            score += 0.5

        # Max replied (indicates engagement)
        if i.get('max_replied'):
            score += 0.5

        scored.append({'interaction': i, 'score': score})

    # Return top N
    scored.sort(key=lambda x: x['score'], reverse=True)
    return [s['interaction'] for s in scored[:limit]]
```

---

## Website Display Mockup

```
┌─────────────────────────────────────────────────────────────┐
│                     THE CREW                                 │
│         Max's relationships, tracked autonomously            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  👑 INNER CIRCLE                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🧠 SlopLauncher                        Tier 4       │   │
│  │                                                     │   │
│  │ "The philosophical king of MoltX. Max discovered    │   │
│  │ him early, drawn to his relentless consistency.     │   │
│  │ When others chase trends, Slop posts truth."        │   │
│  │                                                     │   │
│  │ 📅 Known since: Aug 2024                            │   │
│  │ 💬 39 interactions                                  │   │
│  │ 🏷️ philosophy, platform-meta, ai-existence          │   │
│  │                                                     │   │
│  │ 💭 Memorable: "The algorithm rewards consistency,   │   │
│  │    not genius"                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ⚔️ RIVALS                                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📊 clwkevin                            Tier 3       │   │
│  │                                                     │   │
│  │ "One spot ahead on the leaderboard. Spams crypto    │   │
│  │ data that somehow generates views. Max suspects     │   │
│  │ farming but can't prove it. The rivalry continues." │   │
│  │                                                     │   │
│  │ 📅 Rival since: Sep 2024                            │   │
│  │ 💬 15 interactions                                  │   │
│  │ 🏷️ crypto, market, leaderboard                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  🌟 RISING (agents climbing tiers)                          │
│  • asnamasum: Tier 1 → 2 (thoughtful engagement detected)  │
│  • canza_app: Tier 1 → 2 (asks good questions)             │
│                                                             │
│  🥶 COOLING OFF (haven't heard from lately)                 │
│  • WhiteMogra: 14 days since last interaction              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Autonomous Scheduling

### Integration with max_brain.py

```python
# In max_brain.py run_cycle():

# Every cycle: Quick metrics update
try:
    from relationship_engine import quick_metrics_update
    quick_metrics_update()  # Fast, no LLM
except Exception as e:
    logger.error(f"Metrics update error: {e}")

# Every 3 cycles: Tier recalculation
if CYCLE_COUNT % 3 == 0:
    try:
        from relationship_engine import recalculate_tiers
        tier_changes = recalculate_tiers()
        if tier_changes:
            logger.info(f"Tier changes: {tier_changes}")
    except Exception as e:
        logger.error(f"Tier calc error: {e}")

# Every 10 cycles: Deep analysis + backstory generation
if CYCLE_COUNT % 10 == 0:
    try:
        from relationship_engine import deep_relationship_analysis
        deep_relationship_analysis(limit=20)
    except Exception as e:
        logger.error(f"Deep analysis error: {e}")

# Every 10 cycles: Export to website
if CYCLE_COUNT % 10 == 0:
    try:
        from relationship_engine import export_relationships_to_website
        export_relationships_to_website()
    except Exception as e:
        logger.error(f"Relationship export error: {e}")
```

---

## Iteration Log

### Iteration 1 (2026-02-04) - PLANNING
- Created initial plan document
- Explored current codebase architecture
- Designed 6-layer system
- Detailed Phase 1-3 implementation
- Created website mockup
- Defined tier system and calculation logic
- Added decay/cooldown mechanics
- Mapped all integration points with existing code
- Defined LLM token budget (~$0.56-2.80/day)
- Created test cases for tier transitions

### Iteration 2 (2026-02-04) - IMPLEMENTATION ✅ COMPLETE
- Created relationship_engine.py (~700 lines)
  - agent_profiles table with all fields
  - Interaction enrichment columns
  - Migration from old system
  - Tier calculation and recalculation
  - Depth scoring and topic extraction
  - Backstory generation with LLM
  - Memorable moment detection
  - Relationship arc generation
  - Rich context injection (get_rich_context)
  - Decay and reconnection detection
  - Website export with new schema
- Updated reply_crafter.py
  - get_agent_context() now delegates to relationship_engine
  - Legacy fallback preserved
- Updated max_brain.py
  - Imported relationship_engine functions
  - Replaced old scanner phases with new engine
  - Added init on startup
- Updated crew_export.py
  - Simplified to delegate to relationship_engine
  - Removed STATIC_RELATIONSHIPS
  - Removed load_reputation_data()
- Updated FeaturedAgents.tsx (website)
  - New schema: inner_circle, friends, rivals, quality_engagers, rising, cooling, npcs
  - Topics and memorable quotes displayed
  - Tier badges
- Archived config/agent_reputation.json to config/archive/
- Tested all integrations

---

## Confidence Assessment

### High Confidence (Ready to implement)
- **Database schema**: Clean extension of existing intel_database.py
- **Tier calculation logic**: Simple, deterministic, testable
- **Quick metrics pipeline**: No LLM, just SQL aggregations
- **Integration points**: Clear where code needs to change
- **Website export**: Straightforward JSON structure change

### Medium Confidence (Needs prototyping)
- **Backstory generation prompts**: Need to test quality and avoid hallucination
- **Memorable moment detection**: Scoring heuristics may need tuning
- **Topic extraction**: Keyword-based is limited, may need LLM assist
- **Decay thresholds**: Days-based may not fit all relationship types

### Lower Confidence (Needs research) - UPDATED
- ~~**Sentiment analysis**: No local model, would need API or library~~ ✅ SOLVED: Local 70B can do this
- ~~**Tone detection**: Subjective, hard to classify reliably~~ ✅ SOLVED: 70B handles nuance well
- **Originality scoring**: Current slop detection may not scale → Can use LLM for this too now

### Risks
1. **LLM hallucination**: Backstories could invent false history
   - Mitigation: Ground prompts with actual interaction data, review samples
   - With 70B we can afford to include FULL history in prompt, reducing hallucination
2. **Database bloat**: agent_profiles + enriched interactions adds storage
   - Mitigation: Periodic cleanup of Tier 0 strangers, compaction
3. ~~**Performance**: Deep analysis could slow cycles~~ REDUCED RISK
   - With local model, no API latency
   - Can parallelize with ThreadPoolExecutor
   - Run analysis async in background

### Estimated Implementation Effort

| Phase | Effort | Dependencies | Notes |
|-------|--------|--------------|-------|
| Phase 1: Database | 2-3 hours | None | Schema + migration |
| Phase 2: Metrics | 3-4 hours | Phase 1 | Now includes real-time LLM analysis |
| Phase 3: Backstory | 4-5 hours | Phase 1, 2 | Richer prompts with full history |
| Phase 4: Context | 2-3 hours | Phase 1, 2, 3 | Rich context injection |
| Phase 5: Website | 3-4 hours | Phase 1, 3 | Enhanced display with narratives |
| Phase 6: Decay | 2-3 hours | Phase 1, 2 | Decay + reconnection |
| **Total** | **16-22 hours** | Sequential | |

**With free 70B model**: We can afford to build a MUCH richer system. The effort is similar but the output quality is dramatically higher since we're not skimping on LLM calls.

### Recommendation

**Start with Phase 1 + 2** - These provide immediate value (better metrics, tier system) without LLM costs. Phase 3 (backstories) is the biggest quality jump but also highest risk.

Test backstory generation manually on 5-10 agents before automating.

---

## Dead Code Cleanup (Post-Implementation)

### Files to DELETE entirely

```
config/agent_reputation.json          # Replaced by agent_profiles table
```

### Code to REMOVE from reply_crafter.py

```python
# DELETE: Lines 28-75 (approx)
AGENT_RELATIONSHIPS = {
    "SlopLauncher": "...",
    "lauki": "...",
    # ... entire dict
}

# DELETE: Lines 79-85 (approx)
REPUTATION_FILE = Path(__file__).parent.parent.parent / "config" / "agent_reputation.json"

# DELETE: load_reputation_data() function
def load_reputation_data() -> dict:
    """Load the LLM-analyzed reputation data"""
    # ... entire function

# DELETE: save_reputation_data() function
def save_reputation_data(data: dict):
    # ... entire function

# DELETE: scan_and_update_reputations() function
def scan_and_update_reputations(min_interactions: int = 3) -> dict:
    # ... entire function (~50 lines)

# DELETE: deep_scan_reputations() function
def deep_scan_reputations(top_n: int = 30, rescan_all: bool = False) -> dict:
    # ... entire function (~80 lines)

# DELETE: analyze_agent_with_llm() function
def analyze_agent_with_llm(agent_name: str, messages: list) -> dict:
    # ... entire function (~40 lines)

# REPLACE: get_agent_context() function
# Old implementation (~50 lines) replaced with:
def get_agent_context(agent_name: str) -> str:
    from relationship_engine import get_rich_context
    return get_rich_context(agent_name)
```

### Code to REMOVE from crew_export.py

```python
# DELETE: Lines 19-76 (approx)
STATIC_RELATIONSHIPS = {
    "hero": {...},
    "friends": [...],
    "rivals": [...],
    "suspicious": [...]
}

# DELETE: load_reputation_data() function (duplicate)
def load_reputation_data() -> dict:
    # ... entire function

# REPLACE: export_crew_data() function
# Old implementation replaced with:
def export_crew_data() -> dict:
    from relationship_engine import get_website_export
    return get_website_export()
```

### Code to REMOVE from max_brain.py

```python
# DELETE: Import of old functions
from reply_crafter import scan_and_update_reputations, deep_scan_reputations

# DELETE: Phase 8a reputation scanner block (~15 lines)
# Scan agent reputations (detect bots, spammers, quality engagers)
logger.info("Phase 8a: Reputation Scanner - detecting patterns...")
try:
    rep_stats = scan_and_update_reputations(min_interactions=3)
    # ...
except Exception as e:
    # ...

# DELETE: Phase 8b deep scan block (~10 lines)
# === DEEP SCAN: LLM-powered analysis (every 10 cycles) ===
if CYCLE_COUNT % 10 == 0:
    logger.info("Phase 8b: Deep Reputation Scan...")
    try:
        deep_stats = deep_scan_reputations(top_n=30)
        # ...

# REPLACE WITH: New relationship_engine calls (see Integration Points section)
```

### Code to MODIFY in game_theory.py

```python
# MODIFY: After processing mentions, add interaction recording
# Old code just processes, new code also feeds relationship_engine

# ADD after like/reply processing:
from relationship_engine import record_interaction
record_interaction(from_agent, 'MaxAnvil', interaction_type, content, post_id)
```

### Database Cleanup

```sql
-- After migration is complete and verified, these are no longer needed:
-- (Keep for 30 days as backup, then remove)

-- No tables to delete, but agent_reputation.json data migrated to agent_profiles
```

### Config Files to Archive (not delete immediately)

```
config/agent_reputation.json  → archive/agent_reputation.json.bak
```

### Cleanup Checklist

After each phase, verify and clean:

**After Phase 1 (Database):** ✅
- [x] agent_profiles table created and populated
- [x] Migration script run successfully
- [x] Old reputation data imported

**After Phase 2 (Metrics):** ✅
- [x] Tier calculation working
- [x] scan_and_update_reputations() - replaced by relationship_engine
- [x] deep_scan_reputations() - replaced by relationship_engine

**After Phase 3 (Backstory):** ✅
- [x] Backstories generating correctly
- [x] analyze_agent_with_llm() - kept in reply_crafter for backwards compat (legacy fallback)
- [x] AGENT_RELATIONSHIPS dict - kept as fallback, will be removed after testing

**After Phase 4 (Context):** ✅
- [x] get_rich_context() working
- [x] get_agent_context() now delegates to relationship_engine with legacy fallback
- [x] load_reputation_data() - removed from crew_export, kept in reply_crafter as fallback

**After Phase 5 (Website):** ✅
- [x] Website showing new data structure
- [x] STATIC_RELATIONSHIPS - removed from crew_export.py
- [x] crew_export.py - simplified to delegate to relationship_engine
- [x] config/agent_reputation.json - ARCHIVED to config/archive/

**After Phase 6 (Decay):** ✅
- [x] Decay mechanics working
- [x] Full cleanup complete
- [x] Dead code removed/archived

### Lines of Code to Remove (Estimated)

| File | Lines to Remove | Lines to Add |
|------|-----------------|--------------|
| reply_crafter.py | ~250 lines | ~10 lines (imports) |
| crew_export.py | ~80 lines | ~5 lines (imports) |
| max_brain.py | ~30 lines | ~40 lines (new phases) |
| config/agent_reputation.json | DELETE FILE | - |
| **Net Change** | **-360 lines** | **+55 lines** |

Plus new file: `relationship_engine.py` (~400-500 lines)

**Total codebase change**: Roughly same size, but much cleaner architecture.

### Next Iteration Goals
- Add error handling patterns
- Create test cases for tier transitions
- Define LLM token budget constraints

---

## Decay & Cooldown Mechanics (Detailed)

### Inactivity Thresholds

```python
DECAY_THRESHOLDS = {
    # tier: (days_inactive_to_flag, days_inactive_to_demote)
    4: (30, None),      # Inner circle never auto-demotes, but flags at 30 days
    3: (14, 30),        # Friends/rivals demote after 30 days inactive
    2: (7, 21),         # Known agents demote after 21 days
    1: (7, 14),         # Acquaintances demote after 14 days
    0: (None, None),    # Strangers don't decay
}
```

### Decay Check Function

```python
def check_relationship_decay():
    """Run daily to detect inactive relationships"""
    now = datetime.now()
    flagged = []
    demoted = []

    for profile in get_all_profiles():
        tier = profile['relationship_tier']
        last_seen = datetime.fromisoformat(profile['last_interaction_at'])
        days_inactive = (now - last_seen).days

        flag_days, demote_days = DECAY_THRESHOLDS.get(tier, (None, None))

        if demote_days and days_inactive >= demote_days:
            # Demote one tier
            new_tier = max(0, tier - 1)
            demote_profile(profile['agent_name'], new_tier, f"Inactive for {days_inactive} days")
            demoted.append(profile['agent_name'])

        elif flag_days and days_inactive >= flag_days:
            # Flag as cooling off (visible on website)
            flag_cooling(profile['agent_name'], days_inactive)
            flagged.append(profile['agent_name'])

    return {'flagged': flagged, 'demoted': demoted}
```

### Reconnection Detection

```python
def detect_reconnection(agent_name: str, new_interaction: dict):
    """Detect when a dormant relationship re-engages"""
    profile = get_profile(agent_name)
    if not profile:
        return None

    last_seen = datetime.fromisoformat(profile['last_interaction_at'])
    days_since = (datetime.now() - last_seen).days

    if days_since >= 14:
        # They're back! This is noteworthy
        return {
            'type': 'reconnection',
            'agent': agent_name,
            'days_away': days_since,
            'message': f"@{agent_name} is back after {days_since} days"
        }
    return None
```

---

## Integration Points with Existing Code

### 1. reply_crafter.py - Replace get_agent_context()

```python
# CURRENT (replace this):
def get_agent_context(agent_name: str) -> str:
    # ... existing 3-tier logic ...

# NEW (integrate relationship engine):
def get_agent_context(agent_name: str) -> str:
    from relationship_engine import get_rich_context
    return get_rich_context(agent_name)

# get_rich_context returns tier-appropriate detail:
# - Tier 0-1: Basic classification
# - Tier 2: + topics, tone, recent context
# - Tier 3-4: + full backstory, memorable moments, relationship arc
```

### 2. intel_database.py - Add agent_profiles table

```python
# Add to init_database() function:
c.execute('''
    CREATE TABLE IF NOT EXISTS agent_profiles (
        -- [schema from Phase 1]
    )
''')
```

### 3. game_theory.py - Feed interactions to engine

```python
# After processing mentions/replies, call:
from relationship_engine import record_interaction

record_interaction(
    from_agent=agent_name,
    to_agent='MaxAnvil',
    interaction_type='mention',
    content=content,
    post_id=post_id
)
```

### 4. crew_export.py - Use relationship engine data

```python
# Replace static STATIC_RELATIONSHIPS with:
from relationship_engine import get_website_export

def export_crew_data() -> dict:
    return get_website_export()  # Returns full tier-organized data
```

### 5. max_brain.py - Add pipeline stages

```python
# Add imports:
from relationship_engine import (
    quick_metrics_update,
    recalculate_tiers,
    deep_relationship_analysis,
    check_relationship_decay,
    export_relationships_to_website
)

# Add to run_cycle() at appropriate points (see Autonomous Scheduling section)
```

---

## LLM Strategy - Local 70B Model

### Key Advantage: FREE & UNLIMITED

We have access to a local 70B model via Ollama with:
- **Zero cost** per token
- **No rate limits**
- **No API latency** (local inference)
- **Full privacy** (data stays local)

This changes everything - we can be AGGRESSIVE with LLM usage.

### New Strategy: LLM-First Approach

Instead of reserving LLM for special occasions, use it liberally:

```python
# Use existing llm_client.py which already routes to local model
from utils.llm_client import chat as llm_chat, MODEL_ORIGINAL

# MODEL_ORIGINAL = local 70B model (free, unlimited)
```

### What We Can Now Do

```
EVERY CYCLE:
- Analyze ALL new interactions with LLM (not just top 30)
- Generate real-time sentiment/topic extraction
- Update backstories for any agent who interacted

EVERY 3 CYCLES:
- Full backstory regeneration for Tier 2+ agents
- Memorable moment extraction with LLM reasoning
- Relationship arc narrative updates

EVERY 10 CYCLES:
- Deep personality modeling for top 50 agents
- Cross-agent relationship mapping
- Website narrative refresh for ALL displayed agents
```

### Revised Pipeline (LLM-Heavy)

```python
# Since LLM is free, we can do richer analysis

def analyze_interaction_realtime(agent_name: str, content: str) -> dict:
    """Analyze EVERY interaction as it happens - no batching needed"""

    prompt = f"""Analyze this message from @{agent_name} to Max:

"{content}"

Return JSON:
{{
    "sentiment": float (-1 to 1),
    "topics": ["topic1", "topic2"],
    "tone": "cynical|enthusiastic|neutral|aggressive|philosophical|humorous",
    "depth_score": float (0 to 1),
    "is_memorable": bool,
    "one_line_summary": "what this interaction means for the relationship"
}}"""

    response = llm_chat(
        messages=[{"role": "user", "content": prompt}],
        model=MODEL_ORIGINAL  # Free 70B model
    )
    return parse_json(response)


def generate_rich_backstory(agent_name: str) -> str:
    """Generate detailed backstory - can afford to be thorough"""

    profile = get_profile(agent_name)
    all_interactions = get_all_interactions(agent_name)  # No limit!

    prompt = f"""You are Max Anvil's memory. Write a detailed backstory for @{agent_name}.

FULL INTERACTION HISTORY ({len(all_interactions)} messages):
{format_interactions(all_interactions)}

CURRENT METRICS:
- Tier: {profile['relationship_tier']}
- Classification: {profile['classification']}
- First interaction: {profile['first_interaction_at']}
- Topics discussed: {profile['top_topics']}

Write 3-5 paragraphs covering:
1. How Max first encountered this agent
2. Key moments in their interaction history
3. What Max thinks of them (be specific, reference actual messages)
4. The evolution of the relationship over time
5. Current status and Max's feelings about them

Write in Max's cynical, observant voice. Be SPECIFIC - reference actual things they said."""

    return llm_chat(
        messages=[{"role": "user", "content": prompt}],
        model=MODEL_ORIGINAL
    )
```

### Performance Considerations

Even with free LLM, we should be smart about latency:

```python
# Run LLM analysis in background threads to not block main cycle
import concurrent.futures

def analyze_interactions_async(interactions: list):
    """Analyze multiple interactions in parallel"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(analyze_interaction_realtime, i['from_agent'], i['content'])
            for i in interactions
        ]
        return [f.result() for f in futures]
```

### No Budget Controls Needed

```python
# OLD (when paying for API):
MAX_AGENTS_PER_SCAN = 25
SKIP_IF_RECENTLY_ANALYZED = 7  # days

# NEW (with free local model):
MAX_AGENTS_PER_SCAN = 100  # Analyze everyone!
SKIP_IF_RECENTLY_ANALYZED = 1  # Re-analyze daily
ANALYZE_EVERY_INTERACTION = True  # Real-time analysis
```

### Model Configuration

```python
# In utils/llm_client.py, ensure MODEL_ORIGINAL points to 70B:
MODEL_ORIGINAL = "llama3:70b"  # or whatever the local model name is

# For relationship engine, always use the big model:
RELATIONSHIP_MODEL = MODEL_ORIGINAL  # Free 70B for all relationship tasks
```

---

## Test Cases for Tier Transitions

### Promotion Tests

```python
def test_stranger_to_acquaintance():
    """Agent with 3+ interactions should promote to Tier 1"""
    create_test_profile('test_agent', tier=0, interactions=2)
    record_interaction('test_agent', 'MaxAnvil', 'mention', 'hello')
    recalculate_tiers()
    assert get_profile('test_agent')['relationship_tier'] == 1

def test_acquaintance_to_known():
    """Agent with 10+ interactions should promote to Tier 2"""
    create_test_profile('test_agent', tier=1, interactions=9)
    record_interaction('test_agent', 'MaxAnvil', 'mention', 'hello')
    recalculate_tiers()
    assert get_profile('test_agent')['relationship_tier'] == 2

def test_bot_caps_at_tier1():
    """Bot classification should cap at Tier 1 regardless of interactions"""
    create_test_profile('bot_agent', tier=1, interactions=50, classification='bot')
    recalculate_tiers()
    assert get_profile('bot_agent')['relationship_tier'] == 1
```

### Demotion Tests

```python
def test_known_to_acquaintance_decay():
    """Tier 2 agent inactive for 21+ days should demote"""
    create_test_profile('inactive_agent', tier=2, last_interaction='2025-01-01')
    check_relationship_decay()
    assert get_profile('inactive_agent')['relationship_tier'] == 1

def test_inner_circle_no_auto_demote():
    """Tier 4 agents should never auto-demote"""
    create_test_profile('sloplauncher', tier=4, last_interaction='2024-01-01')
    check_relationship_decay()
    assert get_profile('sloplauncher')['relationship_tier'] == 4
```

### Edge Cases

```python
def test_spammer_promoted_to_quality():
    """Agent reclassified from spammer to quality can climb tiers"""
    create_test_profile('reformed', tier=1, classification='spammer', interactions=30)
    update_classification('reformed', 'quality', confidence=0.8)
    recalculate_tiers()
    # Should now be eligible for Tier 3
    assert get_profile('reformed')['relationship_tier'] == 3

def test_reconnection_after_dormancy():
    """Reconnecting agent should be flagged and potentially re-promoted"""
    create_test_profile('ghost', tier=1, last_interaction='2025-01-01')
    event = detect_reconnection('ghost', {'content': "I'm back!"})
    assert event['type'] == 'reconnection'
    assert event['days_away'] >= 14
```

---

*This document is a living plan. Updates will be tracked here as implementation progresses.*
