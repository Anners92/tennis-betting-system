# Tennis Betting System - Model Analysis Guide (v3.1)

Reference document for understanding and analysing matches using the 8-factor prediction model plus edge modifiers.

---

## Factor Weights (v3.1)

| # | Factor | Weight | What It Measures |
|---|--------|--------|------------------|
| 1 | Surface | 22% | Win rate on the specific surface (Hard/Clay/Grass) |
| 2 | Form | 20% | Recent match results (last 20 matches), quality-adjusted |
| 3 | Fatigue | 17% | Matches played in last 7/14/21 days, rest/rust detection |
| 4 | Ranking | 13% | ATP/WTA ranking converted to Elo |
| 5 | Perf Elo | 13% | Performance Elo from actual results vs ranking expectation |
| 6 | Recent Loss | 8% | Psychological impact of recent losses |
| 7 | H2H | 5% | Head-to-head record between the two players |
| 8 | Momentum | 2% | Win/loss streaks |

**Total: 100%** | Weights sum to 1.0.

**Deprecated/Removed factors**:
- **Injury** (was 5%) -- **DEPRECATED in v3.1**. Replaced by Activity Edge Modifier which detects returning/inactive players more reliably.
- **Opponent Quality** (was a separate factor) -- signal is fully captured by form's quality-adjusted scoring and loss-quality stability analysis.
- **Recency** (was a separate factor) -- signal is fully captured by form's exponential date-decay weighting.

**Edge Modifiers** (post-probability adjustments, not weighted factors):
- **Serve Edge Modifier** -- reduces edge up to 20% when serve stats conflict with pick
- **Activity Edge Modifier** -- reduces edge up to 40% for returning/inactive players

---

## How Each Factor Works

### 1. Surface (22%)

Win percentage on the match surface (Hard, Clay, Grass) from historical data. Players with strong surface-specific records get an edge. **This is believed to be one of the model's strongest signals vs the market** — hence the highest weight in v3.1.

### 2. Form (20%)

Analyses the last 20 matches for each player. Each match gets a score based on:

- **Elo-Expected Scoring**: Win score = `50 + 50 * (1 - expected_win_prob)`. Upset wins score high (~95), routine wins score low (~52). Loss score = `60 * (1 - expected_win_prob)`. Expected losses barely hurt (~48), upset losses are severe (~5).
- **Set Score Dominance**: A 6-0 6-0 win gets +15% bonus; a 2-6 0-6 loss gets -11% penalty. Parsed from score strings.
- **Date Decay**: Exponential decay with ~83-day half-life. Last week's match = 0.94x weight, 3 months ago = 0.47x.
- **Tournament Weight**: Grand Slam results = 1.3x, ATP = 1.15x, Challenger = 1.0x, ITF = 0.85x.
- **Surprise Weighting (losses only)**: Upset losses (losing to a weaker opponent) get up to 3x weight. This penalizes players who lose to players they shouldn't lose to.
- **Confirmed Strong Wins**: If a player beats a significantly higher-ranked opponent AND follows up with another strong win within 2 matches, both wins get 2x amplification. Catches genuine breakthroughs vs lucky wins.
- **Diminishing Returns**: Raw form advantage is capped via `tanh` scaling at +/-0.10. Prevents form from dominating when records differ.
- **Loss Quality Stability**: After form scores, compares the quality of each player's losses. Player who only loses to top opponents gets a stability bonus (up to +/-0.20). This is where "who do you lose to" matters.

**Key insight**: A player with a 14-6 record beating weak opponents can score WORSE than a player with 10-10 record losing only to elite opponents, thanks to surprise weighting and stability adjustments.

### 3. Fatigue (17%)

Measures physical load from recent schedule. Players with many recent matches may be fatigued. Considers matches in the last 7, 14, and 21 days. **The market tends to underweight this factor** — hence the increased weight in v3.1.

**Enhanced rust detection**: Players who have not competed recently receive a penalty. Max rust penalty is 25 points with an exponential decay constant (tau) of 8. At 14 days inactive the penalty is approximately 14.6 points.

### 4. Ranking (13%)

ATP/WTA ranking converted to Elo using: `2500 - 150 * log2(rank)`. The Elo difference produces a win probability. Rank #1 = Elo 2500, Rank #100 = Elo 1504, Rank #500 = Elo 1154.

**Large-gap handling**: When the ranking gap exceeds a threshold, the model normally boosts ranking weight by +0.25 and blends prediction toward ranking-based Elo (70/30 or 90/10). This is **suppressed** when breakout detection triggers (see below).

### 5. Performance Elo (13%)

A rolling 12-month Elo calculated from actual match results, using K-factors weighted by tournament level. This measures **actual recent performance** vs what the ranking says.

- **K-factors**: Grand Slam 48, ATP 32, WTA 28, Challenger 24, ITF 20
- When Performance Elo diverges from official ranking, the player may be over/under-ranked
- When Performance Elo data is missing for a player, ranking uses ATP/WTA Elo alone

### 6. Recent Loss (8%)

Psychological impact of a recent loss. Captures the "bounce back" vs "confidence dip" dynamic.

### 7. H2H (5%)

Head-to-head record between the two specific players. Lower weight because the market already prices this well, and sample sizes are often small.

### 8. Momentum (2%)

Current win/loss streaks. Kept small because momentum is noisy and largely captured by form.

### Deprecated: Injury (0%)

**DEPRECATED in v3.1.** Injury signals from withdrawal patterns were too noisy to be reliable. This has been replaced by the **Activity Edge Modifier**, which detects returning/inactive players more accurately by analyzing match frequency over 90 days rather than trying to infer injury from withdrawal patterns.

---

## Edge Modifiers

Edge modifiers are **post-probability adjustments** that reduce edge (not probability) when certain conditions indicate lower confidence. They operate after the factor-weighted probability is calculated.

### Serve Edge Modifier

The system scrapes serve and return statistics from Tennis Ratio for both players. These include 13 metrics per player:

- 1st serve percentage, 1st serve points won, 2nd serve points won
- Aces per match, double faults per match
- Break points saved percentage
- Return points won (1st serve, 2nd serve)
- Break points converted percentage
- Service games won percentage, return games won percentage
- Tiebreak win percentage

**DR (Dominance Ratio)** is the key metric: `service_games_won / return_games_won`. A DR > 1.0 indicates serve-dominant play.

**How it works:**
- **DR gap < 0.10**: Noise — no modification
- **DR aligned with bet**: No modification (don't double-count)
- **DR conflicting with bet, gap ≥ 0.10**: Edge reduced up to 20% (linear scale to gap 0.30)

Example: Model says pick has 8% edge. Serve stats conflict (opponent has better DR by 0.20). Edge reduced by ~13% → effective edge = 6.96%.

### Activity Edge Modifier

**Added in v3.1.** Replaces the deprecated injury factor. Detects returning/inactive players whose rankings may be unreliable.

**Activity Score (0-100):**
- **Match count in 90 days** (0-60 pts): More matches = higher score
- **Largest gap in 120 days** (0-40 pts): Smaller gaps = higher score

**Activity Labels:**
| Score | Label | Meaning |
|-------|-------|---------|
| ≥80 | Active | Playing regularly |
| ≥60 | Moderate | Some gaps but playing |
| ≥40 | Low Activity | Concerning gaps |
| ≥20 | Returning | Just came back from break |
| <20 | Inactive | Serious absence |

**Edge reduction:**
- Uses minimum score of both players
- Both active (≥80) = 1.0x (no reduction)
- Returning (20-40) = ~0.75x
- Inactive (<20) = 0.60x (40% max reduction)

**Staking reduction:** Additional 30% max cut when min activity < 50.

**Backtest mode:** Returns neutral (score=100) to avoid distorting historical analysis.

---

## Breakout Detection

When a lower-ranked player's recent results dramatically outperform their ranking, the breakout system adjusts the ranking input rather than adding a counterbalancing factor.

### Trigger Conditions
- Player ranked **outside top 150** (top players' rankings are already accurate)
- **2+ quality wins** in the last **45 days**
- Quality win = beating an opponent ranked at **half your ranking or better** (e.g., #1137 beating #500 or better)

### What Happens
1. **Implied ranking** computed from avg opponent rank of quality wins x 1.2 buffer
2. **Effective ranking** = blend of actual + implied (50% base, +10% per extra win, max 75%)
3. **Age multiplier**: Young (<=22) = 1.3x blend, Neutral (23-28) = 1.0x, Veteran (28+) = 0.6x
4. Ranking factor **recalculated** using effective ranking
5. Large-gap weight boost and Elo blend **suppressed**

### Example: Barsukov (#1137)
- Quality wins: #163 Mikrut, #192 Gomez Federico
- Implied ranking: avg(163, 192) x 1.2 = **213**
- Effective ranking: 1137 x 0.35 + 213 x 0.65 = **~675** (with age data would be ~536)
- Result: Shin probability dropped from 68.4% to 56.3%

### When It Doesn't Apply
- Top-150 players (Sinner, Alcaraz, etc.) -- ranking already accurate
- Single upset wins -- requires 2+ clustered wins to trigger
- Old wins -- quality wins age out of the 45-day cluster window

---

## Match Context System (Tournament Level Awareness)

When a player competes below their home tournament level, their ranking/H2H advantages are less meaningful. The match context system detects this and applies adjustments.

### Level Hierarchy
| Level | Value | Examples |
|-------|-------|----------|
| ITF | 1 | ITF Vero Beach, Futures events |
| Challenger | 2 | Challenger events |
| ATP/WTA | 3 | ATP/WTA tour events |
| Grand Slam | 4 | Australian Open, Wimbledon, etc. |

### How Player Home Level Is Determined
- **Ranking-based (primary)**: Rank 1-200 = ATP/WTA (3), 201-500 = check history (2 or 3), 501-1000 = Challenger (2), 1000+ = ITF (1)
- **Match history (fallback)**: Most common tournament level from last 20 matches

### Displacement & Discount
- **Displacement** = home_level - match_level (0 if playing at or above home level)
- **Discount** = 0.20 per level of displacement, capped at 0.60
- Applied **asymmetrically**: only discounts factor scores that favour the displaced player
- Affects: ranking, h2h factor scores

### Form Level Relevance
Historical form results are weighted by how close their tournament level is to the current match:
| Distance | Weight | Example |
|----------|--------|---------|
| 0 (same level) | 1.00 | ITF result when analyzing ITF match |
| 1 level away | 0.85 | Challenger result when analyzing ITF match |
| 2 levels away | 0.70 | WTA result when analyzing ITF match |
| 3 levels away | 0.55 | Grand Slam result when analyzing ITF match |

### Enhanced Rust Detection
- Max penalty increased from 15 to 25 points
- Decay constant (tau) decreased from 10 to 8 (steeper curve)
- 14 days inactive: old penalty ~7.6 points, new penalty ~14.6 points

### Context Warnings
The analysis dialog shows amber warnings for:
- **Level mismatch**: When a player is displaced below their home level
- **Rust**: When a player has not played in 10+ days
- **Near-breakout**: When a player has 1 quality win (needs 2 to trigger breakout)

### Example: Urhobo (#337) vs Osuigwe (#152) -- ITF Vero Beach
- Osuigwe: home level WTA (3), match level ITF (1), displacement = 2, discount = 40%
- Urhobo: home level Challenger (2), match level ITF (1), displacement = 1, discount = 20%
- Osuigwe's ranking advantage (-0.060) discounted to -0.036
- Combined shift: 6.1 points toward Urhobo (35.0% to 41.1%)
- Warnings: level mismatch for both + 14-day rust for Osuigwe

### When It Doesn't Apply
- **Same-level matches**: No displacement = no discount. Most matches are unaffected.
- **Control test**: Sinner vs Alcaraz at Australian Open -- 0.1 point difference (negligible)

---

## What to Look For When Analysing a Match

### Step 1: Check the Factor Breakdown
Double-click any match in the Bet Suggester to see the detailed factor analysis. Look at:

- **Which factors favour which player** -- are they all pointing the same direction, or is there disagreement?
- **Form scores** -- check the raw scores and the quality of wins/losses
- **Surface stats** -- does either player have a significantly better record on this surface? (highest-weighted factor)
- **Ranking vs Performance Elo** -- if they diverge, the player may be over/under-ranked
- **Edge modifiers** -- check serve alignment (DR gap, conflict indicator) and activity scores for both players

### Step 2: Compare to Market (Betfair Odds)
- **Our probability vs implied probability** from Betfair odds
- **Expected Value (EV)** = (Our Prob x Odds) - 1. Positive EV = value bet.
- Look for matches where our model disagrees with the market by 5%+ (EV > 5%)

### Step 3: Red Flags to Watch For

| Signal | What It Means |
|--------|---------------|
| Our % much higher than market | Model may be overvaluing form/ranking; check if opponent is a breakout candidate |
| Low liquidity (< 25 matched) | Market not yet formed; odds unreliable. These are filtered from analysis. |
| Large ranking gap + close odds | Market knows something about the lower-ranked player. Check for breakout signals. |
| Player losing to much weaker opponents | Loss quality stability should penalize this, but verify the form breakdown |
| First match after long break | Fatigue factor helps here, but form data may be stale |
| Surface specialist vs generalist | Surface factor (20%) can be the biggest edge source |

### Step 4: Breakout Candidates
If a lower-ranked player (150+) has:
- 2+ recent wins against opponents ranked much higher
- Wins clustered in last 45 days
- Young age (under 22-23)

The breakout system should detect this automatically. Check the analysis detail view -- if breakout triggered, it will show the effective ranking.

---

## Betting Models

### Hard Models (stake-determining)
| Model | Criteria | Use Case |
|-------|----------|----------|
| **M1** | Triple confirmation: model edge + serve aligned + active players | Premium (1.5x staking) |
| M3 | EV 5-15%, any odds | Core value ("Sharp") |
| M4 | Probability ≥ 60%, any odds | High confidence (Favorites) |
| M5 | Underdog: edge ≥ 10%, odds 3-10, 15+ matches | Upset value |
| M7 | EV 3-8%, odds < 2.50 | Lower risk value ("Grind") |
| M8 | Probability ≥ 55%, odds < 2.50 | Lower risk confidence (Profitable Baseline) |

### Soft Models (tag-only, no staking impact)
| Model | Criteria | Use Case |
|-------|----------|----------|
| M2 | Serve data available + both active | Data confirmed |
| M9 | Odds 2.00-2.99, serve data, edge 5-10% | Value zone |
| M10 | Odds < 2.20, prob ≥ 55%, both active | Confident grind |
| M11 | Surface factor ≥ 0.15, odds 2.00-3.50, edge ≥ 5% | Surface edge |

### Fade Model
| Model | Criteria | Use Case |
|-------|----------|----------|
| M12 | Pure M3/M5 triggers + opponent odds 1.20-1.50 | 2-0 fade (bet opponent 2-0 scoreline) |

**Notes:**
- All models enforce a minimum odds floor of 1.70
- A match can qualify for multiple models simultaneously
- M1 receives 1.5x staking boost (premium model)
- **M1+M11 thesis (n=40)**: 65.0% win rate, +55.6% ROI — proven edge
- **Pure M3**: 7.7% win rate at n=39 — catastrophic in isolation

---

## Known Limitations

1. **ITF-level players**: Both opponents often face similar-quality opposition, so form differentiation is weak. The model's biggest blind spot.
2. **Missing data**: Some players have NULL date-of-birth (affects breakout age multiplier), NULL set scores (affects dominance modifier), or NULL match-time rankings.
3. **Tournament-run inflation**: A player winning 5 matches at one ITF event inflates their form score, but all wins were at the same level. Date decay and tournament weighting partially mitigate this.
4. **Market intelligence**: Professional bettors and insiders have information (fitness, motivation, travel) the model cannot capture. A 20+ point gap between model and market often means the market knows something.
5. **Serve-return matchup blind spot**: The model evaluates players independently. The Serve Edge Modifier compares DR vs DR, but doesn't directly answer "can Player A break Player B's serve?" A serve-dominant player facing a weak returner may be undervalued. Manual review of return games won vs service games won is recommended.

---

## Case Studies

### Case 1: Shaikh (#409) vs Dmitruk (#421) -- ITF Hard
**Market**: 29.9% Shaikh / 70.1% Dmitruk
**Model (final)**: 48.2% Shaikh / 51.8% Dmitruk

Both ITF players with similar rankings. Shaikh had a 14-6 record vs Dmitruk's 10-10. Raw form heavily favoured Shaikh. However:
- Dmitruk's losses were all to top-350 opponents (avg #295) -- quality losses
- Shaikh lost to opponents as weak as #1479 Van Sambeek -- upset losses got 3x surprise weight
- Loss quality stability adjustment swung +0.12 toward Dmitruk
- Net effect: form advantage neutralised from +0.124 to +0.000

**Lesson**: Record alone is misleading. WHO you lose to matters as much as how many times you lose.

### Case 2: Shin (#358) vs Barsukov (#1137) -- Hard
**Market**: ~48% Shin / ~52% Barsukov
**Model (before breakout)**: 68.4% Shin -- massive gap
**Model (after breakout)**: 56.3% Shin

779-rank gap meant ranking factor heavily favoured Shin. But Barsukov had beaten #163 Mikrut and #192 Gomez Federico in the last 10 days. Breakout detection:
- Moved effective ranking from #1137 to #675
- Suppressed large-gap boost and Elo blend

**Lesson**: When a low-ranked player has recent quality wins clustered together, the ranking is stale. Breakout detection corrects this, but a gap to market may remain (12 points here) -- the market may be pricing in information beyond what the model captures.

### Case 3: Sinner (#2) vs Alcaraz (#1) -- Hard
**Model**: 60.6% Sinner / 39.4% Alcaraz

Top players with accurate rankings. Breakout doesn't trigger (top-150 excluded). Form, surface, and ranking all contribute normally. Sinner's 19-1 form vs Alcaraz's strong but slightly weaker recent results produce a sensible output.

**Lesson**: The model works well for top players where all data sources are rich and reliable.

### Case 4: Urhobo (#337) vs Osuigwe (#152) -- ITF Vero Beach, Hard
**Market**: ~72% Urhobo (1.38) / ~47% Osuigwe (2.12)
**Model**: 35.0% Urhobo / 65.0% Osuigwe -- **37-point disagreement, model inverted from market**

| Factor | Weighted | Favours |
|--------|----------|---------|
| Form | -0.001 | Neutral |
| Surface | -0.000 | Neutral |
| Ranking | -0.060 | Osuigwe |
| Fatigue | +0.002 | Urhobo |
| Recent Loss | 0.000 | Neutral |
| H2H | -0.050 | Osuigwe (2-0) |
| Injury | 0.000 | Neutral |
| Momentum | +0.002 | Urhobo |

**Form detail:**
- Urhobo: 70.0 score, 16-4 record, avg opp rank 623. On a 5-match win streak at ITF Weston. Confirmed strong wins vs Andreescu (#228) and Chang (#324) at 2.0x. All losses to top-380 -- quality losses.
- Osuigwe: 51.6 score, 10-10 record, avg opp rank 253. Played Australian Open qualifying (beat #139, #186) and Auckland (beat #98). But upset losses to #407 Nugroho Priska (3.0x surprise) and #632 Honer (3.0x surprise) -- she can lose to anyone on a bad day.
- Net form advantage: essentially zero (-0.004). Urhobo's record cancelled by Osuigwe's stronger schedule, but Osuigwe's upset losses pull her back.

**Why model favours Osuigwe (65%):** Ranking gap (#152 vs #337) and H2H (0-2). These are all legitimate signals -- Osuigwe IS the better-ranked player.

**Why market favours Urhobo (72%):**
1. Current form/rhythm -- 5 straight wins in last week vs 14 days since Osuigwe's last match (rust)
2. ITF venue -- ranking gap matters less at ITF level; Osuigwe's ranking built from WTA events
3. Osuigwe's inconsistency -- 10-10 record with upset losses to #407 and #632
4. Home advantage -- Urhobo based in Florida, playing Florida ITF circuit
5. Near-breakout -- Urhobo's wins vs #228 and #324 are strong for a #337 player, but didn't meet breakout threshold (needs opponent <= #168)

**Lesson**: Tournament level context matters enormously. A 185-rank gap at WTA level is very significant; at ITF level, much less so. The **Match Context System** (added after this case study) now detects this: Osuigwe gets a 40% discount on ranking/h2h advantages, shifting the model from 35% to 41% Urhobo. The remaining gap to market (72%) reflects information the model cannot capture (fitness, motivation, local knowledge). When the model and market disagree by 20+ points on cross-level matches, the market likely has insider intelligence.

---

## Quick Reference: Config Settings

```
FACTOR WEIGHTS (v3.1, 8 active factors):
  surface: 0.22             # Surface-specific win rate (STRONGEST SIGNAL)
  form: 0.20                # Quality-adjusted recent results
  fatigue: 0.17             # Schedule load / rust (market underweights)
  ranking: 0.13             # ATP/WTA Elo
  perf_elo: 0.13            # Performance Elo from actual results
  recent_loss: 0.08         # Psychological impact
  h2h: 0.05                 # Head-to-head record
  momentum: 0.02            # Win/loss streaks
  injury: 0.00              # DEPRECATED - replaced by Activity Edge Modifier

EDGE MODIFIERS (post-probability adjustments):
  Serve Edge Modifier:
    dr_gap_threshold: 0.10    # Minimum gap to trigger
    max_edge_reduction: 0.20  # 20% max reduction
    max_dr_gap: 0.30          # Gap at which max reduction applies
  Activity Edge Modifier:
    active_threshold: 80      # Score ≥80 = Active
    max_edge_reduction: 0.40  # 40% max reduction
    max_staking_reduction: 0.30  # 30% additional stake cut

PROBABILITY CALIBRATION (ENABLED):
  shrinkage_factor: 0.60      # Pulls probabilities toward 50%
  shrinkage_mode: asymmetric  # Favorites only
  market_blend_weight: 0.35   # 35% market, 65% calibrated

STAKING (Kelly-based):
  kelly_fraction: 0.375       # Fractional Kelly
  m1_boost: 1.50              # M1 gets 1.5x stake
  no_data_multiplier: 0.50    # 50% stake when missing data
  min_odds_floor: 1.70        # Minimum odds

FORM_SETTINGS:
  default_matches: 20         # Form window
  max_form_advantage: 0.10    # Tanh cap on form diff
  max_stability_adjustment: 0.20  # Loss quality cap

BREAKOUT_SETTINGS:
  min_ranking: 150            # Top-150 excluded
  quality_win_threshold: 0.5  # Opponent rank <= player_rank * 0.5
  cluster_window_days: 45     # Quality wins must be recent
  min_quality_wins: 2         # At least 2 to trigger
  base_blend: 0.50            # Starting blend toward implied rank
  max_blend: 0.75             # Hard cap on blend

PERFORMANCE_ELO_SETTINGS:
  rolling_months: 12          # Elo calculation window
  K-factors: Grand Slam 48, ATP 32, WTA 28, Challenger 24, ITF 20

MATCH_CONTEXT_SETTINGS:
  level_hierarchy: ITF=1, Challenger=2, ATP/WTA=3, Grand Slam=4
  discount_per_level: 0.20    # Score discount per displacement level
  max_discount: 0.60          # Hard cap
  discounted_factors: ranking, h2h
  form_level_relevance: same=1.0, 1 away=0.85, 2 away=0.70, 3 away=0.55

FATIGUE_SETTINGS:
  rust_max_penalty: 25        # Max rust penalty
  rust_tau: 8                 # Decay constant

MIN_MATCHED_LIQUIDITY: 25     # Minimum 25 matched to show/analyse
```

---

*Document version: 3.1 | System version: v3.1 | Updated: Feb 5, 2026*
