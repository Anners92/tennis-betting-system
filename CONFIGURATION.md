# Tennis Betting System - Configuration Guide

All configuration is in `src/config.py`. This document explains each setting.

---

## Paths

| Setting | Default | Description |
|---------|---------|-------------|
| `BASE_DIR` | `<project>` (dev) or `C:/Users/Public/Documents/Tennis Betting System` (installed) | Root data directory |
| `DATA_DIR` | `BASE_DIR/data` | Database and data files |
| `OUTPUT_DIR` | `BASE_DIR/output` | Generated reports |
| `LOGS_DIR` | `BASE_DIR/logs` | Log files |
| `DB_PATH` | `DATA_DIR/tennis_betting.db` | SQLite database |

---

## Analysis Weights

Controls how much each factor affects win probability calculation.

```python
DEFAULT_ANALYSIS_WEIGHTS = {
    "form": 0.20,           # Recent match performance
    "surface": 0.15,        # Surface-specific win rate
    "ranking": 0.20,        # Current ATP/WTA ranking
    "h2h": 0.10,            # Head-to-head record
    "fatigue": 0.05,        # Rest days, workload
    "injury": 0.05,         # Injury status
    "opponent_quality": 0.10,  # Quality of recent opponents
    "recency": 0.08,        # How recent the form data is
    "recent_loss": 0.05,    # Penalty for recent losses
    "momentum": 0.02,       # Winning streak bonus
}
```

**Note:** Weights should sum to 1.0 (100%).

---

## Form Settings

```python
FORM_SETTINGS = {
    "default_matches": 10,      # Matches to analyze for form
    "min_matches": 5,           # Minimum for reliable form
    "max_matches": 20,          # Maximum to consider
    "recency_decay": 0.9,       # Older matches weighted less (exponential)
    "opponent_ranking_weight": 0.3,  # How much opponent strength affects score
}
```

---

## Opponent Quality Settings

```python
OPPONENT_QUALITY_SETTINGS = {
    "matches_to_analyze": 6,    # Recent matches to check
    "max_rank_for_bonus": 200,  # Only bonus for beating top 200
    "unranked_default": 200,    # Assume unranked = rank 200
}
```

---

## Recency Settings

How recent matches are weighted.

```python
RECENCY_SETTINGS = {
    "matches_to_analyze": 6,
    "weight_7d": 1.0,      # Full weight for last 7 days
    "weight_30d": 0.7,     # 70% for 7-30 days ago
    "weight_90d": 0.4,     # 40% for 30-90 days ago
    "weight_old": 0.2,     # 20% for 90+ days ago
}
```

---

## Recent Loss Settings

Penalty for coming off a loss.

```python
RECENT_LOSS_SETTINGS = {
    "penalty_3d": 0.10,       # 10% penalty for loss in last 3 days
    "penalty_7d": 0.05,       # 5% penalty for loss in last 7 days
    "five_set_penalty": 0.05, # Extra 5% for 5-set loss (fatigue)
}
```

---

## Momentum Settings

Bonus for winning streak.

```python
MOMENTUM_SETTINGS = {
    "window_days": 14,     # Look back 14 days
    "win_bonus": 0.03,     # 3% bonus per win on same surface
    "max_bonus": 0.10,     # Cap at 10% bonus
}
```

---

## Surface Settings

```python
SURFACE_SETTINGS = {
    "career_weight": 0.4,       # 40% weight to career stats
    "recent_weight": 0.6,       # 60% weight to recent (2 years)
    "recent_years": 2,          # Definition of "recent"
    "min_matches_reliable": 20, # Need 20+ matches for reliable stats
}
```

---

## Fatigue Settings

```python
FATIGUE_SETTINGS = {
    "optimal_rest_days": 3,           # Ideal rest between matches
    "rust_start_days": 7,             # Rust penalty starts after 7 days
    "max_rest_days": 14,              # Steep rust penalty after 14 days
    "overplay_window_14": 5,          # Concern if >5 matches in 14 days
    "overplay_window_30": 10,         # Concern if >10 matches in 30 days
    "difficulty_window_days": 7,      # Days to calculate difficulty
    "difficulty_min": 0.5,            # Walkover multiplier
    "difficulty_max": 3.0,            # Marathon 5-setter multiplier
    "difficulty_baseline_minutes": 60,# Normal match = 60 min
    "difficulty_max_minutes": 300,    # Cap at 5 hours
    "difficulty_baseline_sets": 2,    # Baseline for best-of-3
    "difficulty_overload_threshold": 6.0,  # 6 difficulty pts = concerning
}
```

---

## Kelly Staking Settings

Evidence-based stake sizing.

```python
KELLY_STAKING = {
    "unit_size_percent": 2.0,    # 1 unit = 2% of bankroll
    "kelly_fraction": 0.40,      # Use 40% of full Kelly (balanced)
    "exchange_commission": 0.02, # Betfair commission rate (2%)
    "min_odds": 1.70,            # Don't bet below 1.70 odds
    "min_units": 0.5,            # Minimum stake to place
    "max_units": 3.0,            # Maximum stake per bet
    "min_model_confidence": 0.50, # Minimum 50% model confidence

    "disagreement_penalty": {
        "minor": {"max_ratio": 1.5, "penalty": 1.0},    # Up to 1.5x market: full stake
        "moderate": {"max_ratio": 2.0, "penalty": 0.75}, # 1.5-2x: 75% stake
        "major": {"max_ratio": 3.0, "penalty": 0.50},    # 2-3x: 50% stake
        "extreme": {"max_ratio": 999, "penalty": 0.25},  # 3x+: 25% stake
    },
}
```

### Commission Rates

| Betfair Tier | Commission |
|--------------|------------|
| Basic | 2% (`0.02`) |
| Rewards | 5% (`0.05`) |
| Rewards+ | 8% (`0.08`) |

---

## Betting Settings

```python
BETTING_SETTINGS = {
    "min_ev_threshold": 0.05,    # Minimum 5% EV to suggest bet
    "high_ev_threshold": 0.15,   # 15%+ = "high value"
    "max_odds": 10.0,            # Ignore odds above 10.0
    "min_probability": 0.10,     # Ignore if <10% win probability
    "kelly_fraction": 0.25,      # Legacy setting
}
```

---

## Set Betting Settings

```python
SET_BETTING = {
    "bo3_scores": ["2-0", "2-1", "0-2", "1-2"],
    "bo5_scores": ["3-0", "3-1", "3-2", "0-3", "1-3", "2-3"],
    "grand_slams": [
        "Australian Open",
        "Roland Garros",
        "Wimbledon",
        "US Open"
    ],
}
```

---

## UI Colors

Dark mode theme colors.

```python
UI_COLORS = {
    # Backgrounds
    "bg_dark": "#0f172a",      # Main background
    "bg_medium": "#1e293b",    # Cards/panels
    "bg_light": "#334155",     # Inputs/hover
    "border": "#334155",

    # Text
    "text_primary": "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",

    # Actions
    "primary": "#3b82f6",      # Blue
    "success": "#22c55e",      # Green
    "warning": "#f59e0b",      # Amber
    "danger": "#ef4444",       # Red

    # Surfaces
    "surface_hard": "#3b82f6",
    "surface_clay": "#f97316",
    "surface_grass": "#22c55e",
    "surface_carpet": "#a855f7",
}
```

---

## Data Import Settings

```python
IMPORT_SETTINGS = {
    "start_year": 2000,    # Earliest year to import
    "end_year": 2025,      # Latest year to import
    "batch_size": 1000,    # DB insert batch size
}
```

---

## Scraper Settings

```python
SCRAPER_SETTINGS = {
    "atp_rankings_pages": 15,   # 15 pages × 100 = 1500 players
    "wta_rankings_pages": 15,
    "match_history_months": 12, # Scrape 12 months of matches
}
```

---

## Betfair Capture Settings

Controls for filtering Betfair odds capture.

```python
BETFAIR_CAPTURE = {
    "MIN_LIQUIDITY_GBP": 100,      # Minimum £100 available to back
    "MAX_ODDS_DISCREPANCY": 0.15,  # 15% max difference from Pinnacle
}
```

**MIN_LIQUIDITY_GBP:** Filters out thin markets with unreliable prices. Markets with less than £100 available are skipped.

**MAX_ODDS_DISCREPANCY:** When Pinnacle comparison is enabled, matches where Betfair odds are worse than Pinnacle by more than 15% are flagged with "SKIP".

---

## The Odds API Settings (Pinnacle Comparison)

Settings for comparing Betfair odds against sharp bookmaker (Pinnacle).

```python
ODDS_API = {
    "cache_duration_minutes": 15,  # Cache to preserve API quota
    "enabled": True,               # Toggle Pinnacle comparison
}
```

**API Quota:** Free tier allows 500 requests/month. The 15-minute cache helps preserve this quota.

**Comparison Logic:**
- **SKIP**: Betfair < Pinnacle by >15% (bad value)
- **CAUTION**: Betfair < Pinnacle by 7.5-15%
- **GOOD VALUE**: Betfair > Pinnacle (keep these bets)

---

## Betting Models (M1-M7)

Seven models for different betting strategies.

```python
BETTING_MODELS = {
    "M1": {"name": "All Bets", "criteria": "Every value bet"},
    "M2": {"name": "Tiered", "criteria": "Extreme odds + filtered middle"},
    "M3": {"name": "Moderate Edge", "criteria": "5-15% edge range"},
    "M4": {"name": "Favorites", "criteria": "Model probability >= 60%"},
    "M5": {"name": "Underdogs", "criteria": "Model probability < 45%"},
    "M6": {"name": "Large Edge", "criteria": "Edge >= 10%"},
    "M7": {"name": "Grind", "criteria": "3-8% edge + odds < 2.50"},
}
```

Each bet is tagged with applicable models (e.g., "M1,M4,M6").

---

## Constants

### Surfaces
```python
SURFACES = ["Hard", "Clay", "Grass", "Carpet"]
```

### Tournament Categories
```python
TOURNAMENT_CATEGORIES = [
    "Grand Slam",
    "Masters 1000",
    "ATP 500",
    "ATP 250",
    "ATP Finals",
    "Davis Cup",
    "Olympics",
    "Other"
]
```

### Match Rounds
```python
ROUNDS = ["F", "SF", "QF", "R16", "R32", "R64", "R128", "RR", "BR", "ER"]
```

### Injury Statuses
```python
INJURY_STATUS = [
    "Active",
    "Minor Concern",
    "Questionable",
    "Doubtful",
    "Out",
    "Returning",
]
```

---

## Modifying Configuration

1. Edit `src/config.py`
2. Save the file
3. Restart the application (changes take effect on restart)
4. If building installer, sync to `dist/TennisBettingSystem/config.py`
