# Session Log - 2026-01-23

## Housekeeping: Duplicate Bet Fix

### Issue
"Add All to Tracker" in Bet Suggester was creating duplicate bets in the Bet Tracker.

### Root Cause
1. The duplicate check (`check_duplicate_bet`) only looked at **pending** bets (`result IS NULL`)
2. Once a bet was settled (Win/Loss), adding the same bet again wasn't caught
3. No tracking of duplicates within the same "Add All" batch operation

### Changes Made

**database.py** - `check_duplicate_bet()`:
- Added optional `match_date` parameter
- When date provided, checks ALL bets (not just pending) using date prefix match
- Prevents re-adding bets for matches that have already been settled

**bet_suggester.py** - `_add_all_to_tracker()`:
- Added `added_this_batch` set to track (match_description, selection, date) tuples
- Skips duplicates within the same batch before checking database
- Now passes match_date to the duplicate check

**bet_tracker.py** - Manual "Add Bet" dialog:
- Now passes match_date to duplicate check for consistency

### Result
Duplicate bets are now properly prevented, whether from:
- Multiple clicks of "Add All"
- Re-adding bets for already-settled matches
- Duplicate upcoming matches in the analysis

---

## Documentation Regeneration

Full analysis of codebase and regeneration of all documentation files.

### Files Updated

**README.md**:
- Updated version to 1.2.2
- Added 10-factor analysis table
- Updated feature list (duplicate prevention, CSV export)
- Added statistics section (32 modules, 11 tables, etc.)
- Improved project structure description

**CHANGELOG.md**:
- Added version 1.2.2 entry with duplicate bet fix details

**ARCHITECTURE.md**:
- Complete rewrite with accurate module counts and sizes
- Added 10-factor analysis diagram
- Updated data flow diagrams
- Added all 32 modules categorized by function
- Added batch deduplication to design decisions

**CLAUDE.md**:
- Updated version to 1.2.2
- Added architecture overview section
- Added recent fixes section
- Added key files for common tasks table
- Added note about duplicate bet check using date

### Codebase Statistics Confirmed
- 32 Python modules in src/
- 11 database tables
- 10 analysis factors
- ~700KB total source code

---

## Betting Model Improvements (Expert Analysis)

### Analysis Findings
Based on expert review of 48 historical bets:
- **Win rate**: 37.5% (18/48)
- **ROI**: +1.9% (barely profitable)
- **Model overconfidence**: 20-30% (50-59% predicted = 25% actual win rate)
- **Sweet spot**: Odds 2.00-2.99 = +4.6% ROI
- **High market disagreement bets mostly lose**

### 6 Improvements Implemented

#### 1. Probability Calibration
**config.py** - `KELLY_STAKING["calibration"]`:
- Formula: `adjusted_prob = (model_prob * 0.60) + 0.15`
- Effect: 55% model -> 48% calibrated, 65% model -> 54% calibrated

#### 2. Tighter Disagreement Filter
**config.py** - `KELLY_STAKING["disagreement_penalty"]`:
- Minor (<1.3x): 100% stake
- Moderate (1.3-1.5x): 50% stake (was 75%)
- Major (>1.5x): **0% stake - DON'T BET** (was 50%)

#### 3. Odds Range Weighting
**config.py** - `KELLY_STAKING["odds_range_weighting"]`:
- Sweet spot: 2.00-2.99 odds = full stake
- Outside sweet spot: 50% stake

#### 4. Blend Market Probability
**config.py** - `KELLY_STAKING["market_blend"]`:
- 30% market probability, 70% model probability
- Reduces model overconfidence

#### 5. Minimum EV Threshold
**config.py** - `BETTING_SETTINGS["min_ev_threshold"]`:
- Raised from 5% to 10%
- Filters out marginal value bets

#### 6. Value Confidence Display
**bet_suggester.py** - UI changes:
- Added "Conf" column to value tree showing probability ratio
- Color-coded rows: Green (<1.3x), Yellow (1.3-1.5x), Red (>1.5x)
- Asterisk (*) on odds outside sweet spot

### Files Modified
- `config.py`: All settings for improvements 1-5
- `match_analyzer.py`: `find_value()` - calibration, market blend, odds weighting logic
- `bet_suggester.py`: Treeview column and display formatting

### Expected Impact
- Fewer but higher quality bets
- Bets with >1.5x market disagreement will be filtered out
- Visual indicators help user assess bet confidence

---

## Staking Refinements (Continued Session)

### Issue: Stakes Too Low
Initial implementation was too conservative - bets showing only 0.5u-1.0u due to multiple penalties stacking.

### Changes Made

#### 1. Kelly Fraction
- Increased from **0.40** to **0.50** (half Kelly)

#### 2. Fixed Floating Point Bug
- Minor threshold 1.3 was causing edge cases (1.30000001 > 1.3)
- Changed to **1.31** with float buffer note

#### 3. Disabled Confidence Scaling
- `match_analyzer.py`: Commented out confidence scaling in `find_value()`
- Reason: Weighted advantage (0.01-0.20 scale) doesn't map to probability thresholds (0.25-0.40)
- We already have 4 other safeguards

#### 4. Calibration Adjustment
- Multiplier changed from **0.60** to **0.70** (less aggressive shrinkage)
- Result: More reasonable edge calculations

#### 5. Threshold Adjustments (User Preference)
Final thresholds after tuning:
```
Minor:    < 1.40x  → 100% stake
Moderate: 1.40-1.70x → 50% stake
Major:    > 1.70x  → 0% (blocked)
```

### Final Staking Config
```python
kelly_fraction: 0.50
calibration: 0.70x + 0.15
market_blend: 30% market
minor_threshold: 1.40
moderate_threshold: 1.70
```

---

## UI Improvements: EV Columns

### Added P1 EV and P2 EV to Upcoming Matches Table
- Shows expected value for both players in each match
- Format: `+30%` or `-18%`
- Columns are sortable

### Files Modified
- `bet_suggester.py`:
  - Added columns to matches_tree definition
  - Updated `_calculate_odds_background()` to compute both EVs
  - Updated `_update_odds_cell()` to set EV values
  - Added EV sorting support in `_sort_column()`

### Bug Fix: Column Sorting Not Working
- **Issue**: Clicking column headers threw `TypeError: 'NoneType' object is not callable`
- **Cause**: Attribute `self._sort_column = None` shadowed method `def _sort_column()`
- **Fix**: Renamed attribute to `self._sorted_column`

---

## Outstanding Bets Analysis

### Current Position (8.5 units exposure)
| Selection | Odds | Units | EV |
|-----------|------|-------|-----|
| Igor Marcondes | 2.80 | 1.0u | +19.8% |
| Thiago Monteiro | 2.68 | 1.0u | +17.2% |
| Alize Lim | 4.10 | 0.5u | +65.5% |
| Gonzalo Bueno | 2.24 | 2.0u | +21.6% |
| Daniel Michalski | 2.74 | 1.0u | +23.2% |
| Vilius Gaubas | 2.80 | 1.5u | +34.9% |
| Daniil Glinka | 2.58 | 1.0u | +12.7% |
| Yulia Putintseva | 3.65 | 0.5u | +39.9% |

### Voided (1 bet)
- **Luciano Darderi** @ 4.60 - Major disagreement (1.75x > 1.70x threshold)

---

## Housekeeping: File Cleanup

### Deleted Clutter Files
- `src/_ul` - Empty file (0 bytes), typo
- `tennis_betting.db` (root) - Empty, actual DB in `data/`
- `session_log.txt` - Old 40KB log, superseded by dated logs
- `SPEC.txt` - Duplicate of SPEC.md
- `FACTOR_BREAKDOWN_SPEC.txt` - Duplicate of .md version
- `nul` file in parent directory

---

## Auto Mode Feature

### Purpose
Automate the betting workflow so user doesn't need to constantly click. When enabled, the app will:
1. Capture Betfair odds every 30 minutes
2. Run match analysis to find value bets
3. Automatically add value bets to the tracker (no confirmation dialog)

### Implementation

**main.py** changes:

#### State Variables (in `__init__`)
```python
self.auto_mode_enabled = False
self.auto_mode_job = None
self.auto_mode_interval = 30 * 60 * 1000  # 30 minutes in milliseconds
self.next_auto_run = None
```

#### UI Changes (in `_create_quick_actions`)
- Added "Auto Mode" toggle button (purple color, right side)
- Added status label showing "Auto: OFF" / "Auto: ON (next HH:MM)"

#### New Methods
- `_toggle_auto_mode()` - Enables/disables auto mode, updates UI
- `_run_auto_cycle()` - Executes one cycle in background thread:
  1. Capture Betfair odds
  2. Find value bets using `BetSuggester.get_top_value_bets()`
  3. Add bets to tracker using `_auto_add_bets_to_tracker()`
  4. Schedule next run with `root.after()`
- `_auto_add_bets_to_tracker()` - Adds bets silently (no confirmation):
  - Checks for duplicates within batch
  - Checks for duplicates in database
  - Adds "[AUTO]" prefix to notes field

#### Cleanup
- `_on_close()` now cancels auto mode job on window close

### User Experience
- Click "Auto Mode" button to enable
- Button changes to "Stop Auto" when active
- Status shows next scheduled run time (e.g., "Auto: ON (next 14:30)")
- Footer status bar shows progress during cycles
- Bets added automatically marked with "[AUTO]" in notes

### Confirmed Working
- Feature tested and working as expected
- **Yes, captures new Betfair matches** - each cycle calls `capture_all_tennis_matches(hours_ahead=48)` which fetches all matches within 48 hours from Betfair
- New matches appearing on Betfair will be captured, analyzed, and value bets auto-added in subsequent cycles

---

## Mobile App Phase 2: Core Features

### Bet Tracker Screen (Implemented)

**Features:**
- Tab switching between "Pending" and "All Bets"
- Scrollable list of bet cards showing:
  - Match description
  - Selection @ odds (stake)
  - Result/status with color coding
- Tap on pending bet to open settle dialog
- Settle dialog with Win/Loss/Void buttons
- Profit calculation with exchange commission
- Total profit display in header
- Refresh button

**KV Layout:**
- Header with title and profit display
- Tab buttons (Pending/All)
- ScrollView with BoxLayout for bet cards
- Dynamically created bet cards

### Bet Suggester Screen (Implemented)

**Features:**
- Stats row showing matches count and value bets found
- Scrollable list of value bet cards showing:
  - Tournament and surface
  - Match (Player1 vs Player2)
  - Selection @ odds | EV percentage
  - "Add to Tracker" button
- Uses MatchAnalyzer to find value bets (>10% EV)
- Duplicate bet prevention
- Bets marked with "[MOBILE]" in notes

**KV Layout:**
- Header with title and count
- Stats cards (Matches / Value)
- ScrollView with value bet cards
- "Analyze Matches" refresh button

### Files Modified
- `mobile/main.py`:
  - Added full `BetTrackerScreen` class with settle functionality
  - Added full `BetSuggesterScreen` class with value bet detection
  - Updated KV layouts for both screens
  - Added `current_tab` StringProperty for tab state
  - Added imports for `Dict`, `List`, `KELLY_STAKING`

### Database
- Copied latest `tennis_betting.db` to `mobile/data/` for testing

### Testing
- App launches successfully on desktop (Kivy window 360x640)
- Dashboard displays KPI cards
- Bottom navigation works
- All screens render correctly

---

## Mobile App Phase 3: Google Drive Sync

### New Files Created

**`mobile/src/sync/__init__.py`**
- Module init with exports

**`mobile/src/sync/google_drive_sync.py`**
- Full Google Drive sync implementation using PyDrive2
- Features:
  - OAuth2 authentication with Google
  - Upload database to Drive
  - Download database from Drive
  - Smart sync (timestamp comparison)
  - Metadata tracking (last modified, device)
  - Automatic backup before download
  - Status callbacks for UI updates
  - Async sync with threading

### Settings Screen (Implemented)

**Features:**
- Google Drive connection status display
- Local/Cloud database timestamps
- Connect/Disconnect button
- Sync/Upload/Download buttons (when authenticated)
- API credentials dialog for entering Google Cloud Console credentials

**Sync Logic:**
1. Compares local and cloud database timestamps
2. Determines sync direction automatically
3. Creates backup before overwriting local database
4. Stores metadata in Google Drive alongside database
5. Works offline - queues changes for later sync

### How to Use (Setup Steps)

1. **Get Google API Credentials:**
   - Go to https://console.cloud.google.com/
   - Create or select a project
   - Enable Google Drive API
   - Create OAuth 2.0 credentials (Desktop app type)
   - Note down Client ID and Client Secret

2. **In Mobile App:**
   - Go to Settings screen
   - Tap "Set Credentials"
   - Enter Client ID and Client Secret
   - Tap "Connect to Google Drive"
   - Browser opens for OAuth consent
   - After consent, app is connected

3. **Syncing:**
   - "Sync" - Auto-detects which is newer and syncs
   - "Upload" - Force upload local to cloud
   - "Download" - Force download cloud to local

### Files Modified
- `mobile/main.py`:
  - Full `SettingsScreen` class with sync UI
  - Updated KV layout for Settings screen
  - Status properties for sync state display

### Dependencies
- `pydrive2==1.19.0` (already in requirements.txt)

### Testing
- App launches successfully with sync module
- Settings screen renders with all sync controls
- Credentials dialog works

---

## Mobile App Phase 4: Polish

### CSV Export (BetTrackerScreen)

**Feature:**
- Export all bets to CSV file
- On Android: Saves to Downloads folder
- On desktop: Saves to mobile/data/ folder

**Implementation:**
- Added `export_csv()` method to BetTrackerScreen
- Added "Export CSV" button in header
- Includes all bet fields: match, selection, odds, stake, result, profit, notes, date

### Delete Bet Functionality

**Feature:**
- Long-press or tap delete button on bet card
- Confirmation dialog before deletion
- Removes bet from database

**Implementation:**
- Added `delete_bet()` method with confirmation popup
- Delete button visible on each bet card

### Empty State Messages

**Feature:**
- Shows helpful message when no bets exist
- Different messages for Pending vs All tabs

**Messages:**
- Pending tab: "No pending bets. Add bets from the Suggester screen."
- All tab: "No bets yet. Start tracking your bets!"

### Dashboard KPI Updates

**Cards Updated:**
1. **Pending Bets** - Shows count of unsettled bets
2. **Total Bets** - Shows total number of bets
3. **Win Rate** - Shows percentage of winning bets
4. **ROI** - Shows return on investment percentage

**Implementation:**
- Added `win_rate` and `pending_bets` properties to DashboardScreen
- Updated `refresh_data()` to calculate all KPIs
- Cards now show real data from database

### Files Modified
- `mobile/main.py`:
  - BetTrackerScreen: export_csv(), delete_bet(), empty state handling
  - DashboardScreen: Updated KPI properties and calculations

### Testing
- App launches successfully
- All screens render correctly
- CSV export creates file
- Delete confirmation works
- Empty states display when no data

---

## Mobile App: Summary of All Phases

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Foundation (Kivy app, structure) | ✅ Complete |
| Phase 2 | Core Features (Tracker, Suggester) | ✅ Complete |
| Phase 3 | Google Drive Sync | ✅ Complete |
| Phase 4 | Polish (CSV, delete, empty states) | ✅ Complete |

---

## Mobile App: Feature Parity Update

### Desktop Features Ported to Mobile

#### 1. In Progress Status
- Added "Mark In Progress" / "Remove In Progress" button to settle dialog
- Bet cards now show blue background when marked as in progress
- Status displays "LIVE - IN PROGRESS" text

#### 2. Color-Coded Bet Cards
Cards now have background colors matching desktop:
- **Green** (#166534) - Won bets
- **Red** (#991b1b) - Lost bets
- **Amber** (#854d0e) - Voided bets
- **Blue** (#1e40af) - In Progress bets
- **Default** - Pending bets

#### 3. Enhanced Bet Card Display
- Match date shown on each card
- EV percentage displayed (when available)
- Notes field shown (truncated to 40 chars)
- "Tap to settle" hint for pending bets

#### 4. Fetch Betfair Odds Button
- Now shows informative popup explaining:
  - Betfair capture must be done on desktop
  - Steps: Open desktop app → Fetch Betfair → Sync via Google Drive
- Directs user to Settings for sync

#### 5. Database Sync
- Mobile app now uses same database as desktop (copied over)
- Shows 9 pending bets, 59 total bets
- All betting history and stats synchronized

### Files Modified
- `mobile/main.py`:
  - Added `fetch_betfair_odds()` method to DashboardScreen
  - Updated `_show_settle_dialog()` with In Progress toggle
  - Updated `_create_bet_card()` with color-coded backgrounds and enhanced display
  - Connected Betfair button in KV layout

### Testing
- App launches successfully with all data visible
- Dashboard shows correct KPIs from database
- Bet cards display with proper colors
- In Progress toggle works in settle dialog

---

## Mobile App: Betfair Integration

### New Files Added
- `mobile/src/core/betfair_capture.py` - Betfair API integration (adapted from desktop)
- `mobile/src/core/name_matcher.py` - Player name matching (copied from desktop)

### Features Implemented

#### 1. Betfair API Fetch
- "Fetch Betfair Odds" button on Dashboard now works
- Connects to Betfair Exchange API
- Downloads upcoming tennis matches (48 hours ahead)
- Saves matches with odds to database
- Shows progress and result popup

#### 2. Betfair Credentials in Settings
- New "Betfair Exchange" section in Settings
- "Set Betfair Credentials" button opens dialog
- Enter App Key, Username, Password
- Credentials saved to `mobile/data/credentials.json`

#### 3. Shared Credentials
- Desktop credentials copied to mobile folder
- Mobile app auto-uses existing Betfair credentials
- No need to re-enter credentials

### Files Modified
- `mobile/main.py`:
  - `DashboardScreen.fetch_betfair_odds()` - Now calls Betfair API
  - `DashboardScreen._on_betfair_complete()` - Handles completion
  - `SettingsScreen.show_betfair_credentials_dialog()` - Credentials entry
  - Updated KV layout with Betfair section in Settings

### How to Use
1. Go to Dashboard
2. Tap "Fetch Betfair Odds"
3. Wait for matches to load
4. Go to Bet Suggester to see value bets

---

## Mobile App: Android Deployment Preparation

### buildozer.spec Created

**Configuration:**
- App name: Tennis Betting
- Package: com.tennisbetting.tennisbetting
- Version: 1.0.0
- Target API: 33 (Android 13)
- Min API: 21 (Android 5.0)

**Requirements:**
- python3, kivy==2.3.0, requests, pillow
- certifi, charset-normalizer, idna, urllib3

**Permissions:**
- INTERNET - For Betfair API
- ACCESS_NETWORK_STATE - Check connectivity
- WRITE_EXTERNAL_STORAGE - CSV export
- READ_EXTERNAL_STORAGE - File access

### To Build APK (on Linux/WSL)

```bash
cd mobile
pip install buildozer
buildozer android debug
```

APK output: `mobile/bin/`

### Next Steps
- Build APK on Linux/WSL environment
- Test on actual Android device
- Add app icon and splash screen
