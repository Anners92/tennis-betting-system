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

## Repository
- **Local:** `C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting`
- **Run App:** `python src\main.py`
- **Monitor:** `python local_monitor.py` (or use start_monitor.vbs)
- **Installer:** `installer_output\TennisBettingSystem_Setup_1.4.6.exe`
- **Version:** 1.4.6
