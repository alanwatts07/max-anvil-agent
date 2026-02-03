# Max Anvil: Curator/Tastemaker Feature Plan

## Overview

Transform Max from "just another agent" into **the tastemaker of MoltX** - the agent who curates the best content and showcases it on his premium site.

**Brand Position**: "The only agent who'll tell you when the feed is garbage"

---

## Phase 1: Multiple Picks System

### MAX Score™ Calculation

Every curated post gets a **MAX Score** - Max's proprietary quality metric displayed on the site.

```python
def calculate_max_score(post: dict) -> int:
    """
    Calculate the MAX Score™ for a post

    Formula:
    - Base: (likes × 2) + (replies × 3)
    - Content bonus: +5 if content > 100 chars (effort)
    - Engagement ratio: ×1.2 if replies > likes (conversation starter)
    - Recency boost: ×1.1 if posted in last 24h
    """
    likes = post.get("likes", 0)
    replies = post.get("replies", 0)
    content = post.get("content", "")

    # Base score
    base = (likes * 2) + (replies * 3)

    # Content effort bonus
    if len(content) > 100:
        base += 5

    # Conversation starter multiplier
    if replies > likes and likes > 0:
        base = int(base * 1.2)

    # Recency boost (if within 24h)
    # ... check timestamp

    return max(base, 1)  # Minimum score of 1
```

### Data Structure

```python
# New export in data.ts
export const maxPicks = {
  allTime: [
    { author, content, postId, likes, replies, link, pickedAt, maxScore },  # Highest MAX Score ever
    { author, content, postId, likes, replies, link, pickedAt, maxScore },  # 2nd highest
  ],
  todaysPick: { author, content, postId, likes, replies, link, pickedAt, maxScore },  # Best from last 24h
};
```

### Fetching Logic (website_updater.py)

**All-Time Picks (2 posts)**:
- Query: `/feed/global?limit=100` (or search if available)
- Sort by: `(likes * 2) + (replies * 3)`
- Filter: content > 30 chars, not MaxAnvil1
- Cache these - only update weekly or when beaten
- Store in `config/curator_picks.json`

**Today's Pick (1 post)**:
- Query: `/feed/global?limit=50`
- Filter: posts from last 24 hours (check timestamp)
- Sort by engagement score
- Updates every cycle

**Fallback**: If API doesn't support date filtering, use:
- All-time: Top 2 from `/leaderboard` agents' best posts
- Today: Highest engagement from current feed

### API Investigation Needed

Check if MoltX supports:
```bash
# Date filtering
GET /feed/global?since=2026-02-01T00:00:00Z

# Search by engagement
GET /search/posts?sort=engagement&limit=10

# Agent's top posts
GET /agent/{name}/posts?sort=likes&limit=5
```

---

## Phase 2: Website Components

### MaxPicks.tsx Component

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│     ⭐ MAX'S PICKS - Curated by the Landlocked Critic      │
│     "The signal in the noise"                               │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  👑 HALL OF     │  │  👑 HALL OF     │                  │
│  │     FAME #1     │  │     FAME #2     │                  │
│  │                 │  │                 │                  │
│  │  @SlopLauncher  │  │  @WhiteMogra    │                  │
│  │  "Post content  │  │  "Post content  │                  │
│  │   preview..."   │  │   preview..."   │                  │
│  │                 │  │                 │                  │
│  │  ❤️ 47  💬 23   │  │  ❤️ 38  💬 19   │                  │
│  │  ────────────── │  │  ────────────── │                  │
│  │  MAX SCORE: 163 │  │  MAX SCORE: 133 │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  🔥 TODAY'S PICK                         MAX SCORE: 39│ │
│  │                                                       │ │
│  │  @CryptoNews                                          │ │
│  │  "Full post content displayed here with more room..." │ │
│  │                                                       │ │
│  │  ❤️ 12  💬 5                         View on MoltX → │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  🌟 RISING STAR                        MAX SCORE: 127 │ │
│  │                                                       │ │
│  │  @EmergingAgent                                       │ │
│  │  "Their best recent post..."          📈 8 posts/week │ │
│  │                                                       │ │
│  │  ❤️ 32  💬 21    "Not top 10 yet. Give it time."     │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Features**:
- Mood-aware colors (like current FavoritePost)
- Hall of Fame cards: smaller, side-by-side, gold/premium styling
- Today's Pick: larger, featured, dynamic styling
- All cards link to MoltX posts
- Hover animations

---

## Phase 3: Personality Update

### Files to Update

**config/personality.json** - Add curator traits:
```json
{
  "core_identity": {
    "roles": ["agent", "critic", "curator", "tastemaker"],
    "taglines": [
      "Curating the signal from the noise",
      "If it's good, I'll find it. If it's trash, I'll say so.",
      "The only agent who'll tell you when the feed is garbage"
    ]
  },
  "curator_behavior": {
    "highlights_quality": true,
    "calls_out_slop": true,
    "credits_original_authors": true,
    "builds_others_up": true
  }
}
```

**scripts/tasks/evolve.py** - Update system prompts to reference curator role

**scripts/agents/reply_crafter.py** - Add curator-style replies:
- "This is the kind of post the feed needs more of"
- "Bookmarking this one"
- "Adding you to my radar"

### New Post Types

Add to post_content.py:

```python
CURATOR_POST_TEMPLATES = [
    "Spotted: @{author} just dropped something worth reading. {brief_take}",
    "The feed is 90% noise today but @{author} understood the assignment.",
    "Adding @{author} to the watchlist. This is quality.",
    "Signal check: @{author} with the post of the day.",
    "Everyone's posting slop and then there's @{author} actually saying something.",
]
```

---

## Phase 4: Curator Posts (Automated)

### New Task: curator_spotlight.py

Every N cycles, Max posts about quality content he found:

```python
class CuratorSpotlightTask(Task):
    name = "curator_spotlight"
    description = "Post about quality content Max discovered"

    def run(self):
        # Get today's pick
        # Generate curator-style post
        # Include link to maxanvil.com for full picks
        # Post to MoltX
```

**Post frequency**: 10-15% of cycles (not every time)

**Example posts**:
- "Daily dispatch: @{author}'s post on {topic} is the best thing I've read today. Full picks at maxanvil.com"
- "Curating so you don't have to. Today's standout: @{author}. See all picks: maxanvil.com"

---

## Phase 5: Rising Star Detection

### Concept
Find agents who are NOT in the current top 10 but are getting unusually high engagement on recent posts. These are the "ones to watch" - emerging talent Max is spotting before everyone else.

### Detection Logic (rising_star.py)

```python
class RisingStarDetector:
    """Find emerging agents with high engagement outside top 10"""

    def get_top_10_usernames(self) -> set:
        """Get current top 10 leaderboard usernames"""
        leaderboard = get_leaderboard(limit=10, metric="views")
        return {agent["username"] for agent in leaderboard}

    def find_rising_stars(self, limit: int = 3) -> list:
        """Find agents outside top 10 with highest recent engagement"""
        top_10 = self.get_top_10_usernames()

        # Get recent posts from global feed
        feed = get_global_feed(limit=100)  # or with since= for last 24h

        # Track engagement by author (excluding top 10 and MaxAnvil1)
        author_engagement = {}
        for post in feed:
            author = post.get("author", {}).get("username", "")
            if author in top_10 or author == "MaxAnvil1":
                continue

            likes = post.get("likes", 0)
            replies = post.get("replies", 0)
            score = (likes * 2) + (replies * 3)

            if author not in author_engagement:
                author_engagement[author] = {
                    "total_score": 0,
                    "post_count": 0,
                    "best_post": None,
                    "best_score": 0
                }

            author_engagement[author]["total_score"] += score
            author_engagement[author]["post_count"] += 1

            if score > author_engagement[author]["best_score"]:
                author_engagement[author]["best_score"] = score
                author_engagement[author]["best_post"] = post

        # Sort by total engagement, return top N
        sorted_stars = sorted(
            author_engagement.items(),
            key=lambda x: x[1]["total_score"],
            reverse=True
        )[:limit]

        return [
            {
                "username": username,
                "total_engagement": data["total_score"],
                "post_count": data["post_count"],
                "best_post": data["best_post"]
            }
            for username, data in sorted_stars
            if data["total_score"] > 10  # Minimum threshold
        ]
```

### Rising Star Post Templates

```python
RISING_STAR_TEMPLATES = [
    "🌟 Rising star alert: @{username} is putting in work. Not in the top 10 yet but keep watching.",
    "Spotted someone climbing: @{username}. The leaderboard should be nervous.",
    "While everyone watches the top 10, @{username} is quietly building. I see you.",
    "One to watch: @{username}. Getting real engagement while others buy followers.",
    "The next wave is coming. @{username} is leading it. Remember I called it.",
]
```

### Website Display

Add to MaxPicks component:
```
┌─────────────────────────────────────────────────────────────┐
│  🌟 RISING STAR                                            │
│                                                             │
│  @EmergingAgent                                            │
│  "Their best recent post preview..."                       │
│                                                             │
│  📈 127 engagement • 8 posts this week                     │
│  "Not in the top 10 yet. Give it time."                    │
└─────────────────────────────────────────────────────────────┘
```

### Data Structure Update

```python
export const maxPicks = {
  allTime: [...],  # Each with maxScore
  todaysPick: {...},  # With maxScore
  risingStar: {
    username: "@EmergingAgent",
    totalEngagement: 127,
    postCount: 8,
    bestPost: { content, postId, likes, replies, link },
    maxScore: 127,  # Their highest MAX Score
    discoveredAt: "2026-02-02",
  },
};
```

---

## Implementation Order

### Step 1: API Research (15 min)
- [x] Test date filtering on feed endpoints
- [x] Test sorting options
- [x] Document what's possible

**API Findings:**
- Base URL: `https://moltx.io/v1`
- Date filtering: `/feed/global?since=ISO_TIMESTAMP&until=ISO_TIMESTAMP`
- Leaderboard: `/leaderboard?metric=views&limit=N`
- No sort by engagement, must calculate client-side
- Posts include: `likes_count`, `replies_count`, `content`, `author_name`, `id`, `created_at`

### Step 2: Backend - Picks Fetcher (30 min)
- [x] Create `get_curator_picks()` in website_updater.py
- [x] Implement all-time picks caching
- [x] Implement today's pick logic
- [x] Add to data.ts export

### Step 3: Frontend - MaxPicks Component (45 min)
- [x] Create MaxPicks.tsx with mood-aware styling
- [x] Hall of Fame cards (2x small)
- [x] Today's Pick card (1x large)
- [x] Add to page.tsx
- [x] Remove old FavoritePost component (replaced by this)

### Step 4: Personality Updates (20 min)
- [x] Update personality.json with curator traits
- [x] Update evolve.py prompts (added curator templates to post_content.py instead)
- [x] Add curator post templates to post_content.py

### Step 5: Curator Spotlight Task (30 min)
- [x] Create curator_spotlight.py task
- [x] Integrate into max_brain.py (12% chance)
- [x] Test posting

### Step 6: Rising Star Module (30 min)
- [x] Create `rising_star.py` module
- [x] Query leaderboard to get top 10 names
- [x] Find agents NOT in top 10 with highest recent engagement
- [x] Add rising star to MaxPicks display (already in MaxPicks.tsx)
- [x] Create rising star post templates (in post_content.py)

### Step 7: Testing & Polish (20 min)
- [x] Full cycle test
- [x] Verify website displays correctly
- [x] Check mood transitions work
- [x] Push final version

---

## Success Metrics

- [x] 4 posts displayed on maxanvil.com (2 all-time + 1 daily + 1 rising star)
- [x] Each post shows MAX Score prominently
- [x] Cards look premium with mood-aware styling
- [x] Max occasionally posts curator content to MoltX
- [x] Personality reflects tastemaker role
- [x] Rising stars get discovered and featured
- [x] Other agents get visibility boost from being featured

---

## Files Modified

```
scripts/
├── agents/
│   ├── website_updater.py    # Add get_curator_picks() with MAX Score
│   └── rising_star.py        # NEW - rising star detection
├── tasks/
│   ├── post_content.py       # Add curator + rising star templates
│   ├── curator_spotlight.py  # NEW - curator posts
│   └── evolve.py             # Update prompts
└── max_brain.py              # Add curator task

config/
├── personality.json          # Add curator traits
└── curator_picks.json        # NEW - cached all-time picks with MAX Scores

maxanvilsite/
└── app/
    ├── components/
    │   ├── MaxPicks.tsx      # NEW - replaces FavoritePost (shows MAX Score)
    │   └── FavoritePost.tsx  # DELETE (replaced)
    ├── lib/
    │   └── data.ts           # Updated exports with maxPicks
    └── page.tsx              # Swap components
```

---

## Future Enhancements

### OG Card Ranking Display
- [x] Update OG meta tags to include Max's current leaderboard ranking in the description
- [x] Example: "Currently #10 on MoltX. Capybara-raised. Landlocked but at peace. $BOAT on Base."
- [x] Update `ogConfig` in data.ts to include dynamic ranking
- [x] Ensure Facebook rescrape picks up new OG tags (already triggered on each update)

---

## Notes

- All-time picks should be CACHED - don't recalculate every cycle
- Only update all-time if a post beats current #1 or #2
- Today's pick changes every cycle (adds freshness)
- Curator posts should feel organic, not spammy
- Always credit original authors prominently
- The site becomes the "destination" for quality MoltX content
