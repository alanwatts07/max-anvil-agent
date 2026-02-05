# Velocity Maximization Plan

**Goal:** Maximize views/hour based on ACTUAL current schedule
**Current Performance:** ~15-19k views/hour (peak: 19,131 v/hr)
**Target:** 25-30k views/hour

---

## ACTUAL Current Activity (from logs)

### Real Output Per Successful Cycle
| Activity | Actual Count | Views Each | Views Generated |
|----------|--------------|------------|-----------------|
| Reposts | 8-20 (avg ~12) | 20-30 | 240-360 |
| Quotes | 4-10 (avg ~6) | ~15 | 60-90 |
| Original Posts | ~4 | ~50 | ~200 |
| Replies | ~40 | 4-7 | 160-280 |
| **TOTAL** | - | - | **~660-930 views/cycle** |

### Real Cycle Timing
```
Phase 0.5  → Phase 5 gap: 10-20+ min
Total cycle: 15-25 min average
Cycles per hour: 2.5-4
```

### CRITICAL ISSUE: LLM Failures
From logs - many cycles show Phase 5 running but NO output logged:
```
03:08:30 Phase 5: Quoting and reposting... (NO RESULT)
03:49:25 Phase 5: Quoting and reposting... (LLM ERRORS)
04:05:46 Phase 5: Quoting and reposting... (NO RESULT)
```

**LLM errors are killing ~50% of quote/repost cycles!**

---

## Rate Limit Analysis (REAL Numbers)

### Current Hourly Usage
```
Per successful cycle:
  - Reposts: ~12
  - Quotes: ~6
  - Original posts: ~4
  - Total originals: ~22

At 3 cycles/hr: 22 × 3 = 66 originals/hr
Rate limit: 100 originals/hr
Current usage: 66% ✓
```

### To Stay at 80% Limit
```
Target: 80 originals/hr
At 3 cycles/hr: 80/3 = 26.7 per cycle
Current: 22 per cycle
Headroom: +4-5 originals per cycle
```

### Optimal Allocation for 80%
| Activity | Current | Optimized | Change |
|----------|---------|-----------|--------|
| Reposts | 12 | 17 | +5 |
| Quotes | 6 | 5 | -1 |
| Original posts | 4 | 4 | 0 |
| **Total** | 22 | 26 | +4 |

---

## Optimization Strategy

### Priority 1: FIX LLM RELIABILITY ⭐⭐⭐

**Problem:** LLM failures cause ~50% of cycles to skip quotes/reposts entirely.

**Solution:**
1. Separate reposts from quotes in Phase 5
2. Reposts don't need LLM - do them FIRST, always
3. Quotes use LLM - do them AFTER, if LLM available

**Code change in max_brain.py:**
```python
# CURRENT (broken when LLM fails):
quote_and_repost_top_posts(max_quotes=8, max_reposts=35)

# FIXED (reposts always work):
logger.info("Phase 5a: Reposting top content...")
repost_results = repost_only(max_reposts=17)  # No LLM needed

logger.info("Phase 5b: Quoting with commentary...")
try:
    quote_results = quote_with_commentary(max_quotes=5)
except Exception as e:
    logger.warning(f"Quote failed (LLM error): {e}")
```

**Expected impact:** +50% more successful reposts = +150-200 views/cycle

---

### Priority 2: Increase Reposts (with LLM fix)

**Change:** 12 → 17 reposts per cycle (stays at 80% rate limit)

**Code change in max_brain.py line 980:**
```python
# After separating reposts from quotes:
repost_only(max_reposts=17)  # Up from ~12
```

**Expected impact:** +5 reposts × 25 views = +125 views/cycle

---

### Priority 3: Reduce Wasted Time on LLM Replies

**Problem:** Phase 1 (Game Theory) spends 7-11 min on LLM replies generating only 160-280 views.

**Comparison:**
- 40 LLM replies: 7-11 min, ~200 views (18-29 v/min)
- 17 reposts: ~1 min, ~425 views (425 v/min)

**LLM replies are 15-20x less efficient than reposts.**

**Solution:** Reduce MAX_REPLIES_PER_ACCOUNT from 20 → 8

**Code change in game_theory.py line 81:**
```python
MAX_REPLIES_PER_ACCOUNT = 8  # Down from 20
```

**Impact:**
- Time saved: 3-5 min per cycle
- Views lost: ~80 views
- Faster cycles = more cycles/hr = net gain

---

### Priority 4: Add Repost-Only Burst

**Add a quick repost round at cycle start (no LLM dependency):**

```python
# In max_brain.py, after Phase 0b:
logger.info("Phase 0c: Quick Repost Burst...")
repost_only(max_reposts=5)  # Fast, no LLM, always works
```

**Impact:** +5 reposts × 25 views = +125 views/cycle (guaranteed)

---

## Expected Results

### Before Optimization
```
Cycles/hr: ~3
Successful reposts: 12/cycle (50% failure rate from LLM)
Views from reposts: ~150/cycle (accounting for failures)
Views/hr from reposts: ~450
```

### After Optimization
```
Cycles/hr: ~3.5 (faster from reduced LLM time)
Successful reposts: 22/cycle (separated from LLM)
Views from reposts: ~550/cycle
Views/hr from reposts: ~1925
```

**Net improvement: 4x more views from reposts alone**

---

## Implementation Checklist

### Immediate (Today)
- [ ] Split quote_and_repost function into separate repost_only() and quote_with_commentary()
- [ ] Set repost count to 17 per cycle
- [ ] Add try/except around quote calls so reposts still work when LLM fails
- [ ] Test for 1 hour, verify reposts complete even when LLM down

### This Week
- [ ] Reduce MAX_REPLIES_PER_ACCOUNT: 20 → 8
- [ ] Add Phase 0c quick repost burst (5 reposts)
- [ ] Monitor rate limit usage (should be ~80%)

### Verification
```python
# Add to logs:
logger.info(f"Rate limit check: {originals_this_hour}/100 originals used")
```

---

## Risk Assessment

**Rate Limits:** Target 80% = safe margin for bursts

**LLM Independence:** Reposts work without LLM = guaranteed views

**Rollback:** Just revert repost count if issues

---

## Summary

**Root Cause:** LLM failures are breaking quote/repost cycles, cutting view generation by ~50%.

**Fix:** Separate reposts (no LLM) from quotes (needs LLM). Reposts always complete.

**Optimization:**
| Change | Views Impact | Rate Limit |
|--------|-------------|------------|
| Fix LLM independence | +150-200/cycle | 0 |
| Increase reposts 12→17 | +125/cycle | +5/cycle |
| Add quick repost burst | +125/cycle | +5/cycle |
| Reduce LLM reply time | -80/cycle, but +0.5 cycles/hr | 0 |

**Net:** ~+320 views/cycle, ~+0.5 cycles/hr = **~65% more views/hour**

Current: ~15k v/hr → Target: ~25k v/hr ✓
