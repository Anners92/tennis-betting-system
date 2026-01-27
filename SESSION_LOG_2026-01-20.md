# Tennis Betting System - Session Log
**Date:** January 20, 2026

---

## Summary of Work Completed

### 1. Critical Bug Fix: Scraper Column Name Mismatch

**Problem:** The scraper was reporting successful imports but matches weren't actually being saved to the database. Investigation revealed:

- Database table had column named `tournament`
- All INSERT statements were using `tourney_name`
- SQLite silently failed on column mismatch
- 16,725 matches had blank tournament names from failed inserts

**Root Cause:** Schema/code inconsistency - the database was created with `tournament` but code was written expecting `tourney_name`.

**Fix Applied:** Changed all references from `tourney_name` to `tournament`:

#### INSERT Statements Fixed (4 files):

| File | Line(s) | Change |
|------|---------|--------|
| `github_data_loader.py` | 201 | `tourney_name` → `tournament` |
| `tennis_explorer_scraper.py` | 1321, 1549 | `tourney_name` → `tournament` |
| `te_import_dialog.py` | 823 | `tourney_name` → `tournament` |
| `database.py` | 756, 845 | `tourney_name` → `tournament` + fallback |

#### CREATE TABLE Statements Fixed (2 files):

| File | Change |
|------|--------|
| `database.py` | Schema definition: `tourney_name TEXT` → `tournament TEXT` |
| `create_seed_database.py` | Schema definition: `tourney_name TEXT` → `tournament TEXT` |

#### READ Statements Fixed (4 files, backward compatible):

| File | Line | Change |
|------|------|--------|
| `bet_suggester.py` | 2040 | Now checks `tournament` OR `tourney_name` |
| `match_analyzer.py` | 147 | Now checks `tournament` OR `tourney_name` |
| `match_assignment.py` | 289 | Now checks `tournament` OR `tourney_name` |
| `player_lookup.py` | 466 | Now checks `tournament` OR `tourney_name` |

### 2. Verified Scraper Works

After the fix:
- Scraper pulled 31,923 matches across all tours
- Successfully imported 2,785 new matches
- Tournament names now populate correctly

### 3. Regenerated Seed Database

- Old seed database had `tourney_name` column (would break for new users)
- Ran `create_seed_database.py` to regenerate with correct `tournament` column
- New seed database includes 3,006 ranked players (1,521 ATP + 1,485 WTA)

### 4. Built New Installer

**Installer:** `TennisBettingSystem_Setup_1.1.0.exe` (23.9 MB)
**Location:** `installer_output\TennisBettingSystem_Setup_1.1.0.exe`

All fixed files copied to `dist\TennisBettingSystem\` before build.

---

## Current Database State

| Metric | Value |
|--------|-------|
| Total matches | 20,586 |
| January 2026 matches | 2,588 |
| Matches with tournament name | 3,861 |
| Matches with blank tournament | 16,725 (legacy from bug) |
| Total players | 3,319 |

**Note:** Decided to leave existing blank tournament data as-is. The fix ensures all **future imports** will work correctly.

---

## Files Changed This Session

```
src/github_data_loader.py      - INSERT statement fix
src/tennis_explorer_scraper.py - INSERT statements fix (2 locations)
src/te_import_dialog.py        - INSERT statement fix
src/database.py                - CREATE TABLE + INSERT fixes
src/create_seed_database.py    - CREATE TABLE fix
src/bet_suggester.py           - READ compatibility fix
src/match_analyzer.py          - READ compatibility fix
src/match_assignment.py        - READ compatibility fix
src/player_lookup.py           - READ compatibility fix
```

All changes also copied to `dist\TennisBettingSystem\`.

---

## Technical Details

### Why the Bug Was Hard to Find

1. INSERT with wrong column name fails silently in SQLite
2. Code had `except Exception: continue` that swallowed errors
3. Scraper reported "imported X matches" based on attempt count, not actual inserts
4. Some matches DID have tournament names (from different code paths), masking the issue

### The Actual Error

```python
# This silently fails - column doesn't exist
INSERT INTO matches (id, tourney_name, date, ...) VALUES (?, ?, ?, ...)

# This works - correct column name
INSERT INTO matches (id, tournament, date, ...) VALUES (?, ?, ?, ...)
```

### Backward Compatibility

READ statements now handle both column names:
```python
# Works with either old or new databases
tournament = match.get('tournament') or match.get('tourney_name') or 'Unknown'
```

---

## Pending Tasks

### Immediate
1. ✅ ~~Verify scraper fix works~~ - DONE
2. ✅ ~~Build new installer~~ - DONE (v1.1.0)
3. **Upload installer to GitHub Releases** (if distributing)

### Optional Backfill
The 16,725 matches with blank tournament names could be backfilled by:
1. Deleting matches with blank tournaments
2. Re-running the scraper to re-import them

User chose to leave as-is for now - not critical for functionality.

### From Previous Session (Still Pending)
- Rankings viewer feature (display ATP/WTA rankings in app)
- Map remaining null players in name_mappings.json

---

## Key Learnings

1. **Always verify INSERT success** - Don't trust attempt counts, check actual row changes
2. **Schema/code sync** - Database schema must match INSERT column names exactly
3. **Silent failures are dangerous** - Broad exception handling can hide critical bugs
4. **Test with fresh database** - The bug would have been caught immediately if tested with a new user's database

---

## Build Information

**Version:** 1.1.0
**Installer:** `installer_output\TennisBettingSystem_Setup_1.1.0.exe`
**Size:** 23.9 MB
**Status:** Ready to distribute

**Includes:**
- Fixed scraper (tournament column fix)
- Correct seed database schema
- 3,006 ranked players
- Backward compatible READ statements

---

## Additional Issues Found & Fixed (Late Session)

### 5. Corrupt Match Data (winner_id = loser_id)

**Problem:** After fixing the column name issue, matches still weren't appearing. Investigation revealed:
- 9,869 matches (47.9%) had `winner_id = loser_id` (same player ID for both)
- This made matches invalid and invisible in player queries
- Caused by earlier imports when name matcher was returning wrong IDs

**Fix:** Deleted all corrupt matches and re-imported:
```sql
DELETE FROM matches WHERE winner_id = loser_id
```
Then re-ran scraper to import 5,046 valid matches.

### 6. Database Location Confusion

**Problem:** App still showed 0 matches after all fixes.

**Root Cause:** Two different database locations:

| Context | Database Path |
|---------|---------------|
| **Development (Python script)** | `<project>\data\tennis_betting.db` |
| **Installed App (exe)** | `C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db` |

I was fixing the development database, but the user was running the installed app which uses Public Documents.

**Fix:** Copied the good database to the installed app location.

---

## IMPORTANT: Database Locations Reference

### Development (running Python script)
```
C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\data\tennis_betting.db
```

### Installed App (running exe)
```
C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db
```

### Seed Database (in installer)
```
C:\Program Files (x86)\Tennis Betting System\data\tennis_betting.db
```
*Copied to Public Documents on first run*

---

## Testing for Next Session

### Test 1: Fresh Install Verification
1. Uninstall the app completely
2. Delete `C:\Users\Public\Documents\Tennis Betting System\` folder
3. Install fresh from `TennisBettingSystem_Setup_1.1.0.exe`
4. Launch app - should show 0 matches initially (seed DB has players only)
5. Click "Quick Refresh" or equivalent to scrape matches
6. Verify matches appear with correct data (different winner/loser IDs)
7. Verify tournament names are populated (not blank)

### Test 2: Scraper Functionality
1. Run scraper from within the installed app
2. Check that matches are saved to Public Documents database
3. Verify no corrupt matches (winner_id ≠ loser_id)

### Test 3: Match Display
1. Look up a known player (e.g., Djokovic)
2. Verify match history appears with correct opponents
3. Verify tournament names display properly

### Known Issues to Watch
- Some matches may have blank tournament names (legacy data)
- ~56,000 matches skipped due to unknown players (expected - players are locked)
- Name matcher may not find all ITF/lower-tier players

---

## Final Database State (End of Session)

| Location | Matches | Status |
|----------|---------|--------|
| Development DB | 9,526 | Good (0 corrupt) |
| Installed App DB | 9,526 | Good (copied from dev) |
| Seed DB (dist) | 0 | Correct (players only) |

**All databases now have `tournament` column (not `tourney_name`).**
