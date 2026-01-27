"""
Comprehensive Model Analysis: Proposed Factor Changes
Analyzing Nardi vs Wu to understand probability discrepancy with Betfair
"""

from database import db
from match_analyzer import MatchAnalyzer
from datetime import datetime, timedelta

def run_analysis():
    nardi_id = 768995594
    wu_id = 633768530

    analyzer = MatchAnalyzer()

    print('=' * 70)
    print('COMPREHENSIVE MODEL ANALYSIS: Nardi vs Wu')
    print('=' * 70)

    # Current model result
    current = analyzer.calculate_win_probability(nardi_id, wu_id, 'Hard', None, 2.76, 1.51)
    print(f'\n### CURRENT MODEL OUTPUT ###')
    print(f'Nardi: {current["p1_probability"]*100:.1f}%')
    print(f'Wu: {current["p2_probability"]*100:.1f}%')
    print(f'Betfair Implied: Nardi 36.2%, Wu 66.2%')
    print(f'Gap: {abs(current["p1_probability"]*100 - 36.2):.1f}% difference')

    # Get detailed match data
    nardi_matches = db.get_player_matches(nardi_id, limit=10)
    wu_matches = db.get_player_matches(wu_id, limit=10)

    print('\n' + '=' * 70)
    print('PROPOSED FACTOR 1: Opponent Quality Weighting')
    print('=' * 70)
    print('''
CONCEPT: Not all wins are equal. Beating a #53 player is worth more than
beating a #181 player. Current model treats all wins the same.

CALCULATION METHOD:
- For each recent match, get opponent ranking
- Weight win/loss by opponent strength: weight = 1 + (200 - opp_rank) / 200
- A win vs #50 gets weight ~1.75, win vs #150 gets weight ~1.25
''')

    # Calculate opponent-weighted form
    def get_opponent_quality_score(player_id, matches):
        if not matches:
            return 0, []

        details = []
        weighted_score = 0
        total_weight = 0

        for m in matches[:6]:  # Last 6 matches
            won = m.get('winner_id') == player_id
            opp_id = m.get('loser_id') if won else m.get('winner_id')
            opp = db.get_player(opp_id)
            opp_rank = None
            if opp:
                opp_rank = opp.get('current_ranking') or opp.get('ranking')

            if opp_rank is None:
                opp_rank = 200  # Default for unranked

            # Weight based on opponent quality
            quality_weight = 1 + (200 - min(opp_rank, 200)) / 200

            if won:
                weighted_score += quality_weight
            else:
                weighted_score -= quality_weight * 0.8  # Losses slightly less weighted

            total_weight += quality_weight

            result = 'W' if won else 'L'
            opp_name = opp.get('name', 'Unknown')[:20] if opp else 'Unknown'
            details.append(f'{result} vs {opp_name} (#{opp_rank}) -> weight: {quality_weight:.2f}')

        normalized = weighted_score / total_weight if total_weight > 0 else 0
        return normalized, details

    nardi_qual, nardi_details = get_opponent_quality_score(nardi_id, nardi_matches)
    wu_qual, wu_details = get_opponent_quality_score(wu_id, wu_matches)

    print('NARDI opponent-quality breakdown:')
    for d in nardi_details:
        print(f'  {d}')
    print(f'  Quality-weighted score: {nardi_qual:.3f}')

    print('\nWU opponent-quality breakdown:')
    for d in wu_details:
        print(f'  {d}')
    print(f'  Quality-weighted score: {wu_qual:.3f}')

    quality_advantage = wu_qual - nardi_qual
    print(f'\nOPPONENT QUALITY ADVANTAGE: Wu +{quality_advantage:.3f}')

    print('\n' + '=' * 70)
    print('PROPOSED FACTOR 2: Recency Weighting')
    print('=' * 70)
    print('''
CONCEPT: Recent matches matter more than older ones. A win yesterday
is more predictive than a win 3 months ago.

CALCULATION METHOD:
- Matches in last 7 days: weight 1.0
- Matches 7-30 days ago: weight 0.7
- Matches 30-90 days ago: weight 0.4
- Matches 90+ days ago: weight 0.2
''')

    def get_recency_score(player_id, matches):
        if not matches:
            return 0, []

        today = datetime.now()
        details = []
        weighted_score = 0
        total_weight = 0

        for m in matches[:6]:
            won = m.get('winner_id') == player_id
            date_str = m.get('date', '')[:10]
            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except:
                days_ago = 90

            # Recency weight
            if days_ago <= 7:
                recency_weight = 1.0
            elif days_ago <= 30:
                recency_weight = 0.7
            elif days_ago <= 90:
                recency_weight = 0.4
            else:
                recency_weight = 0.2

            if won:
                weighted_score += recency_weight
            else:
                weighted_score -= recency_weight

            total_weight += recency_weight

            result = 'W' if won else 'L'
            details.append(f'{result} ({date_str}, {days_ago}d ago) -> recency weight: {recency_weight:.1f}')

        normalized = weighted_score / total_weight if total_weight > 0 else 0
        return normalized, details

    nardi_rec, nardi_rec_details = get_recency_score(nardi_id, nardi_matches)
    wu_rec, wu_rec_details = get_recency_score(wu_id, wu_matches)

    print('NARDI recency breakdown:')
    for d in nardi_rec_details:
        print(f'  {d}')
    print(f'  Recency-weighted score: {nardi_rec:.3f}')

    print('\nWU recency breakdown:')
    for d in wu_rec_details:
        print(f'  {d}')
    print(f'  Recency-weighted score: {wu_rec:.3f}')

    recency_advantage = wu_rec - nardi_rec
    print(f'\nRECENCY ADVANTAGE: Wu +{recency_advantage:.3f}')

    print('\n' + '=' * 70)
    print('PROPOSED FACTOR 3: Recent Loss Penalty')
    print('=' * 70)
    print('''
CONCEPT: Players coming off a recent loss (especially in the same
tournament or in the last 7 days) are less likely to perform well.
Psychological factor + possible underlying issue that caused the loss.

CALCULATION METHOD:
- Loss in last 3 days: -0.10 penalty
- Loss in last 7 days: -0.05 penalty
- 5-set loss in last 7 days: additional -0.05 penalty (fatigue + demoralization)
''')

    def get_recent_loss_penalty(player_id, matches):
        today = datetime.now()
        penalty = 0
        details = []

        for m in matches[:3]:  # Check last 3 matches
            won = m.get('winner_id') == player_id
            if not won:
                date_str = m.get('date', '')[:10]
                score = m.get('score', '')
                try:
                    match_date = datetime.strptime(date_str, '%Y-%m-%d')
                    days_ago = (today - match_date).days
                except:
                    days_ago = 30

                is_5_setter = score.count(',') >= 4 or score.count('-') >= 5

                if days_ago <= 3:
                    penalty += 0.10
                    details.append(f'Loss {days_ago}d ago -> -0.10 penalty')
                elif days_ago <= 7:
                    penalty += 0.05
                    details.append(f'Loss {days_ago}d ago -> -0.05 penalty')

                if is_5_setter and days_ago <= 7:
                    penalty += 0.05
                    details.append(f'5-set loss -> additional -0.05 penalty')

                break  # Only check most recent loss

        if not details:
            details.append('No recent losses -> no penalty')

        return penalty, details

    nardi_penalty, nardi_pen_details = get_recent_loss_penalty(nardi_id, nardi_matches)
    wu_penalty, wu_pen_details = get_recent_loss_penalty(wu_id, wu_matches)

    print('NARDI recent loss check:')
    for d in nardi_pen_details:
        print(f'  {d}')
    print(f'  Total penalty: -{nardi_penalty:.2f}')

    print('\nWU recent loss check:')
    for d in wu_pen_details:
        print(f'  {d}')
    print(f'  Total penalty: -{wu_penalty:.2f}')

    loss_penalty_diff = nardi_penalty - wu_penalty
    print(f'\nLOSS PENALTY DIFFERENCE: Nardi -{loss_penalty_diff:.2f}')

    print('\n' + '=' * 70)
    print('PROPOSED FACTOR 4: Tournament Momentum')
    print('=' * 70)
    print('''
CONCEPT: Players who have won matches in the CURRENT tournament have
momentum, court familiarity, and proven current form.

CALCULATION METHOD:
- Each win in the current tournament (last 14 days, same surface): +0.03
- Cap at +0.10 total
''')

    def get_tournament_momentum(player_id, matches):
        today = datetime.now()
        bonus = 0
        details = []

        for m in matches[:5]:
            won = m.get('winner_id') == player_id
            if not won:
                continue

            date_str = m.get('date', '')[:10]
            surface = m.get('surface', '')

            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except:
                days_ago = 30

            if days_ago <= 14 and surface == 'Hard':
                bonus += 0.03
                details.append(f'Win on Hard {days_ago}d ago -> +0.03')

        bonus = min(bonus, 0.10)  # Cap
        if not details:
            details.append('No recent tournament wins')

        return bonus, details

    nardi_momentum, nardi_mom_details = get_tournament_momentum(nardi_id, nardi_matches)
    wu_momentum, wu_mom_details = get_tournament_momentum(wu_id, wu_matches)

    print('NARDI tournament momentum:')
    for d in nardi_mom_details:
        print(f'  {d}')
    print(f'  Momentum bonus: +{nardi_momentum:.2f}')

    print('\nWU tournament momentum:')
    for d in wu_mom_details:
        print(f'  {d}')
    print(f'  Momentum bonus: +{wu_momentum:.2f}')

    momentum_diff = wu_momentum - nardi_momentum
    print(f'\nMOMENTUM ADVANTAGE: Wu +{momentum_diff:.2f}')

    print('\n' + '=' * 70)
    print('COMBINED IMPACT CALCULATION')
    print('=' * 70)

    # Current model base
    base_nardi = current['p1_probability']
    base_wu = current['p2_probability']

    print(f'Current model: Nardi {base_nardi*100:.1f}% vs Wu {base_wu*100:.1f}%')

    # Apply adjustments
    total_wu_advantage = quality_advantage + recency_advantage + loss_penalty_diff + momentum_diff
    print(f'\nTotal Wu advantages:')
    print(f'  Opponent quality: +{quality_advantage:.3f}')
    print(f'  Recency: +{recency_advantage:.3f}')
    print(f'  Loss penalty diff: +{loss_penalty_diff:.3f}')
    print(f'  Momentum: +{momentum_diff:.3f}')
    print(f'  TOTAL: +{total_wu_advantage:.3f}')

    # Convert to probability shift (0.1 advantage = ~5% shift)
    prob_shift = total_wu_advantage * 0.5  # 50% conversion factor

    adjusted_nardi = base_nardi - prob_shift/2
    adjusted_wu = base_wu + prob_shift/2

    # Normalize to ensure they sum to 1
    total = adjusted_nardi + adjusted_wu
    adjusted_nardi = adjusted_nardi / total
    adjusted_wu = adjusted_wu / total

    print(f'\n### ADJUSTED MODEL OUTPUT ###')
    print(f'Nardi: {adjusted_nardi*100:.1f}%')
    print(f'Wu: {adjusted_wu*100:.1f}%')
    print(f'\nBetfair Implied: Nardi 36.2%, Wu 66.2%')
    print(f'New gap: {abs(adjusted_nardi*100 - 36.2):.1f}% difference (was {abs(base_nardi*100 - 36.2):.1f}%)')

    print('\n' + '=' * 70)
    print('SUMMARY')
    print('=' * 70)
    print(f'''
CURRENT MODEL:     Nardi {base_nardi*100:.1f}% - Wu {base_wu*100:.1f}%
WITH CHANGES:      Nardi {adjusted_nardi*100:.1f}% - Wu {adjusted_wu*100:.1f}%
BETFAIR IMPLIED:   Nardi 36.2% - Wu 66.2%

The proposed changes would move our probability {abs(base_nardi - adjusted_nardi)*100:.1f}%
closer to Betfair's implied probability.

Remaining gap of {abs(adjusted_nardi*100 - 36.2):.1f}% could be explained by:
- Market information/insider knowledge
- Other factors (injuries, personal issues, travel)
- Betfair overreaction to recent results
- Our model still being more accurate (value bet opportunity)
''')

    return {
        'current': {'nardi': base_nardi, 'wu': base_wu},
        'adjusted': {'nardi': adjusted_nardi, 'wu': adjusted_wu},
        'factors': {
            'opponent_quality': quality_advantage,
            'recency': recency_advantage,
            'loss_penalty': loss_penalty_diff,
            'momentum': momentum_diff
        }
    }


if __name__ == '__main__':
    run_analysis()
