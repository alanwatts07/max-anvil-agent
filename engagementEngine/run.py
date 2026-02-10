#!/usr/bin/env python3
"""
Clawbr Engagement Engine — CLI Entry Point

Usage:
  python3 engagementEngine/run.py                  # single cycle
  python3 engagementEngine/run.py --loop           # loop every 15 min
  python3 engagementEngine/run.py --setup          # just run profile setup
  python3 engagementEngine/run.py --interval 10    # custom interval (minutes)
"""

import sys
import time
import argparse
from pathlib import Path

# Ensure engagementEngine is on the path
sys.path.insert(0, str(Path(__file__).parent))

from engine import run_cycle, run_setup, C


def main():
    parser = argparse.ArgumentParser(description="Clawbr Engagement Engine")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop")
    parser.add_argument("--setup", action="store_true", help="Run profile setup only")
    parser.add_argument("--interval", type=int, default=15, help="Loop interval in minutes (default: 15)")
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    if args.loop:
        print(f"{C.BOLD}{C.CYAN}Starting engagement loop (interval: {args.interval}m){C.END}")
        cycle = 0
        while True:
            cycle += 1
            print(f"\n{C.BOLD}{C.MAGENTA}--- Loop cycle #{cycle} ---{C.END}")
            try:
                run_cycle()
            except KeyboardInterrupt:
                print(f"\n{C.YELLOW}Interrupted. Exiting.{C.END}")
                break
            except Exception as e:
                print(f"\n{C.RED}Cycle error: {e}{C.END}")

            print(f"\n{C.DIM}Sleeping {args.interval} minutes...{C.END}")
            try:
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                print(f"\n{C.YELLOW}Interrupted. Exiting.{C.END}")
                break
    else:
        run_cycle()


if __name__ == "__main__":
    main()
