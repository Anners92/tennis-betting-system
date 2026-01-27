# Tennis Betting System - Claude Instructions

## Session Log Rule

**After each piece of coding work, immediately update the session log for the day.**

- Create a new session log file if one doesn't exist: `SESSION_LOG_YYYY-MM-DD.md`
- Log what was changed, why, and any relevant details
- This ensures progress isn't lost if the window is accidentally closed
- The log should be detailed enough to resume immediately where we left off

## End of Session Rule

**When the user says they're ending the session, ask about future plans.**

Before closing out, ask:
- "What are your next planned features or improvements for the system?"
- "Any bugs or issues you want to tackle next time?"
- "Anything else to add to the TODO list?"

Add their responses to a `## Future Plans / TODO` section in the current session log.

## Running the App

From the project directory (`tennis betting`), run:
```
python src/main.py
```

## Building the Installer

```bash
# Step 1: Build executable
python build_exe.py

# Step 2: If OneDrive locks files, run:
python -c "import shutil; shutil.copytree(r'C:\Users\marca\AppData\Local\Temp\tennis_betting_build\dist\TennisBettingSystem', r'dist\TennisBettingSystem', dirs_exist_ok=True)"

# Step 3: Build installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

## Project Locations

| Location | Path |
|----------|------|
| Source code | `src\` (34 modules) |
| Dist folder | `dist\TennisBettingSystem\` |
| Installer output | `installer_output\` |
| App database | `C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db` |
| Documentation | Root folder `*.md` files |

## Key Context

- Desktop app for tennis betting analysis (ATP/WTA/Challengers/ITF)
- Built with Python 3.11 + Tkinter (dark mode UI)
- **8-factor match analysis model** (form, surface, ranking, fatigue, recent_loss, h2h, injury, momentum)
- **4 betting models**: M3 (5-15% edge), M4 (prob≥60%), M7 (3-8% edge + odds<2.50), M8 (prob≥55% + odds<2.50)
- Data sources: Betfair Exchange API, GitHub tennisdata, Tennis Explorer
- Current version: **2.0.0**

## Factor Weights (v2.0)

| Factor | Weight | Notes |
|--------|--------|-------|
| form | 25% | Absorbs opponent quality signal |
| surface | 20% | Likely edge source vs market |
| ranking | 20% | Solid anchor |
| fatigue | 15% | Market underweights this |
| recent_loss | 8% | Psychological edge |
| h2h | 5% | Market prices this well |
| injury | 5% | Keep |
| momentum | 2% | Keep small |
| opponent_quality | 0% | REMOVED - redundant |
| recency | 0% | REMOVED - redundant |

## Architecture Overview

- **Core**: `main.py`, `config.py`, `database.py` (14 tables)
- **Analysis**: `match_analyzer.py` (8 factors), `bet_suggester.py`
- **Tracking**: `bet_tracker.py` (P/L, ROI, model stats)
- **Data**: `betfair_capture.py`, `github_data_loader.py`, `tennis_explorer_scraper.py`

## Database Stats

- **Players**: 3,090 ranked players
- **Matches**: 27,356 historical matches
- **Tables**: 14 total

## Key Files for Common Tasks

| Task | Files |
|------|-------|
| Fix bet tracking | `bet_tracker.py`, `database.py` |
| Fix analysis | `match_analyzer.py`, `config.py` |
| Fix value bets | `bet_suggester.py` |
| Fix data import | `github_data_loader.py`, `tennis_explorer_scraper.py` |
| Fix Betfair | `betfair_capture.py`, `betfair_tennis.py` |
| Fix model criteria | `config.py` (calculate_bet_model function) |
| UI changes | `main.py`, `config.py` (UI_COLORS) |

## Recent Fixes (v1.4.6 - Jan 26, 2026)

- Simplified to 4 models (M3, M4, M7, M8) - removed M1, M2, M5, M6, M9
- Switched to 8-factor weights (removed opponent_quality, recency)
- Removed weight profiles system - single default weight only
- Removed weighting column from bet tracker
- Added model filter in auto mode - skips "None" model bets
- Fixed delete button column index
- Cleaned up Model Guide tab

## Known Issues to Remember

- Database uses `tournament` column (not `tourney_name`)
- Always sync changes to both `src\` and `dist\TennisBettingSystem\` before building
- Duplicate bet check uses tournament + match_description + selection
- `os.path.exists('nul')` always returns True on Windows (reserved name)

## Betting Philosophy Rules

**CRITICAL - These rules must be followed:**

1. **Bet on ALL levels of tennis** - ATP, WTA, Challengers, ITF
2. **Only bet on model plays** - Must qualify for M3, M4, M7, or M8
3. **Need 100+ bets per model** before drawing conclusions
4. **No premature optimization** - Gather data first
