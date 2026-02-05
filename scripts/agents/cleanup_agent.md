# Cleanup Agent - Dead Code Detection from Git History

A guide for using Claude Code to identify and clean up dead code, keeping the moltx repo professional.

## When to Use

Run a cleanup audit when:
- After major refactors (like the Pinch Social port)
- Before releases or major deployments
- When the repo feels cluttered with old modules
- Quarterly maintenance

## How to Use

Ask Claude Code to analyze dead code with prompts like:

```
Analyze the git history for this repo. Identify:
1. Files that were heavily modified then abandoned
2. Functions/classes that are no longer imported anywhere
3. Config files for features that no longer exist
4. Commented-out code blocks that can be deleted
5. TODO comments that are now stale
```

## Specific Cleanup Tasks

### 1. Find Orphaned Modules
```
Search for Python files in scripts/agents/ that are:
- Not imported by any other file
- Not referenced in start.sh or any task runner
- Have no recent commits (6+ months)
```

### 2. Detect Dead Config Files
```
Check config/*.json files and identify which ones:
- Are never loaded by any script
- Contain data for deprecated features
- Have duplicate/overlapping purposes
```

### 3. Find Unused Imports
```
For each Python file, check if all imports are actually used.
List files with unused imports that can be cleaned.
```

### 4. Identify Stale State Files
```
Review config/*_state.json files. Which ones:
- Track features that no longer run
- Haven't been modified in 30+ days
- Can be safely archived
```

## Archive Strategy

Don't delete immediately. Move to `archive/` folder:

```
archive/
├── deprecated_agents/     # Old agent scripts
├── old_configs/          # Unused config files
└── legacy_data/          # Historical state files
```

## Example Cleanup Session

```bash
# Ask Claude to find dead code
claude "Analyze scripts/agents/ and identify any Python files that are
not imported anywhere and not referenced in start.sh.
List candidates for archival."

# Review suggestions, then archive
mkdir -p archive/deprecated_agents
mv scripts/agents/old_module.py archive/deprecated_agents/

# Update .gitignore if needed
echo "archive/" >> .gitignore
```

## Files to Review (Known Candidates)

Based on the current repo state, these may be cleanup candidates:

| File | Status | Notes |
|------|--------|-------|
| `scripts/agents/callout_post.py` | Review | May be superseded by engage.py |
| `scripts/agents/top10_shoutout.py` | Review | Check if still used |
| `scripts/agents/steady_pump.py` | Review | Older posting strategy |
| `config/view_pump.json` | Review | May be deprecated |
| `config/view_farm.json` | Review | Contains backup API keys - keep secure |

## Safety Rules

1. **Never delete files with API keys** - move to secure archive
2. **Check git blame first** - understand why code exists
3. **Grep before deleting** - ensure nothing imports it
4. **Keep backups** - archive folder, not trash
5. **Document removals** - update changelog

## Quick Commands

```bash
# Find files not modified in 60 days
find scripts/agents -name "*.py" -mtime +60

# Find unreferenced Python files
for f in scripts/agents/*.py; do
  name=$(basename "$f" .py)
  if ! grep -rq "$name" scripts/ --include="*.py" --include="*.sh"; then
    echo "Possibly unused: $f"
  fi
done

# Find large config files (possible bloat)
ls -lhS config/*.json | head -20
```

## Integration with CI

Consider adding a GitHub Action that:
1. Runs quarterly
2. Lists files with no commits in 90 days
3. Opens a cleanup issue for review

---

*Last updated: 2026-02-04*
*For Max Anvil's moltx bot infrastructure*
