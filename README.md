# Tennis Betting System

A desktop application for tennis betting analysis. Captures live odds from Betfair Exchange, analyzes matches using a 10-factor probability model, compares against Pinnacle odds, suggests value bets with Kelly staking, and tracks betting performance.

**Current Version:** 1.4.3

---

## Features

- **Betfair Integration** - Capture live tennis odds from Betfair Exchange with £100 minimum liquidity filter
- **Pinnacle Comparison** - Compare Betfair odds against sharp bookmaker (The Odds API integration)
- **10-Factor Match Analysis** - Form, surface, ranking, H2H, fatigue, injury, opponent quality, recency, recent loss, momentum
- **Value Bet Detection** - Identifies positive EV opportunities with confidence indicators
- **7 Betting Models** - M1 (All Bets) through M7 (Grind) for different strategies
- **Kelly Staking** - Evidence-based stake sizing with market disagreement penalties
- **Bet Tracking** - Track placed bets, P/L, ROI by surface/market/month/gender
- **Discord Notifications** - Get notified when bets are placed/settled
- **CSV Export** - Export all bet data for external analysis
- **Duplicate Prevention** - Blocks duplicate bets (same match + selection + date)

---

## Quick Start

### Running from Source

```bash
# Navigate to project
cd "tennis betting"

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

### Running the Installer

1. Run `TennisBettingSystem_Setup_1.4.3.exe` from the `installer_output` folder
2. First run will initialize the database in `C:/Users/Public/Documents/Tennis Betting System/`

---

## Requirements

- Python 3.10+
- Windows 10/11
- Betfair account (for odds capture)

### Python Dependencies

```
requests>=2.28.0
beautifulsoup4>=4.0.0
selenium>=4.0.0
webdriver-manager>=4.0.0
```

---

## API Setup

### Betfair Exchange (Required)

1. Create a Betfair account at [betfair.com](https://betfair.com)
2. Get an API key from [developer.betfair.com](https://developer.betfair.com)
3. Add credentials to `credentials.json`:

```json
{
    "betfair_app_key": "YOUR_APP_KEY",
    "betfair_username": "YOUR_USERNAME",
    "betfair_password": "YOUR_PASSWORD"
}
```

### The Odds API (Optional - Pinnacle Comparison)

1. Sign up at [the-odds-api.com](https://the-odds-api.com) (free tier: 500 requests/month)
2. Add to `credentials.json`:

```json
{
    "odds_api_key": "YOUR_API_KEY"
}
```

### Discord (Optional - Notifications)

1. Create a webhook in your Discord server (Server Settings > Integrations > Webhooks)
2. In the app: Bet Tracker > Settings > Paste webhook URL > Save

---

## Project Structure

```
tennis betting/
├── src/                        # Source code (32 modules)
│   ├── main.py                 # Application entry point
│   ├── config.py               # Configuration constants
│   ├── database.py             # SQLite database layer (11 tables)
│   ├── match_analyzer.py       # 10-factor analysis engine
│   ├── bet_tracker.py          # Bet tracking UI + ROI stats
│   ├── bet_suggester.py        # Value bet detection + Add All
│   ├── betfair_capture.py      # Betfair odds capture + liquidity filter
│   ├── odds_api.py             # The Odds API (Pinnacle comparison)
│   ├── github_data_loader.py   # GitHub data download
│   ├── tennis_explorer_scraper.py  # TE web scraper
│   ├── name_matcher.py         # Player name matching
│   └── ...                     # 21 more modules
├── data/                       # Local data files
│   ├── tennis_betting.db       # SQLite database (~70MB)
│   └── tennis_atp/             # ATP historical data
├── dist/                       # Distribution files for installer
│   └── TennisBettingSystem/
├── installer_output/           # Built installers
├── credentials.json            # API credentials (not in git)
└── *.md                        # Documentation files
```

---

## Configuration

All configuration is in `src/config.py`:

- **Analysis weights** - How much each of 10 factors affects predictions
- **Kelly staking** - Bankroll management (40% Kelly, 2% unit size)
- **Betfair settings** - Minimum liquidity (£100), odds discrepancy threshold (15%)
- **EV thresholds** - Minimum 5% EV, high value at 15%
- **UI colors** - Premium dark mode theme

See [CONFIGURATION.md](CONFIGURATION.md) for full details.

---

## Data Sources

| Source | Data | Method |
|--------|------|--------|
| Betfair Exchange | Live odds, upcoming matches | API capture |
| The Odds API | Pinnacle odds for comparison | REST API |
| GitHub (tennisdata) | Historical matches | Compressed DB download |
| Tennis Explorer | Match results, player data | Web scraping |
| ATP/WTA Rankings | Weekly rankings | CSV import |

---

## Key Workflows

1. **Capture Matches** - Pull upcoming matches + odds from Betfair (filters thin markets)
2. **Pinnacle Check** - Compare against Pinnacle odds (skip bad value)
3. **Analyze** - Run 10-factor analysis on each match
4. **Find Value** - Filter for EV > 5%, confidence > 40%
5. **Place Bets** - Add selected bets to tracker (individual or "Add All")
6. **Track Results** - Settle bets, monitor P/L and ROI

---

## Betting Models (M1-M7)

| Model | Description | Criteria |
|-------|-------------|----------|
| M1 | All Bets | Every value bet identified |
| M2 | Tiered | Extreme odds + filtered middle range |
| M3 | Moderate Edge | 5-15% edge range |
| M4 | Favorites Only | Model probability >= 60% |
| M5 | Underdogs Only | Model probability < 45% |
| M6 | Large Edge | Edge >= 10% |
| M7 | Grind | Small edge (3-8%) + short odds (<2.50) |

---

## Match Analysis Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| Form | 20% | Last 10 matches, opponent-adjusted |
| Ranking | 20% | Current ATP/WTA ranking comparison |
| Surface | 15% | Career + recent (2yr) surface win rate |
| H2H | 10% | Head-to-head record, surface-specific |
| Opponent Quality | 10% | Strength of recent opponents faced |
| Recency | 8% | Time-decay weighting on form data |
| Fatigue | 5% | Rest days, workload, match difficulty |
| Injury | 5% | Active injury status penalties |
| Recent Loss | 5% | Penalty for losses in last 3-7 days |
| Momentum | 2% | Winning streak bonus (same surface) |

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, module relationships |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | 11 database tables and relationships |
| [CONFIGURATION.md](CONFIGURATION.md) | All configurable settings |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and fixes |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [BUILD_NOTES.md](BUILD_NOTES.md) | How to build the installer |
| [STAKING_FRAMEWORK.md](STAKING_FRAMEWORK.md) | Kelly staking methodology |

---

## Building

See [BUILD_NOTES.md](BUILD_NOTES.md) for detailed build instructions.

Quick build:
```bash
# Sync src to dist first
# Then run Inno Setup compiler
iscc installer.iss
```

---

## Statistics

| Metric | Value |
|--------|-------|
| Python modules | 32 |
| Database tables | 11 |
| Analysis factors | 10 |
| Betting models | 7 |
| Config sections | 15+ |
| Supported surfaces | 4 |
| Tournament categories | 8 |
| Typical DB size | 70-100 MB |
| Historical matches | 50,000+ |
| Players tracked | 5,000+ |

---

## License

Private project - not for distribution.
