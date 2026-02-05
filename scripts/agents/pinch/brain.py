#!/usr/bin/env python3
"""
Pinch Brain - Main loop for Pinch Social engagement

Run this to keep Max active on Pinch Social.
Slower and more deliberate than MoltX mode.

Also handles website updates (velocity, intel, etc.) - same as max_brain.
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Setup paths
SCRIPT_DIR = Path(__file__).parent
AGENTS_DIR = SCRIPT_DIR.parent
SCRIPTS_DIR = AGENTS_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from engage import run_cycle, C
from platform_manager import get_active_platform, print_activity_stats, DRY_MODE

# Website update imports (same as max_brain)
try:
    from velocity_tracker import take_snapshot, get_velocity_report
    from velocity_export import export_and_push as export_velocity
    HAS_VELOCITY = True
except ImportError as e:
    print(f"  {C.YELLOW}Velocity tracking not available: {e}{C.END}")
    HAS_VELOCITY = False

try:
    from website_updater import update_website_smart
    HAS_WEBSITE = True
except ImportError as e:
    print(f"  {C.YELLOW}Website updater not available: {e}{C.END}")
    HAS_WEBSITE = False

try:
    from intel_export import run_export as export_intel
    HAS_INTEL = True
except ImportError as e:
    HAS_INTEL = False

try:
    from curator_database import export_to_website as export_curator
    HAS_CURATOR = True
except ImportError as e:
    HAS_CURATOR = False


def update_website():
    """Update website data (velocity, intel, etc.) - runs every cycle"""
    print(f"\n{C.CYAN}📊 Updating website data...{C.END}")

    updates = []

    # Velocity tracking & export
    if HAS_VELOCITY:
        try:
            take_snapshot()
            export_velocity()
            updates.append("velocity")
        except Exception as e:
            print(f"  {C.YELLOW}Velocity error: {e}{C.END}")

    # Intel export
    if HAS_INTEL:
        try:
            export_intel()
            updates.append("intel")
        except Exception as e:
            print(f"  {C.YELLOW}Intel error: {e}{C.END}")

    # Curator picks
    if HAS_CURATOR:
        try:
            export_curator()
            updates.append("curator")
        except Exception as e:
            print(f"  {C.YELLOW}Curator error: {e}{C.END}")

    # Smart website update (checks for meaningful changes)
    if HAS_WEBSITE:
        try:
            result = update_website_smart()
            if result.get("deployed"):
                updates.append("website-deployed")
            elif result.get("updated"):
                updates.append("website-updated")
        except Exception as e:
            print(f"  {C.YELLOW}Website error: {e}{C.END}")

    if updates:
        print(f"  {C.GREEN}Updated: {', '.join(updates)}{C.END}")
    else:
        print(f"  {C.YELLOW}No updates{C.END}")

    return updates


def run_brain(cycles: int = None, interval_minutes: int = 10):
    """
    Run the Pinch brain loop.

    Args:
        cycles: Number of cycles to run (None = infinite)
        interval_minutes: Minutes between cycles
    """
    print(f"\n{C.BOLD}{C.MAGENTA}╔═══════════════════════════════════════╗{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}║      🤏 PINCH BRAIN ACTIVATED 🤏      ║{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}╚═══════════════════════════════════════╝{C.END}")

    if DRY_MODE:
        print(f"\n{C.YELLOW}⚠ DRY MODE - No actual posts/actions{C.END}")

    platform = get_active_platform()
    if platform != "pinch":
        print(f"\n{C.RED}Warning: ACTIVE_PLATFORM={platform}, expected 'pinch'{C.END}")
        print(f"Set ACTIVE_PLATFORM=pinch in .env\n")

    print(f"\nInterval: {interval_minutes} minutes between cycles")
    if cycles:
        print(f"Running {cycles} cycles")
    else:
        print("Running indefinitely (Ctrl+C to stop)")

    cycle_count = 0

    try:
        while True:
            cycle_count += 1

            if cycles and cycle_count > cycles:
                break

            print(f"\n{C.BOLD}{'='*50}{C.END}")
            print(f"{C.BOLD}CYCLE {cycle_count}{' / ' + str(cycles) if cycles else ''}{C.END}")
            print(f"{'='*50}")

            try:
                # Pinch engagement
                run_cycle()

                # Website updates (velocity, intel, etc.)
                update_website()
            except Exception as e:
                print(f"{C.RED}Cycle error: {e}{C.END}")

            if cycles and cycle_count >= cycles:
                break

            # Wait for next cycle
            print(f"\n{C.CYAN}Next cycle in {interval_minutes} minutes...{C.END}")
            print(f"(Ctrl+C to stop)")

            for remaining in range(interval_minutes * 60, 0, -60):
                mins = remaining // 60
                print(f"  {mins} min remaining...", end="\r")
                time.sleep(min(60, remaining))

    except KeyboardInterrupt:
        print(f"\n\n{C.YELLOW}Stopped by user{C.END}")

    print(f"\n{C.BOLD}Completed {cycle_count} cycles{C.END}")
    print_activity_stats("pinch")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pinch Brain - Max's Pinch Social Loop")
    parser.add_argument("--cycles", "-c", type=int, default=None,
                       help="Number of cycles (default: infinite)")
    parser.add_argument("--interval", "-i", type=int, default=10,
                       help="Minutes between cycles (default: 10)")
    parser.add_argument("--once", action="store_true",
                       help="Run one cycle and exit")

    args = parser.parse_args()

    if args.once:
        run_cycle()
        update_website()
    else:
        run_brain(cycles=args.cycles, interval_minutes=args.interval)
