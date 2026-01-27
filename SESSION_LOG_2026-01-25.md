# Session Log - 2026-01-25

## Session Status: ACTIVE

---

## WinUI 3 UI Exploration (Latest)

### What Was Done
- Explored UI framework options for rebuilding the system (PyQt6, WinUI 3, Electron, Tauri)
- Determined **C# + WinUI 3** is best for professional desktop betting apps
- Installed **Visual Studio Community 2026** with WinUI workload
- Created proof of concept in `winui-poc/` folder
- Styled with glassmorphism dark theme (pink/purple/cyan gradients)
- Added professional trading platform features:
  - Sparkline trend charts
  - Real-time LIVE indicators with timestamps
  - Model performance bars (visual ROI comparison)
  - Upcoming value bets panel with EV badges
  - Data-dense tables with quick filters
  - Sidebar with quick stats and connection status

### Files Created
- `winui-poc/` - Complete WinUI 3 proof of concept
- `FUTURE_SYSTEM_UI.md` - Vision document with migration path

### Current State
- POC runs successfully in Visual Studio (F5)
- Professional dark theme matching fintech/trading apps
- Sample data showing dashboard layout
- Not connected to real data (visual mockup only)

### Next Steps (If Pursuing WinUI Rebuild)
1. Set up MVVM architecture
2. Connect to SQLite database
3. Port Betfair API integration to C#
4. Build out each page with real data binding

---

## Confidence Filter Removed

### Analysis of Historical Bets
Analyzed 77 settled bets to check if confidence was useful:

| Model Prob | Win Rate | P/L | ROI |
|------------|----------|-----|-----|
| <40% (underdogs) | 40% | +5.71u | **+57%** |
| 40-50% | 28% | -6.10u | -21% |
| 50-60% | 21% | -17.68u | -74% |
| 60-70% | 36% | -3.59u | -33% |
| >70% (favorites) | 100% | +10.76u | **+359%** |

**Key finding:** Model does well at extremes, poorly in the middle. Confidence wasn't being stored/used meaningfully.

### Changes Made
- **Removed confidence filter entirely** - was filtering out profitable underdog bets
- **Lowered min units to 0.5** (was 1.0)
- Remaining filters: Min EV 5%, Max EV 100%, Min Units 0.5

### Files Modified
- `src/bet_suggester.py` - Removed confidence from filter_settings, UI dialog, analysis logic, and auto mode

### Installer Rebuilt
`installer_output\TennisBettingSystem_Setup_1.4.4.exe`

---

## The Odds API Integration (Pinnacle Comparison)

### Overview
Added integration with The Odds API to compare Betfair odds against Pinnacle and other bookmakers. This helps validate that captured odds are accurate.

### Setup Required
1. Sign up at https://the-odds-api.com/ (free tier = 500 requests/month)
2. Get your API key
3. Add to `credentials.json`: `"odds_api_key": "YOUR_KEY"`

### Features
- Fetches odds from 40+ bookmakers including Pinnacle, Bet365, William Hill
- 15-minute caching to minimize API usage
- Fuzzy player name matching (handles Betfair vs bookmaker name variations)
- Compares odds and flags discrepancies >15%

### Integration with Betfair Capture
The Pinnacle comparison is now automatic when capturing Betfair odds:
- Fetches Pinnacle odds in bulk (1 API call per capture)
- Compares each match against Pinnacle using **directional logic**
- Stores Pinnacle odds alongside Betfair odds

### Directional Comparison Logic (Updated)

**Key insight:** We only care if Betfair is offering WORSE odds than Pinnacle (bad value). If Betfair offers BETTER odds, that's good for us!

| Scenario | Example | Action |
|----------|---------|--------|
| BF < PIN by >15% | BF:3.00 vs PIN:7.00 | **SKIP** (bad value) |
| BF < PIN by 7.5-15% | BF:2.00 vs PIN:2.30 | **CAUTION** |
| BF > PIN by >15% | BF:27.00 vs PIN:21.65 | **GOOD VALUE** (keep!) |
| Otherwise | Similar odds | OK |

Console output example:
```
Fetching Pinnacle odds for comparison...
Pinnacle: 11 matches available for comparison
  SKIPPED (BF < PIN): Player A BF:3.00 vs PIN:7.50 - Betfair odds lower than Pinnacle by 60% (bad value)
  GOOD VALUE: Darderi BF:27.00 vs PIN:21.65 | Sinner BF:1.03 vs PIN:1.03 - Betfair odds higher than Pinnacle by 24.7% (good value)
  Player C (1.85) vs Player D (2.10) - Australian Open
```

### Files Added
- `src/odds_api.py` - The Odds API client
- `dist/TennisBettingSystem/odds_api.py` - Synced

### Files Modified
- `credentials.json` - Added `odds_api_key` field
- `dist/TennisBettingSystem/credentials.json` - Synced

---

## Betfair Minimum Liquidity Filter

### Problem
User reported Joao Silva showing at 3.00 odds on Betfair capture, but Bet365/Pinnacle showed 7.50. This massive discrepancy indicates thin/unreliable markets.

### Root Cause
Betfair is an exchange where anyone can post odds. In thin markets (low liquidity), prices can be wildly different from true market value because there's little money backing them.

### Fix Applied
Added £100 minimum liquidity filter - markets with less than £100 available to back on either player are now skipped.

```python
# In betfair_capture.py
MIN_LIQUIDITY_GBP = 100

# In capture_all_tennis_matches():
if p1_liquidity < MIN_LIQUIDITY_GBP or p2_liquidity < MIN_LIQUIDITY_GBP:
    print(f"  SKIPPED (low liquidity): {p1['name']} ({p1_odds:.2f}, £{p1_liquidity:.0f}) vs {p2['name']} ({p2_odds:.2f}, £{p2_liquidity:.0f})")
    continue
```

**Files Modified:**
- `src/betfair_capture.py` - Added MIN_LIQUIDITY_GBP constant and filter logic
- `dist/TennisBettingSystem/betfair_capture.py` - Synced

---

## Backtest Weight Profiles Fixed (Night Session)

### Overview
- **Fixed backtest to show differentiation between weight profiles**
- Fixed critical bug: `name_matcher.get_db_id()` was returning Betfair IDs instead of database player IDs
- Made weight profiles more extreme (50-70% dominant factors)
- Backtest now correctly shows different bets/results per profile

---

### Bug Fix: Backfill Player ID Lookup

**Problem Discovered:**
Backtest showed identical results (13 bets, 4W-9L, -4.2% ROI) for ALL weight profiles.

**Investigation:**
1. Confirmed factor_scores were being stored in new format
2. Found most factors had advantage = 0 (should be non-zero)
3. Traced to `find_player_id()` in backfill function
4. `name_matcher.get_db_id("Coco Gauff")` returned `-139591` (Betfair selection ID)
5. Correct database ID is `638` with 30 matches of data

**Root Cause:**
`name_matcher.get_db_id()` returns Betfair selection IDs (negative numbers), not database player IDs. The backfill was looking up the wrong players, resulting in no match data.

**Fix Applied:**
```python
# Before - used name_matcher which returns Betfair IDs
mapped_id = name_matcher.get_db_id(player_name)
if mapped_id:
    return mapped_id

# After - skip name_matcher, use database search only
# Note: Skip name_matcher.get_db_id() - it returns Betfair IDs, not DB IDs
results = db.search_players(player_name, limit=5)
for p in results:
    if p['name'].lower() == player_name.lower():
        return p['id']
```

**Files Modified:**
- `src/bet_tracker.py` - Fixed `find_player_id()` in `_backfill_factor_scores()`

---

### Feature: More Extreme Weight Profiles

Made weight profiles more extreme to create clearer differentiation in backtest:

| Profile | Main Factor | Old Weight | New Weight |
|---------|-------------|------------|------------|
| Form Heavy | form | 35% | **60%** |
| Ranking Heavy | ranking | 35% | **60%** |
| Surface Specialist | surface | 30% | **50%** |
| H2H Focus | h2h | 30% | **50%** |
| Recent Form Only | form+recency | 55% | **70%** |
| Academic Elo | ranking | 50% | **70%** |
| Anti-Market | opp_quality+recency | 45% | **60%** |
| Form Decay | form+recency | 60% | **70%** |
| Upset Hunter | opp_quality+momentum | 45% | **55%** |

**Files Modified:**
- `src/config.py` - Updated `MODEL_WEIGHT_PROFILES`

---

### Result: Backtest Now Shows Differentiation

After fixes, backtest correctly shows different results per profile:

| Profile | Bets | W-L | ROI |
|---------|------|-----|-----|
| H2H Focus | 12 | 4-8 | **+3.4%** |
| Anti-Market | 12 | 4-8 | **+3.4%** |
| Current (Balanced) | 13 | 4-9 | -4.2% |
| Form Heavy | 13 | 4-9 | -4.2% |
| Others | 13 | 4-9 | -4.2% |

H2H Focus and Anti-Market skipped one losing bet, turning a loss into profit.

---

### Technical: How Backtest Works

```
1. Get settled bets (filtered to >= 2026-01-25)
2. For each bet:
   - Load factor_scores JSON (contains advantage values -1 to +1)
   - For each weight profile:
     a. Calculate weighted_advantage = Σ(advantage × weight)
     b. Normalize by total weight
     c. Convert to probability: 0.5 + weighted_advantage/2
     d. Apply shrinkage: 0.5 + (prob - 0.5) × 0.5
     e. Calculate edge = our_prob - implied_prob
     f. If edge > 2%, include bet in this profile's results
3. Display stats per profile
```

**Key insight:** Different weight profiles give different probabilities. When a bet has borderline edge (~2-5%), some profiles will include it while others reject it. This creates the differentiation.

---

## v1.4.2 - Simplified Models (Late Evening Session)

### Overview
- Attempted multi-profile analysis for M8/M9/M10 - reverted (didn't differentiate)
- **Removed Models 8, 9, 10 completely** - now M1-M7 only
- **Rebuilt installer** v1.4.2
- Added end-of-session rule to CLAUDE.md

---

### Bug Fix: Betfair Runner Swap

**Problem Discovered:**
- User and friend had same bet (Simakin vs Kwon) but wildly different odds
- User: Simakin @ 4.40 (underdog)
- Friend: Simakin @ 1.78 (favorite)
- Odds history showed Simakin was always ~4.00

**Root Cause:**
Betfair API returns runners in arbitrary order. Code was taking `runners[0]` and `runners[1]` without sorting, meaning the same match captured at different times could have player/odds assignments swapped.

**Fix Applied:**
```python
# Before (line 392-393 in betfair_capture.py)
p1 = runners[0]
p2 = runners[1]

# After
sorted_runners = sorted(runners, key=lambda r: r.get('sort_priority', 0))
p1 = sorted_runners[0]
p2 = sorted_runners[1]
```

**Files Modified:**
- `src/betfair_capture.py`
- `dist/TennisBettingSystem/betfair_capture.py`

---

### New Feature: Gender Performance Stats

Added male vs female performance breakdown to Statistics tab.

**Logic:**
- Male = ATP, Challenger, Grand Slam
- Female = WTA, ITF

**Files Modified:**
- `src/bet_tracker.py`
  - Added `get_stats_by_gender()` method
  - Added Gender stats treeview in Statistics tab
  - Added refresh logic in `_refresh_stats_tab()`

---

### Staking Investigation

Investigated why user and friend had different unit stakes:
1. **Runner swap bug** - explained the Simakin odds discrepancy
2. **Kelly math is correct** - at different odds, Kelly recommends different stakes
3. **Config differences** - friend may have different `kelly_fraction` setting

User preference: May want to standardize on flat staking for consistency between users.

---

### Research: Factor Weight Models

Completed research on academic/industry approaches to factor weighting:

**Key Findings:**
- Rankings explain ~80% of variance but markets already price this
- Recommended blend: 50/50 overall Elo + surface Elo
- Time decay function: `e^(-0.01 × days)` for recent match weighting
- Momentum: Set 1 winner gets +2.3% serve advantage in set 2
- Calibration over accuracy leads to 69.86% higher betting returns

**Research saved for future implementation.**

---

## Current Analysis Architecture (Pre-Change Documentation)

**Why this documentation:** User noticed all bets always have M1 and asked if we should run analysis with EACH weight profile separately. Before implementing that change, documenting the current approach so we can revert if needed.

### Current Flow: Single Analysis → Multiple Model Tags

```
Match Captured → Single Analysis Run → Value Bet Identified → Model Tags Applied
```

#### Step 1: Factor Calculation (match_analyzer.py:1140-1182)

When a match is analyzed, ALL 10 factors are calculated in parallel:
- `form` - Recent win/loss record with quality weighting
- `surface` - Performance on specific surface
- `ranking` - Elo/ranking difference
- `h2h` - Head-to-head history
- `fatigue` - Recent match load
- `injury` - Injury status
- `opponent_quality` - Quality of recent opponents
- `recency` - How fresh the form data is
- `recent_loss` - Penalty for coming off a loss
- `momentum` - Tournament wins on same surface

Each factor produces an "advantage" score (-1 to +1, positive = P1 favored).

#### Step 2: Probability Calculation (match_analyzer.py:1280-1317)

Uses **DEFAULT_ANALYSIS_WEIGHTS** (the "Balanced" profile):
```python
DEFAULT_ANALYSIS_WEIGHTS = {
    "form": 0.20, "surface": 0.15, "ranking": 0.20, "h2h": 0.10,
    "fatigue": 0.05, "injury": 0.05, "opponent_quality": 0.10,
    "recency": 0.08, "recent_loss": 0.05, "momentum": 0.02
}
```

**Calculation:**
```python
# Sum weighted advantages
weighted_advantage = sum(
    factors[key] * adjusted_weights[key]
    for key in factors
)

# Logistic function (k=3 for steepness)
model_probability = 1 / (1 + math.exp(-k * weighted_advantage))
```

For large ranking gaps, blends with Elo probability (70/30 or 90/10 depending on form agreement).

#### Step 3: Value Bet Identification

A bet is identified as "value" if:
```python
edge = model_probability - implied_probability
value_bet = edge >= BETTING_SETTINGS["min_edge"]  # Currently 0.03 (3%)
```

**CRITICAL:** This is done ONCE with balanced weights. If not value under balanced weights, the match is NOT flagged as a bet.

#### Step 4: Model Tagging (config.py:119-219)

ONLY for matches that passed Step 3, `calculate_bet_model()` is called:

**Models 1-7 (Filter-based):**
- M1: All bets (always applied)
- M2: Tiered strategy (extremes + filtered middle)
- M3: Moderate edge (5-15%)
- M4: Favorites (prob >= 60%)
- M5: Underdogs (prob < 45%)
- M6: Large edge (>= 10%)
- M7: Grind (small edge 3-8% + short odds < 2.50)

**Models 8-10 (Weight Recalculation):**
```python
# ONLY runs if already identified as value bet
if factor_scores and 'factors' in factor_scores and implied_probability:
    for model_name, weights in weight_profiles.items():
        # Recalculate prob with new weights
        total_advantage = sum(
            factor_data['advantage'] * weights.get(factor_name, 0)
            for factor_name, factor_data in factors.items()
        )
        recalc_prob = 0.5 + (total_advantage * 0.5)
        recalc_edge = recalc_prob - implied_probability
        if recalc_edge >= 0.03:
            models.append(model_name)
```

### The Problem

**Current behavior:**
- A match MUST show value under Balanced weights to be captured as a bet
- M8/M9/M10 only check: "does this EXISTING value bet also show value with different weights?"
- Result: Every bet has M1, and M8/M9/M10 are just "additional tags"

**What's missing:**
- Bets that would ONLY show value under M8 weights (Zero Ranking) are never found
- Bets that would ONLY show value under M9 weights (Pure Momentum) are never found
- We're not discovering model-specific opportunities

### Proposed Change

Run analysis MULTIPLE times with different weight profiles:
1. Balanced weights → identifies M1 bets
2. M8 Zero Ranking weights → identifies M8-only bets
3. M9 Pure Momentum weights → identifies M9-only bets
4. M10 Surface Purist weights → identifies M10-only bets

A bet would show "M8 only" if it's value under Zero Ranking weights but NOT under Balanced weights.

**Impact:**
- More bets discovered (some won't have M1)
- Each model truly represents a different betting philosophy
- Can track which weight profile actually performs best

---

## REVERTED: Multi-Profile Analysis (Late Evening Session)

### What Happened
Implemented independent multi-profile analysis so M8/M9/M10 could find bets that balanced weights missed. However, testing showed:
- M8-only bets appeared (working as intended)
- M9/M10 either found no unique bets OR just duplicated M1 bets
- Even with extreme weights (70% momentum, 80% surface), the profiles didn't differentiate

### Why It Didn't Work
The factors themselves correlate - players with good surface stats tend to have good form, players with momentum tend to have good ranking. Making weights extreme doesn't create differentiation when the underlying data correlates.

### Decision
**Reverted all changes.** Back to original system:
- Single analysis with balanced weights
- M1 = all value bets
- M2-M7 = filter criteria on balanced probability
- M8-M10 weight profiles remain in config but aren't used for model tagging

### Files Reverted
- `src/config.py` - Removed helper function, INDEPENDENT_MODEL_PROFILES, reverted calculate_bet_model
- `src/bet_suggester.py` - Reverted analyze_upcoming_match to single-profile analysis
- `src/bet_tracker.py` - Reverted add_bet
- `dist/TennisBettingSystem/` - All above synced

### Removed M8/M9/M10 Completely
User requested full removal of Models 8, 9, 10. Changes:
- `config.py` - Removed M8/M9/M10 weight profiles from MODEL_WEIGHT_PROFILES
- `bet_tracker.py`:
  - Removed from all_models list (now M1-M7 only)
  - Removed Model 8/9/10 cards from Model Guide
  - Updated filter dropdown (now M1-M7 only)
  - Updated model legend label
  - Updated comments

**Current Models:** M1-M7 only

---

## Previous Session: Model 3 + Installer v1.4.0

(See earlier entries in this file)

---

## Files Changed This Session

| File | Changes |
|------|---------|
| `src/config.py` | Removed M8/M9/M10, made weight profiles more extreme (50-70%) |
| `src/bet_tracker.py` | Gender stats, removed M8-10, fixed backfill player ID lookup bug |
| `src/bet_suggester.py` | Reverted multi-profile analysis |
| `src/betfair_capture.py` | Fixed runner ordering bug, added £100 min liquidity filter, integrated Pinnacle comparison |
| `src/odds_api.py` | NEW - The Odds API integration for Pinnacle comparison, directional logic (BF < PIN = skip, BF > PIN = good) |
| `credentials.json` | Added odds_api_key field |
| `CLAUDE.md` | Added end-of-session rule, updated version to 1.4.2 |
| `installer.iss` | Version bump to 1.4.2 |
| `dist/TennisBettingSystem/*` | All above synced |

---

## Installer Build

**Version:** 1.4.3
**File:** `TennisBettingSystem_Setup_1.4.3.exe`
**Location:** `installer_output/`

**Changes in 1.4.3:**
- The Odds API integration for Pinnacle odds comparison
- Directional comparison logic (SKIP when Betfair < Pinnacle, KEEP when Betfair > Pinnacle)
- £100 minimum liquidity filter
- All previous fixes included

**Previous: 1.4.2:**
- Removed Models 8-10 completely
- Now has Models 1-7 only
- All previous 1.4.x fixes included

---

## API Usage (The Odds API)

- **Free tier:** 500 requests/month
- **Used today:** ~32 requests (testing)
- **Remaining:** ~468 requests
- **Estimated monthly usage:** 4 captures/day × 30 days = 120 requests (well under limit)

---

## Installer v1.4.4 Built (Latest)

### Version 1.4.4 Changes
- Removed all capture filters (captures everything)
- Added "Matched" column (total market activity from Betfair)
- £25 minimum matched filter for analysis display
- **Fixed auto mode bug** - matches now re-analyzed when odds update

### Auto Mode Bug Fix
**Problem:** Auto mode wasn't working the same as manual flow.
- Manual: Clear → Capture → Analyse All → works
- Auto: Capture → Analyse → missed already-analyzed matches

**Root cause:** When capturing updated odds for existing matches, the `analyzed` flag wasn't reset to 0. So `analyze_all_upcoming()` (which only gets `analyzed=0` matches) skipped them.

**Fix:** Reset `analyzed=0` when updating existing matches in `add_upcoming_match()`:
```python
# In database.py add_upcoming_match()
SET ... analyzed = 0
WHERE id = ?
```

### Installer Location
`installer_output\TennisBettingSystem_Setup_1.4.4.exe`

### Files Modified
- `src/database.py` - Reset analyzed flag on match update
- `installer.iss` - Version bump to 1.4.4

---

## Capture Limits Removed + Matched Liquidity Column

### Changes Made

#### 1. Removed All Capture Filters
User requested capturing ALL matches without filtering. Removed:
- Minimum liquidity filter (was £100)
- Pinnacle comparison skip (still shows warnings but doesn't skip)

Now captures everything - filtering happens at analysis time instead.

#### 2. Added "Matched" Column to Bet Suggester
Shows total amount already matched on Betfair market (the "Matched: GBP X" value).
- Better indicator of market reliability than individual player liquidity
- Higher matched = more market activity = more reliable odds

#### 3. £25 Minimum Matched Filter for Analysis
Matches with less than £25 total matched are filtered out from analysis display.
- Still captured to database
- Just not shown in bet suggester
- Configurable via `MIN_MATCHED_LIQUIDITY = 25` in bet_suggester.py

### Database Changes
Added columns to `upcoming_matches` table:
- `player1_liquidity` - Amount available at best back for P1
- `player2_liquidity` - Amount available at best back for P2
- `total_matched` - Total amount already matched on market

### Files Modified
- `src/betfair_capture.py` - Removed skip filters, pass liquidity/matched to save
- `src/database.py` - Added liquidity columns, migrations
- `src/bet_suggester.py` - Added "Matched" column, £25 minimum filter
- `dist/TennisBettingSystem/*` - All synced

### UI Changes
- New "Matched" column in bet suggester showing total matched (£)
- Tooltip explains: <£100 thin, £100-500 moderate, £500-2000 good, >£2000 high activity

---

## Betfair Capture Debugging

### Issue Reported
User reports missing matches with over £100 liquidity (e.g., "Piet Fellin v Ma Rosenkranz").

### Investigation
The liquidity filter at line 442-445 requires BOTH players to have over £100 available. If one player has £200 but the other has £50, the match is skipped.

### Enhanced Debugging Added
Added comprehensive logging to diagnose skipped matches:

1. **No odds skip** - Now logs when odds are missing
2. **Low liquidity skip** - Shows both players' liquidity values
3. **Capture summary** - Shows breakdown of all skipped matches:
   - In-play
   - No odds
   - Low liquidity
   - Pinnacle comparison
   - Other (doubles, filters)

### Console Output Example
```
--- CAPTURE SUMMARY ---
Total markets found: 156
Captured: 89
Skipped - In-play: 12
Skipped - No odds: 3
Skipped - Low liquidity (<£100): 41
Skipped - Pinnacle comparison: 5
Skipped - Other (doubles, filter, etc.): 6
-----------------------
```

### Files Modified
- `src/betfair_capture.py` - Added skip counters and summary
- `dist/TennisBettingSystem/betfair_capture.py` - Synced

### Next Steps
Run capture and check console output to see exactly why "Piet Fellin v Ma Rosenkranz" is being skipped.

---

## Documentation Rewrite (Latest)

### Overview
Comprehensive rewrite of all documentation files to reflect v1.4.3 changes.

### Files Updated

| File | Changes |
|------|---------|
| `README.md` | Updated to v1.4.3, added Pinnacle comparison, betting models M1-M7 |
| `ARCHITECTURE.md` | Added odds_api.py, Pinnacle comparison flow, updated data diagrams |
| `CHANGELOG.md` | Added entries for v1.4.0-1.4.3 |
| `CONFIGURATION.md` | Added Betfair capture settings, The Odds API settings, betting models M1-M7 |
| `DATABASE_SCHEMA.md` | Added model/factor_scores columns in bets, pinnacle_odds in upcoming_matches |
| `TROUBLESHOOTING.md` | Added The Odds API issues, Pinnacle comparison, minimum liquidity |
| `BUILD_NOTES.md` | Updated to v1.4.3, added odds_api.py to file list (now 30 files) |
| `DATA_DICTIONARY.md` | Added betting models M1-M7, Pinnacle comparison values, new bet fields |

### Documentation Now Current With
- The Odds API integration (Pinnacle comparison)
- £100 minimum liquidity filter
- Directional comparison logic
- Betting models M1-M7
- model/factor_scores columns in bets table
- pinnacle_odds columns in upcoming_matches table

---

## Pending Bet Date Sync (Latest)

### Issue
User reported Joao Dinis Silva bet showing wrong time - scheduled for tomorrow morning but match was happening now.

### Root Cause
When a bet is added from value bets, it captures the match_date at that moment. If Betfair later updates the match time (rescheduled, different session), the bet keeps the old date.

### Fix Applied
Added automatic date sync when refreshing the bet tracker:

1. **New database function** `sync_pending_bet_dates()`:
   - Gets all pending bets (unsettled)
   - For each bet, looks up matching upcoming_match by player names
   - If found and date differs, updates the bet's match_date
   - Handles player order reversal (P1 vs P2 in either position)

2. **Bet tracker refresh** now calls sync before refreshing tables

### Console Output
When dates are synced, you'll see:
```
Updated 1 pending bet date(s) from upcoming matches
```

### Files Modified
- `src/database.py` - Added `sync_pending_bet_dates()` function
- `src/bet_tracker.py` - Call sync in `_refresh_data()`
- `dist/TennisBettingSystem/database.py` - Synced
- `dist/TennisBettingSystem/bet_tracker.py` - Synced

---

## To Resume

1. **Date sync feature added** - Pending bet dates now sync from upcoming_matches on refresh
2. **Auto mode now works correctly** - same as manual Clear → Capture → Analyse → Add All
3. **Confidence filter removed** - was filtering out profitable underdog bets
4. **Current filters**: Min EV 5%, Max EV 100%, Min Units 0.5, Min Matched £25
5. **"Matched" column** shows total market activity (same as Betfair "Matched: GBP X")
6. **Profitable ranges**: Underdogs <40% (+57% ROI) and Favorites >70% (+359% ROI)
7. **Current models are M1-M7** - multi-profile analysis was scrapped
8. **Betfair capture now has:** Pinnacle comparison (directional), captures all liquidity levels
9. Run app: `python src/main.py`

---

## Duplicate Bet Fix

### Issue
User reported seeing duplicate bets in the bet tracker.

### Investigation
Found 2 duplicate pairs in database:
- Nao Hibino vs Himeno Sakatsume - Nao Hibino (IDs 257, 282)
- Tatjana Maria vs Leolia Jeanjean - Tatjana Maria (IDs 274, 279)

### Root Cause
The `BetTracker.add_bet()` method didn't check for duplicates before inserting. While the UI dialog had a check, the underlying method didn't.

### Fix Applied
1. Added duplicate check to `BetTracker.add_bet()` - now returns -1 if duplicate exists
2. Deleted the duplicate bets (IDs 282, 279)

### Files Modified
- `src/bet_tracker.py` - Added duplicate check in add_bet()
- `dist/TennisBettingSystem/bet_tracker.py` - Synced

---

## Session End

### Future Plans / TODO
- Monitor the model performance and see how it does
- No immediate features or bug fixes planned

### Current State
- **Version:** 1.4.4
- **Installer:** `installer_output\TennisBettingSystem_Setup_1.4.4.exe`
- **Active bets:** ~25 pending bets across various tournaments
- **Key matches to watch:** Fellin vs Rosenkranz (in progress, looking good), Rocha vs Erhard, Pavlova vs Rouvroy

---

## Darts Manager WinUI 3 POC Created

### Overview
Created a WinUI 3 proof of concept for Darts Manager, matching the current home screen design with a professional dark green + gold theme.

### Files Created
- `darts-manager/winui-poc/DartsManagerWinUI.csproj` - Project file
- `darts-manager/winui-poc/App.xaml` + `App.xaml.cs` - App entry
- `darts-manager/winui-poc/MainWindow.xaml` + `MainWindow.xaml.cs` - Home screen layout
- `darts-manager/winui-poc/Styles/AppStyles.xaml` - Color palette and styles
- `darts-manager/winui-poc/app.manifest` - Windows manifest
- `darts-manager/winui-poc/README.md` - Documentation

### Design Features
- **Dark green backgrounds** (#020502, #0a120a, #111a11)
- **Gold accents** (#d4af37) for primary actions and highlights
- **Hero section** with player name, world rank, tour card badge
- **Status indicators row**: Tour Card, Form, Fitness, Morale, Season, Last Match
- **Performance stats** 2x2 grid: Win Rate, Earnings, 3-Dart Average, Form
- **Upcoming events** list with countdown badges (2 DAYS, 8 DAYS, etc.)
- **Top rivalries** with relationship badges (RIVAL, NEMESIS, FRIENDLY)
- **Quick actions** grid: Tournament, Rankings, Inbox, Data Hub, Achievements, Practice, Advance Week
- **Recent matches** table with WIN/LOSS badges
- **Sidebar navigation** with quick stats panel

### How to Run
1. Open Visual Studio 2022/2026
2. File → Open → `darts-manager/winui-poc/DartsManagerWinUI.csproj`
3. Press F5

---

## Repository
- **Local:** `C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting`
- **Run:** `python src/main.py` (from src folder)
