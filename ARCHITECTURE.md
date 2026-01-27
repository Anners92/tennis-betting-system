# Tennis Betting System - Architecture

High-level system architecture and module relationships.

**Version:** 1.4.3 | **Modules:** 32 | **Tables:** 11

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TENNIS BETTING SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   DATA LAYER    │    │  ANALYSIS LAYER │    │    UI LAYER     │         │
│  │                 │    │                 │    │                 │         │
│  │ - database.py   │───▶│ - match_        │───▶│ - main.py       │         │
│  │ - config.py     │    │   analyzer.py   │    │ - bet_tracker   │         │
│  │                 │    │ - bet_suggester │    │ - bet_suggester │         │
│  └────────┬────────┘    └─────────────────┘    └────────┬────────┘         │
│           │                                              │                  │
│           │                                              │                  │
│  ┌────────▼────────┐                          ┌─────────▼────────┐         │
│  │ EXTERNAL DATA   │                          │   INTEGRATIONS   │         │
│  │                 │                          │                  │         │
│  │ - betfair_      │                          │ - discord_       │         │
│  │   capture.py    │                          │   (webhooks)     │         │
│  │ - odds_api.py   │                          │                  │         │
│  │ - tennis_       │                          └──────────────────┘         │
│  │   explorer_     │                                                       │
│  │   scraper.py    │                                                       │
│  │ - github_data   │                                                       │
│  │   _loader.py    │                                                       │
│  └─────────────────┘                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Categories (32 Total)

### Core Modules (3)

| Module | Size | Purpose | Dependencies |
|--------|------|---------|--------------|
| `main.py` | 54KB | Application entry point, main UI | All UI modules |
| `config.py` | 14KB | Configuration constants, weights | None |
| `database.py` | 71KB | SQLite CRUD (11 tables) | config |

### Analysis Engine (4)

| Module | Size | Purpose | Dependencies |
|--------|------|---------|--------------|
| `match_analyzer.py` | 101KB | 10-factor probability model | database, config |
| `bet_suggester.py` | 223KB | Value bet detection + UI | match_analyzer, database |
| `detailed_analysis.py` | 12KB | Deep player analysis | database |
| `model_analysis.py` | 13KB | Model performance analysis | database |

### Data Collection (9)

| Module | Size | Purpose | Dependencies |
|--------|------|---------|--------------|
| `betfair_capture.py` | 41KB | Betfair API + liquidity filter | database, name_matcher, odds_api |
| `betfair_tennis.py` | 22KB | Betfair API wrapper | requests |
| `odds_api.py` | 21KB | The Odds API (Pinnacle comparison) | requests |
| `github_data_loader.py` | 18KB | Download data from GitHub | database, requests |
| `tennis_explorer_scraper.py` | 79KB | Scrape match data | database, requests, bs4 |
| `tennis_abstract_scraper.py` | 15KB | Tennis Abstract scraper (legacy) | requests, bs4 |
| `rankings_scraper.py` | 11KB | Scrape ATP/WTA rankings | requests, bs4 |
| `rankings_downloader.py` | 28KB | Download ranking CSVs | requests |
| `odds_scraper.py` | 21KB | Odds management (legacy) | database |

### User Interface (7)

| Module | Size | Purpose | Dependencies |
|--------|------|---------|--------------|
| `main.py` | 54KB | Main window, feature grid | All UI modules |
| `bet_tracker.py` | 105KB | Bet tracking, P/L, ROI stats | database |
| `bet_suggester.py` | 223KB | Value bet UI, Add All | match_analyzer |
| `rankings_ui.py` | 12KB | Rankings viewer | database |
| `database_ui.py` | 18KB | Database management UI | database |
| `player_lookup.py` | 25KB | Player search/lookup | database |
| `te_import_dialog.py` | 36KB | Tennis Explorer import | tennis_explorer_scraper |

### Player & Ranking Management (5)

| Module | Size | Purpose | Dependencies |
|--------|------|---------|--------------|
| `name_matcher.py` | 9KB | Match Betfair names to DB | database |
| `rankings_manager.py` | 38KB | Ranking calculation | database |
| `match_assignment.py` | 21KB | Fix player assignments | database |
| `data_loader.py` | 11KB | Generic data loading | database |
| `data_validation.py` | 13KB | Data integrity checks | database |

### Utilities (5)

| Module | Purpose |
|--------|---------|
| `cleanup_duplicates.py` | Remove duplicate matches |
| `delete_duplicates.py` | Bulk delete operations |
| `renumber_players.py` | Fix player ID issues |
| `create_seed_database.py` | Generate fresh seed DB |
| `import_test_bets.py` | Import test bet data |

---

## 10-Factor Analysis Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    MATCH ANALYZER                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: Player 1 ID, Player 2 ID, Surface, Date                 │
│                                                                  │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐     │
│  │ FORM (20%)  │SURFACE(15%) │RANKING(20%) │  H2H (10%)  │     │
│  │ Last 10     │ Career +    │ Current     │ Historical  │     │
│  │ matches     │ Recent 2yr  │ ATP/WTA     │ Record      │     │
│  └─────────────┴─────────────┴─────────────┴─────────────┘     │
│                                                                  │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐     │
│  │OPP QUAL(10%)│RECENCY (8%) │FATIGUE (5%) │INJURY (5%)  │     │
│  │ Strength of │ Time-decay  │ Rest days,  │ Status      │     │
│  │ opponents   │ weighting   │ workload    │ penalties   │     │
│  └─────────────┴─────────────┴─────────────┴─────────────┘     │
│                                                                  │
│  ┌─────────────┬─────────────┐                                  │
│  │REC LOSS(5%) │MOMENTUM(2%) │                                  │
│  │ Penalty for │ Win streak  │                                  │
│  │ recent loss │ bonus       │                                  │
│  └─────────────┴─────────────┘                                  │
│                                                                  │
│  Output: P1 Win%, P2 Win%, Confidence Score, Factor Breakdown   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Odds Capture Flow (with Pinnacle Comparison)

```
Betfair API
    │
    ▼
betfair_capture.py
    │
    ├── Liquidity Filter (£100 minimum)
    │
    ▼
odds_api.py (if configured)
    │
    ├── Fetch Pinnacle odds
    ├── Compare: Betfair vs Pinnacle
    ├── SKIP if Betfair < Pinnacle by >15% (bad value)
    ├── CAUTION if Betfair < Pinnacle by 7.5-15%
    └── GOOD VALUE if Betfair > Pinnacle
    │
    ▼
name_matcher.py ──▶ database.py
        │                  │
        ▼                  ▼
Match player names    upcoming_matches table
```

### 2. Match Analysis Flow

```
database.py (players, matches, rankings_history, surface_stats, h2h, injuries)
    │
    ▼
match_analyzer.py
    │
    ├── Form calculation (last 10 matches, opponent-adjusted)
    ├── Surface stats (career 40% + recent 60%)
    ├── Ranking comparison (normalized 1-200)
    ├── H2H lookup (surface-specific)
    ├── Opponent quality (avg rank of last 6 opponents)
    ├── Recency weighting (7d: 1.0, 30d: 0.7, 90d: 0.4)
    ├── Fatigue (rest days, match difficulty)
    ├── Injury check (status penalties)
    ├── Recent loss (3d: -10%, 7d: -5%)
    └── Momentum (same-surface win streak)
    │
    ▼
Win probabilities + confidence score + factor breakdown
```

### 3. Bet Suggestion Flow

```
upcoming_matches (from Betfair)
    │
    ▼
bet_suggester.py ──▶ match_analyzer.py
    │
    ▼
Calculate EV: (Our Prob × (Odds - 1)) - (1 - Our Prob)
    │
    ▼
Calculate Kelly: Edge / (Odds - 1) × Kelly Fraction × Disagreement Penalty
    │
    ▼
Filter: EV > 5%, Confidence > 40%, Units > 0.5
    │
    ▼
Assign Models: M1-M7 based on criteria
    │
    ▼
Display value bets in sortable table
    │
    ▼
"Add All to Tracker" (with batch deduplication)
```

### 4. Bet Tracking Flow

```
User adds bet (individual or batch)
    │
    ├──▶ Duplicate check (match + selection + date)
    │
    ▼
bet_tracker.py ──▶ database.py (save to bets table)
    │
    ├── Store factor_scores JSON
    ├── Identify model tags (M1-M7)
    │
    ▼
Discord webhook (if configured)
    │
    ▼
Discord channel notification
```

---

## Database Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SQLite Database                          │
│                      (11 Tables, ~70MB typical)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   players   │◄───│   matches   │    │    bets     │         │
│  │   (~5000)   │    │  (~50000)   │    │   (~100+)   │         │
│  │             │    │             │    │             │         │
│  │ id (PK)     │    │ winner_id   │    │ id (PK)     │         │
│  │ name        │    │ loser_id    │    │ selection   │         │
│  │ ranking     │    │ tournament  │    │ stake/odds  │         │
│  └──────┬──────┘    │ date/score  │    │ result      │         │
│         │           └─────────────┘    │ model       │         │
│         │                              │ factor_scores│         │
│         │                              └─────────────┘         │
│  ┌──────┴──────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ rankings_   │    │ head_to_    │    │ upcoming_   │         │
│  │ history     │    │ head        │    │ matches     │         │
│  │             │    │             │    │             │         │
│  │ player_id   │    │ player1_id  │    │ player1_id  │         │
│  │ ranking     │    │ player2_id  │    │ player2_id  │         │
│  │ date        │    │ wins        │    │ odds        │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ surface_    │    │  injuries   │    │ app_        │         │
│  │ stats       │    │             │    │ settings    │         │
│  │             │    │ player_id   │    │             │         │
│  │ player_id   │    │ status      │    │ key/value   │         │
│  │ surface     │    │ body_part   │    │             │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐                             │
│  │ tournaments │    │ player_     │                             │
│  │             │    │ aliases     │                             │
│  │ name        │    │             │                             │
│  │ surface     │    │ alias_id    │                             │
│  │ category    │    │ canonical   │                             │
│  └─────────────┘    └─────────────┘                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## External Integrations

### Betfair Exchange

- **Purpose:** Live odds for upcoming matches
- **API:** Betfair Sports API
- **Auth:** App key + username/password (`credentials.json`)
- **Module:** `betfair_tennis.py`, `betfair_capture.py`
- **Data:** Upcoming matches stored in `upcoming_matches` table
- **Filters:**
  - Minimum liquidity: £100 (`MIN_LIQUIDITY_GBP`)
  - Skip in-play matches
  - Skip doubles (names containing "/")

### The Odds API (Pinnacle Comparison)

- **Purpose:** Compare Betfair odds against sharp bookmaker
- **API:** The Odds API REST endpoint
- **Auth:** API key in `credentials.json` (`odds_api_key`)
- **Module:** `odds_api.py`
- **Free Tier:** 500 requests/month
- **Caching:** 15-minute cache to preserve quota
- **Comparison Logic:**
  - SKIP: Betfair < Pinnacle by >15% (bad value)
  - CAUTION: Betfair < Pinnacle by 7.5-15%
  - GOOD VALUE: Betfair > Pinnacle (keep!)

### GitHub (tennisdata repo)

- **Purpose:** Pre-scraped historical match data
- **URL:** `https://github.com/Anners92/tennisdata`
- **Method:** Download `tennis_data.db.gz`, decompress, merge
- **Module:** `github_data_loader.py`
- **Modes:** Quick refresh (7 days) or Full refresh (6 months)

### Tennis Explorer

- **Purpose:** Match history, player data, recent results
- **Method:** Web scraping (BeautifulSoup)
- **Module:** `tennis_explorer_scraper.py`, `te_import_dialog.py`

### Discord

- **Purpose:** Bet notifications
- **Method:** Webhook POST
- **Events:** Add bet, settle bet, edit bet, in-progress toggle, batch add

---

## Betting Models (M1-M7)

| Model | Name | Criteria |
|-------|------|----------|
| M1 | All Bets | Every value bet (always applied) |
| M2 | Tiered | Extreme odds (<1.5 or >4.0) OR filtered middle |
| M3 | Moderate Edge | 5-15% edge range |
| M4 | Favorites | Model probability >= 60% |
| M5 | Underdogs | Model probability < 45% |
| M6 | Large Edge | Edge >= 10% |
| M7 | Grind | Small edge (3-8%) + short odds (<2.50) |

---

## Configuration Architecture

```
config.py
    │
    ├── PATHS
    │   ├── BASE_DIR
    │   ├── DATA_DIR
    │   └── DB_PATH
    │
    ├── ANALYSIS (10 factor settings)
    │   ├── DEFAULT_ANALYSIS_WEIGHTS
    │   ├── FORM_SETTINGS
    │   ├── SURFACE_SETTINGS
    │   ├── FATIGUE_SETTINGS
    │   ├── OPPONENT_QUALITY_SETTINGS
    │   ├── RECENCY_SETTINGS
    │   ├── RECENT_LOSS_SETTINGS
    │   └── MOMENTUM_SETTINGS
    │
    ├── BETTING
    │   ├── KELLY_STAKING
    │   ├── BETTING_SETTINGS
    │   └── SET_BETTING
    │
    ├── BETFAIR CAPTURE
    │   ├── MIN_LIQUIDITY_GBP (£100)
    │   └── MAX_ODDS_DISCREPANCY (15%)
    │
    ├── UI
    │   └── UI_COLORS (dark theme)
    │
    └── DATA
        ├── IMPORT_SETTINGS
        └── SCRAPER_SETTINGS
```

---

## File Locations

### Development Mode

```
<project>/
├── src/           # Source code (32 modules)
├── data/          # Database + data files
│   ├── tennis_betting.db
│   └── tennis_atp/
├── dist/          # Distribution files for installer
├── installer_output/  # Built installers
├── credentials.json   # API credentials
└── *.md           # Documentation
```

### Installed Mode

```
C:/Users/Public/Documents/Tennis Betting System/
├── data/
│   ├── tennis_betting.db
│   └── name_mappings.json
├── output/
└── logs/

C:/Program Files (x86)/Tennis Betting System/
├── TennisBetting.exe
├── _internal/     # Python runtime
├── credentials.json
└── data/          # Seed database (copied on first run)
```

---

## Threading Model

| Operation | Thread | Reason |
|-----------|--------|--------|
| UI (Tkinter) | Main | Tkinter requirement |
| Betfair API capture | Background (daemon) | Non-blocking |
| Pinnacle comparison | Background (within capture) | Part of capture flow |
| Discord notifications | Background (daemon) | Non-blocking |
| Scraping | Background (ThreadPool) | Parallel I/O |
| Data refresh | Background (daemon) | Keep UI responsive |

---

## Error Handling Strategy

| Layer | Strategy |
|-------|----------|
| Database | SQLite exceptions → user-friendly messages |
| Network | Timeout (30s) + retry with backoff |
| Pinnacle API | Silent fail if not configured, log warning |
| Parsing | Try/except with fallback values |
| UI | Dialog boxes for user errors |
| Background | Silent fail + logging |
| Duplicates | Batch + DB deduplication |

---

## Key Design Decisions

1. **SQLite** - Single-file database, no server needed, portable
2. **Tkinter** - Built into Python, no extra dependencies
3. **Decimal odds** - Industry standard, easier math
4. **Units not currency** - Bankroll-agnostic staking
5. **40% Kelly** - Conservative staking (professional recommendation)
6. **Background threads for network** - Keep UI responsive
7. **Webhook for Discord** - No bot hosting needed
8. **Singleton pattern** - One bet tracker window at a time
9. **Batch deduplication** - Prevent duplicate bets in "Add All"
10. **Date-based duplicate check** - Catch duplicates for settled matches
11. **Pinnacle as truth** - Sharp bookmaker validates Betfair prices
12. **Directional comparison** - Only skip when Betfair < Pinnacle (bad value)
