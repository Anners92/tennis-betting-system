"""
Cloud Backtester - Tennis Betting System
Runs the full 8-factor analysis model against historical matches.
Designed for GitHub Actions (headless, Linux) but works locally too.

Usage:
    python cloud_backtester.py --sample 500          # Quick sanity check
    python cloud_backtester.py --months 6            # Full backtest (all data)
    python cloud_backtester.py --sample 100 --db-path /path/to/db
"""

import os
import sys
import time
import random
import csv
import json
import math
import argparse
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ============================================================================
# PHASE 1: Environment setup (MUST happen before any tennis module imports)
# ============================================================================

def setup_environment(db_path: str = None):
    """Configure paths for headless/cloud execution."""
    src_dir = Path(__file__).parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    if db_path:
        # config.py appends /data to BASE_DIR, so TENNIS_DATA_DIR must be
        # the parent of the data/ folder (i.e. two levels up from the .db file)
        data_dir = Path(db_path).parent          # .../data
        base_dir = str(data_dir.parent)           # .../  (workspace root)
        os.environ['TENNIS_DATA_DIR'] = base_dir


# ============================================================================
# PHASE 2: Tennis module imports (after environment is configured)
# ============================================================================

def import_tennis_modules(db_path: str = None):
    """Import tennis modules after environment is set up."""
    setup_environment(db_path)

    from config import (
        get_tournament_surface, calculate_bet_model,
        KELLY_STAKING, BETTING_SETTINGS, DEFAULT_ANALYSIS_WEIGHTS
    )
    from database import TennisDatabase, db as default_db
    from match_analyzer import MatchAnalyzer

    return {
        'get_tournament_surface': get_tournament_surface,
        'calculate_bet_model': calculate_bet_model,
        'KELLY_STAKING': KELLY_STAKING,
        'BETTING_SETTINGS': BETTING_SETTINGS,
        'DEFAULT_ANALYSIS_WEIGHTS': DEFAULT_ANALYSIS_WEIGHTS,
        'TennisDatabase': TennisDatabase,
        'default_db': default_db,
        'MatchAnalyzer': MatchAnalyzer,
    }


# ============================================================================
# BACKTESTER
# ============================================================================

class BacktestRunner:
    """Main backtesting engine. Processes historical matches through the model."""

    def __init__(self, modules: dict, sample_size: int = 0,
                 months: int = 6, from_date: str = None, to_date: str = None,
                 output_csv: bool = True, checkpoint_interval: int = 500):
        self.modules = modules
        self.db = modules['default_db']
        self.analyzer = modules['MatchAnalyzer'](self.db)
        self.get_tournament_surface = modules['get_tournament_surface']
        self.calculate_bet_model = modules['calculate_bet_model']
        self.kelly_settings = modules['KELLY_STAKING']
        self.betting_settings = modules['BETTING_SETTINGS']

        self.sample_size = sample_size
        self.months = months
        self.from_date = from_date
        self.to_date = to_date
        self.output_csv = output_csv
        self.checkpoint_interval = checkpoint_interval

        self.results: List[Dict] = []
        self.errors: List[Dict] = []
        self.start_time = None

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def fetch_matches(self) -> List[Dict]:
        """Fetch historical matches from database."""
        # Determine date range
        if self.from_date:
            start_date = self.from_date
        else:
            start_dt = datetime.now() - timedelta(days=self.months * 30)
            start_date = start_dt.strftime('%Y-%m-%d')

        end_date = self.to_date or datetime.now().strftime('%Y-%m-%d')

        query = """
            SELECT m.id, m.date, m.tournament, m.surface,
                   m.winner_id, m.loser_id, m.score,
                   w.name as winner_name, w.current_ranking as winner_rank,
                   l.name as loser_name, l.current_ranking as loser_rank
            FROM matches m
            LEFT JOIN players w ON m.winner_id = w.id
            LEFT JOIN players l ON m.loser_id = l.id
            WHERE m.date >= ? AND m.date <= ?
              AND m.tournament NOT LIKE '%UTR%'
              AND m.winner_id IS NOT NULL
              AND m.loser_id IS NOT NULL
              AND w.name IS NOT NULL
              AND l.name IS NOT NULL
            ORDER BY m.date ASC
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (start_date, end_date))
            columns = [desc[0] for desc in cursor.description]
            matches = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Apply sample limit
        if self.sample_size > 0 and len(matches) > self.sample_size:
            matches = random.sample(matches, self.sample_size)

        return matches

    # ------------------------------------------------------------------
    # Odds proxy
    # ------------------------------------------------------------------

    def ranking_to_elo(self, ranking: int) -> float:
        """Convert ATP ranking to Elo. Mirrors MatchAnalyzer._ranking_to_elo()."""
        if ranking <= 0:
            ranking = 200
        base_elo = 2500
        elo = base_elo - 150 * math.log2(max(ranking, 1))
        return max(elo, 1000)

    def calculate_odds_proxy(self, p1_rank: int, p2_rank: int) -> Tuple[float, float]:
        """Convert rankings to implied decimal odds using Elo."""
        p1_elo = self.ranking_to_elo(p1_rank)
        p2_elo = self.ranking_to_elo(p2_rank)

        # Elo win probability
        p1_win_prob = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
        p2_win_prob = 1 - p1_win_prob

        # Convert to decimal odds with ~5% overround
        overround = 1.05
        p1_odds = overround / max(p1_win_prob, 0.02)
        p2_odds = overround / max(p2_win_prob, 0.02)

        # Clamp to realistic range
        p1_odds = max(1.01, min(50.0, p1_odds))
        p2_odds = max(1.01, min(50.0, p2_odds))

        return round(p1_odds, 2), round(p2_odds, 2)

    # ------------------------------------------------------------------
    # Match processing
    # ------------------------------------------------------------------

    def process_match(self, match: Dict) -> Optional[Dict]:
        """
        Process a single historical match through the full model.

        1. Randomly assign player1/player2 (avoid winner bias)
        2. Re-derive surface from tournament name
        3. Run calculate_win_probability()
        4. Generate ranking-based odds proxy
        5. Check model qualification (M3/M4/M7/M8)
        6. Calculate theoretical P/L
        7. Track factor accuracy
        """
        try:
            # 1. Random assignment to avoid winner bias
            if random.random() < 0.5:
                p1_id = match['winner_id']
                p2_id = match['loser_id']
                p1_name = match['winner_name']
                p2_name = match['loser_name']
                p1_rank = match['winner_rank'] or 500
                p2_rank = match['loser_rank'] or 500
                actual_winner = 'p1'
            else:
                p1_id = match['loser_id']
                p2_id = match['winner_id']
                p1_name = match['loser_name']
                p2_name = match['winner_name']
                p1_rank = match['loser_rank'] or 500
                p2_rank = match['winner_rank'] or 500
                actual_winner = 'p2'

            # 2. Re-derive surface (fixes corruption bug)
            surface = self.get_tournament_surface(
                match['tournament'], match['date']
            )

            # 3. Generate odds proxy from rankings
            p1_odds, p2_odds = self.calculate_odds_proxy(p1_rank, p2_rank)

            # 4. Run full model analysis
            analysis = self.analyzer.calculate_win_probability(
                p1_id, p2_id, surface,
                match_date=match['date'],
                p1_odds=p1_odds, p2_odds=p2_odds,
                tournament=match['tournament']
            )

            p1_prob = analysis.get('p1_probability', 0.5)

            # 5. Determine predicted winner and if correct
            predicted_winner = 'p1' if p1_prob > 0.5 else 'p2'
            correct = predicted_winner == actual_winner

            # 6. Calculate value and model qualification
            # We bet on whoever we predict to win
            bet_prob = p1_prob if predicted_winner == 'p1' else (1 - p1_prob)
            bet_odds = p1_odds if predicted_winner == 'p1' else p2_odds
            implied_prob = 1 / bet_odds

            # Check model qualification
            models_str = self.calculate_bet_model(
                bet_prob, implied_prob, match['tournament'], bet_odds
            )

            # Calculate value using the analyzer's find_value method
            value_result = self.analyzer.find_value(
                bet_prob, bet_odds,
                player_name=p1_name if predicted_winner == 'p1' else p2_name,
                tournament=match['tournament'],
                surface=surface,
                log=False,
                confidence=analysis.get('confidence')
            )

            # 7. Calculate P/L
            stake_units = value_result.get('recommended_units', 0)
            profit = 0.0
            if stake_units > 0 and models_str != "None":
                commission = self.kelly_settings.get('exchange_commission', 0.02)
                if correct:
                    profit = stake_units * (bet_odds - 1) * (1 - commission)
                else:
                    profit = -stake_units

            # 8. Factor accuracy tracking
            factors = analysis.get('factors', {})
            factor_accuracy = {}
            for fname, fdata in factors.items():
                if isinstance(fdata, dict):
                    advantage = fdata.get('advantage', 0)
                    if advantage != 0:
                        # Positive advantage means factor favours p1
                        factor_favours_p1 = advantage > 0
                        factor_correct = (
                            (factor_favours_p1 and actual_winner == 'p1') or
                            (not factor_favours_p1 and actual_winner == 'p2')
                        )
                        factor_accuracy[fname] = factor_correct

            return {
                'match_id': match['id'],
                'date': match['date'],
                'tournament': match['tournament'],
                'surface': surface,
                'p1_name': p1_name,
                'p2_name': p2_name,
                'p1_rank': p1_rank,
                'p2_rank': p2_rank,
                'p1_probability': round(p1_prob, 4),
                'predicted_winner': predicted_winner,
                'actual_winner': actual_winner,
                'correct': correct,
                'bet_prob': round(bet_prob, 4),
                'bet_odds': bet_odds,
                'implied_prob': round(implied_prob, 4),
                'edge': round(bet_prob - implied_prob, 4),
                'models': models_str,
                'is_value_bet': value_result.get('is_value', False),
                'stake_units': stake_units,
                'profit_units': round(profit, 4),
                'confidence': round(analysis.get('confidence', 0), 4),
                'weighted_advantage': round(analysis.get('weighted_advantage', 0), 4),
                'factor_accuracy': factor_accuracy,
            }

        except Exception as e:
            self.errors.append({
                'match_id': match.get('id'),
                'tournament': match.get('tournament'),
                'error': str(e)
            })
            return None

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    def save_checkpoint(self, index: int):
        """Save progress for resumption."""
        checkpoint = {
            'last_index': index,
            'timestamp': datetime.now().isoformat(),
            'results_count': len(self.results),
            'errors_count': len(self.errors),
        }
        checkpoint_path = Path('backtest_checkpoint.json')
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def load_checkpoint(self) -> int:
        """Load checkpoint and return resume index. Returns 0 if no checkpoint."""
        checkpoint_path = Path('backtest_checkpoint.json')
        if checkpoint_path.exists():
            try:
                with open(checkpoint_path) as f:
                    data = json.load(f)
                idx = data.get('last_index', 0)
                print(f"  Resuming from checkpoint at match {idx}")
                return idx
            except (json.JSONDecodeError, KeyError):
                pass
        return 0

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def run(self):
        """Execute the full backtest."""
        self.start_time = time.time()
        today = datetime.now().strftime('%Y-%m-%d')

        print("=" * 70)
        print("  TENNIS BETTING SYSTEM - CLOUD BACKTESTER")
        print("=" * 70)
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Fetch matches
        print("  Fetching matches...")
        matches = self.fetch_matches()
        total = len(matches)
        print(f"  Found {total} matches to process")

        if total == 0:
            print("  No matches found. Check date range and database.")
            return

        # Resume from checkpoint if exists
        start_idx = self.load_checkpoint()

        print(f"  Processing from index {start_idx}...")
        print()

        for i in range(start_idx, total):
            match = matches[i]
            result = self.process_match(match)
            if result:
                self.results.append(result)

            # Progress reporting every 100 matches
            if (i + 1) % 100 == 0 or i == total - 1:
                elapsed = time.time() - self.start_time
                rate = (i + 1 - start_idx) / elapsed if elapsed > 0 else 0
                remaining = (total - i - 1) / rate if rate > 0 else 0
                pct = (i + 1) / total * 100
                correct = sum(1 for r in self.results if r['correct'])
                accuracy = correct / len(self.results) * 100 if self.results else 0
                print(f"  [{pct:5.1f}%] {i+1}/{total} | "
                      f"Accuracy: {accuracy:.1f}% | "
                      f"Rate: {rate:.1f}/sec | "
                      f"ETA: {remaining/60:.0f}min | "
                      f"Errors: {len(self.errors)}")

            # Checkpoint every N matches
            if (i + 1) % self.checkpoint_interval == 0:
                self.save_checkpoint(i + 1)

        elapsed = time.time() - self.start_time
        print()
        print(f"  Completed in {elapsed/60:.1f} minutes")
        print(f"  Processed: {len(self.results)} results, {len(self.errors)} errors")

        # Generate outputs
        summary = BacktestSummary(self.results, self.errors)
        report = summary.format_report()
        print(report)

        # Save summary to file
        summary_path = f"backtest_summary_{today}.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n  Summary saved to: {summary_path}")

        # Save CSV
        if self.output_csv and self.results:
            csv_path = f"backtest_results_{today}.csv"
            self.write_csv(csv_path)
            print(f"  CSV saved to: {csv_path}")

        # Clean up checkpoint on successful completion
        checkpoint_path = Path('backtest_checkpoint.json')
        if checkpoint_path.exists():
            checkpoint_path.unlink()

    def write_csv(self, path: str):
        """Write per-match results to CSV."""
        if not self.results:
            return

        fieldnames = [
            'match_id', 'date', 'tournament', 'surface',
            'p1_name', 'p2_name', 'p1_rank', 'p2_rank',
            'p1_probability', 'predicted_winner', 'actual_winner', 'correct',
            'bet_prob', 'bet_odds', 'implied_prob', 'edge',
            'models', 'is_value_bet', 'stake_units', 'profit_units',
            'confidence', 'weighted_advantage',
            'factor_form', 'factor_surface', 'factor_ranking',
            'factor_h2h', 'factor_fatigue', 'factor_injury',
            'factor_recent_loss', 'factor_performance_elo', 'factor_momentum',
        ]

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for r in self.results:
                row = dict(r)
                # Flatten factor accuracy into columns
                fa = row.pop('factor_accuracy', {})
                for fname in ['form', 'surface', 'ranking', 'h2h', 'fatigue',
                              'injury', 'recent_loss', 'performance_elo', 'momentum']:
                    row[f'factor_{fname}'] = fa.get(fname, '')
                writer.writerow(row)


# ============================================================================
# SUMMARY / ANALYSIS
# ============================================================================

class BacktestSummary:
    """Analyzes backtest results and generates a comprehensive report."""

    def __init__(self, results: List[Dict], errors: List[Dict] = None):
        self.results = results
        self.errors = errors or []
        self.settled = [r for r in results if r.get('models', 'None') != 'None']

    def overall_accuracy(self) -> Dict:
        """Overall prediction accuracy."""
        total = len(self.results)
        correct = sum(1 for r in self.results if r['correct'])
        return {
            'total': total,
            'correct': correct,
            'accuracy': correct / total * 100 if total > 0 else 0,
        }

    def model_performance(self) -> Dict:
        """Performance breakdown by model."""
        model_names = ['Model 3', 'Model 4', 'Model 7', 'Model 8']
        perf = {}

        for model in model_names:
            bets = [r for r in self.results
                    if model in r.get('models', '') and r['stake_units'] > 0]
            if not bets:
                continue

            wins = sum(1 for b in bets if b['correct'])
            losses = len(bets) - wins
            total_staked = sum(b['stake_units'] for b in bets)
            total_profit = sum(b['profit_units'] for b in bets)
            roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
            win_rate = wins / len(bets) * 100 if bets else 0
            avg_odds = statistics.mean(b['bet_odds'] for b in bets) if bets else 0

            perf[model] = {
                'bets': len(bets),
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_staked': total_staked,
                'total_profit': total_profit,
                'roi': roi,
                'avg_odds': avg_odds,
            }

        return perf

    def factor_accuracy(self) -> Dict:
        """Per-factor prediction accuracy."""
        factor_names = ['form', 'surface', 'ranking', 'h2h', 'fatigue',
                        'injury', 'recent_loss', 'performance_elo', 'momentum']
        weights = {
            'form': 20, 'surface': 20, 'ranking': 13, 'h2h': 5,
            'fatigue': 15, 'injury': 5, 'recent_loss': 8,
            'performance_elo': 12, 'momentum': 2,
        }

        acc = {}
        for fname in factor_names:
            correct = 0
            total = 0
            for r in self.results:
                fa = r.get('factor_accuracy', {})
                if fname in fa:
                    total += 1
                    if fa[fname]:
                        correct += 1

            accuracy = correct / total * 100 if total > 0 else 0
            acc[fname] = {
                'correct': correct,
                'total': total,
                'accuracy': accuracy,
                'weight': weights.get(fname, 0),
            }

        return acc

    def calibration_analysis(self) -> List[Dict]:
        """Model probability vs actual win rate in buckets."""
        buckets = [
            (0.50, 0.55), (0.55, 0.60), (0.60, 0.65),
            (0.65, 0.70), (0.70, 0.75), (0.75, 1.00),
        ]

        cal = []
        for lo, hi in buckets:
            matches = [r for r in self.results if lo <= r['bet_prob'] < hi]
            if not matches:
                continue
            actual_win_rate = sum(1 for m in matches if m['correct']) / len(matches) * 100
            expected = (lo + hi) / 2 * 100
            cal.append({
                'range': f'{lo*100:.0f}-{hi*100:.0f}%',
                'count': len(matches),
                'actual_win_rate': actual_win_rate,
                'expected': expected,
                'diff': actual_win_rate - expected,
            })

        return cal

    def surface_breakdown(self) -> Dict:
        """Performance by surface."""
        surfaces = {}
        for r in self.results:
            s = r.get('surface', 'Unknown')
            if s not in surfaces:
                surfaces[s] = {'total': 0, 'correct': 0, 'bets': [], 'profit': 0}
            surfaces[s]['total'] += 1
            if r['correct']:
                surfaces[s]['correct'] += 1
            if r['stake_units'] > 0 and r.get('models', 'None') != 'None':
                surfaces[s]['bets'].append(r)
                surfaces[s]['profit'] += r['profit_units']

        result = {}
        for s, data in sorted(surfaces.items()):
            accuracy = data['correct'] / data['total'] * 100 if data['total'] > 0 else 0
            staked = sum(b['stake_units'] for b in data['bets'])
            roi = (data['profit'] / staked * 100) if staked > 0 else 0
            result[s] = {
                'matches': data['total'],
                'accuracy': accuracy,
                'value_bets': len(data['bets']),
                'profit': data['profit'],
                'roi': roi,
            }

        return result

    def odds_range_breakdown(self) -> List[Dict]:
        """Performance by odds range."""
        ranges = [
            ('1.01-1.99', 1.01, 2.00),
            ('2.00-2.49', 2.00, 2.50),
            ('2.50-2.99', 2.50, 3.00),
            ('3.00-3.99', 3.00, 4.00),
            ('4.00+', 4.00, 100.00),
        ]

        breakdown = []
        for label, lo, hi in ranges:
            bets = [r for r in self.results
                    if lo <= r['bet_odds'] < hi
                    and r['stake_units'] > 0
                    and r.get('models', 'None') != 'None']
            if not bets:
                continue

            wins = sum(1 for b in bets if b['correct'])
            staked = sum(b['stake_units'] for b in bets)
            profit = sum(b['profit_units'] for b in bets)
            roi = (profit / staked * 100) if staked > 0 else 0

            breakdown.append({
                'range': label,
                'bets': len(bets),
                'wins': wins,
                'win_rate': wins / len(bets) * 100 if bets else 0,
                'profit': profit,
                'roi': roi,
            })

        return breakdown

    def format_report(self) -> str:
        """Format the complete summary report as text."""
        lines = []
        w = 70  # Width

        lines.append('=' * w)
        lines.append('  TENNIS BETTING SYSTEM - BACKTEST SUMMARY')
        lines.append(f'  Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        lines.append('=' * w)

        # Overall
        oa = self.overall_accuracy()
        lines.append(f'\n  Matches analysed: {oa["total"]}')
        lines.append(f'  Errors: {len(self.errors)}')
        lines.append(f'  Prediction accuracy: {oa["correct"]}/{oa["total"]} = {oa["accuracy"]:.1f}%')
        lines.append(f'  Breakeven threshold: ~52.4% (at average odds)')

        # Model performance
        mp = self.model_performance()
        if mp:
            lines.append(f'\n{"=" * w}')
            lines.append('  MODEL PERFORMANCE')
            lines.append(f'{"=" * w}')
            lines.append(f'  {"Model":<12} {"Bets":>6} {"Wins":>6} {"Win%":>7} {"Profit":>10} {"ROI":>8} {"Avg Odds":>9}')
            lines.append(f'  {"-" * 58}')
            for model, data in sorted(mp.items()):
                lines.append(
                    f'  {model:<12} {data["bets"]:>6} {data["wins"]:>6} '
                    f'{data["win_rate"]:>6.1f}% {data["total_profit"]:>+9.1f}u '
                    f'{data["roi"]:>+7.1f}% {data["avg_odds"]:>8.2f}'
                )

        # Factor accuracy
        fa = self.factor_accuracy()
        if fa:
            lines.append(f'\n{"=" * w}')
            lines.append('  FACTOR ACCURACY')
            lines.append(f'{"=" * w}')
            lines.append(f'  {"Factor":<18} {"Correct/Total":>14} {"Accuracy":>9} {"Weight":>7} {"Verdict"}')
            lines.append(f'  {"-" * 62}')
            for fname, data in sorted(fa.items(), key=lambda x: x[1]['accuracy'], reverse=True):
                if data['total'] == 0:
                    verdict = 'No data'
                elif data['accuracy'] >= 60:
                    verdict = 'STRONG'
                elif data['accuracy'] >= 50:
                    verdict = 'OK'
                else:
                    verdict = 'HARMFUL'
                lines.append(
                    f'  {fname:<18} {data["correct"]:>5}/{data["total"]:<7} '
                    f'{data["accuracy"]:>8.1f}% {data["weight"]:>5}%   {verdict}'
                )

        # Calibration
        cal = self.calibration_analysis()
        if cal:
            lines.append(f'\n{"=" * w}')
            lines.append('  CALIBRATION (predicted vs actual win rate)')
            lines.append(f'{"=" * w}')
            lines.append(f'  {"Range":<12} {"Matches":>8} {"Actual":>8} {"Expected":>9} {"Diff":>7}')
            lines.append(f'  {"-" * 46}')
            for c in cal:
                lines.append(
                    f'  {c["range"]:<12} {c["count"]:>8} {c["actual_win_rate"]:>7.1f}% '
                    f'{c["expected"]:>8.1f}% {c["diff"]:>+6.1f}%'
                )

        # Surface breakdown
        sb = self.surface_breakdown()
        if sb:
            lines.append(f'\n{"=" * w}')
            lines.append('  SURFACE BREAKDOWN')
            lines.append(f'{"=" * w}')
            lines.append(f'  {"Surface":<10} {"Matches":>8} {"Accuracy":>9} {"Bets":>6} {"Profit":>9} {"ROI":>8}')
            lines.append(f'  {"-" * 52}')
            for s, data in sorted(sb.items()):
                lines.append(
                    f'  {s:<10} {data["matches"]:>8} {data["accuracy"]:>8.1f}% '
                    f'{data["value_bets"]:>6} {data["profit"]:>+8.1f}u {data["roi"]:>+7.1f}%'
                )

        # Odds range breakdown
        ob = self.odds_range_breakdown()
        if ob:
            lines.append(f'\n{"=" * w}')
            lines.append('  ODDS RANGE BREAKDOWN')
            lines.append(f'{"=" * w}')
            lines.append(f'  {"Range":<12} {"Bets":>6} {"Wins":>6} {"Win%":>7} {"Profit":>9} {"ROI":>8}')
            lines.append(f'  {"-" * 50}')
            for o in ob:
                lines.append(
                    f'  {o["range"]:<12} {o["bets"]:>6} {o["wins"]:>6} '
                    f'{o["win_rate"]:>6.1f}% {o["profit"]:>+8.1f}u {o["roi"]:>+7.1f}%'
                )

        lines.append(f'\n{"=" * w}')
        return '\n'.join(lines)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Cloud Backtester - Tennis Betting System'
    )
    parser.add_argument('--sample', type=int, default=0,
                        help='Number of matches to sample (0 = all)')
    parser.add_argument('--months', type=int, default=6,
                        help='Months of historical data (default: 6)')
    parser.add_argument('--from-date', type=str, default=None,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to-date', type=str, default=None,
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--no-csv', action='store_true',
                        help='Skip CSV output')
    parser.add_argument('--checkpoint-interval', type=int, default=500,
                        help='Save checkpoint every N matches')
    parser.add_argument('--db-path', type=str, default=None,
                        help='Path to tennis_betting.db')
    args = parser.parse_args()

    # Import tennis modules (must happen after args parsed for db-path)
    modules = import_tennis_modules(args.db_path)

    runner = BacktestRunner(
        modules=modules,
        sample_size=args.sample,
        months=args.months,
        from_date=args.from_date,
        to_date=args.to_date,
        output_csv=not args.no_csv,
        checkpoint_interval=args.checkpoint_interval,
    )
    runner.run()


if __name__ == '__main__':
    main()
