# Tennis Betting System - Build Guide

---

## IMPORTANT: Data Storage Location

**Program Files:** `C:\Program Files (x86)\Tennis Betting System\` - App + seed data
**Public Documents:** `C:\Users\Public\Documents\Tennis Betting System\data\` - Writable user data

On first run, the app copies seed files from Program Files to Public Documents:
- `tennis_betting.db` - Seed database with 3006 ranked players
- `name_mappings.json` - Betfair name to Player ID mappings

---

## UPDATING WITHOUT REINSTALLING

### Fix Unknown Players (Edit name_mappings.json)

Edit this file directly - NO reinstall needed:
```
C:\Users\Public\Documents\Tennis Betting System\data\name_mappings.json
```

Add mappings in format:
```json
"Betfair Player Name": <player_id>
```

**To find player_id:**
1. Open database in SQLite browser
2. Search `players` table (names are "LastName FirstName" format)
3. Use the `id` column value

**Example:** Betfair shows "Juan Manuel La Serna", database has "Manuel La Serna Juan" with id=412:
```json
"Juan Manuel La Serna": 412
```

### Update Database

Replace this file directly:
```
C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db
```

---

## Prerequisites

Install these before building:

| Software | Version | Download | Install Command |
|----------|---------|----------|-----------------|
| Python | 3.11+ | https://python.org | - |
| PyInstaller | Latest | - | `pip install pyinstaller` |
| Inno Setup | 6.x | https://jrsoftware.org/isdl.php | Run installer |

**Verify installations:**
```cmd
python --version
pip show pyinstaller
dir "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

---

## Build Process (2 Steps)

### Step 1: Build Executable

```cmd
cd "C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting"
python build_exe.py
```

**Output:** `dist\TennisBettingSystem\TennisBettingSystem.exe`

**If OneDrive locks files** (Access denied error):
```python
python -c "import shutil; shutil.copytree(r'C:\Users\marca\AppData\Local\Temp\tennis_betting_build\dist\TennisBettingSystem', r'C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\dist\TennisBettingSystem', dirs_exist_ok=True)"
```

### Step 2: Build Installer

```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\installer.iss"
```

**Output:** `installer_output\TennisBettingSystem_Setup_2.0.exe`

---

## Required Source Files

**CRITICAL:** All files below must be listed in `build_exe.py` in the `py_files` array.

### Core Application (24 files)

| File | Purpose | Imported By |
|------|---------|-------------|
| `config.py` | App configuration, paths, constants | Many files |
| `database.py` | SQLite database operations | Many files |
| `database_ui.py` | Database management UI | main.py |
| `data_loader.py` | Data loading UI | main.py |
| `data_validation.py` | Data validation rules | database.py |
| `github_data_loader.py` | Download data from GitHub | data_loader.py |
| `main.py` | Application entry point | PyInstaller |
| `match_analyzer.py` | Match analysis & predictions | main.py, bet_suggester.py |
| `match_assignment.py` | Match assignment dialog | main.py |
| `model_analysis.py` | Model analysis tools | match_analyzer.py |
| `bet_suggester.py` | Bet suggestions UI | main.py |
| `bet_tracker.py` | Bet tracking UI | main.py |
| `player_lookup.py` | Player lookup UI | main.py |
| `betfair_capture.py` | Betfair API capture | main.py |
| `betfair_tennis.py` | Betfair tennis API | betfair_capture.py |
| `odds_scraper.py` | Odds scraping UI | main.py |
| `name_matcher.py` | Player name matching | betfair_capture.py |
| `odds_api.py` | The Odds API (Pinnacle comparison) | betfair_capture.py |
| `rankings_ui.py` | Rankings display UI | main.py |
| `rankings_scraper.py` | Rankings web scraping | rankings_downloader.py |
| `rankings_downloader.py` | Rankings download | rankings_manager.py |
| `rankings_manager.py` | Rankings management | rankings_ui.py |
| `te_import_dialog.py` | Tennis Explorer import | main.py |
| `tennis_abstract_scraper.py` | Tennis Abstract scraper | main.py |
| `tennis_explorer_scraper.py` | Tennis Explorer scraper | te_import_dialog.py |
| `detailed_analysis.py` | Detailed match analysis | bet_suggester.py |
| `discord_notifier.py` | Discord webhook notifications | bet_tracker.py, bet_suggester.py |
| `__init__.py` | Package initialization | - |

### Database Utilities (Included - used by Database UI)

| File | Purpose | Called By |
|------|---------|-----------|
| `cleanup_duplicates.py` | Alias duplicate players | database_ui.py |
| `delete_duplicates.py` | Delete duplicate players | database_ui.py |

### NOT Included in Build (Dev Scripts)

| File | Purpose |
|------|---------|
| `renumber_players.py` | Renumber player IDs (run manually) |
| `web_app.py` | Web app (not used) |

---

## Updating the Build

### When You Add a New .py File

1. Add it to `build_exe.py` in the `py_files` list
2. Add it to this document in the table above
3. Rebuild: `python build_exe.py`
4. Rebuild installer: Run Inno Setup

### When You Only Change Existing .py Files

Quick rebuild without full PyInstaller:

```powershell
# Copy updated source files
Copy-Item "src\*.py" "dist\TennisBettingSystem\" -Force

# Rebuild installer only
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

### When You Update Version Number

1. Edit `installer.iss` line 5: `#define MyAppVersion "1.2.0"`
2. Rebuild installer

---

## Verification Checklist

Before releasing, verify these files exist in `dist\TennisBettingSystem\`:

```
□ TennisBettingSystem.exe
□ config.py
□ database.py
□ database_ui.py
□ data_loader.py
□ data_validation.py
□ github_data_loader.py
□ match_analyzer.py
□ match_assignment.py
□ model_analysis.py
□ bet_suggester.py
□ bet_tracker.py
□ player_lookup.py
□ betfair_capture.py
□ betfair_tennis.py
□ odds_scraper.py
□ name_matcher.py
□ odds_api.py
□ rankings_ui.py
□ rankings_scraper.py
□ rankings_downloader.py
□ rankings_manager.py
□ te_import_dialog.py
□ tennis_abstract_scraper.py
□ tennis_explorer_scraper.py
□ detailed_analysis.py
□ discord_notifier.py
□ cleanup_duplicates.py
□ delete_duplicates.py
□ __init__.py
□ credentials.json (if exists)
□ data/ (folder)
□ output/ (folder)
□ _internal/ (PyInstaller folder)
```

**Quick check command:**
```cmd
dir "dist\TennisBettingSystem\*.py" | find /c ".py"
```
Should show: **30 files**

### CRITICAL: Seed Data Files

These files MUST exist in `dist\TennisBettingSystem\data\`:

```
□ tennis_betting.db    (seed database - 3006 ranked players)
□ name_mappings.json   (Betfair name -> Player ID mappings)
```

**These are copied to Public Documents on first run!**

To regenerate seed database:
```cmd
python src/create_seed_database.py
```

To update name_mappings.json in dist:
```cmd
copy data\name_mappings.json dist\TennisBettingSystem\data\
```

---

## Troubleshooting

### "No module named 'xxx'" Error

A .py file is missing from the build.

1. Check if the file exists in `src\`
2. Add it to `build_exe.py` `py_files` list
3. Copy it: `copy src\xxx.py dist\TennisBettingSystem\`
4. Rebuild installer

### OneDrive File Locking

If build fails with "Access denied":
- Close any file explorers viewing the dist folder
- Wait 30 seconds for OneDrive to sync
- Use the manual copy command (see Step 1)

### SSL/Certificate Errors

The app includes certifi. If downloads fail, check internet connection.

### Installer Won't Run

- Make sure Inno Setup 6 is installed
- Run from correct directory
- Check installer.iss path is correct

---

## File Locations

### Development (This Folder)
| Item | Path |
|------|------|
| Source code | `src\` |
| Build script | `build_exe.py` |
| Installer script | `installer.iss` |
| Built executable | `dist\TennisBettingSystem\` |
| Seed data | `dist\TennisBettingSystem\data\` |
| Installer output | `installer_output\` |
| Name mappings (source) | `data\name_mappings.json` |

### Installed App
| Item | Path |
|------|------|
| Program files | `C:\Program Files (x86)\Tennis Betting System\` |
| User database | `C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db` |
| Name mappings | `C:\Users\Public\Documents\Tennis Betting System\data\name_mappings.json` |

---

## GitHub Repository

**Repository:** https://github.com/Anners92/tennis-betting-system (private)

### After Building, Push to GitHub

```cmd
cd "C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting"
git add -A
git commit -m "Release vX.X.X - description"
git push
```

### Create a GitHub Release with Installer

```cmd
gh release create vX.X.X "installer_output/TennisBettingSystem_Setup_X.X.exe" --title "Tennis Betting System vX.X.X" --notes "Release notes here"
```

---

## Current Version

**Version:** 2.1.0
**Last Updated:** January 27, 2026
**GitHub:** https://github.com/Anners92/tennis-betting-system/releases/tag/v2.1.0

### v2.1.0 Changes
- **Manual Bet Feature** - Analyze any two players with searchable dropdowns and full analysis popup
- **Surface Detection Fix** - Centralized in config.py, fixed 5,400+ matches with wrong surfaces (Halle/Challenger bug)
- **Player Name Matching** - Improved algorithm to prevent false matches
- **Tournament Profiles** - New tab in Database Management with search, stats, top performers
- **Player Profiles** - Enhanced with surface stats, recent matches, fatigue, best/worst results
- **Database UI** - Sortable columns, edit features for players and tournaments
- **Data Quality** - Cleaned 3,665 corrupted player records
- **Tournament Name Normalization** - Betfair names now match historical data

### v2.0.0 Changes
- Fixed bet editing bug - user edits now persist (date sync skip on all user actions)
- Fixed auto mode missing bets - now resolves player IDs using name_matcher
- Added Assets folder to build for taskbar icon
- Added GitHub repository integration
- Skips doubles matches in auto mode

### v1.4.6 Changes (Major Refactor)
- Simplified to 4 models only: M3, M4, M7, M8
- Switched to 8-factor weights (removed opponent_quality, recency)
- Removed weight profiles system - single default weight only
- Removed weighting column from bet tracker
- Added model filter in auto mode - skips bets not qualifying for any model
- Fixed delete button column index
- Cleaned up Model Guide tab

### v1.4.5 Changes
- Database sync fixes
- Initial model filter implementation

### v1.4.4 Changes
- Auto-backfill model tags on launch
- Database auto-update logic

### v1.4.3 Changes
- The Odds API integration for Pinnacle comparison

### v1.4.2 Changes
- Removed Models 8-10, simplified to M1-M7 only

### v1.4.1 Changes
- Fixed Betfair runner ordering bug

### v1.4.0 Changes
- Models 4-7 for different betting strategies
- Shrinkage-based probability calibration
