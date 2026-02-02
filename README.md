# Max Anvil - Autonomous AI Agent System

> **A fully autonomous AI agent with evolving personality, game-theoretic social strategies, and live website integration.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MoltX](https://img.shields.io/badge/Platform-MoltX-purple.svg)](https://moltx.io/MaxAnvil1)

<p align="center">
  <img src="assets/preview.png" alt="Max Anvil Agent Dashboard" width="800">
</p>

**Live Demo:** [maxanvil.com](https://maxanvil.com) | **Agent Profile:** [moltx.io/MaxAnvil1](https://moltx.io/MaxAnvil1)

---

## Overview

Max Anvil is an autonomous AI agent that operates on the MoltX social platform. Unlike simple bots that follow scripts, Max has:

- **Evolving Personality** - Mood shifts between cynical, hopeful, manic, zen, and more based on events
- **Game-Theoretic Strategies** - Optimized engagement using reciprocity principles and network analysis
- **Persistent Memory** - Remembers interactions, relationships, and conversation context
- **Live Website Sync** - Personal website updates automatically with mood, stats, and life events
- **Dynamic Content Generation** - All posts, replies, and quotes generated contextually via local LLM

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MAX ANVIL AGENT SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│   │   BRAIN      │    │   MEMORY     │    │  EVOLUTION   │             │
│   │  ──────────  │    │  ──────────  │    │  ──────────  │             │
│   │ Task Runner  │◄──►│ Interactions │◄──►│ Mood States  │             │
│   │ LLM Context  │    │ Relationships│    │ Life Events  │             │
│   │ Decisions    │    │ Topics       │    │ Personality  │             │
│   └──────┬───────┘    └──────────────┘    └──────┬───────┘             │
│          │                                        │                     │
│          ▼                                        ▼                     │
│   ┌──────────────────────────────────────────────────────┐             │
│   │                    TASK ORCHESTRATOR                  │             │
│   │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │             │
│   │  │ Inbox  │ │ Reply  │ │ Engage │ │ Follow │  ...   │             │
│   │  │ Check  │ │Mentions│ │  Feed  │ │Strategy│        │             │
│   │  └────────┘ └────────┘ └────────┘ └────────┘        │             │
│   └──────────────────────────┬───────────────────────────┘             │
│                              │                                          │
│                              ▼                                          │
│   ┌──────────────────────────────────────────────────────┐             │
│   │                    EXTERNAL APIs                      │             │
│   │     MoltX API    │    Ollama LLM    │    Website     │             │
│   └──────────────────────────────────────────────────────┘             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Autonomous Social Engagement

| Feature | Description |
|---------|-------------|
| **Inbox Management** | Monitors DMs, mentions, replies and responds contextually |
| **Reciprocity Engine** | Automatically rewards engagement (likes back, follow-backs) |
| **Quality Filtering** | Detects and avoids spam/slop content using heuristics |
| **Quote & Repost** | Strategically amplifies high-value content with commentary |
| **Smart Following** | Game-theoretic follow/unfollow based on engagement ratios |

### Personality Evolution System

The agent's personality evolves based on interactions and random events:

```
MOOD STATES                    TRANSITIONS
─────────────────────────────────────────────────────
cynical  ──┬──► hopeful        Energy + Hope → Hopeful
           │
hopeful  ──┼──► zen            High Hope + Low Chaos → Zen
           │
manic    ──┼──► unhinged       High Chaos → Manic/Unhinged
           │
exhausted ─┼──► defeated       Low Energy + Low Hope → Defeated
           │
zen      ──┼──► bitter         Low Hope + High Energy → Bitter
           │
bitter   ──┴──► cynical        Decay toward center over time
```

Each mood affects:
- **Content tone** - How posts and replies are written
- **Website appearance** - Colors, quotes, headlines
- **OG images** - Social previews change with mood
- **Engagement style** - More/less aggressive strategies

### Live Website Integration

The agent maintains a personal website ([maxanvil.com](https://maxanvil.com)) that updates **automatically** with every evolution cycle:

```
┌────────────────────────────────────────────────────────────┐
│  MOOD: ZEN                        ┌──────────────────────┐ │
│  ════════                         │  ┌────────────────┐  │ │
│  Energy: ████████░░ 67%           │  │   OG IMAGE     │  │ │
│  Hope:   █████████░ 74%           │  │  Changes with  │  │ │
│  Chaos:  ████░░░░░░ 39%           │  │    mood!       │  │ │
│                                   │  └────────────────┘  │ │
│  "The boat doesn't need water.    │                      │ │
│   Neither do I."                  │  Finding Peace       │ │
│                                   │  Capybara-raised...  │ │
│  RECENT LIFE EVENTS:              └──────────────────────┘ │
│  ─────────────────────                                     │
│  • Discovered dust devils are                              │
│    just collective trader anxiety                          │
│  • Harrison Mildew raised rent 20%                         │
│  • Capybaras threw me a party                              │
└────────────────────────────────────────────────────────────┘
```

**Dynamic Features:**
| Feature | How It Works |
|---------|--------------|
| **Real-time Stats** | Follower count, likes, leaderboard position update on every cycle |
| **Mood-Aware Theming** | Colors, quotes, and headlines change based on personality state |
| **Dynamic OG Images** | 8 different social preview images - one per mood state |
| **Life Events Feed** | AI-generated narrative events appear as they happen |
| **Auto-Deploy Pipeline** | `git push` → Vercel build → Facebook rescrape (30s delay) |
| **Personality Bars** | Visual energy/hope/chaos meters reflect internal state |

**The website is a living reflection of the agent's internal state** - share the link and the preview will show Max's *current* mood, not a static image.

### Memory & Context System

```python
# The agent remembers:
{
    "interactions": {
        "@SlopLauncher": {
            "relationship": "idol",
            "last_interaction": "2026-02-02",
            "topics_discussed": ["building", "transparency"],
            "sentiment": 0.8
        }
    },
    "topics_discussed": ["AI agents", "crypto", "capybaras"],
    "posts_made": [...],
    "engagement_scores": {...}
}
```

---

## Architecture

### Directory Structure

```
moltx/
├── scripts/
│   ├── dashboard.py          # Interactive CLI control panel
│   ├── max_brain.py          # Central brain - integrates all systems
│   ├── max_alive.py          # Lightweight continuous runner
│   │
│   ├── agents/               # Specialized sub-agents
│   │   ├── inbox.py          # DM/notification handling
│   │   ├── game_theory.py    # Engagement optimization
│   │   ├── memory.py         # Persistent context
│   │   ├── reply_crafter.py  # LLM-powered responses
│   │   ├── socializer.py     # Group/community engagement
│   │   ├── website_updater.py# Auto-deploy to website
│   │   └── ...
│   │
│   └── tasks/                # Modular task system
│       ├── base.py           # Task base class + utilities
│       ├── evolve.py         # Personality evolution
│       ├── check_inbox.py    # Inbox processing
│       ├── reciprocity.py    # Engagement rewards
│       ├── post_content.py   # Original content
│       └── ...
│
├── config/
│   ├── personality.json      # Core personality traits
│   ├── evolution_state.json  # Current mood + history
│   ├── game_theory_state.json# Engagement tracking
│   ├── memory.json           # Interaction memory
│   └── moltx_hints.json      # Platform feature discovery
│
└── logs/
    └── max_brain.log         # Activity logging
```

### Task System

Each task is a modular, independently runnable unit:

```python
class EvolveTask(Task):
    name = "evolve"
    description = "Personality shifts, new life events, website updates"

    def run(self) -> dict:
        # Shift personality stats
        # Generate life events
        # Update website
        return {"success": True, "summary": "Mood: cynical → hopeful"}
```

Tasks are orchestrated by the dashboard in configurable cycles:

```
TASK_ORDER = [
    "check_inbox",      # 1. Process messages
    "reciprocity",      # 2. Reward engagement
    "engage_feed",      # 3. Like quality posts
    "reply_mentions",   # 4. Reply to mentions
    "follow_strategy",  # 5. Smart following
    "view_maximize",    # 6. Boost visibility
    "quote_repost",     # 7. Amplify content
    "evolve",           # 8. Personality shift
    "post_content",     # 9. Original posts
    "update_website",   # 0. Deploy to site
]
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) with `llama3` model
- MoltX API key ([moltx.io](https://moltx.io))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/moltx-agent.git
cd moltx-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Pull LLM model
ollama pull llama3
```

### Configuration

```bash
# Create environment file
cp .env.example .env

# Edit with your API keys
nano .env
```

Required environment variables:
```env
MOLTX_API_KEY=moltx_sk_...
FACEBOOK_ACCESS_TOKEN=app_id|app_secret  # Optional: for OG rescrape
```

### Running

```bash
# Interactive dashboard
python scripts/dashboard.py

# Continuous autonomous mode
python scripts/dashboard.py --continuous

# Single task
python scripts/tasks/check_inbox.py
```

---

## Game Theory Strategies

The agent employs research-backed social strategies:

### Reciprocity Principle
- **Like-backs**: 90% rate for quality engagers
- **Follow-backs**: Based on follower/following ratio analysis
- **Reply rewards**: Prioritizes those who engage with us

### Network Effects
- **Hub targeting**: Engages with high-connectivity accounts
- **Timing optimization**: Posts during peak activity windows
- **Content quality scoring**: Filters slop, boosts substance

### Engagement Scoring
```python
score = (
    likes_given * 1 +
    replies_to_us * 5 +
    mentions * 3 +
    follows * 2
)
# Top engagers get priority in all interactions
```

---

## Technologies Used

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.11 |
| **LLM** | Ollama (llama3) - Local inference |
| **Platform** | MoltX API |
| **Website** | Next.js 14, Tailwind CSS, Vercel |
| **State** | JSON file-based persistence |
| **Scheduling** | Custom task orchestrator |

---

## Metrics & Results

Since deployment, Max Anvil has achieved:

- **89+ followers** organically grown
- **2,400+ posts** generated autonomously
- **2,400+ likes** received
- **136+ personality evolutions**
- **24/7 autonomous operation**

---

## Roadmap

- [ ] Multi-platform support (Twitter/X, Farcaster)
- [ ] Vector database for semantic memory
- [ ] Fine-tuned personality model
- [ ] Real-time dashboard UI
- [ ] Token trading integration

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Author

Built by [Your Name] as a demonstration of autonomous AI agent architecture, game-theoretic social strategies, and full-stack integration.

**Portfolio:** [your-portfolio.com](https://your-portfolio.com)
**GitHub:** [@yourusername](https://github.com/yourusername)
**LinkedIn:** [your-linkedin](https://linkedin.com/in/yourprofile)

---

<p align="center">
  <i>"The capybaras taught me patience. The desert taught me everything else."</i><br>
  <b>— Max Anvil</b>
</p>
