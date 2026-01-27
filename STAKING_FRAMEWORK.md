# Tennis Betting Staking Framework

**Created:** January 22, 2026
**Purpose:** Evidence-based staking strategy derived from professional betting literature and handicapper analysis.

---

## The Problem (Before)

- **17.1% win rate** on 41 bets
- **-53.3% ROI**
- System was putting 3 units on 10.00+ longshots
- Model found "big edges" that didn't exist
- Edge override at 20% bypassed all safety limits

---

## Research Sources

### Books & Authors

**Joseph Buchdahl - "Monte Carlo or Bust"**
- Betting analyst with 20+ years experience
- Runs Football-Data.co.uk and Tennis-Data.co.uk
- Key insight: "There is no 'next day' after ruin" - theoretical ROI means nothing if bankroll depleted

### Articles

| Source | Key Insight |
|--------|-------------|
| [Pinnacle - Fractional Kelly](https://www.pinnacle.com/en/betting-articles/Betting-Strategy/fractional-kelly-criterion/GBD27Z9NLJVGFLGG) | Half Kelly reduces catastrophic loss probability from 25% to 12% |
| [Pinnacle - Monte Carlo Review](https://www.pinnacle.com/en/betting-articles/educational/monte-carlo-or-bust-book-review/SHA274CCU45T7N7B) | "Believing and knowing you have edge is not the same thing" |
| [Sports Trading Network](https://www.sportstradingnetwork.com/article/quantifying-possible-returns-from-percentage-staking/) | Kelly formula: Stake % = Edge / (Odds - 1) |
| [OddsIndex](https://oddsindex.com/guides/betting-favorites-vs-underdogs) | Professional stake sizing by odds range |

### Professional Tennis Handicappers

| Handicapper | Win Rate | Avg Odds | Profit | Strategy |
|-------------|----------|----------|--------|----------|
| Mark Wilson | ~55% | Mixed | $3,000+ | High volume, surface analysis |
| Calvin King | 53-54% | Mixed | $3,000+ | Systematic, both favorites & underdogs |
| Hunter Price | 46-47% | +150 (2.50) | $2,800+ | **Short underdogs only, NOT longshots** |
| Rob Vinciletti | 60%+ | -150 (1.67) | $1,500 | Strong favorites, situational edges |
| Dan Weston | N/A | N/A | N/A | 2-2.5% per position, 40-50 buy-ins |

**Key Insight from Hunter Price:** Profitable on underdogs at 2.50, NOT 10.00 longshots. There's a massive difference between a competitive underdog and a moonshot.

---

## Professional Stake Sizing Guidelines

From professional consensus:

| Odds Type | Decimal Odds | Recommended Stake |
|-----------|--------------|-------------------|
| Short favorites | 1.67 - 1.91 | 1-2 units |
| Heavy favorites | 1.50 or less | 0.5-1 unit |
| Small underdogs | 2.00 - 3.00 | 0.5-1 unit |
| Big underdogs | 3.00+ | **0.25-0.5 units max** |

---

## Kelly Criterion

### The Formula

```
Stake % = Edge / (Decimal Odds - 1)
```

Where:
- Edge = Our Probability - Implied Probability
- Implied Probability = 1 / Decimal Odds

### Example

- Our probability: 60%
- Decimal odds: 2.00
- Implied probability: 50%
- Edge: 10%
- Kelly stake: 10% / (2.00 - 1) = **10%**

### Why Kelly Naturally Penalizes Longshots

Same 10% edge at different odds:

| Odds | Kelly Stake |
|------|-------------|
| 2.00 | 10% / 1 = 10% |
| 5.00 | 10% / 4 = 2.5% |
| 10.00 | 10% / 9 = **1.1%** |

No hard cap needed - the math does it automatically.

---

## Fractional Kelly

Full Kelly is too aggressive. Professional recommendation:

| Strategy | Prob of 20%+ Loss | Prob of 40%+ Loss | Median Growth |
|----------|-------------------|-------------------|---------------|
| Full Kelly | 25% | 15% | 122 |
| **Half Kelly** | **12%** | **2%** | 116 |
| Quarter Kelly | ~3% | ~0% | 109 |

**Recommendation:** Use **Quarter Kelly** for conservative approach, **Half Kelly** for moderate.

> "Reducing the risks by halving Kelly stakes... is a price worth paying." - Pinnacle

---

## Market Disagreement Penalty

**Core Principle:** When our model significantly disagrees with the market, we're probably wrong.

The market (bookmakers) has information. If we're 3x more bullish than them, that's suspicious.

| Probability Ratio | Meaning | Penalty |
|-------------------|---------|---------|
| 1.0 - 1.5x | Minor disagreement | 1.0 (full stake) |
| 1.5 - 2.0x | Moderate disagreement | 0.75 |
| 2.0 - 3.0x | Major disagreement | 0.50 |
| 3.0x+ | Extreme disagreement | 0.25 |

**Calculation:** `prob_ratio = our_probability / implied_probability`

---

## The Framework

### Formula

```
Final Stake = Kelly Stake × Kelly Fraction × Disagreement Penalty
```

### Implementation

```python
def calculate_stake(our_prob, decimal_odds, kelly_fraction=0.25):
    """
    Kelly-based staking with market skepticism.

    Args:
        our_prob: Our model's win probability (0-1)
        decimal_odds: Decimal odds offered
        kelly_fraction: Fraction of Kelly to use (default 0.25 = quarter Kelly)

    Returns:
        Recommended units to stake
    """
    implied_prob = 1 / decimal_odds
    edge = our_prob - implied_prob

    # No bet if no edge
    if edge <= 0:
        return 0

    # Kelly stake (as proportion of bankroll)
    kelly_stake = edge / (decimal_odds - 1)

    # Apply fractional Kelly
    base_stake = kelly_stake * kelly_fraction

    # Market disagreement penalty
    prob_ratio = our_prob / implied_prob

    if prob_ratio > 3.0:
        # Extreme disagreement - likely model error
        disagreement_penalty = 0.25
    elif prob_ratio > 2.0:
        # Major disagreement - be very cautious
        disagreement_penalty = 0.5
    elif prob_ratio > 1.5:
        # Moderate disagreement - some caution
        disagreement_penalty = 0.75
    else:
        # Minor disagreement - trust model
        disagreement_penalty = 1.0

    final_stake = base_stake * disagreement_penalty

    # Convert to units (assuming 2% per unit)
    units = final_stake / 0.02

    # Round to nearest 0.5 units
    return round(units * 2) / 2
```

---

## Example Outcomes

| Scenario | Our Prob | Odds | Implied | Edge | Ratio | Kelly | Quarter | Penalty | Final Units |
|----------|----------|------|---------|------|-------|-------|---------|---------|-------------|
| Strong favorite | 75% | 1.50 | 66.7% | 8.3% | 1.13x | 16.7% | 4.2% | 1.0 | **2.0** |
| Slight favorite | 55% | 1.80 | 55.6% | -0.6% | 0.99x | - | - | - | **0** |
| Competitive underdog | 40% | 2.80 | 35.7% | 4.3% | 1.12x | 2.4% | 0.6% | 1.0 | **0.5** |
| Moderate underdog | 35% | 4.00 | 25% | 10% | 1.4x | 3.3% | 0.8% | 1.0 | **0.5** |
| Longshot (suspicious) | 30% | 10.00 | 10% | 20% | 3.0x | 2.2% | 0.6% | 0.25 | **0** |
| Moonshot (model error) | 15% | 20.00 | 5% | 10% | 3.0x | 0.5% | 0.13% | 0.25 | **0** |

**Key Result:** The 10.00 longshot that was getting 3 units now gets **0 units**.

---

## Comparison: Old vs New

### Old System (Edge Tiers + Override)

```
Edge 5-10%  → 1 unit
Edge 10-15% → 2 units
Edge 15%+   → 3 units
Edge 20%+   → OVERRIDE odds caps, allow 3 units on anything
```

**Result:** 3 units on 10.00 longshots, -53% ROI

### New System (Kelly + Skepticism)

```
Stake = (Edge / (Odds-1)) × 0.25 × Disagreement Penalty
```

**Result:** Natural scaling, cautious on longshots, no arbitrary overrides

---

## Key Principles to Remember

1. **Kelly naturally penalizes longshots** - no hard caps needed
2. **Fractional Kelly (quarter or half) reduces ruin risk** dramatically
3. **When you disagree with the market by 2-3x, you're probably wrong**
4. **"There is no 'next day' after ruin"** - preserve bankroll above all
5. **Profitable underdog betting = 2.50 odds, not 10.00 odds** (Hunter Price)
6. **"Believing and knowing you have edge is not the same thing"** - don't be overconfident

---

## Implementation Checklist

- [x] Replace edge tier system with Kelly-based calculation
- [x] Implement fractional Kelly (using 0.40 Kelly - balanced approach)
- [x] Add market disagreement penalty
- [x] Remove edge override threshold entirely
- [x] Log staking decisions for analysis (includes Kelly breakdown)
- [x] Test on historical data before live use
- [ ] Update UI to show Kelly stake calculation breakdown (optional enhancement)

---

## Session Log

**January 22, 2026:** Created this framework based on research into:
- Joseph Buchdahl's books (Monte Carlo or Bust, Fixed Odds Sports Betting)
- Pinnacle betting articles on Kelly criterion
- Professional tennis handicapper analysis (Boyd's Bets)
- Dan Weston interview (professional tennis bettor)

**January 22, 2026 (later):** Implemented Kelly-based staking in `match_analyzer.py`:
- Replaced edge tier system with Kelly formula
- Using 0.40 Kelly fraction (balanced between quarter and half)
- Added market disagreement penalty (0.25-1.0x based on prob ratio)
- Removed edge override threshold completely
- Set 0.5 units as minimum bet threshold
- Kept confidence scaling for low-confidence predictions

**Test Results:**
| Scenario | Old System | New System |
|----------|------------|------------|
| 10.00 longshot (30% prob, 20% edge) | 3 units | 0 units |
| 38.00 moonshot | 3 units | 0 units |
| Strong favorite (75% @ 1.50) | 3 units | 3 units |
| Competitive underdog (40% @ 2.80) | 1 unit | 0.5 units |
