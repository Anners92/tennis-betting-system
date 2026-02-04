# Risk Management Framework

## Tennis Betting System v3.1

**Document Classification:** Internal -- Risk Committee
**Version:** 1.1
**Date:** 5 February 2026
**Owner:** Quantitative Betting Operations

---

## Table of Contents

1. [Risk Framework Overview](#1-risk-framework-overview)
2. [Staking Strategy](#2-staking-strategy)
3. [Model Risk](#3-model-risk)
4. [Bankroll Management](#4-bankroll-management)
5. [Exposure Limits](#5-exposure-limits)
6. [Market Risk](#6-market-risk)
7. [Data Risk](#7-data-risk)
8. [Operational Risk](#8-operational-risk)
9. [Model Validation](#9-model-validation)
10. [Betting Philosophy](#10-betting-philosophy)
11. [Risk Monitoring](#11-risk-monitoring)
12. [Scenario Analysis](#12-scenario-analysis)
13. [Risk Register](#13-risk-register)

---

## 1. Risk Framework Overview

The Tennis Betting System v3.1 operates on the Betfair Exchange across all levels of professional tennis. This framework identifies, quantifies, and mitigates risks across five primary categories.

### 1.1 Risk Categories

| Category | Description | Severity Potential |
|----------|-------------|-------------------|
| **Model Risk** | Inaccurate probability estimates, overfitting, miscalibrated outputs | High |
| **Operational Risk** | System downtime, API failures, database corruption, notification failures | Medium |
| **Data Risk** | Stale odds, incorrect settlement, player name mismatches, scraping failures | Medium-High |
| **Market Risk** | Odds movement, line changes, liquidity withdrawal, exchange restrictions | Medium |
| **Execution Risk** | Bet placement delays, commission changes, manual error, duplicate bets | Low-Medium |

### 1.2 Risk Appetite Statement

The system is currently in a **data-gathering phase**. The primary objective is to accumulate a statistically significant sample (100+ settled bets per model, 500+ total bets) before making optimisation decisions. During this phase, the risk appetite is calibrated to preserve capital while maximising bet volume within controlled limits.

### 1.3 Governance

- All bets must qualify for at least one of six hard models (M1, M3, M4, M5, M7, M8)
- Soft models (M2, M9, M10, M11) provide additional classification without staking impact
- M1 (Triple Confirmation) receives 1.5x staking boost
- No manual overrides of model selections are permitted during the data-gathering phase
- System parameters are defined in `config.py` and version-controlled
- All staking decisions are logged to `staking_decisions.csv` for audit

---

## 2. Staking Strategy

### 2.1 Kelly Criterion Implementation

The system uses a **fractional Kelly** staking approach. The Kelly Criterion is the mathematically optimal strategy for long-term bankroll growth, but the full Kelly is too aggressive in practice due to estimation error. The system employs the following formula:

```
Final Stake = Kelly Stake % x Kelly Fraction x Disagreement Penalty x Odds Multiplier
```

**Source:** `config.py` lines 928-1029, `match_analyzer.py` lines 2384-2665

### 2.2 Kelly Formula (Exact Implementation)

**Step 1 -- Raw Kelly Calculation:**
```
Kelly Stake % = Edge / (Odds - 1)

Where:
  Edge = Our Probability - Implied Probability
  Implied Probability = 1 / Decimal Odds
```

**Step 2 -- Fractional Kelly:**
```
Fractional Kelly % = Kelly Stake % x 0.375
```

The system uses **37.5% of full Kelly** (`kelly_fraction = 0.375`). This is a balanced position between quarter Kelly (0.25, conservative) and half Kelly (0.50, aggressive). The fraction controls the trade-off between expected growth rate and drawdown risk.

**Step 3 -- Market Disagreement Penalty:**

When the system's probability significantly exceeds the market-implied probability, the stake is reduced. The probability ratio (`our_probability / implied_probability`) determines the penalty tier:

| Disagreement Level | Probability Ratio | Penalty Multiplier | Rationale |
|-------------------|-------------------|-------------------|-----------|
| Minor | Up to 1.20x | 1.00 (full stake) | Model and market broadly agree |
| Moderate | 1.20x -- 1.50x | 0.75 (75% stake) | Meaningful disagreement, reduce exposure |
| Major | 1.50x+ | 0.50 (50% stake) | Large disagreement, still bet to build sample |

**Step 4 -- Unit Conversion:**
```
Base Units = Final Stake % / (Unit Size % / 100)
Unit Size = 2.0% of bankroll per unit
```

**Step 5 -- Caps and Rounding:**
- Maximum: 3.0 units per bet (`max_units = 3.0`)
- Minimum: 0.25 units per bet (`min_units = 0.25`)
- Rounding: to nearest 0.5 units
- Below minimum: bet is not placed

### 2.3 Stake Tiers

| Tier | Units | Classification |
|------|-------|---------------|
| Strong | >= 2.0u | High confidence, strong edge |
| Confident | >= 1.0u | Solid edge, reasonable confidence |
| Standard | 0.25u -- 0.5u | Smaller edge, data gathering |
| Below Minimum | < 0.25u | Not placed |

### 2.4 Minimum Odds Floor

**All odds below 1.70 are rejected** (`min_odds = 1.70`). This prevents:
- Exposure to short-priced favourites where a single loss erodes multiple wins
- Insufficient value extraction from thin margins
- Over-reliance on favourites bias

### 2.5 Minimum Opponent Odds Filter

**If either player in a match has odds below 1.05, the match is skipped** (`min_opponent_odds = 1.05`). This serves as a liquidity filter to avoid extremely one-sided markets where price discovery is unreliable.

### 2.6 Betfair Exchange Commission

The system accounts for Betfair's exchange commission on winnings:
- **Current rate: 2%** (`exchange_commission = 0.02`)
- Applied to gross profit on winning bets: `Net Profit = Gross Profit x (1 - 0.02)`
- Losing bets are not subject to commission

### 2.7 Expected Value Threshold

A bet is only placed if:
```
EV = (Our Probability x (Odds - 1)) - (1 - Our Probability) > 5%
```

The minimum EV threshold is **5%** (`min_ev_threshold = 0.05`). A "high value" threshold exists at **10%** (`high_ev_threshold = 0.10`) for reporting purposes.

### 2.8 Staking Modifiers (v3.1)

**M1 Boost:** Premium model (Triple Confirmation: model edge + serve aligned + active players) receives 1.5x staking multiplier.

**No-Data Multiplier:** When serve data or activity scores are missing, stake is reduced to 0.50x.

**Activity-Based Reduction:** When min activity score < 50, additional stake reduction up to 30%.

### 2.9 Enabled Probability Calibration (v3.1)

Probability calibration is now **ENABLED** based on 160+ settled bets showing systematic overconfidence:

| Feature | Status | Configuration |
|---------|--------|---------------|
| Shrinkage Calibration | **ENABLED** | Factor: 0.60 (asymmetric - favorites only) |
| Market Blend | **ENABLED** | Weight: 0.35 (35% market, 65% calibrated) |
| Odds Range Weighting | Disabled | Need 1000+ bets before concluding which odds ranges are profitable |
| Challenger Restrictions | Disabled | Need 1000+ bets before drawing tour-level conclusions |

**Combined effect:** Raw 60% model + 45% market → 56% after shrinkage → 52.15% after blend. Edges roughly halved.

---

## 3. Model Risk

### 3.1 Model Architecture

The system uses a **multi-factor weighted model** with 9 active factors. Win probability is calculated as:

```
Weighted Advantage = SUM(Factor_i x Weight_i) for i in [1..9]
P1 Probability = 1 / (1 + exp(-3 x Weighted Advantage))   [logistic function, k=3]
```

### 3.2 Factor Weights (v3.1 Profile)

| Factor | Weight | Signal |
|--------|--------|--------|
| Surface | 22% | Combined career (40%) and recent 2-year (60%) surface win rates — **strongest signal** |
| Form | 20% | Recent match results (last 20 matches), Elo-expected scoring, recency decay |
| Fatigue | 17% | Rest days, match density (14/30 day windows) — **market underweights this** |
| Ranking | 13% | ATP/WTA ranking converted to Elo via logarithmic scale |
| Perf Elo | 13% | Rolling 12-month results-based Elo rating |
| Recent Loss | 8% | Penalty for losing in last 3 days (-0.10) or 7 days (-0.05) |
| H2H | 5% | Head-to-head record, surface-specific, recency-weighted |
| Momentum | 2% | Surface-specific wins in last 14 days |
| Injury | 0% | **DEPRECATED** — replaced by Activity Edge Modifier |

**Edge Modifiers** (post-probability adjustments, not weighted factors):
- **Serve Edge Modifier**: Reduces edge up to 20% when serve stats (DR) conflict with the pick
- **Activity Edge Modifier**: Reduces edge up to 40% for returning/inactive players (replaces injury factor)

Legacy factors (opponent_quality, recency) carry 0% weight and are retained for backward compatibility only.

### 3.3 The Eleven Betting Models

Each bet must qualify for at least one hard model. Models are not mutually exclusive; a single bet may qualify for multiple models.

#### Hard Models (stake-determining)

**Model 1 -- "Triple Confirmation" (Premium)**
- **Requirements:** Model edge + serve stats aligned + both players active
- **Staking:** 1.5x boost (premium confidence)
- **Risk profile:** Highest-confidence plays where all signals agree
- **Performance (n=40):** 65.0% win rate, +55.6% ROI when combined with M11

**Model 3 -- "Sharp" (Moderate Edge)**
- **Edge requirement:** 5% to 15% (`0.05 <= edge <= 0.15`)
- **Risk profile:** Core model targeting meaningful disagreement with market
- **Warning:** Pure M3 (no other models) has shown 7.7% win rate at n=39 — avoid in isolation

**Model 4 -- "Favourites" (High Probability)**
- **Probability requirement:** Our probability >= 60% (`our_probability >= 0.60`)
- **Risk profile:** Backs strongly favoured players where our model is highly confident

**Model 5 -- "Underdog" (Upset Value)**
- **Requirements:** Edge >= 10%, odds 3.00-10.00, 15+ matches for both players
- **Risk profile:** Targets genuine upsets with strong data support

**Model 7 -- "Grind" (Small Edge, Short Odds)**
- **Edge requirement:** 3% to 8%, odds < 2.50
- **Risk profile:** High strike-rate, small-margin strategy

**Model 8 -- "Profitable Baseline" (Probability + Short Odds)**
- **Probability requirement:** >= 55%, odds < 2.50
- **Risk profile:** Safety net where probability and odds align

#### Soft Models (tag-only, no staking impact)

**Model 2 -- "Data Confirmed":** Serve data available + both players active
**Model 9 -- "Value Zone":** Odds 2.00-2.99, serve data, edge 5-10%
**Model 10 -- "Confident Grind":** Odds < 2.20, prob >= 55%, both active
**Model 11 -- "Surface Edge":** Surface factor >= 0.15, odds 2.00-3.50, edge >= 5%

#### Fade Model

**Model 12 -- "2-0 Fade":** Pure M3/M5 triggers + opponent odds 1.20-1.50 → bet opponent 2-0

#### Odds Floor (All Models)
- **All models reject odds below 1.70** (`min_odds_floor = 1.70`)
- If `odds < 1.70`, the function returns `"None"` regardless of edge or probability

#### Key Thesis (n=160 settled bets)
- **M1+M11 combination:** 65.0% win rate, +55.6% ROI at n=40 — proven edge
- **Pure M3 only:** 7.7% win rate at n=39 — catastrophic in isolation

### 3.4 Model Overlap and Disagreement

A bet can qualify for multiple models simultaneously. For example:
- A bet at odds 2.10 with our probability of 62% and implied probability of 47.6% has an edge of 14.4%, qualifying for **M3** (5-15% edge) and **M4** (prob >= 60%)
- A bet at odds 2.20 with our probability of 56% and implied probability of 45.5% has an edge of 10.5%, qualifying for **M3** only

When models disagree (e.g., a bet qualifies for M3 but not M4), this is expected and reflects different filtering criteria. The system places the bet if it qualifies for **any** model. This is intentional during the data-gathering phase to maximise sample size per model.

### 3.5 Probability Model Risks

| Risk | Description | Mitigation |
|------|-------------|------------|
| Overconfidence | Model probabilities may be systematically too extreme | Calibration framework ready (disabled pending 500+ sample) |
| Factor correlation | Form and surface may overlap | Weight optimisation post-data-gathering |
| Data sparsity | Players with <3 matches get neutral form (50) | Has_data flag triggers weight redistribution to ranking |
| Ranking staleness | ATP/WTA rankings update weekly | Performance Elo provides results-based supplement |
| Large ranking gap bias | Huge skill gaps can dominate | Dynamic weight boost (up to 0.60 for ranking) with Elo probability blend |
| Breakout blindness | Rising players rated by stale ranking | Breakout detection system adjusts effective ranking |

### 3.6 Data Quality Gates for Stakes

For bets of **2.0 units or higher**, additional data quality checks apply:

1. **Minimum matches:** Both players need 5+ matches in last 60 days (3+ for lower stakes)
2. **Form comparison:** If the selected player's 2026 form is 15%+ worse than the opponent's, the bet is blocked
3. **Tennis Explorer verification:** If database shows insufficient matches, the system checks Tennis Explorer live to verify
4. **Stake reduction:** If a player has <5 matches but played this month, stake is reduced by 50% rather than blocked
5. **Confidence adjustment for 2u+ stakes:**
   - No surface data for either player: -20%
   - Surface data missing for one player: -10%
   - No H2H history: -10%
   - Limited form data (<5 matches per player): -15%
   - Ranking dominates (>40% of edge): -10%
   - Floor: confidence multiplier never drops below 0.50

---

## 4. Bankroll Management

### 4.1 Unit Size Definition

```
1 Unit = 2.0% of total bankroll
```

This is defined in `KELLY_STAKING["unit_size_percent"] = 2.0`. At a GBP 1,000 bankroll, 1 unit = GBP 20.

### 4.2 Stake Range

| Metric | Value |
|--------|-------|
| Minimum bet | 0.25 units (0.5% of bankroll) |
| Maximum bet | 3.0 units (6.0% of bankroll) |
| Typical bet | 0.5 -- 1.5 units (1% -- 3% of bankroll) |

### 4.3 Drawdown Tolerance

The fractional Kelly approach (37.5%) provides significant drawdown protection compared to full Kelly:

| Kelly Fraction | Expected Max Drawdown (1000 bets) | Growth Rate vs Full Kelly |
|---------------|-----------------------------------|--------------------------|
| Full (1.00) | ~50-60% | 100% |
| Half (0.50) | ~25-35% | ~75% |
| **0.375 (Current)** | **~20-28%** | **~65%** |
| Quarter (0.25) | ~15-20% | ~50% |

### 4.4 When to Reduce Stakes

Stakes should be reduced by 50% (move to 0.1875 Kelly fraction) when:
- Bankroll has declined by 20% from peak
- All four models show negative ROI over 50+ bets each
- Average CLV is consistently negative over 100+ bets (indicating systematic mispricing)

### 4.5 When to Stop Betting

The system should be paused entirely when:
- Bankroll has declined by 40% from peak
- Primary data source (Betfair API) is unavailable for >24 hours
- A critical software bug is discovered affecting probability calculations
- Database corruption is detected

### 4.6 When to Resume

Resume at reduced stakes (50% of normal) when:
- Root cause of any pause trigger has been identified and resolved
- At least one model shows positive CLV over last 50 bets
- All data sources are confirmed operational

---

## 5. Exposure Limits

### 5.1 Single-Event Exposure

| Limit | Value | Source |
|-------|-------|--------|
| Maximum stake per bet | 3.0 units (6% of bankroll) | `KELLY_STAKING["max_units"] = 3.0` |
| Minimum stake per bet | 0.25 units (0.5% of bankroll) | `KELLY_STAKING["min_units"] = 0.25` |
| Both sides blocked | Yes -- system prevents betting both sides of same match | Duplicate check: `check_match_already_bet()` |

### 5.2 Concurrent Exposure

The system does not currently enforce hard limits on concurrent open bets. However, the following soft limits are recommended:

| Metric | Recommended Limit | Rationale |
|--------|-------------------|-----------|
| Maximum concurrent pending bets | 20 | Correlation risk in same-day events |
| Maximum single-tournament open bets | 5 | Tournament-level correlation |
| Maximum daily new bets placed | 15 | Operational review capacity |
| Maximum daily gross exposure | 15 units (30% of bankroll) | Absolute loss ceiling per day |

### 5.3 Liquidity Filters

- **Minimum matched liquidity per market:** GBP 25 (`MIN_MATCHED_LIQUIDITY = 25`)
- **Minimum opponent odds:** 1.05 (filters out extreme mismatch markets with no liquidity)
- **Doubles matches:** Excluded entirely (detected by '/' in player names)

---

## 6. Market Risk

### 6.1 Odds Movement Risk

**Risk:** Odds captured during analysis may have moved by the time a bet is placed or by the time the match starts.

**Quantification:**
- Betfair odds refresh cycle: approximately every 5 minutes during the system's quick refresh
- Typical odds movement for tennis match-winner markets: 2-5% implied probability shift over 4-8 hours pre-match
- Steam moves (sharp money) can shift odds 10-20% in minutes

**Mitigation:**
- Closing Line Value (CLV) tracking compares placement odds to closing odds from Betfair
- Positive CLV over time is the strongest indicator of genuine edge
- Discord alerts notify immediately when value is detected, reducing delay

### 6.2 Closing Line Value (CLV) Tracking

CLV measures execution quality:
```
CLV = (Closing Implied Probability - Placement Implied Probability)
```

Positive CLV means we consistently get better odds than the market's final assessment, which is the hallmark of sharp betting.

The system:
- Captures closing odds from Betfair before match start
- Stores CLV per bet in the database
- Reports average CLV per model in the statistics breakdown
- Discord bot includes CLV data in result alerts

### 6.3 Exchange-Specific Risks

| Risk | Description | Impact | Mitigation |
|------|-------------|--------|------------|
| Commission increase | Betfair may raise commission from 2% to 5%+ | Reduces net edge by ~3% | Monitor Betfair Rewards tier; model uses configurable `exchange_commission` |
| Account restriction | Betfair may impose premium charges on winning accounts | Up to 60% effective commission | Diversify to multiple exchanges; keep below premium charge thresholds |
| Liquidity withdrawal | Market makers may pull liquidity pre-match | Unable to place at desired odds | Minimum liquidity filter (GBP 25); place bets earlier when liquidity exists |
| Market suspension | Betfair suspends market during in-play transitions | Cannot place or cancel bets | Only pre-match betting; avoid in-play exposure |

---

## 7. Data Risk

### 7.1 Risk Assessment Matrix

| Risk | Likelihood | Impact | Detection | Mitigation |
|------|-----------|--------|-----------|------------|
| **Stale odds** | Medium | Medium | CLV tracking shows negative CLV trend | Quick refresh cycle (~5 min); Discord alerts for immediate action |
| **Incorrect settlement** | Low | High | P/L reconciliation against Betfair account | Manual settlement review; Betfair live score checking; void option available |
| **Player name mismatch** | Medium | Medium | Unknown player resolver dialog triggers | Name mappings JSON file (persistent); fuzzy matching with similarity scores; manual resolution workflow |
| **Scraping failure** | Medium | Low-Medium | Missing/incomplete data in analysis | Fallback to database historical data; Tennis Explorer verification; multiple data sources |
| **Database corruption** | Low | Critical | Application crash on startup; SQLite integrity check | Regular backups; Supabase cloud sync; seed database restoration |
| **Rankings data staleness** | Medium | Low | Rankings cache age check | Rankings cache JSON updated from scraper; fallback to database rankings; odds-based rank estimation for unranked players |

### 7.2 Player Name Resolution

Betfair uses non-standard player names that often differ from database names. The system manages this through:

1. **Name Mappings File** (`name_mappings.json`): Persistent mapping from Betfair names to database player IDs
2. **Fuzzy Matching** (`name_matcher.py`): Similarity scoring to suggest likely matches
3. **Interactive Resolution**: Unknown players trigger a dialog allowing manual matching, new player addition, or bet skipping
4. **Odds-Based Rank Estimation**: For completely unknown players, odds are used to estimate ranking (e.g., odds < 1.5 suggests top 50)

### 7.3 Data Source Redundancy

| Data Type | Primary Source | Fallback | Second Fallback |
|-----------|---------------|----------|----------------|
| Live odds | Betfair Exchange API | None (required) | -- |
| Match results | Tennis Explorer (via GitHub scraper) | Database historical | Manual entry |
| Player rankings | Rankings cache JSON (scraped) | Database `players.current_ranking` | Odds-based estimation |
| Surface detection | `config.py` tournament mapping | Explicit surface tags in data | Default to Hard |
| Serve/return stats | Tennis Ratio scraper (13 metrics) | None | -- |
| Performance Elo | `performance_elo.py` calculation | Ranking-derived Elo fallback | Odds-based estimation |

---

## 8. Operational Risk

### 8.1 Risk Assessment Matrix

| Risk | Likelihood | Impact | Detection | Mitigation |
|------|-----------|--------|-----------|------------|
| **System downtime** | Low | Medium | No Discord alerts; no bet suggestions | Local monitor (`local_monitor.py`) runs as background service; `start_monitor.vbs` for silent startup |
| **Betfair API failure** | Medium | High | Connection timeout errors; no odds refresh | Retry logic; graceful degradation; manual bet entry fallback |
| **Discord bot failure** | Medium | Low | No notifications received | Bot has `!refresh` command for manual trigger; separate from core analysis |
| **Database corruption** | Low | Critical | Application crash; query errors | Supabase cloud sync; seed database copy on first run; SQLite WAL mode |
| **Installer/deployment failure** | Low | Low | Version mismatch; missing modules | Build pipeline documented; module checklist in `build_exe.py` |
| **Tennis Explorer/Ratio scraper blocked** | Medium | Medium | HTTP errors; empty data returns | User-agent spoofing; rate limiting; Tennis Ratio returns 200 for unknown players (handled) |

### 8.2 System Architecture Resilience

The system has three operational modes:

1. **Desktop Application** (`main.py`): Full GUI with analysis, tracking, and management
2. **Local Monitor** (`local_monitor.py`): Background service with Discord bot for automated monitoring
3. **Cloud Backtester** (`cloud_backtester.py`): Separate process for historical validation

Each can operate independently. The local monitor can detect and report value bets even if the desktop application is not running.

### 8.3 Database Protection

- **Location:** `C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db`
- **Schema:** 16 tables covering players (~3,100), matches (~65,000), bets, analyses, and configuration
- **Cloud sync:** Optional Supabase integration for off-site backup
- **Seed database:** Bundled with installer for first-run initialisation
- **Bet cloud sync:** Individual bets are synced to Supabase on creation and settlement

---

## 9. Model Validation

### 9.1 Sample Size Requirements

**Minimum sample sizes before drawing conclusions:**

| Level | Minimum Bets | Rationale |
|-------|-------------|-----------|
| Per model | 100+ | Statistical power to detect 5% ROI difference from zero |
| Total system | 500+ | Sufficient for calibration analysis and factor tuning |
| Per tour level | 200+ | ATP/WTA/Challenger/ITF each need independent validation |
| Per odds range | 100+ | Short/medium/long odds may have different edge profiles |
| Per surface | 100+ | Surface-specific model accuracy assessment |

These requirements are explicitly stated in the betting philosophy: *"Need 100+ bets per model before drawing conclusions."*

### 9.2 Calibration Monitoring

The system's probability calibration framework is now **ENABLED** (v3.1):

**Active calibration (ENABLED):**
- **Shrinkage:** Factor 0.60 (asymmetric — favorites only). Pulls probabilities toward 50%.
- **Market Blend:** Weight 0.35. Final = 65% calibrated + 35% market.

**Combined effect:** Model's raw 60% → 56% after shrinkage → 52.15% after market blend with 45% market odds.

**Legacy calibration types (not active):**
- **Polynomial:** Quadratic calibration curve (legacy, parameters: a=7.5566, b=-7.3102, c=1.9932)
- **Linear:** Simple multiplier + offset (legacy, multiplier=0.70, offset=0.15)

**Calibration was enabled because:**
1. 160+ settled bets showed systematic overconfidence (47.7% predicted vs 34.8% actual)
2. Brier score analysis confirmed the model overestimated probabilities (p=0.014)
3. Asymmetric shrinkage chosen as favorites were most affected

### 9.3 ROI Tracking

The system tracks ROI at multiple granularities:

| Dimension | Tracked | Breakdowns |
|-----------|---------|------------|
| Overall | Total staked, profit/loss, ROI % | Cumulative and rolling |
| By model | All models (M1-M12) | Win rate, ROI, average CLV |
| By tour | Grand Slam, ATP, WTA, Challenger, ITF | Win rate, ROI |
| By surface | Hard, Clay, Grass, Carpet | Win rate, ROI |
| By odds range | 1.00-1.50, 1.50-2.00, 2.00-3.00, 3.00-5.00, 5.00+ | Win rate, ROI |
| By stake size | 0.5u, 1.0u, 1.5u, 2.0u, 2.5u, 3.0u | Win rate, ROI |
| By gender | Male (ATP/Challenger/GS), Female (WTA/ITF) | Win rate, ROI |
| By month | Monthly time series | Bets, staked, profit, ROI |
| By week | Weekly P/L grid | Uses `settled_at` date |

### 9.4 CLV Analysis

CLV (Closing Line Value) is the gold standard for validating betting skill:

- **Positive average CLV** over 200+ bets: Strong evidence of genuine edge
- **Negative average CLV** over 200+ bets: Model may be capturing stale lines, not real value
- **CLV is tracked per model** to identify which models capture real value vs. noise

### 9.5 Backtesting

The cloud backtester (`cloud_backtester.py`) validates the model against historical data with:
- **Lookahead bias prevention:** Only uses data available at the time of each historical match
- **Match-time rankings:** Uses ranking overrides to simulate historical ranking positions
- **Out-of-sample testing:** Data is split to avoid fitting parameters to test data

---

## 10. Betting Philosophy

### 10.1 Core Principles

These rules are **mandatory** and override any model output or intuition:

1. **Bet on ALL levels of tennis** -- ATP, WTA, Challengers, and ITF. No level is excluded. The market is less efficient at lower levels, which may provide greater edge.

2. **Only bet on model plays** -- Every bet must qualify for at least one hard model (M1, M3, M4, M5, M7, M8). No discretionary bets. No "feel" bets. The model decides.

3. **Need 100+ bets per model before drawing conclusions** -- No model will be disabled, modified, or weighted differently until it has 100+ settled results. Early variance is expected and tolerated.

4. **No premature optimisation** -- During the data-gathering phase:
   - Do not restrict which tour levels to bet on
   - Do not restrict which odds ranges to bet on
   - Do not tighten or loosen model thresholds
   - Do not enable probability calibration until 500+ bets
   - Gather data first, optimise later

### 10.2 Rationale

Tennis betting markets vary significantly by tour level:
- **ATP/Grand Slam:** Highly efficient, thin edges, deep liquidity
- **WTA:** Less efficient, higher variance, moderate liquidity
- **Challengers:** Under-followed, potential for larger edges, lower liquidity
- **ITF:** Least efficient but highest data risk, low liquidity

By betting across all levels, the system:
- Maximises sample size for validation
- Avoids premature filtering that could exclude profitable niches
- Builds a comprehensive dataset for future model refinement

---

## 11. Risk Monitoring

### 11.1 Daily Monitoring

| Metric | Action Trigger | Response |
|--------|---------------|----------|
| P/L for the day | Loss exceeds 5 units | Review all open bets; consider pausing for the day |
| Number of bets placed | > 15 bets in a day | Review bet quality; ensure not chasing losses |
| Betfair API status | Connection failure | Check credentials; restart monitor; manual fallback |
| Discord alert delivery | No alerts for 6+ hours during active schedule | Check bot status; run `!refresh` command |
| Odds freshness | Last capture > 15 minutes old | Trigger manual refresh; investigate API status |

### 11.2 Weekly Monitoring

| Metric | Action Trigger | Response |
|--------|---------------|----------|
| Weekly P/L | Loss exceeds 10 units | Full review of model performance; check for data issues |
| Win rate by model | Any model below 30% win rate (50+ bets) | Investigate factor scores for those bets |
| Average CLV | CLV negative for 2 consecutive weeks | Review odds capture timing; check for stale data |
| Data quality | > 5 unknown player failures in a week | Update name mappings; check Betfair name format changes |
| System uptime | Monitor downtime > 2 hours total | Review startup reliability; check Windows Task Scheduler |

### 11.3 Monthly Monitoring

| Metric | Action Trigger | Response |
|--------|---------------|----------|
| Monthly ROI | Negative ROI for 2 consecutive months | Formal model review; compare to CLV-based expected ROI |
| Model comparison | Any model with < -10% ROI over 100+ bets | Consider disabling that model (only if 100+ sample met) |
| Bankroll trajectory | Below 70% of peak | Reduce stakes by 50%; conduct full system audit |
| Sample size progress | Not on track for 100 bets/model within 3 months | Investigate why bet volume is low; check filters |
| Factor calibration | Brier score analysis (when 500+ bets) | Enable calibration if overconfidence confirmed |

### 11.4 Warning Signs

The following patterns should trigger immediate investigation:

1. **Consistent negative CLV** -- Indicates the model is not finding genuine value but rather stale lines
2. **Win rate below implied probability across all models** -- Model is systematically overestimating player chances
3. **All long-odds bets losing** -- Model may have a systematic bias toward underdogs
4. **Clustering of losses in one tour level** -- Data quality may differ by level
5. **Sudden spike in "unknown player" rate** -- Betfair may have changed name formats

---

## 12. Scenario Analysis

### 12.1 Scenario: 20-Bet Losing Streak

**Probability:** At a 55% average win rate, the probability of 20 consecutive losses is approximately 0.45^20 = 0.000001 (one in a million). At 45% win rate, it is 0.55^20 = 0.0002 (one in 5,000). This is extremely unlikely but must be planned for.

**Financial impact (worst case):**
- 20 bets at average 1.5u = 30 units lost = 60% of bankroll
- 20 bets at average 0.75u = 15 units lost = 30% of bankroll

**Response protocol:**
1. After 10 consecutive losses: Automated alert via Discord; manual review of last 10 bets for data errors
2. After 15 consecutive losses: Reduce all stakes by 50%; investigate model calculation integrity
3. After 20 consecutive losses: Pause system entirely; full audit of probability model, data sources, and bet settlement accuracy

**Recovery:** Resume at 50% stakes after root cause analysis. Require 10 consecutive profitable days before returning to full stakes.

### 12.2 Scenario: All Models Negative ROI for a Month

**Probability:** Moderate during early data-gathering phase. Expected during normal variance periods.

**Financial impact:** Depends on volume. At 100 bets/month averaging 1u at -5% ROI = -5 units = -10% of bankroll.

**Response protocol:**
1. Verify settlement accuracy (spot-check 10 random bets against Betfair account)
2. Review CLV data: if average CLV is positive despite negative ROI, this is likely variance -- continue
3. If average CLV is also negative: the model is not finding value. Review factor weights and data quality
4. If sample per model is still below 100: **do not change anything** -- this is expected variance
5. If sample per model exceeds 100 and ROI is below -10%: consider disabling the worst-performing model

### 12.3 Scenario: Betfair Account Restricted

**Probability:** Low-medium. Betfair Exchange accounts are less prone to restriction than bookmaker accounts, but premium charges can apply to consistent winners.

**Impact:**
- Premium charge (20-60% on net profits): Significantly reduces net edge
- Account closure: Complete loss of betting venue

**Response protocol:**
1. Monitor Betfair Rewards tier and premium charge status weekly
2. Maintain accounts on alternative exchanges (Smarkets, Betdaq) as backup
3. System architecture is exchange-agnostic -- odds capture and bet placement can be redirected
4. Store all historical data locally and in Supabase cloud -- no data loss if account closed
5. Commission rate is configurable (`exchange_commission`); update if premium charges apply

### 12.4 Scenario: Primary Data Source Down for a Week

**Data sources at risk:**
- **Betfair API** (odds): Cannot generate new bets without live odds. Impact = Critical.
- **Tennis Explorer / GitHub scraper** (match results): Historical model degrades but existing data usable. Impact = Medium.
- **Tennis Ratio** (serve stats): Supplementary data only. Impact = Low.

**Response protocol for Betfair API outage:**
1. Day 1: Investigate API status; check Betfair status page; retry authentication
2. Day 2: Switch to manual odds entry if critical matches identified
3. Day 3-7: Pause automated betting; focus on data quality tasks (player matching, database cleanup)
4. Recovery: Resume automated operation once API confirmed stable for 4+ hours

**Response protocol for Tennis Explorer/GitHub outage:**
1. System continues with existing database data (65,000+ historical matches)
2. Form scores become increasingly stale after 7-14 days
3. Rankings can be supplemented from ATP/WTA websites manually
4. Flag all bets during this period as "reduced data quality" in notes

---

## 13. Risk Register

### 13.1 Complete Risk Register

| ID | Risk | Category | Likelihood | Impact | Risk Score | Mitigation | Owner | Review Frequency |
|----|------|----------|-----------|--------|------------|------------|-------|-----------------|
| R01 | Model overconfidence (systematic probability overestimation) | Model | High | High | **Critical** | Fractional Kelly (0.375); calibration framework pending 500+ sample; CLV tracking | Quant | Monthly |
| R02 | Insufficient sample size leading to premature optimisation | Model | Medium | High | **High** | 100+ bets/model minimum rule; philosophy of "gather data first" | Quant | Monthly |
| R03 | Factor weight miscalibration | Model | Medium | Medium | **Medium** | Backtesting with lookahead bias prevention; multiple weight profiles available | Quant | Quarterly |
| R04 | Breakout detection failure (player improvement undetected) | Model | Medium | Low | **Low** | Breakout detection system with configurable thresholds; Performance Elo supplement | Quant | Monthly |
| R05 | Stale odds at time of bet placement | Market | Medium | Medium | **Medium** | 5-minute refresh cycle; CLV tracking; Discord instant alerts | Operations | Weekly |
| R06 | Betfair commission increase / premium charges | Market | Low | High | **Medium** | Configurable commission rate; alternative exchange accounts | Operations | Monthly |
| R07 | Betfair account restriction | Market | Low | Critical | **High** | Alternative exchange readiness; local data storage; Supabase backup | Operations | Monthly |
| R08 | Line manipulation / match fixing | Market | Low | High | **Medium** | Liquidity filter (GBP 25 minimum); odds floor (1.70); unusual movement review | Operations | Weekly |
| R09 | Player name mismatch causing wrong analysis | Data | Medium | Medium | **Medium** | Name mappings JSON; fuzzy matching; interactive resolution dialog; odds-based rank estimation | Data | Weekly |
| R10 | Database corruption | Operational | Low | Critical | **High** | Supabase cloud sync; seed database restoration; SQLite WAL mode | Tech | Monthly |
| R11 | Betfair API connection failure | Operational | Medium | High | **High** | Retry logic; graceful degradation; manual entry fallback; local monitor watchdog | Tech | Daily |
| R12 | Discord notification failure | Operational | Medium | Low | **Low** | Separate from core analysis; `!refresh` manual command; desktop app independent | Tech | Weekly |
| R13 | Duplicate bet placement (both sides of match) | Execution | Low | High | **Medium** | `check_match_already_bet()` function; tournament + match_description unique check | Tech | Per bet |
| R14 | Tennis Explorer scraper blocked/rate-limited | Data | Medium | Medium | **Medium** | User-agent rotation; rate limiting; HTTP 200 false-positive handling for Tennis Ratio | Data | Weekly |
| R15 | Incorrect bet settlement | Execution | Low | Medium | **Medium** | Live score checking via Betfair; manual settlement review; void option | Operations | Per settlement |
| R16 | Surface detection error (wrong surface assigned) | Data | Low | Medium | **Low** | Centralised `get_tournament_surface()` with word-boundary matching; grass season check (June-July only); explicit surface tags override | Data | Per tournament |
| R17 | Rankings data staleness (>7 days old) | Data | Medium | Low | **Low** | Rankings cache with scraper refresh; database fallback; Performance Elo supplement; odds-based estimation | Data | Weekly |
| R18 | Loss of local machine (hardware failure) | Operational | Low | High | **Medium** | Supabase cloud sync; installer available on GitHub Releases; source code in OneDrive | Tech | Monthly |
| R19 | Bankroll decline exceeding 40% | Financial | Low | Critical | **Critical** | Fractional Kelly; max 3u per bet; 6% max bankroll per event; drawdown monitoring with pause triggers | Quant | Daily |
| R20 | Model drift (market adapts to system's patterns) | Model | Low | Medium | **Low** | System operates at scale too small to move markets; multiple weight profiles for adaptation | Quant | Quarterly |

### 13.2 Risk Score Methodology

```
Risk Score = Likelihood x Impact

Likelihood: Low (1), Medium (2), High (3)
Impact:     Low (1), Medium (2), High (3), Critical (4)

Score Ranges:
  1-2:  Low
  3-4:  Medium
  6-8:  High
  9-12: Critical
```

---

## Appendix A: Key Configuration Parameters Reference

All parameters below are defined in `config.py` and are the single source of truth for the system.

| Parameter | Value | Location |
|-----------|-------|----------|
| `kelly_fraction` | 0.375 | `KELLY_STAKING` |
| `m1_boost` | 1.50 | `KELLY_STAKING` |
| `unit_size_percent` | 2.0% | `KELLY_STAKING` |
| `exchange_commission` | 0.02 (2%) | `KELLY_STAKING` |
| `min_odds` | 1.70 | `KELLY_STAKING` |
| `min_opponent_odds` | 1.05 | `KELLY_STAKING` |
| `min_units` | 0.25 | `KELLY_STAKING` |
| `max_units` | 3.0 | `KELLY_STAKING` |
| `no_data_multiplier` | 0.50 | `KELLY_STAKING` |
| `min_ev_threshold` | 0.05 (5%) | `BETTING_SETTINGS` |
| `high_ev_threshold` | 0.10 (10%) | `BETTING_SETTINGS` |
| `max_odds` | 10.0 | `BETTING_SETTINGS` |
| `min_probability` | 0.10 (10%) | `BETTING_SETTINGS` |
| `min_model_confidence` | 0.30 (30%) | `KELLY_STAKING` |
| `disagreement_minor_max_ratio` | 1.20 | `KELLY_STAKING` |
| `disagreement_moderate_max_ratio` | 1.50 | `KELLY_STAKING` |
| `disagreement_major_penalty` | 0.50 | `KELLY_STAKING` |
| `calibration_enabled` | **True** | `PROBABILITY_CALIBRATION` |
| `shrinkage_factor` | 0.60 | `PROBABILITY_CALIBRATION` |
| `market_blend_enabled` | **True** | `MARKET_BLEND` |
| `market_blend_weight` | 0.35 | `MARKET_BLEND` |
| `challenger_restrictions_enabled` | False | `KELLY_STAKING` |

## Appendix B: Model Qualification Summary

```
Odds Floor (all models): odds >= 1.70

HARD MODELS (stake-determining):
Model 1 ("Triple"):    model_edge + serve_aligned + both_active (1.5x stake)
Model 3 ("Sharp"):     0.05 <= edge <= 0.15
Model 4 ("Favourites"): our_probability >= 0.60
Model 5 ("Underdog"):  edge >= 0.10 AND 3.00 <= odds <= 10.00 AND 15+ matches
Model 7 ("Grind"):     0.03 <= edge <= 0.08 AND odds < 2.50
Model 8 ("Baseline"):  our_probability >= 0.55 AND odds < 2.50

SOFT MODELS (tag-only):
Model 2 ("Data"):      serve_data + both_active
Model 9 ("Value"):     2.00 <= odds <= 2.99 AND serve_data AND 0.05 <= edge <= 0.10
Model 10 ("Conf"):     odds < 2.20 AND prob >= 0.55 AND both_active
Model 11 ("Surface"):  surface_factor >= 0.15 AND 2.00 <= odds <= 3.50 AND edge >= 0.05

FADE MODEL:
Model 12 ("Fade"):     pure_M3_or_M5 AND 1.20 <= opp_odds <= 1.50 → bet opponent 2-0

Edge = our_probability - (1 / odds)

KEY PERFORMANCE (n=160):
- M1+M11 combined: 65.0% win, +55.6% ROI
- Pure M3 only: 7.7% win — avoid
```

## Appendix C: Factor Weight Profiles

| Profile | Surface | Form | Fatigue | Ranking | Perf Elo | Recent Loss | H2H | Momentum | Injury |
|---------|---------|------|---------|---------|----------|-------------|-----|----------|--------|
| **v3.1 Default** | 0.22 | 0.20 | 0.17 | 0.13 | 0.13 | 0.08 | 0.05 | 0.02 | 0.00 |
| Form Focus | 0.15 | 0.35 | 0.10 | 0.10 | 0.10 | 0.08 | 0.05 | 0.02 | 0.00 |
| Surface Focus | 0.35 | 0.15 | 0.10 | 0.10 | 0.10 | 0.08 | 0.05 | 0.02 | 0.00 |
| Ranking Focus | 0.15 | 0.15 | 0.10 | 0.25 | 0.15 | 0.08 | 0.05 | 0.02 | 0.00 |
| Fatigue Focus | 0.15 | 0.15 | 0.30 | 0.10 | 0.10 | 0.08 | 0.05 | 0.02 | 0.00 |

**Note:** Injury factor is deprecated in v3.1 (weight = 0). The Activity Edge Modifier provides more reliable returning/inactive player detection.

## Appendix D: Edge Modifiers

| Modifier | Trigger | Max Reduction | Notes |
|----------|---------|---------------|-------|
| Serve Edge | DR gap ≥ 0.10 conflicting with pick | 20% | Linear scale to gap 0.30 |
| Activity Edge | Min activity score < 80 | 40% | Both active = no reduction |

---

*Document prepared for the Risk Committee. All parameters are extracted directly from system source code (v3.1, 5 February 2026). This document should be reviewed and updated whenever material changes are made to model parameters, staking configuration, or system architecture.*
