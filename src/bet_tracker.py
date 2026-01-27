"""
Tennis Betting System - Bet Tracker
Track placed bets and analyze betting performance
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Dict, List, Optional
import csv
import threading
import re

import json
from config import UI_COLORS, SURFACES, KELLY_STAKING, get_tour_level, calculate_bet_model, DEFAULT_ANALYSIS_WEIGHTS
from database import db, TennisDatabase

# Import Betfair client for live scores
try:
    from betfair_capture import BetfairTennisCapture, load_credentials_from_file
    BETFAIR_AVAILABLE = True
except ImportError:
    BETFAIR_AVAILABLE = False

# Import Discord notifier
try:
    from discord_notifier import get_notifier, notify_bet_live
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

# Import Cloud Sync for Supabase
try:
    from cloud_sync import get_cloud_sync, sync_bet_to_cloud
    CLOUD_SYNC_AVAILABLE = True
except ImportError:
    CLOUD_SYNC_AVAILABLE = False


class BetTracker:
    """Track and analyze betting history."""

    def __init__(self, database: TennisDatabase = None):
        self.db = database or db

    def add_bet(self, bet_data: Dict) -> int:
        """Add a new bet. Returns bet ID, or -1 if duplicate exists, -2 if match already bet."""
        # Check for duplicate first
        match_description = bet_data.get('match_description')
        selection = bet_data.get('selection')
        match_date = bet_data.get('match_date')
        tournament = bet_data.get('tournament')

        if match_description:
            # Check if we already have ANY bet on this match (prevents betting both sides)
            existing_match = self.db.check_match_already_bet(match_description, tournament)
            if existing_match:
                return -2  # Match already has a bet

            # Check for exact duplicate (same selection)
            if selection:
                existing = self.db.check_duplicate_bet(match_description, selection, match_date, tournament)
                if existing:
                    return -1  # Duplicate found

        # Calculate implied probability and EV
        if bet_data.get('odds'):
            odds = bet_data['odds']
            implied_prob = 1 / odds
            bet_data['implied_probability'] = implied_prob

            if bet_data.get('our_probability'):
                our_prob = bet_data['our_probability']
                ev = (our_prob * (odds - 1)) - (1 - our_prob)
                bet_data['ev_at_placement'] = ev

        # Calculate which model(s) this bet qualifies for
        our_prob = bet_data.get('our_probability', 0.5)
        implied_prob = bet_data.get('implied_probability', 0.5)
        tournament = bet_data.get('tournament', '')
        odds = bet_data.get('odds')
        # Parse factor_scores if it's a JSON string
        factor_scores = bet_data.get('factor_scores')
        if isinstance(factor_scores, str):
            import json
            try:
                factor_scores = json.loads(factor_scores)
            except:
                factor_scores = None
        bet_data['model'] = calculate_bet_model(our_prob, implied_prob, tournament, odds, factor_scores)

        return self.db.add_bet(bet_data)

    def settle_bet(self, bet_id: int, result: str):
        """Settle a bet with result."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT stake, odds FROM bets WHERE id = ?", (bet_id,))
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Bet {bet_id} not found")

            stake = row[0]
            odds = row[1]

            commission = KELLY_STAKING.get('exchange_commission', 0.05)

            if result == "Win":
                # Apply Betfair commission to winnings
                gross_profit = stake * (odds - 1)
                profit_loss = gross_profit * (1 - commission)
            elif result == "Loss":
                profit_loss = -stake
            elif result == "Void":
                profit_loss = 0
            else:
                profit_loss = 0

            self.db.settle_bet(bet_id, result, profit_loss)

    def update_bet(self, bet_id: int, bet_data: Dict):
        """Update an existing bet's details."""
        self.db.update_bet(bet_id, bet_data)

    def get_bet_by_id(self, bet_id: int) -> Optional[Dict]:
        """Get a single bet by ID."""
        return self.db.get_bet_by_id(bet_id)

    def get_stats_by_surface(self) -> Dict[str, Dict]:
        """Get betting stats broken down by surface."""
        stats = {}

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            for surface in SURFACES:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN result = 'Win' THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN result = 'Loss' THEN 1 ELSE 0 END) as losses,
                        SUM(stake) as staked,
                        SUM(COALESCE(profit_loss, 0)) as profit
                    FROM bets
                    WHERE match_description LIKE ? OR notes LIKE ?
                """, (f"%{surface}%", f"%{surface}%"))

                row = cursor.fetchone()
                total = row[0] or 0
                staked = row[3] or 0

                stats[surface] = {
                    'total_bets': total,
                    'wins': row[1] or 0,
                    'losses': row[2] or 0,
                    'total_staked': staked,
                    'profit': row[4] or 0,
                    'roi': (row[4] / staked * 100) if staked > 0 else 0,
                    'win_rate': (row[1] / total * 100) if total > 0 else 0,
                }

        return stats

    def get_stats_by_month(self) -> List[Dict]:
        """Get monthly betting stats."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    strftime('%Y-%m', match_date) as month,
                    COUNT(*) as bets,
                    SUM(CASE WHEN result = 'Win' THEN 1 ELSE 0 END) as wins,
                    SUM(stake) as staked,
                    SUM(COALESCE(profit_loss, 0)) as profit
                FROM bets
                GROUP BY strftime('%Y-%m', match_date)
                ORDER BY month DESC
                LIMIT 12
            """)

            results = []
            for row in cursor.fetchall():
                staked = row[3] or 0
                results.append({
                    'month': row[0],
                    'bets': row[1],
                    'wins': row[2] or 0,
                    'staked': staked,
                    'profit': row[4] or 0,
                    'roi': (row[4] / staked * 100) if staked > 0 else 0,
                })

            return results

    def get_stats_by_market(self) -> Dict[str, Dict]:
        """Get stats by bet market type."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COALESCE(market, 'Unknown') as market,
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'Win' THEN 1 ELSE 0 END) as wins,
                    SUM(stake) as staked,
                    SUM(COALESCE(profit_loss, 0)) as profit
                FROM bets
                GROUP BY market
            """)

            stats = {}
            for row in cursor.fetchall():
                market = row[0]
                staked = row[3] or 0
                stats[market] = {
                    'total_bets': row[1],
                    'wins': row[2] or 0,
                    'staked': staked,
                    'profit': row[4] or 0,
                    'roi': (row[4] / staked * 100) if staked > 0 else 0,
                }

            return stats

    def get_stats_by_tour(self) -> List[Dict]:
        """Get betting stats broken down by tour level."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tournament,
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'Win' THEN 1 ELSE 0 END) as wins,
                    SUM(stake) as staked,
                    SUM(COALESCE(profit_loss, 0)) as profit
                FROM bets
                WHERE result IN ('Win', 'Loss')
                GROUP BY tournament
            """)

            # Aggregate by tour level
            tour_stats = {}
            for row in cursor.fetchall():
                tournament = row[0] or ''
                tour = get_tour_level(tournament)

                if tour not in tour_stats:
                    tour_stats[tour] = {'bets': 0, 'wins': 0, 'staked': 0, 'profit': 0}

                tour_stats[tour]['bets'] += row[1] or 0
                tour_stats[tour]['wins'] += row[2] or 0
                tour_stats[tour]['staked'] += row[3] or 0
                tour_stats[tour]['profit'] += row[4] or 0

            # Convert to list with calculated fields
            results = []
            # Order: Grand Slam, ATP, WTA, Challenger, ITF, Unknown
            tour_order = ['Grand Slam', 'ATP', 'WTA', 'Challenger', 'ITF', 'Unknown']
            for tour in tour_order:
                if tour in tour_stats:
                    s = tour_stats[tour]
                    results.append({
                        'tour': tour,
                        'bets': s['bets'],
                        'wins': s['wins'],
                        'win_rate': (s['wins'] / s['bets'] * 100) if s['bets'] > 0 else 0,
                        'staked': s['staked'],
                        'profit': s['profit'],
                        'roi': (s['profit'] / s['staked'] * 100) if s['staked'] > 0 else 0,
                    })

            return results

    def get_stats_by_model(self) -> List[Dict]:
        """Get betting stats broken down by model.

        Model 1: All bets (baseline)
        Model 2: Tiered strategy (extremes + filtered middle)
        Model 3: Moderate edge (5-15%) with Sharp weights
        Model 4: Favorites only (our prob >= 60%)
        Model 5: Underdogs only (our prob < 45%)
        Model 6: Large edge (>= 10%)
        Model 7: Small edge (3-8%) + short odds (< 2.50)
        Model 8: Profitable baseline - our prob >= 55% AND odds < 2.50
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get all settled bets with model data
            cursor.execute("""
                SELECT
                    our_probability,
                    implied_probability,
                    tournament,
                    result,
                    stake,
                    profit_loss,
                    model,
                    odds,
                    factor_scores
                FROM bets
                WHERE result IN ('Win', 'Loss')
            """)

            # Calculate stats for each model (v2.0: only Models 3, 4, 7, 8)
            all_models = ['Model 3', 'Model 4', 'Model 7', 'Model 8']
            model_stats = {m: {'bets': 0, 'wins': 0, 'staked': 0, 'profit': 0} for m in all_models}

            for row in cursor.fetchall():
                our_prob, implied_prob, tournament, result, stake, profit_loss, model, odds, factor_scores_json = row
                stake = stake or 0
                profit_loss = profit_loss or 0

                # Parse factor_scores JSON
                factor_scores = None
                if factor_scores_json:
                    import json
                    try:
                        factor_scores = json.loads(factor_scores_json)
                    except:
                        factor_scores = None

                # Recalculate model for existing bets using current criteria
                model = calculate_bet_model(
                    our_prob or 0.5,
                    implied_prob or 0.5,
                    tournament or '',
                    odds,
                    factor_scores
                )

                # Check each active model for qualifying bets
                for model_name in all_models:
                    if model_name in model:
                        model_stats[model_name]['bets'] += 1
                        model_stats[model_name]['staked'] += stake
                        model_stats[model_name]['profit'] += profit_loss
                        if result == 'Win':
                            model_stats[model_name]['wins'] += 1

            # Convert to list with calculated fields
            results = []
            for model_name in all_models:
                s = model_stats[model_name]
                if s['bets'] > 0:
                    results.append({
                        'model': model_name,
                        'bets': s['bets'],
                        'wins': s['wins'],
                        'losses': s['bets'] - s['wins'],
                        'win_rate': (s['wins'] / s['bets'] * 100) if s['bets'] > 0 else 0,
                        'staked': s['staked'],
                        'profit': s['profit'],
                        'roi': (s['profit'] / s['staked'] * 100) if s['staked'] > 0 else 0,
                    })

            return results

    def get_stats_by_gender(self) -> List[Dict]:
        """Get betting stats broken down by gender (Male/Female).

        Male = ATP, Challenger, Grand Slam (men's)
        Female = WTA, ITF
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    tournament,
                    result,
                    stake,
                    profit_loss
                FROM bets
                WHERE result IN ('Win', 'Loss')
            """)

            gender_stats = {
                'Male': {'bets': 0, 'wins': 0, 'staked': 0, 'profit': 0},
                'Female': {'bets': 0, 'wins': 0, 'staked': 0, 'profit': 0},
            }

            for row in cursor.fetchall():
                tournament, result, stake, profit_loss = row
                stake = stake or 0
                profit_loss = profit_loss or 0

                # Determine gender from tournament name
                tour = get_tour_level(tournament or '')
                if tour in ['ATP', 'Challenger', 'Grand Slam']:
                    gender = 'Male'
                elif tour in ['WTA', 'ITF']:
                    gender = 'Female'
                else:
                    # Check tournament name for ladies/women's indicators
                    tournament_lower = (tournament or '').lower()
                    if 'ladies' in tournament_lower or "women" in tournament_lower or 'wta' in tournament_lower:
                        gender = 'Female'
                    else:
                        gender = 'Male'

                gender_stats[gender]['bets'] += 1
                gender_stats[gender]['staked'] += stake
                gender_stats[gender]['profit'] += profit_loss
                if result == 'Win':
                    gender_stats[gender]['wins'] += 1

            # Convert to list with calculated fields
            results = []
            for gender_name in ['Male', 'Female']:
                s = gender_stats[gender_name]
                if s['bets'] > 0:
                    results.append({
                        'gender': gender_name,
                        'bets': s['bets'],
                        'wins': s['wins'],
                        'losses': s['bets'] - s['wins'],
                        'win_rate': (s['wins'] / s['bets'] * 100) if s['bets'] > 0 else 0,
                        'staked': s['staked'],
                        'profit': s['profit'],
                        'roi': (s['profit'] / s['staked'] * 100) if s['staked'] > 0 else 0,
                    })

            return results

    def get_stats_by_odds_range(self) -> List[Dict]:
        """Get betting stats broken down by odds range."""
        ranges = [
            ("1.00 - 1.50", 1.00, 1.50),
            ("1.50 - 2.00", 1.50, 2.00),
            ("2.00 - 3.00", 2.00, 3.00),
            ("3.00 - 5.00", 3.00, 5.00),
            ("5.00+", 5.00, 9999),
        ]

        results = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            for label, min_odds, max_odds in ranges:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN result = 'Win' THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN result = 'Loss' THEN 1 ELSE 0 END) as losses,
                        SUM(stake) as staked,
                        SUM(COALESCE(profit_loss, 0)) as profit
                    FROM bets
                    WHERE odds >= ? AND odds < ?
                    AND result IN ('Win', 'Loss')
                """, (min_odds, max_odds))

                row = cursor.fetchone()
                total = row[0] or 0
                staked = row[3] or 0
                wins = row[1] or 0

                results.append({
                    'range': label,
                    'bets': total,
                    'wins': wins,
                    'losses': row[2] or 0,
                    'win_rate': (wins / total * 100) if total > 0 else 0,
                    'staked': staked,
                    'profit': row[4] or 0,
                    'roi': (row[4] / staked * 100) if staked > 0 else 0,
                })

        return results

    def get_stats_by_stake_size(self) -> List[Dict]:
        """Get betting stats broken down by stake/units size."""
        ranges = [
            ("0.5", 0, 0.75),
            ("1.0", 0.75, 1.25),
            ("1.5", 1.25, 1.75),
            ("2.0", 1.75, 2.25),
            ("2.5", 2.25, 2.75),
            ("3.0", 2.75, 9999),
        ]

        results = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            for label, min_stake, max_stake in ranges:
                cursor.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN result = 'Win' THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN result = 'Loss' THEN 1 ELSE 0 END) as losses,
                        SUM(stake) as staked,
                        SUM(COALESCE(profit_loss, 0)) as profit
                    FROM bets
                    WHERE stake >= ? AND stake < ?
                    AND result IN ('Win', 'Loss')
                """, (min_stake, max_stake))

                row = cursor.fetchone()
                total = row[0] or 0
                staked = row[3] or 0
                wins = row[1] or 0

                if total > 0:  # Only include stake sizes that have bets
                    results.append({
                        'units': label,
                        'bets': total,
                        'wins': wins,
                        'losses': row[2] or 0,
                        'win_rate': (wins / total * 100) if total > 0 else 0,
                        'staked': staked,
                        'profit': row[4] or 0,
                        'roi': (row[4] / staked * 100) if staked > 0 else 0,
                    })

        return results

    def get_stats_by_disagreement(self) -> List[Dict]:
        """Get betting stats broken down by market disagreement level."""
        results = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get all settled bets with probability data
            cursor.execute("""
                SELECT
                    our_probability,
                    implied_probability,
                    result,
                    stake,
                    profit_loss
                FROM bets
                WHERE result IN ('Win', 'Loss')
                AND our_probability IS NOT NULL
                AND implied_probability IS NOT NULL
                AND implied_probability > 0
            """)

            # Categorize by disagreement level
            categories = {
                'Minor (< 1.5x)': {'bets': 0, 'wins': 0, 'staked': 0, 'profit': 0},
                'Moderate (1.5-2x)': {'bets': 0, 'wins': 0, 'staked': 0, 'profit': 0},
                'Major (2-3x)': {'bets': 0, 'wins': 0, 'staked': 0, 'profit': 0},
                'Extreme (3x+)': {'bets': 0, 'wins': 0, 'staked': 0, 'profit': 0},
            }

            for row in cursor.fetchall():
                our_prob, implied_prob, result, stake, profit_loss = row
                ratio = our_prob / implied_prob if implied_prob > 0 else 1

                if ratio < 1.5:
                    cat = 'Minor (< 1.5x)'
                elif ratio < 2.0:
                    cat = 'Moderate (1.5-2x)'
                elif ratio < 3.0:
                    cat = 'Major (2-3x)'
                else:
                    cat = 'Extreme (3x+)'

                categories[cat]['bets'] += 1
                categories[cat]['staked'] += stake or 0
                categories[cat]['profit'] += profit_loss or 0
                if result == 'Win':
                    categories[cat]['wins'] += 1

            for cat_name, data in categories.items():
                if data['bets'] > 0:
                    results.append({
                        'level': cat_name,
                        'bets': data['bets'],
                        'wins': data['wins'],
                        'win_rate': (data['wins'] / data['bets'] * 100) if data['bets'] > 0 else 0,
                        'staked': data['staked'],
                        'profit': data['profit'],
                        'roi': (data['profit'] / data['staked'] * 100) if data['staked'] > 0 else 0,
                    })

        return results

    def get_flagged_bets(self) -> List[Dict]:
        """Get bets that should be flagged for review."""
        flagged = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    id, match_date, match_description, selection, odds, stake,
                    our_probability, implied_probability, result, profit_loss
                FROM bets
                WHERE result = 'Loss'
                ORDER BY match_date DESC
            """)

            for row in cursor.fetchall():
                bet_id, date, match, selection, odds, stake, our_prob, implied_prob, result, pl = row
                flags = []

                # Calculate disagreement ratio
                if our_prob and implied_prob and implied_prob > 0:
                    ratio = our_prob / implied_prob
                    if ratio >= 3.0:
                        flags.append("EXTREME_DISAGREEMENT")
                    elif ratio >= 2.0:
                        flags.append("HIGH_DISAGREEMENT")

                # High stake on longshot
                if odds and odds >= 5.0 and stake and stake >= 2.0:
                    flags.append("HIGH_STAKE_LONGSHOT")

                # Max stake loss
                if stake and stake >= 3.0:
                    flags.append("MAX_STAKE_LOSS")

                # Longshot loss
                if odds and odds >= 10.0:
                    flags.append("EXTREME_LONGSHOT")

                if flags:
                    flagged.append({
                        'id': bet_id,
                        'date': date,
                        'match': match or f"{selection}",
                        'selection': selection,
                        'odds': odds,
                        'units': stake,
                        'our_prob': our_prob,
                        'implied_prob': implied_prob,
                        'profit_loss': pl,
                        'flags': flags,
                    })

        return flagged

    def get_cumulative_pl(self) -> List[Dict]:
        """Get cumulative P/L over time for charting."""
        results = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    match_date,
                    profit_loss
                FROM bets
                WHERE result IN ('Win', 'Loss')
                AND profit_loss IS NOT NULL
                ORDER BY match_date ASC, id ASC
            """)

            cumulative = 0
            for row in cursor.fetchall():
                date, pl = row
                cumulative += pl or 0
                results.append({
                    'date': date,
                    'pl': pl,
                    'cumulative': round(cumulative, 2),
                })

        return results

    def auto_settle_from_results(self) -> Dict:
        """Automatically settle pending bets by checking match results in database.

        Returns:
            Dict with counts of settled, not_found, errors
        """
        results = {
            'settled': 0,
            'wins': 0,
            'losses': 0,
            'not_found': 0,
            'errors': 0,
            'details': []
        }

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get all pending bets (no result yet)
            cursor.execute("""
                SELECT id, match_date, player1, player2, selection, match_description
                FROM bets
                WHERE result IS NULL
            """)
            pending_bets = cursor.fetchall()

            for bet in pending_bets:
                bet_id, match_date, player1, player2, selection, match_desc = bet

                # Try to extract player names from match_description if not set
                if (not player1 or not player2) and match_desc:
                    for sep in [' vs ', ' v ', ' - ', ' VS ', ' V ']:
                        if sep in match_desc:
                            parts = match_desc.split(sep, 1)
                            if len(parts) == 2:
                                player1 = parts[0].strip()
                                player2 = parts[1].strip()
                                break

                # Skip if we still don't have player info
                if not player1 or not player2:
                    results['not_found'] += 1
                    continue

                try:
                    # Search for the match in completed matches
                    # Try to find by matching player names within a few days of the bet date
                    cursor.execute("""
                        SELECT winner_name, loser_name, winner_id, loser_id, score, date
                        FROM matches
                        WHERE date BETWEEN date(?, '-2 days') AND date(?, '+2 days')
                        AND (
                            (winner_name LIKE ? AND loser_name LIKE ?)
                            OR (winner_name LIKE ? AND loser_name LIKE ?)
                            OR (winner_name LIKE ? AND loser_name LIKE ?)
                            OR (winner_name LIKE ? AND loser_name LIKE ?)
                        )
                        ORDER BY date DESC
                        LIMIT 1
                    """, (
                        match_date, match_date,
                        f'%{player1}%', f'%{player2}%',
                        f'%{player2}%', f'%{player1}%',
                        f'{player1[:10]}%', f'{player2[:10]}%',
                        f'{player2[:10]}%', f'{player1[:10]}%',
                    ))

                    match_result = cursor.fetchone()

                    if match_result:
                        winner_name, loser_name, winner_id, loser_id, score, match_date_actual = match_result

                        # Determine if our selection won
                        selection_lower = selection.lower().strip()
                        winner_lower = winner_name.lower().strip()

                        # Check if the selection matches the winner
                        selection_won = (
                            selection_lower in winner_lower or
                            winner_lower in selection_lower or
                            self._names_match(selection, winner_name)
                        )

                        if selection_won:
                            result_str = "Win"
                            results['wins'] += 1
                        else:
                            result_str = "Loss"
                            results['losses'] += 1

                        # Settle the bet
                        self.settle_bet(bet_id, result_str)
                        results['settled'] += 1

                        # Opponent is the other player (loser if we won, winner if we lost)
                        opponent = loser_name if selection_won else winner_name

                        results['details'].append({
                            'bet_id': bet_id,
                            'selection': selection,
                            'opponent': opponent,
                            'result': result_str,
                            'score': score
                        })
                    else:
                        results['not_found'] += 1

                except Exception as e:
                    results['errors'] += 1
                    print(f"Error settling bet {bet_id}: {e}")

        return results

    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two player names likely refer to the same person."""
        # Normalize names
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()

        # Exact match
        if n1 == n2:
            return True

        # One contains the other
        if n1 in n2 or n2 in n1:
            return True

        # Split into parts and check for significant overlap
        parts1 = set(n1.replace('.', ' ').split())
        parts2 = set(n2.replace('.', ' ').split())

        # Remove single-letter initials for comparison
        parts1_long = {p for p in parts1 if len(p) > 1}
        parts2_long = {p for p in parts2 if len(p) > 1}

        # Check if they share significant parts (last name usually)
        if parts1_long and parts2_long:
            overlap = parts1_long & parts2_long
            if overlap:
                return True

        return False


class BetTrackerUI:
    """Tkinter UI for Bet Tracker."""

    # Class variable to track singleton instance
    _instance = None
    _root_window = None

    def __new__(cls, parent: tk.Tk = None, prefill_bet: Dict = None, on_change_callback=None):
        """Ensure only one instance of BetTrackerUI exists."""
        # Check if instance exists and window is still valid
        if cls._instance is not None and cls._root_window is not None:
            try:
                if cls._root_window.winfo_exists():
                    # Window exists, bring to front
                    cls._root_window.lift()
                    cls._root_window.focus_force()
                    # If prefill data provided, open add dialog
                    if prefill_bet:
                        cls._instance.prefill_bet = prefill_bet
                        cls._instance.root.after(100, cls._instance._add_bet_dialog)
                    return cls._instance
            except tk.TclError:
                # Window was destroyed, allow new instance
                pass

        # Create new instance
        instance = super().__new__(cls)
        cls._instance = instance
        return instance

    def __init__(self, parent: tk.Tk = None, prefill_bet: Dict = None, on_change_callback=None):
        # Skip init if window already exists (singleton returned existing instance)
        if hasattr(self, '_initialized') and self._initialized:
            return

        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        # Store reference for singleton check
        BetTrackerUI._root_window = self.root

        self.root.title("Bet Tracker")
        self.root.state('zoomed')  # Launch maximized
        self.root.configure(bg=UI_COLORS["bg_dark"])

        # Handle window close to clear singleton reference
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.tracker = BetTracker()
        self.prefill_bet = prefill_bet
        self.on_change_callback = on_change_callback

        # Track sort state for each tree
        self.sort_state = {}

        # Live score state
        self.live_scores = {}  # bet_id -> score string
        self.previously_live = {}  # bet_id -> {bet_data, market_info} for bets that were live
        self.live_score_refresh_id = None  # For cancelling auto-refresh
        self.betfair_client = None  # Lazy-loaded Betfair client
        self.live_score_status = "Not connected"

        # Auto-refresh for results from monitor
        self.result_refresh_id = None
        self.last_settled_ids = set()  # Track settled bet IDs to detect changes

        self._setup_styles()
        self._build_ui()
        self._refresh_data()
        self._start_result_refresh()  # Start auto-checking for new results

        # Mark as initialized
        self._initialized = True

        # If prefill data provided, open the add bet dialog with it
        if self.prefill_bet:
            self.root.after(100, self._add_bet_dialog)

    def _on_close(self):
        """Handle window close to clear singleton reference."""
        # Stop live score refresh
        self._stop_live_score_refresh()
        # Stop result auto-refresh
        self._stop_result_refresh()

        BetTrackerUI._instance = None
        BetTrackerUI._root_window = None
        self._initialized = False
        self.root.destroy()

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
        style.configure("Stat.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 18, "bold"))
        style.configure("StatLabel.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_secondary"], font=("Segoe UI", 9))

        # Transparent stat card styles (like Darts Manager home buttons)
        style.configure("TransparentStat.TFrame", background=UI_COLORS["bg_dark"])
        style.configure("TransparentStat.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 18, "bold"))
        style.configure("TransparentStatLabel.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_secondary"], font=("Segoe UI", 9))

        style.configure("Treeview",
                       background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"],
                       fieldbackground=UI_COLORS["bg_medium"],
                       font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                       background=UI_COLORS["bg_light"],
                       foreground=UI_COLORS["text_primary"],
                       font=("Segoe UI", 9, "bold"))

        # Checkbutton style for dark mode
        style.configure("Dark.TCheckbutton",
                       background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"],
                       font=("Segoe UI", 9))
        style.map("Dark.TCheckbutton",
                 background=[('active', UI_COLORS["bg_dark"]), ('hover', UI_COLORS["bg_dark"])],
                 foreground=[('active', UI_COLORS["text_primary"]), ('hover', UI_COLORS["text_primary"])])

    def _setup_column_sorting(self, tree: ttk.Treeview, columns: tuple):
        """Setup clickable column headers for sorting."""
        tree_id = id(tree)
        self.sort_state[tree_id] = {'column': None, 'reverse': False}

        for col in columns:
            tree.heading(col, command=lambda c=col: self._sort_treeview(tree, c))

    def _sort_treeview(self, tree: ttk.Treeview, col: str):
        """Sort treeview by column."""
        tree_id = id(tree)
        state = self.sort_state[tree_id]

        # Toggle sort direction if same column
        if state['column'] == col:
            state['reverse'] = not state['reverse']
        else:
            state['column'] = col
            state['reverse'] = False

        # Get all items with their values
        items = [(tree.set(item, col), item) for item in tree.get_children('')]

        # Determine sort key based on column content
        def sort_key(item):
            value = item[0]
            # Try to parse as number (handles $10.00, +5.2%, etc.)
            clean_val = value.replace('$', '').replace('%', '').replace('+', '').replace(',', '').strip()
            try:
                return (0, float(clean_val))
            except (ValueError, TypeError):
                # Sort strings case-insensitively
                return (1, value.lower() if value else '')

        items.sort(key=sort_key, reverse=state['reverse'])

        # Rearrange items in sorted order
        for index, (_, item) in enumerate(items):
            tree.move(item, '', index)

        # Update column headers to show sort direction
        for c in tree['columns']:
            heading_text = c.upper() if c == 'id' else c.title()
            # Map column names to display text
            heading_map = {
                'id': 'ID', 'date': 'Date', 'match': 'Match', 'market': 'Market',
                'selection': 'Selection', 'stake': 'Units', 'odds': 'Odds',
                'result': 'Result', 'pl': 'P/L', 'ev': 'EV',
                'month': 'Month', 'bets': 'Bets', 'wins': 'Wins',
                'staked': 'Units', 'profit': 'Profit', 'roi': 'ROI'
            }
            text = heading_map.get(c, c.title())
            if c == col:
                arrow = ' ▼' if state['reverse'] else ' ▲'
                text += arrow
            tree.heading(c, text=text)

    def _reapply_sort(self, tree: ttk.Treeview):
        """Re-apply the current sort after data refresh."""
        tree_id = id(tree)
        if tree_id not in self.sort_state:
            return

        state = self.sort_state[tree_id]
        if state['column'] is None:
            return

        # Get the current sort column and direction
        col = state['column']
        was_reverse = state['reverse']

        # Toggle reverse so that _sort_treeview will set it back correctly
        state['reverse'] = not was_reverse

        # Re-apply sort
        self._sort_treeview(tree, col)

    def _build_ui(self):
        """Build the main UI."""
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text="Bet Tracker", style="Title.TLabel").pack(side=tk.LEFT)

        # Action buttons
        btn_frame = ttk.Frame(header_frame, style="Dark.TFrame")
        btn_frame.pack(side=tk.RIGHT)

        add_btn = tk.Button(
            btn_frame,
            text="+ New Bet",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._add_bet_dialog,
            padx=15,
            pady=5
        )
        add_btn.pack(side=tk.LEFT, padx=5)

        refresh_btn = tk.Button(
            btn_frame,
            text="Refresh",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._refresh_data,
            padx=15,
            pady=5
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)

        export_btn = tk.Button(
            btn_frame,
            text="Export",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["bg_light"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._export_bets,
            padx=15,
            pady=5
        )
        export_btn.pack(side=tk.LEFT, padx=5)

        # Stats cards
        stats_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        stats_frame.pack(fill=tk.X, pady=(0, 20))

        self.stat_widgets = {}
        stats_config = [
            ("total_bets", "Total Bets", "0"),
            ("win_rate", "Win Rate", "0%"),
            ("total_profit", "Total P/L", "0.00"),
            ("roi", "ROI", "0%"),
            ("pending", "Pending", "0"),
        ]

        for idx, (key, label, default) in enumerate(stats_config):
            card = self._create_stat_card(stats_frame, label, default)
            card.grid(row=0, column=idx, padx=10, sticky="nsew")
            self.stat_widgets[key] = card
            stats_frame.columnconfigure(idx, weight=1)

        # Notebook for different views
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # All Bets tab
        bets_frame = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(bets_frame, text="All Bets")
        self._build_bets_table(bets_frame)

        # Pending Bets tab
        pending_frame = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(pending_frame, text="Pending")
        self._build_pending_table(pending_frame)

        # Statistics tab
        stats_tab = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(stats_tab, text="Statistics")
        self._build_stats_tab(stats_tab)

        # Model Guide tab
        guide_tab = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(guide_tab, text="Model Guide")
        self._build_model_guide_tab(guide_tab)

    def _build_model_guide_tab(self, parent):
        """Build the model guide tab explaining each betting model."""
        # Scrollable frame
        canvas = tk.Canvas(parent, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="Dark.TFrame")

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Content
        content = ttk.Frame(scroll_frame, style="Dark.TFrame", padding=20)
        content.pack(fill=tk.BOTH, expand=True)

        # Title
        title = tk.Label(content, text="Betting Models Explained",
                        font=("Segoe UI", 18, "bold"),
                        fg=UI_COLORS["text_primary"], bg=UI_COLORS["bg_dark"])
        title.pack(anchor=tk.W, pady=(0, 20))

        # Model 3
        self._add_model_card(content, "Model 3 - Sharp (Moderate Edge)",
            "#f59e0b",  # Amber
            "Targets the 'smart money' zone where our analysis disagrees moderately with the market.",
            [
                ("Criteria", "Edge between 5-15% (our probability minus implied probability)"),
                ("Rationale", "Moderate disagreement with market often indicates genuine value"),
                ("Risk Profile", "Balanced risk/reward - not too aggressive, not too conservative"),
            ])

        # Model 4
        self._add_model_card(content, "Model 4 - Favorites",
            "#8b5cf6",  # Purple
            "Backs strong favorites where our model agrees with market direction.",
            [
                ("Criteria", "Our probability >= 60%"),
                ("Rationale", "Favorites have higher strike rates - consistent returns with lower variance"),
                ("Risk Profile", "Lower variance, more frequent wins but smaller payouts"),
            ])

        # Model 7
        self._add_model_card(content, "Model 7 - Grind",
            "#06b6d4",  # Cyan
            "Small edges on safer bets - grinding out consistent small profits.",
            [
                ("Criteria", "Edge 3-8% AND odds < 2.50"),
                ("Rationale", "Shorter odds have higher probability of winning - small but frequent edges"),
                ("Risk Profile", "Lowest variance, requires high volume to be meaningful"),
            ])

        # Model 8
        self._add_model_card(content, "Model 8 - Profitable Baseline",
            "#22c55e",  # Green
            "The proven profitable segment combining probability and odds filters.",
            [
                ("Criteria", "Our probability >= 55% AND odds < 2.50"),
                ("Rationale", "Combines confidence threshold with odds cap to filter highest quality bets"),
                ("Risk Profile", "Conservative approach - only bets where we're confident AND odds are reasonable"),
            ])

        # Edge calculation explanation
        edge_frame = ttk.Frame(content, style="Card.TFrame", padding=15)
        edge_frame.pack(fill=tk.X, pady=10)

        tk.Label(edge_frame, text="How Edge is Calculated",
                font=("Segoe UI", 12, "bold"),
                fg=UI_COLORS["text_primary"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

        edge_text = """
Edge = Our Probability - Implied Probability

Example:
• Our model says player has 55% chance to win
• Betfair odds are 2.20 → Implied probability = 1/2.20 = 45%
• Edge = 55% - 45% = 10%

A 10% edge means we think the player is 10 percentage points more likely to win than the market believes.
        """
        tk.Label(edge_frame, text=edge_text.strip(),
                font=("Consolas", 10),
                fg=UI_COLORS["text_secondary"], bg=UI_COLORS["bg_medium"],
                justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 0))

        # Current weights summary
        weights_frame = ttk.Frame(content, style="Card.TFrame", padding=15)
        weights_frame.pack(fill=tk.X, pady=10)

        tk.Label(weights_frame, text="Current Factor Weights",
                font=("Segoe UI", 12, "bold"),
                fg=UI_COLORS["text_primary"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

        tk.Label(weights_frame, text="The 8-factor model used for all analysis:",
                font=("Segoe UI", 9),
                fg=UI_COLORS["text_secondary"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=(2, 10))

        # Simple weights display
        from config import DEFAULT_ANALYSIS_WEIGHTS
        weights_text = ""
        for factor, weight in sorted(DEFAULT_ANALYSIS_WEIGHTS.items(), key=lambda x: -x[1]):
            if weight > 0:
                weights_text += f"  • {factor.replace('_', ' ').title()}: {weight*100:.0f}%\n"

        tk.Label(weights_frame, text=weights_text.strip(),
                font=("Consolas", 10),
                fg=UI_COLORS["text_secondary"], bg=UI_COLORS["bg_medium"],
                justify=tk.LEFT).pack(anchor=tk.W)

    def _add_model_card(self, parent, title: str, color: str, description: str, details: list):
        """Add a model explanation card."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=15)
        card.pack(fill=tk.X, pady=10)

        # Title with colored indicator
        title_frame = ttk.Frame(card, style="Card.TFrame")
        title_frame.pack(fill=tk.X)

        indicator = tk.Frame(title_frame, bg=color, width=4, height=20)
        indicator.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(title_frame, text=title,
                font=("Segoe UI", 12, "bold"),
                fg=UI_COLORS["text_primary"], bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)

        # Description
        tk.Label(card, text=description,
                font=("Segoe UI", 10),
                fg=UI_COLORS["text_secondary"], bg=UI_COLORS["bg_medium"],
                wraplength=700, justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 5))

        # Details
        for label, value in details:
            detail_frame = ttk.Frame(card, style="Card.TFrame")
            detail_frame.pack(fill=tk.X, pady=2)

            tk.Label(detail_frame, text=f"• {label}:",
                    font=("Segoe UI", 9, "bold"),
                    fg=UI_COLORS["text_primary"], bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)
            tk.Label(detail_frame, text=f" {value}",
                    font=("Segoe UI", 9),
                    fg=UI_COLORS["text_secondary"], bg=UI_COLORS["bg_medium"],
                    wraplength=600, justify=tk.LEFT).pack(side=tk.LEFT)

    def _create_stat_card(self, parent, label: str, value: str) -> tk.Frame:
        """Create a statistics card with transparent background and slate border."""
        # Use tk.Frame for border support (ttk.Frame doesn't support highlightbackground)
        card = tk.Frame(
            parent,
            bg=UI_COLORS["bg_dark"],
            highlightbackground="#475569",  # Slate border
            highlightthickness=2,
            padx=15,
            pady=15
        )

        value_label = tk.Label(
            card,
            text=value,
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"],
            font=("Segoe UI", 18, "bold")
        )
        value_label.pack(anchor=tk.CENTER)
        card.value_label = value_label

        label_widget = tk.Label(
            card,
            text=label,
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_secondary"],
            font=("Segoe UI", 9)
        )
        label_widget.pack(anchor=tk.CENTER, pady=(5, 0))

        return card

    def _build_bets_table(self, parent):
        """Build the all bets table."""
        # Filter frame
        filter_frame = ttk.Frame(parent, style="Dark.TFrame")
        filter_frame.pack(fill=tk.X, pady=(10, 5))

        ttk.Label(filter_frame, text="Filter by:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 10))

        # Result filter - multi-select checkboxes
        ttk.Label(filter_frame, text="Result:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 5))

        # Checkbox variables for each result type
        self.result_filter_vars = {
            'Win': tk.BooleanVar(value=True),
            'Loss': tk.BooleanVar(value=True),
            'Void': tk.BooleanVar(value=True),
            'Pending': tk.BooleanVar(value=True),
            'None': tk.BooleanVar(value=True),
        }

        result_check_frame = ttk.Frame(filter_frame, style="Dark.TFrame")
        result_check_frame.pack(side=tk.LEFT, padx=(0, 15))

        for result_type in ['Win', 'Loss', 'Void', 'Pending', 'None']:
            cb = ttk.Checkbutton(
                result_check_frame,
                text=result_type,
                variable=self.result_filter_vars[result_type],
                command=self._apply_bets_filter,
                style="Dark.TCheckbutton"
            )
            cb.pack(side=tk.LEFT, padx=3)

        # Market filter dropdown
        ttk.Label(filter_frame, text="Market:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        self.market_filter_var = tk.StringVar(value="All")
        market_combo = ttk.Combobox(filter_frame, textvariable=self.market_filter_var,
                                     values=["All", "Match Winner", "Set Betting", "Handicap", "Total Games", "Other"],
                                     width=14, state="readonly")
        market_combo.pack(side=tk.LEFT, padx=(0, 15))
        market_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_bets_filter())

        # Model filter dropdown
        ttk.Label(filter_frame, text="Model:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        self.model_filter_var = tk.StringVar(value="All")
        model_combo = ttk.Combobox(filter_frame, textvariable=self.model_filter_var,
                                    values=["All", "Model 3", "Model 4", "Model 7", "Model 8"],
                                    width=12, state="readonly")
        model_combo.pack(side=tk.LEFT, padx=(0, 15))
        model_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_bets_filter())

        # Search box for match/selection
        ttk.Label(filter_frame, text="Search:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        self.search_filter_var = tk.StringVar()
        self.search_filter_var.trace('w', lambda *args: self._apply_bets_filter())
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_filter_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 15))

        # Clear filters button
        clear_btn = tk.Button(
            filter_frame,
            text="Clear Filters",
            font=("Segoe UI", 9),
            fg="white",
            bg="#6b7280",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._clear_bets_filters,
            padx=10,
            pady=2
        )
        clear_btn.pack(side=tk.LEFT)

        # Spacer
        ttk.Label(filter_frame, text="  |  ", style="Dark.TLabel").pack(side=tk.LEFT, padx=5)

        # Settle buttons for All Bets (same height as Clear Filters)
        win_btn = tk.Button(
            filter_frame,
            text="Mark Win",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._settle_from_all_bets("Win"),
            padx=10,
            pady=2
        )
        win_btn.pack(side=tk.LEFT, padx=2)

        loss_btn = tk.Button(
            filter_frame,
            text="Mark Loss",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["danger"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._settle_from_all_bets("Loss"),
            padx=10,
            pady=2
        )
        loss_btn.pack(side=tk.LEFT, padx=2)

        void_btn = tk.Button(
            filter_frame,
            text="Mark Void",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._settle_from_all_bets("Void"),
            padx=10,
            pady=2
        )
        void_btn.pack(side=tk.LEFT, padx=2)

        in_progress_btn = tk.Button(
            filter_frame,
            text="In Progress",
            font=("Segoe UI", 9),
            fg="white",
            bg="#1e40af",  # Blue-800
            relief=tk.FLAT,
            cursor="hand2",
            command=self._toggle_in_progress_all_bets,
            padx=10,
            pady=2
        )
        in_progress_btn.pack(side=tk.LEFT, padx=2)

        delete_btn = tk.Button(
            filter_frame,
            text="Delete",
            font=("Segoe UI", 9),
            fg="white",
            bg="#6b7280",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._delete_selected(self.bets_tree),
            padx=10,
            pady=2
        )
        delete_btn.pack(side=tk.LEFT, padx=2)

        check_results_btn = tk.Button(
            filter_frame,
            text="Check Results",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["primary"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._auto_check_results,
            padx=10,
            pady=2
        )
        check_results_btn.pack(side=tk.LEFT, padx=2)

        # Create a container for tree and scrollbar
        tree_frame = ttk.Frame(parent, style="Dark.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("id", "date", "tour", "tournament", "match", "score", "market", "selection", "stake", "odds", "result", "pl", "model")
        self.bets_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        self.bets_tree.heading("id", text="ID")
        self.bets_tree.heading("date", text="Date")
        self.bets_tree.heading("tour", text="Tour")
        self.bets_tree.heading("tournament", text="Tournament")
        self.bets_tree.heading("match", text="Match")
        self.bets_tree.heading("score", text="Live")
        self.bets_tree.heading("market", text="Market")
        self.bets_tree.heading("selection", text="Selection")
        self.bets_tree.heading("stake", text="Units")
        self.bets_tree.heading("odds", text="Odds")
        self.bets_tree.heading("result", text="Result")
        self.bets_tree.heading("pl", text="P/L")
        self.bets_tree.heading("model", text="Model")

        self.bets_tree.column("id", width=40)
        self.bets_tree.column("date", width=80)
        self.bets_tree.column("tour", width=65)
        self.bets_tree.column("tournament", width=110)
        self.bets_tree.column("match", width=150)
        self.bets_tree.column("score", width=70)
        self.bets_tree.column("market", width=80)
        self.bets_tree.column("selection", width=100)
        self.bets_tree.column("stake", width=45)
        self.bets_tree.column("odds", width=45)
        self.bets_tree.column("result", width=50)
        self.bets_tree.column("pl", width=55)
        self.bets_tree.column("model", width=70)

        # Enable column sorting
        self._setup_column_sorting(self.bets_tree, columns)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.bets_tree.yview)
        self.bets_tree.configure(yscrollcommand=scrollbar.set)

        self.bets_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure row tags for win/loss/void highlighting
        self.bets_tree.tag_configure('win', background='#166534', foreground='white')  # Dark green
        self.bets_tree.tag_configure('loss', background='#991b1b', foreground='white')  # Dark red
        self.bets_tree.tag_configure('void', background='#854d0e', foreground='white')  # Dark yellow/amber
        self.bets_tree.tag_configure('in_progress', background='#1e40af', foreground='white')  # Blue-800

        # Button frame for All Bets
        btn_frame = ttk.Frame(parent, style="Dark.TFrame")
        btn_frame.pack(fill=tk.X, pady=10)

        delete_btn = tk.Button(
            btn_frame,
            text="Delete Selected",
            font=("Segoe UI", 10),
            fg="white",
            bg="#6b7280",  # Gray
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._delete_selected(self.bets_tree),
            padx=15,
            pady=5
        )
        delete_btn.pack(side=tk.LEFT, padx=5)

        delete_all_btn = tk.Button(
            btn_frame,
            text="Delete All",
            font=("Segoe UI", 10),
            fg="white",
            bg="#dc2626",  # Red
            relief=tk.FLAT,
            cursor="hand2",
            command=self._delete_all_bets,
            padx=15,
            pady=5
        )
        delete_all_btn.pack(side=tk.LEFT, padx=5)

        # Double-click to settle
        self.bets_tree.bind("<Double-1>", self._on_bet_double_click)

    def _build_pending_table(self, parent):
        """Build the pending bets table."""
        columns = ("id", "date", "tour", "tournament", "match", "score", "market", "selection", "stake", "odds", "ev")
        self.pending_tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)

        self.pending_tree.heading("id", text="ID")
        self.pending_tree.heading("date", text="Date")
        self.pending_tree.heading("tour", text="Tour")
        self.pending_tree.heading("tournament", text="Tournament")
        self.pending_tree.heading("match", text="Match")
        self.pending_tree.heading("score", text="Live Score")
        self.pending_tree.heading("market", text="Market")
        self.pending_tree.heading("selection", text="Selection")
        self.pending_tree.heading("stake", text="Units")
        self.pending_tree.heading("odds", text="Odds")
        self.pending_tree.heading("ev", text="EV")

        self.pending_tree.column("id", width=40)
        self.pending_tree.column("date", width=90)
        self.pending_tree.column("tour", width=80)
        self.pending_tree.column("tournament", width=130)
        self.pending_tree.column("match", width=170)
        self.pending_tree.column("score", width=90)
        self.pending_tree.column("market", width=90)
        self.pending_tree.column("selection", width=110)
        self.pending_tree.column("stake", width=50)
        self.pending_tree.column("odds", width=50)
        self.pending_tree.column("ev", width=55)

        # Enable column sorting
        self._setup_column_sorting(self.pending_tree, columns)

        # Configure tag for in-progress bets (light blue)
        self.pending_tree.tag_configure('in_progress', background='#1e40af', foreground='white')

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.pending_tree.yview)
        self.pending_tree.configure(yscrollcommand=scrollbar.set)

        self.pending_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        # Settle buttons
        btn_frame = ttk.Frame(parent, style="Dark.TFrame")
        btn_frame.pack(fill=tk.X, pady=10)

        win_btn = tk.Button(
            btn_frame,
            text="Mark Win",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._settle_selected("Win"),
            padx=15,
            pady=5
        )
        win_btn.pack(side=tk.LEFT, padx=5)

        loss_btn = tk.Button(
            btn_frame,
            text="Mark Loss",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["danger"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._settle_selected("Loss"),
            padx=15,
            pady=5
        )
        loss_btn.pack(side=tk.LEFT, padx=5)

        void_btn = tk.Button(
            btn_frame,
            text="Mark Void",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._settle_selected("Void"),
            padx=15,
            pady=5
        )
        void_btn.pack(side=tk.LEFT, padx=5)

        in_progress_btn = tk.Button(
            btn_frame,
            text="In Progress",
            font=("Segoe UI", 10),
            fg="white",
            bg="#1e40af",  # Blue-800
            relief=tk.FLAT,
            cursor="hand2",
            command=self._toggle_in_progress,
            padx=15,
            pady=5
        )
        in_progress_btn.pack(side=tk.LEFT, padx=5)

        delete_btn = tk.Button(
            btn_frame,
            text="Delete",
            font=("Segoe UI", 10),
            fg="white",
            bg="#6b7280",  # Gray
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._delete_selected(self.pending_tree),
            padx=15,
            pady=5
        )
        delete_btn.pack(side=tk.LEFT, padx=5)

        # Auto-check results button
        check_btn = tk.Button(
            btn_frame,
            text="Check Results",
            font=("Segoe UI", 10),
            fg="white",
            bg="#06b6d4",  # Cyan
            relief=tk.FLAT,
            cursor="hand2",
            command=self._auto_check_results,
            padx=15,
            pady=5
        )
        check_btn.pack(side=tk.RIGHT, padx=5)

        # Live scores section (right side)
        self.live_score_btn = tk.Button(
            btn_frame,
            text="Refresh Scores",
            font=("Segoe UI", 10),
            fg="white",
            bg="#8b5cf6",  # Purple
            relief=tk.FLAT,
            cursor="hand2",
            command=self._manual_refresh_scores,
            padx=15,
            pady=5
        )
        self.live_score_btn.pack(side=tk.RIGHT, padx=5)

        # Live score status label
        self.live_score_status_var = tk.StringVar(value="Live scores: Not connected")
        self.live_score_label = tk.Label(
            btn_frame,
            textvariable=self.live_score_status_var,
            font=("Segoe UI", 9),
            fg=UI_COLORS["text_muted"],
            bg=UI_COLORS["bg_dark"]
        )
        self.live_score_label.pack(side=tk.RIGHT, padx=10)

        # Double-click to settle
        self.pending_tree.bind("<Double-1>", self._on_pending_double_click)

        # Start auto-refresh for live scores (every 30 seconds)
        self._start_live_score_refresh()

    def _build_stats_tab(self, parent):
        """Build the statistics tab with comprehensive analytics dashboard."""
        # Create scrollable canvas for all stats
        canvas = tk.Canvas(parent, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.stats_canvas = canvas  # Store reference for width updates

        scrollable_frame = ttk.Frame(canvas, style="Dark.TFrame")
        self.stats_scrollable_frame = scrollable_frame  # Store reference

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Create window and store the ID for resizing
        self.stats_canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Bind canvas resize to update scrollable frame width
        def _on_canvas_configure(event):
            canvas.itemconfig(self.stats_canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ========== ROW 1: CHARTS (Two columns) ==========
        charts_row = ttk.Frame(scrollable_frame, style="Dark.TFrame")
        charts_row.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)
        charts_row.columnconfigure(0, weight=1, uniform="charts")
        charts_row.columnconfigure(1, weight=1, uniform="charts")

        # LEFT: Cumulative P/L Chart
        pl_chart_frame = ttk.Frame(charts_row, style="Card.TFrame", padding=15)
        pl_chart_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        ttk.Label(pl_chart_frame, text="Cumulative P/L",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)

        self.pl_chart_canvas = tk.Canvas(pl_chart_frame, height=180,
                                          bg=UI_COLORS["bg_dark"], highlightthickness=0)
        self.pl_chart_canvas.pack(fill=tk.BOTH, expand=True, pady=5)
        self.pl_chart_canvas.bind("<Configure>", lambda e: self._schedule_chart_redraw())

        # RIGHT: Win Rate & Summary
        summary_frame = ttk.Frame(charts_row, style="Card.TFrame", padding=15)
        summary_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        ttk.Label(summary_frame, text="Win/Loss Breakdown",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)

        # Win rate donut chart
        self.winrate_canvas = tk.Canvas(summary_frame, width=160, height=160,
                                         bg=UI_COLORS["bg_medium"], highlightthickness=0)
        self.winrate_canvas.pack(side=tk.LEFT, padx=20, pady=10)

        # Stats beside donut
        self.summary_stats_frame = ttk.Frame(summary_frame, style="Card.TFrame")
        self.summary_stats_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        self.summary_labels = {}
        for stat in ['wins', 'losses', 'pending', 'best_streak', 'worst_streak', 'avg_odds']:
            row = ttk.Frame(self.summary_stats_frame, style="Card.TFrame")
            row.pack(fill=tk.X, pady=2)
            label = ttk.Label(row, text=stat.replace('_', ' ').title() + ":",
                             style="Card.TLabel", font=("Segoe UI", 9))
            label.pack(side=tk.LEFT)
            value = ttk.Label(row, text="-", style="Card.TLabel", font=("Segoe UI", 9, "bold"))
            value.pack(side=tk.RIGHT)
            self.summary_labels[stat] = value

        # ========== ROW 2: Performance Tables (Two columns) ==========
        tables_row = ttk.Frame(scrollable_frame, style="Dark.TFrame")
        tables_row.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)
        tables_row.columnconfigure(0, weight=1, uniform="tables")
        tables_row.columnconfigure(1, weight=1, uniform="tables")

        # LEFT: ROI by Odds Range
        odds_frame = ttk.Frame(tables_row, style="Card.TFrame", padding=15)
        odds_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        ttk.Label(odds_frame, text="Performance by Odds Range",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(odds_frame, text="Where is your model reliable?",
                  style="Card.TLabel", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 5))

        columns = ("range", "bets", "wins", "win_rate", "profit", "roi")
        self.odds_tree = ttk.Treeview(odds_frame, columns=columns, show="headings", height=5)
        for col, width, stretch in [("range", 90, True), ("bets", 50, False), ("wins", 50, False), ("win_rate", 70, False), ("profit", 70, False), ("roi", 70, False)]:
            self.odds_tree.heading(col, text=col.replace('_', ' ').title())
            self.odds_tree.column(col, width=width, minwidth=width, stretch=stretch)
        self.odds_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Odds bar chart below table
        self.odds_bar_canvas = tk.Canvas(odds_frame, height=80,
                                          bg=UI_COLORS["bg_dark"], highlightthickness=0)
        self.odds_bar_canvas.pack(fill=tk.BOTH, expand=True, pady=5)
        self.odds_bar_canvas.bind("<Configure>", lambda e: self._schedule_chart_redraw())

        # RIGHT: ROI by Stake Size
        stake_frame = ttk.Frame(tables_row, style="Card.TFrame", padding=15)
        stake_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        ttk.Label(stake_frame, text="Performance by Stake Size",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(stake_frame, text="Do higher stakes perform better?",
                  style="Card.TLabel", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 5))

        columns = ("units", "bets", "wins", "win_rate", "profit", "roi")
        self.stake_tree = ttk.Treeview(stake_frame, columns=columns, show="headings", height=5)
        for col, width, stretch in [("units", 70, True), ("bets", 50, False), ("wins", 50, False), ("win_rate", 70, False), ("profit", 70, False), ("roi", 70, False)]:
            self.stake_tree.heading(col, text=col.replace('_', ' ').title())
            self.stake_tree.column(col, width=width, minwidth=width, stretch=stretch)
        self.stake_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Stake bar chart below table
        self.stake_bar_canvas = tk.Canvas(stake_frame, height=80,
                                           bg=UI_COLORS["bg_dark"], highlightthickness=0)
        self.stake_bar_canvas.pack(fill=tk.BOTH, expand=True, pady=5)
        self.stake_bar_canvas.bind("<Configure>", lambda e: self._schedule_chart_redraw())

        # ========== ROW 3: Disagreement & Monthly (Two columns) ==========
        row3 = ttk.Frame(scrollable_frame, style="Dark.TFrame")
        row3.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)
        row3.columnconfigure(0, weight=1, uniform="row3")
        row3.columnconfigure(1, weight=1, uniform="row3")

        # LEFT: Market Disagreement Analysis
        disagree_frame = ttk.Frame(row3, style="Card.TFrame", padding=15)
        disagree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        ttk.Label(disagree_frame, text="Market Disagreement Analysis",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(disagree_frame, text="Our probability vs implied (ratio)",
                  style="Card.TLabel", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 5))

        columns = ("level", "bets", "wins", "win_rate", "profit", "roi")
        self.disagree_tree = ttk.Treeview(disagree_frame, columns=columns, show="headings", height=4)
        for col, width, stretch in [("level", 120, True), ("bets", 50, False), ("wins", 50, False), ("win_rate", 70, False), ("profit", 70, False), ("roi", 70, False)]:
            self.disagree_tree.heading(col, text=col.replace('_', ' ').title())
            self.disagree_tree.column(col, width=width, minwidth=width, stretch=stretch)
        self.disagree_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # RIGHT: Monthly Performance
        monthly_frame = ttk.Frame(row3, style="Card.TFrame", padding=15)
        monthly_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        ttk.Label(monthly_frame, text="Monthly Performance",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)

        columns = ("month", "bets", "wins", "profit", "roi")
        self.monthly_tree = ttk.Treeview(monthly_frame, columns=columns, show="headings", height=4)
        for col, width, stretch in [("month", 90, True), ("bets", 60, False), ("wins", 60, False), ("profit", 80, False), ("roi", 80, False)]:
            self.monthly_tree.heading(col, text=col.replace('_', ' ').title())
            self.monthly_tree.column(col, width=width, minwidth=width, stretch=stretch)
        self.monthly_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # ========== ROW 3.5: Tour Performance (Full width) ==========
        tour_frame = ttk.Frame(scrollable_frame, style="Card.TFrame", padding=15)
        tour_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        ttk.Label(tour_frame, text="Performance by Tour Level",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(tour_frame, text="Which tour levels is the model profitable on?",
                  style="Card.TLabel", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 5))

        columns = ("tour", "bets", "wins", "win_rate", "staked", "profit", "roi")
        self.tour_tree = ttk.Treeview(tour_frame, columns=columns, show="headings", height=5)
        for col, width, stretch in [("tour", 100, True), ("bets", 60, False), ("wins", 60, False), ("win_rate", 80, False), ("staked", 80, False), ("profit", 80, False), ("roi", 80, False)]:
            self.tour_tree.heading(col, text=col.replace('_', ' ').title())
            self.tour_tree.column(col, width=width, minwidth=width, stretch=stretch)
        self.tour_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Configure row tags for color coding
        self.tour_tree.tag_configure('profitable', foreground='#22c55e')  # Green
        self.tour_tree.tag_configure('losing', foreground='#ef4444')      # Red

        # ========== ROW 3.6: Model Performance (Full width) ==========
        model_frame = ttk.Frame(scrollable_frame, style="Card.TFrame", padding=15)
        model_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        ttk.Label(model_frame, text="Performance by Model",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(model_frame, text="M1=All | M2=Tiered | M3=Edge 5-15% | M4=Fav | M5=Dog | M6=Edge≥10% | M7=Grind",
                  style="Card.TLabel", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 5))

        columns = ("model", "bets", "wins", "losses", "win_rate", "staked", "profit", "roi")
        self.model_tree = ttk.Treeview(model_frame, columns=columns, show="headings", height=10)
        for col, width, stretch in [("model", 50, False), ("bets", 60, False), ("wins", 60, False), ("losses", 60, False), ("win_rate", 80, False), ("staked", 80, False), ("profit", 80, False), ("roi", 80, False)]:
            self.model_tree.heading(col, text=col.replace('_', ' ').title())
            self.model_tree.column(col, width=width, minwidth=width, stretch=stretch)
        self.model_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Configure row tags for color coding
        self.model_tree.tag_configure('profitable', foreground='#22c55e')  # Green
        self.model_tree.tag_configure('losing', foreground='#ef4444')      # Red

        # ========== ROW 4: Flagged Bets (Full width) ==========
        flagged_frame = ttk.Frame(scrollable_frame, style="Card.TFrame", padding=15)
        flagged_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        ttk.Label(flagged_frame, text="Flagged Bets for Review",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(flagged_frame, text="Losses that warrant investigation - model errors or variance?",
                  style="Card.TLabel", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 5))

        columns = ("date", "match", "selection", "odds", "units", "pl", "flags")
        self.flagged_tree = ttk.Treeview(flagged_frame, columns=columns, show="headings", height=6)
        for col, width, stretch in [("date", 85, False), ("match", 280, True), ("selection", 140, False), ("odds", 60, False), ("units", 55, False), ("pl", 60, False), ("flags", 250, True)]:
            self.flagged_tree.heading(col, text=col.upper() if col in ['pl'] else col.title())
            self.flagged_tree.column(col, width=width, minwidth=width, stretch=stretch)
        self.flagged_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # ========== ROW 5: Market Breakdown (Full width) ==========
        market_frame = ttk.Frame(scrollable_frame, style="Card.TFrame", padding=15)
        market_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        ttk.Label(market_frame, text="Performance by Market",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)

        columns = ("market", "bets", "wins", "staked", "profit", "roi")
        self.market_tree = ttk.Treeview(market_frame, columns=columns, show="headings", height=5)

        self.market_tree.heading("market", text="Market")
        self.market_tree.heading("bets", text="Bets")
        self.market_tree.heading("wins", text="Wins")
        self.market_tree.heading("staked", text="Units")
        self.market_tree.heading("profit", text="Profit")
        self.market_tree.heading("roi", text="ROI")

        self.market_tree.column("market", width=200, minwidth=150, stretch=True)
        self.market_tree.column("bets", width=80, minwidth=60, stretch=False)
        self.market_tree.column("wins", width=80, minwidth=60, stretch=False)
        self.market_tree.column("staked", width=100, minwidth=80, stretch=False)
        self.market_tree.column("profit", width=100, minwidth=80, stretch=False)
        self.market_tree.column("roi", width=100, minwidth=80, stretch=False)

        self.market_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # ========== ROW 6: Gender Performance (Full width) ==========
        gender_frame = ttk.Frame(scrollable_frame, style="Card.TFrame", padding=15)
        gender_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        ttk.Label(gender_frame, text="Performance by Gender",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(gender_frame, text="Male = ATP, Challenger, Grand Slam | Female = WTA, ITF",
                  style="Card.TLabel", font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0, 5))

        columns = ("gender", "bets", "wins", "losses", "win_rate", "staked", "profit", "roi")
        self.gender_tree = ttk.Treeview(gender_frame, columns=columns, show="headings", height=2)
        for col, width, stretch in [("gender", 100, False), ("bets", 60, False), ("wins", 60, False), ("losses", 60, False), ("win_rate", 80, False), ("staked", 80, False), ("profit", 80, False), ("roi", 80, False)]:
            self.gender_tree.heading(col, text=col.replace('_', ' ').title())
            self.gender_tree.column(col, width=width, minwidth=width, stretch=stretch)
        self.gender_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Configure row tags for color coding
        self.gender_tree.tag_configure('profitable', foreground='#22c55e')  # Green
        self.gender_tree.tag_configure('losing', foreground='#ef4444')      # Red

    def _refresh_data(self, skip_date_sync: bool = False):
        """Refresh all data displays.

        Args:
            skip_date_sync: If True, skip syncing bet dates from upcoming matches.
                           Use this when refreshing after a user edit to preserve
                           manually entered dates.
        """
        # Sync pending bet dates from upcoming_matches first (unless skipped)
        if not skip_date_sync:
            updated = db.sync_pending_bet_dates()
            if updated > 0:
                print(f"Updated {updated} pending bet date(s) from upcoming matches")

        self._refresh_stats()
        self._refresh_bets_table()
        self._refresh_pending_table()
        self._refresh_stats_tab()

    def _notify_change(self):
        """Notify the parent window that bet data has changed."""
        # Use after() to call asynchronously and avoid focus issues
        self.root.after(10, self._safe_callback)

    def _safe_callback(self):
        """Safely call the change callback or find main window to update."""
        try:
            if self.on_change_callback:
                self.on_change_callback()
            else:
                # Try to find main window and update its stats
                main_window = self.root.nametowidget('.')
                if hasattr(main_window, 'main_app') and hasattr(main_window.main_app, '_update_stats'):
                    main_window.main_app._update_stats()
        except Exception:
            pass  # Ignore if parent window was closed

    def _refresh_stats(self):
        """Refresh the stats cards."""
        try:
            stats = db.get_betting_stats()
            pending = db.get_pending_bets()

            self.stat_widgets["total_bets"].value_label.configure(
                text=f"{stats['total_bets']}"
            )
            self.stat_widgets["win_rate"].value_label.configure(
                text=f"{stats['win_rate']:.1f}%"
            )

            profit = stats['total_profit']
            profit_color = UI_COLORS["success"] if profit >= 0 else UI_COLORS["danger"]
            self.stat_widgets["total_profit"].value_label.configure(
                text=f"{profit:+.2f}",
                foreground=profit_color
            )

            roi = stats['roi']
            roi_color = UI_COLORS["success"] if roi >= 0 else UI_COLORS["danger"]
            self.stat_widgets["roi"].value_label.configure(
                text=f"{roi:+.1f}%",
                foreground=roi_color
            )

            self.stat_widgets["pending"].value_label.configure(
                text=f"{len(pending)}"
            )
        except Exception as e:
            print(f"Error refreshing stats: {e}")

    def _format_match_date(self, date_str: str) -> str:
        """Format match date to YYYY-MM-DD HH:MM (strip seconds if present)."""
        if not date_str:
            return ''
        # If it has seconds (e.g., "2026-01-22 14:00:00"), strip them
        # Format: YYYY-MM-DD HH:MM:SS -> YYYY-MM-DD HH:MM
        if len(date_str) > 16 and date_str[16] == ':':
            return date_str[:16]
        return date_str

    def _refresh_bets_table(self):
        """Refresh the all bets table."""
        # Store all bets data for filtering (values tuple + in_progress flag)
        self.all_bets_data = []
        bets = db.get_all_bets()
        for bet in bets:
            pl = bet.get('profit_loss')
            pl_str = f"{pl:+.2f}" if pl is not None else "-"

            # Always recalculate model based on current criteria
            factor_scores = bet.get('factor_scores')
            if isinstance(factor_scores, str):
                import json
                try:
                    factor_scores = json.loads(factor_scores)
                except:
                    factor_scores = None

            model = calculate_bet_model(
                bet.get('our_probability', 0.5),
                bet.get('implied_probability', 0.5),
                bet.get('tournament', ''),
                bet.get('odds'),
                factor_scores
            )
            # Shorten model display: "Model 1, Model 2" -> "M1, M2"
            model_short = model.replace("Model ", "M") if model else "M1"

            # Get live score if available (only for pending bets)
            bet_id = bet.get('id')
            score_str = self.live_scores.get(bet_id, "") if bet.get('result') is None else ""

            values = (
                bet_id,
                self._format_match_date(bet.get('match_date', '')),
                get_tour_level(bet.get('tournament', '')),
                bet.get('tournament', ''),
                bet.get('match_description', ''),
                score_str,
                bet.get('market', ''),
                bet.get('selection', ''),
                f"{bet.get('stake', 0):.2f}",
                f"{bet.get('odds', 0):.2f}",
                bet.get('result', 'Pending'),
                pl_str,
                model_short,
            )
            # Store tuple of (values, in_progress)
            self.all_bets_data.append((values, bet.get('in_progress', 0)))

        self._apply_bets_filter()

    def _apply_bets_filter(self):
        """Apply filters to the bets table."""
        self.bets_tree.delete(*self.bets_tree.get_children())

        if not hasattr(self, 'all_bets_data'):
            return

        # Get filter values
        market_filter = self.market_filter_var.get() if hasattr(self, 'market_filter_var') else "All"
        model_filter = self.model_filter_var.get() if hasattr(self, 'model_filter_var') else "All"
        search_text = self.search_filter_var.get().lower().strip() if hasattr(self, 'search_filter_var') else ""

        # Get selected result types
        selected_results = set()
        if hasattr(self, 'result_filter_vars'):
            for result_type, var in self.result_filter_vars.items():
                if var.get():
                    selected_results.add(result_type)
        else:
            selected_results = {'Win', 'Loss', 'Void', 'Pending', 'None'}

        # Column indices: id=0, date=1, tour=2, tournament=3, match=4, score=5, market=6, selection=7, stake=8, odds=9, result=10, pl=11, model=12
        for bet_values, in_progress in self.all_bets_data:
            # Check result filter (multi-select)
            bet_result = bet_values[10]
            if bet_result is None or bet_result == '' or bet_result == 'None':
                result_key = 'None'
            elif bet_result == 'Pending':
                result_key = 'Pending'
            else:
                result_key = bet_result

            if result_key not in selected_results:
                continue

            # Check market filter
            if market_filter != "All":
                bet_market = str(bet_values[6]) if bet_values[6] else ""
                if bet_market != market_filter:
                    continue

            # Check model filter (model is at index 12)
            # Model data is stored as "M1,M4,M6" format
            if model_filter != "All":
                bet_model = str(bet_values[12]) if bet_values[12] else "M1"
                if model_filter == "Model 1 Only":
                    # Show only bets that are M1 but NOT any other model
                    if any(f"M{i}" in bet_model for i in range(2, 8)):
                        continue
                elif model_filter.startswith("Model "):
                    # Convert "Model 2" to "M2" for comparison
                    model_num = model_filter.replace("Model ", "M")
                    if model_num not in bet_model:
                        continue

            # Check search text (searches match description, tournament, and selection)
            if search_text:
                match_desc = str(bet_values[4]).lower() if bet_values[4] else ""
                tournament = str(bet_values[3]).lower() if bet_values[3] else ""
                selection = str(bet_values[7]).lower() if bet_values[7] else ""
                if search_text not in match_desc and search_text not in selection and search_text not in tournament:
                    continue

            # Determine row tag based on result, in_progress status, or live score
            row_tag = ()
            score_val = bet_values[5] if len(bet_values) > 5 else ""
            if in_progress or (score_val and score_val not in ("", "-")):
                row_tag = ('in_progress',)
            elif bet_result == 'Win':
                row_tag = ('win',)
            elif bet_result == 'Loss':
                row_tag = ('loss',)
            elif bet_result == 'Void':
                row_tag = ('void',)

            self.bets_tree.insert("", tk.END, values=bet_values, tags=row_tag)

        # Re-apply sort if one was set
        self._reapply_sort(self.bets_tree)

    def _clear_bets_filters(self):
        """Clear all filter fields - show all bets."""
        # Check all result checkboxes
        for var in self.result_filter_vars.values():
            var.set(True)
        self.market_filter_var.set("All")
        self.model_filter_var.set("All")
        self.search_filter_var.set("")

    def _refresh_pending_table(self):
        """Refresh the pending bets table."""
        self.pending_tree.delete(*self.pending_tree.get_children())

        pending = db.get_pending_bets()
        for bet in pending:
            ev = bet.get('ev_at_placement')
            ev_str = f"{ev:.1%}" if ev is not None else "-"

            # Get live score if available
            bet_id = bet.get('id')
            score_str = self.live_scores.get(bet_id, "-")

            # Apply in_progress tag if bet is marked as in progress
            tags = ('in_progress',) if bet.get('in_progress') else ()
            # Also highlight if match is live
            if score_str and score_str not in ("-", "Not started"):
                tags = ('in_progress',)

            self.pending_tree.insert("", tk.END, values=(
                bet_id,
                self._format_match_date(bet.get('match_date', '')),
                get_tour_level(bet.get('tournament', '')),
                bet.get('tournament', ''),
                bet.get('match_description', ''),
                score_str,
                bet.get('market', ''),
                bet.get('selection', ''),
                f"{bet.get('stake', 0):.2f}",
                f"{bet.get('odds', 0):.2f}",
                ev_str,
            ), tags=tags)

        # Re-apply sort if one was set
        self._reapply_sort(self.pending_tree)

    def _refresh_stats_tab(self):
        """Refresh the statistics tab with all analytics and charts."""
        # Get all data first
        cumulative = self.tracker.get_cumulative_pl()
        odds_stats = self.tracker.get_stats_by_odds_range()
        stake_stats = self.tracker.get_stats_by_stake_size()
        disagree_stats = self.tracker.get_stats_by_disagreement()
        monthly = self.tracker.get_stats_by_month()
        tour_stats = self.tracker.get_stats_by_tour()
        flagged = self.tracker.get_flagged_bets()
        markets = self.tracker.get_stats_by_market()

        # === DRAW P/L LINE CHART ===
        self._draw_pl_chart(cumulative)

        # === DRAW WIN RATE DONUT ===
        self._draw_winrate_donut(cumulative)

        # === UPDATE SUMMARY STATS ===
        self._update_summary_stats(cumulative, odds_stats)

        # === ROI BY ODDS RANGE TABLE ===
        self.odds_tree.delete(*self.odds_tree.get_children())
        for s in odds_stats:
            tag = "profit" if s['roi'] > 0 else "loss" if s['roi'] < -20 else ""
            self.odds_tree.insert("", tk.END, values=(
                s['range'], s['bets'], s['wins'],
                f"{s['win_rate']:.1f}%", f"{s['profit']:+.2f}", f"{s['roi']:+.1f}%",
            ), tags=(tag,))
        self.odds_tree.tag_configure("profit", foreground="#22c55e")
        self.odds_tree.tag_configure("loss", foreground="#ef4444")

        # === DRAW ODDS BAR CHART ===
        self._draw_bar_chart(self.odds_bar_canvas, odds_stats, 'range', 'roi')

        # === ROI BY STAKE SIZE TABLE ===
        self.stake_tree.delete(*self.stake_tree.get_children())
        for s in stake_stats:
            tag = "profit" if s['roi'] > 0 else "loss" if s['roi'] < -20 else ""
            self.stake_tree.insert("", tk.END, values=(
                s['units'], s['bets'], s['wins'],
                f"{s['win_rate']:.1f}%", f"{s['profit']:+.2f}", f"{s['roi']:+.1f}%",
            ), tags=(tag,))
        self.stake_tree.tag_configure("profit", foreground="#22c55e")
        self.stake_tree.tag_configure("loss", foreground="#ef4444")

        # === DRAW STAKE BAR CHART ===
        self._draw_bar_chart(self.stake_bar_canvas, stake_stats, 'units', 'roi')

        # === MARKET DISAGREEMENT TABLE ===
        self.disagree_tree.delete(*self.disagree_tree.get_children())
        for s in disagree_stats:
            tag = "profit" if s['roi'] > 0 else "loss" if s['roi'] < -20 else ""
            self.disagree_tree.insert("", tk.END, values=(
                s['level'], s['bets'], s['wins'],
                f"{s['win_rate']:.1f}%", f"{s['profit']:+.2f}", f"{s['roi']:+.1f}%",
            ), tags=(tag,))
        self.disagree_tree.tag_configure("profit", foreground="#22c55e")
        self.disagree_tree.tag_configure("loss", foreground="#ef4444")

        # === MONTHLY PERFORMANCE TABLE ===
        self.monthly_tree.delete(*self.monthly_tree.get_children())
        for m in monthly:
            tag = "profit" if m['profit'] > 0 else "loss" if m['profit'] < 0 else ""
            self.monthly_tree.insert("", tk.END, values=(
                m['month'], m['bets'], m['wins'],
                f"{m['profit']:+.2f}", f"{m['roi']:+.1f}%",
            ), tags=(tag,))
        self.monthly_tree.tag_configure("profit", foreground="#22c55e")
        self.monthly_tree.tag_configure("loss", foreground="#ef4444")

        # === TOUR PERFORMANCE TABLE ===
        self.tour_tree.delete(*self.tour_tree.get_children())
        for s in tour_stats:
            tag = "profitable" if s['profit'] > 0 else "losing" if s['profit'] < 0 else ""
            self.tour_tree.insert("", tk.END, values=(
                s['tour'], s['bets'], s['wins'],
                f"{s['win_rate']:.1f}%", f"{s['staked']:.1f}",
                f"{s['profit']:+.2f}", f"{s['roi']:+.1f}%",
            ), tags=(tag,))

        # === MODEL PERFORMANCE TABLE ===
        model_stats = self.tracker.get_stats_by_model()
        self.model_tree.delete(*self.model_tree.get_children())
        for s in model_stats:
            tag = "profitable" if s['profit'] > 0 else "losing" if s['profit'] < 0 else ""
            # Shorten model name: "Model 1" -> "M1"
            model_short = s['model'].replace("Model ", "M")
            self.model_tree.insert("", tk.END, values=(
                model_short, s['bets'], s['wins'], s['losses'],
                f"{s['win_rate']:.1f}%", f"{s['staked']:.1f}",
                f"{s['profit']:+.2f}", f"{s['roi']:+.1f}%",
            ), tags=(tag,))

        # === FLAGGED BETS TABLE ===
        self.flagged_tree.delete(*self.flagged_tree.get_children())
        for bet in flagged[:15]:
            flags_str = ", ".join(bet['flags'])
            self.flagged_tree.insert("", tk.END, values=(
                bet['date'],
                bet['match'][:40] + "..." if len(bet.get('match', '')) > 40 else bet.get('match', ''),
                bet['selection'],
                f"{bet['odds']:.2f}" if bet['odds'] else "-",
                f"{bet['units']:.1f}" if bet['units'] else "-",
                f"{bet['profit_loss']:+.2f}" if bet['profit_loss'] else "-",
                flags_str,
            ), tags=("flagged",))
        self.flagged_tree.tag_configure("flagged", foreground="#f97316")

        # === MARKET BREAKDOWN TABLE ===
        self.market_tree.delete(*self.market_tree.get_children())
        for market, stats in markets.items():
            tag = "profit" if stats['profit'] > 0 else "loss" if stats['profit'] < 0 else ""
            self.market_tree.insert("", tk.END, values=(
                market, stats['total_bets'], stats['wins'],
                f"{stats['staked']:.2f}", f"{stats['profit']:+.2f}", f"{stats['roi']:+.1f}%",
            ), tags=(tag,))
        self.market_tree.tag_configure("profit", foreground="#22c55e")
        self.market_tree.tag_configure("loss", foreground="#ef4444")

        # === GENDER PERFORMANCE TABLE ===
        gender_stats = self.tracker.get_stats_by_gender()
        self.gender_tree.delete(*self.gender_tree.get_children())
        for s in gender_stats:
            tag = "profitable" if s['profit'] > 0 else "losing" if s['profit'] < 0 else ""
            self.gender_tree.insert("", tk.END, values=(
                s['gender'], s['bets'], s['wins'], s['losses'],
                f"{s['win_rate']:.1f}%", f"{s['staked']:.1f}",
                f"{s['profit']:+.2f}", f"{s['roi']:+.1f}%",
            ), tags=(tag,))

    def _draw_pl_chart(self, cumulative):
        """Draw cumulative P/L line chart on canvas."""
        canvas = self.pl_chart_canvas
        canvas.delete("all")

        width = canvas.winfo_width() or 500
        height = canvas.winfo_height() or 180
        padding = 40

        if not cumulative or len(cumulative) < 2:
            canvas.create_text(width//2, height//2, text="Not enough data",
                              fill=UI_COLORS["text_secondary"], font=("Segoe UI", 10))
            return

        # Get data points
        values = [c['cumulative'] for c in cumulative]
        min_val = min(values)
        max_val = max(values)
        val_range = max_val - min_val or 1

        # Draw zero line
        zero_y = height - padding - ((0 - min_val) / val_range) * (height - 2*padding)
        canvas.create_line(padding, zero_y, width-padding, zero_y,
                          fill="#4b5563", dash=(2, 2))
        canvas.create_text(padding-5, zero_y, text="0", anchor="e",
                          fill=UI_COLORS["text_secondary"], font=("Segoe UI", 8))

        # Draw line
        points = []
        for i, val in enumerate(values):
            x = padding + (i / (len(values)-1)) * (width - 2*padding)
            y = height - padding - ((val - min_val) / val_range) * (height - 2*padding)
            points.extend([x, y])

        if len(points) >= 4:
            # Determine color based on final value
            line_color = "#22c55e" if values[-1] >= 0 else "#ef4444"
            canvas.create_line(points, fill=line_color, width=2, smooth=True)

            # Fill area under/over zero
            fill_points = [padding, zero_y] + points + [width-padding, zero_y]
            fill_color = "#22c55e" if values[-1] >= 0 else "#ef4444"
            canvas.create_polygon(fill_points, fill=fill_color, stipple="gray50", outline="")

        # Draw current value
        final_val = values[-1]
        color = "#22c55e" if final_val >= 0 else "#ef4444"
        canvas.create_text(width-padding, 15, text=f"{final_val:+.2f} units",
                          anchor="e", fill=color, font=("Segoe UI", 12, "bold"))

        # Labels
        canvas.create_text(padding, height-10, text=cumulative[0]['date'][:10],
                          anchor="w", fill=UI_COLORS["text_secondary"], font=("Segoe UI", 7))
        canvas.create_text(width-padding, height-10, text=cumulative[-1]['date'][:10],
                          anchor="e", fill=UI_COLORS["text_secondary"], font=("Segoe UI", 7))

    def _draw_winrate_donut(self, cumulative):
        """Draw win rate donut chart."""
        canvas = self.winrate_canvas
        canvas.delete("all")

        size = 150
        center = size // 2
        outer_r = 60
        inner_r = 35

        # Count wins and losses
        wins = sum(1 for c in cumulative if c['pl'] and c['pl'] > 0)
        losses = sum(1 for c in cumulative if c['pl'] and c['pl'] < 0)
        total = wins + losses

        if total == 0:
            canvas.create_text(center, center, text="No data",
                              fill=UI_COLORS["text_secondary"], font=("Segoe UI", 9))
            return

        win_pct = wins / total
        loss_pct = losses / total

        # Draw loss arc (red) - full circle as background
        canvas.create_arc(center-outer_r, center-outer_r, center+outer_r, center+outer_r,
                         start=90, extent=-360, fill="#ef4444", outline="")

        # Draw win arc (green) - overlay
        win_extent = -360 * win_pct
        canvas.create_arc(center-outer_r, center-outer_r, center+outer_r, center+outer_r,
                         start=90, extent=win_extent, fill="#22c55e", outline="")

        # Draw inner circle (donut hole)
        canvas.create_oval(center-inner_r, center-inner_r, center+inner_r, center+inner_r,
                          fill=UI_COLORS["bg_medium"], outline="")

        # Draw percentage text in center
        canvas.create_text(center, center-8, text=f"{win_pct*100:.1f}%",
                          fill=UI_COLORS["text_primary"], font=("Segoe UI", 14, "bold"))
        canvas.create_text(center, center+10, text="Win Rate",
                          fill=UI_COLORS["text_secondary"], font=("Segoe UI", 8))

    def _update_summary_stats(self, cumulative, odds_stats):
        """Update summary statistics labels."""
        wins = sum(1 for c in cumulative if c['pl'] and c['pl'] > 0)
        losses = sum(1 for c in cumulative if c['pl'] and c['pl'] < 0)

        # Calculate streaks
        best_streak = worst_streak = current_streak = 0
        for c in cumulative:
            if c['pl'] and c['pl'] > 0:
                if current_streak > 0:
                    current_streak += 1
                else:
                    current_streak = 1
                best_streak = max(best_streak, current_streak)
            elif c['pl'] and c['pl'] < 0:
                if current_streak < 0:
                    current_streak -= 1
                else:
                    current_streak = -1
                worst_streak = min(worst_streak, current_streak)

        # Get pending count
        pending = len(db.get_pending_bets())

        # Calculate average odds from all bets
        total_bets = sum(s['bets'] for s in odds_stats)

        self.summary_labels['wins'].configure(text=str(wins), foreground="#22c55e")
        self.summary_labels['losses'].configure(text=str(losses), foreground="#ef4444")
        self.summary_labels['pending'].configure(text=str(pending), foreground="#f59e0b")
        self.summary_labels['best_streak'].configure(text=f"{best_streak}W", foreground="#22c55e")
        self.summary_labels['worst_streak'].configure(text=f"{abs(worst_streak)}L", foreground="#ef4444")
        self.summary_labels['avg_odds'].configure(text=f"{total_bets} bets")

    def _draw_bar_chart(self, canvas, data, label_key, value_key):
        """Draw a horizontal bar chart showing ROI by category."""
        canvas.delete("all")

        width = canvas.winfo_width() or 400
        height = canvas.winfo_height() or 80
        padding = 10

        if not data:
            return

        # Find max absolute value for scaling
        max_abs = max(abs(d[value_key]) for d in data) or 1

        bar_height = (height - 2*padding) / len(data) - 4
        center_x = width // 2

        for i, d in enumerate(data):
            y = padding + i * (bar_height + 4)
            val = d[value_key]

            # Calculate bar width (scaled to half the canvas)
            bar_width = (abs(val) / max_abs) * (width//2 - padding - 40)

            # Determine color and position
            if val >= 0:
                color = "#22c55e"
                x1, x2 = center_x, center_x + bar_width
            else:
                color = "#ef4444"
                x1, x2 = center_x - bar_width, center_x

            # Draw bar
            canvas.create_rectangle(x1, y, x2, y + bar_height, fill=color, outline="")

            # Draw label
            canvas.create_text(padding, y + bar_height//2, text=d[label_key],
                              anchor="w", fill=UI_COLORS["text_secondary"], font=("Segoe UI", 7))

            # Draw value
            canvas.create_text(width-padding, y + bar_height//2, text=f"{val:+.1f}%",
                              anchor="e", fill=color, font=("Segoe UI", 7, "bold"))

        # Draw center line
        canvas.create_line(center_x, padding, center_x, height-padding,
                          fill="#4b5563", width=1)

    def _schedule_chart_redraw(self):
        """Schedule a chart redraw with debouncing to avoid excessive redraws."""
        if hasattr(self, '_chart_redraw_pending') and self._chart_redraw_pending:
            self.root.after_cancel(self._chart_redraw_pending)
        self._chart_redraw_pending = self.root.after(100, self._do_chart_redraw)

    def _do_chart_redraw(self):
        """Actually redraw the charts."""
        self._chart_redraw_pending = None
        try:
            self._refresh_stats_tab()
        except Exception:
            pass  # Ignore errors during initial resize

    def _add_bet_dialog(self):
        """Show dialog to add a new bet."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Bet")
        dialog.geometry("500x500")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, style="Dark.TFrame", padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Get prefill data if available
        prefill = self.prefill_bet or {}

        # Date and Time
        ttk.Label(frame, text="Date:", style="Dark.TLabel").grid(row=0, column=0, sticky=tk.W, pady=5)
        date_time_frame = ttk.Frame(frame, style="Dark.TFrame")
        date_time_frame.grid(row=0, column=1, pady=5, padx=10, sticky=tk.W)

        date_var = tk.StringVar(value=prefill.get('date', datetime.now().strftime("%Y-%m-%d")))
        date_entry = ttk.Entry(date_time_frame, textvariable=date_var, width=12)
        date_entry.pack(side=tk.LEFT)

        ttk.Label(date_time_frame, text=" Time:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(10, 5))
        time_var = tk.StringVar(value=prefill.get('time', ''))
        time_entry = ttk.Entry(date_time_frame, textvariable=time_var, width=6)
        time_entry.pack(side=tk.LEFT)
        ttk.Label(date_time_frame, text="(HH:MM)", style="Dark.TLabel", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(5, 0))

        # Tournament
        ttk.Label(frame, text="Tournament:", style="Dark.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        tournament_var = tk.StringVar(value=prefill.get('tournament', ''))
        tournament_entry = ttk.Entry(frame, textvariable=tournament_var, width=30)
        tournament_entry.grid(row=1, column=1, pady=5, padx=10)

        # Match Description
        ttk.Label(frame, text="Match:", style="Dark.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        match_var = tk.StringVar(value=prefill.get('match_description', ''))
        match_entry = ttk.Entry(frame, textvariable=match_var, width=30)
        match_entry.grid(row=2, column=1, pady=5, padx=10)

        # Market
        ttk.Label(frame, text="Market:", style="Dark.TLabel").grid(row=3, column=0, sticky=tk.W, pady=5)
        market_var = tk.StringVar(value=prefill.get('market', 'Match Winner'))
        market_combo = ttk.Combobox(frame, textvariable=market_var,
                                     values=["Match Winner", "Set Betting", "Handicap", "Total Games", "Other"],
                                     width=27)
        market_combo.grid(row=3, column=1, pady=5, padx=10)

        # Selection
        ttk.Label(frame, text="Selection:", style="Dark.TLabel").grid(row=4, column=0, sticky=tk.W, pady=5)
        selection_var = tk.StringVar(value=prefill.get('selection', ''))
        selection_entry = ttk.Entry(frame, textvariable=selection_var, width=30)
        selection_entry.grid(row=4, column=1, pady=5, padx=10)

        # Stake
        ttk.Label(frame, text="Units:", style="Dark.TLabel").grid(row=5, column=0, sticky=tk.W, pady=5)
        stake_var = tk.StringVar(value=prefill.get('stake', ''))
        stake_entry = ttk.Entry(frame, textvariable=stake_var, width=30)
        stake_entry.grid(row=5, column=1, pady=5, padx=10)
        stake_entry.focus_set()  # Focus on stake since it's the main thing user needs to enter

        # Odds
        ttk.Label(frame, text="Odds (decimal):", style="Dark.TLabel").grid(row=6, column=0, sticky=tk.W, pady=5)
        odds_var = tk.StringVar(value=str(prefill.get('odds', '')) if prefill.get('odds') else '')
        odds_entry = ttk.Entry(frame, textvariable=odds_var, width=30)
        odds_entry.grid(row=6, column=1, pady=5, padx=10)

        # Our Probability (optional)
        ttk.Label(frame, text="Our Prob (optional):", style="Dark.TLabel").grid(row=7, column=0, sticky=tk.W, pady=5)
        prob_var = tk.StringVar(value=str(prefill.get('our_probability', '')) if prefill.get('our_probability') else '')
        prob_entry = ttk.Entry(frame, textvariable=prob_var, width=30)
        prob_entry.grid(row=7, column=1, pady=5, padx=10)

        # Notes
        ttk.Label(frame, text="Notes:", style="Dark.TLabel").grid(row=8, column=0, sticky=tk.W, pady=5)
        notes_var = tk.StringVar(value=prefill.get('notes', ''))
        notes_entry = ttk.Entry(frame, textvariable=notes_var, width=30)
        notes_entry.grid(row=8, column=1, pady=5, padx=10)

        # Clear prefill data after using it
        self.prefill_bet = None

        def save_bet():
            try:
                stake = float(stake_var.get())
                odds = float(odds_var.get())
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter valid numbers for stake and odds.")
                return

            our_prob = None
            if prob_var.get():
                try:
                    our_prob = float(prob_var.get())
                except ValueError:
                    pass

            # Extract player names from match description
            match_desc = match_var.get()
            player1, player2 = None, None

            # Try common separators: " vs ", " v ", " - "
            for sep in [' vs ', ' v ', ' - ', ' VS ', ' V ']:
                if sep in match_desc:
                    parts = match_desc.split(sep, 1)
                    if len(parts) == 2:
                        player1 = parts[0].strip()
                        player2 = parts[1].strip()
                        break

            # Combine date and time
            match_datetime = date_var.get()
            if time_var.get().strip():
                match_datetime = f"{date_var.get()} {time_var.get().strip()}"

            bet_data = {
                'match_date': match_datetime,
                'tournament': tournament_var.get(),
                'match_description': match_desc,
                'player1': player1,
                'player2': player2,
                'market': market_var.get(),
                'selection': selection_var.get(),
                'stake': stake,
                'odds': odds,
                'our_probability': our_prob,
                'notes': notes_var.get(),
            }

            # Check if we already have ANY bet on this match (prevents betting both sides)
            tournament = tournament_var.get()
            existing_match = db.check_match_already_bet(match_desc, tournament)
            if existing_match:
                messagebox.showerror(
                    "Match Already Bet",
                    f"A bet already exists for this match.\n\n"
                    f"Tournament: {tournament}\n"
                    f"Match: {match_desc}\n"
                    f"Existing selection: {existing_match.get('selection', 'Unknown')}\n\n"
                    f"You cannot bet on both players in the same match."
                )
                return

            try:
                bet_id = self.tracker.add_bet(bet_data)

                # Sync to cloud if configured
                if CLOUD_SYNC_AVAILABLE and bet_id > 0:
                    try:
                        bet_data['id'] = bet_id
                        sync_bet_to_cloud(bet_data)
                    except Exception:
                        pass  # Silent fail - cloud sync is optional

                self._refresh_data(skip_date_sync=True)
                self._notify_change()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error Adding Bet", f"Failed to add bet: {e}")

        save_btn = tk.Button(
            frame,
            text="Add Bet",
            font=("Segoe UI", 11),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=save_bet,
            padx=20,
            pady=8
        )
        save_btn.grid(row=9, column=1, pady=20, sticky=tk.E)

    def _settle_selected(self, result: str):
        """Settle the selected pending bet."""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showinfo("Select Bet", "Please select a bet to settle.")
            return

        item = self.pending_tree.item(selection[0])
        bet_id = item['values'][0]

        try:
            self.tracker.settle_bet(bet_id, result)
            self._refresh_data(skip_date_sync=True)
            self._notify_change()

            # Bring window back to foreground
            self.root.lift()
            self.root.focus_force()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _toggle_in_progress(self):
        """Toggle in-progress status for the selected pending bet."""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showinfo("Select Bet", "Please select a bet to toggle.")
            return

        item = self.pending_tree.item(selection[0])
        bet_id = item['values'][0]

        # Check current in_progress status
        bet = db.get_bet_by_id(bet_id)
        current_status = bet.get('in_progress', 0) if bet else 0
        new_status = not current_status

        # Toggle the status
        db.set_bet_in_progress(bet_id, new_status)
        self._refresh_pending_table()

        # Bring window back to foreground
        self.root.lift()
        self.root.focus_force()

    def _toggle_in_progress_all_bets(self):
        """Toggle in-progress status for the selected bet in All Bets table."""
        selection = self.bets_tree.selection()
        if not selection:
            messagebox.showinfo("Select Bet", "Please select a bet to toggle.")
            return

        item = self.bets_tree.item(selection[0])
        bet_id = item['values'][0]

        # Check current in_progress status
        bet = db.get_bet_by_id(bet_id)
        current_status = bet.get('in_progress', 0) if bet else 0
        new_status = not current_status

        # Toggle the status
        db.set_bet_in_progress(bet_id, new_status)
        self._refresh_data(skip_date_sync=True)

        # Bring window back to foreground
        self.root.lift()
        self.root.focus_force()

    def _settle_from_all_bets(self, result: str):
        """Settle or re-settle the selected bet from All Bets table."""
        selection = self.bets_tree.selection()
        if not selection:
            messagebox.showinfo("Select Bet", "Please select a bet to settle.")
            return

        item = self.bets_tree.item(selection[0])
        bet_id = item['values'][0]
        current_result = item['values'][7]  # Result column

        # Confirm if re-settling an already settled bet
        if current_result and current_result not in ('Pending', 'None', ''):
            confirm = messagebox.askyesno(
                "Re-settle Bet",
                f"This bet is already marked as '{current_result}'.\n\nChange to '{result}'?"
            )
            if not confirm:
                return

        try:
            self.tracker.settle_bet(bet_id, result)
            self._refresh_data(skip_date_sync=True)
            self._notify_change()

            # Bring window back to foreground
            self.root.lift()
            self.root.focus_force()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_selected(self, tree: ttk.Treeview):
        """Delete the selected bet."""
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("Select Bet", "Please select a bet to delete.")
            return

        item = tree.item(selection[0])
        bet_id = int(item['values'][0])  # Ensure bet_id is an integer
        match_desc = item['values'][4]  # Match description (index 4 after column reorder)

        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete this bet?\n\n{match_desc}"):
            return

        try:
            # Remember current tab
            current_tab = self.notebook.index(self.notebook.select())

            db.delete_bet(bet_id)
            self._refresh_data(skip_date_sync=True)
            self._notify_change()

            # Restore the tab and keep focus on Bet Tracker
            self.notebook.select(current_tab)
            self.root.lift()
            self.root.focus_force()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_all_bets(self):
        """Delete all bets from the tracker."""
        # Get count of all bets
        all_bets = db.get_all_bets()
        count = len(all_bets)

        if count == 0:
            messagebox.showinfo("No Bets", "There are no bets to delete.")
            return

        # Double confirmation for destructive action
        if not messagebox.askyesno("Confirm Delete All",
                                   f"Are you sure you want to delete ALL {count} bet(s)?\n\n"
                                   "This action cannot be undone."):
            return

        # Second confirmation
        if not messagebox.askyesno("Final Confirmation",
                                   f"This will permanently delete {count} bet(s).\n\n"
                                   "Are you absolutely sure?"):
            return

        try:
            deleted = 0
            for bet in all_bets:
                db.delete_bet(bet['id'])
                deleted += 1

            self._refresh_data(skip_date_sync=True)
            self._notify_change()
            messagebox.showinfo("Deleted", f"Successfully deleted {deleted} bet(s).")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete bets: {e}")

    def _auto_check_results(self):
        """Automatically check and settle pending bets from match results."""
        # Run the auto-settle
        results = self.tracker.auto_settle_from_results()

        # Build result message
        if results['settled'] > 0:
            details_text = "\n".join([
                f"  {d['selection']}: {d['result']} (vs {d['opponent']}, {d['score']})"
                for d in results['details'][:10]  # Show first 10
            ])
            if len(results['details']) > 10:
                details_text += f"\n  ... and {len(results['details']) - 10} more"

            message = (
                f"Auto-settled {results['settled']} bet(s):\n"
                f"  Wins: {results['wins']}\n"
                f"  Losses: {results['losses']}\n\n"
                f"Details:\n{details_text}"
            )

            if results['not_found'] > 0:
                message += f"\n\n{results['not_found']} bet(s) not found in results yet."

            messagebox.showinfo("Results Checked", message)
            self._refresh_data(skip_date_sync=True)
        else:
            if results['not_found'] > 0:
                messagebox.showinfo(
                    "No Results Found",
                    f"No match results found for {results['not_found']} pending bet(s).\n\n"
                    "Try running Quick Refresh first to update match results."
                )
            else:
                messagebox.showinfo("No Pending Bets", "No pending bets to check.")

    def _on_bet_double_click(self, event):
        """Handle double-click on bets table - open edit dialog."""
        selection = self.bets_tree.selection()
        if not selection:
            return

        item = self.bets_tree.item(selection[0])
        bet_id = item['values'][0]
        self._edit_bet_dialog(bet_id)

    def _format_factor_value(self, factor_key: str, value, data: dict = None, is_p1: bool = True) -> str:
        """Format a factor value for display."""
        try:
            if factor_key == 'ranking' and data:
                # Ranking shows rank and Elo
                rank_key = 'p1_rank' if is_p1 else 'p2_rank'
                elo_key = 'p1_elo' if is_p1 else 'p2_elo'
                rank = data.get(rank_key, '-')
                elo = data.get(elo_key)
                if rank and elo:
                    return f"#{rank} ({elo:.0f})"
                elif rank:
                    return f"#{rank}"
                return "-"

            elif factor_key == 'form' and value:
                if isinstance(value, dict):
                    wins = value.get('wins', 0)
                    losses = value.get('losses', 0)
                    score = value.get('score', 50)
                    return f"{wins}W-{losses}L ({score:.0f})"
                return "-"

            elif factor_key == 'surface' and value:
                if isinstance(value, dict):
                    score = value.get('score', 50)
                    recent = value.get('recent_matches', 0)
                    return f"{score:.0f}% ({recent}m)"
                return "-"

            elif factor_key == 'h2h' and data:
                p1_wins = data.get('p1_wins', 0)
                p2_wins = data.get('p2_wins', 0)
                if is_p1:
                    return f"{p1_wins} wins"
                else:
                    return f"{p2_wins} wins"

            elif factor_key == 'fatigue' and value:
                if isinstance(value, dict):
                    score = value.get('score', 100)
                    status = value.get('status', 'Good')
                    return f"{status} ({score:.0f})"
                return "-"

            elif factor_key == 'injury' and value:
                if isinstance(value, dict):
                    status = value.get('status', 'Healthy')
                    return status
                return "Healthy"

            elif factor_key == 'opponent_quality' and value:
                if isinstance(value, dict):
                    score = value.get('weighted_score', 0)
                    return f"Score: {score:.1f}"
                return "-"

            elif factor_key == 'recency' and value:
                if isinstance(value, dict):
                    score = value.get('weighted_score', 0)
                    return f"Score: {score:.1f}"
                return "-"

            elif factor_key == 'recent_loss' and value:
                if isinstance(value, dict):
                    penalty = value.get('penalty', 0)
                    if penalty < 0:
                        return f"Penalty: {penalty:.2f}"
                    return "No penalty"
                return "-"

            elif factor_key == 'momentum' and value:
                if isinstance(value, dict):
                    bonus = value.get('bonus', 0)
                    if bonus > 0:
                        return f"Bonus: +{bonus:.2f}"
                    return "No bonus"
                return "-"

            # Default
            if value is None:
                return "-"
            if isinstance(value, (int, float)):
                return f"{value:.2f}"
            if isinstance(value, dict):
                return "-"
            return str(value)[:15]

        except Exception:
            return "-"

    def _build_factor_panel(self, parent, bet: dict):
        """Build the factor information panel for the edit dialog."""
        # Header
        ttk.Label(parent, text="Bet Analysis",
                  style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)

        # Probability info
        prob_frame = ttk.Frame(parent, style="Card.TFrame")
        prob_frame.pack(fill=tk.X, pady=(10, 5))

        our_prob = bet.get('our_probability')
        impl_prob = bet.get('implied_probability')
        odds = bet.get('odds')

        if our_prob:
            ttk.Label(prob_frame, text=f"Our Probability: {our_prob*100:.1f}%",
                      style="Card.TLabel", font=("Segoe UI", 10, "bold"),
                      foreground=UI_COLORS["primary"]).pack(anchor=tk.W)

        if impl_prob:
            ttk.Label(prob_frame, text=f"Market Implied: {impl_prob*100:.1f}%",
                      style="Card.TLabel", font=("Segoe UI", 10)).pack(anchor=tk.W)

        if our_prob and impl_prob:
            edge = (our_prob - impl_prob) * 100
            edge_color = UI_COLORS["success"] if edge > 0 else UI_COLORS["danger"]
            ttk.Label(prob_frame, text=f"Edge: {edge:+.1f}%",
                      style="Card.TLabel", font=("Segoe UI", 10, "bold"),
                      foreground=edge_color).pack(anchor=tk.W)

        ev = bet.get('ev_at_placement')
        if ev:
            ev_color = UI_COLORS["success"] if ev > 0 else UI_COLORS["danger"]
            ttk.Label(prob_frame, text=f"EV at Placement: {ev*100:.1f}%",
                      style="Card.TLabel", font=("Segoe UI", 10),
                      foreground=ev_color).pack(anchor=tk.W)

        # Separator
        ttk.Separator(parent, orient="horizontal").pack(fill=tk.X, pady=10)

        # Factor Analysis
        ttk.Label(parent, text="Factor Analysis",
                  style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)

        factor_scores_json = bet.get('factor_scores')
        if factor_scores_json:
            try:
                factor_data = json.loads(factor_scores_json)

                # Check if it's the new format (with 'factors' key) or old format
                if 'factors' in factor_data:
                    # New format with full data
                    factors = factor_data['factors']
                    p1_name = factor_data.get('p1_name', 'P1')
                    p2_name = factor_data.get('p2_name', 'P2')
                    is_p1_bet = factor_data.get('is_p1_bet', True)

                    # Create table using Treeview
                    columns = ("factor", "p1", "p2", "adv", "wt", "contrib")
                    factor_tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)

                    # Column headers
                    factor_tree.heading("factor", text="Factor")
                    factor_tree.heading("p1", text=p1_name[:15])
                    factor_tree.heading("p2", text=p2_name[:15])
                    factor_tree.heading("adv", text="Adv")
                    factor_tree.heading("wt", text="Wt")
                    factor_tree.heading("contrib", text="Contrib")

                    # Column widths
                    factor_tree.column("factor", width=80, minwidth=70)
                    factor_tree.column("p1", width=90, minwidth=70)
                    factor_tree.column("p2", width=90, minwidth=70)
                    factor_tree.column("adv", width=50, minwidth=40)
                    factor_tree.column("wt", width=40, minwidth=35)
                    factor_tree.column("contrib", width=55, minwidth=45)

                    factor_tree.pack(fill=tk.BOTH, expand=True, pady=5)

                    # Factor display names
                    factor_labels = {
                        'ranking': '1. Ranking',
                        'form': '2. Form',
                        'surface': '3. Surface',
                        'h2h': '4. H2H',
                        'fatigue': '5. Fatigue',
                        'injury': '6. Injury',
                        'opponent_quality': '7. Opp Qual',
                        'recency': '8. Recency',
                        'recent_loss': '9. Loss Pen',
                        'momentum': '10. Momentum',
                    }

                    total_contrib = 0
                    for factor_key in ['ranking', 'form', 'surface', 'h2h', 'fatigue', 'injury', 'opponent_quality', 'recency', 'recent_loss', 'momentum']:
                        if factor_key not in factors:
                            continue

                        f = factors[factor_key]
                        label = factor_labels.get(factor_key, factor_key)
                        adv = f.get('advantage', 0)
                        wt = f.get('weight', 0)
                        contrib = f.get('contribution', adv * wt)
                        total_contrib += contrib

                        # Format p1/p2 values
                        p1_val = self._format_factor_value(factor_key, f.get('p1'), f.get('data'), is_p1=True)
                        p2_val = self._format_factor_value(factor_key, f.get('p2'), f.get('data'), is_p1=False)

                        # Color based on advantage
                        tag = 'positive' if adv > 0 else ('negative' if adv < 0 else 'neutral')

                        factor_tree.insert("", tk.END, values=(
                            label,
                            p1_val,
                            p2_val,
                            f"{adv:.2f}",
                            f"{wt*100:.0f}%",
                            f"{contrib:.3f}"
                        ), tags=(tag,))

                    # Configure tags for colors
                    factor_tree.tag_configure('positive', foreground='#f59e0b')  # Amber for advantage
                    factor_tree.tag_configure('negative', foreground='#94a3b8')  # Gray
                    factor_tree.tag_configure('neutral', foreground='#94a3b8')

                    # Total row
                    ttk.Separator(parent, orient="horizontal").pack(fill=tk.X, pady=5)
                    total_frame = ttk.Frame(parent, style="Card.TFrame")
                    total_frame.pack(fill=tk.X)
                    ttk.Label(total_frame, text="Total Weighted Advantage:",
                              style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
                    adv_color = UI_COLORS["success"] if total_contrib > 0 else UI_COLORS["danger"]
                    ttk.Label(total_frame, text=f"{total_contrib:.4f}",
                              style="Card.TLabel", font=("Segoe UI", 9, "bold"),
                              foreground=adv_color).pack(side=tk.LEFT, padx=5)

                else:
                    # Old format - simple scores
                    ttk.Label(parent, text="(Legacy format - limited data)",
                              style="Card.TLabel", font=("Segoe UI", 8),
                              foreground="#6b7280").pack(anchor=tk.W)

                    for factor_key, score in factor_data.items():
                        if isinstance(score, (int, float)):
                            row = ttk.Frame(parent, style="Card.TFrame")
                            row.pack(fill=tk.X, pady=1)
                            ttk.Label(row, text=f"{factor_key}:", width=12,
                                      style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)
                            ttk.Label(row, text=f"{score*100:.0f}%",
                                      style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)

            except (json.JSONDecodeError, TypeError) as e:
                ttk.Label(parent, text=f"(Factor data error: {e})",
                          style="Card.TLabel", font=("Segoe UI", 9, "italic"),
                          foreground="#6b7280").pack(anchor=tk.W, pady=5)
        else:
            ttk.Label(parent, text="No factor data stored for this bet.\nNew bets will include full factor analysis.",
                      style="Card.TLabel", font=("Segoe UI", 9, "italic"),
                      foreground="#6b7280").pack(anchor=tk.W, pady=5)

        # Model info
        ttk.Separator(parent, orient="horizontal").pack(fill=tk.X, pady=10)

        model = bet.get('model', 'Model 1')
        model_color = UI_COLORS["success"] if 'Model 2' in str(model) else "#94a3b8"
        ttk.Label(parent, text=f"Model: {model or 'Model 1'}",
                  style="Card.TLabel", font=("Segoe UI", 10),
                  foreground=model_color).pack(anchor=tk.W)

    def _edit_bet_dialog(self, bet_id: int):
        """Show dialog to edit an existing bet."""
        # Fetch the bet data
        bet = self.tracker.get_bet_by_id(bet_id)
        if not bet:
            messagebox.showerror("Error", f"Bet {bet_id} not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Bet #{bet_id}")
        dialog.geometry("900x550")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        # Main container with left and right panels
        main_frame = ttk.Frame(dialog, style="Dark.TFrame", padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel - Form
        frame = ttk.Frame(main_frame, style="Dark.TFrame", padding=10)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

        # Right panel - Factor Information
        right_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # Build right panel content
        self._build_factor_panel(right_frame, bet)

        # Date and Time
        ttk.Label(frame, text="Date:", style="Dark.TLabel").grid(row=0, column=0, sticky=tk.W, pady=5)
        date_time_frame = ttk.Frame(frame, style="Dark.TFrame")
        date_time_frame.grid(row=0, column=1, pady=5, padx=10, sticky=tk.W)

        # Parse existing date and time
        existing_date = ''
        existing_time = ''
        match_date_str = bet.get('match_date', '') or ''
        if match_date_str:
            existing_date = match_date_str[:10]  # YYYY-MM-DD
            if len(match_date_str) > 10:
                # Extract time portion (could be " HH:MM" or "THH:MM" or " HH:MM:SS")
                time_part = match_date_str[10:].strip().lstrip('T')
                if time_part:
                    existing_time = time_part[:5]  # HH:MM

        date_var = tk.StringVar(value=existing_date)
        date_entry = ttk.Entry(date_time_frame, textvariable=date_var, width=12)
        date_entry.pack(side=tk.LEFT)

        ttk.Label(date_time_frame, text=" Time:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(10, 5))
        time_var = tk.StringVar(value=existing_time)
        time_entry = ttk.Entry(date_time_frame, textvariable=time_var, width=6)
        time_entry.pack(side=tk.LEFT)
        ttk.Label(date_time_frame, text="(HH:MM)", style="Dark.TLabel", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(5, 0))

        # Tournament
        ttk.Label(frame, text="Tournament:", style="Dark.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        tournament_var = tk.StringVar(value=bet.get('tournament', '') or '')
        tournament_entry = ttk.Entry(frame, textvariable=tournament_var, width=30)
        tournament_entry.grid(row=1, column=1, pady=5, padx=10)

        # Match Description
        ttk.Label(frame, text="Match:", style="Dark.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        match_var = tk.StringVar(value=bet.get('match_description', '') or '')
        match_entry = ttk.Entry(frame, textvariable=match_var, width=30)
        match_entry.grid(row=2, column=1, pady=5, padx=10)

        # Market
        ttk.Label(frame, text="Market:", style="Dark.TLabel").grid(row=3, column=0, sticky=tk.W, pady=5)
        market_var = tk.StringVar(value=bet.get('market', 'Match Winner') or 'Match Winner')
        market_combo = ttk.Combobox(frame, textvariable=market_var,
                                     values=["Match Winner", "Set Betting", "Handicap", "Total Games", "Other"],
                                     width=27)
        market_combo.grid(row=3, column=1, pady=5, padx=10)

        # Selection
        ttk.Label(frame, text="Selection:", style="Dark.TLabel").grid(row=4, column=0, sticky=tk.W, pady=5)
        selection_var = tk.StringVar(value=bet.get('selection', '') or '')
        selection_entry = ttk.Entry(frame, textvariable=selection_var, width=30)
        selection_entry.grid(row=4, column=1, pady=5, padx=10)

        # Stake
        ttk.Label(frame, text="Units:", style="Dark.TLabel").grid(row=5, column=0, sticky=tk.W, pady=5)
        stake_var = tk.StringVar(value=str(bet.get('stake', '')) if bet.get('stake') else '')
        stake_entry = ttk.Entry(frame, textvariable=stake_var, width=30)
        stake_entry.grid(row=5, column=1, pady=5, padx=10)

        # Odds
        ttk.Label(frame, text="Odds (decimal):", style="Dark.TLabel").grid(row=6, column=0, sticky=tk.W, pady=5)
        odds_var = tk.StringVar(value=str(bet.get('odds', '')) if bet.get('odds') else '')
        odds_entry = ttk.Entry(frame, textvariable=odds_var, width=30)
        odds_entry.grid(row=6, column=1, pady=5, padx=10)

        # Our Probability (optional)
        ttk.Label(frame, text="Our Prob (optional):", style="Dark.TLabel").grid(row=7, column=0, sticky=tk.W, pady=5)
        prob_var = tk.StringVar(value=str(bet.get('our_probability', '')) if bet.get('our_probability') else '')
        prob_entry = ttk.Entry(frame, textvariable=prob_var, width=30)
        prob_entry.grid(row=7, column=1, pady=5, padx=10)

        # Notes
        ttk.Label(frame, text="Notes:", style="Dark.TLabel").grid(row=8, column=0, sticky=tk.W, pady=5)
        notes_var = tk.StringVar(value=bet.get('notes', '') or '')
        notes_entry = ttk.Entry(frame, textvariable=notes_var, width=30)
        notes_entry.grid(row=8, column=1, pady=5, padx=10)

        # Current Result (read-only display)
        ttk.Label(frame, text="Result:", style="Dark.TLabel").grid(row=9, column=0, sticky=tk.W, pady=5)
        result_label = ttk.Label(frame, text=bet.get('result', 'Pending') or 'Pending', style="Dark.TLabel")
        result_label.grid(row=9, column=1, sticky=tk.W, pady=5, padx=10)

        def save_changes():
            try:
                stake = float(stake_var.get())
                odds = float(odds_var.get())
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter valid numbers for stake and odds.")
                return

            our_prob = None
            if prob_var.get():
                try:
                    our_prob = float(prob_var.get())
                except ValueError:
                    pass

            # Extract player names from match description
            match_desc = match_var.get()
            player1, player2 = None, None
            for sep in [' vs ', ' v ', ' - ', ' VS ', ' V ']:
                if sep in match_desc:
                    parts = match_desc.split(sep, 1)
                    if len(parts) == 2:
                        player1 = parts[0].strip()
                        player2 = parts[1].strip()
                        break

            # Combine date and time
            match_datetime = date_var.get()
            if time_var.get().strip():
                match_datetime = f"{date_var.get()} {time_var.get().strip()}"

            bet_data = {
                'match_date': match_datetime,
                'tournament': tournament_var.get(),
                'match_description': match_desc,
                'player1': player1,
                'player2': player2,
                'market': market_var.get(),
                'selection': selection_var.get(),
                'stake': stake,
                'odds': odds,
                'our_probability': our_prob,
                'notes': notes_var.get(),
            }

            try:
                self.tracker.update_bet(bet_id, bet_data)

                # Sync to cloud if configured
                if CLOUD_SYNC_AVAILABLE:
                    try:
                        bet_data['id'] = bet_id
                        sync_bet_to_cloud(bet_data)
                    except Exception:
                        pass  # Silent fail - cloud sync is optional

                # Skip date sync to preserve user's manual date edit
                self._refresh_data(skip_date_sync=True)
                self._notify_change()
                dialog.destroy()
                messagebox.showinfo("Success", f"Bet #{bet_id} updated successfully.")

                # Bring bet tracker back to foreground
                self.root.lift()
                self.root.focus_force()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update bet: {e}")

        # Button frame
        btn_frame = ttk.Frame(frame, style="Dark.TFrame")
        btn_frame.grid(row=10, column=0, columnspan=2, pady=20)

        save_btn = tk.Button(
            btn_frame,
            text="Save Changes",
            font=("Segoe UI", 11),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=save_changes,
            padx=20,
            pady=8
        )
        save_btn.pack(side=tk.LEFT, padx=10)

        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 11),
            fg="white",
            bg="#6b7280",
            relief=tk.FLAT,
            cursor="hand2",
            command=dialog.destroy,
            padx=20,
            pady=8
        )
        cancel_btn.pack(side=tk.LEFT, padx=10)

    def _on_pending_double_click(self, event):
        """Handle double-click on pending table - show settle dialog."""
        selection = self.pending_tree.selection()
        if not selection:
            return

        item = self.pending_tree.item(selection[0])
        bet_id = item['values'][0]

        result = messagebox.askquestion("Settle Bet", "Did this bet win?",
                                        icon='question',
                                        type='yesnocancel')

        if result == 'yes':
            self.tracker.settle_bet(bet_id, "Win")
        elif result == 'no':
            self.tracker.settle_bet(bet_id, "Loss")
        else:
            # Cancel - don't refresh
            return

        self._refresh_data(skip_date_sync=True)
        self._notify_change()

        # Bring window back to foreground
        self.root.lift()
        self.root.focus_force()

    def _export_bets(self):
        """Export all bets to a CSV file."""
        # Get all bets from database (no limit)
        with self.tracker.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, match_date, tournament, match_description, player1, player2,
                       market, selection, stake, odds, our_probability, implied_probability,
                       ev_at_placement, result, profit_loss, notes, created_at, settled_at, in_progress
                FROM bets
                ORDER BY match_date DESC
            """)
            bets = cursor.fetchall()
            columns = [description[0] for description in cursor.description]

        if not bets:
            messagebox.showinfo("No Data", "No bets to export.")
            return

        # Open Save As dialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"bets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return  # User cancelled

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(bets)

            messagebox.showinfo("Export Complete", f"Exported {len(bets)} bet(s) to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export bets:\n{str(e)}")

    # =========================================================================
    # LIVE SCORES
    # =========================================================================

    def _refresh_bet_tables_only(self):
        """Refresh just the bet tables (All Bets and Pending) without stats."""
        self._refresh_bets_table()
        self._refresh_pending_table()

    def _start_live_score_refresh(self):
        """Start auto-refreshing live scores every 30 seconds."""
        self._fetch_live_scores()
        # Schedule next refresh in 30 seconds
        self.live_score_refresh_id = self.root.after(30000, self._start_live_score_refresh)

    def _stop_live_score_refresh(self):
        """Stop auto-refreshing live scores."""
        if self.live_score_refresh_id:
            self.root.after_cancel(self.live_score_refresh_id)
            self.live_score_refresh_id = None

    def _start_result_refresh(self):
        """Start auto-checking for new results every 10 seconds."""
        self._check_for_new_results()
        # Schedule next check in 10 seconds
        self.result_refresh_id = self.root.after(10000, self._start_result_refresh)

    def _stop_result_refresh(self):
        """Stop auto-checking for results."""
        if self.result_refresh_id:
            self.root.after_cancel(self.result_refresh_id)
            self.result_refresh_id = None

    def _check_for_new_results(self):
        """Check if any bets have been settled by the monitor and refresh if needed."""
        try:
            # Get current settled bet IDs
            all_bets = db.get_all_bets()
            current_settled_ids = set(
                bet['id'] for bet in all_bets
                if bet.get('result') is not None
            )

            # Check if there are new settled bets
            if current_settled_ids != self.last_settled_ids:
                new_results = current_settled_ids - self.last_settled_ids
                if new_results and self.last_settled_ids:  # Don't refresh on first load
                    print(f"[Auto-refresh] Detected {len(new_results)} new result(s), refreshing...")
                    self._refresh_data(skip_date_sync=True)
                self.last_settled_ids = current_settled_ids
        except Exception as e:
            print(f"[Auto-refresh] Error checking for results: {e}")

    def _manual_refresh_scores(self):
        """Manually trigger a live score refresh."""
        self.live_score_status_var.set("Live scores: Refreshing...")
        self.root.update()
        self._fetch_live_scores()

    def _fetch_live_scores(self):
        """Fetch live scores from Betfair for pending bets."""
        if not BETFAIR_AVAILABLE:
            self.live_score_status_var.set("Live scores: Betfair not available")
            return

        # Run in background thread to avoid blocking UI
        thread = threading.Thread(target=self._do_fetch_live_scores, daemon=True)
        thread.start()

    def _do_fetch_live_scores(self):
        """Background thread: Fetch live scores from Betfair."""
        try:
            # Get pending bets
            pending = db.get_pending_bets()
            if not pending:
                self.root.after(0, lambda: self._update_live_score_status("Live scores: No pending bets"))
                return

            # Initialize Betfair client if needed
            if not self.betfair_client:
                creds = load_credentials_from_file()
                if not creds or not creds.get('app_key'):
                    self.root.after(0, lambda: self._update_live_score_status("Live scores: No Betfair credentials"))
                    return

                self.betfair_client = BetfairTennisCapture(
                    app_key=creds.get('app_key'),
                    username=creds.get('username'),
                    password=creds.get('password')
                )

            # Login if needed
            if not self.betfair_client.session_token:
                if not self.betfair_client.login():
                    self.root.after(0, lambda: self._update_live_score_status("Live scores: Login failed"))
                    return

            # Fetch in-play tennis markets
            in_play_markets = self._get_inplay_markets()

            if not in_play_markets:
                self.root.after(0, lambda: self._update_live_score_status(
                    f"Live scores: No matches in-play ({datetime.now().strftime('%H:%M:%S')})"
                ))
                # Clear any old scores
                self.live_scores = {}
                self.root.after(0, self._refresh_pending_table)
                return

            # Match pending bets to in-play markets and get scores
            matches_found = 0
            newly_live = []  # Bets that just went live (for Discord alerts)
            just_finished = []  # Bets that just finished (were live, now not)
            current_live_ids = set()

            for bet in pending:
                match_desc = bet.get('match_description', '')
                bet_id = bet.get('id')

                # Try to find matching in-play market
                market_info = self._find_market_for_bet(match_desc, in_play_markets)
                if market_info:
                    self.live_scores[bet_id] = market_info.get('score', 'In-Play')
                    matches_found += 1
                    current_live_ids.add(bet_id)

                    # Check if this bet just went live (wasn't live before)
                    if bet_id not in self.previously_live:
                        self.previously_live[bet_id] = {'bet': bet, 'market': market_info}
                        newly_live.append(bet)
                    else:
                        # Update market info
                        self.previously_live[bet_id] = {'bet': bet, 'market': market_info}
                else:
                    # Check if match might be in-play but not found (or not started)
                    self.live_scores[bet_id] = "-"

            # Check for bets that were live but aren't anymore (match finished)
            for bet_id in list(self.previously_live.keys()):
                if bet_id not in current_live_ids:
                    # This bet was live but isn't anymore - match may have finished
                    prev_data = self.previously_live.pop(bet_id)
                    just_finished.append(prev_data)

            # Send Discord alerts for newly live bets
            # Live alerts now handled by local_monitor.py
            # if newly_live and DISCORD_AVAILABLE:
            #     for bet in newly_live:
            #         try:
            #             notify_bet_live(bet)
            #         except Exception as e:
            #             print(f"Discord notification error: {e}")

            # Check finished matches and send result alerts
            if just_finished and DISCORD_AVAILABLE:
                self._check_finished_matches(just_finished)

            # Update UI - refresh both pending and all bets tables
            timestamp = datetime.now().strftime('%H:%M:%S')
            status = f"Live scores: {matches_found} live ({timestamp})"
            self.root.after(0, lambda: self._update_live_score_status(status))
            self.root.after(0, self._refresh_bet_tables_only)

        except Exception as e:
            error_msg = f"Live scores: Error - {str(e)[:30]}"
            self.root.after(0, lambda: self._update_live_score_status(error_msg))

    def _get_inplay_markets(self) -> List[Dict]:
        """Get all in-play tennis markets with scores from Betfair."""
        if not self.betfair_client:
            return []

        # Get in-play tennis markets
        params = {
            "filter": {
                "eventTypeIds": ["2"],  # Tennis
                "inPlayOnly": True,
                "marketTypeCodes": ["MATCH_ODDS"]
            },
            "marketProjection": ["RUNNER_DESCRIPTION", "EVENT", "COMPETITION"],
            "maxResults": "100"
        }

        result = self.betfair_client._api_request("listMarketCatalogue", params)
        if not result:
            return []

        markets = []
        market_ids = []

        for market in result:
            runners = market.get('runners', [])
            if len(runners) == 2:
                event = market.get('event', {})
                market_id = market.get('marketId')
                market_ids.append(market_id)

                # Sort by sort priority for consistent ordering
                sorted_runners = sorted(runners, key=lambda r: r.get('sortPriority', 0))

                markets.append({
                    'market_id': market_id,
                    'event_name': event.get('name', ''),
                    'player1': sorted_runners[0].get('runnerName', ''),
                    'player2': sorted_runners[1].get('runnerName', ''),
                    'selection_ids': {
                        sorted_runners[0].get('runnerName', ''): sorted_runners[0].get('selectionId'),
                        sorted_runners[1].get('runnerName', ''): sorted_runners[1].get('selectionId'),
                    }
                })

        if not market_ids:
            return []

        # Get market books with scores (may be empty if API doesn't return score data)
        scores_by_market = self._get_market_scores(market_ids)

        # Merge scores into markets - default to "In-Play" if no specific score
        for market in markets:
            market_id = market['market_id']
            if market_id in scores_by_market:
                market['score'] = scores_by_market[market_id]
            else:
                market['score'] = "In-Play"  # Default for in-play matches

        return markets

    def _get_market_scores(self, market_ids: List[str]) -> Dict[str, str]:
        """Get live scores for markets from Betfair."""
        if not self.betfair_client or not market_ids:
            return {}

        scores = {}

        # Process in batches of 40 (Betfair limit)
        for i in range(0, len(market_ids), 40):
            batch = market_ids[i:i+40]

            params = {
                "marketIds": batch,
                "priceProjection": {
                    "priceData": ["EX_BEST_OFFERS"]
                }
            }

            result = self.betfair_client._api_request("listMarketBook", params)
            if not result:
                continue

            for market in result:
                market_id = market.get('marketId')

                # Check if in-play
                if not market.get('inplay', False):
                    continue

                # Try to extract score from keyLineDescription or status
                score_str = self._parse_betfair_score(market)
                if score_str:
                    scores[market_id] = score_str

        return scores

    def _parse_betfair_score(self, market: Dict) -> Optional[str]:
        """Parse the score from Betfair market data."""
        # Betfair includes score in the 'scoreState' field for some markets
        # and in runner descriptions for others

        # Check for score in market description (newer API)
        if 'scoreState' in market:
            score_state = market['scoreState']
            # Format: "Sets: 1-0, Games: 3-2"
            return self._format_score(score_state)

        # Check keyLineDescription
        key_line = market.get('keyLineDescription')
        if key_line and 'score' in str(key_line).lower():
            return str(key_line)

        # Fallback: just show "In-Play" if we can't get the score
        if market.get('inplay', False):
            return "In-Play"

        return None

    def _format_score(self, score_state: Dict) -> str:
        """Format Betfair score state into readable string."""
        if not score_state:
            return "In-Play"

        # Try to extract sets and games
        try:
            # Format varies - try common patterns
            if isinstance(score_state, dict):
                sets_p1 = score_state.get('score', {}).get('home', {}).get('sets', 0)
                sets_p2 = score_state.get('score', {}).get('away', {}).get('sets', 0)
                games_p1 = score_state.get('score', {}).get('home', {}).get('games', 0)
                games_p2 = score_state.get('score', {}).get('away', {}).get('games', 0)

                return f"{sets_p1}-{sets_p2} ({games_p1}-{games_p2})"
            else:
                return str(score_state)
        except:
            return "In-Play"

    def _find_score_for_bet(self, match_desc: str, in_play_markets: List[Dict]) -> Optional[str]:
        """Find the live score for a bet by matching player names."""
        market = self._find_market_for_bet(match_desc, in_play_markets)
        if market:
            return market.get('score', 'In-Play')
        return None

    def _find_market_for_bet(self, match_desc: str, in_play_markets: List[Dict]) -> Optional[Dict]:
        """Find the matching in-play market for a bet."""
        if not match_desc or not in_play_markets:
            return None

        # Parse player names from match description
        # Format: "FirstName LastName vs FirstName LastName"
        match_players = self._parse_match_players(match_desc)
        if not match_players:
            return None

        bet_p1, bet_p2 = match_players

        # Search for matching market
        for market in in_play_markets:
            market_p1 = market.get('player1', '').lower()
            market_p2 = market.get('player2', '').lower()

            # Check if players match (either order)
            if self._players_match(bet_p1, bet_p2, market_p1, market_p2):
                return market

        return None

    def _check_finished_matches(self, just_finished: List[Dict]):
        """Check Betfair for results of finished matches and send Discord alerts."""
        if not self.betfair_client or not just_finished:
            return

        from discord_notifier import notify_bet_result

        for data in just_finished:
            try:
                bet = data.get('bet', {})
                market_info = data.get('market', {})
                market_id = market_info.get('market_id')

                if not market_id:
                    continue

                # Get market book to check result
                params = {
                    "marketIds": [market_id],
                    "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}
                }
                result = self.betfair_client._api_request("listMarketBook", params)

                if not result or len(result) == 0:
                    continue

                market_book = result[0]
                status = market_book.get('status')

                # Only process if market is CLOSED (match finished)
                if status != 'CLOSED':
                    # Market still open/suspended - put back in tracking
                    bet_id = bet.get('id')
                    if bet_id:
                        self.previously_live[bet_id] = data
                    continue

                # Find the winner
                runners = market_book.get('runners', [])
                winner_name = None

                for runner in runners:
                    if runner.get('status') == 'WINNER':
                        # Find runner name from market_info
                        selection_id = runner.get('selectionId')
                        selection_ids = market_info.get('selection_ids', {})
                        for name, sid in selection_ids.items():
                            if sid == selection_id:
                                winner_name = name
                                break
                        break

                if not winner_name:
                    continue

                # Determine if user's selection won
                selection = bet.get('selection', '')
                selection_lower = selection.lower()
                winner_lower = winner_name.lower()

                # Match by last name
                selection_last = selection_lower.split()[-1] if selection_lower else ''
                winner_last = winner_lower.split()[-1] if winner_lower else ''

                if selection_last == winner_last or selection_lower in winner_lower or winner_lower in selection_lower:
                    bet_result = 'Win'
                    # Calculate profit
                    odds = bet.get('odds', 0)
                    stake = bet.get('stake', 0)
                    commission = 0.05
                    profit = stake * (odds - 1) * (1 - commission)
                    bet['profit_loss'] = profit
                else:
                    bet_result = 'Loss'
                    bet['profit_loss'] = -bet.get('stake', 0)

                # Result alerts now handled by local_monitor.py
                # notify_bet_result(bet, bet_result)

            except Exception as e:
                print(f"Error checking finished match: {e}")

    def _parse_match_players(self, match_desc: str) -> Optional[tuple]:
        """Parse player names from match description."""
        # Split by " vs "
        if ' vs ' in match_desc:
            parts = match_desc.split(' vs ')
            if len(parts) == 2:
                return (parts[0].strip().lower(), parts[1].strip().lower())
        return None

    def _players_match(self, bet_p1: str, bet_p2: str, market_p1: str, market_p2: str) -> bool:
        """Check if bet players match market players (handles name variations)."""
        # Direct match (either order)
        if (bet_p1 == market_p1 and bet_p2 == market_p2) or \
           (bet_p1 == market_p2 and bet_p2 == market_p1):
            return True

        # Fuzzy match: check if last names match
        bet_p1_last = bet_p1.split()[-1] if bet_p1 else ''
        bet_p2_last = bet_p2.split()[-1] if bet_p2 else ''
        market_p1_last = market_p1.split()[-1] if market_p1 else ''
        market_p2_last = market_p2.split()[-1] if market_p2 else ''

        if (bet_p1_last == market_p1_last and bet_p2_last == market_p2_last) or \
           (bet_p1_last == market_p2_last and bet_p2_last == market_p1_last):
            return True

        # Check if one name contains the other (for nickname variations)
        def name_contains(a: str, b: str) -> bool:
            return a in b or b in a

        if (name_contains(bet_p1_last, market_p1_last) and name_contains(bet_p2_last, market_p2_last)) or \
           (name_contains(bet_p1_last, market_p2_last) and name_contains(bet_p2_last, market_p1_last)):
            return True

        return False

    def _update_live_score_status(self, status: str):
        """Update the live score status label."""
        self.live_score_status_var.set(status)
        # Update label color based on status
        if "Error" in status or "failed" in status:
            self.live_score_label.configure(fg="#ef4444")  # Red
        elif "live" in status.lower() and "0 live" not in status:
            self.live_score_label.configure(fg="#22c55e")  # Green
        else:
            self.live_score_label.configure(fg=UI_COLORS["text_muted"])

    def run(self):
        """Run the UI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = BetTrackerUI()
    app.run()
