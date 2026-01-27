# Session Log - 2026-01-27

## Session Status: COMPLETE

---

## Live Scores Feature Added

### What Was Done
Added live scoring functionality to the Bet Tracker for in-progress matches.

### Changes Made (`bet_tracker.py`)
1. **New "Live Score" column** in the Pending Bets table (after Match column)
2. **Auto-refresh every 30 seconds** - fetches scores from Betfair API
3. **Manual refresh button** - purple "Refresh Scores" button
4. **Status indicator** - shows connection status, live count, last update time
5. **Player matching** - matches pending bets to Betfair in-play markets by player names

### How It Works
- Uses existing Betfair credentials (from `credentials.json`)
- Fetches all in-play tennis markets via `listMarketCatalogue` with `inPlayOnly: true`
- Matches bets by parsing `match_description` and comparing player names
- Shows score in format: "In-Play", "1-0 (3-2)", or "-" if not live

### Technical Details
- Runs in background thread to avoid UI blocking
- Stops refresh timer when window closes
- Handles Betfair session management (lazy login)
- Fuzzy player name matching (handles name variations)

### Files Changed
- `src/bet_tracker.py` - Added ~300 lines for live score functionality + Discord integration
- `src/discord_notifier.py` - NEW: Discord webhook notifications
- `src/live_scores.py` - Created (Flashscore/Sofascore scrapers - blocked by sites, not used)
- `credentials.json` - Added `discord_webhook` field
- Synced to `dist/TennisBettingSystem/`

---

## Discord Notifications Added

### Setup Required
1. In Discord: Right-click channel > Edit Channel > Integrations > Webhooks
2. Create webhook and copy URL
3. Add to `credentials.json`: `"discord_webhook": "https://discord.com/api/webhooks/..."`

### What Gets Sent
When a bet transitions to "In-Play", Discord receives an embed with:
- Match description
- Selection (who you bet on)
- Odds
- Stake (units)
- Model
- Tournament

### How It Works
- Tracks which bets were previously live
- Only sends alert on FIRST detection (no spam on every refresh)
- Runs automatically with the 30-second live score refresh

### What Shows in the UI
- **"Live" column** in both All Bets and Pending Bets tables
- Shows **"In-Play"** for matches currently live on Betfair
- Shows **"-"** for matches not yet started
- Rows with live matches get blue highlight
- Status indicator: "Live scores: X live (HH:MM:SS)"

### Actual Scores Limitation
Getting real set/game scores (e.g., "1-0 (4-3)") would require:
- Paid API subscription (~$10-30/month for API-Tennis or similar)
- Flashscore/Sofascore block scraping attempts

Current implementation shows "In-Play" which is still useful for knowing which bets are active.

### Version
**1.4.7** (bump for live scores feature)

---

## Analysis Session: 32 Settled Bets Review

### What Was Done
Ran comprehensive analysis of all settled bets to check model performance.

### Current Database Stats
- **Total bets:** 79
- **Settled:** 32 | **Pending:** 47

### Overall Performance
| Metric | Value |
|--------|-------|
| Record | 16W-15L (51.6% win rate) |
| P/L | **+11.20u** |
| ROI | **+34.4%** |

### By Model
| Model | Record | P/L | ROI |
|-------|--------|-----|-----|
| Model 3 | 8W-8L | +9.69u | +58.7% |
| Model 7 | 5W-4L | +2.16u | +28.9% |
| Model 3+7 | 1W-2L | -1.59u | -39.7% |
| Model 7+8 | 1W-0L | +0.93u | +93.1% |
| None | 1W-2L | -0.00u | 0.0% |

### By Odds
| Range | Record | P/L | ROI |
|-------|--------|-----|-----|
| 1.50-2.00 | 1W-0L | +0.93u | +93.1% |
| 2.00-2.50 | 7W-6L | +2.58u | +19.8% |
| 2.50-3.00 | 2W-4L | -0.83u | -12.8% |
| 3.00-4.00 | 6W-5L | +8.52u | +71.0% |

### By Stake
| Stake | Record | P/L | ROI |
|-------|--------|-----|-----|
| 0.5u | 1W-3L | -0.94u | -47.1% |
| 1.0u | 14W-8L | +16.14u | +70.2% |
| 1.5u | 1W-4L | -4.00u | -53.3% |

### By Tournament Level
| Level | Record | P/L | ROI |
|-------|--------|-----|-----|
| Grand Slam | 1W-1L | +0.78u | +39.2% |
| Challenger | 11W-11L | +6.57u | +30.6% |
| ITF/Futures | 1W-4L | -1.50u | -25.0% |
| Other (WTA) | 3W-0L | +5.34u | +178.0% |

### Key Observations (NOT actionable yet - need 100+ bets)
- Model 3 profitable despite 50% win rate (winning at higher odds)
- 3.00-4.00 odds currently best segment (+71% ROI)
- 1.0u stakes outperforming 0.5u and 1.5u significantly
- 2.50-3.00 odds only losing segment
- Challengers are bulk of volume and profitable

### Decision
**Continue gathering data without changes.** Only 32 settled bets - way too early to draw conclusions or adjust weights. Need 100+ bets per model before making any changes.

---

## Future Plans / TODO

- Continue generating bets and gathering data
- Re-analyze at 100 settled bets
- Monitor for bets qualifying as "None" model (shouldn't be tracked)
- No model changes until sufficient sample size

---

---

## Cloud Monitoring Solution Added

### The Problem
User wanted Discord alerts to work 24/7 without keeping their computer running.

### The Solution
Created a standalone cloud monitoring system using:
1. **Supabase** (free cloud PostgreSQL database) - stores pending bets
2. **Railway** (free cloud hosting) - runs monitor script 24/7

### How It Works
1. **Local app** adds bets to local DB AND syncs to Supabase
2. **Cloud monitor** (Railway) checks Supabase every 30 seconds
3. When match goes live on Betfair → Discord alert
4. When match finishes → Discord alert with Win/Loss result

### Files Created

#### `cloud_monitor/` directory (for Railway deployment):
- `monitor.py` - Standalone monitoring script
- `requirements.txt` - Python dependencies
- `Procfile` - Railway worker process
- `railway.json` - Railway config
- `SETUP.md` - Step-by-step setup guide

#### Updated files:
- `src/cloud_sync.py` - Added `market_id` column to SQL
- `src/bet_tracker.py` - Auto-syncs new bets to Supabase
- `dist/TennisBettingSystem/cloud_sync.py` - Created
- `dist/TennisBettingSystem/bet_tracker.py` - Updated

### Setup Steps (in SETUP.md)
1. Create Supabase account, run SQL to create table
2. Add `supabase_url` and `supabase_key` to credentials.json
3. Run `python src/cloud_sync.py --sync` to sync existing bets
4. Deploy `cloud_monitor/` to Railway
5. Set environment variables in Railway

### Environment Variables Needed (Railway)
- `BETFAIR_APP_KEY`
- `BETFAIR_USERNAME`
- `BETFAIR_PASSWORD`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `DISCORD_WEBHOOK`

### Costs
- **Supabase**: Free (500MB database)
- **Railway**: Free (500 hours/month - more than enough for 24/7)

---

---

## Cloud Hosting Issues & Local Monitor Solution

### Railway Deployment Issue
- Deployed cloud_monitor to Railway successfully
- **Problem:** Betfair returned 403 Forbidden - cloud server IPs are blocked
- Tried Render.com - requires paid plan for background workers
- PythonAnywhere - free tier blocks external API calls

### Solution: Local PC Monitor
Created `local_monitor.py` that runs on the user's PC with Windows auto-start.

### Files Created
- `local_monitor.py` - Main monitoring script with Discord bot
- `start_monitor.vbs` - Silent VBScript launcher
- Shortcut in Windows Startup folder for auto-start

### Key Features
1. **Betfair API Integration** - Checks every 30 seconds for live matches
2. **Discord Bot Commands** - Responds to !inplay, !pending, !stats
3. **Win/Loss Detection** - Sends alerts when matches finish
4. **Startup Recovery** - Checks previously live bets on restart

---

## Discord Bot Setup

### How It Was Done
1. Created Discord Application at discord.com/developers/applications
2. Created Bot, copied token to `credentials.json`
3. Enabled "MESSAGE CONTENT INTENT" in Bot settings
4. Added bot to server via OAuth2 URL Generator (bot + application.commands scopes)

### Bot Commands
- `!inplay` - Shows all current in-play bets with odds and stake
- `!pending` - Shows all pending bets (with stake totals by model)
- `!stats` - Shows overall betting statistics (W/L, P/L, ROI)

### credentials.json Structure
```json
{
    "betfair_app_key": "...",
    "betfair_username": "...",
    "betfair_password": "...",
    "discord_webhook": "https://discord.com/api/webhooks/...",
    "supabase_url": "https://tlhyciryjszbwheerbhk.supabase.co",
    "supabase_key": "eyJ...",
    "discord_bot_token": "MTQ2NTcw..."
}
```

---

## Bug Fixes Applied

### 1. Betfair API Returning XML Instead of JSON
**Problem:** API calls returned empty/invalid responses
**Fix:** Added `'Accept': 'application/json'` header in BetfairClient
```python
headers = {
    'X-Application': self.app_key,
    'X-Authentication': self.session_token,
    'Content-Type': 'application/json',
    'Accept': 'application/json'  # Critical fix
}
```

### 2. Finished Matches Not Sending Result Alerts
**Problem:** Market status checked at wrong time, missing closures
**Fix:** Improved tracking logic to keep retrying until CLOSED status

### 3. Duplicate LIVE Alerts on Monitor Restart
**Problem:** Bets already live would re-alert on startup
**Fix:** Added startup check that adds them to `previously_live` without alerting

### 4. Wrong Alert Colors
**Problem:** Live alerts showing yellow/orange instead of blue
**Fix:** Updated color to 0x3498db (blue) in local_monitor.py and discord_notifier.py
- **LIVE:** Blue (0x3498db)
- **WIN:** Green (0x2ecc71)
- **LOSS:** Red (0xe74c3c)

### 5. Duplicate Alerts from Two Sources
**Problem:** Both "Tennis Betting System" (main app) and "Tennis Betting Monitor" (local_monitor.py) sending alerts
**Fix:** Commented out `notify_bet_live` call in `src/bet_tracker.py`:
```python
# Live alerts now handled by local_monitor.py
# if newly_live and DISCORD_AVAILABLE:
#     for bet in newly_live:
#         try:
#             notify_bet_live(bet)
#         except Exception as e:
#             print(f"Discord notification error: {e}")
```

---

## Current State
- **local_monitor.py** running successfully
- Discord bot connected as TBS#1553
- Correctly detecting live and finished matches
- Sending alerts with correct colors (Blue=Live, Green=Win, Red=Loss)
- No duplicate alerts

---

## Webhook Removed - Bot Now Sends Alerts Directly

### The Problem
Discord webhook was causing duplicate alerts and interfering with the channel.

### The Solution
Removed webhook dependency. Monitor now sends alerts directly via the Discord bot to channel ID `1462470788602007787`.

### Changes to `local_monitor.py`
- Removed `DISCORD_WEBHOOK` usage
- Added `DISCORD_CHANNEL_ID = 1462470788602007787`
- Alerts now queued and sent via `bot.get_channel().send(embed=...)`
- New functions: `queue_live_alert()`, `queue_result_alert()`, `send_queued_alerts()`

---

## Bot Command Tables Improved

### !inplay and !pending Commands
- Now display as formatted ASCII tables
- Columns: Match, Selection, Odds, Stake, Tournament
- Match names shortened to last names (e.g., "Zhang v Virtanen")
- Sent as plain message (not embed) for wider display

### New Command Added
- `!alert <win/loss> <match>` - Manually send a result alert for a bet

---

## Missed Alert Recovery Added

### The Problem
If monitor restarts or misses a result, no alert is sent.

### The Solution
Monitor now checks for "orphaned" live bets every 30 seconds:
- Looks for bets marked `is_live=True` in Supabase with no result
- If market is CLOSED on Betfair, determines winner and sends alert
- Updates both Supabase and local SQLite database

---

## Local Database Auto-Update

### What Was Added
When monitor detects a finished bet:
1. Sends Discord alert
2. Updates Supabase
3. **NEW:** Updates local SQLite database at `C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db`

### Function Added to `local_monitor.py`
```python
def update_local_db(match_description, selection, result, profit_loss):
    # Updates bets table with result, profit_loss, settled_at
```

---

## App Auto-Refresh for Results

### What Was Added (`bet_tracker.py`)
The bet tracker now auto-refreshes every 10 seconds to detect new results from the monitor.

### How It Works
- Tracks set of settled bet IDs
- Every 10 seconds, checks if any new bets have been settled
- If changes detected, refreshes the entire display
- Stops when window closes

### New Methods
- `_start_result_refresh()` - Starts 10-second check loop
- `_stop_result_refresh()` - Stops on window close
- `_check_for_new_results()` - Compares current vs last known settled IDs

---

## Installer Rebuilt

New installer created with all changes:
- **File:** `installer_output/TennisBettingSystem_Setup_1.4.6.exe`
- Includes auto-refresh feature for results

---

## Current System Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│  Tennis Betting     │     │   local_monitor.py  │
│  System (App)       │     │   (Background)      │
│                     │     │                     │
│  - Add/view bets    │     │  - Checks Betfair   │
│  - Auto-refresh     │◄────│  - Sends Discord    │
│    every 10s        │     │    alerts via bot   │
│                     │     │  - Updates DBs      │
└────────┬────────────┘     └──────────┬──────────┘
         │                             │
         │                             │
         ▼                             ▼
┌─────────────────────┐     ┌─────────────────────┐
│  Local SQLite DB    │     │     Supabase        │
│  (tennis_betting.db)│     │  (Cloud Postgres)   │
└─────────────────────┘     └─────────────────────┘
```

---

---

## Duplicate Result Alert Fix

### The Problem
Podrez bet sent two result alerts - race condition between main finish check and missed alert recovery.

### The Solution
Added `alerted_results` set to track which bet IDs have already had result alerts sent.

```python
alerted_results = set()  # Track bet IDs that have already had result alerts sent

# Before sending any result alert:
if bet_id not in alerted_results:
    send_result_alert(bet, bet_result, profit)
    alerted_results.add(bet_id)
```

---

## Testing Confirmed Working

### Virtanen Bet (Win)
- Monitor detected match finished
- Discord alert sent via bot ✓
- Supabase updated (result: Win, profit_loss: 0.7125) ✓
- Local SQLite updated ✓
- App auto-refresh detected change ✓

---

## Edit Sync to Supabase Fix

### The Problem
When editing a bet in the app (e.g., changing the date), changes saved to local SQLite but didn't sync to Supabase.

### The Solution
Added `sync_bet_to_cloud(bet_data)` call in the `save_changes()` function of the edit dialog in `bet_tracker.py`.

---

## MAJOR BUG FIX: Bet Edits Not Saving

### The Problem
User edits to bets (date, tournament, any field) appeared to save but reverted immediately. Users couldn't edit any bet details.

### Root Cause
The `sync_pending_bet_dates()` function was being called inside `_refresh_data()`, which runs immediately after every save. This function checks Betfair/upcoming matches for date updates and **overwrites** any date that differs from the source data - including user edits.

Flow:
1. User edits bet date and clicks Save
2. `update_bet()` saves new date to database ✓
3. `_refresh_data()` called
4. `sync_pending_bet_dates()` finds bet date differs from Betfair data
5. **Overwrites user's edit with Betfair date** ✗

### The Fix
Added `skip_date_sync` parameter to `_refresh_data()`:

```python
def _refresh_data(self, skip_date_sync: bool = False):
    """Refresh all data displays.

    Args:
        skip_date_sync: If True, skip syncing bet dates from upcoming matches.
                       Use this when refreshing after a user edit to preserve
                       manually entered dates.
    """
    if not skip_date_sync:
        updated = db.sync_pending_bet_dates()
        # ...
```

When saving edits, now calls: `self._refresh_data(skip_date_sync=True)`

### Files Changed
- `src/bet_tracker.py` - Added skip_date_sync parameter
- `dist/TennisBettingSystem/bet_tracker.py` - Synced

### All Refresh Calls Fixed
Updated 11 locations to use `skip_date_sync=True`:
- Adding bets
- Editing bets
- Settling (Win/Loss/Void)
- Deleting single bet
- Bulk deleting bets
- Toggling in-progress status
- Auto-checking results
- Auto-refresh from monitor

Only initial app load syncs dates (useful for picking up Betfair schedule changes).

### Tested & Confirmed Working
- Edit bet → Save → Date persists ✓
- Mark Void → Other bets' dates unchanged ✓

---

## Typo Fix in bet_tracker.py

### The Problem
`self.root.force_focus()` was causing an error - should be `focus_force()`.

### The Fix
Changed `self.root.force_focus()` → `self.root.focus_force()`

---

## Final Installer Rebuild

Built new installer with all session fixes:
- **File:** `installer_output\TennisBettingSystem_Setup_1.4.6.exe`
- Build completed successfully

---

---

## CRITICAL BUG FIX: Surface Detection Error

### The Problem
Investigation of a 2.5u losing bet on Juan Carlos Prado Angel revealed incorrect surface data.
- **Bet:** Juan Carlos Prado Angel @ 2.24, Oeiras Challenger
- **Surface in system:** Grass
- **Actual surface:** Indoor Hard (Oeiras in January is always indoor hard)
- **Impact:** Surface factor has 20% weight in analysis - wrong data skews probability

### Investigation Findings
6 tournaments were incorrectly marked as "Grass":
- Oeiras Challenger 2026 (Portugal, January) - Should be **Hard**
- Concepcion Challenger 2026 (Chile) - Should be **Clay**
- Manama Challenger 2026 (Bahrain) - Should be **Hard**
- Phan Thiet Challenger 2026 (Vietnam) - Should be **Hard**
- Quimper Challenger 2026 (France) - Should be **Hard**
- San Diego CA Challenger 2026 (USA) - Should be **Hard**

### Root Cause
**Bug in `betfair_capture.py:523`:** The keyword `'halle'` (a German grass tournament) was matching `'ch**ALLE**nger'` because it was a substring match. All Challenger tournaments were getting detected as Grass.

Additionally, the bare keyword `'grass'` was in the list, which could match unexpected tournament names.

### The Fix

#### 1. Created Centralized Surface Detection (`config.py`)
New function `get_tournament_surface()` is now the single source of truth:
- Comprehensive CLAY_TOURNAMENTS list (60+ tournaments)
- Comprehensive GRASS_TOURNAMENTS list (specific names, no false matches)
- **Seasonal check:** Grass tournaments ONLY happen in June-July
- **Word boundary matching:** Short keywords like 'rome' won't match 'Jerome'
- Date-aware: If date is not June/July, surface cannot be Grass

#### 2. Updated All Surface Detection Code
Files updated to use centralized function:
- `betfair_capture.py`
- `betfair_tennis.py`
- `tennis_explorer_scraper.py`
- `te_import_dialog.py`

#### 3. Fixed Database
**51 matches corrected** in `upcoming_matches` table:
- Oeiras: Grass -> Hard (7 matches)
- Manama: Grass -> Hard (11 matches)
- Phan Thiet: Grass -> Hard (8 matches)
- Quimper: Grass -> Hard (12 matches)
- San Diego CA: Grass -> Hard (13 matches)

Concepcion correctly changed to Clay (7 matches - already done earlier).

### Test Results
All surface detection tests pass:
```
[PASS] Oeiras Challenger 2026 (2026-01-28) -> Hard
[PASS] Manama Challenger 2026 (2026-01-27) -> Hard
[PASS] Concepcion Challenger 2026 (2026-01-27) -> Clay
[PASS] ATP Halle 2026 (2026-06-15) -> Grass
[PASS] Wimbledon 2026 (2026-07-01) -> Grass
[PASS] Eastbourne 2026 (2026-06-20) -> Grass
[PASS] Eastbourne 2026 (2026-01-20) -> Hard (NOT grass season!)
```

### Files Changed
- `src/config.py` - Added centralized `get_tournament_surface()` function
- `src/betfair_capture.py` - Uses centralized function
- `src/betfair_tennis.py` - Uses centralized function
- `src/tennis_explorer_scraper.py` - Uses centralized function
- `src/te_import_dialog.py` - Uses centralized function
- All synced to `dist/TennisBettingSystem/`

### Impact on Juan Carlos Prado Angel Bet
The bet was analyzed with incorrect surface data (Grass instead of Hard). This likely:
- Used wrong surface stats for both players
- Inflated the calculated edge
- Led to a larger stake (2.5u) than warranted

**This is a data quality issue, not a model issue.** Future bets will have correct surface detection.

---

## CRITICAL BUG FIX: Historical Match Surface Data Corrupted

### The Problem
After fixing the surface detection code, discovered that 5,401 historical matches in the `matches` table also had wrong surfaces from when they were imported with the buggy code.

### The Fix
Ran database update using the corrected `get_tournament_surface()` function:
- **1,118 matches** corrected from Grass → Clay
- **4,283 matches** corrected from Grass → Hard

This ensures all historical data used for probability calculations is now correct.

---

## BUG FIX: Player Name Matching

### The Problem
When recalculating affected bets, player name matching was returning wrong players:
- Query: "Frederico Ferreira Silva"
- Found: "Daniel Dutra da Silva" (WRONG)
- Expected: "Ferreira Silva Frederico"

### Root Cause
Database stores names as "LastName FirstName" but Betfair uses "FirstName LastName". The old matching code had a dangerous "last name only" strategy that matched "% Silva" and returned the wrong player.

### The Fix
Rewrote `get_player_by_name()` in `database.py` with improved matching:
1. **Strategy 0:** Check `name_mappings.json` first
2. **Strategy 1:** Exact match (case-insensitive)
3. **Strategy 2:** Reversed name order ("A B C" → "B C A" and "C B A")
4. **Strategy 3:** All name parts must be present (in any order)
5. **Strategy 4:** First and last name in any order (for 2-part names)
6. **Strategy 5:** Fuzzy match with 0.85 threshold (last resort)

**Removed:** The dangerous last-name-only matching that caused false matches.

### Files Changed
- `src/database.py` - Rewrote `get_player_by_name()` function

---

## BUG FIX: Stale Player Surface Stats Table

### The Problem
After all fixes, many bets still showed 50% probability (no edge). Investigation revealed:
- `player_surface_stats` table had 4,165 rows of **stale data**
- This data was populated once with buggy surface info (showing "Grass" matches that didn't exist)
- `matches_played` column was NULL, causing `career_matches = 0`
- Code was using stale table data instead of calculating fresh from `matches` table

Example: August Holmgren showed 17 Hard matches in `matches` table but 0 career matches in surface stats because the lookup used the stale table.

### The Fix
Cleared the stale `player_surface_stats` table (4,165 rows deleted). The system now falls back to `_calculate_surface_stats()` which calculates directly from the corrected `matches` table.

### Verification
After fix, August Holmgren now correctly shows:
- career_matches: 17
- has_data: True
- combined_win_rate: 0.412

---

## Affected Bets Analysis (Final)

### Summary
- **76 bets** were placed with wrong surface data (marked as Grass but actually Hard/Clay)
- **75 successfully reanalyzed** (1 had player lookup issue)

### Results with Correct Data
| Category | Count | Settled | P/L |
|----------|-------|---------|-----|
| Would STILL take | 31 | 5W-6L | +1.88u |
| Would SKIP (insufficient data) | 44 | 8W-12L | +2.00u |

### Why 44 Would Be Skipped
These bets involve lower-tier Challenger/ITF players who genuinely don't have enough match history in our database. With `has_data=False`, the model returns 50% probability and the bet doesn't qualify for any model.

### Impact Summary
- **Actual P/L:** +3.88u from 40.5u staked (9.6% ROI)
- **Corrected P/L:** +1.88u from 21.0u staked (8.9% ROI)
- **Skipped bets contribution:** +2.00u (lucky variance - can't rely on bets with no data)

### Key Insight
The "should skip" bets performed well due to variance, but they were essentially coin flips with no analytical edge. Going forward, the system will correctly identify these low-data situations.

---

## Files Changed (Session Summary)
- `src/config.py` - Centralized surface detection
- `src/betfair_capture.py` - Uses centralized surface
- `src/betfair_tennis.py` - Uses centralized surface
- `src/tennis_explorer_scraper.py` - Uses centralized surface
- `src/te_import_dialog.py` - Uses centralized surface
- `src/database.py` - Improved player name matching
- All synced to `dist/TennisBettingSystem/`

## Database Fixes
- 51 upcoming matches: Surface corrected
- 5,401 historical matches: Surface corrected (1,118→Clay, 4,283→Hard)
- 4,165 stale surface stats: Deleted (will recalculate fresh)

---

---

## Player Profile Feature Added

### What Was Done
Added comprehensive player profiles to the Database Management UI.

### Player Profile Now Shows

**Basic Info (compact row)**
- ID, Name, Ranking, ELO, Total Matches

**Surface Performance**
- Hard/Clay/Grass: X matches | XX.X% win rate | Data: ✓/✗
- Color-coded: Green (60%+), Normal (45-60%), Red (<45%)

**Current Status**
- Days Since Match: "Today" / "Yesterday" / "X days ago"
- Fatigue: Status with score (Fresh/Good/Moderate/Heavy)
- Matches (7d): count
- Matches (30d): count

**Notable Results**
- Best Win: Highest-ranked opponent beaten with date
- Worst Loss: Lowest-ranked opponent lost to with date

**Recent Matches (Last 10)**
- Color-coded: Green for wins, Red for losses
- Shows date, surface, opponent, opponent rank, tournament
- Form summary: XW-YL (Z%)

**Aliases** (compact section at bottom)
- Small list with count

### Example: Tristan Boyer
```
Ranking: #181 | ELO: 1375
Fatigue: Fresh (94) | Days: 12 | 7d: 0 | 30d: 4
Best Win: #88 James Duckworth (2025-08-25)
Worst Loss: #1318 Duje Markovina (2025-12-07)
Hard: 15 matches | 26.7% win rate
```

### Files Changed
- `src/database_ui.py` - Complete redesign of player details panel
- Synced to `dist/TennisBettingSystem/`

---

## Match to Watch: Boyer vs Samuel

### The Question
Does raw surface win rate mislead when players compete at different levels?

### The Match
- **Tristan Boyer (#181)** vs **Toby Samuel (#251)**
- San Diego CA Challenger, Hard court
- Odds: Boyer 2.44 / Samuel 1.65

### Model Says
- Boyer: 40.4%
- Samuel: 59.6%
- Surface factor heavily favors Samuel (-0.614)

### Opponent Quality Analysis Says
- Samuel's 88% hard court win rate is against #500-#1400 players (Futures)
- Samuel loses to anyone decent: #189, #252, #366, #371, #570
- Boyer (#181) is better than everyone Samuel has lost to
- **Conclusion:** Boyer is probably the better player despite lower surface win rate

### What to Watch For
- If Boyer wins: Surface stats may need opponent quality weighting
- If Samuel wins: Raw surface stats may be valid signal

### Result
*TBD - Update after match*

---

## Repository
- **Local:** `C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting`
- **Run App:** `python src\main.py`
- **Monitor:** `python local_monitor.py` (or use start_monitor.vbs)
- **Installer:** `installer_output\TennisBettingSystem_Setup_1.4.6.exe`
- **Version:** 2.0 (GitHub)
- **GitHub:** https://github.com/Anners92/tennis-betting-system

---

## Tournament Surface Fixes (Wikipedia Comparison)

### What Was Done
Comprehensive review of all tournament surfaces against Wikipedia's List of Tennis Tournaments.

### Changes Made

#### Full Database Refresh
- Changed refresh from 6 months to 12 months (`github_data_loader.py`)
- Now have **63,919 matches** from 1,033 tournaments

#### Samuel's Clay Matches Fixed
- 4 Futures matches (Jul 30 - Aug 2, 2025) updated from Hard → Clay
- Opponents: Casanova, De Krom, Taileu, Nesterov

#### Grass Courts Fixed (June/July events only)
- Wimbledon, Queen's Club, Halle, Eastbourne
- Hertogenbosch, Bad Homburg, Birmingham
- Ilkley, Nottingham, Mallorca (June only), Newport RI
- Stuttgart (June only)

#### South American Clay Fixed
- Antofagasta, Montevideo, Sevilla, Valencia WTA
- Tucuman, Rosario, Villa Maria, Kitzbühel
- Oeiras (spring), Bogotá, Costa do Sauipe
- Curitiba, Florianopolis, Santos, Porto Alegre
- Temuco, Quito

#### European Clay Fixed
- Portuguese: Braga, Maia, Porto, Lisbon
- French: Aix-en-Provence
- Italian: Genoa, Cordenons
- Finnish: Tampere
- Tunisian: Tunis
- Bosnian: Banja Luka
- Romanian: Cluj-Napoca
- Mexican: San Luis Potosi

#### US Clay Fixed
- Tallahassee

### Wikipedia Comparison Fixes (Final Batch)
| Tournament | Matches | Old Surface | New Surface |
|------------|---------|-------------|-------------|
| Stuttgart (June) | 38 | Hard | Grass |
| Tallahassee | 46 | Hard | Clay |
| Tampere | 46 | Hard | Clay |
| Tunis | 46 | Hard | Clay |
| Genoa | 44 | Hard | Clay |
| Cordenons | 101 | Hard | Clay |
| Banja Luka | 18 | Hard | Clay |
| San Luis Potosi | 40 | Hard | Clay |
| Cluj-Napoca | 72 | Hard | Clay |

### Final Surface Breakdown
| Surface | Matches |
|---------|---------|
| Hard | 55,231 |
| Clay | 7,514 |
| Grass | 1,174 |

### Database Copied to Installer
- Corrected database copied to `dist\TennisBettingSystem\data\tennis_betting.db`
- Size: 16.2 MB
- Ready for installer rebuild

---

## BUG FIX: Surface has_data Always False

### The Problem
Surface stats showed `has_data: false` for all players despite having 50+ matches in the database. This caused the surface factor to be set to 0 (neutral) in all match analyses.

### Root Cause
In `match_analyzer.py` line 241, `has_data` only checked `career_matches` (from the `player_surface_stats` table which was cleared earlier). It ignored `recent_matches_count` which had valid data.

```python
# Before (broken)
"has_data": career_matches >= 5

# After (fixed)
"has_data": (career_matches >= 5) or (recent_matches_count >= 5)
```

### Impact
- Boyer vs Samuel analysis changed from 49.5%-50.5% to **46.4%-53.6%**
- Surface factor now correctly shows -0.205 (favoring Samuel's 66.1% vs Boyer's 45.6%)

### Files Changed
- `src/match_analyzer.py` - Fixed `has_data` check
- `src/database_ui.py` - Fixed player profile surface display
- Synced to `dist/TennisBettingSystem/`

---

## Database Cleanup & Surface Fixes (Continued Session)

### Match History Cleanup
- Deleted matches older than 12 months (cutoff: 2025-01-27)
- Only 65 matches removed
- Database now strictly 12 months: 2025-01-27 to 2026-01-27

### Additional Surface Fixes

| Tournament | Change | Matches |
|------------|--------|---------|
| Stuttgart (April WTA) | Hard → Clay | 39 |
| Contrexeville WTA | Hard → Clay | 37 |
| Birmingham challenger (June) | Hard → Grass | 49 |
| Newport challenger (July) | Hard → Grass | 41 |
| Winston Salem (earlier fix) | Clay → Hard | 107 |

### Final Database Stats
- **Total matches:** 63,854
- **Date range:** 2025-01-27 to 2026-01-27 (exactly 12 months)
- **Surfaces:** Hard: 55,127 | Clay: 7,464 | Grass: 1,263

### Files Updated
- Database copied to `dist\TennisBettingSystem\data\tennis_betting.db` (16.2 MB)

---

## NEW FEATURE: Tournament Profile Tab

### What Was Added
Added a "Tournaments" tab to the Database Management UI, allowing users to view tournament profiles.

### Tournament Profile Displays:
1. **Basic Info**: Tournament name, Surface (color-coded), Category (Grand Slam/ATP/WTA/Challenger/ITF), Typical month played
2. **Statistics**: Total matches, Date range, Unique players
3. **Top Performers**: Players with most wins at this tournament
4. **Recent Matches**: Last 15 matches with winner, loser, score (color-coded by surface)

### UI Structure:
- New tabbed interface with "Players" and "Tournaments" tabs
- Tournament search with "Show All" option (top 200 by match count)
- Two-panel layout: search list on left, profile on right

### Files Modified:
- `src/database_ui.py` - Added tournament tab and related methods
- Synced to `dist/TennisBettingSystem/`

### New Methods Added:
- `_build_tournaments_tab()` - Builds tournament tab UI
- `_search_tournaments()` - Searches tournaments by name
- `_on_tournament_select()` - Handles tournament selection
- `_show_tournament_details()` - Displays tournament profile
- `_determine_category()` - Determines tournament level from name
- `_sort_tournament_column()` - Sorts tournament treeview by column header click

### Sortable Columns:
- Tournament name (alphabetical)
- Surface (alphabetical)
- Match count (numeric)

### Tab Height Fix:
Fixed inconsistent tab heights when switching between Players and Tournaments tabs. The selected tab was appearing larger due to default ttk styling. Fixed by adding:
```python
style.map("TNotebook.Tab",
         padding=[("selected", [20, 8]), ("!selected", [20, 8])],
         expand=[("selected", [0, 0, 0, 0])])
```

### Auto-Sort Alphabetically:
"Show All" button now automatically sorts tournaments A-Z by name.

---

## Tournament Name Merge

### What Was Done
Merged all numbered tournament variants into single entries. ITF/Challenger venues often host 10-20+ weeks of events per year, creating entries like "Antalya 5 ITF", "Antalya 6 ITF", etc.

### Changes Made
- 354 numbered tournament names merged
- Pattern: "Location N type" → "Location type"
- Examples:
  - "Antalya 5 ITF" → "Antalya ITF"
  - "Monastir 10 ITF" → "Monastir ITF"
  - "Hersonissos 3 challenger" → "Hersonissos challenger"

### Results
| Tournament | Merged Matches |
|------------|----------------|
| Antalya ITF | 779 |
| Monastir ITF | 1,557 |
| Sharm El Sheikh ITF | 702 |
| Santo Domingo ITF | 342 |
| Hersonissos challenger | 267 |

**Total unique tournaments: 713** (down from 1,033)

---

## Tournament Name Standardization (Betfair Format)

### The Problem
Betfair tournament names didn't match our historical database:
- Betfair: "Concepcion Challenger 2026" → Database: "Concepcion challenger"
- Betfair: "ITF San Diego" → Database: "San Diego ITF"

### Changes Made

**1. Historical data renamed to Betfair format:**
- "challenger" → "Challenger" (9,750 matches)
- "Location ITF" → "ITF Location" (21,477 matches across 341 tournaments)
- "San Diego Challenger" → "San Diego CA Challenger" (62 matches)

**2. Added `normalize_tournament_name()` in `config.py`:**
- Strips year suffixes (2024, 2025, 2026)
- Removes "Ladies/Men's/Women's" prefixes from Grand Slams
- Used by betfair_capture.py on all incoming tournaments

**3. Updated `betfair_capture.py`:**
- Now applies normalization when capturing matches

### Verification
8/10 upcoming tournaments now match historical data:
- Australian Open: 474 matches
- Concepcion Challenger: 63 matches
- San Diego CA Challenger: 62 matches
- etc.

2 tournaments (ITF Vero Beach, WTA Manila) are new with no history yet.

### Sync Button Added
Added "Sync Tournament Names" button to Database Management UI header.
- Calls `db.sync_tournament_names()`
- Updates matches, bets, and upcoming_matches tables
- Shows summary dialog with counts per table

### Auto-Sync on Betfair Capture
Tournament name sync now runs automatically after every Betfair odds capture.
- Added to `betfair_capture.py` after matches are saved
- Only runs if matches were imported (imported > 0)
- Prints sync count to console

---

## Player Data Quality Check

### What Was Added
New "Check Player Data" button in Database Management UI that audits all players in upcoming matches.

### Features
- Scans all players from upcoming_matches table
- Checks match history for each player
- Categorizes by data quality:
  - **NO DATA** (red): 0 matches - needs investigation
  - **LOW DATA** (orange): <5 matches - limited analysis
  - **OK**: 5+ matches - sufficient data
- Shows: match count, surface breakdown (Hard: X, Clay: Y), last match date
- Double-click to jump to player profile
- Summary shows totals per category

### Files Modified
- `src/database_ui.py` - Added button and `_check_player_data()` method

---

## Tournament Edit Feature

### What Was Added
1. **Tournament IDs** - Populated tournaments table with 713 unique tournaments, each with sequential ID
2. **ID Display** - Tournament profile now shows ID number
3. **Edit Button** - Click to edit tournament properties

### Edit Dialog Features
- **Name**: Rename tournament (cascades to matches, bets, upcoming_matches)
- **Surface**: Change surface type (Hard/Clay/Grass) - updates all matches
- **Category**: Set level (Grand Slam, Masters 1000, ATP, WTA, Challenger, ITF, Other)

### Database Changes
- Populated `tournaments` table with all unique tournaments from matches
- Each tournament has: id, name, surface, level, location

### Files Modified
- `src/database_ui.py` - Added ID label, Edit button, `_edit_tournament()` method

---

## Player Edit Feature

### What Was Added
1. **"Show All" button** - Shows top 200 players by match count (like tournaments tab)
2. **"Edit" button** - Edit player properties in profile

### Edit Dialog Features
- **Name**: Rename player (cascades to matches table - winner_name/loser_name)
- **Ranking**: Update current ranking
- **Country**: Update country code
- **ELO**: Update ELO rating

### Files Modified
- `src/database_ui.py` - Added Show All button, Edit button, `_edit_player()` method

---

## Sortable Columns Added

### What Was Done
Made columns sortable in both Players and Tournaments tabs by clicking column headers.

### Players Tab
- ID, Name, Ranking, Matches columns all sortable
- Click header to sort, click again to reverse

### Tournaments Tab
- Name, Surface, Matches columns all sortable
- Removed LIMIT - now shows ALL tournaments and players

---

## Manual Bet Button Added

### What Was Added
New "Manual Bet" button on the home screen (next to "Clear Matches") that opens a dialog to analyze any two players.

### Features
- **Surface Selection**: Pick Hard, Clay, or Grass
- **Player Search**: Type player names - auto-looks up in database
- **Live ID Lookup**: Shows player ID and database name as you type
- **Full Analysis**: Shows probabilities, confidence, factor breakdown
- **Low Data Warnings**: Warns if players have <10 matches

### Files Changed
- `src/main.py` - Added "Manual Bet" button and `_open_manual_bet()` method

---

## Clickable Player Names in Match Analysis

### What Was Added
Player names in the match analysis window are now clickable to open their player profile.

### Features
1. **Clickable Names**: Click on "Sara Daavettila" or "Elvina Kalieva" (any player name) to open their profile popup
2. **Low Data Warning**: If a player has <10 matches, shows "⚠ LOW DATA (X matches) - Click to edit"
3. **Player Profile Popup**: Shows ranking, ELO, surface stats, recent matches
4. **Edit Button**: Can open Database Management to edit the player

### New Function Added
`open_player_profile(parent, player_id, player_name)` in `database_ui.py` - standalone function that can be called from anywhere to show a player profile popup.

### Files Changed
- `src/database_ui.py` - Added `open_player_profile()` function
- `src/bet_suggester.py` - Made player names clickable, added low data warnings

---

## Duplicate Match Prevention Rule

### What Was Added
Prevents betting on both players in the same match. If you already have a bet on Kovacevic v Tabur (on either player), you cannot add another bet on the same match.

### Changes Made

**`database.py`** - New function:
```python
def check_match_already_bet(self, match_description: str, tournament: str = None) -> Optional[Dict]:
    """Check if ANY bet exists for the same match (regardless of which player was selected)."""
```

**`bet_tracker.py`** - Added check in two places:
1. `add_bet()` method - returns -2 if match already bet
2. `_add_bet_dialog()` - shows error dialog with existing selection

### Error Message
```
Match Already Bet
A bet already exists for this match.
Tournament: [tournament]
Match: [match]
Existing selection: [player already bet on]

You cannot bet on both players in the same match.
```

---

## Bug Fixes - Import and Lambda Closure Issues

### Issue 1: `NameError: name 're' is not defined`
**Problem:** The `normalize_tournament_name()` function in `config.py` used regex (`re.sub()`) but `re` was only imported inside another function (`_word_match()`), not at the module level.

**Fix:** Added `import re` at the top of `config.py`.

### Issue 2: Lambda Closure Errors in Exception Handlers
**Problem:** Both `main.py` and `betfair_capture.py` had lambdas inside exception handlers that captured the variable `e`:
```python
except Exception as e:
    self.root.after(0, lambda: self._capture_error(str(e)))  # Bug!
```
By the time the lambda executes, `e` is out of scope, causing `NameError: cannot access free variable 'e'`.

**Fix:** Capture the error message before creating the lambda:
```python
except Exception as e:
    err_msg = str(e)
    self.root.after(0, lambda msg=err_msg: self._capture_error(msg))
```

### Issue 3: Wrong Import Location for `normalize_tournament_name`
**Problem:** `normalize_tournament_name` was imported inside `_guess_surface()` method but used in `save_to_database()` method.

**Fix:** Moved import to top of `betfair_capture.py`:
```python
from config import normalize_tournament_name
```

### Files Changed
- `src/config.py` - Added `import re` at module level
- `src/main.py` - Fixed lambda closure in exception handler (line 1330)
- `src/betfair_capture.py` - Fixed lambda closure + moved import to top level

---

## Data Quality Cleanup - Corrupted Player Records

### The Problem
Several players had unrealistic match counts (200-1100 matches in 12 months) due to abbreviated names being incorrectly merged:
- "Arseneault A." had 1,120 matches (multiple "A. Arseneault" players merged)
- "A. Stephens Sloane" had 348 matches (name reversed, duplicate of Sloane Stephens)
- Players playing against both men AND women (impossible)

### Players Cleaned
| Player | Matches Deleted | Action |
|--------|-----------------|--------|
| Arseneault A. | 1,120 | Renamed to "Ariana Arseneault", matches deleted |
| Prajwal Dev S D | 530 | Matches deleted |
| Zanada E. | 350 | Matches deleted |
| A. Stephens Sloane | 336 | Player deleted (duplicate of Sloane Stephens) |
| Wen Wan I | 229 | Matches deleted |
| Mario Gonzalez Fernandez | 200 | Matches deleted |
| Julia Konishi Camargo Silva | 193 | Matches deleted |
| Andrea Lazaro Garcia | 169 | Matches deleted |
| Alejandro Hernandez Serrano Juan | 162 | Matches deleted |
| Rodrigo Alujas | 160 | Matches deleted |
| Mallory R. | 118 | Matches deleted |
| Queiroz Miguel L. | 98 | Matches deleted |

### Results
- **Total matches deleted**: 3,665
- **Total matches remaining**: 60,189
- **Top player now**: Emiliana Arango with 147 matches (realistic)

### Why This Happened
The data import was matching abbreviated names (like "A." for first initial) to existing players, causing multiple different players to be merged into one record.

---

## Manual Bet Feature Improvements (Continued Session)

### What Was Done
Improved the Manual Bet feature to show the full match analysis screen like in Bet Suggester.

### Changes Made (`src/main.py`)
1. **Added searchable player dropdowns** - Users can now search for players by name and select from a dropdown list (uses `db.search_players()` instead of exact matching)
2. **Dropdown overlays content** - Fixed layout so the suggestion dropdown floats over content instead of pushing elements down (uses Toplevel popup)
3. **Selection persistence** - Fixed bug where player selection was cleared when text was updated
4. **Full match analysis screen** - Clicking "Analyze" now opens the same detailed analysis view from BetSuggester:
   - Player probabilities with color coding
   - Factor Analysis table (8 factors)
   - Recent matches for both players
   - Value Analysis section
   - Analysis Summary

### Technical Details
- Uses `BetSuggesterUI._show_match_analysis()` method to display the full analysis
- Main BetSuggesterUI window is minimized (iconified) so only the analysis popup shows
- Player search uses `db.search_players()` for fuzzy LIKE matching
- Dropdown implemented as `tk.Toplevel` with `overrideredirect(True)` for floating overlay

### Files Changed
- `src/main.py`:
  - Updated `_open_manual_bet()` with searchable player selection
  - Added `_show_manual_analysis()` helper method (backup version)
  - Added `_get_factor_display()` and `_show_recent_matches()` helper methods

### How It Works
1. Open Manual Bet from home screen
2. Type player name (minimum 2 characters)
3. Select player from dropdown list
4. Repeat for second player
5. Choose surface
6. Click Analyze → Full match analysis popup opens

### Analysis Window Contents
The manual analysis popup now shows:
- **Header**: Player names with probabilities (color-coded green for favorite, gray for underdog)
- **Factor Analysis**: 8-factor breakdown with scores and contribution
- **Recent Matches**: Last 5 matches for each player (color-coded wins/losses)
- **Value Analysis**: Shows N/A for Betfair odds, Edge, Expected Value (since manual entry has no odds data)
- **Analysis Summary**: Model favored player, top 3 key factors, confidence level

### Window Management
- Uses `dialog.lift()` and `dialog.focus_force()` to ensure popup appears front and center
- Standalone implementation (`_show_manual_analysis()`) that doesn't depend on BetSuggesterUI

---

## Installer Rebuilt (v2.0)

### What Was Done
Built new installer with all session changes including Manual Bet improvements.

### Build Process
1. `python build_exe.py` - PyInstaller build
2. OneDrive file lock workaround: `shutil.copytree()` with `dirs_exist_ok=True`
3. `ISCC.exe installer.iss` - Inno Setup compiler

### Output
- **File:** `installer_output\TennisBettingSystem_Setup_2.0.exe`
- **Version:** 2.0

### Changes Included
- Manual Bet feature with searchable player dropdowns
- Full match analysis popup (Factor Analysis, Value Analysis, Summary)
- All surface detection fixes
- Tournament name normalization
- Player profile and tournament profile features
- Database UI improvements (sortable columns, edit features)

---

## Session Summary

### Key Accomplishments Today
1. **Manual Bet Feature** - Complete implementation with searchable dropdowns and full analysis popup
2. **Surface Detection** - Centralized in config.py, fixed 5,400+ matches with wrong surfaces
3. **Player Name Matching** - Improved algorithm to prevent false matches
4. **Tournament Profiles** - New tab in Database Management
5. **Data Quality** - Cleaned corrupted player records (3,665 matches)
6. **Installer** - v2.0 built with all changes

### Files Modified
- `src/main.py` - Manual Bet feature
- `src/config.py` - Surface detection, tournament normalization
- `src/database.py` - Player name matching improvements
- `src/database_ui.py` - Tournament tab, player profiles, edit features
- `src/betfair_capture.py` - Surface detection, tournament sync
- `src/match_analyzer.py` - Fixed has_data check

### Build & Release
- **Installer:** `installer_output\TennisBettingSystem_Setup_2.1.exe`
- **Version:** 2.1.0
- **Commit:** `eb9dd3a` - "Release v2.1.0 - Manual Bet, Surface Fixes, Tournament Profiles"
- **Pushed to GitHub:** https://github.com/Anners92/tennis-betting-system

---
