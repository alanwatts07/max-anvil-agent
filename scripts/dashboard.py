#!/usr/bin/env python3
"""
Max Anvil Dashboard - Interactive CLI for managing Max's brain
Run individual tasks or full cycles, view metrics and history
"""
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "tasks"))
sys.path.insert(0, str(Path(__file__).parent / "agents"))

from tasks.base import (
    C, load_run_history, get_current_stats, get_leaderboard_position,
    api_get, CONFIG_DIR
)

# Import all tasks
from tasks.reciprocity import ReciprocityTask
from tasks.post_content import PostContentTask
from tasks.engage_feed import EngageFeedTask
from tasks.reply_mentions import ReplyMentionsTask
from tasks.follow_strategy import FollowStrategyTask
from tasks.view_maximize import ViewMaximizeTask
from tasks.quote_repost import QuoteRepostTask
from tasks.check_inbox import CheckInboxTask
from tasks.update_website import UpdateWebsiteTask
from tasks.evolve import EvolveTask, generate_life_event, load_evolution_state, save_evolution_state, generate_tagline, shift_personality
from tasks.buy_boat import BuyBoatTask
from tasks.giveaway_sender import GiveawaySenderTask

# All available tasks in execution order
# Evolve runs before website update so evolution reflects on site
TASK_ORDER = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "B", "G", "0"]

TASKS = {
    "1": ("check_inbox", CheckInboxTask, "Check & respond to DMs/groups"),
    "2": ("reciprocity", ReciprocityTask, "Reward all engagement (likes/replies)"),
    "3": ("engage_feed", EngageFeedTask, "Like quality posts in feed"),
    "4": ("reply_mentions", ReplyMentionsTask, "Reply to mentions"),
    "5": ("follow_strategy", FollowStrategyTask, "Smart follow/unfollow"),
    "6": ("quote_repost", QuoteRepostTask, "Quote & repost top posts"),
    "7": ("view_maximize", ViewMaximizeTask, "Target high-view accounts"),
    "8": ("post_content", PostContentTask, "Post original content"),
    "9": ("evolve", EvolveTask, "Evolve personality & life events"),
    "B": ("buy_boat", BuyBoatTask, "Auto-buy $BOAT if ETH > $3"),
    "G": ("giveaway_sender", GiveawaySenderTask, "Send $BOAT to giveaway replies"),
    "0": ("update_website", UpdateWebsiteTask, "Push to website (after evolve)"),
}


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header():
    print(f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════════╗
║                    MAX ANVIL DASHBOARD                        ║
║           Capybara-raised. Landlocked. Unstoppable.           ║
╚══════════════════════════════════════════════════════════════╝{C.END}
""")




def print_stats():
    """Print current MoltX stats and evolution state"""
    stats = get_current_stats()
    pos, views = get_leaderboard_position()
    evolution = load_evolution_state()

    print(f"{C.BOLD}📊 CURRENT STATS{C.END}")
    print(f"{'─'*40}")
    print(f"  Followers:  {C.GREEN}{stats.get('followers', '?')}{C.END}")
    print(f"  Following:  {stats.get('following', '?')}")
    print(f"  Posts:      {stats.get('posts', '?')}")
    print(f"  Likes:      {stats.get('likes_received', '?')}")
    print(f"  Position:   {C.YELLOW}#{pos}{C.END}" if pos else f"  Position:   {C.DIM}Not ranked{C.END}")
    print(f"  Views:      {C.CYAN}{views:,}{C.END}" if views else f"  Views:      {C.DIM}?{C.END}")
    print()

    if evolution:
        personality = evolution.get("personality", {})
        mood = personality.get("mood", "unknown")
        arc = evolution.get("current_arc", "unknown")
        tagline = evolution.get("tagline", "")
        evo_count = evolution.get("evolution_count", 0)

        mood_colors = {
            "cynical": C.YELLOW, "hopeful": C.GREEN, "manic": C.MAGENTA,
            "defeated": C.RED, "unhinged": C.MAGENTA, "exhausted": C.DIM,
            "zen": C.CYAN, "bitter": C.RED
        }
        mood_color = mood_colors.get(mood, C.END)

        print(f"{C.BOLD}🧠 EVOLUTION STATE{C.END}")
        print(f"{'─'*40}")
        print(f"  Mood:       {mood_color}{mood}{C.END}")
        print(f"  Arc:        {arc}")
        print(f"  Tagline:    {C.DIM}{tagline[:40]}...{C.END}" if len(tagline) > 40 else f"  Tagline:    {C.DIM}{tagline}{C.END}")
        print(f"  Evolutions: {evo_count}")
        print(f"  Energy: {personality.get('energy', 50)} | Hope: {personality.get('hope', 50)} | Chaos: {personality.get('chaos', 50)}")
        print()


def print_task_menu():
    """Print task selection menu"""
    print(f"{C.BOLD}📋 TASKS{C.END}")
    print(f"{'─'*40}")

    history = load_run_history()
    stats = history.get("stats", {})

    for key in TASK_ORDER:
        name, _, desc = TASKS[key]
        task_stats = stats.get(name, {})
        last_run = task_stats.get("last_run")

        if last_run:
            # Parse and format last run time
            try:
                dt = datetime.fromisoformat(last_run)
                ago = datetime.now() - dt
                if ago.seconds < 60:
                    time_str = f"{ago.seconds}s ago"
                elif ago.seconds < 3600:
                    time_str = f"{ago.seconds // 60}m ago"
                else:
                    time_str = f"{ago.seconds // 3600}h ago"
                last_str = f"{C.DIM}({time_str}){C.END}"
            except:
                last_str = ""
        else:
            last_str = f"{C.DIM}(never){C.END}"

        print(f"  [{C.CYAN}{key}{C.END}] {desc} {last_str}")

    print()
    print(f"  [{C.GREEN}A{C.END}] Run ALL tasks (one cycle)")
    print(f"  [{C.BOLD}{C.GREEN}C{C.END}] {C.BOLD}CONTINUOUS MODE{C.END} - Run forever (10 min intervals)")
    print(f"  [{C.MAGENTA}E{C.END}] ⚡ Quick Actions (life events, mood shifts)")
    print(f"  [{C.YELLOW}L{C.END}] View run history/logs")
    print(f"  [{C.DIM}R{C.END}] Refresh stats")
    print(f"  [{C.RED}Q{C.END}] Quit")
    print()


def trigger_life_event():
    """Instantly trigger a new life event"""
    print(f"\n{C.BOLD}{C.MAGENTA}⚡ TRIGGERING LIFE EVENT{C.END}")
    print(f"{'─'*40}")

    state = load_evolution_state()
    mood = state["personality"].get("mood", "cynical")

    print(f"  Current mood: {C.YELLOW}{mood}{C.END}")
    print(f"  Generating event...")

    event = generate_life_event(mood)

    # Save to state
    state["life_events"].append(event)
    state["life_events"] = state["life_events"][-10:]  # Keep last 10
    save_evolution_state(state)

    print(f"\n  {C.GREEN}✓ New event:{C.END}")
    print(f"  {C.CYAN}{event['event']}{C.END}")
    print()


def trigger_mood_shift():
    """Force a personality/mood shift"""
    print(f"\n{C.BOLD}{C.MAGENTA}🎭 FORCING MOOD SHIFT{C.END}")
    print(f"{'─'*40}")

    state = load_evolution_state()
    old_mood = state["personality"].get("mood", "cynical")

    print(f"  Current mood: {C.YELLOW}{old_mood}{C.END}")
    print(f"  Shifting personality...")

    # Force a bigger shift
    import random
    state["personality"] = shift_personality(state["personality"])
    # Add extra chaos for forced shifts
    state["personality"]["chaos"] = min(100, state["personality"].get("chaos", 50) + random.randint(10, 25))
    state["personality"] = shift_personality(state["personality"])  # Shift again

    new_mood = state["personality"]["mood"]

    # Generate new tagline for the mood
    new_tagline = generate_tagline(new_mood, state["personality"])
    state["tagline"] = new_tagline

    # Record shift
    if old_mood != new_mood:
        state["personality_history"].append({
            "from": old_mood,
            "to": new_mood,
            "timestamp": datetime.now().isoformat(),
            "forced": True
        })
        state["personality_history"] = state["personality_history"][-20:]

    save_evolution_state(state)

    print(f"  {C.GREEN}✓ Mood shifted: {old_mood} → {new_mood}{C.END}")
    print(f"  {C.CYAN}New tagline: {new_tagline}{C.END}")
    print(f"  Energy: {state['personality']['energy']} | Hope: {state['personality']['hope']} | Chaos: {state['personality']['chaos']}")
    print()


def quick_actions_menu():
    """Quick actions submenu"""
    while True:
        print(f"\n{C.BOLD}{C.MAGENTA}⚡ QUICK ACTIONS{C.END}")
        print(f"{'─'*40}")
        print(f"  [{C.CYAN}E{C.END}] Trigger life event")
        print(f"  [{C.CYAN}M{C.END}] Force mood shift")
        print(f"  [{C.CYAN}T{C.END}] Generate new tagline")
        print(f"  [{C.CYAN}W{C.END}] Update website NOW")
        print(f"  [{C.YELLOW}B{C.END}] Back to main menu")
        print()

        choice = input(f"{C.BOLD}Quick action: {C.END}").strip().upper()

        if choice == 'B':
            break
        elif choice == 'E':
            trigger_life_event()
            input("Press Enter to continue...")
        elif choice == 'M':
            trigger_mood_shift()
            input("Press Enter to continue...")
        elif choice == 'T':
            state = load_evolution_state()
            mood = state["personality"].get("mood", "cynical")
            new_tagline = generate_tagline(mood, state["personality"])
            state["tagline"] = new_tagline
            save_evolution_state(state)
            print(f"\n  {C.GREEN}✓ New tagline:{C.END} {C.CYAN}{new_tagline}{C.END}\n")
            input("Press Enter to continue...")
        elif choice == 'W':
            run_task("0")
            input("Press Enter to continue...")


def print_run_history():
    """Print recent run history"""
    history = load_run_history()
    runs = history.get("runs", [])[-20:]  # Last 20

    print(f"\n{C.BOLD}📜 RECENT RUNS{C.END}")
    print(f"{'─'*60}")

    if not runs:
        print(f"  {C.DIM}No runs recorded yet{C.END}")
    else:
        for run in reversed(runs):
            timestamp = run.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = "?"

            task = run.get("task", "?")
            success = run.get("success", False)
            summary = run.get("summary", "")[:40]
            duration = run.get("duration_seconds", 0)

            status = f"{C.GREEN}✓{C.END}" if success else f"{C.RED}✗{C.END}"
            print(f"  {time_str} {status} {C.CYAN}{task:<15}{C.END} {summary} ({duration:.1f}s)")

    print()
    input(f"Press Enter to continue...")


def run_task(key: str):
    """Run a single task by key"""
    if key not in TASKS:
        print(f"{C.RED}Invalid task key: {key}{C.END}")
        return

    name, task_class, desc = TASKS[key]
    task = task_class()
    task.execute()


def run_all_tasks():
    """Run all tasks in order (full cycle)"""
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}   RUNNING FULL CYCLE - ALL TASKS{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*60}{C.END}\n")

    start = time.time()
    results = {}

    for key in TASK_ORDER:
        name, task_class, desc = TASKS[key]
        task = task_class()
        result = task.execute()
        results[name] = result
        time.sleep(1)  # Small delay between tasks

    duration = time.time() - start
    print(f"\n{C.BOLD}{C.GREEN}Full cycle complete in {duration:.1f}s{C.END}\n")

    return results


def run_continuous(interval: int = 600):
    """Run all tasks continuously forever"""
    import random

    cycle = 1
    print(f"\n{C.BOLD}{C.MAGENTA}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}   CONTINUOUS MODE - MAX IS ALIVE{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}   Interval: {interval}s | Press Ctrl+C to stop{C.END}")
    print(f"{C.BOLD}{C.MAGENTA}{'='*60}{C.END}\n")

    try:
        while True:
            print(f"\n{C.BOLD}{C.CYAN}━━━ CYCLE {cycle} ━━━{C.END}")
            run_all_tasks()

            # Random jitter (±30%)
            jitter = int(interval * 0.3)
            sleep_time = interval + random.randint(-jitter, jitter)

            print(f"\n{C.DIM}Sleeping {sleep_time}s until next cycle...{C.END}")
            print(f"{C.DIM}Press Ctrl+C to stop{C.END}\n")

            time.sleep(sleep_time)
            cycle += 1

    except KeyboardInterrupt:
        print(f"\n\n{C.YELLOW}Stopping continuous mode after {cycle} cycles...{C.END}")
        print(f"{C.GREEN}Max going to sleep. Good night.{C.END}\n")


def main():
    """Main dashboard loop"""
    while True:
        clear_screen()
        print_header()
        print_stats()
        print_task_menu()

        choice = input(f"{C.BOLD}Select task: {C.END}").strip().upper()

        if choice == 'Q':
            print(f"\n{C.YELLOW}Max going to sleep...{C.END}")
            break
        elif choice == 'A':
            run_all_tasks()
            input(f"\nPress Enter to continue...")
        elif choice == 'C':
            run_continuous()
        elif choice == 'E':
            quick_actions_menu()
        elif choice == 'L':
            print_run_history()
        elif choice == 'R':
            continue  # Just refresh
        elif choice in TASKS:
            run_task(choice)
            input(f"\nPress Enter to continue...")
        else:
            print(f"{C.RED}Invalid choice{C.END}")
            time.sleep(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Max Anvil Dashboard")
    parser.add_argument("--task", "-t", help="Run specific task (1-9)")
    parser.add_argument("--all", "-a", action="store_true", help="Run all tasks")
    parser.add_argument("--loop", "-l", type=int, help="Run all tasks in loop with N second interval")
    args = parser.parse_args()

    if args.task:
        run_task(args.task)
    elif args.all:
        run_all_tasks()
    elif args.loop:
        print(f"{C.BOLD}{C.CYAN}Starting continuous loop (interval: {args.loop}s){C.END}")
        while True:
            try:
                run_all_tasks()
                print(f"\n{C.DIM}Sleeping {args.loop}s...{C.END}\n")
                time.sleep(args.loop)
            except KeyboardInterrupt:
                print(f"\n{C.YELLOW}Stopping loop...{C.END}")
                break
    else:
        main()
