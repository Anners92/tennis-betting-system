# Tennis Betting System - Session Log
**Date:** January 22, 2026

---

## Session Start

Resuming from January 20, 2026 session. Previous session fixed:
- Scraper column name mismatch (`tourney_name` → `tournament`)
- Corrupt matches (winner_id = loser_id)
- Database location confusion

**Current state:** v1.2.0 installer built, 26,994 matches in database.

---

## Work Completed

### 1. Created CLAUDE.md Files

**Root level (`claude-playground\CLAUDE.md`):**
- Session log rule that applies to ALL projects
- Update log after each piece of coding work to prevent loss on accidental window close

**Project level (`tennis betting\CLAUDE.md`):**
- Project locations reference
- Key context and known issues
- Same session log rule (project-specific copy)

---

### 2. Added Time Field to Bet Tracker

**Problem:** Could only edit date of bets, not time. Tennis matches can be delayed or moved to different times (e.g., rain delay pushing 13:00 match to 16:00).

**Solution:** Added separate time field (24-hour format, HH:MM) to both Add Bet and Edit Bet dialogs.

**Changes to `bet_tracker.py`:**

| Location | Change |
|----------|--------|
| `_add_bet_dialog()` | Added time entry field next to date, combines to `YYYY-MM-DD HH:MM` on save |
| `_edit_bet_dialog()` | Parses existing datetime, displays date/time separately, combines on save |

**UI Layout:**
```
Date: [2026-01-22]  Time: [14:30] (HH:MM)
```

**Behavior:**
- Time is optional (can leave blank)
- If time provided, stored as `YYYY-MM-DD HH:MM`
- If no time, stored as just `YYYY-MM-DD`
- Edit dialog parses existing time from stored value

**File synced to:** `dist\TennisBettingSystem\bet_tracker.py`

---

### 3. Fixed Bet Tracker Window Losing Focus After Edit

**Problem:** After editing a bet, the bet tracker window would go behind the main app window, making it seem like it closed. User couldn't easily edit multiple bets in a row.

**Fix:** Added `self.root.lift()` and `self.root.focus_force()` after the edit save completes, matching the pattern used by other operations like settle bet.

---

### 4. Removed Seconds from Time Display

**Problem:** Times displayed inconsistently - some showed `14:00:00` (with seconds), others `15:00` (without). User wanted consistent HH:MM format.

**Fix:** Added `_format_match_date()` helper method that strips seconds from display:
- If datetime is `YYYY-MM-DD HH:MM:SS`, displays as `YYYY-MM-DD HH:MM`
- Applied to both All Bets table and Pending Bets table

**File synced to:** `dist\TennisBettingSystem\bet_tracker.py`

---

### 5. Added "In Progress" Status for Bets

**Problem:** No way to visually distinguish bets where the match is currently being played (live) from bets that are still pending but haven't started yet.

**Solution:** Added manual "In Progress" toggle with light blue row highlighting.

**Database changes (`database.py`):**
- Added `in_progress INTEGER DEFAULT 0` column to bets table migrations
- Added `set_bet_in_progress(bet_id, in_progress)` method

**UI changes (`bet_tracker.py`):**

| Location | Change |
|----------|--------|
| `_build_pending_table()` | Added "In Progress" button (blue, #1e40af) |
| `_build_pending_table()` | Added `tag_configure('in_progress', background='#1e40af', foreground='white')` |
| `_refresh_pending_table()` | Apply `in_progress` tag to rows where `bet.get('in_progress')` is truthy |
| `_toggle_in_progress()` | New method - toggles in_progress status for selected bet |

**Behavior:**
- Select a pending bet and click "In Progress" button to toggle
- In-progress bets show with light blue background
- Click again to remove the in-progress status
- Status persists in database

**Files synced to:** `dist\TennisBettingSystem\database.py`, `dist\TennisBettingSystem\bet_tracker.py`

---

### 6. Added Discord Notifications for Bet Tracking

**Feature:** Send Discord notifications via webhook when bets are added, settled, or edited.

**New file: `discord_notifier.py`**
- Uses Discord webhooks (no bot token needed)
- Sends formatted embeds with bet details
- Runs in background thread (non-blocking)
- Silent fail if webhook not configured or Discord down

**Notification triggers:**
| Action | Embed Color | Details Included |
|--------|-------------|------------------|
| Add Bet | Green | Tournament, match, date/time, market, selection, odds, stake, potential return |
| Settle Win | Green | Tournament, match, selection, odds, stake, P/L |
| Settle Loss | Red | Tournament, match, selection, odds, stake, P/L |
| Settle Void | Gray | Tournament, match, selection, odds, stake, P/L |
| Edit Bet | Amber | Tournament, match, date/time, market, selection, odds, stake |
| In Progress | Blue | Tournament, match, selection, odds, stake (title: "Match Started") |
| Revert In Progress | Gray | Tournament, match, selection, odds, stake (title: "Match Status Reverted") |

**UI changes (`bet_tracker.py`):**
- Added "Settings" button in header (next to Refresh)
- Settings dialog with:
  - Webhook URL input field
  - Help text for creating Discord webhooks
  - "Test Webhook" button (sends test message)
  - Save/Cancel buttons
- Webhook URL stored in database via `app_settings` table

**Integration points:**
| Location | Change |
|----------|--------|
| `save_bet()` in `_add_bet_dialog()` | Calls `discord_notifier.notify_bet_added()` |
| `_settle_selected()` | Calls `discord_notifier.notify_bet_settled()` |
| `_settle_from_all_bets()` | Calls `discord_notifier.notify_bet_settled()` |
| `save_changes()` in `_edit_bet_dialog()` | Calls `discord_notifier.notify_bet_edited()` |
| `_toggle_in_progress()` | Calls `discord_notifier.notify_bet_in_progress()` |
| `_toggle_in_progress_all_bets()` | Calls `discord_notifier.notify_bet_in_progress()` |

**Files synced to:** `dist\TennisBettingSystem\discord_notifier.py`, `dist\TennisBettingSystem\bet_tracker.py`

---

### 7. Added Duplicate Bet Prevention

**Problem:** When using bet suggester to add bets to the tracker, the same bet could be added multiple times if clicked repeatedly.

**Solution:** Block duplicate bets entirely. Before adding a bet, check if a pending bet with the same match description AND selection already exists.

**Database changes (`database.py`):**
- Added `check_duplicate_bet(match_description, selection)` method
- Returns existing bet if found (pending only), None otherwise

**UI changes (`bet_tracker.py`):**
- Added duplicate check in `save_bet()` inside `_add_bet_dialog()`
- Shows error dialog: "A pending bet already exists for this match and selection"
- Bet is NOT added, dialog stays open

**Mass-add fix (`bet_suggester.py`):**
- Updated `_add_all_to_tracker()` to check for duplicates before adding each bet
- Duplicates are silently skipped
- Shows count of added AND skipped: "Added X bet(s). Y duplicate(s) skipped."
- Sends batch Discord notification with all added bets in a table format

**Batch Discord notification (`discord_notifier.py`):**
- Added `notify_bets_added_batch(bets)` function
- Shows all bets in one embed with a table:
  ```
  Selection            Odds  Stake
  ----------------------------------
  Player Name          2.50  1.00u
  Another Player       1.85  0.75u
  ----------------------------------
  Total                      1.75u
  ```

**Files synced to:** `dist\TennisBettingSystem\database.py`, `dist\TennisBettingSystem\bet_tracker.py`, `dist\TennisBettingSystem\bet_suggester.py`, `dist\TennisBettingSystem\discord_notifier.py`

---

### 8. Updated State Machine Diagrams

Added new flow diagrams to `docs\state_machines.txt`:

| # | Diagram | Description |
|---|---------|-------------|
| 9 | Add Bet Flow | Dialog → Validate → Duplicate Check → Save → Discord |
| 10 | Settle Bet Flow | Select → Calculate P/L → Update DB → Discord |
| 11 | In Progress Toggle | Toggle status → Discord (blue/gray) → UI highlight |
| 12 | Discord Notification | URL check → Build embed → Background thread → POST |
| 13 | Mass-Add Bets | Confirm → Loop with duplicate check → Batch Discord |
| 14 | Settings Dialog | Load URL → Test/Save options → Persist to DB |

---

### 9. Created Technical Documentation Suite

Added 7 new documentation files:

| Document | Purpose | Size |
|----------|---------|------|
| **README.md** | Project overview, quick start, structure | ~2KB |
| **DATABASE_SCHEMA.md** | All tables, columns, relationships, indexes | ~8KB |
| **CHANGELOG.md** | Version history (v0.9.0 → v1.1.0) | ~3KB |
| **CONFIGURATION.md** | All config.py settings explained | ~6KB |
| **TROUBLESHOOTING.md** | Common issues and solutions | ~5KB |
| **DATA_DICTIONARY.md** | Terms, fields, calculated values | ~5KB |
| **ARCHITECTURE.md** | System overview, module relationships, data flows | ~6KB |

**Total documentation files now:** 15 (including existing specs, build notes, session logs)

---

### 10. Built v1.2.0 Installer

**Build process:**
1. Added `discord_notifier.py` to `build_exe.py` py_files list
2. Updated version to `1.2.0` in `installer.iss`
3. Updated `BUILD_NOTES.md` with discord_notifier.py (file count: 29)
4. Updated `CHANGELOG.md` with v1.2.0 release notes
5. Updated `CLAUDE.md` version reference

**PyInstaller build:**
- Ran `python build_exe.py`
- OneDrive file locking issue - resolved by manually removing old dist folder
- Copied from temp directory to dist folder
- Database included: 3,059 players, 26,994 matches

**Inno Setup:**
- Ran `ISCC.exe installer.iss`
- Warning: "Constant 'pf' has been renamed. Use 'commonpf' instead" (non-blocking)
- Successful compile in 83.7 seconds

**Output:** `installer_output\TennisBettingSystem_Setup_1.2.0.exe` (28.2 MB)

**Files included in build:**
- 29 Python source files
- Seed database with 3,059 players
- Name mappings for Betfair matching
- All new features: Discord notifications, duplicate prevention, in-progress status

---

### 11. Copied Test Bets to Installed App

**Problem:** User had 45 bets in the dev database from testing, wanted to use them in the installed app.

**Solution:** Copied bets table data (not entire database) to preserve installed app's other data.

**Script:** Python script to export bets from dev and insert into installed database:
- Skipped ID column (auto-increment in destination)
- Preserved all bet fields including `in_progress` status

**Result:**
- Dev database: 45 bets
- Installed app before: 10 bets
- Installed app after: 55 bets

---

### 12. Added CSV Export to Bet Tracker

**Feature:** Export all bet data to a CSV file.

**UI changes (`bet_tracker.py`):**
- Added "Export" button in header bar (next to Settings)
- Added `_export_bets()` method

**Export behavior:**
- Exports ALL bets (pending + settled) - no limit
- Opens Save As dialog with default filename: `bets_export_YYYYMMDD_HHMMSS.csv`
- User chooses save location
- Shows confirmation with count of exported bets

**CSV columns exported:**
| Column | Description |
|--------|-------------|
| id | Bet ID |
| match_date | Date/time of match |
| tournament | Tournament name |
| match_description | Match description (Player1 vs Player2) |
| player1 | Player 1 name |
| player2 | Player 2 name |
| market | Market type (Match Winner, etc.) |
| selection | Selected player/outcome |
| stake | Stake amount (units) |
| odds | Odds at placement |
| our_probability | Model probability |
| implied_probability | Implied probability from odds |
| ev_at_placement | EV at time of bet |
| result | Win/Loss/Void |
| profit_loss | P/L including commission |
| notes | Any notes |
| created_at | When bet was added |
| settled_at | When bet was settled |
| in_progress | 0/1 if match is live |

**Files synced to:** `dist\TennisBettingSystem\bet_tracker.py`

---

### 13. Built v1.2.1 Installer

**Changes in this version:**
- CSV export feature for bet tracker

**Build process:**
1. Updated version to `1.2.1` in `installer.iss`
2. Ran Inno Setup compiler
3. Updated CHANGELOG.md

**Output:** `installer_output\TennisBettingSystem_Setup_1.2.1.exe`

**Compile time:** 31.9 seconds

---

### 14. Fixed In-Progress Flag Not Clearing on Settle

**Problem:** Bets marked as "in progress" (blue highlight) stayed blue after being settled as Win/Loss/Void. The `in_progress` flag wasn't being reset.

**Fix:** Updated `settle_bet()` in `database.py` to include `in_progress = 0` in the UPDATE statement.

**Files changed:**
- `src\database.py` (line 1311)
- `dist\TennisBettingSystem\database.py` (line 1311)

**Note:** Existing settled bets with stale `in_progress=1` can be fixed with:
```sql
UPDATE bets SET in_progress = 0 WHERE result IS NOT NULL
```

---

### 15. Removed Discord Webhook Feature

**Reason:** User decided to remove the feature entirely rather than just disable it.

**Removed:**
- `discord_notifier.py` - Deleted from both `src\` and `dist\`
- Import statement from `bet_tracker.py`
- All `discord_notifier.notify_*` calls from:
  - `_add_bet_dialog()` save function
  - `_settle_selected()`
  - `_settle_from_all_bets()`
  - `_toggle_in_progress()`
  - `_toggle_in_progress_all_bets()`
  - `_edit_bet_dialog()` save function
- Settings button from bet tracker header
- `_show_settings_dialog()` method
- Batch notification from `bet_suggester.py` `_add_all_to_tracker()`

**Files changed:**
- `src\bet_tracker.py`
- `src\bet_suggester.py`
- `dist\TennisBettingSystem\bet_tracker.py`
- `dist\TennisBettingSystem\bet_suggester.py`

**Files deleted:**
- `src\discord_notifier.py`
- `dist\TennisBettingSystem\discord_notifier.py`

---

### 16. Started Android Mobile App Development (Kivy)

**Goal:** Create a full-featured Android app with Google Drive sync for mobile betting.

**User Requirements (from extensive interview):**
- Full desktop replacement functionality
- Google Drive database sync (either device can be master)
- Must work offline, sync when online
- Betfair API for live odds
- Dark theme matching desktop, bottom tabs navigation
- APK file delivery

**Project Structure Created:**
```
tennis betting/mobile/
├── main.py                      # Kivy app entry point
├── buildozer.spec               # Android build config
├── requirements.txt
├── src/
│   ├── core/
│   │   ├── config.py            # Android-adapted paths
│   │   ├── database.py          # With sync queue support
│   │   ├── match_analyzer.py    # Copied from desktop
│   │   ├── name_matcher.py      # Copied from desktop
│   │   └── data_validation.py   # Copied from desktop
│   ├── sync/                    # (to be implemented)
│   ├── screens/                 # (to be implemented)
│   ├── widgets/                 # (to be implemented)
│   └── utils/                   # (to be implemented)
├── kv/                          # KivyMD layouts
└── assets/
```

**Files Created:**

| File | Purpose |
|------|---------|
| `mobile/main.py` | Kivy app with Dashboard, bottom nav, KPI cards |
| `mobile/src/core/config.py` | Android path detection, all constants |
| `mobile/src/core/database.py` | SQLite with sync queue table and callbacks |
| `mobile/requirements.txt` | Python dependencies (kivy, requests, pydrive2) |
| `mobile/buildozer.spec` | Android APK build configuration |

**Key Adaptations:**

1. **config.py Changes:**
   - Platform detection using `kivy.utils.platform`
   - Android storage paths via `android.storage.app_storage_path()`
   - Fallback paths for desktop development

2. **database.py Changes:**
   - Removed Windows lock file logic
   - Added `pending_sync_queue` table for offline changes
   - Added `sync_timestamp` column to bets table
   - Added `set_sync_callback()` for sync notifications
   - Added `queue_sync_action()` and related methods

3. **main.py Features:**
   - Dashboard with 4 KPI cards (Players, Matches, Bets, ROI)
   - Dark theme matching desktop colors
   - Bottom navigation tabs
   - Placeholder screens for Tracker, Suggester, Settings

**Build Configuration (buildozer.spec):**
- Target API: 33, Min API: 21
- Architecture: arm64-v8a
- Permissions: INTERNET, ACCESS_NETWORK_STATE, WRITE/READ_EXTERNAL_STORAGE

**Phase 1 Status: Foundation Complete**

Next steps for full implementation:
- Phase 2: Core Features (Bet Tracker, Suggester, Analysis)
- Phase 3: Cloud Sync (Google Drive integration)
- Phase 4: Polish (CSV export, error handling, testing)

---

### 17. Added Android Safe Area Padding

**Problem:** Content could overlap with Android status bar (top) and navigation bar (bottom).

**Solution:** Added safe area spacing to `main.py`:

| Property | Default | Purpose |
|----------|---------|---------|
| `status_bar_height` | dp(24) | Top status bar spacer |
| `nav_bar_height` | dp(48) | Bottom navigation bar spacer |

**Changes to `main.py`:**
- Added `_build_status_bar_spacer()` - Creates top spacing widget
- Added `_build_nav_bar_spacer()` - Creates bottom spacing widget
- Added `_get_android_safe_area()` - Detects actual Android insets via jnius
- Root layout now: Status spacer → ScreenManager → Bottom Nav → Nav spacer

**Behavior:**
- Desktop: Uses default values for testing (24dp top, 48dp bottom)
- Android: Detects actual system bar heights via WindowInsets API

---

## Mobile App Saved Location

All mobile app files are saved in:
```
tennis betting/mobile/
├── main.py                 # Kivy app with Dashboard + safe area
├── buildozer.spec          # Android APK build config
├── requirements.txt        # Dependencies
├── data/
│   └── tennis_betting.db   # Local database copy
└── src/
    └── core/
        ├── config.py       # Android-adapted paths
        ├── database.py     # With sync queue support
        ├── match_analyzer.py
        ├── name_matcher.py
        └── data_validation.py
```

**To resume later:** Open this folder and continue from Phase 2.

---

## Pending Tasks

- **Android App Phase 2:** Implement Bet Tracker, Bet Suggester, Match Analysis screens
- **Android App Phase 3:** Google Drive sync integration
- **Android App Phase 4:** Polish and testing
- Surface-specific Elo (plan saved, deferred)
- Fresh install verification testing
- Rankings viewer feature
- Map remaining null players in name_mappings.json
- P0: Model validation, non-linear ranking, reduce longshot bias
- P1: Automation, bet tracking

---
