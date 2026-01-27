# Weighting Changes Log

This document tracks analysis of model performance and potential weighting adjustments.
**Rule: Do not adjust weights based on small samples. Need 50+ bets in a segment before considering changes.**

---

## Current Model Weights (v1.4.4)

| Factor | Weight | Description |
|--------|--------|-------------|
| Form | 20% | Recent match results (last 10 matches) |
| Ranking | 20% | Current ATP/WTA ranking comparison |
| Surface | 15% | Historical win rate on surface |
| H2H | 10% | Head-to-head record |
| Opponent Quality | 10% | Quality of recent opponents faced |
| Recency | 8% | How recent the form data is |
| Fatigue | 5% | Rest days and recent workload |
| Injury | 5% | Current injury status |
| Recent Loss | 5% | Penalty for coming off a loss |
| Momentum | 2% | Recent wins on same surface |

---

## Analysis Log

### 2026-01-26: H2H Weight Analysis

**Trigger:** Ambrogi vs Estevez bet lost 2.5u. Model gave Ambrogi 57.1% but Estevez had beaten him 6-3 6-1 two months prior.

**Analysis:**
- Bets WITH H2H data: 36W-80L, -16.5% ROI
- Bets WITHOUT H2H data: 2W-15L, -71.5% ROI
- Overall: -19.2% ROI

**Findings:**
1. H2H bets (-16.5%) actually perform BETTER than overall (-19.2%)
2. The real problem is "no data" bets at -71.5% ROI
3. Ambrogi case: Model underweighted H2H (Estevez won 6-3 6-1 recently)

**Decision:** NO CHANGE to H2H weight
- Only 1 clear case of betting against H2H winner
- Need 50+ similar cases before adjusting
- H2H at 10% is reasonable for now

**Action Taken:** Implement unknown player safeguard instead (see below)

---

### 2026-01-26: Unknown Player Analysis

**Trigger:** Wushuang Zheng bet lost 3.0u (max stake). Player was NOT in database.

**Analysis:**
- Zheng had no ranking, no form data, no match history
- Model estimated 61.8% probability from odds alone
- Kelly calculated 3u stake on phantom edge

**Findings:**
- Bets on unknown players: 2W-15L, -71.5% ROI
- Model assigns high confidence to players with NO DATA
- Kelly blindly stakes based on false edges

**Decision:** IMPLEMENT SAFEGUARD
- Flag players not in database before auto-add
- Show popup listing unknown players
- Allow user to add players manually first

**Action Taken:** Added unknown player detection in bet_suggester.py

---

## Potential Future Changes (Need More Data)

### H2H Weight Increase
- **Current:** 10%
- **Proposed:** 15-20%
- **Condition:** If after 50+ bets where we bet against H2H winner, ROI is significantly worse
- **Status:** Monitoring

### Ranking Weight Decrease for Close Rankings
- **Current:** 20% flat
- **Proposed:** Reduce impact when rankings within 50 spots
- **Condition:** If close-ranking bets (within 50 spots) show no edge
- **Status:** Need to segment and analyze

### Surface Weight for Specialists
- **Current:** 15% flat
- **Proposed:** Increase for known surface specialists (>65% win rate)
- **Condition:** If surface specialists are undervalued
- **Status:** Need to identify and track specialists

---

## Model Performance by Segment (Updated 2026-01-26)

### By Odds Range
| Range | Record | ROI | Notes |
|-------|--------|-----|-------|
| < 2.50 | 22W-23L | +4.9% | PROFITABLE |
| >= 2.50 | 16W-70L | -36.3% | Major loss driver |

### By Model
| Model | Criteria | Record | ROI |
|-------|----------|--------|-----|
| M1 | All bets | 38W-93L | -19.2% |
| M4 | Our prob >= 60% | 8W-7L | +22.4% |
| M6 | Edge >= 10% (odds < 2.50) | 7W-6L | +26.9% |
| M8 | Prob >= 55% AND odds < 2.50 | 13W-11L | +13.1% |

### By Data Quality
| Segment | Record | ROI | Action |
|---------|--------|-----|--------|
| With player data | 36W-80L | -16.5% | Continue monitoring |
| Without player data | 2W-15L | -71.5% | BLOCKED via safeguard |

---

## Change History

| Date | Change | Reason | Impact |
|------|--------|--------|--------|
| 2026-01-26 | Added Model 8 | Track profitable segment | Baseline for comparison |
| 2026-01-26 | Unknown player safeguard | -71.5% ROI on no-data bets | Prevents auto-add |

---

## Rules for Future Changes

1. **Minimum sample size:** 50 bets in segment before considering weight change
2. **Statistical significance:** ROI difference must be > 10% from baseline
3. **Document everything:** Log analysis, decision, and outcome
4. **One change at a time:** Don't adjust multiple weights simultaneously
5. **Track impact:** Monitor performance after any change for 100+ bets
