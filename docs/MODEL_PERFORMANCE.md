# Model Performance Monitoring & Tracking Framework

**Tennis Betting System v3.1 | Quantitative Analysis Reference**

---

## Table of Contents

1. [Performance Tracking Framework](#1-performance-tracking-framework)
2. [Key Performance Indicators by Model](#2-key-performance-indicators-by-model)
3. [CLV Analysis (Closing Line Value)](#3-clv-analysis-closing-line-value)
4. [Calibration Monitoring](#4-calibration-monitoring)
5. [Performance by Dimension](#5-performance-by-dimension)
6. [Backtest Methodology](#6-backtest-methodology)
7. [Factor Attribution](#7-factor-attribution)
8. [Drawdown Analysis](#8-drawdown-analysis)
9. [Statistical Significance](#9-statistical-significance)
10. [Performance Review Schedule](#10-performance-review-schedule)
11. [Warning Signs](#11-warning-signs)
12. [Performance Report Template](#12-performance-report-template)
13. [Historical Performance Log](#13-historical-performance-log)
14. [CLV Case Studies](#14-clv-case-studies)

---

## 1. Performance Tracking Framework

### Why These Metrics Matter

A betting model's purpose is to identify situations where the true probability of an outcome exceeds the implied probability from market odds. Tracking performance is fundamentally different from most business metrics because:

- **Short-term results are dominated by variance.** A profitable model can lose money for weeks. A broken model can win money for weeks.
- **ROI alone is insufficient.** A model can show positive ROI from a single large win while being systematically wrong.
- **Closing Line Value (CLV) is the only reliable leading indicator.** Consistently beating the closing line proves edge exists, regardless of short-term P/L.

### How Metrics Are Calculated

All performance metrics derive from the `bets` table in `tennis_betting.db`. Key columns:

| Column | Type | Description |
|--------|------|-------------|
| `stake` | REAL | Units wagered (0.25 to 3.0) |
| `odds` | REAL | Decimal odds at time of placement |
| `our_probability` | REAL | Model-predicted win probability (0 to 1) |
| `implied_probability` | REAL | Market-implied probability: `1 / odds` |
| `result` | TEXT | `Win`, `Loss`, or `Void` |
| `profit_loss` | REAL | Net P/L in units (wins net of 2% Betfair commission) |
| `odds_at_close` | REAL | Closing decimal odds from last Betfair snapshot before kickoff |
| `clv` | REAL | Closing Line Value percentage |
| `model` | TEXT | Qualifying models: `"Model 3"`, `"Model 3, Model 4"`, etc. |
| `factor_scores` | TEXT | JSON of individual factor scores at time of bet placement |
| `settled_at` | TEXT | Timestamp when result was recorded |

Source: `database.py` -- `get_betting_stats()`, `get_clv_stats()`, `bets` schema.

### Profit/Loss Calculation

```
Win:  profit_loss = stake * (odds - 1) * (1 - commission)
Loss: profit_loss = -stake
Void: profit_loss = 0
```

Where `commission` = 2% (Betfair exchange basic package). Configured in `KELLY_STAKING['exchange_commission']`.

---

## 2. Key Performance Indicators by Model

### Active Models (v3.1)

The system runs **11 models** in three categories. A bet can qualify for multiple models simultaneously. At least one **hard model** is required for betting.

#### Hard Models (Required for Betting)

| Model | Name | Entry Criteria | Performance |
|-------|------|---------------|-------------|
| **M3** | Sharp Zone | Edge 5-15% | Core value bets |
| **M4** | Favorites | Our prob >= 60% | High-confidence plays |
| **M5** | Underdog | Edge >= 10%, odds 3-10, 15+ matches | **WARNING: 14.3% win rate, -13.31u** |
| **M7** | Grind | Edge 3-8% AND odds < 2.50 | Small edge + short odds |
| **M8** | Baseline | Our prob >= 55% AND odds < 2.50 | 62.5% win rate at n=16 |

#### Soft Models (Tracking Tags)

| Model | Name | Entry Criteria | Rationale |
|-------|------|---------------|-----------|
| **M2** | Data Confirmed | Any hard model + serve data + active | Data quality marker |
| **M9** | Value Zone | Odds 2.00-2.99, serve aligned, edge 5-10% | Best odds range |
| **M10** | Confident Grind | Odds < 2.20, prob >= 55%, both active | Reliability |
| **M11** | Surface Edge | Surface factor >= 0.05, odds 2.00-3.50, edge >= 5% | 61.5% win rate at n=26 |

#### Premium Model (Staking Boost)

| Model | Name | Entry Criteria | Effect |
|-------|------|---------------|--------|
| **M1** | Triple Confirmation | Hard model + serve aligned + not activity-driven | **1.5x staking** |

**M1+M11 Performance (Feb 5, 2026):** 40 bets, 65.0% win rate, +22.53u, **+55.6% ROI**. This is the proven edge.

#### Fade Model

| Model | Name | Trigger | Action |
|-------|------|---------|--------|
| **M12** | 2-0 Fade | Pure M3 or any M5, opponent odds 1.20-1.50 | Bet opponent 2-0 |

All models enforce a minimum odds floor of **1.70** and probability floor of **40%**.

Source: `config.py` -- `calculate_bet_model()`.

### KPI Definitions

#### 2.1 ROI (Return on Investment)

```
ROI = (Total Profit / Total Staked) * 100
```

**Example:**
- Total staked: 150 units across 120 bets
- Total profit: +8.5 units
- ROI = (8.5 / 150) * 100 = **+5.67%**

**Interpretation:**
| ROI Range | Assessment |
|-----------|------------|
| > +5% | Strong (with 100+ bets) |
| +2% to +5% | Positive edge likely |
| -2% to +2% | Inconclusive, need more data |
| -5% to -2% | Possible negative edge, review factors |
| < -5% | Model likely has a problem |

Source: `bet_tracker.py` -- `get_stats_by_model()`, line: `'roi': (s['profit'] / s['staked'] * 100)`.

#### 2.2 Win Rate vs Expected Win Rate

```
Actual Win Rate    = Wins / (Wins + Losses) * 100
Expected Win Rate  = Average(our_probability) * 100  (for all settled bets in the model)
```

**Interpretation:**
- If actual > expected: model is underestimating probabilities (or running hot).
- If actual < expected: model is overestimating probabilities (or running cold).
- Sustained divergence (100+ bets) indicates calibration error.

**Example:**
- Model 3: 55 wins from 100 bets = 55% actual win rate
- Average model probability for those bets = 61%
- Delta = -6% -- model is overconfident. Investigate calibration.

#### 2.3 Average Odds of Bets Placed

```
Avg Odds = SUM(odds) / COUNT(bets)
```

**Why it matters:** Average odds determine the breakeven win rate.

```
Breakeven Win Rate = 1 / Avg Odds
```

| Avg Odds | Breakeven Win Rate |
|----------|-------------------|
| 1.70 | 58.8% |
| 1.80 | 55.6% |
| 1.90 | 52.6% |
| 2.00 | 50.0% |
| 2.20 | 45.5% |
| 2.50 | 40.0% |

Source: `database.py` -- `get_betting_stats()`, `AVG(odds) as avg_odds`.

#### 2.4 Sample Size Requirements

**Minimum: 100 bets per model before drawing any conclusions.**

This is a hard rule. Fewer than 100 bets means results are dominated by variance.

| Sample Size | What You Can Conclude |
|-------------|----------------------|
| < 50 | Nothing. Pure noise. |
| 50-100 | Directional signal only (is CLV positive?) |
| 100-250 | ROI becomes somewhat meaningful |
| 250-500 | Statistically meaningful ROI, calibration analysis possible |
| 500+ | Full model evaluation, factor weight optimization |
| 1000+ | Subset analysis meaningful (by surface, odds range, tour level) |

Source: `CLAUDE.md` -- "Need 100+ bets per model before drawing conclusions."

#### 2.5 Profit/Loss in Units

```
Total P/L = SUM(profit_loss) for all settled bets in the model
```

Track both cumulative P/L (trend line) and daily P/L. The cumulative chart is generated in `bet_tracker.py` via `get_cumulative_pl()`.

#### 2.6 Yield (Profit Per Unit Staked)

Yield is synonymous with ROI in a flat-staking context. With variable staking (Kelly-based), yield provides the normalized profitability measure:

```
Yield = Total Profit / Total Units Staked
```

This differs from "profit per bet" which ignores stake sizing:

```
Profit Per Bet = Total Profit / Number of Bets
```

Both should be tracked. High yield with low profit-per-bet means the model is profitable but stake sizing is conservative. Low yield with high profit-per-bet means large stakes on fewer selections.

---

## 3. CLV Analysis (Closing Line Value)

### What CLV Measures

CLV measures whether you obtained better odds than the final market price before the event started. The closing line is the most efficient price the market produces because it incorporates all available information.

**Beating the closing line consistently is the single strongest predictor of long-term profitability.**

### How CLV Is Calculated

```
CLV% = ((closing_implied_prob - placement_implied_prob) / placement_implied_prob) * 100
```

Equivalently:

```
placement_prob = 1 / odds_at_placement
closing_prob   = 1 / odds_at_close
CLV%           = ((closing_prob - placement_prob) / placement_prob) * 100
```

**Positive CLV** = the closing line was shorter (lower odds) than what you got = you beat the market.
**Negative CLV** = the closing line was longer (higher odds) than what you got = the market moved against you.

Source: `database.py` -- `update_closing_odds()`, lines 1988-1994.

### Example Calculation

```
Placed bet at odds 2.10  =>  placement_prob = 1/2.10 = 0.4762
Closing odds were 1.95   =>  closing_prob   = 1/1.95 = 0.5128

CLV = ((0.5128 - 0.4762) / 0.4762) * 100 = +7.7%
```

This bet beat the closing line by 7.7%. The market moved in our direction, confirming the model identified genuine value.

### What Good CLV Looks Like

| Metric | Good | Concerning |
|--------|------|------------|
| Average CLV | > +1.0% | < -1.0% |
| Positive CLV % | > 55% | < 45% |
| CLV on wins | > +2.0% | < 0% |
| CLV on losses | > -2.0% | < -5.0% |

### CLV as a Leading Indicator

CLV is a leading indicator; P/L is a lagging indicator. Here is why:

- A model with +3% average CLV and -5% ROI over 80 bets is almost certainly running into negative variance. The edge is real; results will revert.
- A model with -2% average CLV and +8% ROI over 80 bets is almost certainly running into positive variance. There is no edge; results will revert.

**Decision rule:** Trust CLV over ROI when sample size is under 500 bets.

### How Closing Odds Are Captured

Each auto-cycle of the Betfair capture updates closing odds for all pending bets via `update_pending_bets_closing_odds()`. The last snapshot before settlement becomes the closing line. This data is stored in `bets.odds_at_close` and CLV in `bets.clv`.

Source: `database.py` -- `update_pending_bets_closing_odds()`, lines 2042-2099.

### CLV Stats Query

The system provides aggregate CLV stats via `get_clv_stats()`:

```
{
    'total_with_clv': 85,
    'avg_clv': +2.3,
    'positive_clv_pct': 58.8,
    'avg_clv_wins': +3.1,
    'avg_clv_losses': +1.2
}
```

Source: `database.py` -- `get_clv_stats()`, lines 2007-2040.

---

## 4. Calibration Monitoring

### What Is Calibration?

A model is well-calibrated when its predicted probabilities match actual outcomes. If the model says "60% chance of winning" for 100 different bets, approximately 60 of those should win.

### Calibration Buckets

Group bets by predicted probability into buckets and compare predicted vs actual win rate:

| Bucket | Expected Win Rate | Actual Win Rate | Count | Status |
|--------|------------------|----------------|-------|--------|
| 50-55% | 52.5% | ? | ? | ? |
| 55-60% | 57.5% | ? | ? | ? |
| 60-65% | 62.5% | ? | ? | ? |
| 65-70% | 67.5% | ? | ? | ? |
| 70-75% | 72.5% | ? | ? | ? |
| 75%+ | 80.0% | ? | ? | ? |

Source: `cloud_backtester.py` -- `calibration_analysis()`, lines 573-595.

### How to Read Calibration

```
Calibration Error = Actual Win Rate - Expected Win Rate
```

| Error Range | Interpretation |
|-------------|---------------|
| -3% to +3% | Well calibrated |
| +3% to +8% | Under-confident (model assigns lower prob than reality) |
| -3% to -8% | Over-confident (model assigns higher prob than reality) |
| > +/-8% | Significant miscalibration -- recalibrate |

**Systematically over-confident** (actual < expected in most buckets): The model needs probability shrinkage (pull predictions toward 50%). The system has a configurable shrinkage mechanism in `KELLY_STAKING['calibration']` -- currently disabled pending 500+ bet sample.

**Systematically under-confident** (actual > expected in most buckets): The model is leaving value on the table. Consider increasing Kelly fraction or removing shrinkage.

### When Recalibration Is Needed

Recalibrate when ALL of the following conditions are met:

1. Sample size exceeds 500 settled bets with tracked predictions
2. Calibration error exceeds +/-5% in 3 or more buckets consistently
3. The pattern has persisted for 4+ weeks (not just a hot/cold streak)
4. CLV confirms the direction (positive CLV with over-confidence means the model is miscalibrated, not broken)

### Calibration Settings (v3.1 -- ENABLED)

```python
# config.py -- PROBABILITY_CALIBRATION
"calibration": {
    "enabled": True,             # Now active
    "shrinkage_factor": 0.60,    # Less aggressive than 0.5
    "asymmetric": True           # Only shrink favorites (prob > 50%)
}

# config.py -- MARKET_BLEND
"market_blend": {
    "enabled": True,
    "market_weight": 0.35        # 35% market, 65% model
}
```

**Layer 1: Shrinkage (favorites only)**
```
if prob > 0.5:
    calibrated = 0.5 + shrinkage_factor × (raw - 0.5)
else:
    calibrated = raw  # Underdogs unchanged
```

With shrinkage_factor = 0.60 (asymmetric):
- 60% raw -> 56% calibrated
- 70% raw -> 62% calibrated
- 80% raw -> 68% calibrated
- 45% raw -> 45% (unchanged - underdog)

**Layer 2: Market Blend**
```
final = calibrated × 0.65 + market_implied × 0.35
```

**Combined effect:** Edges roughly halved, concentrating on bets with genuine signal.

---

## 5. Performance by Dimension

### 5.1 By Surface

Track ROI, win rate, and CLV separately for:

| Surface | Characteristics |
|---------|----------------|
| **Hard** | Most common (~65% of bets). Baseline performance. |
| **Clay** | Specialists exist. Surface factor should carry more weight. |
| **Grass** | Seasonal (June-July only). Small sample risk. |

Source: `bet_tracker.py` -- `get_stats_by_surface()`, lines 131-163.

**Key question:** Does the surface factor (`weight: 0.20`) correctly identify surface specialists? If clay ROI >> hard ROI, the surface factor is adding genuine value.

### 5.2 By Tournament Level

| Level | Characteristics | Expected Sample |
|-------|----------------|----------------|
| **Grand Slam** | Best data quality, 5-set matches, ~4 per year | Small |
| **ATP** | Good data, liquid markets | Medium |
| **WTA** | Less data historically, improving | Medium |
| **Challenger** | Thin markets, less reliable odds, data gaps | Large |
| **ITF** | Thinnest markets, least data, most variance | Large |

Source: `bet_tracker.py` -- `get_stats_by_tour()`, lines 226-273.

**Decision rule:** Need 100+ bets per tour level before drawing conclusions. Currently, Challenger-specific settings are disabled to maximize volume: `KELLY_STAKING['challenger_settings']['enabled'] = False`.

### 5.3 By Odds Range

| Range | Typical Edge Profile | Min Bets for Conclusions |
|-------|---------------------|-------------------------|
| 1.00-1.50 | Below odds floor (1.70). No bets placed. | N/A |
| 1.50-2.00 | M7/M8 territory. Win rate must exceed ~55%. | 100 |
| 2.00-3.00 | Core M3 territory. Win rate must exceed ~40%. | 100 |
| 3.00-5.00 | Higher variance, larger individual wins. | 150 |
| 5.00+ | High variance. Only bet with strong conviction. | 200 |

Source: `bet_tracker.py` -- `get_stats_by_odds_range()`, ranges defined at lines 434-440.

### 5.4 By Factor Dominance

When the model makes a prediction, individual factors contribute different amounts to the weighted advantage. Track performance when specific factors dominate:

```
Factor contribution = abs(factor_advantage * factor_weight) / abs(total_weighted_advantage)
```

If a single factor contributes > 40% of the weighted advantage, that bet is "dominated" by that factor. Track:

- ROI when form dominates (> 40% contribution)
- ROI when surface dominates
- ROI when ranking dominates
- ROI when fatigue dominates

This reveals whether the model's edge comes from one factor or is distributed. A healthy model should profit from multiple factors.

### 5.5 By Market Disagreement

How much does the model disagree with the market?

| Category | Ratio (our_prob / implied_prob) | Expected Profile |
|----------|-------------------------------|-----------------|
| Minor | < 1.5x | High volume, small edge per bet |
| Moderate | 1.5x - 2.0x | Medium volume, larger edge |
| Major | 2.0x - 3.0x | Low volume, model is strongly contrarian |
| Extreme | > 3.0x | Red flag -- model may be miscalibrated |

Source: `bet_tracker.py` -- `get_stats_by_disagreement()`, lines 524-584.

### 5.6 By Stake Size

| Stake | Description |
|-------|-------------|
| 0.5u | Minimum bet (low edge or reduced confidence) |
| 1.0u | Standard bet |
| 1.5u | Above average edge |
| 2.0u | High confidence (subject to data quality checks) |
| 2.5u | Very high confidence |
| 3.0u | Maximum cap |

Source: `bet_tracker.py` -- `get_stats_by_stake_size()`, ranges defined at lines 479-486.

Stakes >= 2.0u undergo additional data quality checks (`config.py` -- `check_data_quality_for_stake()`), including minimum match counts, Tennis Explorer verification, and form comparison.

---

## 6. Backtest Methodology

### How the Cloud Backtester Works

The backtester (`cloud_backtester.py`) processes historical matches through the full 9-factor analysis model to simulate what the system would have bet and whether those bets would have been profitable.

**Pipeline for each match:**

1. **Random player assignment.** Winner and loser are randomly assigned to player1/player2 slots to avoid winner bias (knowing which player won would leak information).

2. **Surface re-derivation.** Tournament surface is derived from the tournament name using the centralised `get_tournament_surface()` function, not from stored data (which may have corruption).

3. **Odds estimation.** Real historical odds are used when available (`--odds-path` flag). Otherwise, a ranking-based proxy generates odds:
   ```
   elo = 2500 - 150 * log2(ranking)
   p1_win_prob = 1 / (1 + 10^((p2_elo - p1_elo) / 400))
   odds = 1.05 / p_win  (with 5% overround)
   ```

4. **Full model analysis.** Calls `MatchAnalyzer.calculate_win_probability()` with rank overrides to use match-time rankings (not current rankings).

5. **Model qualification.** Checks if the predicted bet qualifies for M3/M4/M7/M8.

6. **Staking.** Uses Kelly-based staking through `find_value()` to determine theoretical stake size.

7. **P/L calculation.** Applies 2% Betfair commission to winning bets.

8. **Factor accuracy tracking.** Records which individual factors correctly predicted the winner.

Source: `cloud_backtester.py` -- `BacktestRunner.process_match()`, lines 190-341.

### Lookahead Bias Fix

**Problem:** The original backtester used current player rankings when analysing historical matches. A player ranked #15 today might have been ranked #80 at the time of the match. This inflates the model's apparent accuracy.

**Fix:** The backtester passes `p1_rank_override` and `p2_rank_override` from the match record, forcing the model to use match-time rankings instead of current rankings. This applies to:
- Ranking factor calculation
- Elo conversion for probability estimation
- Performance Elo factor
- Breakout detection

Source: `cloud_backtester.py` line 246-253; `match_analyzer.py` -- `calculate_win_probability()` parameters `p1_rank_override`, `p2_rank_override`.

### What Backtest Results Show

The backtester generates:

| Section | Description |
|---------|-------------|
| Overall accuracy | Prediction accuracy across all matches |
| Model performance | ROI, win rate, profit per model (M3/M4/M7/M8) |
| Factor accuracy | Per-factor prediction accuracy (form, surface, ranking, etc.) |
| Calibration | Predicted vs actual win rate by probability bucket |
| Surface breakdown | Performance by hard/clay/grass |
| Odds range breakdown | Performance by odds bracket |
| Odds source breakdown | Real odds vs ranking proxy performance |

Source: `cloud_backtester.py` -- `BacktestSummary` class, lines 492-800.

### Limitations of Backtesting

1. **Odds proxy is imprecise.** Ranking-based odds do not reflect market-specific factors (injuries, match conditions, news). Performance on proxy odds may differ from real betting. Always prioritize results with real historical odds (`odds_source = 'real'`).

2. **Survivorship bias.** Only matches in the database are tested. Walkovers, retirements, and cancelled matches may be excluded, skewing results.

3. **Data staleness.** Form, fatigue, and momentum calculations use the full database, which may include data that was not available at the time of the historical match.

4. **Liquidity not modelled.** The backtester assumes all bets are placeable at the calculated odds. In practice, Challenger and ITF markets may not have sufficient liquidity.

5. **No closing line data for historical matches.** CLV cannot be calculated in backtests, removing the most reliable edge indicator.

---

## 7. Factor Attribution

### Factor Weights (v3.1 -- 8 Active Factors)

| Factor | Weight | Signal Source |
|--------|--------|--------------|
| `surface` | **22%** | Career + recent (2yr) surface-specific win rates |
| `form` | 20% | Recent match results, recency-weighted, tournament-level-adjusted |
| `fatigue` | **17%** | Days rest, match load, match difficulty |
| `ranking` | 13% | ATP/WTA ranking converted to Elo |
| `performance_elo` | **13%** | Rolling 12-month Elo from actual results |
| `recent_loss` | 8% | Penalty for recent losses (3d/7d/5-set) |
| `h2h` | 5% | Head-to-head record on surface |
| `momentum` | 2% | Win streak on same surface in last 14 days |
| `injury` | **0%** | DEPRECATED -- replaced by Activity Edge Modifier |
| `opponent_quality` | 0% | REMOVED -- redundant with form |
| `recency` | 0% | REMOVED -- already in form's decay |

**Edge Modifiers (v3.1):** In addition to weighted factors, two post-probability modifiers adjust edge:
- **Serve Edge Modifier:** Up to -20% edge reduction when serve data conflicts with pick
- **Activity Edge Modifier:** Up to -40% edge reduction for returning/inactive players

Source: `config.py` -- `DEFAULT_ANALYSIS_WEIGHTS`, `SERVE_ALIGNMENT_SETTINGS`, `ACTIVITY_SETTINGS`.

### How Factor Advantage Is Calculated

Each factor produces an advantage score in the range [-1, +1] where positive values favour Player 1. These are then weighted and summed:

```
weighted_advantage = SUM(factor_advantage[i] * weight[i])
model_probability  = 1 / (1 + exp(-3 * weighted_advantage))    # logistic with k=3
```

Source: `match_analyzer.py` -- `calculate_win_probability()`, lines 2062-2069.

### Factor Accuracy Analysis

The backtester tracks whether each factor's directional prediction was correct:

```
Factor correct = (factor favours P1 AND P1 won) OR (factor favours P2 AND P2 won)
```

**Interpretation guidelines:**

| Factor Accuracy | Verdict | Action |
|----------------|---------|--------|
| > 60% | STRONG | Consider increasing weight |
| 50-60% | OK | Weight is appropriate |
| < 50% | HARMFUL | Factor is anti-predictive. Reduce weight or investigate. |

Source: `cloud_backtester.py` -- `BacktestSummary.factor_accuracy()`, lines 542-571.

### Factor Weight Sensitivity Analysis

To assess sensitivity, the system provides multiple weight profiles for comparison:

| Profile | Form | Surface | Ranking | Fatigue | Perf Elo | Other |
|---------|------|---------|---------|---------|----------|-------|
| **Default** | 0.20 | 0.20 | 0.13 | 0.15 | 0.12 | 0.20 |
| **Form Focus** | 0.35 | 0.15 | 0.10 | 0.10 | 0.10 | 0.20 |
| **Surface Focus** | 0.15 | 0.35 | 0.10 | 0.10 | 0.10 | 0.20 |
| **Ranking Focus** | 0.15 | 0.15 | 0.25 | 0.10 | 0.15 | 0.20 |
| **Fatigue Focus** | 0.15 | 0.15 | 0.10 | 0.30 | 0.10 | 0.20 |
| **Psychology Focus** | 0.20 | 0.15 | 0.10 | 0.10 | 0.10 | 0.35 |

Source: `config.py` -- `MODEL_WEIGHT_PROFILES`.

**Analysis method:** Run backtests with each profile. If a non-default profile consistently outperforms, consider adjusting default weights toward that profile. Require 500+ match backtests before making weight changes.

### Identifying What Drives Performance

Query the `match_analyses` table for settled analyses to find patterns:

1. **Factor dominance on winning bets:**
   - For each winning bet, identify which factor had the largest absolute `factor_advantage * weight`.
   - If 60% of wins are driven by surface factor, the model's edge may be surface-specific.

2. **Factor alignment:**
   - When 3+ factors agree (all favour the same player), win rate should be highest.
   - Track win rate vs number of agreeing factors.

3. **Loss quality adjustment impact:**
   - The form and surface factors include a "loss quality" stability adjustment based on who players lose to.
   - Track whether bets with non-zero loss quality adjustments perform better.

---

## 8. Drawdown Analysis

### Maximum Drawdown Calculation

Maximum drawdown measures the largest peak-to-trough decline in cumulative P/L:

```
For each point in the P/L series:
    peak = max(cumulative P/L up to this point)
    drawdown = peak - current cumulative P/L

Maximum Drawdown = max(all drawdowns)
```

**Example:**
```
Cumulative P/L: [0, +2, +5, +3, +1, -1, +2, +6, +4]
Peaks:          [0, +2, +5, +5, +5, +5, +5, +6, +6]
Drawdowns:      [0,  0,  0,  2,  4,  6,  3,  0,  2]
Maximum Drawdown = 6 units (from peak +5 to trough -1)
```

### Expected Drawdown for Given Sample Size

For a model with true ROI of R% and average bet size S units at average odds O:

```
Expected max drawdown (units) ~ S * sqrt(N) * sqrt(O - 1) * C
```

Where:
- N = number of bets
- O = average odds
- C = constant (~1.5 for 95th percentile)

**Rule of thumb for 1-unit flat staking at odds ~2.00:**

| Bets Placed | Expected Max Drawdown (95%) |
|-------------|---------------------------|
| 50 | ~10-12 units |
| 100 | ~14-17 units |
| 200 | ~20-24 units |
| 500 | ~32-38 units |

### When Drawdowns Are Statistically Significant

A drawdown is **within normal variance** if:

```
Drawdown < 2 * sqrt(N * p * (1 - p)) * avg_stake * (avg_odds - 1)
```

Where p = expected win rate, N = number of bets in the drawdown period.

**Simplified decision rule:**

| Drawdown Duration (bets) | Acceptable Drawdown (units) | Alarm Level (units) |
|--------------------------|---------------------------|-------------------|
| 20 | 8 | 15 |
| 50 | 15 | 25 |
| 100 | 20 | 35 |
| 200 | 30 | 50 |

**Key distinction:** A 15-unit drawdown over 50 bets with positive CLV is normal variance. A 15-unit drawdown over 50 bets with negative CLV suggests model degradation.

---

## 9. Statistical Significance

### When Is ROI Statistically Significant?

**Binomial test approach:**

Under the null hypothesis that the model has no edge, the expected win rate equals the breakeven win rate:

```
p0 = 1 / avg_odds  (breakeven probability, accounting for commission)
```

Given N bets and W wins:

```
z = (W/N - p0) / sqrt(p0 * (1-p0) / N)
```

| z-score | p-value | Confidence |
|---------|---------|------------|
| > 1.65 | < 0.05 | 95% -- statistically significant |
| > 1.96 | < 0.025 | 97.5% -- strong significance |
| > 2.58 | < 0.005 | 99.5% -- very strong significance |

**Example:**
```
N = 200 bets, W = 112 wins, Avg odds = 1.95
p0 = 1/1.95 = 0.513 (breakeven)
Actual win rate = 112/200 = 0.560

z = (0.560 - 0.513) / sqrt(0.513 * 0.487 / 200)
z = 0.047 / 0.0353
z = 1.33

p-value = 0.092 -> NOT statistically significant at 95% level
```

### Minimum Sample Sizes for Significance

For a model with a true edge of E% above breakeven:

| True Edge Above Breakeven | Bets for 95% Confidence | Bets for 99% Confidence |
|--------------------------|------------------------|------------------------|
| 2% | ~2,500 | ~4,200 |
| 3% | ~1,100 | ~1,900 |
| 5% | ~400 | ~670 |
| 8% | ~160 | ~260 |
| 10% | ~100 | ~170 |

**Reality check:** Most betting edges are 2-5%. This means 400-2,500 bets are needed for statistical confirmation. This is why CLV is preferred as an early indicator -- it converges faster than P/L.

### Confidence Intervals for ROI

```
ROI 95% CI = ROI +/- 1.96 * sqrt(variance_of_returns / N)
```

For practical approximation with variable staking:

```
ROI 95% CI ~ ROI +/- 2 * avg_odds * sqrt(1/N)
```

**Example:**
```
N = 150 bets, ROI = +4.2%, Avg odds = 2.00

CI width ~ 2 * 2.00 * sqrt(1/150) = 2 * 2.00 * 0.0816 = 0.327 = 32.7%

95% CI = (+4.2% - 32.7%, +4.2% + 32.7%) = (-28.5%, +36.9%)
```

At 150 bets with average odds of 2.00, the confidence interval is enormous. This illustrates why 100+ bets is a minimum, not a target.

---

## 10. Performance Review Schedule

### Daily Review

| Metric | Source | Action |
|--------|--------|--------|
| Today's P/L | Bet tracker main dashboard | Log in session log |
| Today's CLV (average) | `bets.clv` for today's settled bets | Flag if negative |
| Pending bets count | Bet tracker pending tab | Ensure closing odds are updating |
| Any errors/failures | Application logs | Investigate immediately |

### Weekly Review (Every Monday)

| Metric | Source | Action |
|--------|--------|--------|
| Weekly P/L by day | `get_weekly_stats()` | Log in weekly report |
| ROI by model (M3/M4/M7/M8) | `get_stats_by_model()` | Compare to previous weeks |
| Win rate by model | `get_stats_by_model()` | Compare to expected |
| Average CLV (week) | `get_clv_stats()` | Trend analysis |
| Positive CLV % (week) | `get_clv_stats()` | Should be > 50% |
| Bets by tour level | `get_stats_by_tour()` | Volume distribution |
| Bets by odds range | `get_stats_by_odds_range()` | Check for drift |

### Monthly Review (First Monday of Month)

| Metric | Source | Action |
|--------|--------|--------|
| Full P/L report | `get_stats_by_month()` | Month-over-month trend |
| Calibration check | Backtest calibration analysis | Assess bucket accuracy |
| Factor accuracy | Backtest factor accuracy | Identify weak/strong factors |
| Surface performance | `get_stats_by_surface()` | Seasonal patterns |
| Tour level performance | `get_stats_by_tour()` | Level-specific issues |
| Drawdown assessment | Cumulative P/L chart | Compare to expected range |
| CLV trend (30-day rolling) | Custom query on `bets.clv` | Leading indicator check |
| Weight profile comparison | Backtest with multiple profiles | Consider adjustments |
| Recalibration decision | All above metrics combined | Only if all criteria met |

### Quarterly Review

| Metric | Source | Action |
|--------|--------|--------|
| Full backtest re-run | `cloud_backtester.py` | Baseline update |
| Factor weight review | Backtest factor accuracy + live | Formal weight adjustment decision |
| Model criteria review | Config review | Adjust thresholds if warranted |
| Odds range weighting | `get_stats_by_odds_range()` | Enable if 1000+ bets reached |
| Tour level restrictions | `get_stats_by_tour()` | Enable if 1000+ bets reached |

---

## 11. Warning Signs

### Red Flag: Negative CLV Trend

| Signal | Threshold | Severity |
|--------|-----------|----------|
| Average CLV negative for 1 week | < -1% | MONITOR |
| Average CLV negative for 2 weeks | < -1% | WARNING |
| Average CLV negative for 4 weeks | < -1% | ACTION REQUIRED |
| Positive CLV % below 40% | 2-week rolling | ACTION REQUIRED |

**Possible causes:**
- Model probabilities are drifting (data quality issue)
- Market has adapted to the pattern the model exploits
- Odds capture timing has changed (getting stale odds)

### Red Flag: Calibration Drift

| Signal | Threshold | Severity |
|--------|-----------|----------|
| 2+ buckets off by > 5% | Monthly check | MONITOR |
| 3+ buckets off by > 5% | Monthly check | WARNING |
| Systematic over-confidence | All buckets show actual < expected | ACTION REQUIRED |
| Systematic under-confidence | All buckets show actual > expected | REVIEW (may increase stake) |

### Red Flag: Sustained Negative ROI Beyond Variance

```
If ROI < -10% AND N > 100 AND CLV < 0:
    -> Model has no edge. Stop and investigate.

If ROI < -10% AND N > 100 AND CLV > +1%:
    -> Unlucky variance. Continue but monitor closely.

If ROI < -5% AND N > 250:
    -> Regardless of CLV, review all factors and model criteria.
```

### Red Flag: Single Factor Domination

If > 60% of winning bets are dominated by a single factor:

| Dominant Factor | Risk | Action |
|----------------|------|--------|
| Ranking | Model is just following rankings -- market prices this already | Reduce ranking weight |
| Form | Model is chasing hot streaks -- may regress | Validate form calculation |
| Surface | Possible genuine edge -- validate with CLV | Monitor, potentially increase weight |
| Fatigue | High-value signal if correct -- small sample risk | Validate fatigue data quality |

### Red Flag: Stake Distribution Issues

| Signal | Threshold | Action |
|--------|-----------|--------|
| > 50% of bets at max stake (3u) | Rolling 2-week | Kelly fraction too aggressive |
| > 50% of bets at min stake (0.25u) | Rolling 2-week | Edges are too thin or Kelly fraction too conservative |
| Large stakes losing, small stakes winning | Rolling 100 bets | Data quality check failing on high-stake bets |

### Red Flag: Disappearing Edge by Tour Level

If one tour level (e.g., Challengers) shows consistent negative ROI + negative CLV while others are profitable:

- The model may not generalise to that level
- Data quality may be worse at lower levels
- Market efficiency may differ
- Consider level-specific weight adjustments

---

## 12. Performance Report Template

### Weekly Performance Report

```
================================================================
WEEKLY PERFORMANCE REPORT
Week: [YYYY-MM-DD] to [YYYY-MM-DD]
Generated: [timestamp]
================================================================

SUMMARY
-------
Total bets placed:    [N]
Total bets settled:   [N]
Win/Loss:             [W]-[L] ([win_rate]%)
Weekly P/L:           [+/-X.XX] units
Weekly ROI:           [+/-X.X]%
Cumulative P/L:       [+/-X.XX] units
Cumulative ROI:       [+/-X.X]%

CLV METRICS
-----------
Bets with CLV data:   [N]
Average CLV:          [+/-X.X]%
Positive CLV %:       [X.X]%
CLV (wins):           [+/-X.X]%
CLV (losses):         [+/-X.X]%
CLV trend (4-week):   [Improving / Stable / Declining]

MODEL BREAKDOWN
---------------
Model   | Bets | W-L    | Win%  | P/L     | ROI    | Avg CLV
--------|------|--------|-------|---------|--------|--------
M3      | [N]  | [W]-[L]| [X]%  | [+/-X]u | [X]%   | [X]%
M4      | [N]  | [W]-[L]| [X]%  | [+/-X]u | [X]%   | [X]%
M7      | [N]  | [W]-[L]| [X]%  | [+/-X]u | [X]%   | [X]%
M8      | [N]  | [W]-[L]| [X]%  | [+/-X]u | [X]%   | [X]%

DIMENSIONAL BREAKDOWN (this week)
----------------------------------
By Surface:     Hard [N] bets [+/-X]u | Clay [N] bets [+/-X]u | Grass [N] bets [+/-X]u
By Tour Level:  GS [N] | ATP [N] | WTA [N] | Ch [N] | ITF [N]
By Odds Range:  1.70-2.00 [N] | 2.00-3.00 [N] | 3.00+ [N]

DRAWDOWN STATUS
---------------
Current drawdown:     [X] units from peak
Max drawdown (all-time): [X] units
Bets since last peak: [N]
Status:               [Normal Variance / Elevated / Critical]

ALERTS & FLAGS
--------------
[List any warning signs triggered this week]
[List any notable wins/losses]
[List any data quality issues encountered]

NOTES
-----
[Analyst commentary on the week's performance]
[Any upcoming events that may impact performance]
================================================================
```

### Monthly Performance Report

The monthly report includes everything above, plus:

```
================================================================
MONTHLY PERFORMANCE REPORT (additional sections)
================================================================

CALIBRATION CHECK
-----------------
Bucket     | Count | Expected | Actual | Diff
50-55%     | [N]   | 52.5%    | [X]%   | [+/-X]%
55-60%     | [N]   | 57.5%    | [X]%   | [+/-X]%
60-65%     | [N]   | 62.5%    | [X]%   | [+/-X]%
65-70%     | [N]   | 67.5%    | [X]%   | [+/-X]%
70-75%     | [N]   | 72.5%    | [X]%   | [+/-X]%
75%+       | [N]   | 80.0%    | [X]%   | [+/-X]%
Calibration verdict: [Well Calibrated / Over-confident / Under-confident]

FACTOR PERFORMANCE (from backtest or live tracking)
----------------------------------------------------
Factor           | Accuracy | Weight | Verdict
form             | [X]%     | 20%    | [STRONG/OK/HARMFUL]
surface          | [X]%     | 20%    | [STRONG/OK/HARMFUL]
ranking          | [X]%     | 13%    | [STRONG/OK/HARMFUL]
fatigue          | [X]%     | 15%    | [STRONG/OK/HARMFUL]
performance_elo  | [X]%     | 12%    | [STRONG/OK/HARMFUL]
recent_loss      | [X]%     | 8%     | [STRONG/OK/HARMFUL]
h2h              | [X]%     | 5%     | [STRONG/OK/HARMFUL]
injury           | [X]%     | 5%     | [STRONG/OK/HARMFUL]
momentum         | [X]%     | 2%     | [STRONG/OK/HARMFUL]

STATISTICAL SIGNIFICANCE CHECK
-------------------------------
Total settled bets:    [N]
Average odds:          [X.XX]
Breakeven win rate:    [X.X]%
Actual win rate:       [X.X]%
z-score:               [X.XX]
p-value:               [X.XXX]
Significance (95%):    [Yes / No]

RECOMMENDATIONS
---------------
[ ] Continue current weights
[ ] Adjust [factor] weight from [X] to [Y]
[ ] Enable calibration (if 500+ bets reached)
[ ] Enable tour-level restrictions (if 1000+ bets reached)
[ ] Enable odds range weighting (if 1000+ bets reached)
[ ] Investigate [specific issue]
================================================================
```

---

## 13. Historical Performance Log

### Model Change Log Template

Use this template to record every change to the model and its measured impact:

```
================================================================
MODEL CHANGE LOG
================================================================

Entry #: [sequential number]
Date: [YYYY-MM-DD]
Version: [e.g., v2.61]
Change Type: [Weight Change / New Factor / Bug Fix / Threshold Change / Calibration]

DESCRIPTION
-----------
What was changed:
[Detailed description of the change]

Why it was changed:
[Evidence that prompted the change -- backtest results, CLV analysis, etc.]

BEFORE
------
[Relevant config values / weights / thresholds before the change]

AFTER
-----
[Relevant config values / weights / thresholds after the change]

EXPECTED IMPACT
---------------
[What improvement is expected -- higher accuracy, better calibration, etc.]

MEASURED IMPACT (fill in after 100+ bets post-change)
-----------------------------------------------------
Bets since change:    [N]
ROI before change:    [X]% (last [N] bets)
ROI after change:     [X]% (first [N] bets post-change)
CLV before change:    [X]%
CLV after change:     [X]%
Win rate before:      [X]%
Win rate after:       [X]%

VERDICT (fill in after 250+ bets post-change)
----------------------------------------------
[ ] Improvement confirmed
[ ] No measurable difference
[ ] Regression -- consider reverting
[ ] Inconclusive -- need more data

NOTES
-----
[Any additional observations]
================================================================
```

### Example Historical Entry

```
================================================================
Entry #: 001
Date: 2026-01-26
Version: v2.0

DESCRIPTION
-----------
What: Simplified from 8 models to 4 (M3, M4, M7, M8). Removed M1 (all bets),
      M2 (tiered), M5 (underdogs), M6 (large edge). Added 1.70 odds floor.
Why:  Models 1/2/5/6 showed no edge in preliminary data. Focus on models with
      theoretical basis for edge.

BEFORE: 8 models, no odds floor
AFTER:  4 models (M3: 5-15% edge, M4: prob>=60%, M7: 3-8% edge + odds<2.50,
        M8: prob>=55% + odds<2.50), 1.70 odds floor

MEASURED IMPACT: Pending (< 100 bets)
================================================================

Entry #: 002
Date: 2026-01-26
Version: v2.0

DESCRIPTION
-----------
What: Removed opponent_quality and recency factors (set weight to 0%).
      Form absorbs opponent quality signal. Recency is already in form's decay.
Why:  Backtest showed these factors at < 50% accuracy (harmful).

BEFORE: 10 active factors
AFTER:  8 active factors (opponent_quality=0%, recency=0%)

MEASURED IMPACT: Pending (< 100 bets)
================================================================

Entry #: 003
Date: 2026-01-30
Version: v2.5+

DESCRIPTION
-----------
What: Added performance_elo factor (12% weight). Reduced ranking (-7%) and
      form (-5%) to compensate. Performance Elo uses rolling 12-month results
      with tournament-level K-factors.
Why:  Performance Elo captures actual results vs ranking expectations.
      Rankings update slowly; Elo responds to recent performance.

BEFORE: ranking=20%, form=25%, no performance_elo
AFTER:  ranking=13%, form=20%, performance_elo=12%

MEASURED IMPACT: Pending (< 100 bets)
================================================================
```

---

## 14. CLV Case Studies

### Case Study 1: Mandlik vs Stoiana — Return Stats as Hidden Edge

**Bet #1202 | 2026-01-31 | ITF San Diego | Hard | Model 3**

| Field | Value |
|-------|-------|
| Selection | Elizabeth Mandlik |
| Odds placed | 2.84 |
| Closing odds | 2.52 |
| CLV | **+12.7%** |
| Our probability | 44.5% |
| Stake | 0.5u |
| Result | **Win** |

#### Why This Bet Is Significant

On paper, most traditional stats favoured the opponent (Mary Stoiana):
- Better hard court win rate: 68.9% vs 58.8%
- Better ITF record: 73.0% vs 68.6%
- Better recent form: 8-2 last 10 vs 5-5
- Higher performance Elo: 1434 vs 1361
- Better 3-set record: 69.2% (9-4) vs 52.4% (11-10)
- More match volume: 16 wins in 3 months vs 7

Yet the model identified Mandlik as a value bet at 2.84, and the market confirmed by moving to 2.52 — a 12.7% CLV.

#### What CLV Tells Us

The +12.7% CLV means we got the bet at significantly better odds than the closing line. Since beating the closing line is the single most reliable indicator of long-term profitability (even more reliable than short-term ROI), this bet demonstrates the model can identify value before the market fully prices it in.

The market didn't just agree with the model — it moved *past* the model's implied fair odds. Sharp money came in on Mandlik between placement and close.

#### Tennis Ratio Serve Stats — What Predicted the Winner

The Tennis Ratio data collected for both players reveals which stats most strongly corresponded to the actual outcome:

**Return stats pointed strongly to Mandlik (the winner):**

| Stat | Mandlik | Stoiana | Gap | Signal |
|------|---------|---------|-----|--------|
| Return Games Won % | **44.15%** | 36.84% | +7.31% | Very strong |
| Dominance Ratio | **1.10** | 0.91 | +0.19 | Very strong |
| Return 2nd Won % | **57.65%** | 53.64% | +4.01% | Strong |
| BP Converted % | **50.34%** | 46.91% | +3.43% | Strong |
| Return 1st Won % | **42.62%** | 39.22% | +3.40% | Strong |
| 1st Serve Won % | **63.33%** | 60.13% | +3.20% | Moderate |
| Tiebreak Won % | **66.67%** | 60.00% | +6.67% | Moderate |

**Serve stats pointed to Stoiana (the loser):**

| Stat | Stoiana | Mandlik | Gap | Signal |
|------|---------|---------|-----|--------|
| DFs/Match | **2.79** | 5.09 | -2.30 | Strong (lower better) |
| 2nd Serve Won % | **48.49%** | 43.94% | +4.55% | Strong |
| 1st Serve % | **62.93%** | 57.65% | +5.28% | Moderate |
| BP Saved % | **55.87%** | 52.66% | +3.21% | Moderate |
| Service Games Won % | **62.70%** | 61.28% | +1.42% | Weak |

#### Key Insight: Return > Serve at ITF Level

The serve stats were roughly even or slightly favoured Stoiana, but the **return stats overwhelmingly favoured Mandlik**. The three most predictive Tennis Ratio metrics for this match were:

1. **Return Games Won %** (+7.31% gap) — The single biggest differentiator. Mandlik breaks serve far more frequently. In WTA/ITF tennis where serve is less dominant, the returner's ability to convert is often decisive.

2. **Dominance Ratio** (1.10 vs 0.91) — Mandlik wins more total points than she loses (ratio > 1.0). Stoiana loses more than she wins (ratio < 1.0). This is a fundamental quality indicator that the headline win/loss record masked because Stoiana was beating weaker opponents.

3. **BP Converted %** (+3.43% gap) — Mandlik converts break points at a higher rate, which translates the return game advantage into actual games won.

#### Implications for Model Development

This case study supports adding serve/return stats (currently display-only) as a weighted factor in the model. Specifically:

- **Return Games Won %** and **Dominance Ratio** appear to be the most predictive single metrics
- At ITF/lower levels where serve is less dominant, return stats may be even more valuable than at ATP level
- The model correctly identified Mandlik as value via form/surface/perf_elo factors, but incorporating serve stats could have identified the edge earlier or with higher confidence
- Stoiana's inflated win rate (from weaker opposition) was correctly discounted by the model, but the serve stats provide an independent confirmation of why — her dominance ratio is below 1.0

---

### Case Study 2: Svajda vs Shimabukuro — When Serve Stats Would Have Warned Us Off

**Bet #1203 | 2026-01-31 | San Diego Challenger | Hard | Model 3**

| Field | Value |
|-------|-------|
| Selection | Sho Shimabukuro |
| Odds placed | 2.68 |
| Closing odds | 2.72 |
| CLV | **-1.5%** (negative — market moved against us) |
| Our probability | 44.6% |
| Stake | 1.0u |
| Result | Pending |

#### Why This Bet Is Significant (Contrast to Case Study 1)

This is the opposite scenario to the Mandlik bet. The model identified Shimabukuro as value, but the Tennis Ratio serve stats overwhelmingly favour the opponent — and the CLV is negative, meaning the market disagreed.

#### Traditional Stats — Favour Svajda

| Stat | Svajda | Shimabukuro |
|------|--------|-------------|
| Hard court record | **64.7%** (33-18) | 50.0% (15-15) |
| Performance Elo | **1560.8** (rank 71) | 1449.6 (rank 130) |
| Official ranking | 143 | 144 |

Rankings are nearly identical (143 vs 144), but the performance Elo gap is massive — 111 points. Svajda's hard court win rate (64.7%) vs Shimabukuro's coin-flip 50.0% is a significant red flag.

#### Tennis Ratio Serve Stats — Overwhelmingly Favour Svajda

**Serve stats — Svajda dominant across the board:**

| Stat | Svajda | Shimabukuro | Gap | Favours |
|------|--------|-------------|-----|---------|
| Dominance Ratio | **1.20** | 1.01 | +0.19 | Svajda (very strong) |
| 1st Serve Won % | **73.08%** | 71.73% | +1.35% | Svajda |
| 2nd Serve Won % | **54.34%** | 51.96% | +2.38% | Svajda |
| Aces/Match | **6.82** | 5.79 | +1.03 | Svajda |
| DFs/Match | **2.18** | 3.24 | -1.06 | Svajda (lower better) |
| Service Games Won % | **81.17%** | 79.67% | +1.50% | Svajda |
| BP Converted % | **45.48%** | 44.66% | +0.82% | Svajda |
| Return 2nd Won % | **51.56%** | 49.04% | +2.52% | Svajda |

**Shimabukuro's only advantages:**

| Stat | Shimabukuro | Svajda | Gap | Favours |
|------|-------------|--------|-----|---------|
| Return 1st Won % | **32.91%** | 30.22% | +2.69% | Shimabukuro |
| BP Saved % | **62.78%** | 60.73% | +2.05% | Shimabukuro |
| Tiebreak Won % | **66.67%** | 59.09% | +7.58% | Shimabukuro |

#### Key Insight: Dominance Ratio as a Warning Signal

The dominance ratio tells the same story in both case studies, but from opposite directions:

| Case Study | Our Selection | DR | Opponent | DR | CLV | Outcome |
|------------|--------------|-----|----------|-----|-----|---------|
| 1 (Mandlik) | Mandlik | **1.10** | Stoiana | 0.91 | **+12.7%** | Win |
| 2 (Shimabukuro) | Shimabukuro | 1.01 | Svajda | **1.20** | **-1.5%** | Pending |

In Case Study 1, dominance ratio pointed *toward* our selection and CLV was strongly positive. In Case Study 2, dominance ratio points *against* our selection and CLV is negative. The pattern holds.

Shimabukuro's dominance ratio of 1.01 means he barely wins more points than he loses — he's right on the edge. Svajda at 1.20 comfortably outpoints his opponents. At Challenger level where the serve is more relevant than at ITF, this gap is significant.

#### What Shimabukuro Has Going For Him

- **Tournament momentum**: 3-0 at San Diego including wins over Kozlov (ranked) and Hijikata
- **3-set resilience**: 58.3% (14-10) vs Svajda's 53.6% (15-13)
- **Tiebreak specialist**: 66.67% vs 59.09% — meaningful edge if sets are tight
- **BP Saved**: 62.78% vs 60.73% — holds serve slightly better under pressure

The model saw value because rankings are almost identical and Shimabukuro's recent form was strong. But the deeper serve/return stats suggest Svajda is the fundamentally better hard court player.

#### What This Tells Us About a Future Serve Stats Factor

If serve/return stats had been a weighted factor in the model:
- **Case Study 1 (Mandlik)**: Would have *increased* confidence in the bet — serve stats aligned with model, CLV confirmed
- **Case Study 2 (Shimabukuro)**: Would have *reduced* confidence or stake — serve stats pointed against model, CLV confirmed the warning

The two cases together suggest **dominance ratio** could function as a filter or confidence modifier:
- DR > 1.0 for our selection + DR < 1.0 for opponent → **high confidence** (Mandlik pattern)
- DR near 1.0 for our selection + DR >> 1.0 for opponent → **reduce stake or skip** (Shimabukuro pattern)

This would not require adding a full new factor — it could work as a data quality gate similar to the existing `check_data_quality_for_stake()` function, or as a confidence adjustment that modifies stake sizing.

---

### Cross-Study Summary

| Metric | Most Predictive? | Notes |
|--------|-----------------|-------|
| **Dominance Ratio** | Yes — strongest signal in both cases | Above/below 1.0 is a fundamental quality indicator. Correctly pointed to the likely winner in both matches. |
| **Return Games Won %** | Yes — especially at ITF/lower levels | The biggest single-stat gap in Case Study 1 (+7.31%). Less differentiated in Case Study 2 (Challenger level, serves matter more). |
| **CLV direction** | Yes — confirmed serve stats in both cases | Positive CLV aligned with favourable serve stats (CS1). Negative CLV aligned with unfavourable serve stats (CS2). |
| **Hard court win rate** | Misleading without context | Stoiana's 68.9% was inflated by weak opposition (DR < 1.0). Svajda's 64.7% was backed by DR of 1.20. Surface record needs to be read alongside dominance ratio. |
| **Tiebreak Won %** | Useful but not decisive | Shimabukuro has 66.67% in both matches but that alone doesn't override a 0.19 dominance ratio gap. |

---

## Appendix A: Key Source File Reference

| File | Relevant Functions |
|------|--------------------|
| `config.py` | `calculate_bet_model()`, `DEFAULT_ANALYSIS_WEIGHTS`, `KELLY_STAKING`, `MODEL_WEIGHT_PROFILES` |
| `bet_tracker.py` | `get_stats_by_model()`, `get_stats_by_surface()`, `get_stats_by_tour()`, `get_stats_by_odds_range()`, `get_stats_by_disagreement()`, `get_weekly_stats()` |
| `database.py` | `get_betting_stats()`, `get_clv_stats()`, `update_closing_odds()`, `log_match_analysis()`, `settle_match_analyses()`, `match_analyses` table |
| `match_analyzer.py` | `calculate_win_probability()`, factor calculation methods, `find_value()` |
| `cloud_backtester.py` | `BacktestRunner.process_match()`, `BacktestSummary` class (calibration, factor accuracy, model performance) |

## Appendix B: SQL Queries for Custom Analysis

### Rolling 30-Day CLV

```sql
SELECT
    DATE(settled_at) as date,
    COUNT(*) as bets,
    AVG(clv) as avg_clv,
    SUM(CASE WHEN clv > 0 THEN 1.0 ELSE 0.0 END) / COUNT(*) * 100 as positive_pct
FROM bets
WHERE clv IS NOT NULL
AND result IN ('Win', 'Loss')
AND settled_at >= DATE('now', '-30 days')
GROUP BY DATE(settled_at)
ORDER BY date;
```

### Model-Specific ROI Over Time

```sql
SELECT
    strftime('%Y-%W', settled_at) as week,
    model,
    COUNT(*) as bets,
    SUM(stake) as staked,
    SUM(profit_loss) as profit,
    ROUND(SUM(profit_loss) / SUM(stake) * 100, 1) as roi
FROM bets
WHERE result IN ('Win', 'Loss')
AND model IS NOT NULL
GROUP BY week, model
ORDER BY week DESC;
```

### Factor Score Distribution for Winning vs Losing Bets

```sql
SELECT
    result,
    AVG(json_extract(factor_scores, '$.form')) as avg_form,
    AVG(json_extract(factor_scores, '$.surface')) as avg_surface,
    AVG(json_extract(factor_scores, '$.ranking')) as avg_ranking,
    AVG(json_extract(factor_scores, '$.fatigue')) as avg_fatigue,
    AVG(json_extract(factor_scores, '$.performance_elo')) as avg_perf_elo
FROM bets
WHERE result IN ('Win', 'Loss')
AND factor_scores IS NOT NULL
GROUP BY result;
```

### Calibration From Live Bets

```sql
SELECT
    CASE
        WHEN our_probability >= 0.50 AND our_probability < 0.55 THEN '50-55%'
        WHEN our_probability >= 0.55 AND our_probability < 0.60 THEN '55-60%'
        WHEN our_probability >= 0.60 AND our_probability < 0.65 THEN '60-65%'
        WHEN our_probability >= 0.65 AND our_probability < 0.70 THEN '65-70%'
        WHEN our_probability >= 0.70 AND our_probability < 0.75 THEN '70-75%'
        WHEN our_probability >= 0.75 THEN '75%+'
    END as bucket,
    COUNT(*) as count,
    ROUND(SUM(CASE WHEN result = 'Win' THEN 1.0 ELSE 0.0 END) / COUNT(*) * 100, 1) as actual_win_pct
FROM bets
WHERE result IN ('Win', 'Loss')
AND our_probability >= 0.50
GROUP BY bucket
ORDER BY bucket;
```

### Cumulative P/L for Drawdown Calculation

```sql
SELECT
    id,
    settled_at,
    profit_loss,
    SUM(profit_loss) OVER (ORDER BY settled_at, id) as cumulative_pl
FROM bets
WHERE result IN ('Win', 'Loss')
ORDER BY settled_at, id;
```

---

*Document version: 1.1 | System version: v3.1 | Last updated: 2026-02-05*
