"""
Detailed Model Analysis for Nardi vs Wu
"""

from match_analyzer import MatchAnalyzer
from database import db
from datetime import datetime

def run_detailed_analysis():
    analyzer = MatchAnalyzer()

    nardi_id = 768995594
    wu_id = 633768530

    # Get player info
    nardi = db.get_player(nardi_id)
    wu = db.get_player(wu_id)

    print('=' * 70)
    print('DETAILED MODEL ANALYSIS: Nardi vs Wu')
    print('Australian Open 2026 - Hard Court')
    print('=' * 70)

    print()
    print('PLAYER PROFILES:')
    print('-' * 70)
    print(f"Luca Nardi: Ranking #{nardi.get('current_ranking', 'N/A')}")
    print(f"Yibing Wu: Ranking #{wu.get('current_ranking', 'N/A')}")

    # Get recent matches for both
    print()
    print('=' * 70)
    print('RECENT MATCH HISTORY')
    print('=' * 70)

    today = datetime.now()

    print()
    print('NARDI - Last 6 matches:')
    nardi_matches = db.get_player_matches(nardi_id, limit=6)
    for m in nardi_matches:
        won = m.get('winner_id') == nardi_id
        result = 'WIN' if won else 'LOSS'
        opp_id = m.get('loser_id') if won else m.get('winner_id')
        opp = db.get_player(opp_id)
        opp_name = opp.get('name', 'Unknown') if opp else 'Unknown'
        opp_rank = opp.get('current_ranking', 'N/A') if opp else 'N/A'
        date_str = m.get('date', '')[:10]
        try:
            match_date = datetime.strptime(date_str, '%Y-%m-%d')
            days_ago = (today - match_date).days
        except:
            days_ago = '?'
        print(f"  {date_str} ({days_ago}d ago): {result} vs {opp_name} (#{opp_rank}) - {m.get('score', '')}")

    print()
    print('WU - Last 6 matches:')
    wu_matches = db.get_player_matches(wu_id, limit=6)
    for m in wu_matches:
        won = m.get('winner_id') == wu_id
        result = 'WIN' if won else 'LOSS'
        opp_id = m.get('loser_id') if won else m.get('winner_id')
        opp = db.get_player(opp_id)
        opp_name = opp.get('name', 'Unknown') if opp else 'Unknown'
        opp_rank = opp.get('current_ranking', 'N/A') if opp else 'N/A'
        date_str = m.get('date', '')[:10]
        try:
            match_date = datetime.strptime(date_str, '%Y-%m-%d')
            days_ago = (today - match_date).days
        except:
            days_ago = '?'
        print(f"  {date_str} ({days_ago}d ago): {result} vs {opp_name} (#{opp_rank}) - {m.get('score', '')}")

    # Run full analysis
    result = analyzer.calculate_win_probability(nardi_id, wu_id, 'Hard', None, 2.76, 1.51)

    print()
    print('=' * 70)
    print('FACTOR-BY-FACTOR ANALYSIS')
    print('=' * 70)

    factors = result['factors']

    # 1. RANKING
    print()
    print('1. RANKING FACTOR')
    print('-' * 70)
    rank_data = factors['ranking']['data']
    print(f"   Nardi: #{rank_data['p1_rank']} (Elo: {rank_data['p1_elo']:.0f})")
    print(f"   Wu: #{rank_data['p2_rank']} (Elo: {rank_data['p2_elo']:.0f})")
    print(f"   Elo Win Probability: {rank_data['elo_win_prob']*100:.1f}% for Nardi")
    print(f"   Advantage: {factors['ranking']['advantage']:+.3f} (Nardi favored by ranking)")
    print(f"   Weight: {factors['ranking']['weight']*100:.0f}%")

    # 2. FORM
    print()
    print('2. FORM FACTOR (Recent Win/Loss Record)')
    print('-' * 70)
    print(f"   Nardi: Score {factors['form']['p1']['score']:.1f}/100 ({factors['form']['p1']['wins']}W-{factors['form']['p1']['losses']}L)")
    print(f"   Wu: Score {factors['form']['p2']['score']:.1f}/100 ({factors['form']['p2']['wins']}W-{factors['form']['p2']['losses']}L)")
    print(f"   Advantage: {factors['form']['advantage']:+.3f} (Wu has better form)")
    print(f"   Weight: {factors['form']['weight']*100:.0f}%")

    # 3. SURFACE
    print()
    print('3. SURFACE FACTOR (Hard Court Performance)')
    print('-' * 70)
    print(f"   Nardi: {factors['surface']['p1']['combined_win_rate']*100:.1f}% win rate on Hard")
    print(f"   Wu: {factors['surface']['p2']['combined_win_rate']*100:.1f}% win rate on Hard")
    print(f"   Advantage: {factors['surface']['advantage']:+.3f} (Wu better on Hard)")
    print(f"   Weight: {factors['surface']['weight']*100:.0f}%")

    # 4. H2H
    print()
    print('4. HEAD-TO-HEAD FACTOR')
    print('-' * 70)
    h2h = factors['h2h']['data']
    print(f"   Record: Nardi {h2h['p1_wins']} - {h2h['p2_wins']} Wu")
    print(f"   Advantage: {factors['h2h']['advantage']:+.3f}")
    print(f"   Weight: {factors['h2h']['weight']*100:.0f}%")

    # 5. FATIGUE
    print()
    print('5. FATIGUE FACTOR')
    print('-' * 70)
    print(f"   Nardi: {factors['fatigue']['p1']['status']} (Score: {factors['fatigue']['p1']['score']:.0f})")
    print(f"   Wu: {factors['fatigue']['p2']['status']} (Score: {factors['fatigue']['p2']['score']:.0f})")
    print(f"   Advantage: {factors['fatigue']['advantage']:+.3f}")
    print(f"   Weight: {factors['fatigue']['weight']*100:.0f}%")

    # 6. INJURY
    print()
    print('6. INJURY FACTOR')
    print('-' * 70)
    print(f"   Nardi: {factors['injury']['p1']['status']}")
    print(f"   Wu: {factors['injury']['p2']['status']}")
    print(f"   Advantage: {factors['injury']['advantage']:+.3f}")
    print(f"   Weight: {factors['injury']['weight']*100:.0f}%")

    # NEW FACTORS
    print()
    print('=' * 70)
    print('NEW FACTORS (Added from Analysis)')
    print('=' * 70)

    # 7. OPPONENT QUALITY
    print()
    print('7. OPPONENT QUALITY FACTOR')
    print('-' * 70)
    print('   Concept: Wins vs top players worth more than wins vs low-ranked players.')
    print('   Also weighted by recency - old results count less.')
    print()
    print('   NARDI:')
    for d in factors['opponent_quality']['p1']['details']:
        print(f"     {d['result']} vs {d['opponent']} (#{d['opponent_rank']}) {d['days_ago']}d ago -> weight {d['combined_weight']:.2f}")
    print(f"   Score: {factors['opponent_quality']['p1']['score']:.3f}")
    print()
    print('   WU:')
    for d in factors['opponent_quality']['p2']['details']:
        print(f"     {d['result']} vs {d['opponent']} (#{d['opponent_rank']}) {d['days_ago']}d ago -> weight {d['combined_weight']:.2f}")
    print(f"   Score: {factors['opponent_quality']['p2']['score']:.3f}")
    print(f"   Advantage: {factors['opponent_quality']['advantage']:+.3f}")
    print(f"   Weight: {factors['opponent_quality']['weight']*100:.0f}%")

    # 8. RECENCY
    print()
    print('8. RECENCY FACTOR')
    print('-' * 70)
    print('   Concept: Recent matches (last 7 days) matter more than old ones.')
    print()
    print('   NARDI:')
    for d in factors['recency']['p1']['details']:
        print(f"     {d['result']} on {d['date']} ({d['days_ago']}d ago) -> recency weight {d['recency_weight']}")
    print(f"   Score: {factors['recency']['p1']['score']:.3f}")
    print()
    print('   WU:')
    for d in factors['recency']['p2']['details']:
        print(f"     {d['result']} on {d['date']} ({d['days_ago']}d ago) -> recency weight {d['recency_weight']}")
    print(f"   Score: {factors['recency']['p2']['score']:.3f}")
    print(f"   Advantage: {factors['recency']['advantage']:+.3f}")
    print(f"   Weight: {factors['recency']['weight']*100:.0f}%")

    # 9. RECENT LOSS
    print()
    print('9. RECENT LOSS PENALTY FACTOR')
    print('-' * 70)
    print('   Concept: Players coming off a recent loss may have issues.')
    print()
    print(f"   NARDI: {factors['recent_loss']['p1']['details']}")
    print(f"   Penalty: {factors['recent_loss']['p1']['penalty']:.3f}")
    print()
    print(f"   WU: {factors['recent_loss']['p2']['details']}")
    print(f"   Penalty: {factors['recent_loss']['p2']['penalty']:.3f}")
    print(f"   Advantage: {factors['recent_loss']['advantage']:+.3f}")
    print(f"   Weight: {factors['recent_loss']['weight']*100:.0f}%")

    # 10. MOMENTUM
    print()
    print('10. MOMENTUM FACTOR')
    print('-' * 70)
    print('   Concept: Recent wins on same surface = tournament momentum.')
    print()
    print(f"   NARDI: {factors['momentum']['p1']['details']}")
    print(f"   Bonus: {factors['momentum']['p1']['bonus']:.3f}")
    print()
    print(f"   WU: {factors['momentum']['p2']['details']}")
    print(f"   Bonus: {factors['momentum']['p2']['bonus']:.3f}")
    print(f"   Advantage: {factors['momentum']['advantage']:+.3f}")
    print(f"   Weight: {factors['momentum']['weight']*100:.0f}%")

    # FINAL CALCULATION
    print()
    print('=' * 70)
    print('FINAL PROBABILITY CALCULATION')
    print('=' * 70)
    print()
    print('Weighted Advantages (positive = Nardi, negative = Wu):')
    print(f"   Ranking:          {factors['ranking']['advantage']:+.3f} x {factors['ranking']['weight']*100:.0f}% = {factors['ranking']['advantage'] * factors['ranking']['weight']:+.4f}")
    print(f"   Form:             {factors['form']['advantage']:+.3f} x {factors['form']['weight']*100:.0f}% = {factors['form']['advantage'] * factors['form']['weight']:+.4f}")
    print(f"   Surface:          {factors['surface']['advantage']:+.3f} x {factors['surface']['weight']*100:.0f}% = {factors['surface']['advantage'] * factors['surface']['weight']:+.4f}")
    print(f"   H2H:              {factors['h2h']['advantage']:+.3f} x {factors['h2h']['weight']*100:.0f}% = {factors['h2h']['advantage'] * factors['h2h']['weight']:+.4f}")
    print(f"   Fatigue:          {factors['fatigue']['advantage']:+.3f} x {factors['fatigue']['weight']*100:.0f}% = {factors['fatigue']['advantage'] * factors['fatigue']['weight']:+.4f}")
    print(f"   Injury:           {factors['injury']['advantage']:+.3f} x {factors['injury']['weight']*100:.0f}% = {factors['injury']['advantage'] * factors['injury']['weight']:+.4f}")
    print(f"   Opp Quality:      {factors['opponent_quality']['advantage']:+.3f} x {factors['opponent_quality']['weight']*100:.0f}% = {factors['opponent_quality']['advantage'] * factors['opponent_quality']['weight']:+.4f}")
    print(f"   Recency:          {factors['recency']['advantage']:+.3f} x {factors['recency']['weight']*100:.0f}% = {factors['recency']['advantage'] * factors['recency']['weight']:+.4f}")
    print(f"   Recent Loss:      {factors['recent_loss']['advantage']:+.3f} x {factors['recent_loss']['weight']*100:.0f}% = {factors['recent_loss']['advantage'] * factors['recent_loss']['weight']:+.4f}")
    print(f"   Momentum:         {factors['momentum']['advantage']:+.3f} x {factors['momentum']['weight']*100:.0f}% = {factors['momentum']['advantage'] * factors['momentum']['weight']:+.4f}")
    print()
    print(f"   Total Weighted Advantage: {result['weighted_advantage']:+.4f}")
    print()
    print(f"   Converted to probability using logistic function:")
    print(f"   P(Nardi) = 1 / (1 + e^(-3 x {result['weighted_advantage']:.4f})) = {result['p1_probability']*100:.1f}%")

    print()
    print('=' * 70)
    print('FINAL RESULT')
    print('=' * 70)
    print(f"   Our Model:  Nardi {result['p1_probability']*100:.1f}% - Wu {result['p2_probability']*100:.1f}%")
    print(f"   Betfair:    Nardi 36.2% - Wu 66.2%")
    print(f"   Gap:        {abs(result['p1_probability']*100 - 36.2):.1f}%")
    print()
    print("   Key insight: Ranking still heavily favors Nardi (#108 vs #168),")
    print("   but form factors show Wu is the better current player.")


if __name__ == '__main__':
    run_detailed_analysis()
