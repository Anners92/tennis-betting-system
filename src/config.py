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
elif os.environ.get('TENNIS_DATA_DIR'):
    # Cloud/CI environment: use environment variable for data paths
    INSTALL_DIR = Path(__file__).parent.parent
    BASE_DIR = Path(os.environ['TENNIS_DATA_DIR'])
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

    # Odds floor - odds below 1.70 are not considered value
    min_odds_floor = 1.70
    if odds and odds < min_odds_floor:
        return "None"

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


def _get_te_recent_matches(db_name: str, db_connection, days: int = 60) -> tuple:
    """
    Scrape Tennis Explorer to get actual recent match count for a player.
    Returns (match_count, played_this_month, te_url) or (None, None, None) if unable to fetch.
    """
    import urllib.request
    import re
    from datetime import datetime, timedelta

    try:
        cursor = db_connection.cursor()
        cursor.execute('SELECT tennis_explorer_url FROM players WHERE name = ?', (db_name,))
        row = cursor.fetchone()

        if not row or not row[0]:
            return None, None, None

        te_url = row[0]

        # Fetch the page
        req = urllib.request.Request(te_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')

        # Count matches in 2026 (current year)
        # Tennis Explorer format: dates like "27.01." or "27.01.26"
        current_year = datetime.now().year
        current_month = datetime.now().month
        cutoff_date = datetime.now() - timedelta(days=days)

        # Look for match rows - they contain dates in format DD.MM.
        match_count = 0
        played_this_month = False

        # Pattern for dates like "14.01." or "27.01."
        date_pattern = re.compile(r'(\d{1,2})\.(\d{1,2})\.')

        # Find all dates in the page
        for match in date_pattern.finditer(html):
            day, month = int(match.group(1)), int(match.group(2))
            try:
                # Assume current year for dates in first part of year
                match_date = datetime(current_year, month, day)
                if match_date >= cutoff_date:
                    match_count += 1
                    if month == current_month:
                        played_this_month = True
            except ValueError:
                continue

        # Divide by 3 because each match appears multiple times (date shown in multiple places)
        # This is approximate - Tennis Explorer shows date in multiple places per match
        match_count = max(1, match_count // 3) if match_count > 0 else 0

        return match_count, played_this_month, te_url

    except Exception as e:
        return None, None, None


def _get_mapped_player_name(betfair_name: str, db_connection) -> str:
    """
    Convert a Betfair player name to the database name using name_mappings.json.
    Returns the database name if a mapping exists, otherwise returns the original name.
    """
    if not betfair_name:
        return betfair_name

    try:
        import json
        # Load name mappings
        mappings_path = INSTALL_DIR / "data" / "name_mappings.json"
        if not mappings_path.exists():
            # Try alternate location for dev
            mappings_path = Path(__file__).parent.parent / "data" / "name_mappings.json"

        if mappings_path.exists():
            with open(mappings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                mappings = data.get('mappings', {})

                if betfair_name in mappings:
                    mapped_value = mappings[betfair_name]

                    # If mapped to an integer ID, look up the player name
                    if isinstance(mapped_value, int):
                        cursor = db_connection.cursor()
                        cursor.execute('SELECT name FROM players WHERE id = ?', (mapped_value,))
                        row = cursor.fetchone()
                        if row:
                            return row[0]
                    else:
                        # Mapped to a name string
                        return mapped_value
    except Exception:
        pass

    return betfair_name


def check_data_quality_for_stake(player1_name: str, player2_name: str, stake: float,
                                  db_connection=None, selection_name: str = None) -> dict:
    """
    Check data quality for bets - BLOCKS bets if players have insufficient data.

    For HIGH STAKES (2u+), applies STRONGER justification requirements:
    - Both players need 5+ matches (not just 3+)
    - Selection's 2026 form must not be 20%+ worse than opponent
    - This ensures we're not betting purely on ranking against form

    Returns dict with:
        - 'passed': bool - True if data quality is acceptable
        - 'warnings': list - Any warnings about data quality
        - 'recommended_stake': float - Original stake (not modified)
    """
    result = {
        'passed': True,
        'warnings': [],
        'recommended_stake': stake
    }

    if db_connection is None:
        return result

    try:
        from datetime import datetime, timedelta

        cursor = db_connection.cursor()
        cutoff_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        year_start = datetime.now().strftime('%Y') + '-01-01'

        # Determine minimum matches required based on stake
        is_high_stake = stake >= 2.0
        min_matches = 5 if is_high_stake else 3

        # Map Betfair names to database names
        db_player1 = _get_mapped_player_name(player1_name, db_connection)
        db_player2 = _get_mapped_player_name(player2_name, db_connection)
        db_selection = _get_mapped_player_name(selection_name, db_connection) if selection_name else None

        # Create mapping from original to database names for warnings
        name_map = {
            player1_name: db_player1,
            player2_name: db_player2
        }
        if selection_name:
            name_map[selection_name] = db_selection

        # Store player stats for form comparison
        player_stats = {}

        for orig_name, db_name in [(player1_name, db_player1), (player2_name, db_player2)]:
            if not db_name:
                continue

            # Use EXACT name match - not LIKE which can match wrong players
            cursor.execute('''
                SELECT COUNT(*) FROM matches
                WHERE (winner_name = ? OR loser_name = ?)
                AND date >= ?
            ''', (db_name, db_name, cutoff_date))
            recent_matches = cursor.fetchone()[0]

            if recent_matches < min_matches:
                # Database shows insufficient matches - verify on Tennis Explorer
                te_matches, played_this_month, te_url = _get_te_recent_matches(db_name, db_connection, days=60)

                if te_matches is not None and te_matches >= min_matches:
                    # Tennis Explorer shows enough matches - database is stale, PASS
                    result['warnings'].append(
                        f"{orig_name}: DB shows {recent_matches} matches but TE shows ~{te_matches} (PASSED via TE: {te_url})"
                    )
                    # Don't set passed = False - TE verification passed
                elif te_matches is not None and played_this_month:
                    # TE shows insufficient matches BUT player has played this month
                    # PASS with stake reduction instead of blocking
                    result['warnings'].append(
                        f"{orig_name}: Only {te_matches} matches on TE (need {min_matches}+) but PLAYED THIS MONTH - reduce stake 50% - {te_url}"
                    )
                    # Apply 50% stake reduction
                    result['recommended_stake'] = round(result['recommended_stake'] * 0.5, 2)
                    result['stake_reduced'] = True
                    # Don't set passed = False - allow bet with reduced stake
                elif te_matches is not None:
                    # TE shows insufficient AND hasn't played this month - BLOCK
                    result['warnings'].append(
                        f"{orig_name}: Only {te_matches} matches on TE, hasn't played this month (need {min_matches}+ for {stake}u bet) - {te_url}"
                    )
                    result['passed'] = False
                else:
                    # Couldn't fetch TE - fall back to database result
                    result['warnings'].append(
                        f"{orig_name}: Only {recent_matches} matches in DB (need {min_matches}+), TE verification failed"
                    )
                    result['passed'] = False

            # For high stakes, also get 2026 win/loss record for form comparison
            if is_high_stake:
                cursor.execute('''
                    SELECT
                        SUM(CASE WHEN winner_name = ? THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN loser_name = ? THEN 1 ELSE 0 END) as losses
                    FROM matches
                    WHERE (winner_name = ? OR loser_name = ?)
                    AND date >= ?
                ''', (db_name, db_name, db_name, db_name, year_start))
                row = cursor.fetchone()
                wins = row[0] or 0
                losses = row[1] or 0
                total = wins + losses
                win_rate = (wins / total * 100) if total > 0 else 0
                player_stats[orig_name] = {'wins': wins, 'losses': losses, 'win_rate': win_rate, 'total': total}

        # For high stakes: Check form comparison
        if is_high_stake and selection_name and len(player_stats) == 2:
            # Determine which player is selection and which is opponent
            opponent_name = player1_name if selection_name == player2_name else player2_name

            if selection_name in player_stats and opponent_name in player_stats:
                sel_stats = player_stats[selection_name]
                opp_stats = player_stats[opponent_name]

                # Both need minimum matches for form comparison to be meaningful
                if sel_stats['total'] >= 3 and opp_stats['total'] >= 3:
                    form_diff = sel_stats['win_rate'] - opp_stats['win_rate']

                    # Block if selection's form is 15%+ worse than opponent
                    if form_diff <= -15:
                        result['warnings'].append(
                            f"FORM CHECK FAILED: {selection_name} ({sel_stats['wins']}W-{sel_stats['losses']}L = {sel_stats['win_rate']:.0f}%) "
                            f"vs {opponent_name} ({opp_stats['wins']}W-{opp_stats['losses']}L = {opp_stats['win_rate']:.0f}%) - "
                            f"Selection's form is {abs(form_diff):.0f}% worse"
                        )
                        result['passed'] = False

    except Exception as e:
        result['warnings'].append(f"Data quality check error: {e}")

    return result


def adjust_stake_for_confidence(base_stake: float, factor_analysis: dict) -> dict:
    """
    Adjust stake based on data confidence from factor analysis.

    High-stake bets (2u+) require multiple factors to support the bet.
    If key factors have missing data, stake is reduced.

    Returns dict with:
        - 'adjusted_stake': float - The recommended stake after adjustment
        - 'original_stake': float - The original calculated stake
        - 'confidence_multiplier': float - The multiplier applied (0.5 to 1.0)
        - 'adjustments': list - Reasons for any reductions
    """
    result = {
        'adjusted_stake': base_stake,
        'original_stake': base_stake,
        'confidence_multiplier': 1.0,
        'adjustments': []
    }

    # Only apply adjustments to 2u+ stakes
    if base_stake < 2.0:
        return result

    if not factor_analysis or 'factors' not in factor_analysis:
        return result

    factors = factor_analysis.get('factors', {})
    multiplier = 1.0

    # Check surface data
    surface = factors.get('surface', {})
    p1_surface_data = surface.get('p1', {}).get('has_data', False)
    p2_surface_data = surface.get('p2', {}).get('has_data', False)

    if not p1_surface_data and not p2_surface_data:
        multiplier -= 0.20
        result['adjustments'].append('No surface data for either player (-20%)')
    elif not p1_surface_data or not p2_surface_data:
        multiplier -= 0.10
        result['adjustments'].append('Surface data missing for one player (-10%)')

    # Check H2H data
    h2h = factors.get('h2h', {})
    h2h_matches = h2h.get('data', {}).get('total_matches', 0)

    if h2h_matches == 0:
        multiplier -= 0.10
        result['adjustments'].append('No H2H history (-10%)')

    # Check form data quality (matches analyzed)
    form = factors.get('form', {})
    p1_form_matches = form.get('p1', {}).get('matches', 0)
    p2_form_matches = form.get('p2', {}).get('matches', 0)

    if p1_form_matches < 5 or p2_form_matches < 5:
        multiplier -= 0.15
        result['adjustments'].append(f'Limited form data (P1: {p1_form_matches}, P2: {p2_form_matches} matches) (-15%)')

    # Check if ranking is the dominant factor (>40% of weighted advantage)
    ranking = factors.get('ranking', {})
    ranking_advantage = abs(ranking.get('advantage', 0))
    ranking_weight = ranking.get('weight', 0.2)

    weighted_advantage = abs(factor_analysis.get('weighted_advantage', 0))
    if weighted_advantage > 0:
        ranking_contribution = (ranking_advantage * ranking_weight) / weighted_advantage
        if ranking_contribution > 0.40:
            multiplier -= 0.10
            result['adjustments'].append(f'Ranking dominates ({ranking_contribution*100:.0f}% of edge) (-10%)')

    # Floor at 0.5 (never reduce by more than half)
    multiplier = max(0.5, multiplier)

    # Calculate adjusted stake
    adjusted = base_stake * multiplier

    # Round to nearest 0.5
    adjusted = round(adjusted * 2) / 2

    # Minimum stake of 0.5
    adjusted = max(0.5, adjusted)

    result['adjusted_stake'] = adjusted
    result['confidence_multiplier'] = multiplier

    return result


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
# ANALYSIS WEIGHTS (Configurable) - v2.2 (9 active factors)
# Added performance_elo: actual results-based Elo from last 12 months
# Weight taken from ranking (-0.07) and form (-0.05) since perf_elo overlaps both
# ============================================================================
DEFAULT_ANALYSIS_WEIGHTS = {
    "form": 0.20,              # Reduced from 0.25 - perf_elo captures some form signal
    "surface": 0.20,           # Unchanged - likely edge source vs market
    "ranking": 0.13,           # Reduced from 0.20 - perf_elo is better ranking signal
    "h2h": 0.05,               # Unchanged
    "fatigue": 0.15,           # Unchanged - market underweights this
    "injury": 0.05,            # Unchanged
    "opponent_quality": 0.00,  # REMOVED - redundant with form
    "recency": 0.00,           # REMOVED - already in form's decay
    "recent_loss": 0.08,       # Unchanged - psychological edge
    "momentum": 0.02,          # Unchanged
    "performance_elo": 0.12,   # NEW - actual results vs ranking expectation
}

# ============================================================================
# MODEL WEIGHT PROFILES (v2.2 - 9 active factors)
# All profiles include performance_elo factor
# ============================================================================
MODEL_WEIGHT_PROFILES = {
    "Default": {
        "form": 0.20, "surface": 0.20, "ranking": 0.13, "h2h": 0.05,
        "fatigue": 0.15, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02,
        "performance_elo": 0.12
    },
    "Form Focus": {
        "form": 0.35, "surface": 0.15, "ranking": 0.10, "h2h": 0.05,
        "fatigue": 0.10, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02,
        "performance_elo": 0.10
    },
    "Surface Focus": {
        "form": 0.15, "surface": 0.35, "ranking": 0.10, "h2h": 0.05,
        "fatigue": 0.10, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02,
        "performance_elo": 0.10
    },
    "Ranking Focus": {
        "form": 0.15, "surface": 0.15, "ranking": 0.25, "h2h": 0.05,
        "fatigue": 0.10, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02,
        "performance_elo": 0.15
    },
    "Fatigue Focus": {
        "form": 0.15, "surface": 0.15, "ranking": 0.10, "h2h": 0.05,
        "fatigue": 0.30, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.08, "momentum": 0.02,
        "performance_elo": 0.10
    },
    "Psychology Focus": {
        "form": 0.20, "surface": 0.15, "ranking": 0.10, "h2h": 0.05,
        "fatigue": 0.10, "injury": 0.05, "opponent_quality": 0.00,
        "recency": 0.00, "recent_loss": 0.15, "momentum": 0.10,
        "performance_elo": 0.10
    },
}

# ============================================================================
# FORM CALCULATION SETTINGS
# ============================================================================
FORM_SETTINGS = {
    "default_matches": 20,       # Default number of matches for form calculation
    "min_matches": 5,            # Minimum matches for form calculation
    "max_matches": 20,           # Maximum matches for form calculation
    "recency_decay": 0.9,        # Decay factor for older matches (exponential)
    "max_form_advantage": 0.10,  # Diminishing returns cap (tanh) on form advantage
    "max_stability_adjustment": 0.20,  # Cap for loss quality adjustment (tanh)
    # Loss quality consistency dampening — reduces stability adjustment when
    # a player's losses are scattered (some to top 100, some to #400+)
    "loss_consistency_baseline": 150,     # StdDev (Elo) at which consistency ~= 0.50
    "loss_consistency_steepness": 2.0,    # Exponent controlling decay rate
    "loss_consistency_min_losses": 2,     # Min losses per player to compute std dev
}

# Tournament level weight for form calculation.
# Higher-level tournament results carry more weight in the form score average.
TOURNAMENT_FORM_WEIGHT = {
    "Grand Slam": 1.3,
    "ATP": 1.15,
    "WTA": 1.1,
    "Challenger": 1.0,
    "ITF": 0.85,
    "Unknown": 1.0,
}

# ============================================================================
# PERFORMANCE ELO SETTINGS
# Rolling 12-month Elo calculated from actual match results.
# K-factor determines how much a single result shifts the rating.
# Higher K for bigger tournaments = those results matter more.
# ============================================================================
PERFORMANCE_ELO_SETTINGS = {
    "rolling_months": 12,
    "default_elo": 1200,
    "k_factors": {
        "Grand Slam": 48,
        "ATP": 32,
        "WTA": 28,
        "Challenger": 24,
        "ITF": 20,
        "Unknown": 24,
    },
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
# BREAKOUT DETECTION SETTINGS
# ============================================================================
# Detects when a player's recent results dramatically outperform their ranking,
# signaling a genuine level shift ("breakout") rather than random variance.
BREAKOUT_SETTINGS = {
    "min_ranking": 150,            # Top-150 don't qualify (ranking already accurate)
    "peak_breakout_age": 22,       # Full age bonus at/below this age
    "max_breakout_age": 28,        # No age bonus above this
    "quality_win_threshold": 0.5,  # Opponent rank must be <= player_rank * threshold
    "cluster_window_days": 45,     # Quality wins must be within this window
    "min_quality_wins": 2,         # Minimum to trigger breakout
    "base_blend": 0.50,            # Blend toward implied ranking (2 wins)
    "per_extra_win_blend": 0.10,   # Extra blend per additional quality win
    "max_blend": 0.75,             # Hard cap on blend
    "young_age_multiplier": 1.3,   # Under peak age
    "neutral_age_multiplier": 1.0, # peak to max age
    "old_age_multiplier": 0.6,     # Over max age
    "implied_rank_buffer": 1.2,    # Multiply avg opponent rank (don't over-promote)
    "suppress_large_gap_boost": True,
}

# ============================================================================
# MATCH CONTEXT SETTINGS
# When a player competes below their home tournament level, their ranking/
# perf_elo/h2h advantages are less meaningful. This system detects level
# displacement and discounts factor scores accordingly.
# ============================================================================
MATCH_CONTEXT_SETTINGS = {
    "level_hierarchy": {
        "ITF": 1,
        "Challenger": 2,
        "WTA": 3,
        "ATP": 3,
        "Grand Slam": 4,
        "Unknown": 2,  # Default to middle ground
    },
    "discount_per_level": 0.20,       # Score discount per level of displacement
    "max_discount": 0.60,             # Hard cap on discount
    "discounted_factors": ["ranking", "performance_elo", "h2h"],
    "form_level_relevance": {
        0: 1.00,   # Same level as current match
        1: 0.85,   # 1 level away
        2: 0.70,   # 2 levels away
        3: 0.55,   # 3 levels away
    },
    "rust_warning_days": 10,
    "level_mismatch_warning": True,
    "near_breakout_warning": True,
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
    # Enhanced rust parameters (configurable instead of hardcoded)
    "rust_max_penalty": 25,    # Max rust penalty points (was hardcoded at 15)
    "rust_tau": 8,             # Exponential decay constant (was hardcoded at 10)
}

# ============================================================================
# BETTING SETTINGS
# ============================================================================
BETTING_SETTINGS = {
    "min_ev_threshold": 0.05,    # Minimum expected value (5%)
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
    # Quarter (0.25) = conservative, Half (0.50) = aggressive, 0.375 = balanced
    "kelly_fraction": 0.375,

    # Betfair exchange commission rate (applied to winnings)
    # Basic package: 2%, Rewards: 5%, Rewards+: 8%
    "exchange_commission": 0.02,

    # Minimum odds floor - odds below this are not considered value
    "min_odds": 1.70,

    # Minimum opponent odds - skip match if either player is below this (liquidity filter)
    "min_opponent_odds": 1.05,

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
            "max_ratio": 1.20,   # Up to 1.2x market probability
            "penalty": 1.0,      # Full stake
        },
        "moderate": {            # Moderate disagreement - reduce stake
            "max_ratio": 1.50,   # 1.2x - 1.5x market probability
            "penalty": 0.75,     # 75% of calculated stake
        },
        "major": {               # Major disagreement - still bet but smaller
            "max_ratio": 999,    # 1.5x+ market probability
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
    # DISABLED: You can't beat the market by agreeing with it.
    # If model has 10% edge, blending gives 7% edge. Mathematically self-defeating.
    "market_blend": {
        "enabled": False,  # Disabled - let model disagree with market
        "market_weight": 0.30,   # 30% market, 70% model (unused when disabled)
    },

    # Probability calibration - shrinkage method
    # DISABLED: Based on only 60 bets - statistically meaningless sample.
    # Re-enable when you have 500+ bets with tracked predictions vs outcomes.
    # Then calibrate based on actual Brier scores, not guesses.
    "calibration": {
        "enabled": False,  # Disabled - need 500+ bets before calibrating
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
