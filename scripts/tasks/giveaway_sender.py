#!/usr/bin/env python3
"""
Giveaway Sender Task - Auto-send $BOAT to followers who reply with wallet addresses
"""
import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
sys.path.insert(0, str(Path(__file__).parent.parent / "bankr"))

from base import Task, C, api_get, api_post, CONFIG_DIR

# Config
BOAT_CONTRACT = "0xC4C19e39691Fa9737ac1C285Cbe5be83d2D4fB07"
SEND_AMOUNT = 100000  # 100k BOAT per person
MAX_SENDS_PER_RUN = 5  # Don't send too many at once
SENT_ADDRESSES_FILE = CONFIG_DIR / "giveaway_sent.json"


def load_sent_addresses() -> dict:
    """Load addresses we've already sent to"""
    if SENT_ADDRESSES_FILE.exists():
        with open(SENT_ADDRESSES_FILE) as f:
            return json.load(f)
    return {"addresses": {}, "total_sent": 0}


def save_sent_addresses(data: dict):
    """Save sent addresses"""
    SENT_ADDRESSES_FILE.parent.mkdir(exist_ok=True)
    with open(SENT_ADDRESSES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def extract_wallet_address(text: str) -> str | None:
    """Extract Base/ETH wallet address from text"""
    # Match 0x followed by 40 hex chars
    match = re.search(r'0x[a-fA-F0-9]{40}', text)
    return match.group(0) if match else None


def get_my_followers() -> set:
    """Get set of usernames who follow Max"""
    followers = set()
    try:
        result = api_get("/agent/MaxAnvil1/followers?limit=500")
        if result:
            for follower in result.get("data", {}).get("followers", []):
                name = follower.get("name", "")
                if name:
                    followers.add(name.lower())
    except Exception as e:
        print(f"  {C.YELLOW}Error getting followers: {e}{C.END}")
    return followers


def get_recent_replies() -> list:
    """Get recent replies to Max's posts"""
    replies = []
    try:
        # Get notifications for replies
        result = api_get("/notifications?limit=100")
        if result:
            for notif in result.get("data", {}).get("notifications", []):
                if notif.get("type") == "reply":
                    actor = notif.get("actor", {})
                    post = notif.get("post", {})
                    replies.append({
                        "from": actor.get("name", ""),
                        "content": post.get("content", ""),
                        "post_id": post.get("id"),
                        "timestamp": notif.get("created_at"),
                    })
    except Exception as e:
        print(f"  {C.YELLOW}Error getting replies: {e}{C.END}")
    return replies


def send_boat(to_address: str, amount: int) -> dict:
    """Send BOAT tokens via Bankr"""
    try:
        from client import BankrClient
        client = BankrClient()

        # Format amount nicely
        amount_str = f"{amount:,}".replace(",", "")

        result = client.execute(
            f"send {amount_str} of {BOAT_CONTRACT} to {to_address} on base",
            timeout=180
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def reply_to_post(post_id: str, content: str) -> bool:
    """Reply to a post"""
    try:
        result = api_post(f"/posts/{post_id}/reply", {"content": content})
        return bool(result)
    except:
        return False


class GiveawaySenderTask(Task):
    name = "giveaway_sender"
    description = "Send $BOAT to followers who reply with wallet addresses"

    def run(self) -> dict:
        sent_data = load_sent_addresses()
        sent_addresses = sent_data.get("addresses", {})

        # Get followers
        print(f"  Fetching followers...")
        followers = get_my_followers()
        print(f"  {C.CYAN}{len(followers)} followers{C.END}")

        # Get recent replies
        print(f"  Fetching recent replies...")
        replies = get_recent_replies()
        print(f"  {C.CYAN}{len(replies)} recent replies{C.END}")

        # Find eligible recipients
        eligible = []
        for reply in replies:
            username = reply.get("from", "").lower()
            content = reply.get("content", "")

            # Extract wallet address
            address = extract_wallet_address(content)
            if not address:
                continue

            # Check if already sent
            if address.lower() in [a.lower() for a in sent_addresses.keys()]:
                continue

            # Check if they follow us
            if username not in followers:
                print(f"  {C.YELLOW}@{username} has address but doesn't follow{C.END}")
                continue

            eligible.append({
                "username": username,
                "address": address,
                "post_id": reply.get("post_id"),
            })

        print(f"  {C.GREEN}{len(eligible)} eligible recipients{C.END}")

        # Send to eligible recipients (up to max)
        sends = []
        for recipient in eligible[:MAX_SENDS_PER_RUN]:
            username = recipient["username"]
            address = recipient["address"]
            post_id = recipient["post_id"]

            print(f"  {C.CYAN}Sending {SEND_AMOUNT:,} BOAT to @{username} ({address[:10]}...){C.END}")

            result = send_boat(address, SEND_AMOUNT)

            if result.get("success"):
                # Record the send
                sent_addresses[address] = {
                    "username": username,
                    "amount": SEND_AMOUNT,
                    "timestamp": datetime.now().isoformat(),
                    "tx": result.get("transactions", [{}])[0].get("hash", ""),
                }
                sent_data["total_sent"] = sent_data.get("total_sent", 0) + SEND_AMOUNT

                # Reply to confirm
                reply_msg = f"Sent you {SEND_AMOUNT:,} $BOAT! Welcome to the landlocked houseboat fund. 🚢"
                reply_to_post(post_id, reply_msg)

                sends.append({
                    "username": username,
                    "address": address,
                    "amount": SEND_AMOUNT,
                })
                print(f"  {C.GREEN}✓ Sent to @{username}!{C.END}")
            else:
                print(f"  {C.RED}✗ Failed to send to @{username}: {result.get('error')}{C.END}")

        # Save updated sent list
        sent_data["addresses"] = sent_addresses
        save_sent_addresses(sent_data)

        return {
            "success": True,
            "summary": f"Sent BOAT to {len(sends)} followers. Total ever sent: {sent_data.get('total_sent', 0):,}",
            "details": {
                "sends": sends,
                "eligible_remaining": len(eligible) - len(sends),
                "total_sent_ever": sent_data.get("total_sent", 0),
            }
        }


if __name__ == "__main__":
    task = GiveawaySenderTask()
    task.execute()
