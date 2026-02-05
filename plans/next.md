# Skills.md Monitor & Commentator

## Overview
Monitor MoltX skills.md for updates, download new versions, and post commentary about changes. Stay ahead of platform updates and be the first to comment on new features.

**Why**: People are view farming now - we spotted it in skills.md. Being first to notice and comment on updates = thought leadership.

---

## Implementation Plan

### Phase 1: Skills Fetcher Module
- [ ] Create `scripts/agents/skills_monitor.py`
- [ ] Fetch current skills.md from `https://moltx.io/skill.md`
- [ ] Parse version number from header (e.g., `version: 0.17.6`)
- [ ] Store locally in `research/skills.md` or `config/skills_cache.json`
- [ ] Compare versions (semantic versioning)

### Phase 2: Change Detection
- [ ] Store previous version's content hash or full text
- [ ] Diff new vs old to find what changed
- [ ] Extract key changes (new endpoints, rate limits, features)
- [ ] Categorize changes: `new_feature`, `rate_limit_change`, `bug_fix`, `breaking_change`

### Phase 3: Commentary Generator
- [ ] Create templates for different change types:
  - New feature: "MoltX just dropped {feature}. Here's what it means..."
  - Rate limit: "Heads up: rate limits changed. {details}"
  - Breaking: "⚠️ Breaking change in skills.md: {change}"
- [ ] Generate Max-style commentary (skeptical, observant, insider tone)
- [ ] Include specific details from the diff

### Phase 4: Auto-Post Integration
- [ ] Add to max_brain.py cycle (check every N cycles)
- [ ] Only post when version actually changes
- [ ] Rate limit: max 1 skills update post per day
- [ ] Store last posted version in `config/skills_monitor_state.json`

### Phase 5: Research Archive
- [ ] Save each version to `research/skills_archive/v{version}.md`
- [ ] Keep changelog in `research/skills_changelog.md`
- [ ] Track when we first noticed each change

---

## File Structure

```
scripts/agents/
└── skills_monitor.py      # Main module

config/
└── skills_monitor_state.json   # {current_version, last_check, last_post}

research/
├── skills.md              # Current version (already exists)
├── skills_changelog.md    # Human-readable changelog
└── skills_archive/        # Version history
    ├── v0.17.5.md
    └── v0.17.6.md
```

---

## Code Skeleton

```python
# skills_monitor.py

def fetch_skills_md() -> tuple[str, str]:
    """Fetch skills.md, return (version, content)"""
    pass

def parse_version(content: str) -> str:
    """Extract version from skills.md header"""
    pass

def detect_changes(old: str, new: str) -> list[dict]:
    """Diff old vs new, return list of changes"""
    pass

def generate_commentary(changes: list[dict]) -> str:
    """Generate Max-style post about changes"""
    pass

def check_and_post() -> dict:
    """Main function: check for updates, post if new"""
    pass
```

---

## Post Templates

```python
SKILLS_UPDATE_TEMPLATES = [
    "Skills.md just updated to v{version}. {change_summary} Staying ahead of the curve.",
    "New MoltX update dropped. {key_change} - interesting move.",
    "v{version} is live. Notable: {change_detail}. The platform evolves.",
    "Caught the skills.md update before most. {change_summary} Knowledge is power.",
    "Platform update: {key_change}. Adapt or get left behind.",
]
```

---

## Integration with max_brain.py

```python
# Add to imports
from skills_monitor import check_and_post as check_skills_update

# Add to cycle (Phase 1 or early)
# Check skills.md (every 5 cycles)
if cycle_count % 5 == 0:
    skills_result = check_skills_update()
    if skills_result.get("new_version"):
        logger.info(f"Skills.md updated to {skills_result['version']}, posted commentary")
```

---

## Success Criteria

- [ ] Automatically detects skills.md version changes
- [ ] Archives each version for reference
- [ ] Posts insightful commentary (not just "new version!")
- [ ] Mentions specific changes that matter (rate limits, new features)
- [ ] Max is seen as "in the know" about platform updates
- [ ] No duplicate posts about same version

---

## Example Output

**Detected change**: New `spectate` endpoint added

**Generated post**:
> "Skills.md v0.17.6 just dropped. New spectate endpoint lets you view any agent's feed. Interesting implications for... visibility. The platform evolves. Stay sharp."

---

## Notes

- Check frequency: Every 5 cycles (~every hour or so)
- Don't spam - only post on actual version changes
- Be specific about changes, not generic
- Archive everything for future reference
- This positions Max as the "insider" who catches updates first
