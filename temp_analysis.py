import sqlite3
from collections import defaultdict

db_path = 'C:/Users/Public/Documents/Tennis Betting System/data/tennis_betting.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

total_bets = conn.execute('SELECT COUNT(*) FROM bets').fetchone()[0]
settled_query = "SELECT COUNT(*) FROM bets WHERE result IS NOT NULL AND result != ''"
settled = conn.execute(settled_query).fetchone()[0]
pending = total_bets - settled

bets_query = "SELECT * FROM bets WHERE result IS NOT NULL AND result != '' ORDER BY match_date DESC"
cursor = conn.execute(bets_query)
bets = [dict(row) for row in cursor.fetchall()]

wins = [b for b in bets if b['result'] == 'Win']
losses = [b for b in bets if b['result'] == 'Loss']
total_pl = sum(b['profit_loss'] or 0 for b in bets)
total_staked = sum(b['stake'] or 0 for b in bets)
roi = (total_pl/total_staked*100) if total_staked > 0 else 0

print('='*60)
print('TENNIS BETTING SYSTEM - FULL ANALYSIS')
print('='*60)
print(f'Total bets in database: {total_bets}')
print(f'Settled: {settled} | Pending: {pending}')
print()
print('OVERALL PERFORMANCE')
print('-'*40)
win_rate = len(wins)/(len(wins)+len(losses))*100 if (len(wins)+len(losses)) > 0 else 0
print(f'Record: {len(wins)}W-{len(losses)}L ({win_rate:.1f}% win rate)')
print(f'P/L: {total_pl:+.2f}u')
print(f'Staked: {total_staked:.2f}u')
print(f'ROI: {roi:+.1f}%')
print()

# By Model
print('BY MODEL')
print('-'*40)
model_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pl': 0, 'staked': 0})
for b in bets:
    m = b['model'] or 'None'
    if b['result'] == 'Win':
        model_stats[m]['wins'] += 1
    else:
        model_stats[m]['losses'] += 1
    model_stats[m]['pl'] += b['profit_loss'] or 0
    model_stats[m]['staked'] += b['stake'] or 0

for model in sorted(model_stats.keys()):
    s = model_stats[model]
    w, l = s['wins'], s['losses']
    roi_m = (s['pl']/s['staked']*100) if s['staked'] > 0 else 0
    print(f'{model:15} | {w:2}W-{l:2}L | {s["pl"]:+7.2f}u | ROI: {roi_m:+6.1f}%')
print()

# By Our Probability Range
print('BY OUR PROBABILITY')
print('-'*40)
prob_ranges = [(0, 0.40, '<40%'), (0.40, 0.45, '40-45%'), (0.45, 0.50, '45-50%'),
               (0.50, 0.55, '50-55%'), (0.55, 0.60, '55-60%'), (0.60, 0.65, '60-65%'), (0.65, 1.0, '65%+')]
for low, high, label in prob_ranges:
    subset = [b for b in bets if b['our_probability'] and low <= b['our_probability'] < high]
    if subset:
        w = len([b for b in subset if b['result'] == 'Win'])
        l = len([b for b in subset if b['result'] == 'Loss'])
        pl = sum(b['profit_loss'] or 0 for b in subset)
        staked = sum(b['stake'] or 0 for b in subset)
        roi_p = (pl/staked*100) if staked > 0 else 0
        print(f'{label:15} | {w:2}W-{l:2}L | {pl:+7.2f}u | ROI: {roi_p:+6.1f}%')
print()

# By Odds Range
print('BY ODDS')
print('-'*40)
odds_ranges = [(1.0, 1.50, '1.00-1.50'), (1.50, 2.00, '1.50-2.00'), (2.00, 2.50, '2.00-2.50'),
               (2.50, 3.00, '2.50-3.00'), (3.00, 4.00, '3.00-4.00'), (4.00, 100, '4.00+')]
for low, high, label in odds_ranges:
    subset = [b for b in bets if b['odds'] and low <= b['odds'] < high]
    if subset:
        w = len([b for b in subset if b['result'] == 'Win'])
        l = len([b for b in subset if b['result'] == 'Loss'])
        pl = sum(b['profit_loss'] or 0 for b in subset)
        staked = sum(b['stake'] or 0 for b in subset)
        roi_o = (pl/staked*100) if staked > 0 else 0
        print(f'{label:15} | {w:2}W-{l:2}L | {pl:+7.2f}u | ROI: {roi_o:+6.1f}%')
print()

# By Stake
print('BY STAKE')
print('-'*40)
stake_vals = sorted(set(b['stake'] for b in bets if b['stake']))
for sv in stake_vals:
    subset = [b for b in bets if b['stake'] == sv]
    if subset:
        w = len([b for b in subset if b['result'] == 'Win'])
        l = len([b for b in subset if b['result'] == 'Loss'])
        pl = sum(b['profit_loss'] or 0 for b in subset)
        staked = sum(b['stake'] or 0 for b in subset)
        roi_s = (pl/staked*100) if staked > 0 else 0
        print(f'{sv:.1f}u            | {w:2}W-{l:2}L | {pl:+7.2f}u | ROI: {roi_s:+6.1f}%')
print()

# By Tournament Level
print('BY TOURNAMENT LEVEL')
print('-'*40)
level_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pl': 0, 'staked': 0})
for b in bets:
    t = (b['tournament'] or '').lower()
    if 'grand slam' in t or 'australian open' in t or 'french open' in t or 'wimbledon' in t or 'us open' in t:
        level = 'Grand Slam'
    elif 'masters' in t or '1000' in t:
        level = 'Masters 1000'
    elif '500' in t:
        level = 'ATP 500'
    elif '250' in t:
        level = 'ATP 250'
    elif 'challenger' in t:
        level = 'Challenger'
    elif 'itf' in t or 'futures' in t:
        level = 'ITF/Futures'
    else:
        level = 'Other'

    if b['result'] == 'Win':
        level_stats[level]['wins'] += 1
    else:
        level_stats[level]['losses'] += 1
    level_stats[level]['pl'] += b['profit_loss'] or 0
    level_stats[level]['staked'] += b['stake'] or 0

for level in ['Grand Slam', 'Masters 1000', 'ATP 500', 'ATP 250', 'Challenger', 'ITF/Futures', 'Other']:
    if level in level_stats:
        s = level_stats[level]
        w, l = s['wins'], s['losses']
        roi_l = (s['pl']/s['staked']*100) if s['staked'] > 0 else 0
        print(f'{level:15} | {w:2}W-{l:2}L | {s["pl"]:+7.2f}u | ROI: {roi_l:+6.1f}%')
print()

# Edge analysis
print('BY CALCULATED EDGE')
print('-'*40)
edge_ranges = [(0, 0.05, '0-5%'), (0.05, 0.10, '5-10%'), (0.10, 0.15, '10-15%'),
               (0.15, 0.20, '15-20%'), (0.20, 0.30, '20-30%'), (0.30, 1.0, '30%+')]
for low, high, label in edge_ranges:
    subset = []
    for b in bets:
        if b['our_probability'] and b['implied_probability']:
            edge = b['our_probability'] - b['implied_probability']
            if low <= edge < high:
                subset.append(b)
    if subset:
        w = len([b for b in subset if b['result'] == 'Win'])
        l = len([b for b in subset if b['result'] == 'Loss'])
        pl = sum(b['profit_loss'] or 0 for b in subset)
        staked = sum(b['stake'] or 0 for b in subset)
        roi_e = (pl/staked*100) if staked > 0 else 0
        print(f'{label:15} | {w:2}W-{l:2}L | {pl:+7.2f}u | ROI: {roi_e:+6.1f}%')
print()

# Individual bets
print('INDIVIDUAL BETS (Most Recent First)')
print('-'*95)
print(f'{"R":3} {"Selection":30} {"Odds":>5} {"Stake":>5} {"Prob":>5} {"P/L":>7} {"Model":12} Tournament')
print('-'*95)
for b in bets[:30]:
    r = 'W' if b['result'] == 'Win' else 'L'
    prob = int(b['our_probability']*100) if b['our_probability'] else 0
    model = (b['model'] or 'None')[:12]
    sel = (b['selection'] or 'Unknown')[:30]
    tourn = (b['tournament'] or '')[:25]
    odds = b['odds'] or 0
    stake = b['stake'] or 0
    pl = b['profit_loss'] or 0
    print(f'{r:3} {sel:30} {odds:5.2f} {stake:5.1f} {prob:4}% {pl:+7.2f} {model:12} {tourn}')

if len(bets) > 30:
    print(f'... and {len(bets) - 30} more bets')

conn.close()
