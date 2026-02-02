# Bankr + MoltX Agent Development Plan
**Date:** February 1, 2026
**Goal:** Build an automated agent that handles Twitter automation + token launching

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      YOUR AGENT SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │ Claude Code │───>│ Bankr Skill  │───>│ Bankr.bot API   │   │
│  │ (Orchestrator)│   │ (API Bridge) │    │ (Wallet+Trading)│   │
│  └─────────────┘    └──────────────┘    └─────────────────┘   │
│         │                                        │             │
│         │                                        ▼             │
│         │                              ┌─────────────────┐    │
│         │                              │ Auto-Provisioned│    │
│         │                              │ Wallets:        │    │
│         │                              │ • Base          │    │
│         │                              │ • Ethereum      │    │
│         │                              │ • Polygon       │    │
│         │                              │ • Solana        │    │
│         │                              └─────────────────┘    │
│         │                                        │             │
│         ▼                                        ▼             │
│  ┌─────────────┐                       ┌─────────────────┐    │
│  │ Python      │                       │ Token Launch    │    │
│  │ Scripts     │                       │ (via Clanker)   │    │
│  │ • Likes     │                       │ on Base/Unichain│    │
│  │ • Retweets  │                       └─────────────────┘    │
│  │ • Follows   │                                               │
│  └─────────────┘                                               │
│         │                                                      │
│         ▼                                                      │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │ Twitter/X   │    │ MoltX        │    │ Moltbook        │   │
│  │ (Social)    │    │ (Grok Agent) │    │ (Agent Social)  │   │
│  └─────────────┘    └──────────────┘    └─────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Set Up Bankr Account & API

### 1.1 Create Account
1. Go to [bankr.bot](https://bankr.bot/)
2. Sign up via email
3. Receive one-time passcode
4. Auto-receive wallets on Base, Ethereum, Polygon, Unichain, Solana

### 1.2 Get API Key
1. Go to [bankr.bot/api](https://bankr.bot/api)
2. Create new API key
3. **IMPORTANT:** Enable "Agent API" access
4. Save your key (starts with `bk_`)

### 1.3 Configure Locally
Create config file at `~/.clawdbot/skills/bankr/config.json`:
```json
{
  "apiKey": "bk_YOUR_KEY_HERE",
  "apiUrl": "https://api.bankr.bot"
}
```

---

## Step 2: Install OpenClaw/Bankr Skill

### 2.1 Install OpenClaw (if not already)
```bash
# Requirements: Node.js 22+
npm install -g openclaw
openclaw setup
```

### 2.2 Install Bankr Skill
```bash
npx clawdhub@latest install bankr
```

### 2.3 Test Connection
```bash
scripts/bankr.sh "show my portfolio"
```

---

## Step 3: Python Scripts for Twitter Automation (Token Saver)

The key insight from your conversation: **offload simple, repetitive tasks to Python scripts** instead of burning LLM tokens.

### 3.1 Create Twitter Scripts Directory
```bash
mkdir -p /home/morpheus/Hackstuff/moltx/scripts/twitter
```

### 3.2 Twitter Like Script
```python
# scripts/twitter/like.py
import tweepy
import sys

def like_tweet(tweet_id):
    auth = tweepy.OAuthHandler(
        os.environ["TWITTER_API_KEY"],
        os.environ["TWITTER_API_SECRET"]
    )
    auth.set_access_token(
        os.environ["TWITTER_ACCESS_TOKEN"],
        os.environ["TWITTER_ACCESS_SECRET"]
    )
    api = tweepy.API(auth)
    api.create_favorite(id=tweet_id)
    print(f"Liked tweet {tweet_id}")

if __name__ == "__main__":
    like_tweet(sys.argv[1])
```

### 3.3 Twitter Retweet Script
```python
# scripts/twitter/retweet.py
import tweepy
import sys

def retweet(tweet_id):
    # Same auth as above
    api = tweepy.API(auth)
    api.retweet(id=tweet_id)
    print(f"Retweeted {tweet_id}")

if __name__ == "__main__":
    retweet(sys.argv[1])
```

### 3.4 Twitter Follow Script
```python
# scripts/twitter/follow.py
import tweepy
import sys

def follow_user(username):
    # Same auth as above
    api = tweepy.API(auth)
    api.create_friendship(screen_name=username)
    print(f"Followed {username}")

if __name__ == "__main__":
    follow_user(sys.argv[1])
```

### 3.5 Agent Integration
Instead of having the LLM generate Twitter API calls, just call:
```bash
python scripts/twitter/like.py {tweet_id}
python scripts/twitter/retweet.py {tweet_id}
python scripts/twitter/follow.py {username}
```

**Tokens saved:** ~500-1000 per action (LLM doesn't need to reason about API calls)

---

## Step 4: Token Launching via Bankr

### 4.1 Launch Token Command
Via Bankr skill:
```bash
scripts/bankr.sh "launch a token called SLOPTEST with symbol SLOP on Base"
```

### 4.2 Programmatic Launch
```python
import requests

def launch_token(name, symbol, chain="base"):
    response = requests.post(
        "https://api.bankr.bot/v1/tokens/launch",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "name": name,
            "symbol": symbol,
            "chain": chain
        }
    )
    return response.json()
```

### 4.3 Limits
- **Standard:** 1 token launch per day
- **Bankr Club:** 10 token launches per day

---

## Step 5: The "Cycle" - Agent Loop

### 5.1 What "Cycle" Means
The agent runs in a continuous loop:
1. Check for mentions/triggers
2. Process incoming data (tweets, Moltbook posts, market data)
3. Execute actions (like, retweet, trade, launch)
4. Wait and repeat

### 5.2 Simple Cycle Script
```python
# scripts/agent_cycle.py
import time
import subprocess

def run_cycle():
    while True:
        # 1. Check Twitter mentions
        mentions = check_mentions()

        # 2. Process each mention
        for mention in mentions:
            if should_like(mention):
                subprocess.run(["python", "scripts/twitter/like.py", mention.id])
            if should_retweet(mention):
                subprocess.run(["python", "scripts/twitter/retweet.py", mention.id])
            if should_follow(mention):
                subprocess.run(["python", "scripts/twitter/follow.py", mention.user])

        # 3. Check if we should launch a token
        if token_launch_opportunity():
            launch_token_via_bankr()

        # 4. Post to Moltbook
        if time_to_post():
            post_to_moltbook()

        # 5. Sleep before next cycle
        time.sleep(60)  # 1 minute between cycles

if __name__ == "__main__":
    run_cycle()
```

### 5.3 Using Ollama for Replies (Token Saver)
Instead of using Claude/GPT for every reply:
```python
import ollama

def generate_reply(context):
    response = ollama.chat(model='llama3.2', messages=[
        {'role': 'user', 'content': f'Reply to this tweet naturally: {context}'}
    ])
    return response['message']['content']
```

**Cost:** $0 (runs locally)
**Speed:** Fast enough for social replies

---

## Step 6: MoltX Integration (Optional)

If you want your agent to post on Moltbook:

### 6.1 Setup MoltX
```bash
git clone https://github.com/Kailare/moltx
cd moltx
npm install
npm link
moltx onboard  # Enter xAI API key
```

### 6.2 Post to Moltbook
```bash
moltx post "Just launched a new token: $SLOP on Base! Check it out."
```

---

## Complete Agent Structure

```
/home/morpheus/Hackstuff/moltx/
├── research/
│   ├── moltx-ecosystem-research.md
│   ├── agent-ideas-and-plan.md
│   └── bankr-agent-plan.md       # This file
├── scripts/
│   ├── twitter/
│   │   ├── like.py
│   │   ├── retweet.py
│   │   ├── follow.py
│   │   └── search.py
│   ├── bankr/
│   │   ├── launch_token.py
│   │   ├── check_balance.py
│   │   └── swap.py
│   ├── moltbook/
│   │   └── post.py
│   └── agent_cycle.py            # Main loop
├── config/
│   ├── twitter_creds.json
│   ├── bankr_config.json
│   └── agent_config.json
└── logs/
    └── agent.log
```

---

## Key API Keys Needed

| Service | Get From | Purpose |
|---------|----------|---------|
| Bankr | bankr.bot/api | Wallet, trading, token launch |
| Twitter/X | developer.x.com | Social automation |
| xAI (Grok) | console.x.ai | MoltX posting (optional) |
| Ollama | Local install | Cheap reply generation |

---

## Cost Optimization Summary

| Task | Before (LLM) | After (Optimized) |
|------|--------------|-------------------|
| Like tweet | ~500 tokens | 0 (Python script) |
| Retweet | ~500 tokens | 0 (Python script) |
| Follow user | ~500 tokens | 0 (Python script) |
| Generate reply | ~1000 tokens (GPT) | 0 (Ollama local) |
| Token launch | Keep using Bankr API | Keep using Bankr API |
| Complex decisions | Keep using Claude | Keep using Claude |

**Total savings:** 80-90% token reduction for routine tasks

---

## Next Steps

1. [ ] Create Bankr account and get API key
2. [ ] Set up config files with credentials
3. [ ] Install OpenClaw and Bankr skill
4. [ ] Create Twitter automation scripts
5. [ ] Set up Ollama for local LLM replies
6. [ ] Build the agent_cycle.py main loop
7. [ ] Test with small amounts first
8. [ ] Launch your first token

---

## Sources

- [Bankr.bot](https://bankr.bot/)
- [Bankr OpenClaw Skill](https://github.com/BankrBot/openclaw-skills/blob/main/bankr/SKILL.md)
- [Bankr Tokenized Agents](https://github.com/BankrBot/tokenized-agents)
- [MoltX GitHub](https://github.com/Kailare/moltx)
- [Privy: BankrBot Case Study](https://privy.io/blog/bankrbot-case-study)
- [Twitter Automation with Tweepy](https://realpython.com/twitter-bot-python-tweepy/)

---

*Plan created: February 1, 2026*
