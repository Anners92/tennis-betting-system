# Session Log - 2026-01-26

## Session Status: ACTIVE

---

## Bug Fix 1: Results Dialog Showing Wrong Opponent Name

### Problem
The "Results Checked" dialog showed wrong opponent name:
```
Maximus Jones: Win (vs Maximus Jones, 6-3 7-64)
```
Should have shown "vs Marat Sharipov" (the opponent).

### Root Cause
Code was displaying `d['winner']` instead of the opponent. When our selection won, the winner IS our selection.

### Fix Applied
- Added opponent calculation: `opponent = loser_name if selection_won else winner_name`
- Changed details dict to store `opponent` instead of `winner`
- Updated display format to use `d['opponent']`

### Files Modified
- `src/bet_tracker.py` - Lines 732-740, line 3357
- `dist/TennisBettingSystem/bet_tracker.py` - Synced

---

## Bug Fix 2: Model Tags Not Saving to Database

### Problem
The `model` column in bets table was NULL for all bets. Model tags displayed in UI but never saved.

### Root Cause
`bet_suggester.py` `_add_all_to_tracker()` called `db.add_bet()` directly, bypassing `bet_tracker.add_bet()` which calculates model tags.

### Fix Applied
Added model calculation in `_add_all_to_tracker()`:
```python
db_bet['model'] = calculate_bet_model(
    db_bet.get('our_probability', 0.5),
    db_bet.get('implied_probability', 0.5),
    db_bet.get('tournament', ''),
    db_bet.get('odds'),
    factor_scores
)
```

### Files Modified
- `src/bet_suggester.py` - Added model calculation before db.add_bet()
- `dist/TennisBettingSystem/bet_suggester.py` - Synced

### Backfill
Ran script to populate model tags for all 130 existing bets.

---

## Bug Fix 3: Bet Tracker Only Showed Last 100 Bets

### Problem
Bet tracker only showed bets from Jan 25th onwards - older bets missing.

### Root Cause
`database.py` `get_all_bets()` had default `limit=100`, but 170 bets in database.

### Fix Applied
Changed default limit from 100 to None (no limit):
```python
def get_all_bets(self, limit: int = None) -> List[Dict]:
```

### Files Modified
- `src/database.py` - Removed default limit
- `dist/TennisBettingSystem/database.py` - Synced

---

## Model Performance Analysis

### Today's Results (26/01/2026)
- **Settled:** 4W-12L (all bets) | 3W-6L (no 0.5u bets)
- **P/L:** -2.78u (all) | -0.72u (no 0.5u)
- **0.5u bets went 1W-8L** - dragging down results

### All-Time Performance (No 0.5u Filter)

| Model | Description | Record | P/L | ROI |
|-------|-------------|--------|-----|-----|
| M1 | All Bets | 28W-61L | -13.21u | -10.5% |
| **M2** | Tiered (extremes) | 15W-29L | +2.65u | **+4.7%** |
| M3 | Moderate Edge | 19W-37L | -6.49u | -8.8% |
| **M4** | Favorites (>=60%) | 7W-7L | +7.17u | **+21.7%** |
| M5 | Underdogs (<45%) | 10W-26L | -2.15u | -5.8% |
| M6 | Large Edge | 15W-33L | -2.66u | -3.4% |
| **M7** | Grind (<2.50 odds) | 7W-8L | +0.98u | **+5.6%** |

### Key Insights
- **Profitable models:** M2, M4, M7
- **Best performer:** M4 (Favorites >=60%) at +21.7% ROI
- **0.5u bets cost 3.06u all-time** (1W-8L)
- Removing 0.5u bets improves overall ROI from -12.5% to -10.5%

---

## Bug Fix 4: Match Times Not Syncing

### Problem
Match times in bet tracker were often wrong because they were captured from Betfair at bet placement time, but actual match times change.

### Fix Applied
1. **Enhanced `sync_pending_bet_dates()`** in database.py:
   - Now uses fuzzy matching (LIKE) instead of exact player names
   - Checks `betfair_matches` table first (most accurate for live/upcoming)
   - Falls back to `upcoming_matches` table
   - Extracts player names from match_description if needed

2. **Auto-update on result check**: When settling a bet, the match_date is updated from the actual match result date

### When Times Sync
- Automatically when bet tracker refreshes (calls `sync_pending_bet_dates()`)
- When checking/settling results (updates from matches table)

### Files Modified
- `src/database.py` - Enhanced sync_pending_bet_dates() with fuzzy matching
- `src/bet_tracker.py` - Updates match_date when settling from results
- `dist/TennisBettingSystem/*` - Synced

---

## Bug Fix 5: Duplicate Bets When Match Time Changes

### Problem
Duplicate bets could be added if the match time changed (e.g., 10:00 → 14:00). Same tournament, same match, same selection should not be allowed twice.

### Root Cause
Duplicate check used match_description + selection + date prefix, but didn't include tournament. Time changes could slip through.

### Fix Applied
Updated `check_duplicate_bet()` to use **tournament + match_description + selection** as the primary key:
- Added `tournament` parameter to `database.py` `check_duplicate_bet()`
- Updated all callers: `bet_suggester.py`, `bet_tracker.py`, `main.py`
- Batch duplicate check now uses `(tournament, match_description, selection)` tuple

### Files Modified
- `src/database.py` - Added tournament to check_duplicate_bet()
- `src/bet_suggester.py` - Pass tournament to duplicate check
- `src/bet_tracker.py` - Pass tournament to duplicate check (2 locations)
- `src/main.py` - Pass tournament to duplicate check
- `dist/TennisBettingSystem/*` - All synced

---

## Feature 6: Flashscore Results Checker

### Purpose
Alternative method to check match results when GitHub data source is stale or missing recent matches.

### Implementation
Created `flashscore_results.py` - Selenium-based web scraper that:
1. Searches Flashscore for a player
2. Navigates to their results page
3. Finds match against opponent
4. Extracts winner/loser and score

### Key Technical Details
- Uses Selenium WebDriver with headless Chrome
- Search uses longest name part (usually surname) for best results
- Verifies search results have ALL significant name parts (>3 chars)
- Win/loss detected via `wcl-win`/`wcl-lose` badge classes
- Caches player page URLs for efficiency
- Score format: sets won (e.g., "2-0", "0-3")

### DOM Selectors Used
- Search: `#searchWindow` -> `input.searchInput__input`
- Results: `.searchResult` with "TENNIS" text
- Match rows: `.event__match`
- Participants: `.event__participant`
- Win badge: `[class*="wcl-win"]`
- Loss badge: `[class*="wcl-lose"]`
- Score: `.event__score--home`, `.event__score--away`

### Added to Bet Tracker
- New "Check (Flashscore)" button (orange) in filter row
- Calls `check_flashscore_results(db, max_bets=10)`
- Shows results dialog same as regular "Check Results"

### Files Modified
- `src/flashscore_results.py` - NEW FILE (Selenium scraper)
- `src/bet_tracker.py` - Added Flashscore button and handler
- `dist/TennisBettingSystem/*` - Synced

### Testing
```python
checker.lookup_match_result('Jannik Sinner', 'Ben Shelton')
# Returns: {'winner': 'Jannik Sinner', 'loser': 'Ben Shelton', 'score': '2-0'}
```

---

## Files Changed This Session

| File | Changes |
|------|---------|
| `src/bet_tracker.py` | Fixed opponent name in results dialog, added tournament to duplicate check, added Flashscore button |
| `src/bet_suggester.py` | Added model tag calculation when adding bets, added tournament to duplicate check |
| `src/database.py` | Removed 100 bet limit, added tournament to check_duplicate_bet() |
| `src/main.py` | Added tournament to duplicate check |
| `src/flashscore_results.py` | NEW: Selenium-based Flashscore results scraper |
| `dist/TennisBettingSystem/*` | All above synced |

---

## Database Stats
- **Total bets:** 170
- **Date range:** 2026-01-21 to 2026-01-27
- **All bets now have model tags**

---

## To Resume

1. All three bug fixes deployed and working
2. Consider filtering out 0.5u bets or raising minimum stake
3. M4 (Favorites >=60%) is the clear winner - consider focusing on these
4. Run app: `python src/main.py`

---

## Feature 7: Removed Flashscore Integration

### Reason
Flashscore checking was too slow for practical use.

### Changes
- Removed "Check (Flashscore)" button from bet_tracker.py
- Removed `_check_results_flashscore` method

---

## Feature 8: Removed Match Date Update on Settle

### Reason
The match date was being updated when settling bets, but it was removing the time component anyway, making it pointless.

### Changes
- Removed match_date update code from `auto_settle_from_results()` in bet_tracker.py

---

## Bug Fix 6: Installer Missing Config Module

### Problem
Friend got error: "No module named 'config'"

### Fix
Added src directory to `pathex` in `TennisBettingSystem.spec`:
```python
pathex=['C:\\Users\\marca\\OneDrive\\Documents\\claude-playground\\tennis betting\\src']
```

---

## Feature 9: Auto-Backfill Model Tags on App Launch

### Purpose
Ensure any bets missing model tags are automatically populated when the app starts.

### Implementation
1. **database.py** - Added `backfill_model_tags()` method:
   - Finds all bets where `model` is NULL
   - Calculates model tags using `calculate_bet_model()` from config
   - Updates those bets with the calculated model tags
   - Returns count of bets updated

2. **main.py** - Modified `_auto_startup_tasks()`:
   - Calls `db.backfill_model_tags()` on startup
   - Shows status update if any bets were backfilled

### Files Modified
- `src/database.py` - Added `backfill_model_tags()` method
- `src/main.py` - Call backfill in `_auto_startup_tasks()`

---

## Installer Build v1.4.4

### Location
`C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\installer_output\TennisBettingSystem_Setup_1.4.4.exe`

### Changes Included
- Fixed "No module named 'config'" error
- Added auto-backfill for model tags on launch
- Removed Flashscore integration

---

---

## Session 2 Updates (Continued)

### Feature 10: Auto-Update Database on Install

**Problem:** Friend's database wasn't being replaced because the installer only copied seed database if none existed.

**Fix:** Modified `_ensure_db_exists()` in database.py to:
1. Check if seed database is newer than user's existing database
2. If newer, back up old database to `.db.backup`
3. Copy the new seed database with all model tags

### Installer v1.4.4 Final Contents
- Database with 183 bets (all model-tagged)
- credentials.json with Betfair credentials
- name_mappings.json for player matching
- Auto-update logic to replace older databases

### Files Modified
- `src/database.py` - Added betfair_matches table creation, improved backfill logic, auto-update seed database logic

---

## Repository
- **Local:** `C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting`
- **Run:** `python src/main.py`
- **Installer:** `installer_output\TennisBettingSystem_Setup_1.4.4.exe`

---

## Future Plans / TODO

- No specific features planned currently
- Focus is on gathering more betting data to analyze model performance
- Need 1000+ bets before drawing conclusions on model weighting
- M4 (Favorites >=60%) and M7 (Grind) showing promise so far

---

## Session Status: ACTIVE

---

## Session 3: Comprehensive Analysis & Model 8 Creation

### Full Database Analysis (193 bets, 131 settled)

**Overall Performance:**
- Record: 38W-93L (29% win rate)
- P/L: -29.97 units
- ROI: -19.2%

### Critical Finding: Odds Range Performance

| Odds Range | Record | P/L | ROI |
|------------|--------|-----|-----|
| **< 2.50** | 22W-23L | **+3.22u** | **+4.9%** |
| **>= 2.50** | 16W-70L | -33.19u | -36.3% |

**The model is profitable on favorites but hemorrhaging money on underdogs.**

### Model-by-Model (Odds < 2.50 Only)

| Model | Record | P/L | ROI |
|-------|--------|-----|-----|
| Model 1 | 22W-23L | +3.22u | +4.9% |
| Model 2 | 7W-10L | +4.11u | +14.9% |
| Model 3 | 8W-14L | -7.97u | -21.2% |
| **Model 4** | 8W-7L | **+7.52u** | **+22.4%** |
| Model 5 | 0W-1L | -0.50u | -100.0% |
| **Model 6** | 7W-6L | **+8.89u** | **+26.9%** |
| Model 7 | 13W-14L | -3.27u | -11.9% |

### Most Profitable Segments

| Filter | Record | P/L | ROI |
|--------|--------|-----|-----|
| Our Prob >= 50% + Odds < 2.50 | 16W-19L | +0.83u | +1.4% |
| **Our Prob >= 55% + Odds < 2.50** | **13W-9L** | **+11.65u** | **+28.1%** |
| Our Prob >= 60% + Odds < 2.50 | 8W-7L | +7.52u | +22.4% |
| Our Prob >= 65% + Odds < 2.50 | 5W-2L | +10.26u | +50.0% |

### Edge Accuracy Problem

The edge calculation is broken - higher calculated edges perform WORSE:

| Edge Range | Record | P/L | ROI |
|------------|--------|-----|-----|
| 0-5% | 4W-3L | +0.09u | +2.6% |
| 5-10% | 6W-4L | +0.33u | +4.4% |
| 10-15% | 4W-11L | -5.39u | -34.8% |
| 20-30% | 3W-16L | -15.39u | -54.0% |
| 30%+ | 15W-52L | -9.98u | -12.1% |

### Model 8 Created (Profitable Baseline)

Created Model 8 to track the profitable segment while continuing to gather data on all other models:

**Model 8 Criteria:**
- Our probability >= 55% AND odds < 2.50
- Historical: 13W-9L, +11.65u, +28.1% ROI

**Purpose:** Treat as the "baseline profitable model" while all other models continue to track for data collection.

### Files Modified
- `src/config.py` - Added Model 8 to `calculate_bet_model()`
- `dist/TennisBettingSystem/config.py` - Synced

### Key Insight
The model severely overestimates win probability for underdogs. When odds are >= 2.50 (40% implied probability), our model is way off. Continue tracking all bets to build sample size, but Model 8 represents the "safe" segment.

---

## Deep Dive Analysis: Zheng and Ambrogi Bets

### Wushuang Zheng (3u Loss)
- **Problem**: Player NOT in database
- **Model did**: Estimated 61.8% from odds alone, calculated 16.3% "edge"
- **Kelly said**: 3u max stake
- **Reality**: We knew NOTHING about this player
- **Result**: Lost 3u on phantom edge

### Luciano Ambrogi (2.5u Loss)
- **Problem**: Model underweighted H2H
- **Context**: Estevez had beaten Ambrogi 6-3 6-1 two months prior
- **Model gave**: Ambrogi 57.1% (12.5% edge) based on 18-spot ranking advantage
- **Reality**: All other factors were even, H2H strongly favored Estevez
- **Result**: Lost 2.5u

### Analysis Findings
| Segment | Record | ROI |
|---------|--------|-----|
| Bets WITH player data | 36W-80L | -16.5% |
| Bets WITHOUT player data | 2W-15L | **-71.5%** |

Unknown players are bleeding -71.5% ROI!

---

## Safeguard Implemented: Unknown Player Detection

### What It Does
When clicking "Add All to Tracker":
1. Scans all bets for players NOT in database (ranking estimated from odds)
2. Shows popup listing unknown players with stake amounts
3. Warns about -71.5% historical ROI on unknown players
4. Options: Add only known players, or Cancel to add players first

### Files Modified
- `src/bet_suggester.py` - Added unknown player detection in `_add_all_to_tracker()`
- `dist/TennisBettingSystem/bet_suggester.py` - Synced

---

## Documentation Created

### WEIGHTING_CHANGES.md
New document to track:
- Current model weights
- Analysis of potential changes
- Decision log (change or no change)
- Rules for future adjustments (50+ bet minimum sample)

---

## Session 3 Summary

### What Was Done
1. Comprehensive analysis of 193 bets (133 settled)
2. Created Model 8 (profitable baseline: prob >= 55% AND odds < 2.50)
3. Deep dive into Zheng (unknown player) and Ambrogi (H2H) losses
4. Implemented unknown player safeguard with popup warning
5. Created WEIGHTING_CHANGES.md for tracking model adjustments

### Key Findings
- Unknown players: 2W-15L, -71.5% ROI (now blocked)
- Model 8 segment: 13W-11L, +13.1% ROI
- H2H weight: No change needed yet (only 1 case)

### Files Changed
- `src/config.py` - Model 8
- `src/bet_tracker.py` - Model 8 UI
- `src/bet_suggester.py` - Unknown player safeguard
- `WEIGHTING_CHANGES.md` - New file

---

## Future Plans / TODO

- Continue gathering data to identify patterns and issues
- Monitor Model 8 performance as baseline
- Review WEIGHTING_CHANGES.md when 50+ bet samples are reached in segments

---

## Session Status: CLOSED

---

## Session 4: Unknown Player Resolver Feature

### Feature: Unknown Player Resolver Dialog

**Problem Solved:**
When clicking "Add All to Tracker", unknown players (not in database) were blocking bets with only two options: skip all unknown or cancel. Users needed a way to resolve these players by matching them to existing database entries or adding them as new players.

**New Workflow:**
1. Unknown players detected → New popup with **3 options**:
   - **Review & Match** - Opens resolver dialog (NEW)
   - **Add Known Only** - Previous behavior (skip unknowns)
   - **Cancel**

2. **Resolver Dialog** (one player at a time):
   - Shows: Betfair name, match info, stake, odds
   - **Auto-fuzzy search** - Pre-populated with player name, shows potential DB matches
   - **Manual search** - Type to search for alternative spellings
   - Results show: Name, Ranking, Match Count, Country
   - **"Use Selected Player"** - Maps Betfair name to DB player (saves permanently)
   - **"Add as New Player"** - Creates new player in database with estimated ranking
   - **"Skip This Bet"** - Don't add this bet
   - **"Cancel All"** - Abort the entire operation

3. **After Resolution:**
   - Name mappings saved to `name_mappings.json`
   - `upcoming_matches` table updated with correct player IDs
   - Matches re-analyzed with proper player data
   - Bets added with accurate probabilities

### Files Modified

| File | Changes |
|------|---------|
| `src/database.py` | Added `add_player()` function to create new players |
| `src/database.py` | Added `update_upcoming_match_player_id()` to fix player IDs after resolving |
| `src/bet_suggester.py` | Added `UnknownPlayerResolverDialog` class (full resolver UI) |
| `src/bet_suggester.py` | Added `_show_unknown_players_dialog()` helper for 3-option popup |
| `src/bet_suggester.py` | Modified `_add_all_to_tracker()` to use new resolver flow |
| `dist/TennisBettingSystem/*` | All above synced |

### Technical Details

**New Database Functions:**
```python
# Add a new player to the database
db.add_player(name="Kyle Seelig", ranking=200, country="USA", hand="R")
# Returns: new player ID

# Update upcoming match with resolved player ID
db.update_upcoming_match_player_id(match_id=123, player_position='player1', new_player_id=456)
# Also resets analyzed=0 so match will be re-analyzed
```

**Name Mapping Storage:**
- Uses existing `name_matcher.add_mapping()` function
- Saves to `data/name_mappings.json`
- Format: `"Betfair Name": player_id` (integer)
- Mappings persist across sessions

**Re-Analysis Flow:**
- After resolving unknowns, matches are re-analyzed with correct player IDs
- Uses `suggester.analyze_upcoming_match()` to get proper probabilities
- Bet data updated before adding to tracker

### UI Components

**UnknownPlayerResolverDialog:**
- Modal dialog, centered on parent window
- Header shows progress: "Resolve Unknown Player (1 of 4)"
- Player info card with name, match, bet details
- Search entry with 300ms debounce
- Treeview showing: Name, Ranking, Matches, Country
- Results sorted by similarity score
- Checkbox: "Save name mapping permanently" (default: checked)

**Custom 3-Option Popup:**
- Warning icon with count of unknown players
- Scrollable list of unknown players with stakes/odds
- ROI warning: "Historical ROI on unknown players: -71.5%"
- Three buttons: Review & Match (accent), Add Known Only (success), Cancel

---

## Session 5: Model 9 & CLV Tracking Implementation

### Feature 11: Model 9 (Experimental Weights)

**Purpose:**
A/B test different weight schemes by creating a secondary probability calculation using "reduced overlap" weights that remove redundant factors.

**Experimental Weights:**
| Factor | Current | Experimental | Rationale |
|--------|---------|--------------|-----------|
| form | 0.20 | 0.25 | Absorbs opponent_quality |
| surface | 0.15 | 0.20 | Likely edge source |
| ranking | 0.20 | 0.20 | Solid anchor |
| h2h | 0.10 | 0.05 | Often noise, market prices it |
| fatigue | 0.05 | 0.15 | Market underweights |
| injury | 0.05 | 0.05 | Keep |
| opponent_quality | 0.10 | 0.00 | Redundant with form |
| recency | 0.08 | 0.00 | Already in form's decay |
| recent_loss | 0.05 | 0.08 | Psychological edge |
| momentum | 0.02 | 0.02 | Keep small |

**Model 9 Qualification:**
- Recalculates probability using experimental weights
- Uses same calibration (0.5 shrinkage) and market blend (70/30)
- Qualifies if BOTH original AND experimental models show >= 2% EV
- This tests if consensus between two weight schemes identifies higher-quality bets

**Files Modified:**
- `src/config.py` - Added Model 9 logic to `calculate_bet_model()` function (lines 189-247)
- `dist/TennisBettingSystem/config.py` - Synced

---

### Feature 12: CLV (Closing Line Value) Tracking

**Purpose:**
Track whether we're beating the closing line - a key indicator of betting edge independent of short-term results.

**Implementation:**

1. **Database Columns Added:**
   - `odds_at_close REAL` - The closing odds for the bet
   - `clv REAL` - Calculated CLV percentage

2. **New Database Methods:**

```python
# Update closing odds and calculate CLV
db.update_closing_odds(bet_id=123, closing_odds=1.85)
# Returns CLV percentage

# Get CLV statistics
db.get_clv_stats()
# Returns: {
#   'total_with_clv': 50,
#   'avg_clv': 2.3,
#   'positive_clv_pct': 65.0,
#   'avg_clv_wins': 3.1,
#   'avg_clv_losses': 1.2
# }
```

3. **CLV Formula:**
```
CLV% = ((1/closing_odds - 1/placement_odds) / (1/placement_odds)) * 100
```
- Positive CLV = Beat the closing line (got better odds than market settled at)
- Negative CLV = Closing line was better

**Why CLV Matters:**
- Long-term profitability correlates with consistently beating the closing line
- Even during losing streaks, positive CLV indicates edge
- If avg_clv > 0 but ROI < 0, likely just variance
- If avg_clv < 0 and ROI < 0, model needs work

**Files Modified:**
- `src/database.py` - Added CLV columns to bets_migrations, added `update_closing_odds()` and `get_clv_stats()` methods
- `dist/TennisBettingSystem/database.py` - Synced

---

### What User Did NOT Want (Noted)

**Model 8 as Default Filter:**
User explicitly declined making Model 8 the default filter, saying: "I don't want default model filter yet, I have a gut feeling Model 8 was just picking up wrong information but I can't prove it."

---

### Files Changed This Session

| File | Changes |
|------|---------|
| `src/config.py` | Added Model 9 with experimental weights logic |
| `src/database.py` | Added CLV columns and tracking methods |
| `dist/TennisBettingSystem/*` | Both synced |

---

### Next Steps

1. **Populate CLV data:** Need to capture closing odds when settling bets (can be done manually or via Betfair API before match starts)
2. **Add UI for CLV stats:** Show avg CLV in bet tracker dashboard
3. **Track Model 9 performance:** Compare M9 results vs M1 to validate experimental weights

---

## Session 6: Multi-Profile Analysis System

### Feature 13: Analyze All Profiles

**Purpose:**
Analyze every upcoming match with EVERY weight profile, creating separate bet entries for each profile that finds value. This allows A/B testing of different weighting strategies with real bets.

**Implementation:**

1. **New "Analyze All Profiles" Button** (Purple) in Bet Suggester
   - Loops through all 12+ weight profiles
   - Analyzes each match with each profile's weights
   - Creates separate value bet entry for each profile that finds value
   - Shows profile name in new "Weighting" column

2. **Database Changes:**
   - Added `weighting TEXT` column to bets table
   - Updated `add_bet()` to include weighting
   - Updated `check_duplicate_bet()` to allow same match with different weightings

3. **UI Changes:**
   - Value Bets table: Added "Weighting" column
   - Bet Tracker bets list: Added "Weighting" column
   - Both show shortened profile name (e.g., "Form Heavy", "Ranking Heavy")

4. **Duplicate Logic:**
   - Same match + selection can now exist multiple times with different weight profiles
   - Each profile tracked independently for performance analysis

**Files Modified:**
- `src/database.py` - Added weighting column, updated add_bet and check_duplicate_bet
- `src/bet_suggester.py` - Added _analyze_all_profiles method, weighting column in UI
- `src/bet_tracker.py` - Added weighting column to bets display
- `dist/TennisBettingSystem/*` - All synced

---

### Feature 14: Weight Profile Comparison in Model Guide

**Purpose:**
Show all weight profiles in the Model Guide tab for easy reference.

**Implementation:**
Replaced the old 3-column static table with a full Treeview showing ALL profiles with all 10 factor weights displayed as percentages.

**Files Modified:**
- `src/bet_tracker.py` - Updated _build_model_guide_tab with full profile table

---

### Bug Fix: Model 9 Not in Stats

**Problem:** Opening Bet Tracker failed with "KeyError: Model 9"

**Fix:** Added Model 9 to:
- `all_models` list in `get_stats_by_model()`
- Model filter dropdown values

---

### How to Use Multi-Profile Analysis

1. **Bet Suggester** → Click **"Analyze All Profiles"** (purple button)
2. Wait for analysis to complete (processes all profiles)
3. Results show in table with "Weighting" column indicating which profile found each bet
4. **"Add All to Tracker"** - Each bet is saved with its weight profile
5. **Bet Tracker** → View bets with "Weighting" column
6. **Statistics** → Analyze which profiles perform best over time

---

## Session 7: Major Model Refactor - Simplified to 4 Models

### Changes Made

**1. Removed Models 1, 2, 5, 6, 9**

Only 4 models remain:
- **Model 3**: Moderate edge bets (5-15% edge) - "Sharp" zone
- **Model 4**: Favorites only (our probability >= 60%)
- **Model 7**: Small edge (3-8%) + short odds (< 2.50) - "Grind"
- **Model 8**: Profitable baseline - Our prob >= 55% AND odds < 2.50

**2. Experimental Weights Now Default**

Updated `DEFAULT_ANALYSIS_WEIGHTS` to the experimental weights (removing redundant factors):

| Factor | Old Weight | New Weight | Rationale |
|--------|-----------|------------|-----------|
| form | 0.20 | **0.25** | Absorbs opponent_quality signal |
| surface | 0.15 | **0.20** | Likely edge source vs market |
| ranking | 0.20 | 0.20 | Solid anchor |
| h2h | 0.10 | **0.05** | Often noise, market prices it well |
| fatigue | 0.05 | **0.15** | Market underweights this |
| injury | 0.05 | 0.05 | Keep |
| opponent_quality | 0.10 | **0.00** | REMOVED - redundant with form |
| recency | 0.08 | **0.00** | REMOVED - already in form's decay |
| recent_loss | 0.05 | **0.08** | Psychological edge |
| momentum | 0.02 | 0.02 | Keep small |

**3. Simplified Weight Profiles**

Replaced 12+ profiles with 6 clean profiles:
- **Default**: The new experimental weights
- **Form Focus**: 35% form (increased from 25%)
- **Surface Focus**: 30% surface (increased from 20%)
- **Ranking Focus**: 30% ranking (increased from 20%)
- **Fatigue Focus**: 25% fatigue (increased from 15%)
- **Psychology Focus**: 15% recent_loss, 8% momentum

### Files Modified

| File | Changes |
|------|---------|
| `src/config.py` | Updated `calculate_bet_model()` to only include Models 3, 4, 7, 8. Updated `DEFAULT_ANALYSIS_WEIGHTS`. Replaced `MODEL_WEIGHT_PROFILES` with 6 simplified profiles. |
| `src/bet_tracker.py` | Updated `all_models` list. Updated model filter dropdown. Fixed `get_stats_by_model()` to only calculate stats for Models 3, 4, 7, 8. |
| `dist/TennisBettingSystem/*` | All above synced |

### Rationale

Based on Session 5 analysis:
- H2H Focus showed +95% ROI but only had 7 settled bets - insufficient sample
- The experimental weights remove redundant factors (opponent_quality absorbed by form, recency already in form's decay)
- Increased fatigue weight because market tends to underweight schedule/rest advantage
- Reduced H2H weight because market already prices H2H records efficiently

---

## Session 8 Continued: Weighting Column Removal

### Change: Removed Weighting Column from Bet Tracker

**Context:**
After removing weight profiles in Session 7, the weighting column in bet tracker was no longer needed since we only have one default weight profile now.

**What Was Removed:**
1. Column definition from tree columns tuple
2. Column heading
3. Column width setting
4. `weighting_short` variable and logic (lines 2002-2007)
5. `weighting_short` from the values tuple

**Files Modified:**
- `src/bet_tracker.py` - Removed all weighting column references
- `dist/TennisBettingSystem/bet_tracker.py` - Synced

---

## Session Status: ACTIVE
