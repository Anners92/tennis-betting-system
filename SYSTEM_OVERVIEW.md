# Tennis Betting System - Technical Documentation

**Version:** 1.4.6
**Last Updated:** January 26, 2026

---

## 1. Technology Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| **Language** | Python 3.11 | Core application |
| **GUI Framework** | Tkinter | Native Python GUI, dark mode themed |
| **Database** | SQLite | Single file, serverless, portable |
| **Packaging** | PyInstaller | Creates standalone Windows .exe |
| **Installer** | Inno Setup 6 | Professional Windows installer |
| **Data Sources** | Betfair Exchange API, GitHub tennisdata, Tennis Explorer |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN APPLICATION                          │
│                          (main.py)                               │
│         Entry point, auto-mode scheduling, tab management        │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│   Bet Tracker   │  Bet Suggester  │ Betfair Capture │   Data    │
│ (bet_tracker.py)│(bet_suggester.py)│(betfair_capture)│  Loader   │
│                 │                 │                 │           │
│ - P/L tracking  │ - Value detect  │ - Live odds     │ - GitHub  │
│ - Result check  │ - Kelly staking │ - Match import  │ - Tennis  │
│ - Model stats   │ - Model filter  │ - Name matching │   Explorer│
├─────────────────┴─────────────────┴─────────────────┴───────────┤
│                       MATCH ANALYZER                             │
│                     (match_analyzer.py)                          │
│            8-factor probability model with calibration           │
├─────────────────────────────────────────────────────────────────┤
│                         DATABASE                                 │
│                       (database.py)                              │
│     SQLite: 14 tables, 3090 players, 27,356 historical matches  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Source Files (34 Python modules)

### Core Application
| File | Purpose |
|------|---------|
| `main.py` | Application entry, window management, auto-mode scheduling |
| `config.py` | Settings, model criteria, factor weights, paths |
| `database.py` | SQLite operations, all database queries |

### Analysis Engine
| File | Purpose |
|------|---------|
| `match_analyzer.py` | 8-factor probability calculation |
| `bet_suggester.py` | Value bet detection, Kelly staking, model filtering |
| `model_analysis.py` | Model performance analysis tools |
| `detailed_analysis.py` | In-depth match breakdowns |

### Bet Management
| File | Purpose |
|------|---------|
| `bet_tracker.py` | P/L tracking, result checking, statistics, model guide |

### Data Integration
| File | Purpose |
|------|---------|
| `betfair_capture.py` | Betfair Exchange API integration |
| `betfair_tennis.py` | Betfair tennis-specific API calls |
| `github_data_loader.py` | Historical match data from GitHub |
| `tennis_explorer_scraper.py` | Web scraping Tennis Explorer |
| `name_matcher.py` | Fuzzy matching Betfair names to database players |
| `odds_api.py` | Pinnacle odds comparison (The Odds API) |

### Rankings & Players
| File | Purpose |
|------|---------|
| `rankings_ui.py` | Rankings display interface |
| `rankings_scraper.py` | Web scraping for rankings |
| `rankings_downloader.py` | Rankings download management |
| `rankings_manager.py` | Rankings data management |
| `player_lookup.py` | Player search interface |

### UI Components
| File | Purpose |
|------|---------|
| `database_ui.py` | Database management interface |
| `data_loader.py` | Data loading interface |
| `te_import_dialog.py` | Tennis Explorer import dialog |
| `match_assignment.py` | Match assignment dialog |
| `odds_scraper.py` | Odds scraping interface |

### Utilities
| File | Purpose |
|------|---------|
| `data_validation.py` | Data validation rules |
| `cleanup_duplicates.py` | Duplicate player cleanup |
| `delete_duplicates.py` | Duplicate deletion |
| `create_seed_database.py` | Seed database generation |
| `flashscore_results.py` | Flashscore scraper (unused) |
| `tennis_abstract_scraper.py` | Tennis Abstract scraper |
| `renumber_players.py` | Player ID renumbering (dev tool) |
| `import_test_bets.py` | Test bet importing (dev tool) |
| `web_app.py` | Web interface (unused) |
| `__init__.py` | Package initialization |

---

## 4. Probability Model (8 Active Factors)

The system uses 8 weighted factors to calculate win probability:

| Factor | Weight | Description |
|--------|--------|-------------|
| **Form** | 25% | Recent match results (last 10 matches with decay) |
| **Surface** | 20% | Historical win rate on Hard/Clay/Grass/Carpet |
| **Ranking** | 20% | ATP/WTA ranking comparison |
| **Fatigue** | 15% | Rest days since last match, recent workload |
| **Recent Loss** | 8% | Penalty for coming off a loss |
| **H2H** | 5% | Head-to-head record between players |
| **Injury** | 5% | Current injury status |
| **Momentum** | 2% | Recent wins on same surface |

**Removed Factors (set to 0%):**
- `opponent_quality` - Redundant, absorbed by form calculation
- `recency` - Redundant, already in form's exponential decay

### Probability Calculation Pipeline

```
1. Calculate raw factor scores for each player
2. Apply weights to get weighted probability
3. Apply 0.5 shrinkage toward 50% (calibration)
4. Blend: 70% model probability + 30% market implied probability
5. Calculate edge: our_probability - implied_probability
```

---

## 5. Betting Models (4 Active)

Only bets qualifying for at least one model are tracked:

| Model | Criteria | Rationale |
|-------|----------|-----------|
| **Model 3** | Edge 5-15% | "Sharp" zone - moderate, realistic edges |
| **Model 4** | Probability ≥ 60% | High confidence favorites only |
| **Model 7** | Edge 3-8% AND odds < 2.50 | Grind strategy on short odds |
| **Model 8** | Probability ≥ 55% AND odds < 2.50 | Profitable baseline segment |

Bets that don't qualify for any model are automatically filtered out.

---

## 6. Kelly Staking

```python
edge = our_probability - implied_probability
kelly_fraction = edge / (odds - 1)
stake = kelly_fraction * 0.25          # Quarter Kelly for safety
stake = max(0.5, min(stake, 3.0))      # Clamp to 0.5u - 3.0u range
```

---

## 7. Database Schema (14 Tables)

### Core Tables
| Table | Rows | Purpose |
|-------|------|---------|
| `players` | 3,090 | Player profiles (name, ranking, country, hand) |
| `matches` | 27,356 | Historical match results |
| `bets` | 63 | Tracked bets with outcomes |
| `upcoming_matches` | 111 | Matches pending analysis |

### Supporting Tables
| Table | Purpose |
|-------|---------|
| `betfair_matches` | Live Betfair odds cache |
| `player_surface_stats` | Surface-specific win rates |
| `player_aliases` | Name mapping variations |
| `head_to_head` | H2H records |
| `rankings_history` | Historical rankings |
| `injuries` | Injury tracking |
| `tournaments` | Tournament metadata |
| `app_settings` | Application settings |
| `metadata` | Database metadata |
| `sqlite_sequence` | SQLite auto-increment tracking |

### Key Bets Table Columns
```sql
bets(
    id, match_date, tournament, match_description,
    player1, player2, market, selection,
    stake, odds, our_probability, implied_probability,
    ev_at_placement, result, profit_loss,
    model,           -- "Model 3, Model 7" etc.
    factor_scores,   -- JSON of all factor data
    notes, in_progress
)
```

---

## 8. Data Flow

```
┌──────────────────┐
│   BETFAIR API    │──→ Live odds, match times
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  NAME MATCHER    │──→ Map Betfair names to database player IDs
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ UPCOMING_MATCHES │──→ Store matches pending analysis
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ MATCH ANALYZER   │──→ Calculate 8-factor probability
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  BET SUGGESTER   │──→ Find value (model prob > market)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  MODEL FILTER    │──→ Only M3/M4/M7/M8 qualifying bets
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  KELLY STAKING   │──→ Calculate stake size (0.5u - 3.0u)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   BET TRACKER    │──→ Track results, P/L, statistics
└──────────────────┘
```

---

## 9. File Locations

### Development
```
Source Code:     C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\src\
Build Output:    C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\dist\TennisBettingSystem\
Installer:       C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\installer_output\
```

### Installed Application
```
Program Files:   C:\Program Files (x86)\Tennis Betting System\
User Data:       C:\Users\Public\Documents\Tennis Betting System\data\
Database:        C:\Users\Public\Documents\Tennis Betting System\data\tennis_betting.db
Name Mappings:   C:\Users\Public\Documents\Tennis Betting System\data\name_mappings.json
```

---

## 10. Auto Mode

The application can run in auto mode, which:
1. Fetches live odds from Betfair on a schedule
2. Analyzes all upcoming matches
3. Automatically adds qualifying bets to the tracker
4. Filters out bets that don't qualify for any model

---

## 11. Current Limitations

| Limitation | Description |
|------------|-------------|
| **Tkinter GUI** | Dated appearance, limited styling, no modern components |
| **Threading** | UI can freeze during API calls |
| **No Charts** | Statistics are text-only |
| **Desktop Only** | No mobile or web access |
| **Manual Refresh** | No real-time odds updates |
| **Windows Only** | Not tested on Mac/Linux |

---

## 12. For a Modern Rebuild

### Core Logic to Preserve
- `match_analyzer.py` - Probability model (the IP)
- `config.py` - Model criteria, factor weights
- `database.py` - SQLite schema and queries
- `betfair_capture.py` / `betfair_tennis.py` - Betfair API integration
- `name_matcher.py` - Fuzzy name matching logic

### Recommended Modern Stack Options

| Approach | Technologies | Pros |
|----------|--------------|------|
| **C# Desktop** | WPF / WinUI 3, Visual Studio | Native Windows, modern UI, MVVM pattern |
| **Python Desktop** | PyQt6 / PySide6 | Cross-platform, better styling than Tkinter |
| **Web Application** | React + FastAPI + PostgreSQL | Access anywhere, real-time updates, charts |
| **Hybrid Desktop** | Electron + React | Desktop app using web technologies |

### Database Migration
SQLite can remain for simplicity, or migrate to:
- PostgreSQL (production web app)
- SQL Server (C# / .NET ecosystem)
