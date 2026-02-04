# Configuration Reference - Tennis Betting System v3.1

**Version:** 3.1 (February 5, 2026)
**Audience:** Operations team
**Last Updated:** 2026-02-05

This document is the single source of truth for all configurable parameters in the Tennis Betting System. Every constant, dictionary, threshold, and tunable value is documented here with its current value, location in code, and operational impact.

---

## Table of Contents

1. [Model Configuration](#1-model-configuration)
2. [Staking Configuration](#2-staking-configuration)
3. [Betfair Configuration](#3-betfair-configuration)
4. [Surface Detection](#4-surface-detection)
5. [Tournament Classification](#5-tournament-classification)
6. [Data Source Configuration](#6-data-source-configuration)
7. [UI Configuration](#7-ui-configuration)
8. [Discord Configuration](#8-discord-configuration)
9. [Database Configuration](#9-database-configuration)
10. [Auto Mode Configuration](#10-auto-mode-configuration)
11. [Scraping Configuration](#11-scraping-configuration)
12. [Performance Elo Configuration](#12-performance-elo-configuration)

---

## 1. Model Configuration

### 1.1 Factor Weights (DEFAULT_ANALYSIS_WEIGHTS)

The core prediction model uses 11 named factors, of which 8 are active (non-zero weight). Weights must sum to 1.00. **Updated v3.1**.

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `surface` | `0.22` | float | Weight for surface-specific win rate (career + recent blend). Likely edge source vs. the market. **Increased from 0.20**. | 0.00 - 1.00 | Increasing favors surface specialists; decreasing makes the model surface-agnostic. | `config.py:700` | Yes |
| `form` | `0.20` | float | Weight assigned to recent match form (win/loss record weighted by recency decay and tournament level). Absorbs opponent quality signal. | 0.00 - 1.00 | Increasing emphasizes recent results more heavily; decreasing makes the model rely more on static rankings and surface data. | `config.py:699` | Yes |
| `fatigue` | `0.17` | float | Weight for fatigue/rest analysis (days since last match, match density, difficulty load). Market underweights this factor. **Increased from 0.15**. | 0.00 - 1.00 | Increasing penalizes players on tight schedules or coming off marathon matches. This is a believed edge source. | `config.py:703` | Yes |
| `ranking` | `0.13` | float | Weight for ATP/WTA ranking-based advantage. | 0.00 - 1.00 | Increasing anchors predictions to official rankings; decreasing allows form and Elo to dominate. | `config.py:701` | Yes |
| `performance_elo` | `0.13` | float | Weight for rolling 12-month Elo rating based on actual match results. Better signal than official ranking because it decays and uses K-factors per tournament level. **Increased from 0.12**. | 0.00 - 1.00 | Increasing makes the model rely more on results-based Elo over official ranking. | `config.py:709` | Yes |
| `recent_loss` | `0.08` | float | Weight for psychological impact of recent losses (especially within 3-7 days). | 0.00 - 1.00 | Increasing penalizes recently-beaten players more; captures psychological/momentum effects. | `config.py:707` | Yes |
| `h2h` | `0.05` | float | Weight for head-to-head record between the two players. Market already prices this well. | 0.00 - 1.00 | Increasing rewards players with winning H2H records; low value is intentional because H2H is already baked into market prices. | `config.py:702` | Yes |
| `momentum` | `0.02` | float | Weight for winning streak momentum on the current surface. | 0.00 - 1.00 | Increasing rewards players on winning runs; kept small because effect is marginal. | `config.py:708` | Yes |
| `injury` | `0.00` | float | **DEPRECATED - replaced by Activity Edge Modifier.** Injury/returning player signals now handled as post-probability edge modifier. | 0.00 (disabled) | Do not re-enable; use ACTIVITY_SETTINGS instead. | `config.py:704` | Yes |
| `opponent_quality` | `0.00` | float | REMOVED. Previously weighted opponent quality of recent matches. Now redundant with form factor. | 0.00 (disabled) | Setting above 0 re-enables this factor; not recommended as it duplicates form signal. | `config.py:705` | Yes |
| `recency` | `0.00` | float | REMOVED. Previously weighted how recently each player competed. Already captured in form's decay function. | 0.00 (disabled) | Setting above 0 re-enables; not recommended due to redundancy. | `config.py:706` | Yes |

### 1.2 Model Weight Profiles (MODEL_WEIGHT_PROFILES)

Six preset weight profiles are available for different analytical perspectives. Each profile redistributes the same 11 factor weights. Users can select a profile from the UI.

| Profile Name | Key Emphasis | Location |
|-------------|-------------|----------|
| `Default` | Balanced (matches DEFAULT_ANALYSIS_WEIGHTS) | `config.py:717-722` |
| `Form Focus` | form=0.35, surface=0.15, ranking=0.10 | `config.py:723-728` |
| `Surface Focus` | form=0.15, surface=0.35, ranking=0.10 | `config.py:729-734` |
| `Ranking Focus` | form=0.15, surface=0.15, ranking=0.25, performance_elo=0.15 | `config.py:735-740` |
| `Fatigue Focus` | fatigue=0.30, others reduced | `config.py:741-746` |
| `Psychology Focus` | recent_loss=0.15, momentum=0.10 | `config.py:747-753` |

**Impact:** Selecting a non-default profile changes how the model weighs each factor for all subsequent analyses in that session. Does not persist across restarts unless coded as default.

### 1.3 Betting Model Definitions (calculate_bet_model)

**v3.1 has 11 models** in three categories. A match can qualify for multiple models simultaneously. At least one **hard model** (M3, M4, M5, M7, or M8) is required for betting.

#### Hard Models (Required for Betting)

| Model | Name | Criteria | Performance |
|-------|------|----------|-------------|
| **M3** | Sharp Zone | 5% ≤ edge ≤ 15% | Core value bets |
| **M4** | Favorites | prob ≥ 60% | High-confidence plays |
| **M5** | Underdog | edge ≥ 10%, odds 3.00-10.00, both 15+ matches | **WARNING: 14.3% win rate, -13.31u** |
| **M7** | Grind | 3% ≤ edge ≤ 8%, odds < 2.50 | Small edge + short odds |
| **M8** | Profitable Baseline | prob ≥ 55%, odds < 2.50 | 62.5% win rate at n=16 |

#### Soft Models (Tracking Tags)

| Model | Name | Criteria | Rationale |
|-------|------|----------|-----------|
| **M2** | Data Confirmed | Any hard model + serve data + both active (≥40) | Data quality marker |
| **M9** | Value Zone | Odds 2.00-2.99, serve aligned, 5% ≤ edge ≤ 10% | Best odds range |
| **M10** | Confident Grind | Odds < 2.20, prob ≥ 55%, both active (≥60) | Short odds + reliability |
| **M11** | Surface Edge | Surface factor ≥ 0.05, odds 2.00-3.50, edge ≥ 5% | 61.5% win rate at n=26 |

#### Premium Model (Staking Boost)

| Model | Name | Criteria | Effect |
|-------|------|----------|--------|
| **M1** | Triple Confirmation | Hard model + serve aligned + not activity-driven | **1.5x staking multiplier** |

**M1+M11 Performance (Feb 5, 2026):** 40 bets, 65.0% win rate, +22.53u, +55.6% ROI. This is the proven edge.

#### Fade Model (Counter-Signal)

| Model | Name | Trigger | Action |
|-------|------|---------|--------|
| **M12** | 2-0 Fade | Pure M3 or any M5, opponent odds 1.20-1.50 | Bet opponent wins 2-0 |

**Global filters applied to all models:**

| Parameter | Current Value | Type | Description | Location |
|-----------|--------------|------|-------------|----------|
| `min_odds_floor` | `1.70` | float | Minimum odds required. | `config.py:308` |
| `min_probability` | `0.40` | float | Minimum model probability required. | `config.py:309` |

**Key formula:** `edge = our_probability - implied_probability`

If no hard model is matched, the function returns `"None"` and the match is not flagged for betting.

### 1.4 Form Calculation Settings (FORM_SETTINGS)

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `default_matches` | `20` | int | Default number of recent matches used for form calculation. | 5 - 50 | Increasing smooths form over more matches (less volatile); decreasing makes form more reactive to recent results. | `config.py:759` | Yes |
| `min_matches` | `5` | int | Minimum matches required for a valid form calculation. Below this, form data is considered insufficient. | 1 - 20 | Lowering allows form to be computed with less data (noisier); raising requires more history (more stable but excludes more players). | `config.py:760` | Yes |
| `max_matches` | `20` | int | Maximum matches included in the form calculation window. | 10 - 100 | Increasing includes older matches which dilutes recent signal; decreasing focuses on most recent results. | `config.py:761` | Yes |
| `recency_decay` | `0.9` | float | Exponential decay factor applied to older matches. Each match N positions ago is weighted by `0.9^N`. | 0.50 - 1.00 | Values closer to 1.0 treat all matches equally; values closer to 0.5 heavily discount older matches. | `config.py:762` | Yes |
| `max_form_advantage` | `0.10` | float | Diminishing returns cap (via tanh) on the form advantage score. | 0.01 - 0.50 | Increasing allows larger form differences to have proportionally larger impact; decreasing compresses the form advantage range. | `config.py:763` | Yes |
| `max_stability_adjustment` | `0.20` | float | Cap for loss quality consistency adjustment (via tanh). | 0.01 - 0.50 | Higher values allow loss quality to create larger adjustments to stability. | `config.py:764` | Yes |
| `loss_consistency_baseline` | `150` | int | Standard deviation in Elo at which loss consistency factor equals ~0.50. | 50 - 500 | Lower values penalize inconsistent losses more aggressively; higher values are more forgiving. | `config.py:767` | Yes |
| `loss_consistency_steepness` | `2.0` | float | Exponent controlling how sharply consistency decays. | 1.0 - 5.0 | Higher values create sharper penalty for scattered losses; lower values create a gentler curve. | `config.py:768` | Yes |
| `loss_consistency_min_losses` | `2` | int | Minimum number of losses required before computing standard deviation of loss quality. | 1 - 10 | Higher values require more loss data before applying consistency dampening. | `config.py:769` | Yes |

### 1.5 Tournament Form Weights (TOURNAMENT_FORM_WEIGHT)

Results from higher-level tournaments carry more weight in the form score.

| Tournament Level | Weight | Description | Location |
|-----------------|--------|-------------|----------|
| `Grand Slam` | `1.3` | Grand Slam results weighted 30% higher | `config.py:775` |
| `ATP` | `1.15` | ATP Tour results weighted 15% higher | `config.py:776` |
| `WTA` | `1.1` | WTA Tour results weighted 10% higher | `config.py:777` |
| `Challenger` | `1.0` | Challenger results at baseline weight | `config.py:778` |
| `ITF` | `0.85` | ITF/Futures results weighted 15% lower | `config.py:779` |
| `Unknown` | `1.0` | Unknown tournament level at baseline | `config.py:780` |

### 1.6 Recent Loss Settings (RECENT_LOSS_SETTINGS)

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `penalty_3d` | `0.10` | float | Probability penalty for a loss within the last 3 days. | 0.00 - 0.30 | Increasing penalizes recently-defeated players more heavily. | `config.py:820` | Yes |
| `penalty_7d` | `0.05` | float | Probability penalty for a loss within the last 7 days. | 0.00 - 0.20 | Same as above but for slightly older losses. | `config.py:821` | Yes |
| `five_set_penalty` | `0.05` | float | Additional penalty for a 5-set loss (fatigue + demoralization). | 0.00 - 0.15 | Increasing assumes 5-set losers carry more fatigue/mental burden. | `config.py:822` | Yes |

### 1.7 Momentum Settings (MOMENTUM_SETTINGS)

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `window_days` | `14` | int | Number of days to look back for momentum calculation. | 7 - 30 | Longer windows smooth momentum; shorter windows react faster to recent streaks. | `config.py:826` | Yes |
| `win_bonus` | `0.03` | float | Bonus per win on the same surface within the momentum window. | 0.00 - 0.10 | Increasing rewards surface-specific winning streaks more. | `config.py:827` | Yes |
| `max_bonus` | `0.10` | float | Maximum cumulative momentum bonus. | 0.05 - 0.25 | Cap prevents momentum from dominating the model for players on long winning runs. | `config.py:828` | Yes |

### 1.8 Opponent Quality Settings (OPPONENT_QUALITY_SETTINGS)

Currently disabled (weight = 0.00), but settings remain in case the factor is re-enabled.

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `matches_to_analyze` | `6` | int | Number of recent matches to analyze for opponent quality. | `config.py:806` | Yes |
| `max_rank_for_bonus` | `200` | int | Opponents ranked above this get no quality bonus. | `config.py:807` | Yes |
| `unranked_default` | `200` | int | Default ranking assigned to unranked opponents. | `config.py:808` | Yes |

### 1.9 Recency Settings (RECENCY_SETTINGS)

Currently disabled (weight = 0.00), but settings remain in case the factor is re-enabled.

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `matches_to_analyze` | `6` | int | Number of recent matches to analyze. | `config.py:812` | Yes |
| `weight_7d` | `1.0` | float | Weight for matches in the last 7 days. | `config.py:813` | Yes |
| `weight_30d` | `0.7` | float | Weight for matches 7-30 days ago. | `config.py:814` | Yes |
| `weight_90d` | `0.4` | float | Weight for matches 30-90 days ago. | `config.py:815` | Yes |
| `weight_old` | `0.2` | float | Weight for matches 90+ days ago. | `config.py:816` | Yes |

### 1.10 Breakout Detection Settings (BREAKOUT_SETTINGS)

Detects when a player's recent results dramatically outperform their official ranking, indicating a genuine level shift rather than random variance.

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `min_ranking` | `150` | int | Players ranked inside the top 150 do not qualify for breakout detection (ranking already accurate). | 50 - 500 | Lowering excludes more players; raising allows breakout detection for higher-ranked players. | `config.py:838` | Yes |
| `peak_breakout_age` | `22` | int | Age at which the full age bonus is applied. Players at or below this age get maximum breakout credit. | 18 - 25 | Lower values restrict the youth bonus to younger players. | `config.py:839` | Yes |
| `max_breakout_age` | `28` | int | Age above which no age bonus is applied. | 25 - 35 | Higher values extend youth bonus to older players. | `config.py:840` | Yes |
| `quality_win_threshold` | `0.5` | float | To count as a quality win, the opponent's rank must be <= `player_rank * 0.5`. | 0.1 - 0.9 | Lower values require beating much higher-ranked opponents; higher values are more lenient. | `config.py:841` | Yes |
| `cluster_window_days` | `45` | int | Quality wins must occur within this many days of each other. | 14 - 90 | Shorter windows require more concentrated form; longer windows allow quality wins spread over time. | `config.py:842` | Yes |
| `min_quality_wins` | `2` | int | Minimum quality wins required to trigger breakout status. | 1 - 5 | Higher values require more evidence before declaring a breakout. | `config.py:843` | Yes |
| `base_blend` | `0.50` | float | Starting blend toward implied ranking (at minimum 2 quality wins). | 0.10 - 0.90 | Higher values shift the player's effective ranking more aggressively toward their results. | `config.py:844` | Yes |
| `per_extra_win_blend` | `0.10` | float | Additional blend per quality win beyond the minimum. | 0.00 - 0.25 | Higher values accelerate the ranking adjustment with additional wins. | `config.py:845` | Yes |
| `max_blend` | `0.75` | float | Hard cap on the maximum blend toward implied ranking. | 0.50 - 1.00 | Prevents the system from fully replacing official ranking with implied ranking. | `config.py:846` | Yes |
| `young_age_multiplier` | `1.3` | float | Multiplier for players at or below `peak_breakout_age`. | 1.0 - 2.0 | Higher values give more breakout credit to young players. | `config.py:847` | Yes |
| `neutral_age_multiplier` | `1.0` | float | Multiplier for players between peak and max age. | 0.5 - 1.5 | Baseline; no adjustment. | `config.py:848` | Yes |
| `old_age_multiplier` | `0.6` | float | Multiplier for players above `max_breakout_age`. | 0.1 - 1.0 | Lower values discount breakout signals from older players. | `config.py:849` | Yes |
| `implied_rank_buffer` | `1.2` | float | Multiplier on average opponent rank to avoid over-promoting players. | 1.0 - 2.0 | Higher values are more conservative (don't promote as aggressively). | `config.py:850` | Yes |
| `suppress_large_gap_boost` | `True` | bool | When True, suppresses breakout if the ranking gap is implausibly large. | True / False | Setting False allows extreme ranking jumps from breakout detection. | `config.py:851` | Yes |

### 1.11 Match Context Settings (MATCH_CONTEXT_SETTINGS)

When a player competes below their home tournament level, ranking/Elo/H2H advantages are less meaningful. This system detects level displacement and applies discounts.

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `level_hierarchy` | `{"ITF":1, "Challenger":2, "WTA":3, "ATP":3, "Grand Slam":4, "Unknown":2}` | dict | Numeric hierarchy of tournament levels. | 1 - 5 per level | Changing the relative order changes what counts as "playing down." | `config.py:860-867` | Yes |
| `discount_per_level` | `0.20` | float | Score discount per level of displacement. | 0.00 - 0.50 | Higher values penalize ranking advantage more when a top player is slumming. | `config.py:868` | Yes |
| `max_discount` | `0.60` | float | Hard cap on total discount. | 0.20 - 1.00 | Prevents total nullification of factor scores. | `config.py:869` | Yes |
| `discounted_factors` | `["ranking", "performance_elo", "h2h"]` | list | Factor keys affected by level displacement discount. | Any valid factor name | Adding factors (e.g., "form") would apply the discount to more aspects of the model. | `config.py:870` | Yes |
| `form_level_relevance` | `{0: 1.00, 1: 0.85, 2: 0.70, 3: 0.55}` | dict | Relevance multiplier based on how many levels away the form results were. | 0.0 - 1.0 per level gap | Lower values discount form results from other tournament levels more. | `config.py:871-876` | Yes |
| `rust_warning_days` | `10` | int | Number of days without a match before a "rust" warning is shown. | 5 - 30 | Lower triggers rust warnings sooner. | `config.py:877` | Yes |
| `level_mismatch_warning` | `True` | bool | Whether to show warnings when players compete below their usual level. | True / False | Disabling hides these warnings in the UI. | `config.py:878` | Yes |
| `near_breakout_warning` | `True` | bool | Whether to show warnings when a player is close to breakout detection threshold. | True / False | Disabling hides these warnings in the UI. | `config.py:879` | Yes |

### 1.12 Surface Stats Settings (SURFACE_SETTINGS)

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `career_weight` | `0.4` | float | Weight given to career-long surface win rate. | 0.00 - 1.00 | Increasing trusts career data more; must sum with `recent_weight` to 1.0. | `config.py:886` | Yes |
| `recent_weight` | `0.6` | float | Weight given to recent (last 2 years) surface win rate. | 0.00 - 1.00 | Increasing trusts recent surface form more. | `config.py:887` | Yes |
| `recent_years` | `2` | int | Number of years considered "recent" for surface stats. | 1 - 5 | Shorter windows focus on current form; longer windows provide more data. | `config.py:888` | Yes |
| `min_matches_reliable` | `20` | int | Minimum matches on a surface for stats to be considered statistically reliable. | 5 - 50 | Lower thresholds use smaller samples (more noise); higher thresholds may exclude players with less surface history. | `config.py:889` | Yes |

### 1.13 Fatigue Settings (FATIGUE_SETTINGS)

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `optimal_rest_days` | `3` | int | Ideal number of days between matches. No fatigue or rust penalty at this value. | 1 - 7 | Changing shifts the "sweet spot" for rest. | `config.py:897` | Yes |
| `rust_start_days` | `7` | int | Days after which a slight rust penalty begins. | 5 - 14 | Lower values apply rust sooner after inactivity. | `config.py:898` | Yes |
| `max_rest_days` | `14` | int | Beyond this many days, a steeper rust penalty applies. | 10 - 30 | Determines the threshold for significant inactivity. | `config.py:899` | Yes |
| `overplay_window_14` | `5` | int | Number of matches in 14 days that is considered concerning (overplay). | 3 - 8 | Lower values flag overplay sooner. | `config.py:900` | Yes |
| `overplay_window_30` | `10` | int | Number of matches in 30 days that is considered concerning. | 6 - 15 | Same as above for the 30-day window. | `config.py:901` | Yes |
| `difficulty_window_days` | `7` | int | Days to look back for match difficulty impact calculation. | 3 - 14 | Shorter windows focus on most recent physical load. | `config.py:903` | Yes |
| `difficulty_min` | `0.5` | float | Minimum difficulty multiplier (walkover/retirement). | 0.0 - 1.0 | Lower values count walkovers as less taxing. | `config.py:904` | Yes |
| `difficulty_max` | `3.0` | float | Maximum difficulty multiplier (marathon 5-setter). | 1.5 - 5.0 | Higher values penalize marathon matches more. | `config.py:905` | Yes |
| `difficulty_baseline_minutes` | `60` | int | Baseline match duration for difficulty calculation. | 30 - 120 | Lower baseline means a "normal" match is considered shorter. | `config.py:906` | Yes |
| `difficulty_max_minutes` | `300` | int | Maximum match duration cap for difficulty (5 hours). | 180 - 360 | Caps the physical load calculation. | `config.py:907` | Yes |
| `difficulty_baseline_sets` | `2` | int | Baseline number of sets for a best-of-3 match. | 2 - 3 | Used in calculating physical load from set count. | `config.py:908` | Yes |
| `difficulty_overload_threshold` | `6.0` | float | Difficulty points within the difficulty window that triggers an overload warning. | 3.0 - 10.0 | Lower values flag overload sooner; higher values are more permissive. | `config.py:909` | Yes |
| `rust_max_penalty` | `25` | int | Maximum rust penalty points applied for inactivity. | 10 - 50 | Higher values penalize inactivity more severely. | `config.py:911` | Yes |
| `rust_tau` | `8` | int | Exponential decay time constant for rust penalty. | 3 - 20 | Lower values cause rust to ramp up faster with inactivity. | `config.py:912` | Yes |

### 1.14 Betting Threshold Settings (BETTING_SETTINGS)

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `min_ev_threshold` | `0.05` | float | Minimum expected value (5%) for a bet to be considered. | 0.01 - 0.20 | Lowering generates more bets with smaller edges; raising is more selective. | `config.py:918` | Yes |
| `high_ev_threshold` | `0.10` | float | Threshold (10%) above which a bet is flagged as high value. | 0.05 - 0.30 | Changes what gets highlighted as "high value" in the UI. | `config.py:919` | Yes |
| `max_odds` | `10.0` | float | Maximum decimal odds to consider. Bets above this are ignored. | 3.0 - 50.0 | Lowering excludes longshots; raising includes more underdogs. | `config.py:920` | Yes |
| `min_probability` | `0.10` | float | Minimum win probability (10%) to even consider a player. | 0.05 - 0.30 | Filters out extreme underdogs from analysis. | `config.py:921` | Yes |
| `kelly_fraction` | `0.25` | float | Legacy Kelly fraction (not used by the primary staking system; see KELLY_STAKING below). | 0.10 - 1.00 | Only affects legacy code paths. | `config.py:922` | Yes |

### 1.15 Set Betting Settings (SET_BETTING)

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `bo3_scores` | `["2-0", "2-1", "0-2", "1-2"]` | list | All possible best-of-3 correct scores. | `config.py:1036` | Yes |
| `bo5_scores` | `["3-0", "3-1", "3-2", "0-3", "1-3", "2-3"]` | list | All possible best-of-5 correct scores (Grand Slams). | `config.py:1038` | Yes |
| `grand_slams` | `["Australian Open", "Roland Garros", "Wimbledon", "US Open"]` | list | Tournaments using best-of-5 format. | `config.py:1040-1045` | Yes |

---

## 2. Staking Configuration

### 2.1 Kelly Staking System (KELLY_STAKING)

The primary staking engine. Formula: `Final Stake = Kelly Stake x Kelly Fraction x Disagreement Penalty x Odds Multiplier`

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `unit_size_percent` | `2.0` | float | Percentage of bankroll that equals 1 unit. Used to convert Kelly percentage to unit stakes. | 0.5 - 5.0 | Higher = more aggressive bankroll exposure per unit. At 2%, a 100-unit bankroll = 50x leverage. | `config.py:932` | Yes |
| `kelly_fraction` | `0.375` | float | Fraction of full Kelly criterion to use. Full Kelly (1.0) is mathematically optimal but too volatile. Quarter (0.25) = conservative, Half (0.50) = aggressive. | 0.10 - 0.50 | **Critical parameter.** Lower values produce smaller, safer stakes. Higher values increase variance and potential drawdown significantly. 0.375 is a balanced setting. | `config.py:937` | Yes |
| `exchange_commission` | `0.02` | float | Betfair exchange commission rate deducted from winnings. Basic=2%, Rewards=5%, Rewards+=8%. | 0.00 - 0.10 | Must match your actual Betfair commission tier. Wrong value causes systematic staking error. | `config.py:941` | Yes |
| `min_odds` | `1.70` | float | Minimum decimal odds floor. Bets on selections with odds below this are rejected. | 1.01 - 3.00 | Lowering includes shorter-priced selections; raising restricts to higher-odds opportunities. | `config.py:944` | Yes |
| `min_opponent_odds` | `1.05` | float | Minimum opponent odds (liquidity filter). Matches where either side is below this are skipped. | 1.01 - 1.50 | Filters out extreme mismatches with no liquidity on the other side. | `config.py:947` | Yes |
| `min_units` | `0.25` | float | Minimum stake in units. Below this, the bet is not placed. | 0.10 - 1.00 | Lowering generates more small bets; raising filters out marginal edges. | `config.py:950` | Yes |
| `max_units` | `3.0` | float | Maximum stake in units (safety cap). | 1.0 - 10.0 | **Risk parameter.** Capping at 3u limits maximum single-bet exposure. Raising increases tail risk. | `config.py:953` | Yes |

### 2.2 Market Disagreement Penalty (KELLY_STAKING["disagreement_penalty"])

Reduces stake when the model diverges significantly from market-implied probability.

| Tier | `max_ratio` | `penalty` | Description | Location |
|------|------------|-----------|-------------|----------|
| `minor` | `1.20` | `1.0` (100%) | Model probability up to 1.2x market: full stake, trust the model. | `config.py:961-963` |
| `moderate` | `1.50` | `0.75` (75%) | Model probability 1.2x-1.5x market: reduce stake to 75%. | `config.py:965-967` |
| `major` | `999` | `0.50` (50%) | Model probability 1.5x+ market: still bet but at 50% stake to build sample. | `config.py:969-971` |

**Calculation:** `prob_ratio = our_probability / implied_probability`. The tier with the smallest `max_ratio` that exceeds `prob_ratio` determines the penalty.

### 2.3 Challenger-Specific Settings (KELLY_STAKING["challenger_settings"])

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `enabled` | `False` | bool | Whether Challenger-specific restrictions are active. **Currently DISABLED** for volume. | `config.py:977` | Yes |
| `max_disagreement_ratio` | `999` | float | Maximum allowed disagreement ratio for Challengers (effectively unlimited when disabled). | `config.py:978` | Yes |

### 2.4 Confidence and Calibration Settings

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `min_model_confidence` | `0.30` | float | Minimum model confidence (30%) required to place a bet. Lowered for volume. | `config.py:982` | Yes |
| `odds_range_weighting.sweet_spot_min` | `1.01` | float | Sweet spot minimum odds. **Effectively disabled** (set to 1.01). | `config.py:987` | Yes |
| `odds_range_weighting.sweet_spot_max` | `99.0` | float | Sweet spot maximum odds. **Effectively disabled** (set to 99.0). | `config.py:988` | Yes |
| `odds_range_weighting.outside_multiplier` | `1.0` | float | No penalty for bets outside sweet spot. **Effectively disabled.** | `config.py:989` | Yes |

### 2.5 Probability Calibration (PROBABILITY_CALIBRATION) - **ENABLED v3.1**

Two-layer calibration corrects systematic model overconfidence (historical: predicted 47.7% vs 34.8% actual).

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `enabled` | `True` | bool | **ENABLED v3.1.** Calibration is now active. | `config.py:1005` | Yes |
| `shrinkage_factor` | `0.60` | float | Shrinkage toward 50%. 60% raw → 56% calibrated. | `config.py:1011` | Yes |
| `asymmetric` | `True` | bool | **Only shrink favorites (prob > 50%).** Prevents inflating underdog probabilities. | `config.py:1012` | Yes |

**Shrinkage formula (favorites only):**
```
calibrated = 0.5 + (raw - 0.5) × 0.60
```

### 2.6 Market Blend Settings (MARKET_BLEND) - **ENABLED v3.1**

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `enabled` | `True` | bool | **ENABLED v3.1.** Blends calibrated probability with market-implied probability. | `config.py:996` | Yes |
| `market_weight` | `0.35` | float | 35% market, 65% model. Anchors to market while preserving model signal. | `config.py:997` | Yes |

**Combined calibration example:**
```
Raw model: 65%, Market implied: 50%
After shrinkage: 0.5 + (0.65 - 0.5) × 0.60 = 59%
After blend: 59% × 0.65 + 50% × 0.35 = 55.85%
Edge: 55.85% - 50% = 5.85pp (down from 15pp raw)
```

Edges are roughly halved by calibration, concentrating bets where the model has genuine signal.

### 2.7 Data Quality Gate (check_data_quality_for_stake)

This function blocks or reduces stakes when player data is insufficient.

| Rule | Threshold | Description | Location |
|------|-----------|-------------|----------|
| Standard bets (< 2u) | 3 matches in 60 days | Both players need at least 3 recent matches | `config.py:467` |
| High stakes (>= 2u) | 5 matches in 60 days | Stricter requirement for larger bets | `config.py:467` |
| TE verification pass | Player on Tennis Explorer with enough matches | If DB is stale but TE shows enough matches, bet passes | `config.py:501-505` |
| TE played this month | Player active but insufficient matches | Bet allowed with 50% stake reduction | `config.py:507-516` |
| Form comparison (high stakes) | Selection's form 15%+ worse than opponent | Blocks the bet if selection's year-to-date win rate is 15+ points below opponent | `config.py:561` |

### 2.8 Confidence-Based Stake Adjustment (adjust_stake_for_confidence)

Applied to stakes of 2u+ only. Reduces stake when supporting data is weak.

| Condition | Multiplier Reduction | Description | Location |
|-----------|---------------------|-------------|----------|
| No surface data for either player | -20% | Both players missing surface stats | `config.py:611-612` |
| Surface data missing for one player | -10% | One player missing surface stats | `config.py:614-615` |
| No H2H history | -10% | Players have never met | `config.py:621-622` |
| Limited form data (< 5 matches) | -15% | Either player has fewer than 5 matches in form window | `config.py:630-632` |
| Ranking dominates (> 40% of edge) | -10% | Ranking contributes over 40% of the weighted advantage | `config.py:643-644` |
| **Floor** | 50% minimum | Multiplier never drops below 0.50 | `config.py:647` |
| **Minimum stake** | 0.5u | Adjusted stake never below 0.5 units | `config.py:656` |
| **Rounding** | Nearest 0.5u | Adjusted stake rounded to nearest 0.5 units | `config.py:653` |

---

## 3. Betfair Configuration

### 3.1 API Endpoints

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `BETFAIR_LOGIN_URL` | `"https://identitysso.betfair.com/api/login"` | str | SSO login endpoint for obtaining session tokens. | `betfair_capture.py:83` | Yes |
| `BETFAIR_API_URL` | `"https://api.betfair.com/exchange/betting/rest/v1.0/"` | str | Exchange betting API base URL. All API calls append endpoint + "/". | `betfair_capture.py:84` | Yes |
| `BETFAIR_KEEP_ALIVE_URL` | `"https://identitysso.betfair.com/api/keepAlive"` | str | Session keep-alive endpoint to prevent token expiry. | `betfair_capture.py:85` | Yes |
| `BETFAIR_EXCHANGE_URL` | `"https://www.betfair.com/exchange/plus/"` | str | Web exchange URL (used for browser-based operations). | `betfair_tennis.py:25` | Yes |

### 3.2 API Constants

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `TENNIS_EVENT_TYPE_ID` | `"2"` | str | Betfair event type ID for Tennis. | `betfair_capture.py:88` | Yes |
| `MATCH_ODDS_MARKET` | `"MATCH_ODDS"` | str | Market type filter for match winner markets. | `betfair_capture.py:91` | Yes |
| `MIN_LIQUIDITY_GBP` | `0` | int | Minimum liquidity in GBP required to capture odds. Set to 0 to capture all matches regardless of liquidity. | `betfair_capture.py:95` | Yes |
| `MAX_ODDS_DISCREPANCY` | `1.0` | float | Maximum acceptable odds discrepancy vs. Pinnacle (100% = effectively disabled). | `betfair_capture.py:99` | Yes |

### 3.3 Credentials

Credentials are loaded from `credentials.json` in the application root directory. Priority order: (1) function arguments, (2) `credentials.json`, (3) environment variables.

| JSON Key | Environment Variable | Description | Location |
|----------|---------------------|-------------|----------|
| `betfair_app_key` | `BETFAIR_APP_KEY` | Betfair API application key (obtain from Betfair developer portal). | `betfair_capture.py:67, 116` |
| `betfair_username` | `BETFAIR_USERNAME` | Betfair account username. | `betfair_capture.py:68, 117` |
| `betfair_password` | `BETFAIR_PASSWORD` | Betfair account password. | `betfair_capture.py:69, 118` |

**File location:** `<app_root>/credentials.json`
**Security note:** This file contains plaintext credentials. Do NOT commit to version control.

### 3.4 Session Management

| Behavior | Value | Description | Location |
|----------|-------|-------------|----------|
| Login timeout | 10 seconds | HTTP timeout for login request in local monitor. | `local_monitor.py:166` |
| API request timeout | 15 seconds | HTTP timeout for API calls in local monitor. | `local_monitor.py:189` |
| Auto-reconnect | On 401 error | On HTTP 401, session token is cleared and login is re-attempted automatically. | `local_monitor.py:192-194` |
| Capture hours ahead | 48 hours | Default lookahead window for capturing upcoming matches. | `betfair_capture.py:194, 640` |

### 3.5 Local Monitor Betfair Client

The `local_monitor.py` contains its own lightweight Betfair client with identical endpoints:

| Parameter | Current Value | Location |
|-----------|--------------|----------|
| `LOGIN_URL` | `"https://identitysso.betfair.com/api/login"` | `local_monitor.py:148` |
| `API_URL` | `"https://api.betfair.com/exchange/betting/rest/v1.0/"` | `local_monitor.py:149` |

---

## 4. Surface Detection

### 4.1 Surface List (SURFACES)

| Parameter | Current Value | Type | Description | Location |
|-----------|--------------|------|-------------|----------|
| `SURFACES` | `["Hard", "Clay", "Grass", "Carpet"]` | list | All recognized playing surfaces. | `config.py:54` |

### 4.2 Surface Mapping (SURFACE_MAPPING)

Maps input codes/strings to canonical surface names.

| Input | Maps To | Location |
|-------|---------|----------|
| `"hard"`, `"h"` | `"Hard"` | `config.py:57-61` |
| `"clay"`, `"c"` | `"Clay"` | `config.py:58-62` |
| `"grass"`, `"g"` | `"Grass"` | `config.py:59-63` |
| `"carpet"`, `"p"` | `"Carpet"` | `config.py:60-64` |

### 4.3 Clay Tournaments (CLAY_TOURNAMENTS)

68 tournament name fragments that trigger Clay surface detection. Matches use word-boundary matching (short keywords) or substring matching (multi-word keywords).

| Category | Tournaments | Location |
|----------|-------------|----------|
| Grand Slam | `roland garros`, `french open` | `config.py:75` |
| Masters 1000 | `monte carlo`, `madrid`, `rome`, `internazionali` | `config.py:77` |
| ATP 500 | `barcelona`, `hamburg`, `rio`, `rio de janeiro` | `config.py:79` |
| ATP 250 | `buenos aires`, `cordoba`, `santiago`, `sao paulo`, `estoril`, `munich`, `geneva`, `lyon`, `bastad`, `umag`, `kitzbuhel`, `gstaad`, `winston-salem`, `winston salem`, `marrakech`, `houston`, `cagliari`, `parma`, `belgrade`, `sardegna`, `tiriac`, `bucharest` | `config.py:81-86` |
| WTA Clay | `charleston`, `strasbourg`, `rabat`, `bogota`, `prague`, `warsaw`, `portoroz`, `palermo`, `lausanne`, `budapest`, `birmingham wta` | `config.py:87-89` |
| Challenger Clay | `concepcion`, `santa cruz`, `campinas`, `santo domingo`, `medellin`, `salinas`, `lima`, `cali`, `guayaquil`, `san miguel de tucuman`, `punta del este`, `asuncion`, `barletta`, `francavilla`, `santa margherita`, `perugia`, `iasi`, `sibiu`, `split`, `zadar`, `todi`, `como`, `prague challenger`, `braunschweig`, `heilbronn`, `aix-en-provence`, `prostejov`, `liberec`, `szczecin`, `poznan`, `wroclaw` | `config.py:91-98` |

**Full list location:** `config.py:73-98`

### 4.4 Grass Tournaments (GRASS_TOURNAMENTS)

18 tournament name fragments that trigger Grass surface detection. **Only checked during grass season (June-July).**

| Category | Tournaments | Location |
|----------|-------------|----------|
| Grand Slam | `wimbledon` | `config.py:105` |
| ATP 500 | `queens`, `queen's`, `queen's club`, `atp halle`, `halle open`, `terra wortmann` | `config.py:107-108` |
| ATP 250 | `s-hertogenbosch`, `hertogenbosch`, `rosmalen`, `libema open`, `boss open`, `eastbourne`, `mallorca`, `newport` | `config.py:110-112` |
| WTA Grass | `birmingham classic`, `rothesay classic birmingham`, `nottingham`, `rothesay open nottingham`, `berlin wta`, `ecotrans ladies`, `bad homburg`, `bad homburg open` | `config.py:114-117` |

**Full list location:** `config.py:103-118`

### 4.5 Indoor Hard Tournaments (INDOOR_HARD_TOURNAMENTS)

Reference list only; these are still classified as "Hard" surface.

| Tournaments | Location |
|-------------|----------|
| `paris masters`, `paris-bercy`, `rolex paris`, `vienna`, `basel`, `stockholm`, `antwerp`, `st petersburg`, `metz`, `sofia`, `moselle`, `marseille`, `montpellier`, `rotterdam`, `dallas`, `adelaide`, `quimper`, `oeiras`, `koblenz`, `loughborough`, `andria` | `config.py:121-128` |

### 4.6 Surface Detection Logic (get_tournament_surface)

The `get_tournament_surface()` function is the **single source of truth** for surface detection. Decision order:

1. Explicit surface in name (e.g., `" - clay"`, `"(grass)"`, `"(hard)"`, `" - indoor"`) -- returns immediately.
2. Grass season check: extracts month from `date_str`; grass season = months 6 and 7 only.
3. Check against `CLAY_TOURNAMENTS` list using word-boundary matching.
4. If grass season, check against `GRASS_TOURNAMENTS` list using word-boundary matching.
5. Default: returns `"Hard"` (most common surface, especially for Challengers).

| Parameter | Value | Description | Location |
|-----------|-------|-------------|----------|
| Grass season months | `[6, 7]` (June, July) | Only months when grass tournaments are recognized. | `config.py:209` |
| Default surface | `"Hard"` | Returned when no tournament name match is found. | `config.py:225` |
| Word boundary matching | Short keywords (<=6 chars, single word) use regex `\b` boundaries | Prevents "halle" from matching "challenger" or "rome" from matching "Jerome". | `config.py:131-143` |

---

## 5. Tournament Classification

### 5.1 Tournament Categories (TOURNAMENT_CATEGORIES)

| Categories | Location |
|-----------|----------|
| `"Grand Slam"`, `"Masters 1000"`, `"ATP 500"`, `"ATP 250"`, `"ATP Finals"`, `"Davis Cup"`, `"Olympics"`, `"Other"` | `config.py:230-239` |

### 5.2 Tournament Level Mapping (TOURNEY_LEVEL_MAPPING)

Maps single-character codes from Tennis Abstract data to full level names.

| Code | Level | Location |
|------|-------|----------|
| `"G"` | `"Grand Slam"` | `config.py:243` |
| `"M"` | `"Masters 1000"` | `config.py:244` |
| `"A"` | `"ATP 500"` | `config.py:245` |
| `"B"` | `"ATP 250"` | `config.py:246` |
| `"F"` | `"ATP Finals"` | `config.py:247` |
| `"D"` | `"Davis Cup"` | `config.py:248` |
| `"O"` | `"Olympics"` | `config.py:249` |
| `"C"` | `"Challenger"` | `config.py:250` |

### 5.3 Tour Level Detection (get_tour_level)

The `get_tour_level()` function categorizes tournaments by name-based heuristics:

| Priority | Rule | Returns | Location |
|----------|------|---------|----------|
| 1 | Name contains `australian open`, `roland garros`, `french open`, `wimbledon`, `us open`, `u.s. open` | `"Grand Slam"` | `config.py:265-267` |
| 2 | Name contains `atp` or `masters` | `"ATP"` | `config.py:270` |
| 3 | Name contains `wta`, `women's`, or `ladies` | `"WTA"` | `config.py:274` |
| 4 | Name contains `challenger` or `ch ` | `"Challenger"` | `config.py:278` |
| 5 | Name contains `itf`, `futures`, or `$` | `"ITF"` | `config.py:282` |
| 6 | Name contains `men` | `"ATP"` | `config.py:286` |
| 7 | Name contains `women` | `"WTA"` | `config.py:288` |
| Default | No match | `"Unknown"` | `config.py:290` |

### 5.4 Match Rounds (ROUNDS, ROUND_NAMES)

| Code | Full Name | Location |
|------|-----------|----------|
| `"F"` | Final | `config.py:668, 681` |
| `"SF"` | Semi-Final | `config.py:669, 682` |
| `"QF"` | Quarter-Final | `config.py:670, 683` |
| `"R16"` | Round of 16 | `config.py:671, 684` |
| `"R32"` | Round of 32 | `config.py:672, 685` |
| `"R64"` | Round of 64 | `config.py:673, 686` |
| `"R128"` | Round of 128 | `config.py:674, 687` |
| `"RR"` | Round Robin | `config.py:675, 688` |
| `"BR"` | Bronze Medal | `config.py:676, 689` |
| `"ER"` | Early Round | `config.py:677, 690` |

---

## 6. Data Source Configuration

### 6.1 Tennis Explorer Data (GitHub)

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `TENNIS_EXPLORER_DATA_URL` | `"https://github.com/Anners92/tennisdata/raw/main/tennis_data.db.gz"` | str | URL for the compressed Tennis Explorer database download. | `config.py:1118` | Yes |

### 6.2 Scraper Settings (SCRAPER_SETTINGS)

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `atp_rankings_pages` | `15` | int | Number of ranking pages to scrape (100 players per page = 1500 ATP players). | 1 - 50 | Higher values scrape deeper into the ranking list; increases scrape time. | `config.py:1122` | Yes |
| `wta_rankings_pages` | `15` | int | Number of WTA ranking pages to scrape (1500 WTA players). | 1 - 50 | Same as above for WTA. | `config.py:1123` | Yes |
| `match_history_months` | `12` | int | Months of match history to scrape per player. | 1 - 36 | Higher values provide more history but take longer and use more storage. | `config.py:1124` | Yes |

### 6.3 Tennis Explorer Scraper

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `BASE_URL` | `"https://www.tennisexplorer.com"` | str | Base URL for Tennis Explorer website. | `tennis_explorer_scraper.py:356` | Yes |
| User-Agent | `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"` | str | Browser User-Agent string sent with all requests. | `tennis_explorer_scraper.py:361` | Yes |
| Accept header | `"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"` | str | HTTP Accept header. | `tennis_explorer_scraper.py:362` | Yes |
| Request timeout | `15` seconds | int | HTTP request timeout for all Tennis Explorer requests. | `tennis_explorer_scraper.py:379, 419` | Yes |

### 6.4 Tennis Ratio Scraper

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `BASE_URL` | `"https://www.tennisratio.com/players/"` | str | Base URL for Tennis Ratio player profiles. | `tennis_ratio_scraper.py:27` | Yes |
| `REQUEST_TIMEOUT` | `15` | int | HTTP request timeout in seconds. | `tennis_ratio_scraper.py:28` | Yes |
| `USER_AGENT` | `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"` | str | Browser User-Agent string. | `tennis_ratio_scraper.py:29` | Yes |

### 6.5 Data Import Settings (IMPORT_SETTINGS)

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `start_year` | `2000` | int | Earliest year to import match data from. | 1990 - 2025 | Lowering imports more historical data; increasing limits to recent years. | `config.py:1086` | Yes |
| `end_year` | `2025` | int | Latest year to import match data from. | 2020 - 2030 | Should be set to current or previous year. | `config.py:1087` | Yes |
| `batch_size` | `1000` | int | Number of records per database insert batch. | 100 - 10000 | Higher values are faster but use more memory. | `config.py:1088` | Yes |

### 6.6 GitHub Data Loader

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `months_to_fetch` | `12` | int | Default number of months of data to fetch when importing. | `github_data_loader.py:28` | Yes |

### 6.7 Cloud Sync (Supabase)

| JSON Key | Description | Location |
|----------|-------------|----------|
| `supabase_url` | Supabase project URL (e.g., `https://xxxxx.supabase.co`) | `cloud_sync.py:42` |
| `supabase_key` | Supabase anonymous API key | `cloud_sync.py:43` |

**File location:** `<app_root>/credentials.json`
**Request timeout:** 10 seconds (`cloud_sync.py:83`)

---

## 7. UI Configuration

### 7.1 Color Palette (UI_COLORS)

All colors used across the application UI. Defined centrally in `config.py` and imported by all UI modules.

#### Background Colors

| Parameter | Current Value | CSS Equivalent | Description | Location |
|-----------|--------------|---------------|-------------|----------|
| `bg_dark` | `"#0f172a"` | Slate-900 | Deep slate main background. | `config.py:1053` |
| `bg_medium` | `"#1e293b"` | Slate-800 | Cards, panels, and content areas. | `config.py:1054` |
| `bg_light` | `"#334155"` | Slate-700 | Input fields and hover states. | `config.py:1055` |
| `bg_card` | `"#1e293b"` | Slate-800 | Card background (same as bg_medium). | `config.py:1056` |
| `border` | `"#334155"` | Slate-700 | Subtle border color. | `config.py:1057` |

#### Text Colors

| Parameter | Current Value | CSS Equivalent | Description | Location |
|-----------|--------------|---------------|-------------|----------|
| `text_primary` | `"#f1f5f9"` | Slate-100 | Primary text (headings, labels). | `config.py:1060` |
| `text_secondary` | `"#94a3b8"` | Slate-400 | Secondary text (descriptions, metadata). | `config.py:1061` |
| `text_muted` | `"#64748b"` | Slate-500 | Muted text (timestamps, disabled items). | `config.py:1062` |

#### Brand and Action Colors

| Parameter | Current Value | Description | Location |
|-----------|--------------|-------------|----------|
| `primary` | `"#3b82f6"` | Electric Blue -- primary brand color for all interactive elements. | `config.py:1065` |
| `accent` | `"#3b82f6"` | Same as primary for consistency. | `config.py:1066` |
| `success` | `"#22c55e"` | Green -- positive ROI, success states, wins. | `config.py:1067` |
| `warning` | `"#f59e0b"` | Amber -- warnings, caution states. | `config.py:1068` |
| `danger` | `"#ef4444"` | Red -- negative ROI, errors, losses. | `config.py:1069` |

#### Surface Colors

| Parameter | Current Value | Description | Location |
|-----------|--------------|-------------|----------|
| `surface_hard` | `"#3b82f6"` | Blue for Hard court indicators. | `config.py:1072` |
| `surface_clay` | `"#f97316"` | Orange for Clay court indicators. | `config.py:1073` |
| `surface_grass` | `"#22c55e"` | Green for Grass court indicators. | `config.py:1074` |
| `surface_carpet` | `"#a855f7"` | Purple for Carpet court indicators. | `config.py:1075` |

#### Player Colors

| Parameter | Current Value | Description | Location |
|-----------|--------------|-------------|----------|
| `player1` | `"#3b82f6"` | Blue for Player 1 in visualizations. | `config.py:1078` |
| `player2` | `"#eab308"` | Yellow for Player 2 in visualizations. | `config.py:1079` |

### 7.2 Main Window Colors (MainApplication class)

Additional color constants defined directly on the main application class.

| Parameter | Current Value | Description | Location |
|-----------|--------------|-------------|----------|
| `BG_DARK` | `"#0f172a"` | Deep slate background. | `main.py:259` |
| `BG_CARD` | `"#1e293b"` | Card background. | `main.py:260` |
| `BG_CARD_HOVER` | `"#334155"` | Card hover state. | `main.py:261` |
| `BORDER_DEFAULT` | `"#334155"` | Subtle border. | `main.py:262` |
| `BORDER_HOVER` | `"#475569"` | Brighter border on hover. | `main.py:263` |
| `ACCENT_PRIMARY` | `"#3b82f6"` | Brand accent for all buttons. | `main.py:266` |
| `GLOW_CYAN` | `"#06b6d4"` | Betfair section glow. | `main.py:269` |
| `GLOW_GREEN` | `"#22c55e"` | Bet Suggester section glow. | `main.py:270` |
| `GLOW_BLUE` | `"#3b82f6"` | Bet Tracker section glow. | `main.py:271` |
| `GLOW_PURPLE` | `"#a855f7"` | Rankings section glow. | `main.py:272` |
| `GLOW_AMBER` | `"#f59e0b"` | Database section glow. | `main.py:273` |
| `ACCENT_SUCCESS` | `"#22c55e"` | Green for success states. | `main.py:276` |
| `ACCENT_DANGER` | `"#ef4444"` | Red for error/loss states. | `main.py:277` |
| `ACCENT_WARNING` | `"#f59e0b"` | Amber for warnings. | `main.py:278` |
| `TEXT_PRIMARY` | `"#f1f5f9"` | Primary text. | `main.py:281` |
| `TEXT_SECONDARY` | `"#94a3b8"` | Secondary text. | `main.py:282` |
| `TEXT_MUTED` | `"#64748b"` | Muted text. | `main.py:283` |

### 7.3 Window Settings

| Window | Title | Size | Launch State | Location |
|--------|-------|------|-------------|----------|
| Main Application | `"Tennis Betting System"` | Maximized | `root.state('zoomed')` | `main.py:287-290` |
| Betfair Capture | `"Betfair Tennis - Live Odds Capture"` | Maximized | `root.state('zoomed')` | `betfair_capture.py:721-722` |
| Betfair Tennis | `"Betfair Tennis - Live Matches"` | `1100x700` | Fixed geometry | `betfair_tennis.py:324-325` |
| Bet Tracker | `"Bet Tracker"` | Maximized (assumed) | Full window | `bet_tracker.py:935` |
| Quick Import dialog | `"Quick Import"` | `500x400` | Centered | `main.py:981-982` |
| Refresh Data dialog | `"Refresh Data"` | `500x400` | Centered | `main.py:1093-1094` |
| Quick Refresh dialog | `"Quick Refresh (7 Days)"` | `500x400` | Centered | `main.py:1205-1206` |
| API Help dialog | `"How to Get Betfair API Credentials"` | `550x480` | Fixed geometry | `betfair_capture.py:927-928` |

### 7.4 Font Settings

| Context | Font Family | Size | Weight | Location |
|---------|------------|------|--------|----------|
| Default labels | `"Segoe UI"` | 10 | Normal | `betfair_capture.py:744` |
| Title labels | `"Segoe UI"` | 16 | Bold | `betfair_capture.py:746` |
| Treeview data | `"Segoe UI"` | 9 | Normal | `betfair_capture.py:757` |
| Treeview headings | `"Segoe UI"` | 9 | Bold | `betfair_capture.py:759` |
| Modern buttons | `"Segoe UI"` | 10 | Bold | `main.py:74` |

### 7.5 Table Column Widths

#### Betfair Capture Matches Table

| Column | Width (px) | Location |
|--------|-----------|----------|
| `time` | 80 | `betfair_capture.py:889` |
| `tournament` | 180 | `betfair_capture.py:890` |
| `player1` | 150 | `betfair_capture.py:891` |
| `p1_odds` | 60 | `betfair_capture.py:892` |
| `player2` | 150 | `betfair_capture.py:893` |
| `p2_odds` | 60 | `betfair_capture.py:894` |
| `surface` | 70 | `betfair_capture.py:895` |

#### Bet Tracker - Settled Bets Table

| Column | Width (px) | Location |
|--------|-----------|----------|
| `id` | 40 | `bet_tracker.py:1592` |
| `date` | 80 | `bet_tracker.py:1593` |
| `tour` | 65 | `bet_tracker.py:1594` |
| `tournament` | 110 | `bet_tracker.py:1595` |
| `match` | 150 | `bet_tracker.py:1596` |
| `score` | 70 | `bet_tracker.py:1597` |
| `market` | 80 | `bet_tracker.py:1598` |
| `selection` | 100 | `bet_tracker.py:1599` |
| `stake` | 45 | `bet_tracker.py:1600` |
| `odds` | 45 | `bet_tracker.py:1601` |
| `result` | 50 | `bet_tracker.py:1602` |
| `pl` | 55 | `bet_tracker.py:1603` |
| `model` | 70 | `bet_tracker.py:1604` |
| `close_odds` | 50 | `bet_tracker.py:1605` |
| `clv` | 50 | `bet_tracker.py:1606` |

#### Bet Tracker - Pending Bets Table

| Column | Width (px) | Location |
|--------|-----------|----------|
| `id` | 40 | `bet_tracker.py:1675` |
| `date` | 90 | `bet_tracker.py:1676` |
| `tour` | 80 | `bet_tracker.py:1677` |
| `tournament` | 130 | `bet_tracker.py:1678` |
| `match` | 170 | `bet_tracker.py:1679` |
| `score` | 90 | `bet_tracker.py:1680` |
| `market` | 90 | `bet_tracker.py:1681` |
| `selection` | 110 | `bet_tracker.py:1682` |
| `stake` | 50 | `bet_tracker.py:1683` |
| `odds` | 50 | `bet_tracker.py:1684` |
| `ev` | 55 | `bet_tracker.py:1685` |

---

## 8. Discord Configuration

### 8.1 Discord Bot (local_monitor.py)

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `DISCORD_BOT_TOKEN` | Loaded from `credentials.json` key `"discord_bot_token"` | str | Discord bot authentication token. | `local_monitor.py:50` | Yes |
| `DISCORD_CHANNEL_ID` | `1462470788602007787` | int | Discord channel ID where all alerts are posted. | `local_monitor.py:51` | Yes |
| `CHECK_INTERVAL` | `30` | int | Seconds between each bet-checking loop iteration. The Discord bot polls for pending bet updates on this interval. | `local_monitor.py:53` | Yes |

### 8.2 Discord Webhook (discord_notifier.py)

The webhook notifier is **currently disabled** (hard-coded `return False` in `is_configured()`). Alerts are now handled exclusively by the Discord bot in `local_monitor.py`.

| Parameter | Source | Description | Location |
|-----------|--------|-------------|----------|
| `discord_webhook` | `credentials.json` key `"discord_webhook"` | Webhook URL (e.g., `https://discord.com/api/webhooks/...`). | `discord_notifier.py:37` |

### 8.3 Alert Types

The Discord bot sends two types of embedded alerts:

| Alert Type | Trigger | Fields Included | Location |
|-----------|---------|-----------------|----------|
| **Live Alert** | Bet goes in-play | Match, Selection, Odds, Stake, Model, Tournament, Close Odds, CLV | `local_monitor.py:441-463` |
| **Result Alert** | Bet is settled (win/loss) | Match, Selection, Odds, P/L, Close Odds, CLV | `local_monitor.py:466-494` |

### 8.4 Bot Commands

| Command | Description | Location |
|---------|-------------|----------|
| `!inplay` | Show currently live bets | `local_monitor.py` |
| `!pending` | Show all pending (unsettled) bets | `local_monitor.py` |
| `!stats` | Overall statistics summary | `local_monitor.py` |
| `!refresh` | Check all pending bets against Betfair + Tennis Explorer and settle finished matches | `local_monitor.py` |
| `!alert` | Manual alert trigger | `local_monitor.py` |
| `!resend` | Re-send the most recent result alert | `local_monitor.py` |

---

## 9. Database Configuration

### 9.1 File Paths

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `INSTALL_DIR` | `Path(sys.executable).parent` (frozen) or `Path(__file__).parent.parent` (script) | Path | Root installation directory. Source of seed data and static assets. | `config.py:18-27` | Yes |
| `BASE_DIR` | `Path("C:/Users/Public/Documents/Tennis Betting System")` | Path | Root data directory. All user data is stored under this path. Overridable via `TENNIS_DATA_DIR` environment variable. | `config.py:20, 28` | Yes |
| `DATA_DIR` | `BASE_DIR / "data"` | Path | Subdirectory for database files and name mappings. | `config.py:30` | Yes |
| `OUTPUT_DIR` | `BASE_DIR / "output"` | Path | Subdirectory for exported files and reports. | `config.py:31` | Yes |
| `LOGS_DIR` | `BASE_DIR / "logs"` | Path | Subdirectory for log files. | `config.py:32` | Yes |
| `DB_PATH` | `DATA_DIR / "tennis_betting.db"` | Path | Full path to the SQLite database file. | `config.py:33` | Yes |
| `SEED_DB_PATH` | `INSTALL_DIR / "data" / "tennis_betting.db"` | Path | Seed database copied on first run if no user database exists. | `config.py:42` | Yes |
| `LOCAL_DB_PATH` (monitor) | `r"C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db"` | str | Hardcoded path used by the local monitor. Matches `DB_PATH`. | `local_monitor.py:56` | Yes |

### 9.2 Environment Variable Override

| Variable | Description | Location |
|----------|-------------|----------|
| `TENNIS_DATA_DIR` | When set, overrides `BASE_DIR` to this path. Used for cloud/CI environments. | `config.py:21-24` |

### 9.3 Seed Database Behavior

On first run, if `DB_PATH` does not exist but `SEED_DB_PATH` does, the seed database is copied to the data directory. This happens in two places:

1. `config.py:43-49` -- Early copy during module import.
2. `database.py:83-89` -- Copy during database initialization with file locking to prevent race conditions.

Additionally, `name_mappings.json` is always overwritten from the install directory on startup (it is reference data, not user data). Location: `database.py:91-96`.

### 9.4 Name Mappings

| File | Path | Description | Location |
|------|------|-------------|----------|
| `name_mappings.json` | `INSTALL_DIR / "data" / "name_mappings.json"` or `DATA_DIR / "name_mappings.json"` | Maps Betfair player names to database names or player IDs. Used by `_get_mapped_player_name()`. | `config.py:405-428` |

---

## 10. Auto Mode Configuration

### 10.1 Auto Mode Parameters

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `auto_mode_interval` | `30 * 60 * 1000` (1,800,000 ms = 30 minutes) | int | Milliseconds between auto mode cycles. Each cycle captures odds and runs analysis. | 300000 - 7200000 (5 min - 2 hours) | Shorter intervals capture odds more frequently but increase API usage and CPU load. | `main.py:298` | No (runtime toggle) |
| `auto_mode_enabled` | `False` (default) | bool | Whether auto mode is active. Toggled via UI button. | True / False | Enabling starts the automatic capture-analyze-alert loop. | `main.py:296` | No |
| Capture hours ahead | `48` | int | How many hours ahead to look for matches when auto-capturing from Betfair. | 1 - 168 (1 week) | Higher values capture more distant matches; lower values focus on imminent matches. | `main.py:1930, 1986` | No |

### 10.2 Background Updater

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| `update_interval` | `30 * 60` (1,800 seconds = 30 minutes) | int | Seconds between background player update cycles. | `main.py:134` | Yes |
| `player_delay` | `5` | int | Seconds between individual player updates (rate limiting). | `main.py:135` | Yes |
| Player update window | +/- 3 days | - | Only players with matches within 3 days of today are updated. | `main.py:161-162` | Yes |
| Update freshness check | 6 hours | - | Players updated within the last 6 hours are skipped. | `main.py:213` | Yes |

---

## 11. Scraping Configuration

### 11.1 Tennis Explorer Scraper

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| Base URL | `"https://www.tennisexplorer.com"` | str | Root URL for all Tennis Explorer requests. | `tennis_explorer_scraper.py:356` | Yes |
| User-Agent | `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"` | str | Full browser User-Agent to avoid bot detection. | `tennis_explorer_scraper.py:361` | Yes |
| Request timeout | `15` seconds | int | HTTP timeout for all Tennis Explorer page fetches. | `tennis_explorer_scraper.py:379, 419, 603` | Yes |

### 11.2 Tennis Ratio Scraper

| Parameter | Current Value | Type | Description | Location | Restart Required |
|-----------|--------------|------|-------------|----------|-----------------|
| Base URL | `"https://www.tennisratio.com/players/"` | str | Root URL for Tennis Ratio player profiles. | `tennis_ratio_scraper.py:27` | Yes |
| Request timeout | `15` seconds | int | HTTP timeout for page fetches. | `tennis_ratio_scraper.py:28` | Yes |
| User-Agent | `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"` | str | Abbreviated browser User-Agent. | `tennis_ratio_scraper.py:29` | Yes |

### 11.3 Tennis Explorer Data Quality Check

When the database shows insufficient matches for a player, the system verifies against Tennis Explorer directly.

| Parameter | Current Value | Description | Location |
|-----------|--------------|-------------|----------|
| TE check timeout | `10` seconds | HTTP timeout when verifying player data on Tennis Explorer. | `config.py:355` |
| TE check window | `60` days | How far back to count matches on Tennis Explorer. | `config.py:334` |
| User-Agent (TE check) | `"Mozilla/5.0"` | Minimal User-Agent for quick TE verification requests. | `config.py:354` |

### 11.4 Other Request Timeouts

| Context | Timeout | Location |
|---------|---------|----------|
| Betfair API requests (main capture) | Default `requests` timeout | `betfair_capture.py:182` |
| Betfair API requests (local monitor) | `15` seconds | `local_monitor.py:189` |
| Betfair login (local monitor) | `10` seconds | `local_monitor.py:166` |
| Supabase cloud sync requests | `10` seconds | `cloud_sync.py:83` |
| Discord webhook posts | `10` seconds | `discord_notifier.py:168` |
| Live score fetches | `10` seconds | `live_scores.py:39, 179` |
| Betfair web scraper | `30` seconds | `betfair_tennis.py:53` |
| Rankings downloader | `30` seconds | `rankings_downloader.py:144` |
| Rankings scraper | `30` seconds | `rankings_scraper.py:40, 124` |
| Odds API requests | `30` seconds | `odds_api.py:90` |
| Bet suggester TE requests | `15` seconds | `bet_suggester.py:5558` |

### 11.5 Rate Limiting

| Context | Delay | Description | Location |
|---------|-------|-------------|----------|
| Background player updates | `5` seconds between players | Prevents overloading Tennis Explorer/Abstract during bulk updates. | `main.py:135` |
| Auto mode cycle interval | `30` minutes | Time between full capture+analysis cycles. | `main.py:298` |
| Local monitor check interval | `30` seconds | Time between Betfair polling loops in the Discord bot. | `local_monitor.py:53` |

---

## 12. Performance Elo Configuration

### 12.1 Performance Elo Settings (PERFORMANCE_ELO_SETTINGS)

Rolling 12-month Elo ratings calculated from actual match results. K-factor determines how much a single match result shifts the rating, with larger K-factors for more important tournaments.

| Parameter | Current Value | Type | Description | Valid Range | Impact of Change | Location | Restart Required |
|-----------|--------------|------|-------------|-------------|-----------------|----------|-----------------|
| `rolling_months` | `12` | int | Number of months of match data used for Elo calculation. Older results fall off. | 3 - 36 | Shorter windows make Elo more reactive; longer windows provide more stability. | `config.py:791` | Yes |
| `default_elo` | `1200` | int | Initial/default Elo rating for players with no history. | 800 - 1600 | Higher default assumes players are stronger by default; lower is more conservative. | `config.py:792` | Yes |

### 12.2 K-Factors by Tournament Level

K-factor determines the maximum Elo points exchanged per match. Higher K = more volatile, but also more responsive to results at that level.

| Tournament Level | K-Factor | Description | Location |
|-----------------|----------|-------------|----------|
| `Grand Slam` | `48` | Maximum responsiveness; Grand Slam results shift Elo the most. | `config.py:794` |
| `ATP` | `32` | Standard ATP Tour events. | `config.py:795` |
| `WTA` | `28` | WTA Tour events (slightly lower than ATP due to typically less data). | `config.py:796` |
| `Challenger` | `24` | Challenger-level events. | `config.py:797` |
| `ITF` | `20` | ITF/Futures events (lowest-weighted results). | `config.py:798` |
| `Unknown` | `24` | Default K-factor when tournament level cannot be determined. | `config.py:799` |

**Impact of K-factor changes:**
- Increasing a K-factor makes Elo ratings at that level more volatile (bigger swings per match).
- Decreasing makes ratings more stable but slower to reflect level changes.
- The relative ordering of K-factors creates a hierarchy where Grand Slam results matter most.

---

## Appendix A: Player Metadata Constants

### Hand Mapping (HAND_MAPPING)

| Code | Full Name | Location |
|------|-----------|----------|
| `"R"` | `"Right"` | `config.py:1095` |
| `"L"` | `"Left"` | `config.py:1096` |
| `"U"` | `"Unknown"` | `config.py:1097` |
| `"A"` | `"Ambidextrous"` | `config.py:1098` |

### Injury Status Options (INJURY_STATUS)

| Status | Description | Location |
|--------|-------------|----------|
| `"Active"` | Fully fit | `config.py:1105` |
| `"Minor Concern"` | Minor issue, likely to play | `config.py:1106` |
| `"Questionable"` | May or may not play | `config.py:1107` |
| `"Doubtful"` | Unlikely to play | `config.py:1108` |
| `"Out"` | Confirmed out | `config.py:1109` |
| `"Returning"` | Coming back from injury | `config.py:1110` |

---

## Appendix B: Credentials File Reference

All external service credentials are stored in `<app_root>/credentials.json`. This file must **never** be committed to version control.

```json
{
    "betfair_app_key": "your-betfair-app-key",
    "betfair_username": "your-betfair-username",
    "betfair_password": "your-betfair-password",
    "discord_bot_token": "your-discord-bot-token",
    "discord_webhook": "https://discord.com/api/webhooks/...",
    "supabase_url": "https://xxxxx.supabase.co",
    "supabase_key": "your-supabase-anon-key"
}
```

| Key | Used By | Required |
|-----|---------|----------|
| `betfair_app_key` | `betfair_capture.py`, `local_monitor.py` | Yes (for odds capture) |
| `betfair_username` | `betfair_capture.py`, `local_monitor.py` | Yes (for odds capture) |
| `betfair_password` | `betfair_capture.py`, `local_monitor.py` | Yes (for odds capture) |
| `discord_bot_token` | `local_monitor.py` | Yes (for Discord alerts) |
| `discord_webhook` | `discord_notifier.py` | No (currently disabled) |
| `supabase_url` | `cloud_sync.py` | No (optional cloud sync) |
| `supabase_key` | `cloud_sync.py` | No (optional cloud sync) |

---

## Appendix C: Tournament Name Normalization

The `normalize_tournament_name()` function (`config.py:146-172`) standardizes tournament names from Betfair:

1. Strips year suffixes matching `\s+20[2-3]\d$` (e.g., "Concepcion Challenger 2026" becomes "Concepcion Challenger").
2. Strips Grand Slam prefixes: `Ladies`, `Men's`, `Women's`.
3. Strips trailing whitespace.

This ensures consistent tournament matching between Betfair data and the internal database.

---

## Appendix D: Legacy Aliases

| Alias | Points To | Description | Location |
|-------|-----------|-------------|----------|
| `UNIT_STAKING` | `KELLY_STAKING` | Backwards compatibility alias for the staking configuration dictionary. | `config.py:1029` |

---

*End of Configuration Reference*
