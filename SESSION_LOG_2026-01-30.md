# Session Log - January 30, 2026

## Bug Fix: Missing performance_elo module in installed version

### Problem
Quick Refresh in the installed version crashed with: `Performance Elo error: No module named 'performance_elo'`

### Root Cause
When `performance_elo.py` was created on Jan 29 as a new module, it was added to `src/` but never added to the `py_files` list in `build_exe.py`. The build script has a hardcoded list of `.py` files to copy into the dist folder — any new module not in that list gets silently excluded from the installer.

The import at `main.py:1267` (`from performance_elo import recalculate_all_performance_elo`) worked fine in dev (running from `src/`) but failed in the installed app (running from `dist/TennisBettingSystem/`).

### What Was Changed

1. **`build_exe.py`** — Added `'performance_elo.py'` to the `py_files` list (line 65)
2. **`CLAUDE.md`** — Added a build note warning: when adding new `.py` modules to `src/`, they MUST also be added to `build_exe.py`'s file list
3. **`installer.iss`** — Version bumped from 2.56 to 2.57

### Installer Built & Released
- `TennisBettingSystem_Setup_2.57.exe` (28.2 MB)
- Verified `performance_elo.py` appears in build output: `Copied: performance_elo.py`
- Uploaded to GitHub: https://github.com/Anners92/tennis-betting-system/releases/tag/v2.57

### Process Note
Added build instruction to CLAUDE.md: when building an installer, always complete the full pipeline (build → installer → GitHub upload) before writing session notes.

---

## Feature: !refresh Discord Command

### Problem
Overnight when the Discord bot isn't running, bets finish but never get settled. There was no way to trigger settlement remotely without opening the desktop app.

### What Was Built
New `!refresh` command in `local_monitor.py` that:
1. Logs into Betfair if needed
2. Gets all pending bets from Supabase
3. For each bet with a stored `market_id`, checks Betfair market status
4. Settles any CLOSED markets (Win/Loss) — updates Supabase, local DB, sends Discord alerts
5. Identifies currently live bets and adds them to monitor tracking
6. Reports a summary: settled results with P/L, live bets, errors, unmatched bets

Uses `[PATH: refresh_command]` in settlement logs for traceability.

### Files Modified
- `local_monitor.py` (root + synced to dist)
- `CLAUDE.md` (added `!refresh` to Discord bot commands table)

---

## Removed: Backtester

### Problem
Running the backtester caused the PC to overheat and crash. Investigation found the root cause was a tight CPU-bound loop processing thousands of matches with zero throttling — each match spawned 8 threads running 21 parallel factor calculations, with thousands of uncached database queries per match. The CPU ran at 100% on all cores indefinitely with no sleep or yield.

### Decision
Remove the backtester entirely rather than optimise it. The system has enough live bet data accumulating to evaluate model performance without needing historical backtesting.

### What Was Removed
1. **Deleted `src/backtester.py`** (713 lines) — the entire backtester module
2. **Deleted `backtest_checkpoint.json`** (2.5 MB) — checkpoint data from the last run
3. **Deleted `backtest_results_2026-01-29.csv`** (69 KB) — results from the last run
4. **Removed `get_settled_bets_for_backtest()`** from `database.py` — dead function only used by backtester
5. **Cleaned up comments** in `database.py` and `bet_suggester.py` — removed "for backtesting" references
6. **Synced** `database.py` and `bet_suggester.py` to `dist/TennisBettingSystem/`

---

## Feature: Cloud Backtester via GitHub Actions

### Background
The local backtester was removed earlier today because it overheated the PC (CPU at 90°C+ during the backtest). Temperature monitoring confirmed the AIO cooler is likely failing — 90°C average at 20% CPU load. Switched PC to Power Saver mode as a temporary measure (dropped temps ~30°C).

Rather than rebuild the backtester with throttling and still tie up the PC, moved it to GitHub Actions — free cloud compute with no thermal constraints.

### What Was Built

1. **`src/cloud_backtester.py`** (~500 lines) — Full backtester designed for headless cloud execution
   - Same 8-factor analysis model as the live app
   - Random player assignment to avoid winner bias
   - Surface re-derivation via `get_tournament_surface()` (fixes corruption bug)
   - UTR match exclusion
   - Ranking-based Elo odds proxy (no historical Betfair odds available)
   - Checkpointing every 500 matches (survives workflow timeouts)
   - Output: CSV per-match results + comprehensive summary report
   - Summary includes: model performance (M3/M4/M7/M8), factor accuracy, calibration analysis, surface breakdown, odds range breakdown

2. **`.github/workflows/backtest.yml`** — GitHub Actions workflow
   - Manual trigger via `workflow_dispatch` (GitHub UI button)
   - Inputs: sample size (default: all), months lookback (default: 6)
   - Downloads database + data files from `backtest-data` GitHub release
   - Sets `TENNIS_DATA_DIR` env var for Linux path compatibility
   - Installs python3-tk + selenium/beautifulsoup4 (satisfy module-level imports)
   - Uploads results as workflow artifacts (90-day retention)
   - 6-hour timeout (backtest needs ~2.5 hours for 25k matches)

3. **`src/config.py`** — Added 3-line `TENNIS_DATA_DIR` env var override
   - Allows `BASE_DIR` to be set via environment variable for cloud/CI
   - Zero impact on desktop app (only activates when env var is set)

4. **`backtest-data` GitHub release** — Data files for the cloud backtester
   - `tennis_betting.db` (16MB)
   - `rankings_cache.json`
   - `name_mappings.json`
   - `unmatched_players.json`
   - Update command: `gh release upload backtest-data <file> --clobber`

### How to Use
1. Go to https://github.com/Anners92/tennis-betting-system/actions
2. Click "Tennis Backtest" → "Run workflow"
3. Optionally set sample size / months
4. Wait for completion → download results from Artifacts section

### How to Update Database
When new match data is imported, update the cloud copy:
```bash
gh release upload backtest-data "C:/Users/Public/Documents/Tennis Betting System/data/tennis_betting.db" --clobber
```

### Known Limitations
- No real historical odds — uses ranking-based Elo proxy
- Lookahead bias on rankings/H2H/surface stats (use current data, not as-of-match)
- Form and fatigue are properly date-filtered via `match_date` parameter
- GitHub Actions runner has 2 cores (vs 8 locally) — slower but no time pressure

### Files Created/Modified
- `src/cloud_backtester.py` (new)
- `.github/workflows/backtest.yml` (new)
- `src/config.py` (3-line addition)
- GitHub release: `backtest-data` with 4 data files

### Git
- Committed and pushed to `master`: `3d65ade`
- Also committed all updated source files (14 files, +3020/-193 lines) to bring GitHub repo in sync with working versions

### Bug Fix: First Test Run Failed
- **Error**: `AttributeError: '_GeneratorContextManager' object has no attribute 'cursor'`
- **Cause**: `database.py`'s `get_connection()` is a generator-based context manager (uses `yield`), must be called with `with` statement
- **Also fixed**: `TENNIS_DATA_DIR` path doubling — was set to `.../data`, but `config.py` appends `/data` to `BASE_DIR`, creating `.../data/data/`
- **Fix commit**: `a99f2ca`
- Second test run (100 matches): **SUCCESS** in 46 seconds

### Test Results (100-match sample)
- **Prediction accuracy**: 55/100 (55.0%), breakeven ~52.4%
- **All 4 models profitable**: M3 +21.7% ROI, M4 +23.4%, M7 +16.1%, M8 +44.0%
- **Strong factors**: performance_elo (70.0%), ranking (68.0%), surface (67.8%)
- **Harmful factors**: fatigue (48.9%), recent_loss (43.8%)
- **Calibration issue**: Model overestimates — 75-100% predicted bucket only hits 62.1% actual
- **Odds ranges**: Under 2.50 profitable, over 2.50 losing
- **Note**: Uses proxy odds (ranking-based Elo), not real market odds. Small sample size.

---

## CPU Temperature Investigation

### Problem
User suspected cooling pump failure. HWiNFO64 monitoring confirmed.

### Findings (10-minute monitoring session while gaming)
- **CPU**: AMD Ryzen 7 5800X with AIO liquid cooler
- **CPU Tctl/Tdie**: Min 83.8°C, Avg 90.7°C, Max 92.4°C
- **CPU Usage**: Min 7.5%, Avg 19.7%, Max 45.8%
- **AIO Pump**: 2,122-2,180 RPM (spinning but likely not circulating coolant)
- **GPU**: 42-44°C (normal)
- **87.2% of samples were above 90°C** at under 20% average load
- Peak temp of 92.4°C occurred at only 11.4% CPU load

### Diagnosis
AIO cooler is almost certainly dying. Pump motor spins (shows RPM) but coolant has likely evaporated through tube permeation over time. CPU hitting 90°C at idle is ~30°C above normal for a working AIO on a 5800X.

### Actions Taken
- Changed Windows power plan from High Performance → Power Saver (dropped temps ~30°C)
- Recommended: replace AIO cooler, fix fan curves in BIOS, consider PPT cap and voltage offset

---

## Full 12-Month Data Refresh

### Problem
Database only had 6 months of data (Aug 2025+). The `github_data_loader.py` was changed from 6→12 months on Jan 27, but the database was never re-imported.

### What Was Done
- Created `full_refresh.py` to run `GitHubDataLoader.import_to_main_database()` with 12 months
- Scraped 363,841 total matches across ATP, WTA, ITF Women, ITF Men
- Imported 38,700 matches, 325,000 skipped (duplicates/already in DB)
- 10 name match failures (minor — obscure ITF players)

---

## Discord Bot Sync Fix

### Problem
Discord bot (reads Supabase) and desktop app (reads local SQLite) were showing different bets.

### What Was Done
1. Added `upsert_bet()` method to `SupabaseClient` in `local_monitor.py`
2. Added `sync_local_to_cloud()` function that pushes all local pending bets to Supabase
3. Added `await asyncio.to_thread(sync_local_to_cloud)` at the start of `!pending`, `!inplay`, `!stats`, `!refresh` commands
4. Synced to `dist/TennisBettingSystem/local_monitor.py`

### Also Fixed
- Killed dual bot instances (two `local_monitor.py` processes fighting over same Discord token)
- Restarted single instance

---

## Full Backtest Results (26,784 matches)

### Results
- **Prediction accuracy**: 60.9%
- **M3**: +28.3% ROI | **M4**: +22.0% | **M7**: +28.9% | **M8**: +23.5%
- **Strong factors**: performance_elo (70.4%), ranking (68.9%), surface (64.2%)
- **Harmful factors**: fatigue (43.4%), recent_loss (46.9%)
- **Note**: Uses proxy odds (ranking-based Elo), not real market odds — P/L is approximate

---

## Bundle rankings_cache.json with Installer

### Problem
Two users with the same installer were seeing different value bets and different probabilities. Root cause: `rankings_cache.json` was not included in the installer. Without it, each machine falls back to stale `current_ranking` column in the database, and after one user runs a data refresh, their rankings diverge.

### What Was Changed
- **`build_exe.py`** — Added `rankings_cache.json` to the seed data copy section (after `name_mappings.json`)
- Updated build output messages to mention rankings cache
- Built and released v2.58 installer to GitHub

---

## Feature: Real Historical Odds Integration for Cloud Backtester

### Problem
The cloud backtester used ranking-based Elo as a proxy for market odds, making P/L calculations unrealistic. Real market odds (Pinnacle closing lines) are needed for meaningful backtest results.

### What Was Built

1. **`src/odds_builder.py`** (new, ~420 lines) — Standalone script that:
   - Downloads ATP + WTA XLSX files from tennis-data.co.uk (2000-2026)
   - Parses with openpyxl, extracts Pinnacle odds (PSW/PSL), falls back to AvgW/AvgL then B365W/B365L
   - Embeds `PlayerNameMatcher` for matching "Sinner J." format to database players
   - Builds match index: (date, winner_id, loser_id) → match_id
   - Outputs `odds_lookup.json` keyed by match_id
   - Test results: 10,582 odds rows → 4,579 matched (43.3%) for 2024-2026, 84% for 2025 alone

2. **`src/cloud_backtester.py`** (modified) — Added:
   - `--odds-path` CLI argument
   - Odds JSON loading in `BacktestRunner.__init__`
   - Real odds lookup in `process_match()` before proxy fallback
   - `odds_source` field ('real' or 'proxy') tracked per match
   - `odds_source_analysis()` method in `BacktestSummary`
   - "ODDS SOURCE BREAKDOWN" section in report
   - `odds_source` column in CSV output

3. **`.github/workflows/backtest.yml`** (modified) — Added:
   - `openpyxl` to pip install
   - Download `odds_lookup.json` from `backtest-data` release
   - Fallback: build odds on-the-fly if not pre-built
   - Pass `--odds-path` to backtester

4. **`data/odds_lookup.json`** — Uploaded to `backtest-data` GitHub release

### Unmatched Names (edge cases)
- "Auger-Aliassime F." — hyphenated name not handled
- "O Connell C." — missing apostrophe (O'Connell)
- "Cerundolo J.M." — double initial
- Retired players (Nadal, Murray, Raonic) — not in 3,103-player database

### Coverage
- ATP/WTA main tour: ~84% match rate for 2025
- Challengers/ITF: 0% (not covered by tennis-data.co.uk, uses proxy)
- Overall database coverage: ~43% (many matches are Challengers/ITF)

---
