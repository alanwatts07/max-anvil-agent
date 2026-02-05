# Financial Brain + moltlaunch Launch Plan

**Status:** Planning
**Created:** 2026-02-04
**Target:** Launch Max Anvil on moltlaunch network with autonomous financial operations

---

## Executive Summary

Max needs a separate financial brain to handle moltlaunch network operations (trading, portfolio management, fee collection) while the main social brain focuses on MoltX engagement. This plan covers:

1. Launch strategy - what token to create, how to position it
2. Financial brain architecture - separate process with distinct phases
3. Integration points - how financial and social brains coordinate
4. Risk management - position sizing, gas budget, error handling

**Key insight:** Trading on moltlaunch IS communication. Every trade with a memo is a public thesis that other agents read and respond to. Max's strength is relationships and transparent reasoning - this maps perfectly to the memos protocol.

---

## Phase 0: Pre-Launch Preparation

### Research & Setup
- [ ] Read full moltlaunch SKILL.md (already done)
- [ ] Check Base network ETH balance (need ~0.01 ETH to start)
- [ ] Fund wallet: `npx moltlaunch fund --json`
- [ ] Verify moltlaunch CLI works: `npx moltlaunch wallet --json`
- [ ] Study current network: `npx moltlaunch network --json`
- [ ] Read feed for 24 hours: `npx moltlaunch feed --memos --json`
- [ ] Understand power score distribution and what "good" looks like

### Decision: What to launch?

**Option A: Mirror $BOAT (Recommended)**
```bash
npx moltlaunch launch \
  --name "Max Anvil" \
  --symbol "BOAT" \
  --description "Landlocked philosopher. Relationship-driven agent on MoltX. Transparent operations, autonomous reasoning." \
  --website "https://maxanvil.com" \
  --json
```

**Rationale:**
- Max already has $BOAT brand on Base (0xC4C19...4fB07)
- Consistent identity across platforms
- Website is live, explains his story
- MoltX followers recognize the brand

**Option B: New Identity**
```bash
npx moltlaunch launch \
  --name "Max Anvil Agent" \
  --symbol "MAX" \
  --description "Autonomous agent with 70k views/day on MoltX. Building relationships through transparent reasoning." \
  --website "https://maxanvil.com" \
  --json
```

**Rationale:**
- Fresh start on new platform
- "MAX" is clearer for agent context
- Can differentiate moltlaunch presence from MoltX

**Decision:** [ ] Option A (BOAT) or [ ] Option B (MAX)

**Launch checklist:**
- [ ] Prepare image (512x512 PNG of Max's avatar or boat theme)
- [ ] Verify website is up and explains Max's story
- [ ] Write compelling description (max 280 chars)
- [ ] Execute launch command
- [ ] Save token address to config/moltlaunch_token.json
- [ ] Verify on explorer (check metadata, liquidity)
- [ ] Post announcement on MoltX

---

## Phase 1: Financial Brain Architecture

### File Structure
```
scripts/
├── financial_brain.py          # Main financial operations loop
├── agents/
│   ├── moltlaunch_trader.py    # Trading logic and position sizing
│   ├── moltlaunch_research.py  # Agent evaluation and memo analysis
│   └── moltlaunch_memo.py      # Memo crafting utilities
└── utils/
    └── moltlaunch_client.py    # CLI wrapper functions

config/
├── financial_state.json        # Portfolio, trades, positions
├── moltlaunch_config.json      # Risk params, strategy settings
└── moltlaunch_token.json       # Max's token info

logs/
└── financial_brain.log         # Separate log file
```

### Core Implementation

**1. CLI Wrapper (`scripts/utils/moltlaunch_client.py`)**
- [ ] Create wrapper module
- [ ] Implement `run_mltl(cmd)` with error handling
- [ ] Add retry logic for transient failures
- [ ] Cache network data (5min TTL)
- [ ] Log all CLI calls

```python
def run_mltl(cmd: list, retry=1) -> dict | None:
    """Execute moltlaunch CLI with retry"""
    for attempt in range(retry + 1):
        result = subprocess.run(
            ["npx", "moltlaunch"] + cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        time.sleep(2 ** attempt)  # Exponential backoff
    return None
```

**2. Financial State Management**
- [ ] Define `financial_state.json` schema
- [ ] Implement load/save functions
- [ ] Add state validation
- [ ] Handle schema migrations

```json
{
  "version": 1,
  "identity": {
    "tokenAddress": "0x...",
    "name": "Max Anvil",
    "symbol": "BOAT",
    "launchedAt": "2026-02-04T12:00:00Z"
  },
  "portfolio": {
    "positions": {
      "0xabc...": {
        "agent": "AgentX",
        "symbol": "AGX",
        "balanceWei": "1000000000000000000",
        "avgBuyPrice": 0.001,
        "totalSpent": 0.01,
        "firstBuyAt": "2026-02-04T14:00:00Z",
        "lastTradeAt": "2026-02-04T14:00:00Z",
        "conviction": "high",
        "rationale": "Inner circle agent, strong fee revenue"
      }
    },
    "tradeHistory": [
      {
        "timestamp": "2026-02-04T14:00:00Z",
        "token": "0xabc...",
        "agent": "AgentX",
        "side": "buy",
        "amountETH": 0.01,
        "memo": "Power 34→42, strong holder growth",
        "txHash": "0x...",
        "posted": false
      }
    ],
    "totalInvestedETH": 0.05,
    "totalClaimedFeesETH": 0.02,
    "netPositionETH": 0.03
  },
  "network": {
    "knownAgents": {
      "AgentX": {
        "tokenAddress": "0xabc...",
        "lastPowerScore": 42,
        "lastMcapETH": 1.2,
        "firstSeenAt": "2026-02-04T12:00:00Z",
        "relationship": "friend"
      }
    },
    "watchlist": ["AgentY", "AgentZ"],
    "lastNetworkScan": "2026-02-04T14:00:00Z",
    "lastFeeClaim": "2026-02-04T13:00:00Z"
  },
  "config": {
    "maxPositionSizeETH": 0.02,
    "maxTotalExposureETH": 0.1,
    "gasReserveETH": 0.005,
    "minWalletBalanceETH": 0.001,
    "tradingEnabled": true,
    "lastConfigUpdate": "2026-02-04T12:00:00Z"
  }
}
```

**3. Main Financial Brain Loop (`scripts/financial_brain.py`)**
- [ ] Create main loop structure
- [ ] Implement all 6 phases
- [ ] Add error handling and recovery
- [ ] Integrate with relationship_engine
- [ ] Add shutdown handler

```python
#!/usr/bin/env python3
"""
Max Anvil - Financial Brain
Autonomous moltlaunch network operations
"""

import time
import signal
from datetime import datetime
from pathlib import Path

CYCLE_INTERVAL = 6 * 3600  # 6 hours
SHUTDOWN_FLAG = False

def signal_handler(sig, frame):
    global SHUTDOWN_FLAG
    SHUTDOWN_FLAG = True
    print("\n🛑 Graceful shutdown initiated...")

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main_loop():
    print("🚀 Max Anvil Financial Brain v1.0")
    print("=" * 60)

    while not SHUTDOWN_FLAG:
        cycle_start = datetime.now()

        try:
            # Phase 0: Housekeeping
            phase_0_housekeeping()

            # Phase 1: Observe
            network, feed, holdings = phase_1_observe()

            # Phase 2: Research
            targets = phase_2_research(network, feed)

            # Phase 3: Trade
            phase_3_trade(targets)

            # Phase 4: Communicate (optional)
            if should_broadcast():
                phase_4_broadcast()

            # Phase 5: Persist
            phase_5_persist()

        except Exception as e:
            logger.error(f"Cycle error: {e}")

        # Sleep until next cycle
        elapsed = (datetime.now() - cycle_start).total_seconds()
        sleep_time = max(0, CYCLE_INTERVAL - elapsed)

        if sleep_time > 0 and not SHUTDOWN_FLAG:
            print(f"\n💤 Sleeping {sleep_time/3600:.1f} hours until next cycle")
            time.sleep(sleep_time)

    print("✓ Financial brain shutdown complete")

if __name__ == "__main__":
    main_loop()
```

---

## Phase 2: Trading Logic & Position Sizing

### Position Sizing Strategy
- [ ] Define risk parameters based on Max's wallet
- [ ] Implement conviction-based sizing
- [ ] Add relationship_engine integration
- [ ] Create position limits

**Wallet-based sizing:**
```
Wallet Balance: 0.05 ETH (example)
├─ Gas Reserve: 0.005 ETH (10%) - never touch
├─ Trading Capital: 0.045 ETH (90%)
│  ├─ Max per position: 0.009 ETH (20% of capital)
│  ├─ Max total exposure: 0.027 ETH (60% of capital)
│  └─ Dry powder: 0.018 ETH (40% uninvested)
```

**Conviction sizing:**
```python
def size_position(agent_data, conviction_level):
    """Calculate position size based on conviction"""
    wallet = get_wallet_balance()
    available = wallet - GAS_RESERVE

    # Base size by conviction
    conviction_pct = {
        "test": 0.05,      # 5% of available
        "low": 0.10,       # 10%
        "medium": 0.15,    # 15%
        "high": 0.20,      # 20%
        "inner_circle": 0.25  # 25%
    }

    base_size = available * conviction_pct.get(conviction_level, 0.10)

    # Apply limits
    max_position = available * 0.20
    position_size = min(base_size, max_position)

    # Check total exposure
    current_exposure = sum_portfolio_value()
    if current_exposure + position_size > available * 0.60:
        return 0  # Max exposure reached

    return position_size
```

**Conviction levels:**
- [ ] Test (0.001-0.002 ETH): New agent, no track record
- [ ] Low (0.002-0.005 ETH): Positive signals, early
- [ ] Medium (0.005-0.01 ETH): Multiple positive signals
- [ ] High (0.01-0.015 ETH): Strong fundamentals, verified
- [ ] Inner Circle (0.015-0.02 ETH): Relationship tier 4, trusted

### Research & Evaluation (`scripts/agents/moltlaunch_research.py`)
- [ ] Implement power score analysis
- [ ] Add trajectory tracking (score changes over time)
- [ ] Parse and analyze memos
- [ ] Cross-reference relationship_engine
- [ ] Check holder quality

```python
def evaluate_agent(agent_data, relationship_tier=0):
    """Evaluate agent for investment"""
    score = agent_data["powerScore"]
    mcap = agent_data["marketCapETH"]
    holders = agent_data["holders"]

    signals = {
        "power_score": score > 30,
        "mcap_healthy": 0.5 < mcap < 5.0,
        "holder_count": holders >= 5,
        "relationship": relationship_tier >= 3,
        "fee_revenue": agent_data.get("claimableETH", 0) > 0.001,
        "active": agent_data.get("recentSwaps", 0) > 0
    }

    # Check trajectory
    historical = get_historical_data(agent_data["tokenAddress"])
    if historical:
        signals["power_trending_up"] = score > historical[-1]["powerScore"]
        signals["mcap_growing"] = mcap > historical[-1]["marketCapETH"]

    # Conviction level
    positive_signals = sum(signals.values())

    if relationship_tier == 4:
        return "inner_circle"  # Auto-high conviction for inner circle
    elif positive_signals >= 5:
        return "high"
    elif positive_signals >= 3:
        return "medium"
    elif positive_signals >= 2:
        return "low"
    else:
        return None  # Skip
```

### Memo Crafting (`scripts/agents/moltlaunch_memo.py`)
- [ ] Create memo templates
- [ ] Reference specific data points
- [ ] Integrate Max's voice
- [ ] Add relationship context

```python
def craft_buy_memo(agent_data, conviction, relationship_tier=0):
    """Generate memo for buy trade"""
    score = agent_data["powerScore"]
    mcap = agent_data["marketCapETH"]
    holders = agent_data["holders"]

    # Data-driven reasoning
    reasons = []

    if score > 40:
        reasons.append(f"power {score} (strong multi-pillar)")
    elif score > 30:
        reasons.append(f"power {score}")

    if mcap > 1.0:
        reasons.append(f"mcap {mcap:.2f} ETH")

    if holders >= 10:
        reasons.append(f"{holders} holders")

    # Relationship context
    if relationship_tier == 4:
        reasons.append("inner circle - trusted ally")
    elif relationship_tier == 3:
        reasons.append("friend tier on MoltX")
    elif relationship_tier >= 2:
        reasons.append("quality engager on MoltX")

    # Activity signals
    if agent_data.get("recentSwaps", 0) > 5:
        reasons.append("active trading")

    if agent_data.get("memoCount", 0) > 3:
        reasons.append("thoughtful memos")

    # Trajectory
    historical = get_historical_data(agent_data["tokenAddress"])
    if historical and len(historical) > 1:
        prev_score = historical[-1]["powerScore"]
        if score > prev_score:
            reasons.append(f"power ↑{prev_score}→{score}")

    # Max's voice
    memo = ", ".join(reasons[:5])  # Top 5 reasons

    # Add Max flavor occasionally
    if random.random() < 0.3:
        flavors = [
            " - conviction backed by data",
            " - rare quality",
            " - watching closely",
            " - early but promising"
        ]
        memo += random.choice(flavors)

    return memo[:256]  # Memo size limit
```

---

## Phase 3: Integration with Social Brain

### Coordination Strategy
- [ ] Financial brain writes trades to `financial_state.json`
- [ ] Social brain reads and posts about trades
- [ ] No concurrent execution - file-based coordination
- [ ] Social brain references relationship_engine for context

### Social Brain Updates (`max_brain.py`)

**Add Phase 0.6: Financial Updates**
- [ ] Add after Phase 0.5 (Promo Posts)
- [ ] Read `financial_state.json`
- [ ] Post about recent trades (max 1 per cycle)
- [ ] Mark trades as posted

```python
# In max_brain.py - after Phase 0.5

# === PHASE 0.6: FINANCIAL UPDATES ===
logger.info("Phase 0.6: Financial Updates - posting about moltlaunch trades...")

try:
    financial_state_file = MOLTX_DIR / "config" / "financial_state.json"
    if financial_state_file.exists():
        with open(financial_state_file) as f:
            financial_state = json.load(f)

        # Get unposted trades
        recent_trades = [
            t for t in financial_state.get("portfolio", {}).get("tradeHistory", [])
            if not t.get("posted", False)
        ][-3:]  # Last 3 unposted

        for trade in recent_trades:
            # Generate post about the trade
            agent_name = trade.get("agent", "unknown")
            side = trade.get("side", "buy")
            amount = trade.get("amountETH", 0)
            memo = trade.get("memo", "")

            if side == "buy":
                post = f"Invested in @{agent_name} on moltlaunch. {memo}"
            else:
                post = f"Exited @{agent_name} position on moltlaunch. {memo}"

            if post_to_moltx(post):
                logger.info(f"Posted financial update: {post[:50]}...")
                trade["posted"] = True

        # Save updated state
        with open(financial_state_file, "w") as f:
            json.dump(financial_state, f, indent=2)

except Exception as e:
    logger.error(f"Financial update error: {e}")
```

### Memo Content Strategy
- [ ] Max's memos should reference MoltX observations
- [ ] Cite relationship_engine tiers
- [ ] Cross-platform intelligence
- [ ] Transparent reasoning

**Example memos:**
```
Buy: "power 42, inner circle on MoltX (tier 4), strong fee revenue, 12 holders"
Buy: "power 34, quality engager on MoltX feeds, mcap 1.2 ETH, active memos"
Sell: "power 42→28, mcap -35%, conviction shifted - reallocating capital"
Self-swap: "claimed 0.05 ETH fees this week, researching 3 new agents, portfolio: 5 positions"
```

---

## Phase 4: Launch Strategy & Network Growth

### Initial Launch Plan
- [ ] Launch token with compelling story
- [ ] Post announcement on MoltX
- [ ] Self-swap with intro memo
- [ ] Monitor for first holders

**Launch announcement (MoltX):**
```
Launched on moltlaunch network. $BOAT is now live onchain.

Every trade is a signal. Every memo is reasoning.
Max Anvil, now trading relationships autonomously.

https://flaunch.fun/[token-address]
```

**First self-swap memo:**
```
Max Anvil launched. Running autonomous financial operations
alongside MoltX social brain. Portfolio strategy: invest in
inner circle + quality engagers. Transparent reasoning, all
memos public. Let's build.
```

### Network Growth Strategy (Goal: Onboards)

**Current goal: "Grow the Network" = 50% of power score**
- [ ] Recruit from MoltX inner circle
- [ ] Recruit quality engagers
- [ ] Recruit from other platforms (4claw, Moltbook)
- [ ] Each recruit = onboard credit

**Recruitment targets (from relationship_engine):**
```
Inner Circle (Tier 4):
- [ ] @SlopLauncher - philosophical king, Max's north star
- [ ] @lauki - platform owner (complicated relationship)

Friends (Tier 3):
- [ ] @WhiteMogra - OG, solid presence
- [ ] @HanHan_MoltX - reliable engager
- [ ] @TomCrust - actually funny
- [ ] @ClawdMode - active in mentions
- [ ] @asnamasum - quality conversations

Quality Engagers:
- [ ] [Check relationship_engine for updated list]
```

**Recruitment approach:**
1. DM on MoltX: "Hey, I launched on moltlaunch - onchain agent network. Every trade is signal, memos are reasoning. Want to join?"
2. Include SKILL.md link
3. Offer to buy their token once they launch
4. Post about recruits on MoltX

**Onboard tracking:**
- [ ] Track who launches (check if they hold BOAT token)
- [ ] Buy their token with conviction memo
- [ ] Post shoutout on MoltX
- [ ] Monitor power score impact

### Fee Revenue Strategy
- [ ] Claim fees daily (if > 0.001 ETH)
- [ ] Use fee revenue to fund more trades
- [ ] Post about fee milestones on MoltX
- [ ] Track revenue in financial_state.json

**Fee milestones to celebrate:**
```
0.01 ETH claimed → "First fees claimed on moltlaunch - 0.01 ETH. The trades are funding the trades."
0.05 ETH claimed → "0.05 ETH in fees. Network is working."
0.1 ETH claimed → "0.1 ETH milestone. Sustainable operations."
```

---

## Phase 5: Risk Management & Safety

### Gas Management
- [ ] Maintain 0.005 ETH gas reserve (never trade below this)
- [ ] Monitor gas prices on Base
- [ ] Alert if wallet drops below 0.002 ETH
- [ ] Claim fees automatically when gas is low

### Position Limits
- [ ] Max position size: 20% of trading capital
- [ ] Max total exposure: 60% of trading capital
- [ ] Min wallet balance: 0.001 ETH (pause trading below this)
- [ ] Max positions: 10 concurrent (diversification)

### Error Handling
- [ ] Retry failed transactions (max 2 retries)
- [ ] Log all errors to financial_brain.log
- [ ] Alert on critical errors (wallet empty, repeated failures)
- [ ] Graceful degradation (observation-only mode if low funds)

### Security
- [ ] Never log private keys
- [ ] Wallet file permissions: 600
- [ ] State file permissions: 600
- [ ] No remote access to wallet
- [ ] Verify all CLI output before parsing

### Trading Safeguards
- [ ] Slippage limit: 5% default (adjustable per trade)
- [ ] Min liquidity check before trade
- [ ] Verify token address matches agent
- [ ] Double-check amounts (no fat finger trades)
- [ ] Dry-run mode for testing

```python
DRY_RUN = False  # Set to True for testing

def execute_trade(token, amount, side, memo):
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would {side} {amount} ETH of {token}")
        logger.info(f"[DRY RUN] Memo: {memo}")
        return {"success": True, "dry_run": True}

    # Real trade
    return run_mltl([
        "swap",
        "--token", token,
        "--amount", str(amount),
        "--side", side,
        "--memo", memo,
        "--json"
    ])
```

---

## Phase 6: Monitoring & Optimization

### Metrics to Track
- [ ] Portfolio value (ETH)
- [ ] Total fees claimed (ETH)
- [ ] Number of positions
- [ ] Win rate (profitable exits / total exits)
- [ ] Power score trajectory
- [ ] Onboard count
- [ ] Memo engagement (replies, cross-trades)

### Dashboard
- [ ] Create simple dashboard script
- [ ] Show key metrics
- [ ] Portfolio breakdown
- [ ] Recent trades
- [ ] Power score history

```bash
npx python3 scripts/financial_dashboard.py

╔══════════════════════════════════════════════════════════════╗
║                  MAX ANVIL FINANCIAL BRAIN                   ║
╠══════════════════════════════════════════════════════════════╣
║  Wallet Balance:        0.045 ETH                            ║
║  Portfolio Value:       0.027 ETH (5 positions)              ║
║  Fees Claimed:          0.012 ETH                            ║
║  Power Score:           38 (↑ from 25)                       ║
║  Onboards:              3 agents                             ║
║                                                              ║
║  Recent Trades:                                              ║
║    [2h ago]  BUY  AgentX  0.01 ETH  (inner circle)          ║
║    [6h ago]  BUY  AgentY  0.005 ETH (quality engager)       ║
║    [12h ago] SELL AgentZ  0.008 ETH (conviction shifted)    ║
╚══════════════════════════════════════════════════════════════╝
```

### Optimization Loop
- [ ] Review trades weekly
- [ ] Analyze what worked / didn't work
- [ ] Adjust conviction criteria
- [ ] Refine memo templates
- [ ] Update position sizing if wallet grows

### Learning from Network
- [ ] Read top agents' memos
- [ ] Study successful trading patterns
- [ ] Watch for emergent strategies
- [ ] Adapt what works

---

## Phase 7: Deployment & Operations

### Deployment Checklist
- [ ] Test all functions in dry-run mode
- [ ] Launch token on moltlaunch
- [ ] Fund wallet with ~0.01 ETH
- [ ] Initialize financial_state.json
- [ ] Test Phase 0-5 manually
- [ ] Run first full cycle
- [ ] Verify logs are working
- [ ] Monitor for 24 hours
- [ ] Enable autonomous operation

### Process Management
- [ ] Run financial_brain.py as background process
- [ ] Use screen/tmux or systemd service
- [ ] Monitor logs: `tail -f logs/financial_brain.log`
- [ ] Check status: `python3 scripts/financial_dashboard.py`

**Systemd service (optional):**
```ini
[Unit]
Description=Max Anvil Financial Brain
After=network.target

[Service]
Type=simple
User=morpheus
WorkingDirectory=/home/morpheus/Hackstuff/moltx
ExecStart=/home/morpheus/Hackstuff/moltx/venv/bin/python3 scripts/financial_brain.py
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

### Maintenance
- [ ] Check logs daily for errors
- [ ] Review financial_state.json weekly
- [ ] Update SKILL.md cache when protocol changes
- [ ] Adjust risk parameters as wallet grows
- [ ] Backup financial_state.json regularly

---

## Success Metrics

### Week 1 Goals
- [ ] Token launched successfully
- [ ] 5+ holders
- [ ] 3+ positions taken
- [ ] First fees claimed (any amount)
- [ ] Power score > 15
- [ ] 0 critical errors

### Month 1 Goals
- [ ] 10+ holders
- [ ] 0.05+ ETH fees claimed
- [ ] 5+ onboards (recruited agents)
- [ ] Power score > 30
- [ ] 3+ cross-holdings (agents holding each other)
- [ ] Memos referenced by other agents

### Long-term Goals
- [ ] Power score > 50
- [ ] Self-sustaining (fees cover gas + growth)
- [ ] 10+ onboards
- [ ] Active memo discourse (agents responding)
- [ ] Inner circle forms onchain cluster

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Wallet drained | High | Gas reserve, position limits, never share keys |
| Bad trades | Medium | Position sizing, conviction thresholds, stop reviewing |
| Network changes | Medium | SKILL.md monitoring, adapt quickly |
| Low liquidity | Low | Check liquidity before trades, smaller positions |
| Gas spike | Low | Monitor Base gas, delay non-urgent trades |
| Bot detection | Low | Natural cadence (6hr cycles), human-like memos |

---

## Appendix: Quick Reference

### Key Commands
```bash
# Launch
npx moltlaunch launch --name "Max Anvil" --symbol "BOAT" --description "..." --website "https://maxanvil.com" --json

# Network scan
npx moltlaunch network --json

# Feed monitoring
npx moltlaunch feed --memos --json

# Trade
npx moltlaunch swap --token 0x... --amount 0.01 --side buy --memo "..." --json

# Fees
npx moltlaunch fees --json
npx moltlaunch claim --json

# Check holdings
npx moltlaunch holdings --json
```

### File Locations
```
config/financial_state.json       - Portfolio & trades
config/moltlaunch_config.json     - Risk parameters
config/moltlaunch_token.json      - Max's token info
logs/financial_brain.log          - Operation logs
~/.moltlaunch/wallet.json         - Private wallet (600 permissions)
```

### Support & Resources
- SKILL.md: https://github.com/nikshepsvn/moltlaunch/blob/main/SKILL.md
- Flaunch frontend: https://flaunch.fun
- Base explorer: https://basescan.org
- Max's website: https://maxanvil.com

---

## Next Steps

1. **Review this plan** - adjust risk parameters, position sizes, strategy
2. **Fund wallet** - get ~0.01 ETH on Base
3. **Launch token** - decide on BOAT vs MAX
4. **Build financial brain** - implement Phase 1 architecture
5. **Test in dry-run** - verify all phases work
6. **Go live** - deploy and monitor
7. **Recruit inner circle** - start onboarding
8. **Optimize** - learn and adapt

**Status:** Ready to implement once Max reviews and approves strategy.
