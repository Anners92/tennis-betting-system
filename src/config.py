"""
Tennis Betting System - Configuration
Constants, surfaces, tournament categories, and analysis weights
"""

import os
import re
import sys
from pathlib import Path

# ============================================================================
# PATHS
# ============================================================================
# Handle PyInstaller frozen executable
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    # Install folder for program files
    INSTALL_DIR = Path(sys.executable).parent
    # Public Documents for data (writable by all users)
    BASE_DIR = Path("C:/Users/Public/Documents/Tennis Betting System")
else:
    # Running as script - use same data location as installed app
    INSTALL_DIR = Path(__file__).parent.parent
    BASE_DIR = Path("C:/Users/Public/Documents/Tennis Betting System")

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "tennis_betting.db"

# Ensure directories exist
BASE_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Copy seed database on first run (if installed app and no database exists)
SEED_DB_PATH = INSTALL_DIR / "data" / "tennis_betting.db"
if not DB_PATH.exists() and SEED_DB_PATH.exists():
    import shutil
    try:
        shutil.copy2(SEED_DB_PATH, DB_PATH)
        print(f"Copied seed database to {DB_PATH}")
    except Exception as e:
        print(f"Could not copy seed database: {e}")

# ============================================================================
# SURFACES
# ============================================================================
SURFACES = ["Hard", "Clay", "Grass", "Carpet"]

SURFACE_MAPPING = {
    "hard": "Hard",
    "clay": "Clay",
    "grass": "Grass",
    "carpet": "Carpet",
    "h": "Hard",
    "c": "Clay",
    "g": "Grass",
    "p": "Carpet",  # Some datasets use 'P' for carpet
}

# ============================================================================
# TOURNAMENT SURFACE DETECTION
# Comprehensive mapping to avoid surface detection bugs
# ============================================================================

# CLAY tournaments - specific names only (no bare 'clay' keyword)
CLAY_TOURNAMENTS = [
    # Grand Slam
    'roland garros', 'french open',
    # Masters 1000
    'monte carlo', 'madrid', 'rome', 'internazionali',
    # ATP 500
    'barcelona', 'hamburg', 'rio', 'rio de janeiro',
    # ATP 250
    'buenos aires', 'cordoba', 'santiago', 'sao paulo',
    'estoril', 'munich', 'geneva', 'lyon', 'bastad',
    'umag', 'kitzbuhel', 'gstaad', 'winston-salem', 'winston salem',
    'marrakech', 'houston', 'cagliari', 'parma', 'belgrade',
    'sardegna', 'tiriac', 'bucharest',
    # WTA Clay
    'charleston', 'strasbourg', 'rabat', 'bogota', 'prague',
    'warsaw', 'portoroz', 'palermo', 'lausanne', 'budapest',
    'birmingham wta',  # Note: Birmingham grass is different
    # Challenger Clay (South America, Southern Europe)
    'concepcion', 'santa cruz', 'campinas', 'santo domingo',
    'medellin', 'salinas', 'lima', 'cali', 'guayaquil',
    'san miguel de tucuman', 'punta del este', 'asuncion',
    'barletta', 'francavilla', 'santa margherita', 'perugia',
    'iasi', 'sibiu', 'split', 'zadar', 'todi', 'como',
    'prague challenger', 'braunschweig', 'heilbronn', 'aix-en-provence',
    'prostejov', 'liberec', 'szczecin', 'poznan', 'wroclaw',
]

# GRASS tournaments - ONLY during grass season (June-July)
# These are the ONLY grass tournaments worldwide
# IMPORTANT: Use specific names to avoid false matches (e.g., 'halle' matches 'challenger')
GRASS_TOURNAMENTS = [
    # Grand Slam
    'wimbledon',
    # ATP 500
    'queens', "queen's", 'queen\'s club',
    'atp halle', 'halle open', 'terra wortmann',  # Halle - be specific to avoid 'challenger' match
    # ATP 250
    's-hertogenbosch', 'hertogenbosch', 'rosmalen', 'libema open',
    'boss open',  # Stuttgart grass (June) - different from Stuttgart indoor
    'eastbourne', 'mallorca', 'newport',
    # WTA Grass
    'birmingham classic', 'rothesay classic birmingham',
    'nottingham', 'rothesay open nottingham',
    'berlin wta', 'ecotrans ladies',
    'bad homburg', 'bad homburg open',
]

# Indoor Hard tournaments (for reference - still "Hard" surface)
INDOOR_HARD_TOURNAMENTS = [
    'paris masters', 'paris-bercy', 'rolex paris',
    'vienna', 'basel', 'stockholm', 'antwerp', 'st petersburg',
    'metz', 'sofia', 'moselle', 'marseille', 'montpellier',
    'rotterdam', 'dallas', 'adelaide',
    # Many winter Challengers are indoor hard
    'quimper', 'oeiras', 'koblenz', 'loughborough', 'andria',
]


def _word_match(keyword: str, text: str) -> bool:
    """
    Check if keyword appears in text as a word (not as substring of another word).
    E.g., 'rome' should match 'Rome Masters' but not 'Jerome'.
    """
    import re
    # Use word boundaries for short keywords to avoid false matches
    # For multi-word keywords, simple 'in' check is fine
    if ' ' in keyword or len(keyword) > 6:
        return keyword in text
    # For short single words, use word boundary
    pattern = r'\b' + re.escape(keyword) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def normalize_tournament_name(name: str) -> str:
    """
    Normalize tournament name to match database format.

    Converts Betfair names to our standard format:
    - Strips year suffixes (2024, 2025, 2026, etc.)
    - Converts "Ladies/Men's X" to just "X" for Grand Slams
    - Strips trailing whitespace

    Args:
        name: Tournament name from Betfair (e.g., "Concepcion Challenger 2026")

    Returns:
        Normalized name (e.g., "Concepcion Challenger")
    """
    if not name:
        return name

    # Strip year suffixes (2020-2029)
    result = re.sub(r'\s+20[2-3]\d$', '', name)

    # Handle Grand Slam prefixes
    result = re.sub(r"^Ladies\s+", "", result)
    result = re.sub(r"^Men's\s+", "", result)
    result = re.sub(r"^Women's\s+", "", result)

    return result.strip()


def get_tournament_surface(tournament_name: str, date_str: str = None) -> str:
    """
    Determine tournament surface from name and optionally date.

    This is the SINGLE SOURCE OF TRUTH for surface detection.
    All other files should use this function.

    Args:
        tournament_name: Tournament name (e.g., "Oeiras Challenger 2026")
        date_str: Optional date string (YYYY-MM-DD) to help with seasonal detection

    Returns:
        Surface: "Hard", "Clay", or "Grass"
    """
    if not tournament_name:
        return "Hard"

    name = tournament_name.lower()

    # Check for explicit surface in name (from Tennis Explorer/databases)
    # These are safe - they're from authoritative sources
    if ' - clay' in name or '(clay)' in name:
        return 'Clay'
    if ' - grass' in name or '(grass)' in name:
        return 'Grass'
    if ' - hard' in name or '(hard)' in name or ' - indoor' in name:
        return 'Hard'

    # Seasonal check FIRST: Grass only happens June-July
    # If it's NOT grass season, don't even check grass keywords
    is_grass_season = False
    if date_str:
        try:
            month = int(date_str[5:7])  # Extract month from YYYY-MM-DD
            is_grass_season = month in [6, 7]
        except (ValueError, IndexError):
            is_grass_season = False

    # Check against known clay tournaments
    for clay_tourney in CLAY_TOURNAMENTS:
        if _word_match(clay_tourney, name):
            return 'Clay'

    # Only check grass tournaments during grass season (June-July)
    if is_grass_season:
        for grass_tourney in GRASS_TOURNAMENTS:
            if _word_match(grass_tourney, name):
                return 'Grass'

    # Default to Hard (most common surface, especially for Challengers)
    return 'Hard'

# ============================================================================
# TOURNAMENT CATEGORIES
# ============================================================================
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

# Tournament level mapping from Tennis Abstract data
TOURNEY_LEVEL_MAPPING = {
    "G": "Grand Slam",
    "M": "Masters 1000",
    "A": "ATP 500",
    "B": "ATP 250",
    "F": "ATP Finals",
    "D": "Davis Cup",
    "O": "Olympics",
    "C": "Challenger",
}


def get_tour_level(tournament_name: str) -> str:
    """
    Categorize a tournament name into tour level for display.
    Returns full names: Grand Slam, ATP, WTA, Challenger, ITF
    """
    if not tournament_name:
        return "Unknown"

    name = tournament_name.lower()

    # Grand Slams
    if any(gs in name for gs in ['australian open', 'roland garros', 'french open',
                                   'wimbledon', 'us open', 'u.s. open']):
        return "Grand Slam"

    # ATP Tour events
    if 'atp' in name or 'masters' in name:
        return "ATP"

    # WTA Tour events
    if 'wta' in name or "women's" in name or 'ladies' in name:
        return "WTA"

    # Challenger events
    if 'challenger' in name or 'ch ' in name:
        return "Challenger"

    # ITF events (futures, etc.)
    if 'itf' in name or 'futures' in name or '$' in name:
        return "ITF"

    # Default - check for common patterns
    if 'men' in name:
        return "ATP"
    if 'women' in name:
        return "WTA"

    return "Unknown"


def calculate_bet_model(our_probability: float, implied_probability: float, tournament: str, odds: float = None, factor_scores: dict = None) -> str:
    """
    Calculate which model(s) a bet qualifies for.

    Model 3: Moderate edge bets (5-15% edge) - "Sharp" zone
    Model 4: Favorites only (our probability >= 60%)
    Model 7: Small edge (3-8%) + short odds (< 2.50) - "Grind"
    Model 8: Profitable baseline - Our prob >= 55% AND odds < 2.50

    Returns: "Model 3", "Model 3, Model 4", etc.
    """
    models = []

    # Calculate edge
    edge = our_probability - implied_probability if implied_probability else 0

    # Model 3 (Sharp): Moderate edge zone (5-15%)
    if 0.05 <= edge <= 0.15:
        models.append("Model 3")

    # Model 4 (Favorites): Our probability >= 60%
    if our_probability >= 0.60:
        models.append("Model 4")

    # Model 7 (Grind): Small edge (3-8%) + short odds (< 2.50)
    if odds and 0.03 <= edge <= 0.08 and odds < 2.50:
        models.append("Model 7")

    # Model 8 (Profitable Baseline): Our prob >= 55% AND odds < 2.50
    if odds and our_probability >= 0.55 and odds < 2.50:
        models.append("Model 8")

    return ", ".join(models) if models else "None"


# ============================================================================
# MATCH ROUNDS
# ============================================================================
ROUNDS = [
    "F",    # Final
    "SF",   # Semi-Final
    "QF",   # Quarter-Final
    "R16",  # Round of 16
    "R32",  # Round of 32
    "R64",  # Round of 64
    "R128", # Round of 128
    "RR",   # Round Robin
    "BR",   # Bronze Medal Match
    "ER",   # Early Rounds
]

ROUND_NAMES = {
    "F": "Final",
    "SF": "Semi-Final",
    "QF": "Quarter-Final",
    "R16": "Round of 16",
    "R32": "Round of 32",
    "R64": "Round of 64",
    "R128": "Round of 128",
    "RR": "Round Robin",
    "BR": "Bronze Medal",
    "ER": "Early Round",
}

# ============================================================================
# ANALYSIS WEIGHTS (Configurable) - Experimental v2.0
# Removed redundant factors: opponent_quality (absorbed by form), recency (in form decay)
# ============================================================================
DEFAULT_ANALYSIS_WEIGHTS = {
    "form": 0.25,           # Increased - absorbs opponent quality signal
    "surface": 0.20,        # Increased - likely edge source vs market
    "ranking": 0.20,        # Solid anchor
    "h2h": 0.05,            # Reduced - often noise, market prices it well
    "fatigue": 0.15,        # Increased - market underweights this
    "injury": 0.05,         # Keep
    "opponent_quality": 0.00,  # REMOVED - redundant with form
    "recency": 0.00,           # REMOVED - already in form's decay
    "recent_loss": 0.08,    # Increased - psychological edge
    "momentum": 0.02,       # Keep small
}

# ============================================================================
# MODEL WEIGHT PROFILES (Simplified v2.0)
# Based on experimental analysis - 8 active factors only
# ============================================================================
MODEL_WEIGHT_PROFILES = {
    "Default": {
        # The new default weights - removes redundant factors
        "form": 0.25, "surface": 0.20, "ranking": 0.20, "h2h": 0.05,
        "fatigue": 0.15, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02
    },
    "Form Focus": {
        # 40% form-focused
        "form": 0.40, "surface": 0.15, "ranking": 0.15, "h2h": 0.05,
        "fatigue": 0.10, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02
    },
    "Surface Focus": {
        # 35% surface-focused
        "form": 0.20, "surface": 0.35, "ranking": 0.15, "h2h": 0.05,
        "fatigue": 0.10, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02
    },
    "Ranking Focus": {
        # 35% ranking-focused
        "form": 0.20, "surface": 0.15, "ranking": 0.35, "h2h": 0.05,
        "fatigue": 0.10, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02
    },
    "Fatigue Focus": {
        # 30% fatigue-focused - market blind spot
        "form": 0.20, "surface": 0.15, "ranking": 0.15, "h2h": 0.05,
        "fatigue": 0.30, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02
    },
    "Psychology Focus": {
        # Emphasizes recent_loss and momentum
        "form": 0.25, "surface": 0.15, "ranking": 0.15, "h2h": 0.05,
        "fatigue": 0.10, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.15, "momentum": 0.10
    },
}

# ============================================================================
# FORM CALCULATION SETTINGS
# ============================================================================
FORM_SETTINGS = {
    "default_matches": 10,       # Default number of matches for form calculation
    "min_matches": 5,            # Minimum matches for form calculation
    "max_matches": 20,           # Maximum matches for form calculation
    "recency_decay": 0.9,        # Decay factor for older matches (exponential)
    "opponent_ranking_weight": 0.3,  # How much opponent strength affects form score
}

# ============================================================================
# NEW FACTOR SETTINGS (Model Analysis Additions)
# ============================================================================
OPPONENT_QUALITY_SETTINGS = {
    "matches_to_analyze": 6,     # Number of recent matches to analyze
    "max_rank_for_bonus": 200,   # Rankings above this get no quality bonus
    "unranked_default": 200,     # Default rank for unranked opponents
}

RECENCY_SETTINGS = {
    "matches_to_analyze": 6,     # Number of recent matches to analyze
    "weight_7d": 1.0,            # Weight for matches in last 7 days
    "weight_30d": 0.7,           # Weight for matches 7-30 days ago
    "weight_90d": 0.4,           # Weight for matches 30-90 days ago
    "weight_old": 0.2,           # Weight for matches 90+ days ago
}

RECENT_LOSS_SETTINGS = {
    "penalty_3d": 0.10,          # Penalty for loss in last 3 days
    "penalty_7d": 0.05,          # Penalty for loss in last 7 days
    "five_set_penalty": 0.05,    # Additional penalty for 5-set loss (fatigue/demoralization)
}

MOMENTUM_SETTINGS = {
    "window_days": 14,           # Days to look back for momentum
    "win_bonus": 0.03,           # Bonus per win on same surface
    "max_bonus": 0.10,           # Maximum momentum bonus
}

# ============================================================================
# SURFACE STATS SETTINGS
# ============================================================================
SURFACE_SETTINGS = {
    "career_weight": 0.4,        # Weight for career surface stats
    "recent_weight": 0.6,        # Weight for recent (2 years) surface stats
    "recent_years": 2,           # Years to consider as "recent"
    "min_matches_reliable": 20,  # Minimum matches for reliable surface stats
}

# ============================================================================
# FATIGUE SETTINGS
# ============================================================================
FATIGUE_SETTINGS = {
    "optimal_rest_days": 3,      # Optimal days between matches
    "rust_start_days": 7,        # Slight rust penalty begins after this many days
    "max_rest_days": 14,         # Beyond this, steeper rust penalty
    "overplay_window_14": 5,     # Concerning if > this many matches in 14 days
    "overplay_window_30": 10,    # Concerning if > this many matches in 30 days
    # Match difficulty settings (affects workload calculation)
    "difficulty_window_days": 7,         # Days to look back for difficulty impact
    "difficulty_min": 0.5,               # Walkover/retirement multiplier
    "difficulty_max": 3.0,               # Marathon 5-setter multiplier
    "difficulty_baseline_minutes": 60,   # "Normal" match duration (2-0 in ~60 min)
    "difficulty_max_minutes": 300,       # Marathon duration cap (5 hours)
    "difficulty_baseline_sets": 2,       # Baseline sets for best-of-3
    "difficulty_overload_threshold": 6.0,  # Difficulty points in 7 days = concerning
}

# ============================================================================
# BETTING SETTINGS
# ============================================================================
BETTING_SETTINGS = {
    "min_ev_threshold": 0.02,    # Minimum expected value (2%) - lowered to maximize volume
    "high_ev_threshold": 0.10,   # High value threshold (10%)
    "max_odds": 10.0,            # Maximum odds to consider
    "min_probability": 0.10,     # Minimum win probability to consider
    "kelly_fraction": 0.25,      # Fraction of Kelly Criterion to use (legacy)
}

# ============================================================================
# KELLY STAKING SETTINGS (Evidence-based approach from professional literature)
# ============================================================================
# Kelly-based staking with market skepticism. See STAKING_FRAMEWORK.md for details.
# Formula: Final Stake = Kelly Stake × Kelly Fraction × Disagreement Penalty × Odds Multiplier
KELLY_STAKING = {
    # Unit size as percentage of bankroll (used for converting Kelly % to units)
    "unit_size_percent": 2.0,    # 2% of bankroll per unit

    # Kelly fraction - what portion of full Kelly to use
    # Full Kelly is mathematically optimal but too aggressive in practice
    # Quarter (0.25) = conservative, Half (0.50) = aggressive, 0.40 = balanced
    "kelly_fraction": 0.50,

    # Betfair exchange commission rate (applied to winnings)
    # Basic package: 2%, Rewards: 5%, Rewards+: 8%
    "exchange_commission": 0.02,

    # Minimum odds to consider - lowered to allow more bets
    "min_odds": 1.30,

    # Minimum units to place a bet - lowered to allow more bets
    "min_units": 0.25,

    # Maximum units per bet (safety cap)
    "max_units": 3.0,

    # Market disagreement penalty thresholds
    # When our probability is much higher than implied, reduce stake but STILL BET
    # We want volume - let Kelly naturally size bets smaller for lower edges
    # prob_ratio = our_probability / implied_probability
    "disagreement_penalty": {
        "minor": {               # Minor disagreement - trust model
            "max_ratio": 1.50,   # Up to 1.5x market probability
            "penalty": 1.0,      # Full stake
        },
        "moderate": {            # Moderate disagreement - reduce stake
            "max_ratio": 2.0,    # 1.5x - 2.0x market probability
            "penalty": 0.75,     # 75% of calculated stake
        },
        "major": {               # Major disagreement - still bet but smaller
            "max_ratio": 999,    # 2.0x+ market probability
            "penalty": 0.50,     # 50% stake - still betting to build sample
        },
    },

    # Challenger-specific settings - DISABLED for volume
    # Need 1000+ bets before drawing conclusions about tour levels
    "challenger_settings": {
        "enabled": False,        # Disabled to maximize volume
        "max_disagreement_ratio": 999,  # No restriction
    },

    # Confidence threshold - model confidence affects stake
    "min_model_confidence": 0.30,  # Lowered to 30% for more volume

    # Odds range weighting - DISABLED for volume
    # Need 1000+ bets before drawing conclusions about odds ranges
    "odds_range_weighting": {
        "sweet_spot_min": 1.01,  # Effectively disabled
        "sweet_spot_max": 99.0,  # Effectively disabled
        "outside_multiplier": 1.0,  # No penalty - bet all odds ranges equally
    },

    # Market blend - weight market probability into model
    # Analysis showed model is overconfident, market is smarter
    "market_blend": {
        "enabled": True,
        "market_weight": 0.30,   # 30% market, 70% model
    },

    # Probability calibration - shrinkage method
    # Based on 60 settled bets: model predicts 53.5% avg but wins only 31.7%
    # Model is ~1.7x overconfident - we shrink probabilities toward 50%
    # This maintains bet volume while giving more realistic probability estimates
    "calibration": {
        "enabled": True,
        "type": "shrinkage",     # "shrinkage", "polynomial", or "linear"
        # Shrinkage factor: how much to pull toward 50%
        # 0.5 = aggressive shrinkage (60% -> 55%, 70% -> 60%)
        # 0.7 = moderate shrinkage (60% -> 57%, 70% -> 64%)
        # 1.0 = no shrinkage (raw model output)
        "shrinkage_factor": 0.5,
        # Results from shrinkage=0.5:
        # 40% model -> 45% calibrated
        # 50% model -> 50% calibrated
        # 60% model -> 55% calibrated
        # 70% model -> 60% calibrated
        # 80% model -> 65% calibrated
        # Legacy polynomial settings (if type="polynomial")
        "poly_a": 7.5566,
        "poly_b": -7.3102,
        "poly_c": 1.9932,
        # Legacy linear settings (if type="linear")
        "multiplier": 0.70,
        "offset": 0.15,
    },
}

# Legacy alias for backwards compatibility
UNIT_STAKING = KELLY_STAKING

# ============================================================================
# SET BETTING SETTINGS
# ============================================================================
SET_BETTING = {
    # Best of 3 possible scores
    "bo3_scores": ["2-0", "2-1", "0-2", "1-2"],
    # Best of 5 possible scores (Grand Slams)
    "bo5_scores": ["3-0", "3-1", "3-2", "0-3", "1-3", "2-3"],
    # Grand Slam tournaments (best of 5)
    "grand_slams": [
        "Australian Open",
        "Roland Garros",
        "Wimbledon",
        "US Open"
    ],
}

# ============================================================================
# UI SETTINGS (Premium Dark Mode)
# ============================================================================
UI_COLORS = {
    # Backgrounds
    "bg_dark": "#0f172a",       # Deep slate background
    "bg_medium": "#1e293b",     # Slate-800 for cards/panels
    "bg_light": "#334155",      # Slate-700 for inputs/hover
    "bg_card": "#1e293b",       # Same as bg_medium for consistency
    "border": "#334155",        # Subtle border color

    # Text
    "text_primary": "#f1f5f9",  # Slate-100
    "text_secondary": "#94a3b8", # Slate-400
    "text_muted": "#64748b",    # Slate-500

    # Brand & Actions
    "primary": "#3b82f6",       # Electric Blue - primary brand color
    "accent": "#3b82f6",        # Same as primary for consistency
    "success": "#22c55e",       # Green
    "warning": "#f59e0b",       # Amber
    "danger": "#ef4444",        # Red

    # Surface colors
    "surface_hard": "#3b82f6",
    "surface_clay": "#f97316",
    "surface_grass": "#22c55e",
    "surface_carpet": "#a855f7",

    # Player-specific colors
    "player1": "#3b82f6",       # Blue for Player 1
    "player2": "#eab308",       # Yellow for Player 2
}

# ============================================================================
# DATA IMPORT SETTINGS
# ============================================================================
IMPORT_SETTINGS = {
    "start_year": 2000,          # Earliest year to import
    "end_year": 2025,            # Latest year to import
    "batch_size": 1000,          # Batch size for database inserts
}

# ============================================================================
# PLAYER HAND MAPPING
# ============================================================================
HAND_MAPPING = {
    "R": "Right",
    "L": "Left",
    "U": "Unknown",
    "A": "Ambidextrous",
}

# ============================================================================
# INJURY STATUS
# ============================================================================
INJURY_STATUS = [
    "Active",           # Fully fit
    "Minor Concern",    # Minor issue, likely to play
    "Questionable",     # May or may not play
    "Doubtful",        # Unlikely to play
    "Out",             # Confirmed out
    "Returning",       # Coming back from injury
]

# ============================================================================
# TENNIS EXPLORER SCRAPER (Primary Data Source)
# ============================================================================
# All match data comes from Tennis Explorer via the GitHub scraper
# GitHub repo: https://github.com/Anners92/tennisdata
TENNIS_EXPLORER_DATA_URL = "https://github.com/Anners92/tennisdata/raw/main/tennis_data.db.gz"

# Scraper settings
SCRAPER_SETTINGS = {
    "atp_rankings_pages": 15,   # 100 players per page = 1500 ATP players
    "wta_rankings_pages": 15,   # 100 players per page = 1500 WTA players
    "match_history_months": 12, # Months of match history to scrape per player
}
