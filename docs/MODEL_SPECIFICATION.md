# Tennis Betting System v3.1 -- Model Specification

**Document Type:** Authoritative Technical Reference
**System Version:** 3.1 (February 5, 2026)
**Model Type:** Multi-factor weighted probability model with edge modifiers and Kelly-based staking
**Scope:** ATP, WTA, Challenger, and ITF tennis match winner prediction

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Factor Model](#2-factor-model)
3. [Probability Calculation Pipeline](#3-probability-calculation-pipeline)
4. [Betting Model Definitions](#4-betting-model-definitions) (11 models)
5. [Staking Strategy](#5-staking-strategy)
6. [Surface Detection](#6-surface-detection)
7. [Breakout Detection](#7-breakout-detection)
8. [Performance Elo](#8-performance-elo)
9. [Edge Modifiers](#9-edge-modifiers) (Serve + Activity)
10. [Match Context System](#10-match-context-system)
11. [Edge Cases and Constraints](#11-edge-cases-and-constraints)
12. [Appendix: Factor Score Examples](#12-appendix-factor-score-examples)

---

## 1. Executive Summary

### Purpose

The Tennis Betting System is a quantitative match-winner probability model designed to identify value bets on the Betfair Exchange across all levels of professional tennis. It compares its internally generated probabilities against Betfair market-implied probabilities to find positive expected-value (EV) opportunities, then sizes bets using a fractional Kelly criterion.

### Architecture Overview

The model operates as a **9-factor weighted linear combination** (with 2 legacy factors zeroed out for a total of 11 factor slots), converted to a probability via a logistic function. The pipeline is:

```
Raw Data --> Factor Scores (-1 to +1 each) --> Weighted Sum --> Logistic Transform --> P1 Win Probability
```

### Key Metrics

| Metric | Value |
|--------|-------|
| Active factors | 8 (form, surface, ranking, fatigue, recent_loss, h2h, momentum, performance_elo) |
| Inactive factors | 3 (opponent_quality 0%, recency 0%, injury 0% - replaced by Activity Modifier) |
| Edge modifiers | 2 (Serve Alignment, Activity Level) |
| Probability calibration | Enabled: 0.60 shrinkage (asymmetric), 0.35 market blend |
| Factor weights sum | 1.00 |
| Logistic steepness (k) | 3.0 |
| Kelly fraction | 0.375 (37.5% of full Kelly) |
| M1 staking boost | 1.5x |
| No-data staking factor | 0.50x |
| Unit size | 2.0% of bankroll |
| Minimum bet | 0.25 units |
| Maximum bet | 3.0 units |
| Minimum odds floor | 1.70 decimal |
| Minimum probability | 40% |
| Betting models | 11 (M1-M5, M7-M12, excluding M6) |

### Data Sources

| Source | Data Provided |
|--------|--------------|
| Betfair Exchange API | Live odds, market liquidity, match schedules |
| GitHub tennisdata (Tennis Explorer scrape) | Match results, scores, player data |
| Tennis Explorer (live verification) | Recent match counts for data quality checks |
| Tennis Ratio | Serve/return statistics (13 metrics per player, display-only) |
| Rankings cache (JSON) | Current ATP/WTA rankings (scraped) |

---

## 2. Factor Model

### 2.1 Factor Weights (Default Profile)

| # | Factor | Weight | Signal Type | Range |
|---|--------|--------|-------------|-------|
| 1 | Surface | 0.22 (22%) | Surface-specific win rates | -1.0 to +1.0 |
| 2 | Form | 0.20 (20%) | Recent match performance | -0.30 to +0.30 |
| 3 | Fatigue | 0.17 (17%) | Schedule load and rest | -1.0 to +1.0 |
| 4 | Ranking | 0.13 (13%) | ATP/WTA ranking via Elo conversion | -1.0 to +1.0 |
| 5 | Performance Elo | 0.13 (13%) | Results-based 12-month rolling Elo | -1.0 to +1.0 |
| 6 | Recent Loss | 0.08 (8%) | Psychological impact of recent losses | -0.20 to +0.20 |
| 7 | H2H | 0.05 (5%) | Head-to-head record | -1.0 to +1.0 |
| 8 | Momentum | 0.02 (2%) | Same-surface win streak | -0.10 to +0.10 |
| 9 | Injury | 0.00 (0%) | DEPRECATED -- replaced by Activity Edge Modifier | N/A |
| 10 | Opponent Quality | 0.00 (0%) | REMOVED -- redundant with form | N/A |
| 11 | Recency | 0.00 (0%) | REMOVED -- already in form decay | N/A |

**Total active weight: 1.00**

**Note:** The Injury factor (formerly 5%) has been replaced by the Activity Edge Modifier, which operates as a post-probability modifier rather than a weighted factor. See Section 9.3 for details.

All factor scores are expressed as Player 1 advantage. Positive values favour P1; negative values favour P2.

### 2.2 Alternative Weight Profiles

The system supports 6 weight profiles. The Default profile is used for all automated betting. Alternative profiles are available for manual analysis:

| Profile | Form | Surface | Ranking | Perf Elo | Fatigue | Recent Loss | H2H | Injury | Momentum |
|---------|------|---------|---------|----------|---------|-------------|-----|--------|----------|
| **Default** | 0.20 | 0.20 | 0.13 | 0.12 | 0.15 | 0.08 | 0.05 | 0.05 | 0.02 |
| Form Focus | 0.35 | 0.15 | 0.10 | 0.10 | 0.10 | 0.08 | 0.05 | 0.05 | 0.02 |
| Surface Focus | 0.15 | 0.35 | 0.10 | 0.10 | 0.10 | 0.08 | 0.05 | 0.05 | 0.02 |
| Ranking Focus | 0.15 | 0.15 | 0.25 | 0.15 | 0.10 | 0.08 | 0.05 | 0.05 | 0.02 |
| Fatigue Focus | 0.15 | 0.15 | 0.10 | 0.10 | 0.30 | 0.08 | 0.05 | 0.05 | 0.02 |
| Psychology Focus | 0.20 | 0.15 | 0.10 | 0.10 | 0.10 | 0.15 | 0.05 | 0.05 | 0.10 |

---

### 2.3 Factor 1: Form (Weight: 0.20)

**Purpose:** Measures recent match performance quality-adjusted for opponent strength, set dominance, match importance, and recency.

**Input:** Last 20 matches for each player (configurable via `FORM_SETTINGS["default_matches"]`).

**Minimum data:** 3 matches required for `has_data = True`. Below this, form factor is set to 0 (neutral).

#### 2.3.1 Per-Match Scoring

Each match receives a base score using **Elo-expected scoring**. The player's ranking is converted to Elo, and the opponent's ranking is converted to Elo. The expected win probability is calculated:

```
player_elo = 2500 - 150 * log2(player_rank)
opponent_elo = 2500 - 150 * log2(opponent_rank)
expected_win = 1 / (1 + 10^((opponent_elo - player_elo) / 400))
expected_win = clamp(expected_win, 0.05, 0.95)
```

**Win score:**
```
base_score = 50 + 50 * (1 - expected_win)
```
- Upset win (expected_win = 0.10): score = 95
- Even match win (expected_win = 0.50): score = 75
- Expected win (expected_win = 0.90): score = 55

**Loss score:**
```
base_score = 60 * (1 - expected_win)
```
- Expected loss (expected_win = 0.10): score = 54
- Even match loss (expected_win = 0.50): score = 30
- Upset loss (expected_win = 0.90): score = 6

#### 2.3.2 Set Score Dominance Modifier

Games won and lost are extracted from the match score string. A dominance multiplier is applied:

```
player_ratio = player_games / (player_games + opponent_games)
dominance = 1 + (player_ratio - 0.5) * 0.3
```

Range: 0.85 (blowout loss) to 1.15 (dominant win). A 6-0 6-0 win has ratio 1.0, giving dominance = 1.15. A 0-6 0-6 loss has ratio 0.0, giving dominance = 0.85.

```
match_score = base_score * dominance
```

#### 2.3.3 Weight Calculation

Each match receives a combined weight from four components:

```
weight = position_decay * tournament_weight * date_decay * surprise_weight
```

**Position decay:** Exponential decay by match position (most recent = index 0):
```
position_decay = 0.9 ^ index
```

**Tournament weight:** Tournament level multiplier:
| Level | Weight |
|-------|--------|
| Grand Slam | 1.30 |
| ATP | 1.15 |
| WTA | 1.10 |
| Challenger | 1.00 |
| ITF | 0.85 |
| Unknown | 1.00 |

**Date decay:** Exponential decay based on days since match (~83-day half-life):
```
date_decay = exp(-days_ago / 120)
```
- 7 days ago: 0.943
- 30 days ago: 0.779
- 60 days ago: 0.607
- 90 days ago: 0.472

**Level relevance (when match context is active):** If the current match level is known, historical results are further weighted by proximity to that level:
| Level Distance | Relevance |
|----------------|-----------|
| 0 (same level) | 1.00 |
| 1 level away | 0.85 |
| 2 levels away | 0.70 |
| 3 levels away | 0.55 |

The tournament weight is multiplied by the level relevance.

**Surprise weighting (losses only):** Upset losses (losing to a weaker opponent) get amplified weight to penalise unreliable players:
```
if won:
    surprise = 1.0
else:
    surprise = clamp(expected_win / (1 - expected_win), 1.0, 3.0)
```
- Expected loss (expected_win 0.10): surprise = 0.111 -> clamped to 1.0
- Even-match loss (expected_win 0.50): surprise = 1.0
- Upset loss (expected_win 0.90): surprise = 9.0 -> clamped to 3.0

#### 2.3.4 Confirmed Strong Wins Amplification

After the initial pass, the system looks for **confirmed strong wins**: if a player beats a higher-ranked opponent AND follows up with another strong win (against someone ranked within 1.5x of the first opponent's rank) within the next 2 matches, both wins are amplified to a surprise weight of 2.0. This catches genuine breakthroughs versus one-off upsets.

```
For each win against opponent ranked higher than player:
    Check if any of the next 2 matches is also a win against similarly-ranked opponent
    If yes: amplify both wins' weight to effective surprise = 2.0
```

#### 2.3.5 Final Form Score

```
form_score = sum(match_score * weight) / sum(weight)
```

Range: approximately 0 to 100, centred around 50.

#### 2.3.6 Form Advantage Calculation

The raw form difference is converted to a factor advantage using **tanh diminishing returns**:

```
raw_form_diff = (p1_form_score - p2_form_score) / 100
max_advantage = 0.10
form_advantage = max_advantage * tanh(raw_form_diff / max_advantage)
```

This caps the form advantage at approximately +/-0.10, preventing form from dominating the model.

#### 2.3.7 Loss Quality Stability Adjustment

After form advantage is calculated, a **loss quality stability adjustment** is applied. This measures who each player loses to.

1. Collect all losses for each player from their form data
2. Convert each loss opponent's rank to Elo
3. Calculate mean Elo of losses for each player
4. Calculate the difference:
```
loss_quality_diff = (p2_mean_loss_elo - p1_mean_loss_elo) / 400
```
Positive value means P2 loses to stronger opponents (P2 is more stable).

5. Apply **consistency dampening** when losses are scattered:
```
if both players have 2+ losses:
    p1_std = stdev(p1_loss_elos)
    p2_std = stdev(p2_loss_elos)
    max_std = max(p1_std, p2_std)
    consistency = 1.0 / (1.0 + (max_std / 150) ^ 2.0)
    loss_quality_diff *= consistency
```

6. Apply to form factor:
```
stability_adjustment = -0.20 * tanh(loss_quality_diff / 0.40)
form_advantage += stability_adjustment
```

Maximum stability adjustment: +/-0.20 (via tanh cap). Total form factor is clamped to `[-0.30, +0.30]` (max_advantage + max_stability).

---

### 2.4 Factor 2: Surface (Weight: 0.20)

**Purpose:** Compares surface-specific win rates for the match surface (Hard, Clay, or Grass).

**Calculation:**

1. Retrieve career surface stats and recent surface stats (last 2 years, configurable via `SURFACE_SETTINGS["recent_years"]`)
2. Calculate combined win rate:
```
If career_matches >= 20 (min_matches_reliable):
    combined_win_rate = career_win_rate * 0.4 + recent_win_rate * 0.6

If career_matches < 20:
    career_reliability = career_matches / 20
    career_weight = 0.4 * career_reliability
    recent_weight = 0.6
    neutral_weight = 1 - career_weight - recent_weight
    combined_win_rate = career_win_rate * career_weight + recent_win_rate * recent_weight + 0.5 * neutral_weight
```

3. Surface advantage:
```
surface_advantage = p1_combined_win_rate - p2_combined_win_rate
```

4. Loss quality stability adjustment (same as form):
```
surface_stability = -0.20 * 0.5 * tanh(loss_quality_diff / 0.40)
surface_advantage += surface_stability
```

The 0.5 multiplier halves the stability effect for surface compared to form.

**Data requirements:** `has_data = True` when career_matches >= 5 OR recent_matches >= 5. If either player lacks data, surface advantage is set to 0.

---

### 2.5 Factor 3: Ranking (Weight: 0.13)

**Purpose:** Converts ATP/WTA rankings to Elo ratings and derives a win probability from the Elo gap.

**Ranking-to-Elo conversion:**
```
elo = 2500 - 150 * log2(max(ranking, 1))
elo = max(elo, 1000)  // Floor at 1000
```

Reference values:
| Ranking | Elo |
|---------|-----|
| #1 | 2500 |
| #10 | 2002 |
| #50 | 1654 |
| #100 | 1504 |
| #200 | 1354 |
| #500 | 1154 |
| #1000 | 1004 |

**Elo-based win probability:**
```
elo_win_prob = 1 / (1 + 10^((p2_elo - p1_elo) / 400))
```

**Ranking advantage (on -1 to +1 scale):**
```
rank_advantage = (elo_win_prob - 0.5) * 2
```

**Ranking fallback for unranked players:**
- If a player has no ranking but has Betfair odds, ranking is estimated from odds:

| Odds Range | Estimated Rank |
|------------|---------------|
| 1.01 - 1.05 | 3 |
| 1.05 - 1.15 | 10 |
| 1.15 - 1.30 | 25 |
| 1.30 - 1.50 | 50 |
| 1.50 - 2.00 | 100 |
| 2.00 - 3.00 | 150 |
| 3.00+ | 200 |

- If neither ranking nor odds available, the lowest ranking in the database is used as default.

**Large gap detection:**
```
rank_gap = abs(p1_rank - p2_rank)
is_large_gap = rank_gap > 100 OR (min(p1_rank, p2_rank) <= 10 AND rank_gap > 50)
```

When a large gap is detected (and no breakout or significant displacement), the ranking weight is dynamically boosted by +0.25 (capped at 0.60), with the boost distributed from other factors at -0.03125 each.

---

### 2.6 Factor 4: Performance Elo (Weight: 0.12)

**Purpose:** A "model ranking" based on actual match results over the last 12 months. Divergence from ranking-derived Elo indicates a player performing above or below their official ranking.

See [Section 8: Performance Elo](#8-performance-elo) for the full calculation.

**Advantage calculation:**
```
win_prob = 1 / (1 + 10^((p2_perf_elo - p1_perf_elo) / 400))
advantage = (win_prob - 0.5) * 2
```

**Fallback:** When no Performance Elo data exists for a player, ranking-derived Elo is used instead. When neither player has Performance Elo data, the entire weight (0.12) is redistributed to the ranking factor.

**Breakout interaction:** When breakout detection triggers, the Performance Elo is blended upward toward the effective ranking Elo:
```
perf_elo = max(perf_elo, 0.5 * perf_elo + 0.5 * ranking_to_elo(effective_rank))
```

---

### 2.7 Factor 5: Fatigue (Weight: 0.15)

**Purpose:** Measures physical load from recent schedule, including rest days, match frequency, and match difficulty. The market tends to underweight this factor, making it a potential edge source.

**Score composition (0-100):**
```
total_score = rest_component (0-40) + workload_component (0-40) + base_fitness (20)
```

#### Rest Component (0-40 points)

```
if days_rest < 3 (optimal_rest_days):
    rest_score = days_rest / 3 * 40

elif days_rest <= 7 (rust_start_days):
    rest_score = 40  // Full points in optimal window

else:  // Rust penalty
    rust_days = days_rest - 7
    rust_penalty = 25 * (1 - exp(-rust_days / 8))
    rest_score = max(25, 40 - rust_penalty)
```

Rust penalty examples:
| Days Rest | Rust Penalty | Rest Score |
|-----------|-------------|------------|
| 7 | 0.0 | 40.0 |
| 10 | 7.9 | 32.1 |
| 14 | 14.6 | 25.4 |
| 21 | 20.8 | 25.0 (floor) |
| 30 | 23.9 | 25.0 (floor) |

#### Workload Component (0-40 points)

Three sub-penalties, each capped independently:

**1. Match difficulty in last 7 days** (cap: 20 points)
- Each match has a difficulty score from 0.5 (walkover) to 3.0 (5-set marathon)
- Difficulty = `1.0 + combined_factor * (3.0 - 1.0)` where `combined_factor = duration_factor * 0.6 + sets_factor * 0.4`
```
if difficulty_7d > 3.0:
    if difficulty_7d <= 6.0:
        penalty = (difficulty_7d - 3.0) * 1.0
    else:
        penalty = (6.0 - 3.0) * 1.0 + (difficulty_7d - 6.0) * 5
penalty = min(penalty, 20)
```

**2. Matches in 14 days** (cap: 15 points)
```
if matches_14d > 2:
    if matches_14d <= 5:
        penalty = (matches_14d - 2) * 1.5
    else:
        penalty = (5 - 2) * 1.5 + (matches_14d - 5) * 3
penalty = min(penalty, 15)
```

**3. Matches in 30 days** (cap: 10 points)
```
if matches_30d > 6:
    if matches_30d <= 10:
        penalty = (matches_30d - 6) * 0.5
    else:
        penalty = (10 - 6) * 0.5 + (matches_30d - 10) * 2
penalty = min(penalty, 10)
```

Total workload penalty is capped at 40.

#### Fatigue Factor Advantage
```
fatigue_advantage = (p1_score - p2_score) / 100
```

#### Status Labels
| Score | Status |
|-------|--------|
| >= 75 | Fresh |
| >= 60 | Good |
| >= 45 | Moderate |
| >= 30 | Tired |
| < 30 | Fatigued |

---

### 2.8 Factor 6: Recent Loss (Weight: 0.08)

**Purpose:** Captures the psychological impact of coming off a recent loss.

**Calculation:** Examines the 3 most recent matches for each player. Checks for the most recent loss only.

| Condition | Penalty |
|-----------|---------|
| Loss within 3 days | -0.10 |
| Loss within 7 days (but >3 days) | -0.05 |
| 5-set loss within 7 days | additional -0.05 |
| No recent loss | 0.00 |

Maximum penalty per player: -0.15 (3-day loss that was a 5-setter).

**Factor advantage:**
```
recent_loss_advantage = p1_penalty - p2_penalty
```

Since penalties are negative, if P2 has a worse (more negative) penalty, the advantage is positive (favouring P1).

---

### 2.9 Factor 7: Head-to-Head (Weight: 0.05)

**Purpose:** Direct historical record between the two players.

**Overall H2H advantage:**
```
h2h_advantage = (p1_wins - p2_wins) / total_matches
```
Range: -1.0 to +1.0. Zero if no H2H matches.

**Surface-specific H2H advantage:**
```
surface_advantage = (surface_p1_wins - surface_p2_wins) / surface_total
```

**Combined advantage (blended):**
```
if surface_total >= 2:
    combined = 0.6 * h2h_advantage + 0.4 * surface_advantage
else:
    combined = h2h_advantage
```

Low weight (5%) because the market already prices H2H well and sample sizes are often small.

---

### 2.10 Factor 8: Injury (Weight: 0.05)

**Purpose:** Detects injury and retirement signals.

**Score assignment based on injury status:**

| Status | Score |
|--------|-------|
| Healthy (no injuries, retirement rate <= 10%) | 100 |
| Concern (no injuries, retirement rate > 10%) | 70 |
| Minor Concern | 80 |
| Returning | 70 |
| Questionable | 60 |
| Doubtful | 40 |
| Out | 0 |

The retirement rate is calculated from the last 20 matches:
```
retirement_rate = retirements / total_recent_matches
```

**Injury advantage:**
```
injury_advantage = (p1_score - p2_score) / 100
```

**Note:** In backtesting mode, injury returns neutral (score 100) since no historical injury data is available.

---

### 2.11 Factor 9: Momentum (Weight: 0.02)

**Purpose:** Bonus for recent wins on the same surface as the upcoming match.

**Calculation:** Examines the last 5 matches (within the last 14 days) on the same surface.

```
bonus = wins_on_surface * 0.03
bonus = min(bonus, 0.10)
```

**Momentum advantage:**
```
momentum_advantage = p1_bonus - p2_bonus
```

Range: -0.10 to +0.10. Kept small because momentum is noisy and largely captured by form.

---

## 3. Probability Calculation Pipeline

This section describes the exact step-by-step pipeline from raw data to final probability, implemented in `MatchAnalyzer.calculate_win_probability()`.

### Step 1: Compute Match Context

Determine tournament level and each player's "home" level. Calculate displacement and discounts (see [Section 10](#10-match-context-system)).

### Step 2: Calculate All Factor Scores (Parallel)

All 11 factor scores are computed in parallel using a ThreadPoolExecutor with 8 workers. This includes breakout detection for both players.

### Step 3: Apply Breakout Adjustments

If either player triggers breakout detection:
- Recompute ranking factors using effective rankings
- Recompute Performance Elo factors using effective rankings

### Step 4: Calculate Factor Advantages

Each factor produces an advantage score on a scale roughly -1.0 to +1.0 (positive = P1 advantage):

| Factor | Advantage Formula |
|--------|------------------|
| Form | `tanh(raw_diff / 0.10) * 0.10 + stability_adj` |
| Surface | `p1_combined_rate - p2_combined_rate + surface_stability` |
| Ranking | `(elo_win_prob - 0.5) * 2` |
| Performance Elo | `(perf_elo_win_prob - 0.5) * 2` |
| Fatigue | `(p1_score - p2_score) / 100` |
| Recent Loss | `p1_penalty - p2_penalty` |
| H2H | `0.6 * overall_adv + 0.4 * surface_adv` (if surface data) |
| Injury | `(p1_score - p2_score) / 100` |
| Momentum | `p1_bonus - p2_bonus` |

### Step 5: Apply Match Context Discounts

For factors in `["ranking", "performance_elo", "h2h"]`:
- If the factor score favours P1 AND P1 is displaced, multiply by `(1 - p1_discount)`
- If the factor score favours P2 AND P2 is displaced, multiply by `(1 - p2_discount)`

Discounts are asymmetric -- only the displaced player's advantages are reduced.

### Step 6: Adjust Weights for Data Availability

**Missing data redistribution:**
- If either player lacks form data: form weight goes to 0, weight redistributed to ranking
- If either player lacks surface data: surface weight goes to 0, weight redistributed to ranking
- If neither player has Performance Elo: perf_elo weight goes to 0, weight redistributed to ranking

**Large ranking gap boost** (when `is_large_gap = True` AND no breakout AND no significant displacement):
```
ranking_weight += 0.25 (capped at 0.60)
All other factor weights -= 0.03125 each (floored at 0.01-0.05 depending on factor)
```

### Step 7: Calculate Weighted Advantage

```
weighted_advantage = SUM(factor_advantage[i] * adjusted_weight[i]) for all factors
```

### Step 8: Logistic Transform

```
model_probability = 1 / (1 + exp(-3.0 * weighted_advantage))
```

The steepness parameter k=3.0 determines how aggressively the model moves away from 50%. A weighted advantage of +0.10 yields approximately 57.4% probability.

### Step 9: Large Gap Elo Blend

For large ranking gaps (without breakout or significant displacement), the model probability is blended with the pure Elo win probability:

```
if ranking and form agree on direction:
    p1_probability = 0.7 * model_probability + 0.3 * elo_win_prob
else (ranking and form disagree):
    p1_probability = 0.9 * model_probability + 0.1 * elo_win_prob
```

When no large gap exists: `p1_probability = model_probability` (no blend).

### Step 10: Confidence Calculation

Confidence (0 to 1) is computed from three components:

```
confidence = data_quality * 0.4 + factor_agreement * 0.3 + prediction_clarity * 0.3
```

**Data Quality (40%):**
- Form data quality: up to 0.4 (based on match count, 10 = max)
- Surface data quality: up to 0.25 (based on match count, 20 = max)
- H2H data quality: up to 0.15 (based on match count, 5 = max)
- Ranking availability: up to 0.2

**Factor Agreement (30%):**
- Weighted count of factors pointing in the same direction as the overall prediction

**Prediction Clarity (30%):**
```
clarity = min(|p1_probability - 0.5| / 0.4, 1.0)
```

Confidence is clamped to [0.05, 0.95].

---

## 4. Betting Model Definitions

Bets must qualify for at least one hard model (M3, M4, M5, M7, or M8) to be placed. A bet can qualify for multiple models simultaneously. All models require odds >= 1.70 (odds floor) and probability >= 40% (probability floor).

### 4.1 Model Categories

Models are categorised into three types:

1. **Hard Models (M3, M4, M5, M7, M8):** Gate to betting. At least one hard model must qualify.
2. **Soft Models (M2, M9, M10, M11):** Tracking tags. Added for analysis but don't gate betting.
3. **Premium Model (M1):** Staking boost. Qualifies when hard model + serve alignment + active players.
4. **Fade Model (M12):** Counter-signal. Triggers on Pure M3 or M5 → bet opponent 2-0.

### 4.2 Hard Models (Required for Betting)

Implemented in `config.py::calculate_bet_model()`.

| Model | Name | Criteria | Use Case |
|-------|------|----------|----------|
| **M3** | Sharp Zone | 5% ≤ edge ≤ 15% | Core value bets with moderate edge |
| **M4** | Favorites | prob ≥ 60% | High-confidence selections |
| **M5** | Underdog | edge ≥ 10%, odds 3.00-10.00, both 15+ matches | Large edge on long odds |
| **M7** | Grind | 3% ≤ edge ≤ 8%, odds < 2.50 | Small edge, short odds |
| **M8** | Profitable Baseline | prob ≥ 55%, odds < 2.50 | Moderate confidence + short odds |

**WARNING:** M5 has -13.31u P/L at 14.3% win rate (n=35). Pure M5 triggers M12 fade.

### 4.3 Soft Models (Tracking Tags)

| Model | Name | Criteria | Rationale |
|-------|------|----------|-----------|
| **M2** | Data Confirmed | Any hard model + serve data for both + both active (≥40 score) | Data quality marker |
| **M9** | Value Zone | Odds 2.00-2.99, serve aligned, 5% ≤ edge ≤ 10% | Best odds range + validation |
| **M10** | Confident Grind | Odds < 2.20, prob ≥ 55%, both active (≥60 score) | Short odds + active players |
| **M11** | Surface Edge | Surface factor ≥ 0.05, odds 2.00-3.50, edge ≥ 5% | Surface-driven plays |

### 4.4 Premium Model (Staking Boost)

| Model | Name | Criteria | Effect |
|-------|------|----------|--------|
| **M1** | Triple Confirmation | Any hard model + serve aligned + not activity-driven edge | **1.5x staking multiplier** |

**Performance (Feb 5, 2026):** 40 bets, 65.0% win rate, +22.53u, +55.6% ROI. This is the proven edge.

### 4.5 Fade Model (Counter-Signal)

| Model | Name | Trigger | Action |
|-------|------|---------|--------|
| **M12** | 2-0 Fade | Pure M3 (M3 only) OR any M5 AND opponent odds 1.20-1.50 | Bet opponent wins 2-0 |

**Rationale:** 71% of favourite wins are 2-0. Market prices 2-0 at ~52.5% implied → 18.5pp edge.

### 4.6 Example Qualifications

| Our Prob | Edge | Odds | Serve | Activity | Hard Models | Soft Models |
|----------|------|------|-------|----------|-------------|-------------|
| 65% | 10% | 1.82 | aligned | both 80+ | M3, M4, M8 | M1, M2, M11 |
| 58% | 8% | 2.00 | neutral | both 60+ | M3, M7, M8 | M2, M9, M10 |
| 55% | 12% | 4.00 | aligned | both 80+ | M3, M5 | M1, M2 |
| 52% | 5% | 2.50 | conflict | one 40 | M3 | M2 |
| 55% | 5% | 3.00 | aligned | both 80+ | M3 | M1, M11 |

---

## 5. Staking Strategy

### 5.1 Kelly Criterion Formula

The system uses **fractional Kelly criterion** with market disagreement penalties for stake sizing. Implemented in `MatchAnalyzer.find_value()`.

**Master formula:**
```
Final Stake = Kelly Stake % * Kelly Fraction * Disagreement Penalty * Odds Multiplier
```

### 5.2 Step-by-Step Staking Pipeline

**Preconditions for betting:**
```
edge > 0 AND EV > 5% AND odds >= 1.70
```
Where:
```
implied_prob = 1 / decimal_odds
edge = our_prob - implied_prob
EV = (our_prob * (decimal_odds - 1)) - (1 - our_prob)
```

**Step 1: Full Kelly Stake**
```
kelly_stake_pct = edge / (decimal_odds - 1)
```

**Step 2: Fractional Kelly**
```
fractional_kelly_pct = kelly_stake_pct * 0.375
```
The fraction 0.375 is a balanced approach between quarter Kelly (0.25, conservative) and half Kelly (0.50, aggressive).

**Step 3: Market Disagreement Penalty**

Calculate the probability ratio:
```
prob_ratio = our_probability / implied_probability
```

| Disagreement Level | Ratio Range | Penalty |
|-------------------|-------------|---------|
| Minor | <= 1.20 | 1.00 (full stake) |
| Moderate | 1.20 - 1.50 | 0.75 |
| Major | > 1.50 | 0.50 |

```
final_stake_pct = fractional_kelly_pct * disagreement_penalty
```

**Step 4: Convert to Units**
```
base_units = final_stake_pct / (unit_size_percent / 100)
         = final_stake_pct / 0.02
```

Where 1 unit = 2% of bankroll.

**Step 5: Odds Range Weighting**

Currently **disabled** (outside_multiplier = 1.0, sweet_spot range effectively 1.01 - 99.0). When enabled, bets outside the 2.00-2.99 "sweet spot" would receive a 0.5x multiplier.

**Step 6: Caps and Rounding**
```
recommended_units = min(base_units, 3.0)    // Max cap
recommended_units = round(recommended_units * 2) / 2  // Round to nearest 0.5
if recommended_units < 0.25:
    recommended_units = 0  // Below minimum, no bet
```

**Step 7: Stake as Bankroll Percentage**
```
recommended_stake = recommended_units * (2.0 / 100)
```

### 5.3 Stake Tiers

| Units | Tier |
|-------|------|
| 0 (below 0.25 minimum) | below_minimum (no bet) |
| 0.25 - 0.5 | standard |
| 1.0 - 1.5 | confident |
| 2.0 - 3.0 | strong |

### 5.4 Probability Calibration (v3.1 - ENABLED)

Two-layer calibration corrects systematic model overconfidence (historical: predicted 47.7% vs 34.8% actual).

**Layer 1: Shrinkage Calibration**
```
if probability > 0.5:  # Asymmetric - favorites only
    calibrated = 0.5 + (raw - 0.5) × 0.60
else:
    calibrated = raw  # Underdogs unchanged
```
Shrinkage factor: **0.60**

Examples:
| Raw Prob | After Shrinkage |
|----------|-----------------|
| 60% | 56% |
| 65% | 59% |
| 70% | 62% |
| 80% | 68% |

**Asymmetric Rationale (v3.1.9):** Only shrinking favorites prevents calibration from inflating underdog probabilities and creating phantom edges on longshots.

**Layer 2: Market Blend**
```
final = calibrated × 0.65 + market_implied × 0.35
```
Market weight: **0.35**

**Combined Effect Example:**
```
Raw model: 65%, Market implied: 50%
After shrinkage: 0.5 + (0.65 - 0.5) × 0.60 = 59%
After blend: 59% × 0.65 + 50% × 0.35 = 55.85%
Edge: 55.85% - 50% = 5.85pp (down from 15pp raw)
```

Edges are roughly halved by calibration, but remain where the model has genuine signal.

### 5.6 Staking Modifiers (v3.1)

Multiple modifiers can stack to adjust the final stake:

**Model-Based Modifiers:**
| Model | Modifier | Effect |
|-------|----------|--------|
| M1 (Triple Confirmation) | 1.5x | Boost stake for highest-confidence plays |

**Edge Modifier-Based:**
| Condition | Modifier | Effect |
|-----------|----------|--------|
| No serve data for either player | 0.50x | Reduce stake on blind bets |
| Serve conflict (DR gap ≥ 0.30) | up to 0.70x | Additional reduction for worst conflicts |
| Low activity (min score < 50) | up to 0.70x | Reduce stake when ranking unreliable |

**Data Quality Adjustments (2u+ bets):**
For bets of 2.0 units or higher, additional confidence-based adjustments apply (`config.py::adjust_stake_for_confidence()`):

| Condition | Multiplier Reduction |
|-----------|---------------------|
| No surface data for either player | -20% |
| Surface data missing for one player | -10% |
| No H2H history | -10% |
| Limited form data (<5 matches per player) | -15% |
| Ranking dominates (>40% of edge) | -10% |

Minimum multiplier: 0.50 (never reduce by more than half). Result rounded to nearest 0.5 units, floored at 0.5 units.

### 5.7 Data Quality Gate

Before placing any bet, a data quality check runs (`config.py::check_data_quality_for_stake()`):

**Standard bets (<2u):** Each player needs 3+ recent matches (last 60 days).
**High-stakes bets (2u+):** Each player needs 5+ recent matches.

If database shows insufficient matches, the system verifies against Tennis Explorer:
- TE shows enough matches: **PASS** (database is stale)
- TE shows insufficient but player played this month: **PASS with 50% stake reduction**
- TE shows insufficient and no recent play: **BLOCK** (bet rejected)

**High-stakes form check:** For 2u+ bets, the selection's current-year win rate must not be 15%+ worse than the opponent's.

### 5.8 Exchange Commission

The Betfair exchange commission rate is stored as 2% (`exchange_commission: 0.02`) but is **not currently applied** in the EV or Kelly calculations. This means the model slightly overestimates edge. The commission represents a known but minor systematic bias.

---

## 6. Surface Detection

Surface detection is centralised in `config.py::get_tournament_surface()`. This is the **single source of truth** for all surface decisions.

### 6.1 Detection Priority

1. **Explicit surface in tournament name:** Check for ` - clay`, `(clay)`, ` - grass`, `(grass)`, ` - hard`, `(hard)`, ` - indoor`
2. **Known clay tournaments:** Match against `CLAY_TOURNAMENTS` list (95+ entries)
3. **Known grass tournaments (seasonal):** Match against `GRASS_TOURNAMENTS` list, but **only during June-July** (months 6-7)
4. **Default:** Hard (most common surface, especially for Challengers)

### 6.2 Grass Season Constraint

Grass tournaments are **only recognised during June and July**. If the match date is outside these months, grass tournament names are ignored and the surface defaults to Hard. This prevents false matches (e.g., "Halle" matching a Challenger event in February).

```python
is_grass_season = month in [6, 7]
```

### 6.3 Word Boundary Matching

Short tournament keywords (6 characters or fewer, single words) use regex word boundary matching to prevent substring false positives:

```python
if len(keyword) <= 6 and ' ' not in keyword:
    pattern = r'\b' + re.escape(keyword) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))
else:
    return keyword in text
```

Example: "rome" matches "Rome Masters" but not "Jerome".

### 6.4 Tournament Name Normalisation

Before surface detection, tournament names are normalised:
- Year suffixes stripped (e.g., "Concepcion Challenger 2026" -> "Concepcion Challenger")
- Grand Slam prefixes stripped ("Ladies/Men's/Women's")

### 6.5 Key Tournament Lists

**Clay tournaments (95+ entries):** Roland Garros, Monte Carlo, Madrid, Rome, Barcelona, Hamburg, Rio, Buenos Aires, and ~85 additional ATP 250/Challenger/WTA clay events.

**Grass tournaments (20+ entries):** Wimbledon, Queens, Halle, s-Hertogenbosch, Stuttgart (Boss Open), Eastbourne, Mallorca, Newport, Birmingham Classic, Nottingham, Bad Homburg.

**Indoor Hard tournaments (for reference):** Paris Masters, Vienna, Basel, Stockholm, etc. These still return "Hard" surface.

---

## 7. Breakout Detection

Implemented in `MatchAnalyzer.calculate_breakout_signal()`.

### 7.1 Purpose

Detects when a lower-ranked player's recent results dramatically outperform their ranking, signalling a genuine level shift rather than random variance. Adjusts the effective ranking used by the ranking and Performance Elo factors.

### 7.2 Trigger Conditions

All conditions must be met:
1. Player ranked **outside top 150** (`min_ranking = 150`)
2. At least **2 quality wins** within the last **45 days** (`cluster_window_days`)
3. A quality win is defined as beating an opponent ranked at `player_rank * 0.5` or better

Example: Player ranked #400 must beat opponents ranked #200 or better.

### 7.3 Effective Ranking Calculation

**Step 1: Implied ranking**
```
avg_opponent_rank = mean(quality_win_opponent_ranks)
implied_ranking = int(avg_opponent_rank * 1.2)  // 1.2x buffer to avoid over-promotion
implied_ranking = max(implied_ranking, 50)  // Floor at 50
```

**Step 2: Age multiplier**
```
if age <= 22: age_mult = 1.3   // Young players (full bonus)
elif age <= 28: age_mult = 1.0  // Neutral
else: age_mult = 0.6           // Veterans (reduced bonus)
// If age unknown: age_mult = 1.0
```

**Step 3: Blend factor**
```
blend = 0.50 + (num_quality_wins - 2) * 0.10
blend = min(blend, 0.75)  // Hard cap
blend *= age_mult
blend = min(blend, 0.85)  // Absolute hard cap
```

| Quality Wins | Base Blend | With Age <= 22 | With Age 28+ |
|-------------|-----------|----------------|--------------|
| 2 | 50% | 65% | 30% |
| 3 | 60% | 78% | 36% |
| 4 | 70% | 85% (capped) | 42% |
| 5+ | 75% (capped) | 85% (capped) | 45% |

**Step 4: Effective ranking**
```
effective_ranking = int(player_rank * (1 - blend) + implied_ranking * blend)
effective_ranking = max(effective_ranking, implied_ranking)  // Never worse than implied
effective_ranking = min(effective_ranking, player_rank)      // Never worse than actual
```

### 7.4 Effects When Breakout Triggers

1. Ranking factor is recalculated using effective ranking
2. Performance Elo factor is recalculated (blended toward effective ranking Elo)
3. Large-gap weight boost is **suppressed**
4. Large-gap Elo blend is **suppressed**

### 7.5 When Breakout Does Not Apply

- Top-150 players (ranking already accurate)
- Only 1 quality win (need 2+ to trigger)
- Quality wins older than 45 days
- Players without ranking data

---

## 8. Performance Elo

Implemented in `performance_elo.py`.

### 8.1 Purpose

A rolling 12-month Elo rating based on actual match results, weighted by opponent strength and tournament importance. Players whose Performance Elo diverges from their ranking-derived Elo are either outperforming (rising) or underperforming (declining) relative to their official position.

### 8.2 Calculation

**Starting point:** Ranking-derived Elo using the same formula as the ranking factor:
```
starting_elo = 2500 - 150 * log2(max(current_ranking, 1))
starting_elo = max(starting_elo, 1000)
```
Default Elo for unranked players: 1200.

**Match iteration:** Matches from the last 12 months are processed chronologically (oldest first):

```
For each match:
    1. Determine opponent's Elo from their ranking
    2. Calculate expected result:
       expected = 1 / (1 + 10^((opponent_elo - player_elo) / 400))
    3. Determine actual result:
       actual = 1.0 if won, 0.0 if lost
    4. Get K-factor from tournament level
    5. Update Elo:
       elo += K * (actual - expected)
```

### 8.3 K-Factors by Tournament Level

Higher K-factors for more important tournaments mean those results shift the rating more:

| Tournament Level | K-Factor |
|-----------------|----------|
| Grand Slam | 48 |
| ATP | 32 |
| WTA | 28 |
| Challenger | 24 |
| ITF | 20 |
| Unknown | 24 |

### 8.4 Tour Detection

Each player is classified as ATP or WTA based on their match history:
- Count tournaments classified as ATP/Challenger vs WTA
- Women's ITF events (W15, W25, W40, etc.) count toward WTA
- Ambiguous players are resolved iteratively by checking opponents' classifications
- Final fallback: default to ATP if no signal

### 8.5 Performance Ranks

After all Performance Elo values are calculated, players are ranked within their tour (ATP or WTA) by Elo descending. The highest Elo = rank 1.

### 8.6 Key Differences from Official Ranking

| Aspect | ATP/WTA Ranking | Performance Elo |
|--------|----------------|-----------------|
| Window | Rolling 52 weeks (best of) | Rolling 12 months (all matches) |
| Weighting | Points by round reached | K-factor by tournament level |
| Signal | Tournament participation + consistency | Wins against strong opponents |
| Lag | Weekly updates | Recalculated from raw data |

---

## 9. Edge Modifiers

Edge modifiers operate as **post-probability adjustments** rather than weighted factors. They reduce edge or staking when certain conditions are detected.

### 9.1 Serve Edge Modifier (v2.62)

Tennis Ratio serve/return statistics are used to detect serve alignment between our pick and the underlying serve data.

**Key Metric: Dominance Ratio (DR)**
```
DR = service_games_won / return_games_won
```
Higher DR = stronger server relative to return ability.

**Alignment Detection:**
1. Calculate DR gap = |Pick DR - Opponent DR|
2. If DR gap < 0.10 → **NEUTRAL** (noise zone, no modification)
3. If Pick DR > Opponent DR → **ALIGNED** (serve data supports our pick)
4. If Pick DR < Opponent DR → **CONFLICTED** (serve data contradicts our pick)

**Edge Reduction (Conflicted Only):**
```
conflict_strength = min(1.0, (dr_gap - 0.10) / 0.20)
edge_reduction = conflict_strength × 0.20
```
Maximum edge reduction: **20%**

**Staking Reduction:**
- No serve data for either player → **0.50x staking factor** (50% less on blind bets)
- Serve conflict with DR gap ≥ 0.30 → **up to 0.70x staking** (additional 30% reduction)

**M1 Qualification:**
- Serve alignment = "aligned" is required for M1 (Triple Confirmation) model
- This is a key reason M1 outperforms: serve data validates the model's prediction

### 9.2 Serve Stats Display

The system stores 13 metrics per player from Tennis Ratio:
- Aces per match, Double faults per match
- First serve %, 1st serve points won %, 2nd serve points won %
- Break points saved %, Service games won %
- Return 1st won %, Return 2nd won %, Return games won %
- Break points converted %

These are displayed in the match analysis popup as a comparison table.

### 9.3 Activity Edge Modifier (v3.1)

Detects returning or inactive players whose rankings are unreliable. **Replaces the former Injury factor (5%).**

**Activity Score Calculation (0-100):**

```
Signal A: Match Count in 90 days (0-60 points)
  >= 12 matches: 60 pts
  >= 8 matches:  40-60 pts (linear)
  >= 4 matches:  15-40 pts (linear)
  < 4 matches:   0-15 pts (linear)

Signal B: Largest Gap in 120 days (0-40 points)
  <= 14 days: 40 pts (normal)
  <= 21 days: 30-40 pts
  <= 35 days: 15-30 pts
  <= 60 days: 0-15 pts
  > 60 days:  0 pts (returning player)

Activity Score = Signal A + Signal B
```

**Activity Labels:**
| Score | Label |
|-------|-------|
| >= 80 | Active |
| >= 60 | Moderate |
| >= 40 | Low Activity |
| >= 20 | Returning |
| < 20 | Inactive |

**Edge Modifier (uses minimum score of both players):**
```
if min_score >= 70:
    modifier = 1.0 (no reduction)
else:
    reduction = (70 - min_score) / 70 × 0.40
    modifier = 1.0 - reduction
```
Maximum edge reduction: **40%**

**Staking Modifier:**
```
if min_score < 50:
    Additional staking reduction up to 30%
```

**M1 Qualification:**
- Activity-driven edge (detected when betting against inactive player) disqualifies M1
- This prevents the premium staking boost when edge comes from unreliable ranking data

**Note:** In backtest mode, activity modifier returns neutral (score=100) since no historical activity data is tracked.

---

## 10. Match Context System

Implemented in `MatchAnalyzer.get_match_context()` and related methods.

### 10.1 Purpose

When a player competes below their home tournament level (e.g., a WTA-ranked player at an ITF event), their ranking/Elo/H2H advantages are less meaningful. The match context system detects this displacement and discounts the relevant factors.

### 10.2 Level Hierarchy

| Level | Value | Examples |
|-------|-------|----------|
| ITF | 1 | ITF futures, W15/W25 events |
| Challenger | 2 | ATP/WTA Challenger events |
| ATP/WTA | 3 | Tour-level events |
| Grand Slam | 4 | AO, RG, Wimbledon, USO |
| Unknown | 2 | Default (middle ground) |

### 10.3 Player Home Level Determination

**Primary method (ranking-based):**
| Ranking | Home Level |
|---------|-----------|
| 1 - 200 | 3 (ATP/WTA) |
| 201 - 500 | Check match history; if Grand Slam/WTA/ATP appearances, level 3; otherwise level 2 |
| 501 - 1000 | 2 (Challenger) |
| 1000+ | 1 (ITF) |

**Fallback method (match history):** Most common tournament level from last 20 matches.

### 10.4 Displacement and Discount

```
displacement = max(0, home_level - match_level)
discount = min(displacement * 0.20, 0.60)
```

| Displacement | Discount |
|-------------|---------|
| 0 (same level or above) | 0% |
| 1 level below | 20% |
| 2 levels below | 40% |
| 3 levels below | 60% (maximum) |

### 10.5 Discount Application

Discounts are applied **asymmetrically** to three factors: `ranking`, `performance_elo`, `h2h`.

```
For each discounted factor:
    if score > 0 AND p1 is displaced:
        score *= (1 - p1_discount)
    elif score < 0 AND p2 is displaced:
        score *= (1 - p2_discount)
```

Only the **displaced player's advantages** are reduced. If a displaced player's factor score is neutral or favours their opponent, no discount is applied.

### 10.6 Additional Context Features

**Significant displacement suppression:** When either player has displacement >= 2:
- Large-gap ranking weight boost is **suppressed**
- Large-gap Elo blend is **suppressed**

**Rust warnings:** Generated when a player has not played in 10+ days (`rust_warning_days = 10`).

**Near-breakout warnings:** Generated when a player has exactly 1 quality win (needs 2 to trigger full breakout).

**Level mismatch warnings:** Generated when a player is displaced below their home level.

---

## 11. Edge Cases and Constraints

### 11.1 When the Model Does Not Apply

| Scenario | Behaviour |
|----------|----------|
| Odds below 1.70 | Bet rejected (no model qualifies) |
| Opponent odds below 1.05 | Match filtered (liquidity concern) |
| No model qualification (M3/M4/M7/M8) | Bet not placed |
| EV below 5% | Bet not placed |
| Stake below 0.25 units | Bet not placed |
| Both players have < 3 matches in 60 days | Bet may be blocked by data quality gate |

### 11.2 Known Limitations

1. **ITF-level differentiation:** At ITF level, both opponents often face similar-quality opposition, making form differentiation weak. This is the model's biggest blind spot.

2. **Missing data:** Some players have NULL date-of-birth (affects breakout age multiplier), NULL set scores (affects dominance modifier), or NULL match-time rankings. The system uses fallbacks but accuracy is reduced.

3. **Tournament-run inflation:** A player winning 5 matches at one ITF event inflates their form score, but all wins were at the same level. Date decay and tournament weighting partially mitigate this.

4. **Market intelligence gap:** Professional bettors and insiders have information (fitness, motivation, travel, court conditions) the model cannot capture. A 20+ point gap between model and market often means the market knows something.

5. **Performance Elo lag:** Uses 12-month rolling data. Very recent breakthroughs (last 2-3 weeks) may not fully reflect in Performance Elo. The breakout system compensates for this in the ranking factor.

6. **Surface data sparsity:** Grass court matches are limited to June-July. Many players have very few grass matches, making surface stats unreliable for Wimbledon analysis.

7. **H2H small samples:** Most player pairs have 0-3 head-to-head matches. The low weight (5%) reflects this, but the factor can be misleading with very small samples.

8. **Exchange commission not in EV:** The 2% Betfair commission is stored but not deducted from EV calculations, causing slight systematic overestimation of edge.

9. **Injury data staleness:** Injury information is entered manually and can become stale. In backtesting, injury always returns neutral.

10. **Cross-level ranking validity:** A player ranked #150 on WTA may face a different competitive landscape than #150 on ATP, but the model uses a single ranking-to-Elo formula for both.

### 11.3 Data Quality Protections

| Protection | Trigger | Action |
|-----------|---------|--------|
| Minimum matches gate | <3 matches (standard) or <5 matches (2u+ bets) | Block bet or verify via Tennis Explorer |
| High-stake form check | 2u+ bet, selection form 15%+ worse than opponent | Block bet |
| Confidence stake adjustment | 2u+ bet with missing data | Reduce stake by up to 50% |
| Liquidity filter | Opponent odds < 1.05 | Skip match |

### 11.4 Probability Bounds

- Model output is bounded by the logistic function (asymptotically approaches 0 and 1)
- In practice, outputs rarely exceed 80% or fall below 20% due to the tanh caps on form and the moderate logistic steepness (k=3)
- Calibration (when enabled) would further compress toward 50%

---

## 12. Appendix: Factor Score Examples

### Example A: Even Match (Challenger Hard Court)

**Players:** Player A (#180, 13-7 form, 62% Hard) vs Player B (#195, 11-9 form, 58% Hard)

| Factor | P1 Score | P2 Score | Advantage | Weight | Weighted |
|--------|----------|----------|-----------|--------|----------|
| Form | 63.2 | 55.8 | +0.065 (tanh capped) | 0.20 | +0.013 |
| Surface | 62% | 58% | +0.040 | 0.20 | +0.008 |
| Ranking | Elo 1370 | Elo 1348 | +0.062 | 0.13 | +0.008 |
| Perf Elo | 1395 | 1320 | +0.107 | 0.12 | +0.013 |
| Fatigue | 78 | 72 | +0.060 | 0.15 | +0.009 |
| Recent Loss | 0.00 | -0.05 | +0.050 | 0.08 | +0.004 |
| H2H | 2-1 | 1-2 | +0.333 | 0.05 | +0.017 |
| Injury | 100 | 100 | 0.000 | 0.05 | +0.000 |
| Momentum | +0.03 | 0.00 | +0.030 | 0.02 | +0.001 |

**Weighted advantage:** +0.073
**Logistic probability:** `1 / (1 + exp(-3 * 0.073))` = 55.5%
**P1 probability:** 55.5%, **P2 probability:** 44.5%

At Betfair odds of 1.85 (implied 54.1%):
- Edge = 55.5% - 54.1% = 1.4% -> Below 5% EV threshold -> **No bet**

At Betfair odds of 2.10 (implied 47.6%):
- Edge = 55.5% - 47.6% = 7.9%
- EV = (0.555 * 1.10) - 0.445 = 16.6%
- Kelly = 7.9% / 1.10 = 7.18%
- Fractional Kelly = 7.18% * 0.375 = 2.69%
- Units = 2.69% / 2% = 1.35 -> rounded to **1.5 units**
- Models: M3 (5-15% edge), M7 (3-8% + <2.50)

### Example B: Large Ranking Gap with Breakout

**Players:** Top Player (#15, Elo 1914) vs Rising Player (#450, Elo 1164, actual; 2 quality wins in 30 days against #180 and #210)

**Breakout triggers for Rising Player:**
- Rank 450 > 150 threshold
- 2 quality wins against opponents ranked <= 225 (450 * 0.5)
- Implied ranking = int(mean(180, 210) * 1.2) = int(195 * 1.2) = 234
- Blend = 0.50 (base, 2 wins)
- Age 21 -> age_mult = 1.3 -> blend = 0.50 * 1.3 = 0.65
- Effective ranking = int(450 * 0.35 + 234 * 0.65) = int(157.5 + 152.1) = 309

**Without breakout:** Ranking factor heavily favours P1 (Elo gap ~750, ~95% win probability from ranking alone)
**With breakout:** Effective Elo for P2 = 2500 - 150 * log2(309) = ~1255. Gap reduced to ~660, ~90% from ranking.

The large-gap boost and Elo blend are **suppressed** because breakout is active.

### Example C: Cross-Level Match (WTA player at ITF event)

**Players:** WTA Player (#120, home level 3) vs ITF Player (#500, home level 1) at ITF Vero Beach (match level 1)

**Displacement:**
- WTA Player: displacement = 3 - 1 = 2, discount = 40%
- ITF Player: displacement = max(0, 1 - 1) = 0, discount = 0%

**Factor adjustment (ranking):**
- WTA Player has ranking advantage (negative score, favouring P2 in our convention where P2 = WTA player)
- Score is -0.45 (strong P2 advantage)
- P2 is displaced with 40% discount
- Adjusted: -0.45 * (1 - 0.40) = -0.27

Similarly applied to performance_elo and h2h.

**Significant displacement (>= 2) also suppresses:**
- Large-gap weight boost
- Large-gap Elo blend

Result: The WTA player's advantages are significantly reduced, reflecting that ranking differences are less meaningful at lower tour levels.

### Example D: Kelly Staking Worked Example

**Given:**
- Our probability: 58%
- Betfair odds: 2.20 (implied probability: 45.45%)
- Tournament: ATP 250

**Step 1: Edge and EV**
```
edge = 0.58 - 0.4545 = 0.1255 (12.55%)
EV = (0.58 * 1.20) - 0.42 = 0.696 - 0.42 = 0.276 (27.6%)
```

**Step 2: Full Kelly**
```
kelly_stake_pct = 0.1255 / (2.20 - 1) = 0.1255 / 1.20 = 0.1046 (10.46%)
```

**Step 3: Fractional Kelly (37.5%)**
```
fractional_kelly = 0.1046 * 0.375 = 0.03922 (3.92%)
```

**Step 4: Disagreement Penalty**
```
prob_ratio = 0.58 / 0.4545 = 1.276
```
Ratio 1.276 falls in "moderate" range (1.20 - 1.50), penalty = 0.75
```
final_stake_pct = 0.03922 * 0.75 = 0.02942 (2.94%)
```

**Step 5: Convert to Units**
```
base_units = 0.02942 / 0.02 = 1.471
```

**Step 6: Round and Cap**
```
recommended_units = min(1.471, 3.0) = 1.471
rounded = round(1.471 * 2) / 2 = 1.5 units
```

**Model qualification:**
- Edge 12.55% -> M3 (5-15% range)
- Prob 58% -> Not M4 (needs 60%)
- Edge > 8% -> Not M7 (needs 3-8%)
- Prob 58% >= 55% AND odds 2.20 < 2.50 -> M8

**Result:** 1.5 units on M3, M8 at Betfair odds 2.20.

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 3.1 | 2026-02-05 | 11 models (added M1, M2, M5, M9-M12), serve edge modifier, activity edge modifier (replaced injury factor), probability calibration enabled (0.60 shrinkage, 0.35 market blend), updated factor weights (surface 22%, fatigue 17%, perf_elo 13%), M1 staking boost 1.5x |
| 2.62 | 2026-02-01 | Serve alignment detection, asymmetric calibration (favorites only), activity factor prototype |
| 2.61 | 2026-01-31 | Tennis Ratio serve stats (display-only), CLV tracking, Performance Elo, cloud backtester, Discord bot enhancements |
| 2.1.0 | 2026-01-27 | Centralised surface detection, fixed Halle/challenger bug, tournament profiles |
| 2.0.0 | 2026-01-26 | Simplified to 4 models (M3/M4/M7/M8), 8 active factors, added perf_elo as 9th, match context system |

---

## Key Insight (Feb 5, 2026)

Analysis of 157 settled bets reveals a critical pattern:

| Segment | Bets | Record | Win% | P/L | ROI |
|---------|------|--------|------|-----|-----|
| **M1 or M11** | 40 | 26-14 | 65.0% | +22.53u | **+55.6%** |
| Everything else | 117 | 28-89 | 23.9% | -32.76u | -40.0% |
| Pure M3 (M3 only) | 39 | 3-36 | 7.7% | -18.76u | -76.6% |

**Implication:** The system is profitable when concentrated on M1/M11 plays. Pure M3 without additional model confirmation is catastrophic. This validates the Triple Confirmation (M1) and Surface Edge (M11) thesis.

---

*This document is the authoritative reference for the Tennis Betting System probability model. It supersedes MODEL_ANALYSIS_GUIDE.md for all technical implementation details. The guide may be retained as a practical analysis tutorial.*
