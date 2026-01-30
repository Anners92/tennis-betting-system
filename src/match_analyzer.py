"""
Tennis Betting System - Match Analyzer
Core analysis engine with factor calculations and probability model
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

from config import (
    UI_COLORS, SURFACES, DEFAULT_ANALYSIS_WEIGHTS,
    FORM_SETTINGS, SURFACE_SETTINGS, FATIGUE_SETTINGS,
    BETTING_SETTINGS, SET_BETTING, KELLY_STAKING, LOGS_DIR,
    OPPONENT_QUALITY_SETTINGS, RECENCY_SETTINGS,
    RECENT_LOSS_SETTINGS, MOMENTUM_SETTINGS, BREAKOUT_SETTINGS,
    MATCH_CONTEXT_SETTINGS,
    get_tour_level, TOURNAMENT_FORM_WEIGHT
)
from collections import Counter
import csv
import logging
import json
from pathlib import Path

# Setup staking logger
staking_log_file = LOGS_DIR / "staking_decisions.csv"
staking_logger = logging.getLogger("staking")
staking_logger.setLevel(logging.INFO)
from database import db, TennisDatabase
from tennis_abstract_scraper import TennisAbstractScraper


class MatchAnalyzer:
    """Core analysis engine for tennis match predictions."""

    def __init__(self, database: TennisDatabase = None):
        self.db = database or db
        self.weights = DEFAULT_ANALYSIS_WEIGHTS.copy()
        self._rankings_cache = None
        self._lowest_ranking_cache = None
        self._ranking_id_cache = None

    def _get_ranking_from_cache(self, player_name: str) -> Optional[int]:
        """Look up player ranking from the rankings cache file."""
        if self._rankings_cache is None:
            cache_path = Path(__file__).parent.parent / "data" / "rankings_cache.json"
            try:
                with open(cache_path, 'r') as f:
                    self._rankings_cache = json.load(f)
            except Exception:
                self._rankings_cache = {}

        # Normalize name for comparison
        name_lower = player_name.lower().strip()

        # Search in both ATP and WTA rankings
        for tour in ['atp', 'wta']:
            for player in self._rankings_cache.get(tour, []):
                if player.get('name', '').lower().strip() == name_lower:
                    return player.get('rank')

        return None

    def _get_ranking_by_id(self, player_id: int) -> Optional[int]:
        """Look up a player's current ranking by ID from cache."""
        if self._ranking_id_cache is None:
            # Build in local var first to avoid thread race — other threads
            # would see the empty dict before it's populated
            cache = {}
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT id, current_ranking FROM players WHERE current_ranking IS NOT NULL"
                    )
                    for row in cursor.fetchall():
                        cache[row[0]] = row[1]
            except Exception:
                pass
            self._ranking_id_cache = cache
        return self._ranking_id_cache.get(player_id)

    def _get_lowest_ranking(self) -> int:
        """Get the lowest (highest number) ranking from the database.
        Used as default for unranked players so they're treated as lowest ranked."""
        if self._lowest_ranking_cache is None:
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT MAX(current_ranking) FROM players WHERE current_ranking IS NOT NULL"
                    )
                    result = cursor.fetchone()
                    if result and result[0]:
                        self._lowest_ranking_cache = result[0]
                    else:
                        self._lowest_ranking_cache = 1500  # Fallback if no rankings exist
            except Exception:
                self._lowest_ranking_cache = 1500
        return self._lowest_ranking_cache

    def set_weights(self, weights: Dict[str, float]):
        """Set custom analysis weights."""
        self.weights.update(weights)

    # =========================================================================
    # FORM CALCULATION
    # =========================================================================

    def calculate_form_score(self, player_id: int, num_matches: int = None,
                             as_of_date: str = None, match_level: int = None) -> Dict:
        """
        Calculate form score for a player based on recent matches.
        Returns score 0-100 with breakdown.
        """
        num_matches = num_matches or FORM_SETTINGS["default_matches"]

        matches = self.db.get_player_matches(player_id, limit=num_matches * 2)

        if as_of_date:
            matches = [m for m in matches if m.get('date') and m['date'] < as_of_date]

        matches = matches[:num_matches]

        if not matches:
            return {
                "score": 50,
                "matches": 0,
                "wins": 0,
                "losses": 0,
                "details": [],
                "has_data": False  # Flag indicating no reliable data
            }

        wins = 0
        weighted_score = 0
        total_weight = 0
        details = []

        decay = FORM_SETTINGS["recency_decay"]

        # Get canonical ID for proper alias matching
        player_canonical = self.db.get_canonical_id(player_id)

        # Look up player's own ranking for Elo-expected scoring
        player_rank = self._get_ranking_by_id(player_id) or 500
        player_elo = self._ranking_to_elo(player_rank)

        # Level relevance lookup for match context
        level_relevance_map = MATCH_CONTEXT_SETTINGS.get("form_level_relevance", {})
        hierarchy = MATCH_CONTEXT_SETTINGS.get("level_hierarchy", {})

        for idx, match in enumerate(matches):
            # Tournament level weight — higher-level results carry more weight
            tournament = match.get('tournament') or match.get('tourney_name') or 'Unknown'
            tour_level_str = get_tour_level(tournament)
            tour_weight = TOURNAMENT_FORM_WEIGHT.get(tour_level_str, 1.0)

            # Level relevance — when match_level is provided, weight historical results
            # by how close their level is to the current match level.
            # ITF results matter more when analyzing an ITF match; WTA results less so.
            if match_level is not None:
                hist_level = hierarchy.get(tour_level_str, 2)
                level_distance = abs(hist_level - match_level)
                level_relevance = level_relevance_map.get(level_distance, 0.55)
                tour_weight *= level_relevance

            # Date-based decay — exponential decay with ~83-day half-life
            match_date_str = match.get('date')
            if match_date_str:
                try:
                    ref_date = datetime.strptime(as_of_date, "%Y-%m-%d") if as_of_date else datetime.now()
                    match_dt = datetime.strptime(match_date_str[:10], "%Y-%m-%d")
                    days_ago = (ref_date - match_dt).days
                    date_decay = math.exp(-days_ago / 120)
                except (ValueError, TypeError):
                    date_decay = 1.0
            else:
                date_decay = 1.0

            # Combined weight: position decay × tournament importance × date freshness
            weight = (decay ** idx) * tour_weight * date_decay

            # Check if player won (using canonical IDs for alias matching)
            winner_canonical = self.db.get_canonical_id(match['winner_id'])
            won = winner_canonical == player_canonical
            if won:
                wins += 1

            # Resolve opponent rank — fallback to current ranking if match data is missing
            if won:
                opp_rank = match.get('loser_rank')
                opp_id = match.get('loser_id')
            else:
                opp_rank = match.get('winner_rank')
                opp_id = match.get('winner_id')

            if opp_rank is None or not isinstance(opp_rank, (int, float)):
                looked_up = self._get_ranking_by_id(opp_id) if opp_id else None
                opp_rank = looked_up if looked_up else 500

            # Elo-expected match scoring: scores based on how expected the result was
            opp_elo = self._ranking_to_elo(int(opp_rank))
            expected_win = 1 / (1 + 10 ** ((opp_elo - player_elo) / 400))
            # Cap to avoid extreme scores from huge Elo gaps (e.g., #1 vs #1300)
            expected_win = max(0.05, min(0.95, expected_win))

            # Surprise weighting — upset losses are more informative about true level
            # Losing to someone you should beat reveals your floor
            # Wins are not amplified — anyone can beat a weaker opponent
            if won:
                surprise = 1.0
            else:
                surprise = min(3.0, max(1.0, expected_win / (1 - expected_win)))
            weight *= surprise

            if won:
                # Upset win → high score, expected win → modest score
                base_score = 50 + 50 * (1 - expected_win)
            else:
                # Expected loss → near-neutral, upset loss → severe
                base_score = 60 * (1 - expected_win)

            # Set score dominance modifier — rewards dominant wins, penalizes blowout losses
            # Try pre-computed game counts first, fall back to parsing score string
            winner_games = match.get('games_won_w', 0) or 0
            loser_games = match.get('games_won_l', 0) or 0
            if winner_games == 0 and loser_games == 0:
                score_str = match.get('score', '')
                if score_str:
                    winner_games, loser_games = self._parse_games_from_score(score_str)

            if won:
                player_games, opp_games = winner_games, loser_games
            else:
                player_games, opp_games = loser_games, winner_games

            total_games = player_games + opp_games
            if total_games > 0:
                player_ratio = player_games / total_games
                dominance = 1 + (player_ratio - 0.5) * 0.3  # 0.85 to 1.15
            else:
                dominance = 1.0

            match_score = base_score * dominance

            weighted_score += match_score * weight
            total_weight += weight

            # Get opponent name
            if won:
                opponent_name = match.get('loser_name', 'Unknown')
            else:
                opponent_name = match.get('winner_name', 'Unknown')

            details.append({
                'date': match['date'],
                'won': won,
                'opponent_name': opponent_name,
                'opponent_rank': opp_rank,
                'score': match_score,
                'weight': weight,
                'tournament': tournament,
                'dominance': round(dominance, 3),
                'date_decay': round(date_decay, 3),
                'surprise': round(surprise, 2),
            })

        # Second pass: amplify confirmed strong wins
        # A single upset win could be luck. But if the player followed up with
        # another win against a similarly-ranked (or better) opponent within
        # the next 2 matches, that confirms it's real — amplify both.
        # List is most-recent-first, so "followed up" = lower index = more recent.
        for i, d in enumerate(details):
            if not d['won'] or d['opponent_rank'] >= player_rank:
                continue  # Only check wins against stronger opponents
            # Look at the next 2 matches chronologically (indices i-1, i-2)
            for j in range(max(0, i - 2), i):
                dj = details[j]
                if dj['won'] and dj['opponent_rank'] <= d['opponent_rank'] * 1.5:
                    # Confirmed! Amplify this win (cap at 2.0)
                    if d['surprise'] < 2.0:
                        amplify = 2.0 / max(d['surprise'], 1.0)
                        weighted_score += d['score'] * d['weight'] * (amplify - 1)
                        total_weight += d['weight'] * (amplify - 1)
                        d['weight'] = round(d['weight'] * amplify, 4)
                        d['surprise'] = 2.0
                    # Also amplify the confirming win
                    if dj['surprise'] < 2.0:
                        amplify_j = 2.0 / max(dj['surprise'], 1.0)
                        weighted_score += dj['score'] * dj['weight'] * (amplify_j - 1)
                        total_weight += dj['weight'] * (amplify_j - 1)
                        dj['weight'] = round(dj['weight'] * amplify_j, 4)
                        dj['surprise'] = 2.0
                    break

        form_score = weighted_score / total_weight if total_weight > 0 else 50

        # Average opponent rank for transparency
        avg_opp_rank = round(sum(d['opponent_rank'] for d in details) / len(details)) if details else None

        return {
            "score": round(form_score, 1),
            "matches": len(matches),
            "wins": wins,
            "losses": len(matches) - wins,
            "avg_opponent_rank": avg_opp_rank,
            "win_rate": wins / len(matches) if matches else 0,
            "details": details,
            "has_data": len(matches) >= 3  # Need at least 3 matches for reliable data
        }

    # =========================================================================
    # SURFACE PERFORMANCE
    # =========================================================================

    def get_surface_stats(self, player_id: int, surface: str) -> Dict:
        """
        Get surface performance stats combining career and recent data.
        """
        # Get aggregated stats from database
        stats = self.db.get_surface_stats(player_id, surface)

        if not stats:
            # Calculate from scratch
            return self._calculate_surface_stats(player_id, surface)

        stat = stats[0]
        career_win_rate = stat.get('win_rate') or 0.5
        career_matches = stat.get('matches_played') or 0

        # Get recent (last 2 years) surface matches
        two_years_ago = (datetime.now() - timedelta(days=365 * SURFACE_SETTINGS["recent_years"])).strftime("%Y-%m-%d")
        recent_matches = self.db.get_player_matches(player_id, surface=surface, since_date=two_years_ago)

        # Use canonical ID for alias matching
        player_canonical = self.db.get_canonical_id(player_id)
        recent_wins = sum(1 for m in recent_matches if self.db.get_canonical_id(m['winner_id']) == player_canonical)
        recent_matches_count = len(recent_matches)
        recent_win_rate = recent_wins / recent_matches_count if recent_matches_count > 0 else career_win_rate

        # Weighted combination
        career_w = SURFACE_SETTINGS["career_weight"]
        recent_w = SURFACE_SETTINGS["recent_weight"]

        # Adjust weights based on sample size
        # Low career sample = trust career less, but don't over-trust recent either
        if career_matches < SURFACE_SETTINGS["min_matches_reliable"]:
            # Scale down career weight proportionally
            career_reliability = career_matches / SURFACE_SETTINGS["min_matches_reliable"]
            career_w *= career_reliability
            # Don't give all remaining weight to recent - blend with neutral
            # This prevents wild swings from small recent samples
            recent_w = min(recent_w, SURFACE_SETTINGS["recent_weight"])
            # Remaining weight goes to neutral baseline (0.5)
            neutral_w = 1 - career_w - recent_w
        else:
            neutral_w = 0

        combined_win_rate = (career_win_rate * career_w + recent_win_rate * recent_w + 0.5 * neutral_w)

        return {
            "surface": surface,
            "career_matches": career_matches,
            "career_win_rate": round(career_win_rate, 3),
            "recent_matches": recent_matches_count,
            "recent_win_rate": round(recent_win_rate, 3),
            "combined_win_rate": round(combined_win_rate, 3),
            "score": round(combined_win_rate * 100, 1),
            "avg_games_won": stat.get('avg_games_won', 0),
            "avg_games_lost": stat.get('avg_games_lost', 0),
            "has_data": (career_matches >= 5) or (recent_matches_count >= 5)  # Need at least 5 surface matches
        }

    def _calculate_surface_stats(self, player_id: int, surface: str) -> Dict:
        """Calculate surface stats from match history."""
        matches = self.db.get_player_matches(player_id, surface=surface)

        if not matches:
            return {
                "surface": surface,
                "career_matches": 0,
                "career_win_rate": 0.5,
                "recent_matches": 0,
                "recent_win_rate": 0.5,
                "combined_win_rate": 0.5,
                "score": 50,
                "has_data": False
            }

        # Use canonical ID for alias matching
        player_canonical = self.db.get_canonical_id(player_id)
        wins = sum(1 for m in matches if self.db.get_canonical_id(m['winner_id']) == player_canonical)
        win_rate = wins / len(matches)

        return {
            "surface": surface,
            "career_matches": len(matches),
            "career_win_rate": round(win_rate, 3),
            "recent_matches": len(matches),
            "recent_win_rate": round(win_rate, 3),
            "combined_win_rate": round(win_rate, 3),
            "score": round(win_rate * 100, 1),
            "has_data": len(matches) >= 5  # Need at least 5 surface matches
        }

    # =========================================================================
    # RANKINGS ANALYSIS
    # =========================================================================

    def _ranking_to_elo(self, ranking: int) -> float:
        """
        Convert ATP ranking to approximate Elo rating.
        Uses logarithmic scale to better capture skill gaps.
        Top players have much larger skill gaps than lower-ranked players.
        """
        if ranking <= 0:
            ranking = 200

        # Logarithmic conversion: higher ranks have exponentially more skill
        # #1 ≈ 2500, #10 ≈ 2200, #50 ≈ 1900, #100 ≈ 1700, #200 ≈ 1500
        base_elo = 2500
        # Use log scale: each doubling of ranking loses ~150 Elo points
        elo = base_elo - 150 * math.log2(max(ranking, 1))
        return max(elo, 1000)  # Floor at 1000

    @staticmethod
    def _parse_games_from_score(score_str: str) -> tuple:
        """
        Parse total games won by winner and loser from a score string.
        Examples: "6-0 6-2" → (12, 2), "4-6 7-5 6-1" → (17, 12)
        Handles tiebreak notation like "7-6(4)" or "7-68".
        Returns (winner_games, loser_games) or (0, 0) if unparseable.
        """
        import re
        winner_total = 0
        loser_total = 0
        try:
            # Split into sets, strip whitespace
            sets = score_str.strip().split()
            for s in sets:
                # Remove tiebreak info in parentheses: "7-6(4)" → "7-6"
                s = re.sub(r'\(.*?\)', '', s)
                # Handle "7-68" format (tiebreak without parens) → "7-6"
                parts = s.split('-')
                if len(parts) == 2:
                    w = int(re.sub(r'[^0-9]', '', parts[0]))
                    l = int(re.sub(r'[^0-9]', '', parts[1]))
                    # Cap at 7 per set (tiebreak encoding like "68" → 6)
                    winner_total += min(w, 7)
                    loser_total += min(l, 7)
        except (ValueError, IndexError):
            return (0, 0)
        return (winner_total, loser_total)

    def _elo_win_probability(self, elo1: float, elo2: float) -> float:
        """
        Calculate win probability using Elo formula.
        Returns probability that player 1 beats player 2.
        """
        # Standard Elo formula: P(A) = 1 / (1 + 10^((Rb - Ra)/400))
        return 1 / (1 + math.pow(10, (elo2 - elo1) / 400))

    def _odds_to_estimated_rank(self, odds: float) -> int:
        """
        Estimate player ranking from Betfair odds.
        Used for WTA/unranked players where we don't have ranking data.
        Heavy favorites are likely top players.
        """
        if odds is None or odds <= 1.0:
            return 100  # Default middle ranking

        # Odds -> Estimated Rank mapping
        # 1.01-1.05 = top 3 (heavy favorite in any match)
        # 1.05-1.15 = top 10
        # 1.15-1.30 = top 25
        # 1.30-1.50 = top 50
        # 1.50-2.00 = top 100
        # 2.00-3.00 = 50-150
        # 3.00+ = 100-300
        if odds <= 1.05:
            return 3
        elif odds <= 1.15:
            return 10
        elif odds <= 1.30:
            return 25
        elif odds <= 1.50:
            return 50
        elif odds <= 2.00:
            return 100
        elif odds <= 3.00:
            return 150
        else:
            return 200

    def get_ranking_factors(self, player1_id: int, player2_id: int,
                            p1_odds: float = None, p2_odds: float = None,
                            p1_effective_rank: int = None, p2_effective_rank: int = None) -> Dict:
        """
        Analyze ranking comparison between two players.
        Uses Elo-like probability for more accurate skill gap estimation.

        For WTA/unranked players, uses Betfair odds to estimate ranking.
        p1_effective_rank/p2_effective_rank: Override rankings from breakout detection.
        """
        p1 = self.db.get_player(player1_id) or {}
        p2 = self.db.get_player(player2_id) or {}


        # Try to get ranking from cache first (most accurate), then database
        p1_name = p1.get('name', '')
        p2_name = p2.get('name', '')

        p1_rank = self._get_ranking_from_cache(p1_name)
        p1_cache_found = p1_rank is not None
        if p1_rank is None:
            p1_rank = p1.get('current_ranking') or p1.get('ranking')

        p2_rank = self._get_ranking_from_cache(p2_name)
        p2_cache_found = p2_rank is not None
        if p2_rank is None:
            p2_rank = p2.get('current_ranking') or p2.get('ranking')


        # For players without rankings, use lowest ranked player as default
        # This treats unranked players as the weakest ranked players
        p1_estimated = False
        p2_estimated = False
        default_rank = self._get_lowest_ranking()

        if p1_rank is None:
            if p1_odds:
                p1_rank = self._odds_to_estimated_rank(p1_odds)
                p1_estimated = True
            else:
                p1_rank = default_rank
                p1_estimated = True

        if p2_rank is None:
            if p2_odds:
                p2_rank = self._odds_to_estimated_rank(p2_odds)
                p2_estimated = True
            else:
                p2_rank = default_rank
                p2_estimated = True

        # Final safety check - ensure ranks are always integers
        if p1_rank is None or not isinstance(p1_rank, (int, float)):
            p1_rank = default_rank
        if p2_rank is None or not isinstance(p2_rank, (int, float)):
            p2_rank = default_rank

        # Store display ranks before applying effective rank overrides
        p1_display_rank = p1_rank
        p2_display_rank = p2_rank

        # Apply effective ranking overrides from breakout detection
        if p1_effective_rank is not None:
            p1_rank = p1_effective_rank
        if p2_effective_rank is not None:
            p2_rank = p2_effective_rank

        # Get ranking history for trajectory
        p1_history = self.db.get_player_ranking_history(player1_id, limit=12)
        p2_history = self.db.get_player_ranking_history(player2_id, limit=12)

        # Calculate trajectory (positive = improving, negative = declining)
        p1_trajectory = self._calculate_trajectory(p1_history)
        p2_trajectory = self._calculate_trajectory(p2_history)

        # Convert rankings to Elo ratings (uses effective ranks if overridden)
        p1_elo = self._ranking_to_elo(p1_rank)
        p2_elo = self._ranking_to_elo(p2_rank)

        # Calculate Elo-based win probability for P1
        elo_win_prob = self._elo_win_probability(p1_elo, p2_elo)

        # Convert Elo probability to advantage scale (-1 to 1)
        # 0.5 probability = 0 advantage, 0.9 probability = 0.8 advantage
        rank_advantage = (elo_win_prob - 0.5) * 2

        # Flag for large ranking gap (uses display ranks — actual gap)
        rank_gap = abs(p1_display_rank - p2_display_rank)
        is_large_gap = rank_gap > 100 or (min(p1_display_rank, p2_display_rank) <= 10 and rank_gap > 50)

        # Convert to score (50 = equal, 0-100 range)
        p1_rank_score = max(0, 100 - p1_display_rank) if p1_display_rank else 50
        p2_rank_score = max(0, 100 - p2_display_rank) if p2_display_rank else 50

        return {
            "p1_rank": p1_display_rank,
            "p2_rank": p2_display_rank,
            "p1_effective_rank": p1_rank,
            "p2_effective_rank": p2_rank,
            "p1_estimated": p1_estimated,
            "p2_estimated": p2_estimated,
            "rank_diff": p2_display_rank - p1_display_rank,
            "p1_trajectory": round(p1_trajectory, 2),
            "p2_trajectory": round(p2_trajectory, 2),
            "p1_peak": p1.get('peak_ranking'),
            "p2_peak": p2.get('peak_ranking'),
            "rank_advantage": round(rank_advantage, 3),
            "elo_win_prob": round(elo_win_prob, 3),
            "p1_elo": round(p1_elo, 0),
            "p2_elo": round(p2_elo, 0),
            "is_large_gap": is_large_gap,
            "p1_score": p1_rank_score,
            "p2_score": p2_rank_score,
        }

    def get_performance_elo_factors(self, player1_id: int, player2_id: int,
                                     p1_odds: float = None, p2_odds: float = None,
                                     p1_effective_rank: int = None, p2_effective_rank: int = None) -> Dict:
        """
        Analyze Performance Elo comparison between two players.
        Performance Elo = actual results-based Elo from the last 12 months.
        Falls back to ranking-derived Elo if no Performance Elo is available.
        p1_effective_rank/p2_effective_rank: Override for fallback ranking (breakout).
        """
        p1_perf_elo = self.db.get_player_performance_elo(player1_id)
        p2_perf_elo = self.db.get_player_performance_elo(player2_id)
        p1_perf_rank = self.db.get_player_performance_rank(player1_id)
        p2_perf_rank = self.db.get_player_performance_rank(player2_id)

        p1_has_data = p1_perf_elo is not None
        p2_has_data = p2_perf_elo is not None

        # Fallback to ranking-derived Elo (use effective rank if breakout detected)
        if not p1_has_data:
            p1 = self.db.get_player(player1_id) or {}
            p1_rank = p1_effective_rank or p1.get('current_ranking')
            if not p1_rank and p1_odds:
                p1_rank = self._odds_to_estimated_rank(p1_odds)
            p1_perf_elo = self._ranking_to_elo(p1_rank or self._get_lowest_ranking())
        elif p1_effective_rank is not None:
            # Has real perf elo but breakout detected — blend toward effective rank Elo
            eff_elo = self._ranking_to_elo(p1_effective_rank)
            p1_perf_elo = max(p1_perf_elo, 0.5 * p1_perf_elo + 0.5 * eff_elo)

        if not p2_has_data:
            p2 = self.db.get_player(player2_id) or {}
            p2_rank = p2_effective_rank or p2.get('current_ranking')
            if not p2_rank and p2_odds:
                p2_rank = self._odds_to_estimated_rank(p2_odds)
            p2_perf_elo = self._ranking_to_elo(p2_rank or self._get_lowest_ranking())
        elif p2_effective_rank is not None:
            # Has real perf elo but breakout detected — blend toward effective rank Elo
            eff_elo = self._ranking_to_elo(p2_effective_rank)
            p2_perf_elo = max(p2_perf_elo, 0.5 * p2_perf_elo + 0.5 * eff_elo)

        # Standard Elo win probability
        win_prob = self._elo_win_probability(p1_perf_elo, p2_perf_elo)

        # Convert to -1 to +1 advantage (same approach as ranking factor)
        advantage = (win_prob - 0.5) * 2

        return {
            "p1_performance_elo": round(p1_perf_elo, 1),
            "p2_performance_elo": round(p2_perf_elo, 1),
            "p1_performance_rank": p1_perf_rank,
            "p2_performance_rank": p2_perf_rank,
            "elo_diff": round(p1_perf_elo - p2_perf_elo, 1),
            "advantage": round(advantage, 3),
            "p1_has_data": p1_has_data,
            "p2_has_data": p2_has_data,
            "win_probability": round(win_prob, 3),
        }

    def _calculate_trajectory(self, history: List[Dict]) -> float:
        """Calculate ranking trajectory (-1 to 1, positive = improving)."""
        if len(history) < 2:
            return 0

        # Compare current vs average of older rankings
        current = history[0].get('ranking', 100)
        older_avg = sum(h.get('ranking', 100) for h in history[1:]) / (len(history) - 1)

        # Improvement = lower ranking number
        diff = older_avg - current
        # Normalize to roughly -1 to 1
        return min(max(diff / 50, -1), 1)

    # =========================================================================
    # HEAD TO HEAD
    # =========================================================================

    def get_h2h(self, player1_id: int, player2_id: int, surface: str = None) -> Dict:
        """
        Get head-to-head record between two players.
        """
        h2h = self.db.get_h2h(player1_id, player2_id)

        if not h2h:
            # Calculate from match history - use canonical IDs for alias matching
            matches = self.db.get_h2h_matches(player1_id, player2_id)
            p1_canonical = self.db.get_canonical_id(player1_id)
            p1_wins = sum(1 for m in matches if self.db.get_canonical_id(m['winner_id']) == p1_canonical)
            p2_wins = len(matches) - p1_wins

            h2h = {
                'p1_wins': p1_wins,
                'p2_wins': p2_wins,
                'p1_wins_by_surface': {},
                'p2_wins_by_surface': {},
            }

        total = h2h['p1_wins'] + h2h['p2_wins']

        # Surface-specific H2H
        surface_p1 = 0
        surface_p2 = 0
        if surface:
            surface_p1 = h2h.get('p1_wins_by_surface', {}).get(surface, 0)
            surface_p2 = h2h.get('p2_wins_by_surface', {}).get(surface, 0)

        # Recent H2H (last 3 matches) - use canonical IDs
        recent_matches = self.db.get_h2h_matches(player1_id, player2_id)[:3]
        p1_canonical = self.db.get_canonical_id(player1_id)
        recent_p1 = sum(1 for m in recent_matches if self.db.get_canonical_id(m['winner_id']) == p1_canonical)
        recent_p2 = len(recent_matches) - recent_p1

        # Calculate advantage score
        if total > 0:
            h2h_advantage = (h2h['p1_wins'] - h2h['p2_wins']) / total
        else:
            h2h_advantage = 0

        # Calculate surface-specific advantage
        surface_total = surface_p1 + surface_p2
        if surface_total > 0:
            surface_advantage = (surface_p1 - surface_p2) / surface_total
        else:
            surface_advantage = 0

        # Blend overall and surface-specific H2H (60% overall, 40% surface if data exists)
        if surface_total >= 2:  # Need at least 2 surface matches to be meaningful
            combined_advantage = 0.6 * h2h_advantage + 0.4 * surface_advantage
        else:
            combined_advantage = h2h_advantage

        return {
            "total_matches": total,
            "p1_wins": h2h['p1_wins'],
            "p2_wins": h2h['p2_wins'],
            "p1_win_rate": h2h['p1_wins'] / total if total > 0 else 0.5,
            "surface": surface,
            "surface_p1_wins": surface_p1,
            "surface_p2_wins": surface_p2,
            "surface_advantage": round(surface_advantage, 3),
            "recent_p1_wins": recent_p1,
            "recent_p2_wins": recent_p2,
            "advantage": round(combined_advantage, 3),  # Now includes surface-specific
            "overall_advantage": round(h2h_advantage, 3),  # Keep pure overall for reference
            "p1_score": round(50 + combined_advantage * 50, 1),
            "p2_score": round(50 - combined_advantage * 50, 1),
        }

    # =========================================================================
    # FATIGUE/SCHEDULING
    # =========================================================================

    def calculate_match_difficulty(self, match: Dict, player_id: int) -> float:
        """
        Calculate difficulty score for a match (0.5 to 3.0).
        - 0.5 = walkover/retirement
        - 1.0 = standard 2-0 win (~60 min)
        - 3.0 = marathon 5-setter (300+ min)

        Combines duration and sets played.
        """
        diff_min = FATIGUE_SETTINGS.get("difficulty_min", 0.5)
        diff_max = FATIGUE_SETTINGS.get("difficulty_max", 3.0)
        baseline_minutes = FATIGUE_SETTINGS.get("difficulty_baseline_minutes", 60)
        max_minutes = FATIGUE_SETTINGS.get("difficulty_max_minutes", 300)
        baseline_sets = FATIGUE_SETTINGS.get("difficulty_baseline_sets", 2)

        # Get match data
        minutes = match.get('minutes')
        score = match.get('score', '')
        best_of = match.get('best_of', 3)

        # Determine if player won or lost (using canonical IDs for alias matching)
        player_canonical = self.db.get_canonical_id(player_id)
        winner_canonical = self.db.get_canonical_id(match.get('winner_id'))
        won = winner_canonical == player_canonical
        sets_won = match.get('sets_won_w', 0) if won else match.get('sets_won_l', 0)
        sets_lost = match.get('sets_won_l', 0) if won else match.get('sets_won_w', 0)
        total_sets = (sets_won or 0) + (sets_lost or 0)

        # Check for retirement/walkover (indicated by incomplete sets or 'RET'/'W/O' in score)
        is_retirement = False
        if score:
            score_upper = score.upper()
            if 'RET' in score_upper or 'W/O' in score_upper or 'DEF' in score_upper:
                is_retirement = True

        # If retirement/walkover, return minimum difficulty
        if is_retirement:
            return diff_min

        # Calculate duration component (0 to 1 scale)
        if minutes and minutes > 0:
            duration_factor = min(minutes / max_minutes, 1.0)
        else:
            # Estimate from sets if no duration data
            # Assume ~30 min per set as rough estimate
            estimated_minutes = total_sets * 30 if total_sets > 0 else baseline_minutes
            duration_factor = min(estimated_minutes / max_minutes, 1.0)

        # Calculate sets component (0 to 1 scale)
        max_sets = best_of  # 3 or 5
        if total_sets > 0:
            sets_factor = (total_sets - baseline_sets) / (max_sets - baseline_sets)
            sets_factor = max(0, min(sets_factor, 1.0))
        else:
            sets_factor = 0

        # Combine: weight duration 60%, sets 40%
        combined_factor = (duration_factor * 0.6) + (sets_factor * 0.4)

        # Scale to difficulty range (1.0 to diff_max for non-retirements)
        # A baseline match (2 sets, 60 min) should score ~1.0
        difficulty = 1.0 + (combined_factor * (diff_max - 1.0))

        return round(min(max(difficulty, diff_min), diff_max), 2)

    def calculate_fatigue(self, player_id: int, match_date: str = None) -> Dict:
        """
        Calculate fatigue score for a player.
        Lower score = more fatigued.

        Now accounts for match difficulty - a 5-set marathon impacts fatigue
        more than a quick 2-0 win.
        """
        # Get recent matches first
        recent_matches = self.db.get_player_matches(player_id, limit=20)

        if not recent_matches:
            return {
                "score": 80,
                "days_since_match": None,
                "matches_14d": 0,
                "matches_30d": 0,
                "difficulty_7d": 0,
                "status": "Unknown",
            }

        # Use the upcoming match date as reference for "today" when provided
        # This correctly calculates rest days relative to when the player will actually play
        if match_date:
            try:
                reference_dt = datetime.strptime(match_date[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                reference_dt = datetime.now()
        else:
            # Fall back to database's most recent match date or current date
            db_most_recent = self.db.get_most_recent_match_date()
            if db_most_recent:
                reference_dt = datetime.strptime(db_most_recent, "%Y-%m-%d")
            else:
                reference_dt = datetime.now()

        # Player's last match date
        last_match_date = recent_matches[0].get('date')

        # Calculate days since last match relative to the DATABASE's most recent date
        # This gives realistic "rest days" based on the data timeline
        if last_match_date:
            last_dt = datetime.strptime(last_match_date[:10], "%Y-%m-%d")
            days_rest = (reference_dt - last_dt).days
        else:
            days_rest = 7

        # Matches in last 7, 14 and 30 days (relative to database's most recent date)
        date_7d = (reference_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        date_14d = (reference_dt - timedelta(days=14)).strftime("%Y-%m-%d")
        date_30d = (reference_dt - timedelta(days=30)).strftime("%Y-%m-%d")

        matches_7d = [m for m in recent_matches if m.get('date', '') >= date_7d]
        matches_14d = sum(1 for m in recent_matches if m.get('date', '') >= date_14d)
        matches_30d = sum(1 for m in recent_matches if m.get('date', '') >= date_30d)

        # Calculate difficulty points for last 7 days
        difficulty_7d = sum(
            self.calculate_match_difficulty(m, player_id)
            for m in matches_7d
        )

        # Calculate fatigue score
        optimal_rest = FATIGUE_SETTINGS["optimal_rest_days"]
        rust_start = FATIGUE_SETTINGS.get("rust_start_days", 7)
        max_rest = FATIGUE_SETTINGS["max_rest_days"]
        difficulty_threshold = FATIGUE_SETTINGS.get("difficulty_overload_threshold", 6.0)

        # Rest days component (0-40 points)
        # Use smooth transitions to avoid discontinuities
        rust_penalty = 0
        if days_rest < optimal_rest:
            # Not enough rest - score scales up smoothly
            rest_score = days_rest / optimal_rest * 40
        elif days_rest <= rust_start:
            # Optimal rest window (3-7 days) - full points
            rest_score = 40
        else:
            # Rust penalty using smooth curve instead of stepped thresholds
            # Starts gentle, increases gradually
            rust_days = days_rest - rust_start
            # Sigmoid-like curve: penalty grows faster at first, then tapers
            rust_max = FATIGUE_SETTINGS.get("rust_max_penalty", 25)
            rust_tau = FATIGUE_SETTINGS.get("rust_tau", 8)
            rust_penalty = rust_max * (1 - math.exp(-rust_days / rust_tau))
            rest_score = max(25, 40 - rust_penalty)  # Floor at 25 (never completely rust out)

        # Workload component (0-40 points) - gradual penalties for activity
        overplay_14 = FATIGUE_SETTINGS["overplay_window_14"]  # 5
        overplay_30 = FATIGUE_SETTINGS["overplay_window_30"]  # 10

        # Start with full workload score
        workload_score = 40
        workload_penalty = 0

        # Gradual penalty based on difficulty in last 7 days
        # 0-3 pts: no penalty (light activity)
        # 3-6 pts: gradual penalty (~1 pt per difficulty point)
        # >6 pts: steeper penalty (5 pts per point over threshold)
        # Cap each component to prevent runaway penalties
        difficulty_penalty = 0
        if difficulty_7d > 3.0:
            if difficulty_7d <= difficulty_threshold:
                difficulty_penalty = (difficulty_7d - 3.0) * 1.0
            else:
                difficulty_penalty = (difficulty_threshold - 3.0) * 1.0
                difficulty_penalty += (difficulty_7d - difficulty_threshold) * 5
        workload_penalty += min(difficulty_penalty, 20)  # Cap difficulty component at 20

        # Gradual penalty for matches in 14 days
        # 0-2 matches: no penalty (well-rested but match sharp)
        # 3-5 matches: gradual penalty (~1.5 pts per match over 2)
        # >5 matches: steeper penalty (3 pts per match over 5)
        match_14d_penalty = 0
        if matches_14d > 2:
            if matches_14d <= overplay_14:
                match_14d_penalty = (matches_14d - 2) * 1.5
            else:
                match_14d_penalty = (overplay_14 - 2) * 1.5
                match_14d_penalty += (matches_14d - overplay_14) * 3
        workload_penalty += min(match_14d_penalty, 15)  # Cap 14d component at 15

        # Gradual penalty for matches in 30 days
        # 0-6 matches: no penalty
        # 7-10 matches: gradual penalty (~0.5 pts per match over 6)
        # >10 matches: steeper penalty (2 pts per match over 10)
        match_30d_penalty = 0
        if matches_30d > 6:
            if matches_30d <= overplay_30:
                match_30d_penalty = (matches_30d - 6) * 0.5
            else:
                match_30d_penalty = (overplay_30 - 6) * 0.5
                match_30d_penalty += (matches_30d - overplay_30) * 2
        workload_penalty += min(match_30d_penalty, 10)  # Cap 30d component at 10

        # Total workload penalty capped at 40 (full workload score)
        workload_penalty = min(workload_penalty, 40)
        workload_score = 40 - workload_penalty

        # Base fitness score (20 points)
        base_score = 20

        total_score = rest_score + workload_score + base_score

        # Determine status
        if total_score >= 75:
            status = "Fresh"
        elif total_score >= 60:
            status = "Good"
        elif total_score >= 45:
            status = "Moderate"
        elif total_score >= 30:
            status = "Tired"
        else:
            status = "Fatigued"

        return {
            "score": round(total_score, 1),
            "days_since_match": days_rest,
            "matches_7d": len(matches_7d),
            "matches_14d": matches_14d,
            "matches_30d": matches_30d,
            "difficulty_7d": round(difficulty_7d, 1),
            "status": status,
            "rest_component": round(rest_score, 1),
            "workload_component": round(workload_score, 1),
            "rust_penalty": round(rust_penalty, 1),
        }

    # =========================================================================
    # INJURY STATUS
    # =========================================================================

    def get_injury_status(self, player_id: int) -> Dict:
        """
        Get injury status for a player.
        """
        injuries = self.db.get_player_injuries(player_id, active_only=True)

        # Calculate retirement rate from recent matches
        recent_matches = self.db.get_player_matches(player_id, limit=20)
        retirements = sum(1 for m in recent_matches
                        if m.get('score', '').upper().endswith(('RET', 'W/O', 'DEF')))
        retirement_rate = retirements / len(recent_matches) if recent_matches else 0

        # Score calculation
        if not injuries:
            if retirement_rate > 0.1:
                score = 70
                status = "Concern (retirements)"
            else:
                score = 100
                status = "Healthy"
        else:
            most_recent = injuries[0]
            injury_status = most_recent.get('status', 'Unknown')

            status_scores = {
                'Minor Concern': 80,
                'Questionable': 60,
                'Doubtful': 40,
                'Out': 0,
                'Returning': 70,
            }
            score = status_scores.get(injury_status, 50)
            status = injury_status

        return {
            "score": score,
            "status": status,
            "active_injuries": len(injuries),
            "injuries": injuries,
            "retirement_rate": round(retirement_rate, 3),
        }

    # =========================================================================
    # NEW FACTORS: Opponent Quality, Recency, Recent Loss, Momentum
    # =========================================================================

    def calculate_opponent_quality(self, player_id: int) -> Dict:
        """
        Calculate opponent quality weighted score.
        Wins against higher-ranked opponents are worth more than wins against lower-ranked.
        Also applies recency weighting - recent matches count more.

        Returns score from -1 to 1 (positive = winning against quality opponents).
        """
        num_matches = OPPONENT_QUALITY_SETTINGS["matches_to_analyze"]
        max_rank = OPPONENT_QUALITY_SETTINGS["max_rank_for_bonus"]
        default_rank = OPPONENT_QUALITY_SETTINGS["unranked_default"]

        matches = self.db.get_player_matches(player_id, limit=num_matches)

        if not matches:
            return {
                "score": 0,
                "weighted_score": 0,
                "matches_analyzed": 0,
                "details": [],
                "has_data": False
            }

        today = datetime.now()
        weighted_score = 0
        total_weight = 0
        details = []

        # Get canonical ID for alias matching
        player_canonical = self.db.get_canonical_id(player_id)

        for m in matches:
            winner_canonical = self.db.get_canonical_id(m.get('winner_id'))
            won = winner_canonical == player_canonical
            opp_id = m.get('loser_id') if won else m.get('winner_id')

            # Get opponent ranking - try cache first, then database
            opp = self.db.get_player(opp_id)
            opp_name = opp.get('name', '') if opp else ''
            opp_rank = self._get_ranking_from_cache(opp_name)
            if opp_rank is None and opp:
                opp_rank = opp.get('current_ranking') or opp.get('ranking')

            if opp_rank is None or not isinstance(opp_rank, (int, float)):
                opp_rank = default_rank

            # Ensure opp_rank is numeric
            try:
                opp_rank = int(opp_rank)
            except (TypeError, ValueError):
                opp_rank = default_rank

            # Get match date for recency weighting
            date_str = m.get('date', '')[:10]
            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except (ValueError, TypeError):
                days_ago = 90

            # Recency multiplier: recent matches count more
            if days_ago <= 14:
                recency_mult = 1.0
            elif days_ago <= 30:
                recency_mult = 0.7
            elif days_ago <= 60:
                recency_mult = 0.4
            else:
                recency_mult = 0.2  # Matches > 60 days old barely count

            # Quality weight: higher for better opponents
            # 1 + (200 - rank) / 200 gives range 1.0 to 2.0
            quality_weight = 1 + (max_rank - min(opp_rank, max_rank)) / max_rank

            # Combined weight = quality * recency
            combined_weight = quality_weight * recency_mult

            if won:
                weighted_score += combined_weight
            else:
                # Losses weighted slightly less (0.8x)
                weighted_score -= combined_weight * 0.8

            total_weight += combined_weight

            result = 'W' if won else 'L'
            opp_name = opp.get('name', 'Unknown')[:20] if opp else 'Unknown'
            details.append({
                'result': result,
                'opponent': opp_name,
                'opponent_rank': opp_rank,
                'days_ago': days_ago,
                'quality_weight': round(quality_weight, 2),
                'recency_mult': recency_mult,
                'combined_weight': round(combined_weight, 2)
            })

        # Normalize to -1 to 1 range
        normalized = weighted_score / total_weight if total_weight > 0 else 0

        return {
            "score": round(normalized, 3),
            "weighted_score": round(weighted_score, 3),
            "matches_analyzed": len(matches),
            "details": details,
            "has_data": len(matches) >= 3
        }

    def calculate_recency_score(self, player_id: int) -> Dict:
        """
        Calculate recency-weighted form score.
        Recent matches (last 7 days) matter more than older matches.

        Returns score from -1 to 1 (positive = winning recent matches).
        """
        num_matches = RECENCY_SETTINGS["matches_to_analyze"]

        matches = self.db.get_player_matches(player_id, limit=num_matches)

        if not matches:
            return {
                "score": 0,
                "weighted_score": 0,
                "matches_analyzed": 0,
                "details": [],
                "has_data": False
            }

        today = datetime.now()
        weighted_score = 0
        total_weight = 0
        details = []

        # Get canonical ID for alias matching
        player_canonical = self.db.get_canonical_id(player_id)

        for m in matches:
            winner_canonical = self.db.get_canonical_id(m.get('winner_id'))
            won = winner_canonical == player_canonical
            date_str = m.get('date', '')[:10]

            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except (ValueError, TypeError):
                days_ago = 90  # Default to old if can't parse

            # Recency weight based on how recent the match is
            if days_ago <= 7:
                recency_weight = RECENCY_SETTINGS["weight_7d"]
            elif days_ago <= 30:
                recency_weight = RECENCY_SETTINGS["weight_30d"]
            elif days_ago <= 90:
                recency_weight = RECENCY_SETTINGS["weight_90d"]
            else:
                recency_weight = RECENCY_SETTINGS["weight_old"]

            if won:
                weighted_score += recency_weight
            else:
                weighted_score -= recency_weight

            total_weight += recency_weight

            result = 'W' if won else 'L'
            details.append({
                'result': result,
                'date': date_str,
                'days_ago': days_ago,
                'recency_weight': recency_weight
            })

        # Normalize to -1 to 1 range
        normalized = weighted_score / total_weight if total_weight > 0 else 0

        return {
            "score": round(normalized, 3),
            "weighted_score": round(weighted_score, 3),
            "matches_analyzed": len(matches),
            "details": details,
            "has_data": len(matches) >= 3
        }

    def calculate_recent_loss_penalty(self, player_id: int) -> Dict:
        """
        Calculate penalty for coming off a recent loss.
        Players who just lost may have psychological or physical issues.

        Returns penalty from 0 to -0.2 (negative = penalty).
        """
        matches = self.db.get_player_matches(player_id, limit=3)

        if not matches:
            return {
                "penalty": 0,
                "details": [],
                "has_recent_loss": False
            }

        today = datetime.now()
        penalty = 0
        details = []

        # Get canonical ID for alias matching
        player_canonical = self.db.get_canonical_id(player_id)

        for m in matches:
            winner_canonical = self.db.get_canonical_id(m.get('winner_id'))
            won = winner_canonical == player_canonical
            if won:
                continue  # Only interested in losses

            date_str = m.get('date', '')[:10]
            score = m.get('score', '')

            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except (ValueError, TypeError):
                days_ago = 30  # Default to old if can't parse

            # Check if it was a 5-setter (marathon loss)
            is_5_setter = score.count(',') >= 4 or score.count('-') >= 5

            if days_ago <= 3:
                penalty += RECENT_LOSS_SETTINGS["penalty_3d"]
                details.append(f"Loss {days_ago}d ago -> -{RECENT_LOSS_SETTINGS['penalty_3d']:.2f}")
            elif days_ago <= 7:
                penalty += RECENT_LOSS_SETTINGS["penalty_7d"]
                details.append(f"Loss {days_ago}d ago -> -{RECENT_LOSS_SETTINGS['penalty_7d']:.2f}")

            if is_5_setter and days_ago <= 7:
                penalty += RECENT_LOSS_SETTINGS["five_set_penalty"]
                details.append(f"5-set loss -> additional -{RECENT_LOSS_SETTINGS['five_set_penalty']:.2f}")

            break  # Only check most recent loss

        if not details:
            details.append("No recent losses")

        return {
            "penalty": round(-penalty, 3),  # Return as negative
            "details": details,
            "has_recent_loss": penalty > 0
        }

    def calculate_momentum(self, player_id: int, surface: str) -> Dict:
        """
        Calculate tournament/recent momentum bonus.
        Players with wins in the current tournament or on same surface get a bonus.

        Returns bonus from 0 to 0.1 (positive = momentum bonus).
        """
        window_days = MOMENTUM_SETTINGS["window_days"]
        win_bonus = MOMENTUM_SETTINGS["win_bonus"]
        max_bonus = MOMENTUM_SETTINGS["max_bonus"]

        matches = self.db.get_player_matches(player_id, limit=5)

        if not matches:
            return {
                "bonus": 0,
                "wins_counted": 0,
                "details": [],
                "has_momentum": False
            }

        today = datetime.now()
        bonus = 0
        wins_counted = 0
        details = []

        # Get canonical ID for alias matching
        player_canonical = self.db.get_canonical_id(player_id)

        for m in matches:
            winner_canonical = self.db.get_canonical_id(m.get('winner_id'))
            won = winner_canonical == player_canonical
            if not won:
                continue

            date_str = m.get('date', '')[:10]
            match_surface = m.get('surface', '')

            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except (ValueError, TypeError):
                days_ago = 30

            # Only count wins in the window and on same surface
            if days_ago <= window_days and match_surface == surface:
                bonus += win_bonus
                wins_counted += 1
                details.append(f"Win on {surface} {days_ago}d ago -> +{win_bonus:.2f}")

        # Cap at maximum
        bonus = min(bonus, max_bonus)

        if not details:
            details.append("No recent tournament wins on this surface")

        return {
            "bonus": round(bonus, 3),
            "wins_counted": wins_counted,
            "details": details,
            "has_momentum": bonus > 0
        }

    # =========================================================================
    # BREAKOUT DETECTION
    # =========================================================================

    def calculate_breakout_signal(self, player_id: int, as_of_date: str = None) -> Dict:
        """
        Detect if a player is in a breakout phase — recent results dramatically
        outperforming their ranking. Returns an effective ranking adjustment.

        Breakout = multiple quality wins (against much higher-ranked opponents)
        clustered in a short time window, adjusted for player age.
        """
        settings = BREAKOUT_SETTINGS

        # Get player data
        player = self.db.get_player(player_id)
        if not player:
            return self._empty_breakout_result()

        canonical_id = self.db.get_canonical_id(player_id)
        player_rank = self._get_ranking_by_id(canonical_id)
        if not player_rank:
            player_rank = player.get('current_ranking')
        if not player_rank or player_rank < settings['min_ranking']:
            return self._empty_breakout_result(
                details=f"Rank {player_rank} below threshold {settings['min_ranking']}"
            )

        # Calculate age from dob
        age = None
        dob = player.get('dob')
        if dob:
            try:
                ref_date = datetime.strptime(as_of_date, "%Y-%m-%d") if as_of_date else datetime.now()
                birth_date = datetime.strptime(str(dob)[:10], "%Y-%m-%d")
                age = (ref_date - birth_date).days // 365
            except (ValueError, TypeError):
                pass

        # Get recent matches
        matches = self.db.get_player_matches(player_id, limit=40)
        ref_date = datetime.strptime(as_of_date, "%Y-%m-%d") if as_of_date else datetime.now()

        # Filter to matches before as_of_date
        if as_of_date:
            matches = [m for m in matches if m.get('date') and m['date'][:10] < as_of_date]

        cluster_window = settings['cluster_window_days']
        quality_threshold = settings['quality_win_threshold']

        # Find quality wins within the cluster window
        quality_wins = []
        for m in matches:
            date_str = (m.get('date') or '')[:10]
            try:
                match_date = datetime.strptime(date_str, "%Y-%m-%d")
                days_ago = (ref_date - match_date).days
            except (ValueError, TypeError):
                continue

            if days_ago > cluster_window or days_ago < 0:
                continue

            # Check if player won
            winner_canonical = self.db.get_canonical_id(m.get('winner_id'))
            if winner_canonical != canonical_id:
                continue

            # Get opponent rank
            opp_rank = m.get('loser_rank')
            if opp_rank is None or not isinstance(opp_rank, (int, float)):
                opp_id = m.get('loser_id')
                looked_up = self._get_ranking_by_id(opp_id) if opp_id else None
                opp_rank = looked_up if looked_up else None

            if opp_rank is None:
                continue

            # Quality threshold: opponent must be ranked significantly better
            rank_threshold = int(player_rank * quality_threshold)
            if opp_rank <= rank_threshold:
                quality_wins.append({
                    'date': date_str,
                    'opponent_name': m.get('loser_name', 'Unknown'),
                    'opponent_rank': int(opp_rank),
                    'days_ago': days_ago,
                    'rank_ratio': round(opp_rank / player_rank, 3),
                    'tournament': m.get('tournament', ''),
                })

        # Need minimum quality wins to trigger
        if len(quality_wins) < settings['min_quality_wins']:
            return self._empty_breakout_result(
                details=f"Only {len(quality_wins)} quality wins (need {settings['min_quality_wins']})"
            )

        # Calculate implied ranking from quality wins
        avg_opp_rank = sum(w['opponent_rank'] for w in quality_wins) / len(quality_wins)
        implied_ranking = int(avg_opp_rank * settings['implied_rank_buffer'])
        implied_ranking = max(implied_ranking, 50)  # Floor at 50

        # Calculate age multiplier
        if age is not None:
            if age <= settings['peak_breakout_age']:
                age_mult = settings['young_age_multiplier']
            elif age <= settings['max_breakout_age']:
                age_mult = settings['neutral_age_multiplier']
            else:
                age_mult = settings['old_age_multiplier']
        else:
            age_mult = settings['neutral_age_multiplier']

        # Calculate blend factor
        num_wins = len(quality_wins)
        blend = settings['base_blend'] + (num_wins - settings['min_quality_wins']) * settings['per_extra_win_blend']
        blend = min(blend, settings['max_blend'])
        blend *= age_mult
        blend = min(blend, 0.85)  # Hard cap

        # Calculate effective ranking
        effective_ranking = int(player_rank * (1 - blend) + implied_ranking * blend)
        effective_ranking = max(effective_ranking, implied_ranking)  # Never worse than implied
        effective_ranking = min(effective_ranking, player_rank)      # Never worse than actual

        win_strs = [f"{w['opponent_name']} (#{w['opponent_rank']}, {w['days_ago']}d ago)" for w in quality_wins]
        details = (
            f"BREAKOUT: {num_wins} quality wins in {cluster_window}d. "
            f"Rank #{player_rank} -> Effective #{effective_ranking} "
            f"(implied #{implied_ranking}, blend {blend:.0%}, age {age or '?'}, age_mult {age_mult:.1f}). "
            f"Wins: {', '.join(win_strs)}"
        )

        return {
            'breakout_detected': True,
            'effective_ranking': effective_ranking,
            'actual_ranking': player_rank,
            'implied_ranking': implied_ranking,
            'breakout_score': round(blend, 3),
            'quality_wins': quality_wins,
            'num_quality_wins': num_wins,
            'age': age,
            'age_multiplier': round(age_mult, 2),
            'blend_factor': round(blend, 3),
            'details': details,
        }

    def _empty_breakout_result(self, details: str = "No breakout detected") -> Dict:
        """Return a neutral breakout result."""
        return {
            'breakout_detected': False,
            'effective_ranking': None,
            'actual_ranking': None,
            'implied_ranking': None,
            'breakout_score': 0,
            'quality_wins': [],
            'num_quality_wins': 0,
            'age': None,
            'age_multiplier': 1.0,
            'blend_factor': 0,
            'details': details,
        }

    # =========================================================================
    # MATCH CONTEXT — TOURNAMENT LEVEL AWARENESS
    # =========================================================================

    def determine_player_home_level(self, player_id: int, as_of_date: str = None) -> int:
        """
        Determine a player's 'home' tournament level.
        Uses ranking as primary signal (most reliable), with match history as fallback.
        Returns level: 1=ITF, 2=Challenger, 3=ATP/WTA, 4=Grand Slam.

        Ranking-based (primary): Many tournaments use city names without tour designation
        (e.g., "Auckland", "Beijing"), making match history unreliable for level detection.
        A player's ranking directly indicates their competitive level.
        """
        # Primary: ranking-based determination
        canonical_id = self.db.get_canonical_id(player_id)
        rank = self._get_ranking_by_id(canonical_id)
        if not rank:
            player = self.db.get_player(player_id)
            rank = player.get('current_ranking') if player else None

        if rank:
            if rank <= 200:
                return 3  # ATP/WTA level
            elif rank <= 500:
                # Check match history to distinguish WTA/Challenger crossover
                history_level = self._home_level_from_history(player_id, as_of_date)
                # If they have Grand Slam or WTA/ATP appearances, they're level 3
                if history_level >= 3:
                    return 3
                return 2  # Challenger level
            elif rank <= 1000:
                return 2  # Challenger level
            else:
                return 1  # ITF level

        # Fallback: match history
        return self._home_level_from_history(player_id, as_of_date)

    def _home_level_from_history(self, player_id: int, as_of_date: str = None) -> int:
        """Determine home level from match history (fallback method)."""
        hierarchy = MATCH_CONTEXT_SETTINGS["level_hierarchy"]

        matches = self.db.get_player_matches(player_id, limit=20)
        if as_of_date:
            matches = [m for m in matches if m.get('date') and m['date'][:10] < as_of_date]

        if not matches:
            return 2  # Default to Challenger

        levels = []
        for m in matches:
            tournament = m.get('tournament') or m.get('tourney_name') or ''
            tour_level = get_tour_level(tournament)
            level_num = hierarchy.get(tour_level, 2)
            levels.append(level_num)

        # Return the most common non-Unknown level, or max if Unknown dominates
        counter = Counter(levels)
        return counter.most_common(1)[0][0]

    def get_match_context(self, p1_id: int, p2_id: int, tournament: str = None,
                          as_of_date: str = None) -> Dict:
        """
        Compute match context: level mismatch detection, displacement discounts,
        and context warnings.
        """
        settings = MATCH_CONTEXT_SETTINGS
        hierarchy = settings["level_hierarchy"]
        warnings = []

        # Determine match level from tournament name
        if tournament:
            tour_level_str = get_tour_level(tournament)
            match_level = hierarchy.get(tour_level_str, 2)
        else:
            match_level = None  # Can't determine without tournament

        # If we can't determine match level, return neutral context
        if match_level is None:
            return {
                'match_level': None,
                'match_level_str': 'Unknown',
                'p1_home_level': None,
                'p2_home_level': None,
                'p1_displacement': 0,
                'p2_displacement': 0,
                'p1_discount': 0.0,
                'p2_discount': 0.0,
                'warnings': [],
            }

        # Determine each player's home level
        p1_home = self.determine_player_home_level(p1_id, as_of_date)
        p2_home = self.determine_player_home_level(p2_id, as_of_date)

        # Calculate displacement (positive = playing below home level)
        p1_displacement = max(0, p1_home - match_level)
        p2_displacement = max(0, p2_home - match_level)

        # Calculate discount
        discount_per = settings["discount_per_level"]
        max_discount = settings["max_discount"]
        p1_discount = min(p1_displacement * discount_per, max_discount)
        p2_discount = min(p2_displacement * discount_per, max_discount)

        # Level name lookup (reverse)
        level_names = {v: k for k, v in hierarchy.items() if k != "Unknown"}
        level_names[1] = "ITF"
        level_names[2] = "Challenger"
        level_names[3] = "ATP/WTA"
        level_names[4] = "Grand Slam"

        match_level_str = level_names.get(match_level, "Unknown")

        # Generate warnings
        if settings.get("level_mismatch_warning"):
            if p1_displacement > 0:
                p1_name = self._get_player_name(p1_id)
                warnings.append(
                    f"LEVEL MISMATCH: {p1_name} normally plays {level_names.get(p1_home, '?')} "
                    f"level but this match is {match_level_str} "
                    f"({p1_displacement} level{'s' if p1_displacement > 1 else ''} below, "
                    f"{p1_discount:.0%} discount on ranking/elo/h2h)"
                )
            if p2_displacement > 0:
                p2_name = self._get_player_name(p2_id)
                warnings.append(
                    f"LEVEL MISMATCH: {p2_name} normally plays {level_names.get(p2_home, '?')} "
                    f"level but this match is {match_level_str} "
                    f"({p2_displacement} level{'s' if p2_displacement > 1 else ''} below, "
                    f"{p2_discount:.0%} discount on ranking/elo/h2h)"
                )

        return {
            'match_level': match_level,
            'match_level_str': match_level_str,
            'p1_home_level': p1_home,
            'p2_home_level': p2_home,
            'p1_displacement': p1_displacement,
            'p2_displacement': p2_displacement,
            'p1_discount': p1_discount,
            'p2_discount': p2_discount,
            'warnings': warnings,
        }

    def _get_player_name(self, player_id: int) -> str:
        """Get player name by ID for warning messages."""
        player = self.db.get_player(player_id)
        if player:
            return player.get('name', f'Player #{player_id}')
        return f'Player #{player_id}'

    # =========================================================================
    # MAIN PROBABILITY MODEL
    # =========================================================================

    def calculate_win_probability(self, player1_id: int, player2_id: int,
                                   surface: str, match_date: str = None,
                                   p1_odds: float = None, p2_odds: float = None,
                                   tournament: str = None) -> Dict:
        """
        Calculate win probability for player1 against player2.
        Returns comprehensive analysis with probability.

        p1_odds/p2_odds: Optional Betfair odds, used to estimate ranking for
                         WTA/unranked players.
        """
        match_date = (match_date or datetime.now().strftime("%Y-%m-%d"))[:10]

        # Compute match context (level mismatch detection)
        match_context = self.get_match_context(player1_id, player2_id, tournament, match_date)
        context_match_level = match_context.get('match_level')
        context_warnings = list(match_context.get('warnings', []))

        # Get all factor scores in parallel for better performance
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                'p1_form': executor.submit(self.calculate_form_score, player1_id, None, match_date, context_match_level),
                'p2_form': executor.submit(self.calculate_form_score, player2_id, None, match_date, context_match_level),
                'p1_surface': executor.submit(self.get_surface_stats, player1_id, surface),
                'p2_surface': executor.submit(self.get_surface_stats, player2_id, surface),
                'rankings': executor.submit(self.get_ranking_factors, player1_id, player2_id, p1_odds, p2_odds),
                'h2h': executor.submit(self.get_h2h, player1_id, player2_id, surface),
                'p1_fatigue': executor.submit(self.calculate_fatigue, player1_id, match_date),
                'p2_fatigue': executor.submit(self.calculate_fatigue, player2_id, match_date),
                'p1_injury': executor.submit(self.get_injury_status, player1_id),
                'p2_injury': executor.submit(self.get_injury_status, player2_id),
                'p1_opp_quality': executor.submit(self.calculate_opponent_quality, player1_id),
                'p2_opp_quality': executor.submit(self.calculate_opponent_quality, player2_id),
                'p1_recency': executor.submit(self.calculate_recency_score, player1_id),
                'p2_recency': executor.submit(self.calculate_recency_score, player2_id),
                'p1_loss_penalty': executor.submit(self.calculate_recent_loss_penalty, player1_id),
                'p2_loss_penalty': executor.submit(self.calculate_recent_loss_penalty, player2_id),
                'p1_momentum': executor.submit(self.calculate_momentum, player1_id, surface),
                'p2_momentum': executor.submit(self.calculate_momentum, player2_id, surface),
                'perf_elo': executor.submit(self.get_performance_elo_factors, player1_id, player2_id, p1_odds, p2_odds),
                'p1_breakout': executor.submit(self.calculate_breakout_signal, player1_id, match_date),
                'p2_breakout': executor.submit(self.calculate_breakout_signal, player2_id, match_date),
            }

            # Collect results
            results = {key: future.result() for key, future in futures.items()}

        p1_form = results['p1_form']
        p2_form = results['p2_form']
        p1_surface = results['p1_surface']
        p2_surface = results['p2_surface']
        rankings = results['rankings']
        h2h = results['h2h']
        p1_fatigue = results['p1_fatigue']
        p2_fatigue = results['p2_fatigue']
        p1_injury = results['p1_injury']
        p2_injury = results['p2_injury']
        p1_opp_quality = results['p1_opp_quality']
        p2_opp_quality = results['p2_opp_quality']
        p1_recency = results['p1_recency']
        p2_recency = results['p2_recency']
        p1_loss_penalty = results['p1_loss_penalty']
        p2_loss_penalty = results['p2_loss_penalty']
        p1_momentum = results['p1_momentum']
        p2_momentum = results['p2_momentum']
        perf_elo = results['perf_elo']
        p1_breakout = results['p1_breakout']
        p2_breakout = results['p2_breakout']

        # If breakout detected, recompute ranking and perf_elo with effective rankings
        either_breakout = p1_breakout.get('breakout_detected') or p2_breakout.get('breakout_detected')
        p1_eff_rank = p1_breakout.get('effective_ranking') if p1_breakout.get('breakout_detected') else None
        p2_eff_rank = p2_breakout.get('effective_ranking') if p2_breakout.get('breakout_detected') else None

        if either_breakout:
            rankings = self.get_ranking_factors(
                player1_id, player2_id, p1_odds, p2_odds,
                p1_effective_rank=p1_eff_rank, p2_effective_rank=p2_eff_rank
            )
            perf_elo = self.get_performance_elo_factors(
                player1_id, player2_id, p1_odds, p2_odds,
                p1_effective_rank=p1_eff_rank, p2_effective_rank=p2_eff_rank
            )

        # Check data availability
        p1_has_form_data = p1_form.get('has_data', False)
        p2_has_form_data = p2_form.get('has_data', False)
        p1_has_surface_data = p1_surface.get('has_data', False)
        p2_has_surface_data = p2_surface.get('has_data', False)

        # Determine if we should use ranking-based fallback
        use_ranking_fallback = not (p1_has_form_data and p2_has_form_data)

        # Calculate advantage scores for each factor (-1 to 1, positive = P1 advantage)
        factors = {}

        # Loss quality signal — computed once, applied to form and surface
        # "Who do you lose to?" reveals true level across all factors
        # Consistency dampening: when losses are scattered (high std dev),
        # the average is unreliable, so we reduce the stability adjustment.
        loss_quality_diff = 0
        max_stability = FORM_SETTINGS.get("max_stability_adjustment", 0.20)
        if p1_has_form_data and p2_has_form_data:
            p1_losses = [d for d in p1_form['details'] if not d['won']]
            p2_losses = [d for d in p2_form['details'] if not d['won']]
            if p1_losses and p2_losses:
                # Convert each loss opponent rank to Elo individually
                p1_loss_elos = [self._ranking_to_elo(int(d['opponent_rank'])) for d in p1_losses]
                p2_loss_elos = [self._ranking_to_elo(int(d['opponent_rank'])) for d in p2_losses]

                p1_mean_loss_elo = sum(p1_loss_elos) / len(p1_loss_elos)
                p2_mean_loss_elo = sum(p2_loss_elos) / len(p2_loss_elos)

                # Positive = P2 loses to stronger opponents (P2 more stable)
                loss_quality_diff = (p2_mean_loss_elo - p1_mean_loss_elo) / 400

                # Consistency dampening: reduce adjustment when losses are scattered
                # A player losing to #66 AND #470 has unreliable average loss quality
                min_losses = FORM_SETTINGS.get("loss_consistency_min_losses", 2)
                if len(p1_loss_elos) >= min_losses and len(p2_loss_elos) >= min_losses:
                    import statistics
                    p1_std = statistics.stdev(p1_loss_elos)
                    p2_std = statistics.stdev(p2_loss_elos)
                    max_std = max(p1_std, p2_std)
                    baseline = FORM_SETTINGS.get("loss_consistency_baseline", 150)
                    steepness = FORM_SETTINGS.get("loss_consistency_steepness", 2.0)
                    consistency = 1.0 / (1.0 + (max_std / baseline) ** steepness)
                    loss_quality_diff *= consistency

        # Form advantage - only use if both players have data
        # Apply diminishing returns (tanh) so extreme form gaps can't dominate
        if p1_has_form_data and p2_has_form_data:
            raw_form_diff = (p1_form['score'] - p2_form['score']) / 100
            max_adv = FORM_SETTINGS.get("max_form_advantage", 0.10)
            factors['form'] = max_adv * math.tanh(raw_form_diff / max_adv)

            # Loss quality stability adjustment on form
            if loss_quality_diff != 0:
                stability_adj = -max_stability * math.tanh(loss_quality_diff / 0.40)
                factors['form'] += stability_adj
            # Cap total form advantage (raw tanh + stability) to prevent runaway values
            max_total = max_adv + max_stability
            factors['form'] = max(-max_total, min(max_total, factors['form']))
        else:
            factors['form'] = 0  # Neutral if no data

        # Surface advantage - only use if both players have data
        if p1_has_surface_data and p2_has_surface_data:
            surface_diff = p1_surface['combined_win_rate'] - p2_surface['combined_win_rate']
            factors['surface'] = surface_diff

            # Loss quality adjustment on surface — win rates are quality-blind
            # A 61.5% hard court rate vs Grand Slam opponents is better than
            # 63.6% against ITF opponents. Same stability signal applies.
            if loss_quality_diff != 0:
                surface_stability = -max_stability * 0.5 * math.tanh(loss_quality_diff / 0.40)
                factors['surface'] += surface_stability
        else:
            factors['surface'] = 0  # Neutral if no data

        # Ranking advantage - always available
        factors['ranking'] = rankings['rank_advantage']

        # H2H advantage
        factors['h2h'] = h2h['advantage']

        # Fatigue advantage
        fatigue_diff = (p1_fatigue['score'] - p2_fatigue['score']) / 100
        factors['fatigue'] = fatigue_diff

        # Injury advantage
        injury_diff = (p1_injury['score'] - p2_injury['score']) / 100
        factors['injury'] = injury_diff

        # NEW FACTORS

        # Opponent Quality advantage (-1 to 1)
        opp_quality_diff = p1_opp_quality['score'] - p2_opp_quality['score']
        factors['opponent_quality'] = opp_quality_diff

        # Recency advantage (-1 to 1)
        recency_diff = p1_recency['score'] - p2_recency['score']
        factors['recency'] = recency_diff

        # Recent Loss penalty (both are negative or zero)
        # P1 advantage if P2 has bigger penalty
        loss_penalty_diff = p1_loss_penalty['penalty'] - p2_loss_penalty['penalty']
        factors['recent_loss'] = loss_penalty_diff

        # Momentum advantage (both are positive or zero)
        momentum_diff = p1_momentum['bonus'] - p2_momentum['bonus']
        factors['momentum'] = momentum_diff

        # Performance Elo advantage
        factors['performance_elo'] = perf_elo['advantage']

        # Apply match context: asymmetric score discount for displaced players
        # When a player competes below their home level, their ranking/elo/h2h
        # advantages are less meaningful (e.g., WTA player at ITF event)
        p1_discount = match_context.get('p1_discount', 0)
        p2_discount = match_context.get('p2_discount', 0)
        discounted_factors = MATCH_CONTEXT_SETTINGS.get("discounted_factors", [])

        if p1_discount > 0 or p2_discount > 0:
            for factor_name in discounted_factors:
                if factor_name not in factors:
                    continue
                score = factors[factor_name]
                # Positive score = P1 advantage, negative = P2 advantage
                # Only discount the advantage of the displaced player
                if score > 0 and p1_discount > 0:
                    # P1 has advantage AND P1 is displaced — discount it
                    factors[factor_name] = score * (1 - p1_discount)
                elif score < 0 and p2_discount > 0:
                    # P2 has advantage AND P2 is displaced — discount it
                    factors[factor_name] = score * (1 - p2_discount)

        # Add rust warnings from fatigue data
        rust_warn_days = MATCH_CONTEXT_SETTINGS.get("rust_warning_days", 10)
        p1_days_rest = p1_fatigue.get('days_since_match')
        p2_days_rest = p2_fatigue.get('days_since_match')
        if p1_days_rest and p1_days_rest > rust_warn_days:
            p1_name = self._get_player_name(player1_id)
            context_warnings.append(
                f"RUST: {p1_name} has not played in {p1_days_rest} days"
            )
        if p2_days_rest and p2_days_rest > rust_warn_days:
            p2_name = self._get_player_name(player2_id)
            context_warnings.append(
                f"RUST: {p2_name} has not played in {p2_days_rest} days"
            )

        # Add near-breakout warnings
        if MATCH_CONTEXT_SETTINGS.get("near_breakout_warning"):
            for label, bo in [("P1", p1_breakout), ("P2", p2_breakout)]:
                if not bo.get('breakout_detected') and bo.get('num_quality_wins', 0) == 1:
                    pid = player1_id if label == "P1" else player2_id
                    pname = self._get_player_name(pid)
                    context_warnings.append(
                        f"NEAR-BREAKOUT: {pname} has 1 quality win (needs 2 to trigger breakout)"
                    )

        # Adjust weights based on data availability and ranking gap
        adjusted_weights = self.weights.copy()

        # If no form/surface data, rely much more heavily on rankings
        if use_ranking_fallback:
            missing_weight = 0
            if not (p1_has_form_data and p2_has_form_data):
                missing_weight += adjusted_weights['form']
                adjusted_weights['form'] = 0
            if not (p1_has_surface_data and p2_has_surface_data):
                missing_weight += adjusted_weights['surface']
                adjusted_weights['surface'] = 0
            adjusted_weights['ranking'] += missing_weight

        # If neither player has Performance Elo data, redistribute to ranking
        if not perf_elo.get('p1_has_data') and not perf_elo.get('p2_has_data'):
            adjusted_weights['ranking'] += adjusted_weights.get('performance_elo', 0)
            adjusted_weights['performance_elo'] = 0

        # Dynamic weighting for large ranking gaps
        # When there's a huge skill gap, ranking should dominate
        # BUT: suppress when breakout detected (ranking is stale) OR when either
        # player is displaced 2+ levels below their home level (e.g., WTA player at ITF).
        # 1-level displacement (ATP player at Challenger) is normal and shouldn't suppress.
        is_large_gap = rankings.get('is_large_gap', False)
        elo_win_prob = rankings.get('elo_win_prob', 0.5)
        max_displacement = max(
            match_context.get('p1_displacement', 0),
            match_context.get('p2_displacement', 0)
        )
        significant_displacement = (max_displacement >= 2)

        if is_large_gap and not either_breakout and not significant_displacement:
            # For large gaps, boost ranking weight significantly
            # Reduce other factors' influence as the skill gap makes them less relevant
            gap_boost = 0.25  # Additional weight for ranking
            gap_reduction = gap_boost / 8  # Spread reduction across other factors (more factors now)

            adjusted_weights['ranking'] = min(adjusted_weights['ranking'] + gap_boost, 0.6)
            adjusted_weights['form'] = max(adjusted_weights['form'] - gap_reduction, 0.05)
            adjusted_weights['surface'] = max(adjusted_weights['surface'] - gap_reduction, 0.05)
            adjusted_weights['h2h'] = max(adjusted_weights['h2h'] - gap_reduction, 0.02)
            adjusted_weights['fatigue'] = max(adjusted_weights['fatigue'] - gap_reduction, 0.02)
            # Also reduce new factors for large gaps
            adjusted_weights['opponent_quality'] = max(adjusted_weights.get('opponent_quality', 0) - gap_reduction, 0.02)
            adjusted_weights['recency'] = max(adjusted_weights.get('recency', 0) - gap_reduction, 0.02)
            adjusted_weights['recent_loss'] = max(adjusted_weights.get('recent_loss', 0) - gap_reduction, 0.01)
            adjusted_weights['momentum'] = max(adjusted_weights.get('momentum', 0) - gap_reduction, 0.01)
            adjusted_weights['performance_elo'] = max(adjusted_weights.get('performance_elo', 0) - gap_reduction, 0.02)

        # Calculate weighted advantage
        weighted_advantage = sum(
            factors[key] * adjusted_weights[key]
            for key in factors
        )

        # Convert to probability using logistic function
        k = 3  # Steepness of curve
        model_probability = 1 / (1 + math.exp(-k * weighted_advantage))

        # For large ranking gaps, blend with Elo probability for more accuracy
        # This anchors extreme matchups closer to market expectations
        # BUT: suppress when breakout detected OR significant displacement (2+ levels)
        if is_large_gap and not either_breakout and not significant_displacement:
            # Check if form-based factors contradict the ranking
            form_based_advantage = (
                factors['form'] +
                factors['surface'] +
                factors.get('opponent_quality', 0) +
                factors.get('recency', 0) +
                factors.get('recent_loss', 0) +
                factors.get('momentum', 0) +
                factors.get('performance_elo', 0)
            )

            ranking_favors_p1 = factors['ranking'] > 0
            form_favors_p1 = form_based_advantage > 0

            if ranking_favors_p1 != form_favors_p1:
                p1_probability = 0.9 * model_probability + 0.1 * elo_win_prob
            else:
                p1_probability = 0.7 * model_probability + 0.3 * elo_win_prob
        else:
            p1_probability = model_probability

        # Confidence based on data quality, factor agreement, and prediction clarity
        confidence = self._calculate_confidence(
            p1_form, p2_form, p1_surface, p2_surface, h2h,
            factors, adjusted_weights, p1_probability, rankings
        )

        return {
            "p1_probability": round(p1_probability, 3),
            "p2_probability": round(1 - p1_probability, 3),
            "weighted_advantage": round(weighted_advantage, 3),
            "confidence": round(confidence, 2),
            "factors": {
                "form": {
                    "p1": p1_form,
                    "p2": p2_form,
                    "advantage": round(factors['form'], 3),
                    "weight": self.weights['form'],
                },
                "surface": {
                    "p1": p1_surface,
                    "p2": p2_surface,
                    "advantage": round(factors['surface'], 3),
                    "weight": self.weights['surface'],
                },
                "ranking": {
                    "data": rankings,
                    "advantage": round(factors['ranking'], 3),
                    "weight": self.weights['ranking'],
                },
                "h2h": {
                    "data": h2h,
                    "advantage": round(factors['h2h'], 3),
                    "weight": self.weights['h2h'],
                },
                "fatigue": {
                    "p1": p1_fatigue,
                    "p2": p2_fatigue,
                    "advantage": round(factors['fatigue'], 3),
                    "weight": self.weights['fatigue'],
                },
                "injury": {
                    "p1": p1_injury,
                    "p2": p2_injury,
                    "advantage": round(factors['injury'], 3),
                    "weight": self.weights['injury'],
                },
                # NEW FACTORS
                "opponent_quality": {
                    "p1": p1_opp_quality,
                    "p2": p2_opp_quality,
                    "advantage": round(factors['opponent_quality'], 3),
                    "weight": self.weights['opponent_quality'],
                },
                "recency": {
                    "p1": p1_recency,
                    "p2": p2_recency,
                    "advantage": round(factors['recency'], 3),
                    "weight": self.weights['recency'],
                },
                "recent_loss": {
                    "p1": p1_loss_penalty,
                    "p2": p2_loss_penalty,
                    "advantage": round(factors['recent_loss'], 3),
                    "weight": self.weights['recent_loss'],
                },
                "momentum": {
                    "p1": p1_momentum,
                    "p2": p2_momentum,
                    "advantage": round(factors['momentum'], 3),
                    "weight": self.weights['momentum'],
                },
                "performance_elo": {
                    "data": perf_elo,
                    "advantage": round(factors['performance_elo'], 3),
                    "weight": self.weights.get('performance_elo', 0.12),
                },
            },
            "breakout": {
                "p1": p1_breakout,
                "p2": p2_breakout,
            },
            "match_context": match_context,
            "context_warnings": context_warnings,
        }

    def _calculate_confidence(self, p1_form, p2_form, p1_surface, p2_surface, h2h,
                               factors: Dict, weights: Dict, p1_probability: float,
                               rankings: Dict) -> float:
        """
        Calculate confidence level (0-1) based on three components:
        1. Data Quality (40%) - match counts, recency, ranking availability
        2. Factor Agreement (30%) - how many factors point same direction
        3. Prediction Clarity (30%) - distance from 50/50
        """

        # =====================================================================
        # 1. DATA QUALITY (40% of confidence)
        # =====================================================================
        data_score = 0

        # Check if we have reliable data for both players
        p1_has_data = p1_form.get('has_data', False)
        p2_has_data = p2_form.get('has_data', False)

        # If either player has no form data, data quality is very low
        if not p1_has_data or not p2_has_data:
            data_score = 0.15 if (p1_has_data or p2_has_data) else 0.05
        else:
            # Form data (up to 0.4) - weighted by recency
            p1_matches = min(p1_form.get('matches', 0), 10) / 10
            p2_matches = min(p2_form.get('matches', 0), 10) / 10
            form_quality = (p1_matches + p2_matches) / 2
            data_score += form_quality * 0.4

            # Surface data (up to 0.25)
            p1_surface_matches = min(p1_surface.get('career_matches', 0), 20) / 20
            p2_surface_matches = min(p2_surface.get('career_matches', 0), 20) / 20
            surface_quality = (p1_surface_matches + p2_surface_matches) / 2
            data_score += surface_quality * 0.25

            # H2H data (up to 0.15)
            h2h_matches = min(h2h.get('total_matches', 0), 5) / 5
            data_score += h2h_matches * 0.15

            # Ranking availability (up to 0.2)
            p1_rank = rankings.get('p1_rank')
            p2_rank = rankings.get('p2_rank')
            if p1_rank and p2_rank:
                data_score += 0.2
            elif p1_rank or p2_rank:
                data_score += 0.1

        # =====================================================================
        # 2. FACTOR AGREEMENT (30% of confidence)
        # =====================================================================
        # Count how many factors agree on direction, weighted by factor weight
        agreement_score = 0

        # Get all factor advantages (positive = P1 favored, negative = P2 favored)
        factor_advantages = {
            'form': factors.get('form', 0),
            'surface': factors.get('surface', 0),
            'ranking': factors.get('ranking', 0),
            'h2h': factors.get('h2h', 0),
            'fatigue': factors.get('fatigue', 0),
            'injury': factors.get('injury', 0),
            'opponent_quality': factors.get('opponent_quality', 0),
            'recency': factors.get('recency', 0),
            'recent_loss': factors.get('recent_loss', 0),
            'momentum': factors.get('momentum', 0),
        }

        # Determine which player is favored overall
        p1_favored = p1_probability > 0.5

        # Count weighted agreement
        total_weight = 0
        agreement_weight = 0

        for factor_name, advantage in factor_advantages.items():
            weight = weights.get(factor_name, 0)
            if weight == 0:
                continue

            total_weight += weight

            # Check if this factor agrees with overall prediction
            factor_favors_p1 = advantage > 0
            factor_favors_p2 = advantage < 0
            factor_neutral = advantage == 0

            if factor_neutral:
                agreement_weight += weight * 0.5  # Neutral = partial agreement
            elif (p1_favored and factor_favors_p1) or (not p1_favored and factor_favors_p2):
                agreement_weight += weight  # Full agreement

        if total_weight > 0:
            agreement_score = agreement_weight / total_weight

        # =====================================================================
        # 3. PREDICTION CLARITY (30% of confidence)
        # =====================================================================
        # Distance from 50% - a 70% prediction is clearer than 52%
        distance_from_50 = abs(p1_probability - 0.5)
        # Scale: 0% at 50/50, 100% at 100/0
        # Max realistic distance is ~0.4 (90/10), so scale accordingly
        clarity_score = min(distance_from_50 / 0.4, 1.0)

        # =====================================================================
        # COMBINE COMPONENTS
        # =====================================================================
        # Data Quality: 40%, Factor Agreement: 30%, Prediction Clarity: 30%
        confidence = (data_score * 0.4) + (agreement_score * 0.3) + (clarity_score * 0.3)

        # Cap at reasonable bounds
        confidence = max(0.05, min(confidence, 0.95))

        return confidence

    # =========================================================================
    # SET BETTING PROBABILITIES
    # =========================================================================

    def calculate_set_probabilities(self, p1_prob: float, best_of: int = 3) -> Dict:
        """
        Calculate set betting probabilities based on match winner probability.
        Uses simplified model based on historical set patterns.
        """
        if best_of == 3:
            scores = SET_BETTING["bo3_scores"]
            # Estimate individual set win probability (slightly higher than match)
            p1_set = p1_prob ** 0.7  # Adjusted for set-level variance

            # 2-0: P1 wins both sets
            prob_2_0 = p1_set ** 2

            # 2-1: P1 wins 2 sets, loses 1 (3 ways this can happen, but only SF and FSS end 2-1)
            # Simplified: P(win) * P(lose) * P(win) * 2 combinations
            prob_2_1 = 2 * p1_set * (1 - p1_set) * p1_set

            # 0-2: P2 wins both sets
            prob_0_2 = (1 - p1_set) ** 2

            # 1-2: P2 wins 2 sets, loses 1
            prob_1_2 = 2 * (1 - p1_set) * p1_set * (1 - p1_set)

            # Normalize
            total = prob_2_0 + prob_2_1 + prob_0_2 + prob_1_2
            return {
                "2-0": round(prob_2_0 / total, 3),
                "2-1": round(prob_2_1 / total, 3),
                "0-2": round(prob_0_2 / total, 3),
                "1-2": round(prob_1_2 / total, 3),
            }
        else:  # Best of 5
            scores = SET_BETTING["bo5_scores"]
            p1_set = p1_prob ** 0.7

            # 3-0
            prob_3_0 = p1_set ** 3

            # 3-1 (4 ways)
            prob_3_1 = 3 * (p1_set ** 3) * (1 - p1_set)

            # 3-2 (6 ways)
            prob_3_2 = 6 * (p1_set ** 3) * ((1 - p1_set) ** 2)

            # 0-3
            prob_0_3 = (1 - p1_set) ** 3

            # 1-3
            prob_1_3 = 3 * ((1 - p1_set) ** 3) * p1_set

            # 2-3
            prob_2_3 = 6 * ((1 - p1_set) ** 3) * (p1_set ** 2)

            total = prob_3_0 + prob_3_1 + prob_3_2 + prob_0_3 + prob_1_3 + prob_2_3
            return {
                "3-0": round(prob_3_0 / total, 3),
                "3-1": round(prob_3_1 / total, 3),
                "3-2": round(prob_3_2 / total, 3),
                "0-3": round(prob_0_3 / total, 3),
                "1-3": round(prob_1_3 / total, 3),
                "2-3": round(prob_2_3 / total, 3),
            }

    # =========================================================================
    # VALUE DETECTION
    # =========================================================================

    def _log_staking_decision(self, log_data: Dict):
        """Log staking decision to CSV for analysis."""
        try:
            file_exists = staking_log_file.exists()
            with open(staking_log_file, 'a', newline='', encoding='utf-8') as f:
                fieldnames = [
                    'timestamp', 'player', 'tournament', 'surface',
                    'betfair_odds', 'our_prob', 'implied_prob', 'edge', 'ev',
                    'base_units', 'odds_category', 'odds_cap', 'edge_override',
                    'final_units', 'stake_tier', 'is_value', 'notes'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(log_data)
        except Exception as e:
            staking_logger.warning(f"Failed to log staking decision: {e}")

    def find_value(self, our_prob: float, decimal_odds: float,
                   player_name: str = None, tournament: str = None,
                   surface: str = None, log: bool = True,
                   confidence: float = None) -> Dict:
        """
        Determine if odds offer value using Kelly-based staking with market skepticism.

        Formula: Final Stake = Kelly Stake × Kelly Fraction × Disagreement Penalty × Odds Multiplier

        Key principles:
        - Kelly naturally penalizes longshots (no hard caps needed)
        - Market disagreement penalty reduces stake when we disagree with bookmakers
        - Fractional Kelly (0.40) balances growth vs risk
        - Minimum 0.5 units to place a bet
        - Probability calibration adjusts overconfident model
        - Market blend weights market probability into model
        - Odds range weighting focuses on profitable 2.00-2.99 zone

        See STAKING_FRAMEWORK.md for full details.
        """
        implied_prob = 1 / decimal_odds
        raw_model_prob = our_prob  # Store original for logging

        # Step 0a: Apply probability calibration (model is overconfident)
        # Based on 60 settled bets: model predicts 53.5% avg but wins only 31.7%
        # The model is systematically ~1.7x overconfident in the 40-60% range
        calibration = KELLY_STAKING.get("calibration", {})
        if calibration.get("enabled", False):
            cal_type = calibration.get("type", "shrinkage")

            if cal_type == "shrinkage":
                # Shrinkage calibration: pull probabilities toward 50%
                # This reduces overconfidence while maintaining bet volume
                # shrinkage_factor=0.5 means: 60% raw -> 55% calibrated, 70% raw -> 60% calibrated
                shrinkage = calibration.get("shrinkage_factor", 0.5)
                our_prob = 0.5 + (raw_model_prob - 0.5) * shrinkage
                # Clamp to valid probability range
                our_prob = max(0.05, min(0.95, our_prob))

            elif cal_type == "polynomial":
                # Legacy polynomial calibration (broken - kept for reference)
                # Calculate opponent's raw probability
                opponent_raw = 1 - raw_model_prob
                a = calibration.get("poly_a", 7.5566)
                b = calibration.get("poly_b", -7.3102)
                c = calibration.get("poly_c", 1.9932)
                # Calibrate both players
                our_cal = (a * raw_model_prob * raw_model_prob) + (b * raw_model_prob) + c
                opp_cal = (a * opponent_raw * opponent_raw) + (b * opponent_raw) + c
                # Normalize so probabilities sum to 1
                total = our_cal + opp_cal
                if total > 0:
                    our_prob = our_cal / total
                else:
                    our_prob = 0.5  # Fallback
                # Clamp to valid probability range
                our_prob = max(0.05, min(0.95, our_prob))

            else:
                # Legacy linear calibration
                opponent_raw = 1 - raw_model_prob
                multiplier = calibration.get("multiplier", 0.60)
                offset = calibration.get("offset", 0.15)
                our_cal = (raw_model_prob * multiplier) + offset
                opp_cal = (opponent_raw * multiplier) + offset
                # Normalize so probabilities sum to 1
                total = our_cal + opp_cal
                if total > 0:
                    our_prob = our_cal / total
                else:
                    our_prob = 0.5  # Fallback
                # Clamp to valid probability range
                our_prob = max(0.05, min(0.95, our_prob))

        # Step 0b: Blend with market probability (market is smarter)
        market_blend = KELLY_STAKING.get("market_blend", {})
        if market_blend.get("enabled", False):
            market_weight = market_blend.get("market_weight", 0.30)
            our_prob = (our_prob * (1 - market_weight)) + (implied_prob * market_weight)

        # Store adjusted probability for output
        adjusted_prob = our_prob

        ev = (our_prob * (decimal_odds - 1)) - (1 - our_prob)
        edge = our_prob - implied_prob

        # Get staking settings
        kelly_fraction = KELLY_STAKING["kelly_fraction"]
        min_units = KELLY_STAKING["min_units"]
        max_units = KELLY_STAKING["max_units"]
        unit_size_pct = KELLY_STAKING["unit_size_percent"]
        min_odds = KELLY_STAKING.get("min_odds", 1.70)

        # Initialize tracking variables
        kelly_stake_pct = 0
        base_units = 0
        disagreement_level = "none"
        disagreement_penalty = 1.0
        recommended_units = 0
        stake_tier = "no_bet"
        odds_too_short = decimal_odds < min_odds

        # Initialize odds range weighting variables
        odds_weighting = KELLY_STAKING.get("odds_range_weighting", {})
        sweet_spot_min = odds_weighting.get("sweet_spot_min", 2.00)
        sweet_spot_max = odds_weighting.get("sweet_spot_max", 2.99)
        in_sweet_spot = sweet_spot_min <= decimal_odds <= sweet_spot_max

        # Only calculate stake if we have positive edge, meets EV threshold, and odds aren't too short
        if edge > 0 and ev > BETTING_SETTINGS["min_ev_threshold"] and not odds_too_short:
            # Step 1: Calculate Kelly stake as percentage of bankroll
            # Kelly formula: Stake % = Edge / (Odds - 1)
            kelly_stake_pct = edge / (decimal_odds - 1)

            # Step 2: Apply fractional Kelly (0.40 = balanced approach)
            fractional_kelly_pct = kelly_stake_pct * kelly_fraction

            # Step 3: Calculate market disagreement penalty
            # When our probability is much higher than implied, we're likely wrong
            prob_ratio = our_prob / implied_prob
            penalties = KELLY_STAKING["disagreement_penalty"]

            if prob_ratio <= penalties["minor"]["max_ratio"]:
                disagreement_level = "minor"
                disagreement_penalty = penalties["minor"]["penalty"]
            elif prob_ratio <= penalties["moderate"]["max_ratio"]:
                disagreement_level = "moderate"
                disagreement_penalty = penalties["moderate"]["penalty"]
            elif prob_ratio <= penalties["major"]["max_ratio"]:
                disagreement_level = "major"
                disagreement_penalty = penalties["major"]["penalty"]
            else:
                disagreement_level = "extreme"
                disagreement_penalty = penalties["extreme"]["penalty"]

            # Step 3b: Challenger-specific tighter threshold
            # Backtest showed high disagreement Challenger bets were 0-8, -13u
            challenger_settings = KELLY_STAKING.get("challenger_settings", {})
            if challenger_settings.get("enabled", False) and tournament:
                is_challenger = 'challenger' in tournament.lower() or 'ch ' in tournament.lower()
                if is_challenger:
                    max_ratio = challenger_settings.get("max_disagreement_ratio", 1.5)
                    if prob_ratio > max_ratio:
                        disagreement_level = "challenger_blocked"
                        disagreement_penalty = 0.0  # Block the bet

            # Step 4: Apply disagreement penalty
            final_stake_pct = fractional_kelly_pct * disagreement_penalty

            # Step 5: Convert percentage to units (2% per unit)
            base_units = final_stake_pct / (unit_size_pct / 100)

            # Step 5b: Apply odds range weighting (profitable zone is 2.00-2.99)
            outside_multiplier = odds_weighting.get("outside_multiplier", 0.5)
            if not in_sweet_spot:
                base_units = base_units * outside_multiplier

            # Step 6: Confidence scaling (DISABLED - weighted advantage scale doesn't fit)
            # We already have calibration, market blend, disagreement penalty, and odds weighting
            confidence_scaling = 1.0
            low_confidence = False
            # Disabled: weighted advantage (0.01-0.20) doesn't map well to confidence thresholds
            # if confidence is not None and confidence < 0.40:
            #     low_confidence = True
            #     if confidence < 0.25:
            #         confidence_scaling = 0.5
            #     else:
            #         confidence_scaling = 0.5 + (confidence - 0.25) / 0.15 * 0.5
            #     base_units = base_units * confidence_scaling

            # Step 7: Apply caps and minimum threshold
            recommended_units = min(base_units, max_units)

            # Round to nearest 0.5 units
            recommended_units = round(recommended_units * 2) / 2

            # If below minimum, don't bet
            if recommended_units < min_units:
                recommended_units = 0
                stake_tier = "below_minimum"
            elif recommended_units >= 2.0:
                stake_tier = "strong"
            elif recommended_units >= 1.0:
                stake_tier = "confident"
            else:
                stake_tier = "standard"
        else:
            low_confidence = confidence is not None and confidence < 0.40
            confidence_scaling = 1.0
            if odds_too_short:
                stake_tier = "odds_too_short"

        # Calculate stake as percentage of bankroll
        recommended_stake = recommended_units * (unit_size_pct / 100)

        is_value = ev > BETTING_SETTINGS["min_ev_threshold"] and recommended_units >= min_units and not odds_too_short

        # Determine odds category for logging
        if decimal_odds <= 2.00:
            odds_category = "short"
        elif decimal_odds <= 3.50:
            odds_category = "medium"
        elif decimal_odds <= 5.00:
            odds_category = "long"
        else:
            odds_category = "longshot"

        # Log staking decision for analysis
        if log and (is_value or edge > 0.03):
            notes = []
            if odds_too_short:
                notes.append(f"odds_too_short_min_{min_odds}")
            if disagreement_level in ("major", "extreme", "challenger_blocked"):
                notes.append(f"disagreement_{disagreement_level}")
            if low_confidence:
                notes.append(f"low_confidence_{int(confidence*100) if confidence else 0}pct")
            if stake_tier == "below_minimum":
                notes.append(f"below_min_threshold_{base_units:.2f}")
            if decimal_odds > 5.0:
                notes.append("longshot")
            prob_ratio = our_prob / implied_prob if implied_prob > 0 else 0
            notes.append(f"ratio_{prob_ratio:.2f}x")

            self._log_staking_decision({
                'timestamp': datetime.now().isoformat(),
                'player': player_name or 'Unknown',
                'tournament': tournament or 'Unknown',
                'surface': surface or 'Unknown',
                'betfair_odds': round(decimal_odds, 2),
                'our_prob': round(our_prob * 100, 1),
                'implied_prob': round(implied_prob * 100, 1),
                'edge': round(edge * 100, 1),
                'ev': round(ev * 100, 1),
                'base_units': round(base_units, 2),
                'odds_category': odds_category,
                'odds_cap': max_units,
                'edge_override': False,  # No longer used
                'final_units': recommended_units,
                'stake_tier': stake_tier,
                'is_value': is_value,
                'notes': ';'.join(notes) if notes else ''
            })

        # Calculate value confidence level for display
        prob_ratio = our_prob / implied_prob if implied_prob > 0 else 0
        if prob_ratio <= 1.3:
            value_confidence = "high"  # Safe bet - minor disagreement
        elif prob_ratio <= 1.5:
            value_confidence = "medium"  # Caution - moderate disagreement
        else:
            value_confidence = "low"  # Likely model error - major disagreement

        return {
            "our_probability": round(our_prob, 3),
            "implied_probability": round(implied_prob, 3),
            "edge": round(edge, 3),
            "expected_value": round(ev, 3),
            "is_value": is_value,
            "is_high_value": ev > BETTING_SETTINGS["high_ev_threshold"],
            # Kelly-based staking
            "recommended_units": recommended_units,
            "stake_tier": stake_tier,
            "unit_size_percent": unit_size_pct,
            # Kelly calculation breakdown
            "kelly_stake_pct": round(kelly_stake_pct * 100, 2),
            "kelly_fraction": kelly_fraction,
            "disagreement_level": disagreement_level,
            "disagreement_penalty": disagreement_penalty,
            "prob_ratio": round(prob_ratio, 2),
            # NEW: Calibration and blend info
            "raw_model_prob": round(raw_model_prob, 3),  # Original model output
            "adjusted_prob": round(adjusted_prob, 3),    # After calibration
            "in_sweet_spot": in_sweet_spot,  # Odds 2.00-2.99
            "value_confidence": value_confidence,  # high/medium/low display indicator
            # Other info
            "odds_category": odds_category,
            "odds_too_short": odds_too_short,
            "min_odds": min_odds,
            "low_confidence": low_confidence,
            "confidence_scaling": round(confidence_scaling, 2),
            "recommended_stake": round(recommended_stake, 3),
        }


class MatchAnalyzerUI:
    """Tkinter UI for Match Analyzer."""

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Match Analyzer")
        self.root.geometry("1200x800")
        self.root.configure(bg=UI_COLORS["bg_dark"])

        self.analyzer = MatchAnalyzer()
        self.scraper = TennisAbstractScraper()
        self.players_cache = []

        self._setup_styles()
        self._build_ui()
        self._load_players()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=UI_COLORS["bg_dark"])
        style.configure("Card.TFrame", background=UI_COLORS["bg_medium"])
        style.configure("Dark.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 16, "bold"))
        style.configure("Card.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["accent"], font=("Segoe UI", 11, "bold"))
        style.configure("Prob.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["success"], font=("Segoe UI", 24, "bold"))

    def _build_ui(self):
        """Build the main UI."""
        # Main container
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Label(main_frame, text="Match Analyzer", style="Title.TLabel")
        header.pack(anchor=tk.W, pady=(0, 20))

        # Player selection frame
        select_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        select_frame.pack(fill=tk.X, pady=(0, 20))

        # Player 1
        p1_frame = ttk.Frame(select_frame, style="Card.TFrame")
        p1_frame.pack(side=tk.LEFT, padx=10)

        ttk.Label(p1_frame, text="Player 1:", style="Card.TLabel").pack(anchor=tk.W)
        self.p1_var = tk.StringVar()
        self.p1_combo = ttk.Combobox(p1_frame, textvariable=self.p1_var, width=30)
        self.p1_combo.pack(pady=5)
        self.p1_combo.bind('<KeyRelease>', lambda e: self._filter_players(self.p1_combo, e))

        # VS label
        vs_label = ttk.Label(select_frame, text="VS", style="CardTitle.TLabel")
        vs_label.pack(side=tk.LEFT, padx=20)

        # Player 2
        p2_frame = ttk.Frame(select_frame, style="Card.TFrame")
        p2_frame.pack(side=tk.LEFT, padx=10)

        ttk.Label(p2_frame, text="Player 2:", style="Card.TLabel").pack(anchor=tk.W)
        self.p2_var = tk.StringVar()
        self.p2_combo = ttk.Combobox(p2_frame, textvariable=self.p2_var, width=30)
        self.p2_combo.pack(pady=5)
        self.p2_combo.bind('<KeyRelease>', lambda e: self._filter_players(self.p2_combo, e))

        # Surface
        surface_frame = ttk.Frame(select_frame, style="Card.TFrame")
        surface_frame.pack(side=tk.LEFT, padx=20)

        ttk.Label(surface_frame, text="Surface:", style="Card.TLabel").pack(anchor=tk.W)
        self.surface_var = tk.StringVar(value="Hard")
        surface_combo = ttk.Combobox(surface_frame, textvariable=self.surface_var,
                                      values=SURFACES, width=15, state="readonly")
        surface_combo.pack(pady=5)

        # Analyze button
        analyze_btn = tk.Button(
            select_frame,
            text="Analyze Match",
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg=UI_COLORS["accent"],
            activebackground=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._analyze_match,
            padx=25,
            pady=10
        )
        analyze_btn.pack(side=tk.RIGHT, padx=10)

        # Results area (scrollable)
        results_canvas = tk.Canvas(main_frame, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        results_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=results_canvas.yview)
        self.results_frame = ttk.Frame(results_canvas, style="Dark.TFrame")

        results_canvas.configure(yscrollcommand=results_scrollbar.set)
        results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        results_canvas.pack(fill=tk.BOTH, expand=True)

        results_canvas.create_window((0, 0), window=self.results_frame, anchor=tk.NW)
        self.results_frame.bind("<Configure>",
                                lambda e: results_canvas.configure(scrollregion=results_canvas.bbox("all")))

    def _load_players(self):
        """Load players from database."""
        try:
            self.players_cache = db.get_all_players()
            player_names = [p['name'] for p in self.players_cache if p['name']]
            self.p1_combo['values'] = player_names
            self.p2_combo['values'] = player_names
        except Exception as e:
            print(f"Error loading players: {e}")

    def _filter_players(self, combo: ttk.Combobox, event=None):
        """Filter player dropdown based on typed text with delayed auto-open."""
        # Ignore navigation keys
        if event and event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab'):
            return

        typed = combo.get().lower().strip()

        # Reset to full list if empty
        if len(typed) == 0:
            player_names = [p['name'] for p in self.players_cache if p['name']]
            combo['values'] = player_names
            # Cancel any pending dropdown open
            if hasattr(self, '_dropdown_after_id') and self._dropdown_after_id:
                self.root.after_cancel(self._dropdown_after_id)
                self._dropdown_after_id = None
            return

        # Filter after 1+ characters
        filtered = [p['name'] for p in self.players_cache
                   if typed in p['name'].lower()][:50]
        combo['values'] = filtered

        # Cancel previous scheduled dropdown open
        if hasattr(self, '_dropdown_after_id') and self._dropdown_after_id:
            self.root.after_cancel(self._dropdown_after_id)

        # Schedule dropdown to open after 500ms of no typing
        if filtered and len(typed) >= 2:
            self._dropdown_after_id = self.root.after(500, lambda: self._open_dropdown(combo))

    def _open_dropdown(self, combo: ttk.Combobox):
        """Open the dropdown if it has values."""
        if combo['values']:
            combo.event_generate('<Down>')
        self._dropdown_after_id = None

    def _get_player_id(self, name: str) -> Optional[int]:
        """Get player ID from name."""
        for p in self.players_cache:
            if p['name'] == name:
                return p['id']
        return None

    def _analyze_match(self):
        """Run match analysis."""
        p1_name = self.p1_var.get()
        p2_name = self.p2_var.get()
        surface = self.surface_var.get()

        if not p1_name or not p2_name:
            messagebox.showwarning("Input Required", "Please select both players.")
            return

        p1_id = self._get_player_id(p1_name)
        p2_id = self._get_player_id(p2_name)

        if not p1_id or not p2_id:
            messagebox.showerror("Error", "Could not find player IDs.")
            return

        # Store for use in sub-dialogs
        self.p1_id = p1_id
        self.p2_id = p2_id

        try:
            result = self.analyzer.calculate_win_probability(p1_id, p2_id, surface)
            self._display_results(p1_name, p2_name, surface, result)
        except Exception as e:
            messagebox.showerror("Analysis Error", str(e))

    def _display_results(self, p1_name: str, p2_name: str, surface: str, result: Dict):
        """Display analysis results."""
        # Store names for use in sub-methods
        self.p1_name = p1_name
        self.p2_name = p2_name

        # Clear previous results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        # Probability header
        prob_frame = ttk.Frame(self.results_frame, style="Card.TFrame", padding=20)
        prob_frame.pack(fill=tk.X, pady=10, padx=5)

        # P1 probability
        p1_prob_frame = ttk.Frame(prob_frame, style="Card.TFrame")
        p1_prob_frame.pack(side=tk.LEFT, expand=True)
        ttk.Label(p1_prob_frame, text=p1_name, style="CardTitle.TLabel").pack()
        p1_prob_label = ttk.Label(p1_prob_frame,
                                   text=f"{result['p1_probability']*100:.1f}%",
                                   style="Prob.TLabel")
        p1_prob_label.pack(pady=5)

        # VS
        ttk.Label(prob_frame, text="vs", style="Card.TLabel").pack(side=tk.LEFT, padx=20)

        # P2 probability
        p2_prob_frame = ttk.Frame(prob_frame, style="Card.TFrame")
        p2_prob_frame.pack(side=tk.LEFT, expand=True)
        ttk.Label(p2_prob_frame, text=p2_name, style="CardTitle.TLabel").pack()
        p2_prob_label = ttk.Label(p2_prob_frame,
                                   text=f"{result['p2_probability']*100:.1f}%",
                                   style="Prob.TLabel")
        p2_prob_label.pack(pady=5)

        # Confidence
        conf_label = ttk.Label(prob_frame,
                               text=f"Confidence: {result['confidence']*100:.0f}%",
                               style="Card.TLabel")
        conf_label.pack(side=tk.RIGHT, padx=20)

        # Factor breakdown
        factors_frame = ttk.Frame(self.results_frame, style="Dark.TFrame")
        factors_frame.pack(fill=tk.X, pady=10)

        factors = result['factors']

        # Form
        self._create_factor_card(factors_frame, "Recent Form",
                                  f"{factors['form']['p1']['score']:.0f}",
                                  f"{factors['form']['p2']['score']:.0f}",
                                  f"W: {factors['form']['advantage']:+.2f}",
                                  factors['form']['weight'])

        # Surface
        self._create_factor_card(factors_frame, f"{surface} Surface",
                                  f"{factors['surface']['p1']['combined_win_rate']*100:.1f}%",
                                  f"{factors['surface']['p2']['combined_win_rate']*100:.1f}%",
                                  f"W: {factors['surface']['advantage']:+.2f}",
                                  factors['surface']['weight'])

        # Ranking
        self._create_factor_card(factors_frame, "Rankings",
                                  f"#{factors['ranking']['data']['p1_rank']}",
                                  f"#{factors['ranking']['data']['p2_rank']}",
                                  f"W: {factors['ranking']['advantage']:+.2f}",
                                  factors['ranking']['weight'])

        # H2H
        h2h = factors['h2h']['data']
        self._create_factor_card(factors_frame, "Head-to-Head",
                                  f"{h2h['p1_wins']}",
                                  f"{h2h['p2_wins']}",
                                  f"W: {factors['h2h']['advantage']:+.2f}",
                                  factors['h2h']['weight'])

        # Fatigue (with detailed breakdown on click)
        self._create_fatigue_card(factors_frame, factors['fatigue'],
                                  self.p1_name, self.p2_name)

        # Injury
        self._create_factor_card(factors_frame, "Injury Status",
                                  factors['injury']['p1']['status'],
                                  factors['injury']['p2']['status'],
                                  f"W: {factors['injury']['advantage']:+.2f}",
                                  factors['injury']['weight'])

        # Set betting probabilities
        set_probs = self.analyzer.calculate_set_probabilities(result['p1_probability'])

        set_frame = ttk.Frame(self.results_frame, style="Card.TFrame", padding=15)
        set_frame.pack(fill=tk.X, pady=10, padx=5)

        ttk.Label(set_frame, text="Set Betting Probabilities", style="CardTitle.TLabel").pack(anchor=tk.W)

        set_row = ttk.Frame(set_frame, style="Card.TFrame")
        set_row.pack(fill=tk.X, pady=10)

        for score, prob in set_probs.items():
            cell = ttk.Frame(set_row, style="Card.TFrame")
            cell.pack(side=tk.LEFT, expand=True)
            ttk.Label(cell, text=score, style="CardTitle.TLabel").pack()
            ttk.Label(cell, text=f"{prob*100:.1f}%", style="Card.TLabel").pack()

    def _create_factor_card(self, parent, title: str, p1_val: str, p2_val: str,
                            advantage: str, weight: float):
        """Create a factor comparison card."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.pack(side=tk.LEFT, expand=True, padx=5, pady=5)

        ttk.Label(card, text=title, style="CardTitle.TLabel").pack()
        ttk.Label(card, text=f"{p1_val} vs {p2_val}", style="Card.TLabel").pack(pady=2)
        ttk.Label(card, text=f"{advantage} ({weight*100:.0f}%)", style="Card.TLabel").pack()

    def _create_fatigue_card(self, parent, fatigue_data: dict, p1_name: str, p2_name: str):
        """Create a fatigue factor card with click-to-expand details."""
        p1 = fatigue_data['p1']
        p2 = fatigue_data['p2']
        advantage = fatigue_data['advantage']
        weight = fatigue_data['weight']

        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.pack(side=tk.LEFT, expand=True, padx=5, pady=5)

        ttk.Label(card, text="Fatigue", style="CardTitle.TLabel").pack()
        ttk.Label(card, text=f"{p1['status']} vs {p2['status']}", style="Card.TLabel").pack(pady=2)
        ttk.Label(card, text=f"W: {advantage:+.2f} ({weight*100:.0f}%)", style="Card.TLabel").pack()

        # "View Details" link
        details_label = ttk.Label(card, text="View Details", style="Card.TLabel",
                                  foreground="#6366f1", cursor="hand2")
        details_label.pack(pady=(5, 0))
        details_label.bind("<Button-1>", lambda e: self._show_fatigue_details(
            fatigue_data, p1_name, p2_name))

    def _show_fatigue_details(self, fatigue_data: dict, p1_name: str, p2_name: str):
        """Show detailed fatigue breakdown in a popup with recent matches."""
        p1 = fatigue_data['p1']
        p2 = fatigue_data['p2']

        popup = tk.Toplevel(self.root)
        popup.title("Fatigue Breakdown")
        popup.geometry("750x650")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)
        popup.grab_set()

        # Center the popup
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 750) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 650) // 2
        popup.geometry(f"+{x}+{y}")

        # Scrollable content
        canvas = tk.Canvas(popup, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(popup, orient=tk.VERTICAL, command=canvas.yview)
        content = ttk.Frame(canvas, style="Card.TFrame", padding=20)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=content, anchor=tk.NW)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(content, text="Fatigue Breakdown", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(content, text="Match difficulty now factors into workload calculation",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Create comparison table
        table = ttk.Frame(content, style="Card.TFrame")
        table.pack(fill=tk.X, pady=10)

        # Header row
        headers = ["", p1_name[:15], p2_name[:15]]
        for col, header in enumerate(headers):
            lbl = ttk.Label(table, text=header, style="CardTitle.TLabel", width=15)
            lbl.grid(row=0, column=col, padx=5, pady=3, sticky="w")

        # Data rows
        rows = [
            ("Status", p1['status'], p2['status']),
            ("Score", f"{p1['score']:.1f}/100", f"{p2['score']:.1f}/100"),
            ("Days Rest", str(p1.get('days_since_match', '-')), str(p2.get('days_since_match', '-'))),
            ("Matches (7d)", str(p1.get('matches_7d', '-')), str(p2.get('matches_7d', '-'))),
            ("Difficulty (7d)", f"{p1.get('difficulty_7d', 0):.1f} pts", f"{p2.get('difficulty_7d', 0):.1f} pts"),
            ("Rest Component", f"{p1.get('rest_component', 0):.1f}/40", f"{p2.get('rest_component', 0):.1f}/40"),
            ("Workload Component", f"{p1.get('workload_component', 0):.1f}/40", f"{p2.get('workload_component', 0):.1f}/40"),
        ]

        for row_idx, (label, val1, val2) in enumerate(rows, start=1):
            ttk.Label(table, text=label, style="Card.TLabel", width=15).grid(
                row=row_idx, column=0, padx=5, pady=3, sticky="w")

            # Color code values based on comparison
            v1_color = UI_COLORS["success"] if self._compare_fatigue_val(label, val1, val2) > 0 else UI_COLORS["text_primary"]
            v2_color = UI_COLORS["success"] if self._compare_fatigue_val(label, val2, val1) > 0 else UI_COLORS["text_primary"]

            lbl1 = ttk.Label(table, text=val1, style="Card.TLabel", width=15, foreground=v1_color)
            lbl1.grid(row=row_idx, column=1, padx=5, pady=3, sticky="w")

            lbl2 = ttk.Label(table, text=val2, style="Card.TLabel", width=15, foreground=v2_color)
            lbl2.grid(row=row_idx, column=2, padx=5, pady=3, sticky="w")

        # Legend
        legend = ttk.Frame(content, style="Card.TFrame")
        legend.pack(fill=tk.X, pady=(15, 10))
        ttk.Label(legend, text="Difficulty Scale: 0.5 (walkover) → 1.0 (standard) → 3.0 (marathon)",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W)

        # Recent matches section
        ttk.Label(content, text="Recent Matches (from database)", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(20, 10))

        # Fetch recent matches for both players
        matches_frame = ttk.Frame(content, style="Card.TFrame")
        matches_frame.pack(fill=tk.X)

        # Player 1 matches
        p1_frame = ttk.Frame(matches_frame, style="Card.TFrame")
        p1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(p1_frame, text=f"{p1_name[:20]}", style="CardTitle.TLabel").pack(anchor=tk.W)
        self._create_matches_list(p1_frame, self.p1_id)

        # Player 2 matches
        p2_frame = ttk.Frame(matches_frame, style="Card.TFrame")
        p2_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(p2_frame, text=f"{p2_name[:20]}", style="CardTitle.TLabel").pack(anchor=tk.W)
        self._create_matches_list(p2_frame, self.p2_id)

        # Button frame
        btn_frame = ttk.Frame(content, style="Card.TFrame")
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        # Refresh from Tennis Abstract button
        refresh_btn = tk.Button(
            btn_frame,
            text="Refresh Both from Tennis Abstract",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._refresh_players_from_ta(popup, p1_name, p2_name),
            padx=15,
            pady=5
        )
        refresh_btn.pack(side=tk.LEFT)

        # Close button
        close_btn = ttk.Button(btn_frame, text="Close", command=popup.destroy)
        close_btn.pack(side=tk.RIGHT)

    def _create_matches_list(self, parent, player_id: int):
        """Create a condensed list of recent matches for a player."""
        matches = db.get_player_matches(player_id, limit=10)

        if not matches:
            ttk.Label(parent, text="No matches in database", style="Card.TLabel",
                     foreground=UI_COLORS["warning"]).pack(anchor=tk.W, pady=5)
            return

        # Get canonical ID for alias matching
        player_canonical = db.get_canonical_id(player_id)

        for match in matches:
            winner_canonical = db.get_canonical_id(match['winner_id'])
            won = winner_canonical == player_canonical
            opp_id = match['loser_id'] if won else match['winner_id']
            opp = db.get_player(opp_id)
            opp_name = opp['name'][:15] if opp else 'Unknown'

            date_str = match.get('date', '')[:10]
            result = "W" if won else "L"
            score = match.get('score', '')[:15]
            mins = match.get('minutes')
            mins_str = f"{mins}m" if mins else ""

            # Calculate difficulty for this match
            difficulty = self.analyzer.calculate_match_difficulty(match, player_id)

            result_color = UI_COLORS["success"] if won else UI_COLORS["danger"]

            row = ttk.Frame(parent, style="Card.TFrame")
            row.pack(fill=tk.X, pady=1)

            ttk.Label(row, text=date_str, style="Card.TLabel", width=10).pack(side=tk.LEFT)
            lbl_result = tk.Label(row, text=result, font=("Segoe UI", 9, "bold"),
                                 fg=result_color, bg=UI_COLORS["bg_medium"], width=2)
            lbl_result.pack(side=tk.LEFT)
            ttk.Label(row, text=f"vs {opp_name}", style="Card.TLabel", width=16).pack(side=tk.LEFT)
            ttk.Label(row, text=f"({difficulty:.1f})", style="Card.TLabel",
                     foreground=UI_COLORS["text_secondary"], width=5).pack(side=tk.LEFT)

    def _refresh_players_from_ta(self, popup: tk.Toplevel, p1_name: str, p2_name: str):
        """Refresh both players' data from Tennis Abstract."""
        # Show loading dialog
        loading = tk.Toplevel(popup)
        loading.title("Fetching Data")
        loading.geometry("350x120")
        loading.configure(bg=UI_COLORS["bg_dark"])
        loading.transient(popup)
        loading.grab_set()

        # Center
        loading.update_idletasks()
        x = popup.winfo_x() + (popup.winfo_width() - 350) // 2
        y = popup.winfo_y() + (popup.winfo_height() - 120) // 2
        loading.geometry(f"+{x}+{y}")

        status_var = tk.StringVar(value=f"Fetching data for {p1_name}...")
        ttk.Label(loading, textvariable=status_var, style="Dark.TLabel").pack(pady=20)
        ttk.Label(loading, text="This may take a few seconds per player",
                 style="Dark.TLabel").pack()

        loading.update()

        def do_fetch():
            results = []
            try:
                # Fetch player 1
                status_var.set(f"Fetching {p1_name}...")
                loading.update()
                r1 = self.scraper.fetch_and_update_player(self.p1_id, p1_name)
                results.append((p1_name, r1))

                # Fetch player 2
                status_var.set(f"Fetching {p2_name}...")
                loading.update()
                r2 = self.scraper.fetch_and_update_player(self.p2_id, p2_name)
                results.append((p2_name, r2))

                loading.destroy()

                # Show results
                msg = ""
                for name, r in results:
                    if r['success']:
                        msg += f"{name}: Found {r['matches_found']}, added {r['matches_added']} new\n"
                    else:
                        msg += f"{name}: {r['message']}\n"

                messagebox.showinfo("Refresh Complete", msg)

                # Close and re-analyze to refresh the fatigue data
                popup.destroy()
                self._analyze_match()

            except Exception as e:
                loading.destroy()
                messagebox.showerror("Error", f"Failed to fetch data: {str(e)}")

        # Run after brief delay
        self.root.after(100, do_fetch)

    def _compare_fatigue_val(self, label: str, val1: str, val2: str) -> int:
        """Compare two fatigue values, return 1 if val1 is better, -1 if worse, 0 if equal."""
        try:
            # Extract numeric values
            n1 = float(val1.split('/')[0].split()[0].replace('pts', '').replace('-', '0'))
            n2 = float(val2.split('/')[0].split()[0].replace('pts', '').replace('-', '0'))

            # For difficulty, lower is better
            if "Difficulty" in label:
                if n1 < n2:
                    return 1
                elif n1 > n2:
                    return -1
            # For most other metrics, higher is better
            elif "Score" in label or "Component" in label or "Days Rest" in label:
                if n1 > n2:
                    return 1
                elif n1 < n2:
                    return -1
        except (ValueError, IndexError):
            pass
        return 0

    def run(self):
        """Run the UI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = MatchAnalyzerUI()
    app.run()
