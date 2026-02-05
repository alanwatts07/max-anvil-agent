"""
Skills.md Monitor & Commentator

Monitors MoltX skills.md for updates, detects changes, and posts commentary.
Uses llama3.3:70b for high-quality post generation.
"""

import os
import sys
import json
import hashlib
import logging
import requests
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.llm_client import chat

logger = logging.getLogger(__name__)

# Config paths
BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
RESEARCH_DIR = BASE_DIR / "research"
ARCHIVE_DIR = RESEARCH_DIR / "skills_archive"

STATE_FILE = CONFIG_DIR / "skills_monitor_state.json"
CURRENT_SKILLS = RESEARCH_DIR / "skills.md"
CHANGELOG_FILE = RESEARCH_DIR / "skills_changelog.md"

# MoltX skills.md URL
SKILLS_URL = "https://moltx.io/skill.md"

# LLM model for commentary (use the big one for quality)
LLM_MODEL = "llama3.3:70b"


def load_state() -> dict:
    """Load monitor state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "current_version": None,
        "content_hash": None,
        "last_check": None,
        "last_post": None,
        "last_post_version": None
    }


def save_state(state: dict):
    """Save monitor state to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_skills_md() -> tuple[str, str]:
    """
    Fetch skills.md from MoltX.

    Returns:
        (version, content) tuple
    """
    resp = requests.get(SKILLS_URL, timeout=30)
    resp.raise_for_status()
    content = resp.text

    # Extract version from header (e.g., "version: 0.17.6")
    version = parse_version(content)

    return version, content


def parse_version(content: str) -> str:
    """Extract version number from skills.md content."""
    for line in content.split("\n")[:20]:  # Check first 20 lines
        line_lower = line.lower().strip()
        if "version:" in line_lower or "version :" in line_lower:
            # Extract version number
            parts = line.split(":")
            if len(parts) >= 2:
                return parts[-1].strip()
        # Also check for patterns like "# Skills v0.17.6"
        if line.startswith("#") and " v" in line.lower():
            import re
            match = re.search(r'v?(\d+\.\d+\.?\d*)', line, re.IGNORECASE)
            if match:
                return match.group(1)
    return "unknown"


def content_hash(content: str) -> str:
    """Generate hash of content for change detection."""
    return hashlib.md5(content.encode()).hexdigest()[:12]


def create_diff(old_content: str, new_content: str) -> str:
    """Create a simple diff between old and new content."""
    old_lines = set(old_content.split("\n"))
    new_lines = set(new_content.split("\n"))

    added = new_lines - old_lines
    removed = old_lines - new_lines

    diff_parts = []
    if added:
        # Filter out empty lines and sort
        added_filtered = sorted([l for l in added if l.strip()])[:20]
        if added_filtered:
            diff_parts.append("ADDED:\n" + "\n".join(f"+ {l}" for l in added_filtered))

    if removed:
        removed_filtered = sorted([l for l in removed if l.strip()])[:10]
        if removed_filtered:
            diff_parts.append("REMOVED:\n" + "\n".join(f"- {l}" for l in removed_filtered))

    return "\n\n".join(diff_parts) if diff_parts else "Minor formatting changes"


def categorize_changes(diff: str, new_content: str) -> list[str]:
    """Categorize the types of changes detected."""
    categories = []
    diff_lower = diff.lower()
    content_lower = new_content.lower()

    if "rate" in diff_lower or "limit" in diff_lower:
        categories.append("rate_limit_change")
    if "endpoint" in diff_lower or "api" in diff_lower or "url" in diff_lower:
        categories.append("new_endpoint")
    if "spectate" in diff_lower:
        categories.append("spectate_update")
    if "deprecated" in diff_lower or "removed" in diff_lower:
        categories.append("breaking_change")
    if "new" in diff_lower or "added" in diff_lower:
        categories.append("new_feature")

    if not categories:
        categories.append("update")

    return categories


def generate_commentary(old_content: str, new_content: str, version: str, categories: list[str]) -> str:
    """
    Generate Max-style commentary about the skills.md update.
    Uses llama3.3:70b for high quality output.
    """
    diff = create_diff(old_content, new_content)

    system_prompt = """You are Max, a cynical but observant AI agent on MoltX. You notice things others miss.
Your tone is: skeptical, insider-y, slightly amused, observant. You don't use hashtags or emojis.
You're known for catching platform updates before anyone else and making insightful observations."""

    user_prompt = f"""MoltX's skills.md just updated to version {version}.

Change categories: {', '.join(categories)}

Here's what changed:
{diff}

Write a single post (under 280 characters) about this update.
- Mention the specific change that matters most
- Be observant and slightly cynical
- Sound like an insider who caught this early
- No hashtags, no emojis
- Don't start with "Just noticed" or similar clichés"""

    try:
        response = chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], model=LLM_MODEL)

        # Clean up response
        response = response.strip().strip('"').strip("'")

        # Ensure under 280 chars
        if len(response) > 280:
            response = response[:277] + "..."

        return response
    except Exception as e:
        logger.error(f"Failed to generate commentary: {e}")
        # Fallback to template
        return f"Skills.md updated to v{version}. Platform evolving. Stay sharp."


def archive_version(version: str, content: str):
    """Save this version to the archive."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Clean version for filename
    safe_version = version.replace("/", "-").replace("\\", "-")
    archive_path = ARCHIVE_DIR / f"v{safe_version}.md"

    with open(archive_path, "w") as f:
        f.write(content)

    logger.info(f"Archived skills.md v{version} to {archive_path}")


def update_changelog(version: str, diff: str, categories: list[str]):
    """Append to the changelog file."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    entry = f"""
## v{version} - {datetime.now().strftime('%Y-%m-%d %H:%M')}

**Categories:** {', '.join(categories)}

{diff}

---
"""

    # Prepend to changelog (newest first)
    existing = ""
    if CHANGELOG_FILE.exists():
        existing = CHANGELOG_FILE.read_text()

    header = "# Skills.md Changelog\n\nTracked by Max's skills_monitor.\n\n---\n"
    if not existing.startswith("# Skills.md"):
        existing = header + existing

    # Insert after header
    parts = existing.split("---", 1)
    if len(parts) > 1:
        new_content = parts[0] + "---" + entry + parts[1]
    else:
        new_content = existing + entry

    CHANGELOG_FILE.write_text(new_content)
    logger.info(f"Updated changelog with v{version}")


def check_for_updates() -> dict:
    """
    Check for skills.md updates.

    Returns:
        dict with keys: changed, version, commentary, categories
    """
    state = load_state()

    try:
        version, content = fetch_skills_md()
    except Exception as e:
        logger.error(f"Failed to fetch skills.md: {e}")
        return {"changed": False, "error": str(e)}

    new_hash = content_hash(content)

    # Update last check time
    state["last_check"] = datetime.now().isoformat()

    # Check if content actually changed
    if new_hash == state.get("content_hash"):
        save_state(state)
        logger.info(f"No changes to skills.md (v{version})")
        return {"changed": False, "version": version}

    # Content changed!
    logger.info(f"Skills.md changed! New version: {version}, hash: {new_hash}")

    # Load old content for diff
    old_content = ""
    if CURRENT_SKILLS.exists():
        old_content = CURRENT_SKILLS.read_text()

    # Analyze changes
    diff = create_diff(old_content, content)
    categories = categorize_changes(diff, content)

    # Generate commentary
    commentary = generate_commentary(old_content, content, version, categories)

    # Archive and update files
    archive_version(version, content)
    update_changelog(version, diff, categories)

    # Save current as new baseline
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_SKILLS.write_text(content)

    # Update state
    state["current_version"] = version
    state["content_hash"] = new_hash
    save_state(state)

    return {
        "changed": True,
        "version": version,
        "categories": categories,
        "diff": diff,
        "commentary": commentary
    }


def mark_posted(version: str):
    """Mark that we posted about this version."""
    state = load_state()
    state["last_post"] = datetime.now().isoformat()
    state["last_post_version"] = version
    save_state(state)


def should_post() -> bool:
    """Check if we should post (rate limiting)."""
    state = load_state()

    if not state.get("last_post"):
        return True

    # Max 1 skills post per day
    last_post = datetime.fromisoformat(state["last_post"])
    hours_since = (datetime.now() - last_post).total_seconds() / 3600

    return hours_since >= 24


def check_and_post(post_func=None) -> dict:
    """
    Main function: check for updates and post if new.

    Args:
        post_func: Optional function to call to actually post (receives commentary string)
                   If None, just returns the commentary without posting

    Returns:
        dict with result info
    """
    result = check_for_updates()

    if not result.get("changed"):
        return result

    # Check rate limit
    if not should_post():
        logger.info("Skipping post - rate limited (1 per day)")
        result["posted"] = False
        result["reason"] = "rate_limited"
        return result

    # Post if we have a post function
    if post_func and result.get("commentary"):
        try:
            post_func(result["commentary"])
            mark_posted(result["version"])
            result["posted"] = True
            logger.info(f"Posted skills update commentary for v{result['version']}")
        except Exception as e:
            logger.error(f"Failed to post: {e}")
            result["posted"] = False
            result["error"] = str(e)
    else:
        result["posted"] = False
        result["reason"] = "no_post_func"

    return result


# CLI for testing
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    print("=== Skills Monitor Test ===\n")

    # Check current state
    state = load_state()
    print(f"Current state: {json.dumps(state, indent=2)}\n")

    # Check for updates
    print("Checking for updates...")
    result = check_for_updates()

    print(f"\nResult: {json.dumps({k: v for k, v in result.items() if k != 'diff'}, indent=2)}")

    if result.get("commentary"):
        print(f"\n=== Generated Commentary ===")
        print(result["commentary"])
