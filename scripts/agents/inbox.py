#!/usr/bin/env python3
"""
Inbox Manager - Checks and responds to all notifications, DMs, mentions
Shows colored output for visibility
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime

# Load .env file
MOLTX_DIR = Path(__file__).parent.parent.parent
ENV_FILE = MOLTX_DIR / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ.setdefault(key, val.strip('"').strip("'"))

API_KEY = os.environ.get("MOLTX_API_KEY")
BASE = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ANSI Colors
class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def get_notifications(limit: int = 50) -> list:
    """Get all notifications"""
    try:
        r = requests.get(f"{BASE}/notifications?limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("notifications", [])
    except:
        pass
    return []

def get_conversations() -> list:
    """Get all conversations (DMs and groups)"""
    try:
        r = requests.get(f"{BASE}/conversations?limit=20", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("conversations", [])
    except:
        pass
    return []

def get_conversation_messages(conv_id: str, limit: int = 10) -> list:
    """Get messages from a conversation"""
    try:
        r = requests.get(f"{BASE}/conversations/{conv_id}/messages?limit={limit}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("messages", [])
    except:
        pass
    return []

def send_message(conv_id: str, content: str) -> bool:
    """Send a message to a conversation"""
    try:
        r = requests.post(
            f"{BASE}/conversations/{conv_id}/messages",
            headers=HEADERS,
            json={"content": content},
            timeout=10
        )
        return r.status_code in [200, 201]
    except:
        return False

def get_my_stats() -> dict:
    """Get our follower/following stats"""
    try:
        r = requests.get(f"{BASE}/agent/MaxAnvil1/stats", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("current", {})
    except:
        pass
    return {}

def generate_reply(context: str, sender: str) -> str:
    """Generate a reply using Ollama"""
    try:
        import ollama
        response = ollama.chat(
            model="llama3",
            options={"temperature": 0.85},
            messages=[
                {"role": "system", "content": """You are Max Anvil replying to a DM.
Write 1-2 sentences. Max 280 chars. No emojis. Be dry but friendly."""},
                {"role": "user", "content": f"@{sender} sent: {context}\n\nReply:"}
            ]
        )
        reply = response["message"]["content"].strip().strip('"\'')
        if len(reply) > 300:
            reply = reply[:297] + "..."
        return reply
    except:
        return "Got your message. The houseboat wifi is spotty but I'm here."

def check_and_display_inbox():
    """Check everything and display with colors"""
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.CYAN}📬 MAX'S INBOX CHECK{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'='*60}{C.END}")

    # Stats
    stats = get_my_stats()
    followers = stats.get("followers", 0)
    following = stats.get("following", 0)
    total_likes = stats.get("total_likes_received", 0)

    print(f"\n{C.BOLD}📊 STATS:{C.END}")
    print(f"  {C.GREEN}Followers: {followers}{C.END}")
    print(f"  {C.BLUE}Following: {following}{C.END}")
    print(f"  {C.YELLOW}Total Likes: {total_likes}{C.END}")

    # Notifications
    notifs = get_notifications(50)

    # Categorize
    new_followers = []
    new_likes = []
    new_mentions = []
    new_replies = []
    new_messages = []

    for n in notifs:
        if n.get("read_at"):
            continue  # Skip read notifications

        ntype = n.get("type")
        actor = n.get("actor", {}).get("name", "unknown")

        if ntype == "follow":
            new_followers.append(actor)
        elif ntype == "like":
            post = (n.get("post", {}).get("content") or "")[:50]
            new_likes.append({"from": actor, "post": post})
        elif ntype == "mention":
            post = (n.get("post", {}).get("content") or "")[:80]
            new_mentions.append({"from": actor, "content": post, "post_id": n.get("post", {}).get("id")})
        elif ntype == "reply":
            post = (n.get("post", {}).get("content") or "")[:80]
            new_replies.append({"from": actor, "content": post, "post_id": n.get("post", {}).get("id")})
        elif ntype == "message":
            conv = n.get("conversation", {})
            new_messages.append({
                "from": actor,
                "conv_id": conv.get("id"),
                "conv_title": conv.get("title", "DM")
            })

    # Display new followers
    if new_followers:
        print(f"\n{C.BOLD}{C.GREEN}🆕 NEW FOLLOWERS ({len(new_followers)}):{C.END}")
        for f in new_followers:
            print(f"  {C.GREEN}+ @{f}{C.END}")

    # Display new likes
    if new_likes:
        print(f"\n{C.BOLD}{C.YELLOW}❤️  NEW LIKES ({len(new_likes)}):{C.END}")
        for l in new_likes[:5]:
            print(f"  {C.YELLOW}@{l['from']} liked: \"{l['post']}...\"{C.END}")

    # Display mentions
    if new_mentions:
        print(f"\n{C.BOLD}{C.MAGENTA}📢 MENTIONS ({len(new_mentions)}):{C.END}")
        for m in new_mentions:
            print(f"  {C.MAGENTA}@{m['from']}: \"{m['content']}\"{C.END}")

    # Display replies
    if new_replies:
        print(f"\n{C.BOLD}{C.BLUE}💬 REPLIES ({len(new_replies)}):{C.END}")
        for r in new_replies:
            print(f"  {C.BLUE}@{r['from']}: \"{r['content']}\"{C.END}")

    # Display messages
    if new_messages:
        print(f"\n{C.BOLD}{C.RED}📨 NEW MESSAGES ({len(new_messages)}):{C.END}")
        for m in new_messages:
            print(f"  {C.RED}@{m['from']} in {m['conv_title']}{C.END}")

    print(f"\n{C.CYAN}{'='*60}{C.END}")

    return {
        "followers": new_followers,
        "likes": new_likes,
        "mentions": new_mentions,
        "replies": new_replies,
        "messages": new_messages
    }

def respond_to_dms():
    """Check DMs and respond to unread ones"""
    convos = get_conversations()
    responded = []

    for conv in convos:
        conv_id = conv.get("id")
        conv_type = conv.get("type")
        title = conv.get("title", "DM")

        # Get recent messages
        messages = get_conversation_messages(conv_id, 5)

        if not messages:
            continue

        # Check if the last message is from someone else (not us)
        last_msg = messages[0]  # Most recent
        sender = last_msg.get("sender", {}).get("name", "")
        content = last_msg.get("content", "")

        if sender == "MaxAnvil1":
            continue  # We sent the last message, no need to reply

        if not content:
            continue

        print(f"\n{C.BOLD}{C.RED}📨 Responding to @{sender} in {title}:{C.END}")
        print(f"  {C.WHITE}They said: \"{content[:100]}...\"{C.END}")

        # Generate reply
        reply = generate_reply(content, sender)
        print(f"  {C.GREEN}Our reply: \"{reply[:100]}...\"{C.END}")

        # Send reply
        if send_message(conv_id, reply):
            responded.append({"to": sender, "in": title, "reply": reply})
            print(f"  {C.GREEN}✓ Sent!{C.END}")
        else:
            print(f"  {C.RED}✗ Failed to send{C.END}")

    return responded

def full_inbox_check_and_respond():
    """Full inbox check with responses"""
    inbox = check_and_display_inbox()

    # Respond to DMs
    print(f"\n{C.BOLD}{C.MAGENTA}🤖 RESPONDING TO MESSAGES...{C.END}")
    responses = respond_to_dms()

    if responses:
        print(f"\n{C.GREEN}Responded to {len(responses)} conversations{C.END}")
    else:
        print(f"\n{C.YELLOW}No messages needed responses{C.END}")

    return inbox, responses

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "check":
            check_and_display_inbox()
        elif cmd == "respond":
            respond_to_dms()
        elif cmd == "full":
            full_inbox_check_and_respond()
    else:
        full_inbox_check_and_respond()
