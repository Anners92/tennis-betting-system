"""
Tennis Betting System - Performance Elo Calculator

Calculates a rolling 12-month Performance Elo for each player based on
actual match results weighted by opponent strength and tournament level.

A player's Performance Elo diverges from their ranking-derived Elo when
they're performing above or below their ATP ranking. This gap is the signal.
"""

import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable

from config import get_tour_level

# K-factor by tournament level (higher = result shifts Elo more)
K_FACTORS = {
    "Grand Slam": 48,
    "ATP": 32,
    "WTA": 28,
    "Challenger": 24,
    "ITF": 20,
    "Unknown": 24,
}

DEFAULT_ELO = 1200  # For players with no ranking
ROLLING_MONTHS = 12


def ranking_to_elo(ranking) -> float:
    """Convert ATP ranking to Elo rating. Same formula as MatchAnalyzer._ranking_to_elo()."""
    if ranking is None or not isinstance(ranking, (int, float)) or ranking <= 0:
        return DEFAULT_ELO
    base_elo = 2500
    elo = base_elo - 150 * math.log2(max(int(ranking), 1))
    return max(elo, 1000)


def get_k_factor(tournament_name: str) -> int:
    """Get K-factor for a tournament based on its level."""
    level = get_tour_level(tournament_name)
    return K_FACTORS.get(level, 24)


import re

# Pattern for women's ITF events (W15, W25, W40, W60, W80, W100)
_WOMEN_ITF_PATTERN = re.compile(r'\bw(?:15|25|40|60|80|100)\b', re.IGNORECASE)


def _detect_tour_from_matches(matches) -> str:
    """Determine if a player is ATP or WTA from their match tournaments."""
    atp_count = 0
    wta_count = 0
    for match in matches:
        tournament = match.get('tournament', '')
        level = get_tour_level(tournament)
        if level in ("ATP", "Challenger"):
            atp_count += 1
        elif level == "WTA":
            wta_count += 1
        elif level == "ITF":
            # Check for women's ITF naming patterns
            name_lower = tournament.lower()
            if _WOMEN_ITF_PATTERN.search(name_lower) or 'women' in name_lower:
                wta_count += 1
            elif 'men' in name_lower:
                atp_count += 1
            # else ambiguous, skip

    if atp_count == 0 and wta_count == 0:
        return None  # Ambiguous - will be resolved by opponent check
    return "ATP" if atp_count >= wta_count else "WTA"


def _build_ranking_cache(db) -> Dict[int, int]:
    """Build a cache of player_id -> current_ranking for all players. Called once per recalculation."""
    cache = {}
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, current_ranking FROM players WHERE current_ranking IS NOT NULL")
        for row in cursor.fetchall():
            cache[row[0]] = row[1]
    return cache


# Module-level cache, populated by recalculate_all_performance_elo
_ranking_cache: Dict[int, int] = {}


def calculate_player_performance_elo(player_id: int, db) -> Optional[Dict]:
    """
    Calculate Performance Elo for a single player from their last 12 months of matches.

    Process:
    1. Start from ATP ranking-derived Elo (baseline expectation)
    2. Iterate through matches chronologically (oldest first)
    3. For each match, compare actual result to expected result vs opponent's ranking Elo
    4. Adjust Elo up/down using K-factor weighted by tournament importance

    Returns {'elo': float, 'tour': str} or None if no matches in the window.
    """
    player = db.get_player(player_id)
    if not player:
        return None

    # Starting Elo from current ATP ranking
    current_ranking = player.get('current_ranking')
    elo = ranking_to_elo(current_ranking)

    # Get matches from last 12 months
    cutoff_date = (datetime.now() - timedelta(days=ROLLING_MONTHS * 30)).strftime("%Y-%m-%d")
    matches = db.get_player_matches(player_id, since_date=cutoff_date)

    if not matches:
        return None

    # Sort chronologically (oldest first) for proper Elo progression
    matches.sort(key=lambda m: m.get('date', ''))

    # Detect tour from match history
    tour = _detect_tour_from_matches(matches)

    canonical_id = db.get_canonical_id(player_id)

    for match in matches:
        # Determine if this player won
        winner_canonical = db.get_canonical_id(match.get('winner_id'))
        won = (winner_canonical == canonical_id)
        actual = 1.0 if won else 0.0

        # Get opponent's ranking -> derive their Elo
        if won:
            opp_rank = match.get('loser_rank')
            opp_id = match.get('loser_id')
        else:
            opp_rank = match.get('winner_rank')
            opp_id = match.get('winner_id')

        # Fallback: if match data has no rank, look up opponent's current ranking from cache
        if not opp_rank or not isinstance(opp_rank, (int, float)) or opp_rank <= 0:
            if opp_id and opp_id in _ranking_cache:
                opp_rank = _ranking_cache[opp_id]

        if opp_rank and isinstance(opp_rank, (int, float)) and opp_rank > 0:
            opp_elo = ranking_to_elo(int(opp_rank))
        else:
            opp_elo = DEFAULT_ELO

        # Expected win probability
        expected = 1 / (1 + math.pow(10, (opp_elo - elo) / 400))

        # K-factor based on tournament importance
        tournament = match.get('tournament', '')
        k = get_k_factor(tournament)

        # Standard Elo update
        elo += k * (actual - expected)

    return {"elo": round(elo, 1), "tour": tour}


def _fix_ambiguous_tours(player_ids: list, db):
    """
    Fix tour classification for players whose tournaments were all ambiguous (ITF without gender markers).
    Iteratively checks what tour their opponents are classified as. Runs multiple passes so that
    once some players are correctly classified as WTA, their opponents can be reclassified too.
    Falls back to ATP only after convergence.
    """
    remaining = set(player_ids)

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Iterative passes - each pass may resolve more players via newly-classified opponents
        for pass_num in range(10):  # Max 10 iterations for deeper ITF network propagation
            resolved_this_pass = 0
            still_ambiguous = []

            for player_id in remaining:
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN opp.tour = 'ATP' THEN 1 ELSE 0 END) as atp_opps,
                        SUM(CASE WHEN opp.tour = 'WTA' THEN 1 ELSE 0 END) as wta_opps
                    FROM (
                        SELECT loser_id AS opp_id FROM matches WHERE winner_id = ?
                        UNION ALL
                        SELECT winner_id AS opp_id FROM matches WHERE loser_id = ?
                    ) m
                    JOIN players opp ON opp.id = m.opp_id
                    WHERE opp.tour IS NOT NULL
                """, (player_id, player_id))
                row = cursor.fetchone()
                atp_opps = row[0] or 0
                wta_opps = row[1] or 0

                if atp_opps > 0 or wta_opps > 0:
                    tour = "WTA" if wta_opps > atp_opps else "ATP"
                    cursor.execute("UPDATE players SET tour = ? WHERE id = ?", (tour, player_id))
                    resolved_this_pass += 1
                else:
                    still_ambiguous.append(player_id)

            remaining = set(still_ambiguous)
            if resolved_this_pass == 0:
                break  # No progress, stop iterating

        # Final fallback: WTA-aware — check if any opponent is WTA with zero ATP
        for player_id in remaining:
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN opp.tour = 'ATP' THEN 1 ELSE 0 END) as atp_opps,
                    SUM(CASE WHEN opp.tour = 'WTA' THEN 1 ELSE 0 END) as wta_opps
                FROM (
                    SELECT loser_id AS opp_id FROM matches WHERE winner_id = ?
                    UNION ALL
                    SELECT winner_id AS opp_id FROM matches WHERE loser_id = ?
                ) m
                JOIN players opp ON opp.id = m.opp_id
            """, (player_id, player_id))
            row = cursor.fetchone()
            atp_opps = row[0] or 0
            wta_opps = row[1] or 0
            tour = "WTA" if wta_opps > 0 and atp_opps == 0 else "ATP"
            cursor.execute("UPDATE players SET tour = ? WHERE id = ?", (tour, player_id))


def recalculate_all_performance_elo(db, progress_callback: Callable = None) -> int:
    """
    Recalculate Performance Elo for all players with matches in the last 12 months.
    Returns number of players updated.
    """
    global _ranking_cache
    _ranking_cache = _build_ranking_cache(db)
    if progress_callback:
        progress_callback(f"Ranking cache loaded: {len(_ranking_cache)} players")

    cutoff = (datetime.now() - timedelta(days=ROLLING_MONTHS * 30)).strftime("%Y-%m-%d")

    # Find all players who have played in the rolling window
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT id FROM (
                SELECT winner_id AS id FROM matches WHERE date >= ?
                UNION
                SELECT loser_id AS id FROM matches WHERE date >= ?
            )
        """, (cutoff, cutoff))
        active_player_ids = [row[0] for row in cursor.fetchall()]

    total = len(active_player_ids)
    if progress_callback:
        progress_callback(f"Calculating Performance Elo for {total} active players...")

    updated = 0
    ambiguous_ids = []
    for i, player_id in enumerate(active_player_ids):
        result = calculate_player_performance_elo(player_id, db)
        if result is not None:
            db.update_player_performance_elo(player_id, result["elo"])
            if result["tour"] is not None:
                db.update_player_tour(player_id, result["tour"])
            else:
                # Clear any stale tour so opponent check only counts clearly-classified players
                db.update_player_tour(player_id, None)
                ambiguous_ids.append(player_id)
            updated += 1

        if progress_callback and (i + 1) % 200 == 0:
            progress_callback(f"  Performance Elo: {i + 1}/{total} players processed")

    if progress_callback:
        progress_callback(f"Performance Elo complete: {updated}/{total} players updated")

    # Fix ambiguous tours by checking what tour their opponents play on
    if ambiguous_ids:
        if progress_callback:
            progress_callback(f"Resolving tour for {len(ambiguous_ids)} ambiguous players...")
        _fix_ambiguous_tours(ambiguous_ids, db)

    # Assign Performance Ranks within each tour (highest Elo = rank 1)
    if progress_callback:
        progress_callback("Assigning Performance Ranks...")
    db.update_all_performance_ranks()
    if progress_callback:
        progress_callback(f"Performance Ranks assigned for {updated} players")

    return updated
