#!/usr/bin/env python3
"""
Crew Export - Exports Max's relationships for the website.

UPDATED: Now uses relationship_engine.py for all data.
Old STATIC_RELATIONSHIPS and agent_reputation.json are deprecated.

Exports to data/crew.json and pushes to GitHub for website to fetch.
"""
from relationship_engine import export_and_push_to_github, get_website_export


def export_crew_data() -> dict:
    """Export crew data for the website - delegates to relationship_engine"""
    return get_website_export()


def save_and_push() -> bool:
    """Save crew data and push to GitHub - delegates to relationship_engine"""
    return export_and_push_to_github()


if __name__ == "__main__":
    save_and_push()
