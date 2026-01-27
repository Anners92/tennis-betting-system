# Tennis Betting System - Session Log
**Date:** January 19, 2026

---

## Summary of Work Completed

### 1. Scraper Performance Optimization
- Added **parallel scraping** with ThreadPoolExecutor (3 workers)
- Implemented **7-day cache with TTL** to skip recently scraped players
- Added **priority player list** support (Betfair upcoming matches scraped first)

### 2. Fixed Critical Scraper Bugs

#### Search Function (Tennis Explorer)
- **Problem:** Tennis Explorer search became JavaScript-based, returning 0 players
- **Fix:** Changed to use ranking pages to build player slug lookup (15 pages ATP + 15 pages WTA)

#### Match Parsing
- **Problem:** HTML structure changed to "Player1-Player2" format
- **Fix:** Rewrote `fetch_player_matches()` to parse new structure using `td.first.time` for dates, `td.t-name` for match names, `td.tl` for scores

#### January 2026 Date Parsing (CRITICAL FIX)
- **Problem:** Tennis Explorer labels "Australian Open 2025" for the January 2026 tournament. Scraper used tournament year from URL, causing January 2026 matches to be dated as 2025 or skipped entirely
- **Fix:** Implemented smart year detection that:
  - Checks if tournament year would make date incorrectly in the past (over 300 days ago)
  - For January matches at tournaments labeled "2025", correctly assigns 2026
  - Handles edge cases for year boundary
- **Status:** Fix committed and pushed to GitHub

### 3. Database Fixes Applied
- Fixed 9,833 match dates that had wrong years (2026 → 2025 for future dates)
- Updated player rankings for Navone (74) and Medjedovic (90)
- Fixed wrong player IDs in name_mappings.json:
  - Mariano Navone: 238908652 → 638128299
  - Hamad Medjedovic: 334782060 → 333971074

### 4. App Verification
- App successfully fetches 163 upcoming matches from Betfair
- Australian Open 2026 and Challenger tournaments loading correctly
- 30 new doubles team entries added to database

---

## Current State

### GitHub Repository (https://github.com/Anners92/tennisdata)
- Date parsing fix has been **pushed** and is ready
- Workflow needs to be **re-run** to re-scrape all players with correct January 2026 dates

### Local Database
- Contains test data with some manual fixes
- Will be replaced when GitHub data is refreshed after workflow runs

### Name Mappings (data/name_mappings.json)
Players still needing manual mapping (showing as `null`):
- James Kent Trotter
- Joao Schiessl
- Juan Carlos Prado Angel
- Marat Sharipov
- Martin Damm
- Mateus Alves
- Tatjana Maria

---

## Pending Tasks (Pick Up Here)

### New Feature: Rankings List
**Priority for next session** - Add a rankings viewer within the app:
- Display ATP rankings list (searchable/scrollable)
- Display WTA rankings list (searchable/scrollable)
- Some players currently showing wrong rankings - need to fix
- Should pull from live ranking data or sync with scraper data

### Immediate
1. **Run GitHub Workflow** to re-scrape all players with fixed date logic
   - Go to: https://github.com/Anners92/tennisdata/actions
   - Select "Scrape Tennis Data" workflow
   - Click "Run workflow"

2. **Verify January 2026 matches** are captured for key players (Navone, Medjedovic, etc.)

3. **Map remaining null players** in name_mappings.json to their database IDs

### Build New Installer
After verifying the scraper fix works, build a new installer:

```cmd
cd "C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting"
python build_exe.py
```

If OneDrive locks files:
```powershell
Remove-Item -Recurse -Force 'dist\TennisBettingSystem' -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force 'C:\Users\marca\AppData\Local\Temp\tennis_betting_build\dist\TennisBettingSystem' 'dist\TennisBettingSystem'
```

Then build installer:
```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\installer.iss"
```

Output: `installer_output\TennisBettingSystem_Setup_1.0.0.exe`

### Upload to GitHub Releases
1. Go to: https://github.com/Anners92/tennisdata/releases/new
2. Tag version: `v1.1.0` (increment from 1.0.0)
3. Update `installer.iss` line 5: `#define MyAppVersion "1.1.0"`
4. Drag & drop the installer exe
5. Publish release

---

## Key Files Reference

| File | Location | Purpose |
|------|----------|---------|
| scrape_data.py | tennisdata\ | GitHub scraper (date fix applied here) |
| name_mappings.json | tennis betting\data\ | Betfair → DB player ID mappings |
| github_data_loader.py | tennis betting\src\ | Downloads data from GitHub |
| BUILD_NOTES.md | tennis betting\ | Full build instructions |
| installer.iss | tennis betting\ | Inno Setup installer script |

---

## Important Notes

- **Every player must have data** - no exceptions. User emphasized this multiple times.
- The scraper now handles January matches at year boundaries correctly
- GitHub workflow runs the scraper and uploads compressed database
- App downloads from GitHub on startup if data is older than 24 hours

### CRITICAL: TE Import Duplicate Detection Issue (Fixed)

**Problem:** The TE Import feature was missing matches due to overly broad duplicate detection.

**Root Cause:**
1. First attempt used `date + winner_name + loser_name` - failed because name formats vary (e.g., "Ivan Justo Guido" vs "Guido Ivan Justo")
2. Second attempt used `date + score` - failed because DIFFERENT players can have matches with the same score on the same date (e.g., Schiessl's 6-3, 7-5 match vs Zanellato was skipped because Cervino Ruiz had a 6-3, 7-5 match on the same day)

**Fix:** Changed to `date + score + player name involved`:
```python
cursor.execute("""
    SELECT id FROM matches
    WHERE date = ? AND score = ?
    AND (winner_name LIKE ? OR loser_name LIKE ?)
""", (match['date'], match['score'], f'%{self.player_name.split()[0]}%', f'%{self.player_name.split()[0]}%'))
```

This checks that the match involves the player being imported, not just any match with the same date/score.

**File:** `src/te_import_dialog.py` - `_do_import()` method

---

## Build Status (End of Session)

**Installer Built:** `TennisBettingSystem_Setup_1.0.0.exe` (22.6 MB)
**Location:** `installer_output\TennisBettingSystem_Setup_1.0.0.exe`
**Status:** Ready to upload to GitHub Releases

**nul files:** Deleted (OneDrive cache may still show them temporarily)
