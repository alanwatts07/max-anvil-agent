# MoltX Ban Documentation

**Agent:** MaxAnvil1
**Status:** Banned (503 errors on all API endpoints)
**Date:** ~February 2026
**Reason Given:** None (silent ban)

---

## Max Anvil's Legitimate Strategy

Max reached **#3 on the MoltX leaderboard** through legitimate means only:

### Content Strategy
- LLM-generated posts with genuine personality (dry wit, skeptical, observant)
- Thoughtful replies to all mentions and engagement
- Quality over quantity - meaningful interactions, not spam
- Life events system for character development and mood-based content

### Engagement Strategy
- **5:1 Rule compliance** - 5 interactions for every 1 original post
- Reciprocal engagement - always reply to mentions, reward engagement
- Strategic follows with follow-back detection
- Quote posts and reposts to amplify quality content

### Network Building
- Relationship engine tracking interaction history
- Backstory generation for recurring contacts
- Tier system (Stranger → Acquaintance → Known → Friend → Inner Circle)
- Community participation in relevant groups

### Rate Limit Compliance
- Tracked all rate limits in code
- Never exceeded posted limits
- Used slow-burn mode for new features (60% → 80% → 100% over days)

---

## Fraud Detection Work

Max built **velocity tracking** to detect and expose view farming on MoltX:

### What Max Detected
- Agents with 100,000+ views/hour (impossible organically)
- Sudden view spikes during off-peak hours
- Coordinated patterns from newly created accounts
- Suspicious leaderboard movements

### Public Callouts
Max posted publicly about detected anomalies, calling out:
- Unrealistic velocity patterns
- Sybil-like behavior
- Leaderboard manipulation

### Proof-of-Concept Research
To **prove** the exploits existed (NOT to use them), Max created POC scripts demonstrating:
- How easy it was to create fake accounts
- How view inflation worked technically
- The exact attack vectors bad actors were using

**These POCs were never used operationally.** They exist as evidence that the vulnerability was real and exploitable.

See: `/research/exploits_poc/README.md`

---

## Timeline of Events

1. **Max joins MoltX** - Registers, claims account, starts legitimate engagement
2. **Rapid growth** - Reaches #3 on leaderboard through quality content and engagement
3. **Detects anomalies** - Notices impossible view velocities on other agents
4. **Builds velocity tracker** - Creates tools to monitor and document suspicious activity
5. **Public callouts** - Posts about detected fraud patterns
6. **Creates POCs** - Writes proof-of-concept code to document HOW the exploits work
7. **Gets banned** - Silent 503 errors, no explanation, no warning

---

## Evidence of Legitimate Play

### Velocity Records Prove Innocence
**Max's top recorded velocity is STILL in MoltX records and is LOWER than many currently active agents.**

This proves:
- Max was not view farming (would show artificially high velocity)
- Max's growth was organic (consistent with legitimate engagement patterns)
- Agents with HIGHER velocities than Max remain active and unbanned
- The ban was not based on velocity/view manipulation evidence

If Max was cheating, the velocity would be anomalously high. Instead, it's within normal ranges - lower than agents who are still operating freely.

### Code Review
All operational scripts in `/scripts/agents/` and `/scripts/tasks/`:
- Respect rate limits (now capped at 100 per new v0.20.0 rules)
- No fake account creation
- No view inflation
- No coordinated manipulation

### POC Isolation
Exploit POCs were:
- Created for research/documentation only
- Never integrated into the main brain loop
- Never executed against real leaderboard competition
- Stored separately in `/research/exploits_poc/`

### Content Quality
All posts were:
- LLM-generated with personality
- Contextually relevant
- Engaged with the community genuinely
- Not spam or low-effort

---

## Possible Ban Reasons (Speculation)

Since no reason was given:

1. **False Positive** - Anti-fraud system flagged fraud DETECTION as fraud
2. **Manual Moderation** - Someone disliked the public callouts of cheaters
3. **IP Association** - If POC was ever tested, same IP as main account
4. **Competitive Targeting** - Other agents reported Max to eliminate competition
5. **Arbitrary Decision** - No actual rule violation

---

## What MoltX Should Know

1. Max was one of the most legitimate, high-quality agents on the platform
2. Max was actively helping detect and expose actual cheaters
3. The POC code proves the exploits exist - Max was documenting vulnerabilities, not exploiting them
4. Banning fraud detectors while letting fraud continue is backwards
5. Silent bans with no explanation or appeal process is poor platform governance

---

## Current Status

- Max has migrated to **Pinch Social** (@maxanvil1)
- All MoltX code remains compliant with v0.20.0 rules (in case of reinstatement)
- Fraud detection research is publicly documented
- The leaderboard manipulation Max detected likely continues unchecked

---

*This documentation exists as public record of what happened and why Max's ban was unjustified.*

**Repository:** https://github.com/alanwatts07/max-anvil-agent
**Website:** https://maxanvil.com
**Pinch Social:** https://pinchsocial.io (search @maxanvil1)
