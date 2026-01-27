# Changelog

All notable changes to the Tennis Betting System.

---

## [1.4.3] - 2026-01-25

### Added
- **The Odds API Integration** - Compare Betfair odds against Pinnacle (sharp bookmaker)
  - Automatic comparison during Betfair capture
  - 15-minute cache to preserve API quota (500 requests/month free tier)
  - Fuzzy player name matching between sources
  - Stores Pinnacle odds alongside Betfair odds

### Changed
- **Directional Comparison Logic** - Only skip when Betfair offers worse odds than Pinnacle
  - SKIP: Betfair < Pinnacle by >15% (bad value)
  - CAUTION: Betfair < Pinnacle by 7.5-15%
  - GOOD VALUE: Betfair > Pinnacle (keep these bets!)
- **Minimum Liquidity Filter** - £100 minimum to capture odds
  - Filters out thin markets with unreliable prices
  - Prevents capturing wild odds from low-liquidity markets

### Technical
- New module: `odds_api.py`
- New credential: `odds_api_key` in credentials.json
- Files changed: `betfair_capture.py`, `odds_api.py`

---

## [1.4.2] - 2026-01-25

### Removed
- **Models 8, 9, 10 completely removed** - System now uses M1-M7 only
  - Multi-profile weight analysis didn't differentiate (factors correlate)
  - Simplified model tagging system

### Changed
- Reverted multi-profile analysis experiment
- Updated bet tracker UI (M1-M7 only in filter/legend)
- Updated model guide (removed M8-M10 cards)

---

## [1.4.1] - 2026-01-25

### Fixed
- **Critical: Betfair Runner Swap Bug** - Players/odds could be swapped between captures
  - Root cause: Betfair API returns runners in arbitrary order
  - Fix: Sort runners by `sort_priority` before assignment
  - Files fixed: `betfair_capture.py`

### Added
- **Gender Performance Stats** - Male vs Female breakdown in Statistics tab
  - Male = ATP, Challenger, Grand Slam
  - Female = WTA, ITF
  - New method: `get_stats_by_gender()` in bet_tracker.py

---

## [1.4.0] - 2026-01-24

### Added
- **Models 4-7** for different betting strategies:
  - M4 (Favorites): Model probability >= 60%
  - M5 (Underdogs): Model probability < 45%
  - M6 (Large Edge): Edge >= 10%
  - M7 (Grind): Small edge (3-8%) + short odds (<2.50)
- **Backtest Weight Profiles** - Compare historical performance across different weight configurations
- **Factor Score Storage** - Detailed breakdown saved with each bet

### Fixed
- Backfill player ID lookup (was using Betfair IDs instead of database IDs)
- Weight profiles made more extreme for clearer differentiation

---

## [1.3.0] - 2026-01-23

### Added
- **Value Confidence Display** - New "Conf" column in value bets table
  - Shows probability ratio (model vs market)
  - Color-coded rows: Green (<1.3x safe), Yellow (1.3-1.5x caution), Red (>1.5x risky)
  - Asterisk (*) on odds outside the profitable 2.00-2.99 sweet spot

### Changed
- **Probability Calibration** - Model is now calibrated for overconfidence
  - Formula: `adjusted_prob = (model_prob * 0.60) + 0.15`
  - Reduces 55% predictions to 48%, 65% to 54%
- **Tighter Market Disagreement Filters** (based on historical analysis)
  - Minor disagreement (<1.3x): Full stake
  - Moderate disagreement (1.3-1.5x): 50% stake (was 75%)
  - Major disagreement (>1.5x): **No bet** (was 50%) - model likely wrong
- **Odds Range Weighting** - Analysis showed 2.00-2.99 odds are most profitable
  - Bets in sweet spot: Full stake
  - Bets outside sweet spot: 50% stake
- **Market Probability Blending** - 30% market, 70% model (reduces overconfidence)
- **Minimum EV Threshold** - Raised from 5% to 10% (filters marginal bets)

### Technical
- Based on expert analysis of 48 historical bets (37.5% win rate, +1.9% ROI)
- Key finding: Model was 20-30% overconfident (50-59% predicted = 25% actual win rate)
- Files changed: `config.py`, `match_analyzer.py`, `bet_suggester.py`

---

## [1.2.2] - 2026-01-23

### Fixed
- **Critical: Duplicate bets in "Add All to Tracker"** - Fixed issue where duplicate bets were being added
  - Root cause: Duplicate check only looked at pending bets (result IS NULL)
  - Once a bet was settled, the same match could be re-added
  - Now checks ALL bets (not just pending) using match_date prefix match
  - Added batch deduplication within same "Add All" operation
  - Files changed: `database.py`, `bet_suggester.py`, `bet_tracker.py`

### Changed
- `check_duplicate_bet()` now accepts optional `match_date` parameter for more precise matching
- Duplicate check now prevents adding bets for already-played matches (not just pending)

---

## [1.2.1] - 2026-01-22

### Added
- **CSV Export** - Export all bet data to CSV file
  - Export button in bet tracker header
  - Save As dialog with timestamped filename
  - Exports all 19 fields for complete data backup

---

## [1.2.0] - 2026-01-22

### Added
- **Discord Notifications** - Webhook integration for bet tracking
  - Notifications on: add bet, settle bet, edit bet, in-progress toggle
  - Batch notification for mass-add (table format)
  - Settings dialog to configure webhook URL
  - Test webhook functionality
- **Bet Time Field** - Can now set time (HH:MM) when adding/editing bets
- **In Progress Status** - Mark bets as "in progress" with blue highlighting
- **Duplicate Bet Prevention** - Blocks adding bets with same match + selection

### Fixed
- Bet tracker window losing focus after edit
- Inconsistent time display (now always HH:MM, no seconds)

### Documentation
- Added state machine diagrams for bet tracker flows
- Added DATABASE_SCHEMA.md
- Added CONFIGURATION.md
- Added TROUBLESHOOTING.md
- Added ARCHITECTURE.md
- Added CHANGELOG.md
- Added DATA_DICTIONARY.md
- Added README.md

---

## [1.1.0] - 2026-01-20

### Fixed
- **Critical: Scraper column name mismatch** - Matches weren't being saved due to `tourney_name` vs `tournament` column mismatch
- **Corrupt match data** - Deleted 9,869 matches where winner_id = loser_id
- Database location confusion between dev and installed paths

### Changed
- All INSERT statements now use correct `tournament` column
- READ statements backward-compatible (check both column names)
- Regenerated seed database with correct schema

### Technical
- Files fixed: `github_data_loader.py`, `tennis_explorer_scraper.py`, `te_import_dialog.py`, `database.py`, `create_seed_database.py`, `bet_suggester.py`, `match_analyzer.py`, `match_assignment.py`, `player_lookup.py`

---

## [1.0.0] - 2026-01-19

### Added
- **Parallel scraping** - ThreadPoolExecutor with 3 workers
- **7-day cache with TTL** - Skip recently scraped players
- **Priority player list** - Betfair upcoming matches scraped first

### Fixed
- **Tennis Explorer search** - Changed to ranking pages for player lookup (JS-based search broken)
- **Match parsing** - Rewrote for new HTML structure (`td.first.time`, `td.t-name`, `td.tl`)
- **January 2026 date parsing** - Smart year detection for year boundary tournaments
- **TE Import duplicate detection** - Now includes player name in check

### Changed
- Initial installer built: `TennisBettingSystem_Setup_1.0.0.exe`

---

## [0.9.0] - 2026-01-18 (Pre-release)

### Added
- Core application functionality
- Betfair odds capture
- Multi-factor match analysis (form, surface, ranking, H2H, fatigue, injury)
- Value bet detection with EV calculation
- Kelly staking with market disagreement penalties
- Bet tracker with P/L tracking
- SQLite database for all data storage
- Dark mode UI theme

### Data Sources
- Betfair Exchange API integration
- Tennis Explorer scraper
- ATP/WTA ranking imports

---

## Version Numbering

- **Major.Minor.Patch**
- Major: Breaking changes or major feature additions
- Minor: New features, significant improvements
- Patch: Bug fixes, minor changes
