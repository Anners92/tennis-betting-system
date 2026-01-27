"""
Import test bets from screenshot data to populate the dashboard.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
from datetime import datetime

# Bet data extracted from screenshot
# Format: (date, match, selection, units, odds, result, pl)
bets_data = [
    ("2026-01-22", "Soonwoo Kwon vs Nikolai Barsukov", "Nikolai Barsukov", 1.00, 10.00, "Loss", -1.00),
    ("2026-01-22", "Max Hans Rehberg vs Arthur Weber", "Arthur Weber", 3.00, 3.35, "Loss", -3.00),
    ("2026-01-22", "Eliot Spizzirri vs Yibing Wu", "Yibing Wu", 2.00, 2.38, "Loss", -2.00),
    ("2026-01-22", "Elise Mertens vs Moyuka Uchijima", "Moyuka Uchijima", 1.00, 7.00, "Loss", -1.00),
    ("2026-01-22", "Tomas Machac vs Stefanos Tsitsipas", "Stefanos Tsitsipas", 2.00, 2.56, "Loss", -2.00),
    ("2026-01-22", "Arthur Gea vs Stan Wawrinka", "Stan Wawrinka", 1.00, 2.44, "Win", 1.44),
    ("2026-01-22", "Botic Van de Zandschulp vs Juncheng Shang", "Botic Van de Zandschulp", 3.00, 2.38, "Win", 4.14),
    ("2026-01-22", "Omar Jasika vs Ilia Simakin", "Omar Jasika", 3.00, 3.05, "Loss", -3.00),
    ("2026-01-22", "Robin Bertrand vs Hyeon Chung", "Robin Bertrand", 2.00, 1.79, "Win", 1.58),
    ("2026-01-22", "Katerina Siniakova vs Amanda Anisimova", "Katerina Siniakova", 2.00, 3.90, "Loss", -2.00),
    ("2026-01-22", "Francesco Maestrelli vs Novak Djokovic", "Francesco Maestrelli", 1.00, 38.00, "Loss", -1.00),
    ("2026-01-22", "Linda Noskova vs Taylah Preston", "Linda Noskova", 1.00, 1.20, "Win", 0.20),
    ("2026-01-22", "Maddison Inglis vs Laura Siegemund", "Laura Siegemund", 3.00, 1.74, "Loss", -3.00),
    ("2026-01-22", "Anna Kalinskaya vs Julia Grabher", "Julia Grabher", 3.00, 8.60, "Loss", -3.00),
    ("2026-01-22", "Xinyu Wang vs Jelena Ostapenko", "Jelena Ostapenko", 3.00, 2.34, "Loss", -3.00),
    ("2026-01-22", "Peyton Stearns vs Petra Marcinko", "Petra Marcinko", 3.00, 2.46, "Loss", -3.00),
    ("2026-01-22", "Janice Tjen vs Karolina Pliskova", "Janice Tjen", 3.00, 1.37, "Loss", -3.00),
    ("2026-01-22", "Ben Shelton vs Dane Sweeny", "Dane Sweeny", 1.00, 10.00, "Loss", -1.00),
    ("2026-01-22", "Jessica Pegula vs Mccartney Kessler", "Mccartney Kessler", 3.00, 4.30, "Loss", -3.00),
    ("2026-01-22", "Sebastian Baez vs Luciano Darderi", "Luciano Darderi", 3.00, 2.50, "Win", 4.50),
    ("2026-01-22", "Jakub Mensik vs Rafael Jodar", "Jakub Mensik", 2.00, 1.61, "Win", 1.22),
    ("2026-01-22", "Ashlyn Krueger vs Madison Keys", "Ashlyn Krueger", 1.00, 4.80, "Loss", -1.00),
    ("2026-01-22", "Karen Khachanov vs Nishesh Basavareddy", "Karen Khachanov", 2.00, 1.39, "Win", 0.78),
    ("2026-01-21", "Hugo Dellien vs Igor Marcondes", "Hugo Dellien", 1.00, 1.71, "Loss", -1.00),
    ("2026-01-21", "Genaro Alberto Olivieri vs Thiago Seyboth Wild", "Genaro Alberto Olivieri", 3.00, 3.15, "Loss", -3.00),
    ("2026-01-21", "Sofia Johnson vs Bianca Andreescu", "Sofia Johnson", 3.00, 11.00, "Loss", -3.00),
    ("2026-01-21", "Isabella Marton vs Margaux Rouvroy", "Isabella Marton", 1.00, 11.00, "Loss", -1.00),
    ("2026-01-21", "Kira Pavlova vs Emma Van Poppel", "Emma Van Poppel", 1.00, 13.50, "Loss", -1.00),
    ("2026-01-21", "Jiangxue Han vs Katerina Zavatska", "Jiangxue Han", 1.00, 7.40, "Loss", -1.00),
    ("2026-01-21", "Karla Popovic vs Jenna Dean", "Jenna Dean", 1.00, 2.28, "Loss", -1.00),
    ("2026-01-21", "Alicia Herrero Linana vs Malkia Ngounoue", "Malkia Ngounoue", 1.00, 4.10, "Loss", -1.00),
    ("2026-01-21", "Alexis Nguyen vs Kajsa Rinaldo Persson", "Alexis Nguyen", 3.00, 6.00, "Loss", -3.00),
]

def estimate_our_probability(odds, units):
    """
    Estimate what our model's probability was based on stake and odds.
    Higher stakes = model thought there was more edge.
    This is reverse-engineered from the staking behavior.
    """
    implied_prob = 1 / odds

    # The old system used edge tiers:
    # 1 unit = 5-10% edge
    # 2 units = 10-15% edge
    # 3 units = 15%+ edge

    if units >= 3:
        edge = 0.18  # ~18% edge for 3 unit bets
    elif units >= 2:
        edge = 0.12  # ~12% edge for 2 unit bets
    else:
        edge = 0.07  # ~7% edge for 1 unit bets

    our_prob = implied_prob + edge

    # Cap at 95%
    return min(our_prob, 0.95)

def import_bets():
    """Import all bets into the database."""
    print("Importing test bets...")

    count = 0
    for date, match, selection, units, odds, result, pl in bets_data:
        # Extract player names from match
        players = match.split(" vs ")
        player1 = players[0] if len(players) > 0 else ""
        player2 = players[1] if len(players) > 1 else ""

        # Calculate probabilities
        implied_prob = 1 / odds
        our_prob = estimate_our_probability(odds, units)
        ev = (our_prob * (odds - 1)) - (1 - our_prob)

        bet_data = {
            'match_date': date,
            'tournament': 'Australian Open 2026' if 'Australian' in match or any(name in match for name in ['Djokovic', 'Alcaraz', 'Sabalenka', 'Medvedev', 'Zverev', 'Gauff', 'Pegula', 'Tsitsipas', 'Rublev', 'Keys', 'Shelton', 'Khachanov']) else 'ATP/WTA Tour',
            'match_description': match,
            'player1': player1,
            'player2': player2,
            'market': 'Match Winner',
            'selection': selection,
            'stake': units,
            'odds': odds,
            'our_probability': our_prob,
            'implied_probability': implied_prob,
            'ev_at_placement': ev,
            'notes': f"Imported from screenshot | Edge: {(our_prob - implied_prob)*100:.1f}%",
        }

        # Add the bet
        bet_id = db.add_bet(bet_data)

        # Settle the bet
        if result in ('Win', 'Loss'):
            db.settle_bet(bet_id, result, pl)

        count += 1
        print(f"  Added: {selection} @ {odds} ({result}) - Our prob: {our_prob*100:.1f}%, Implied: {implied_prob*100:.1f}%")

    print(f"\nImported {count} bets successfully!")

    # Print summary
    print("\nSummary by odds range:")
    ranges = [
        ("1.00-1.50", 1.00, 1.50),
        ("1.50-2.00", 1.50, 2.00),
        ("2.00-3.00", 2.00, 3.00),
        ("3.00-5.00", 3.00, 5.00),
        ("5.00+", 5.00, 100),
    ]

    for label, min_o, max_o in ranges:
        bets_in_range = [b for b in bets_data if min_o <= b[4] < max_o]
        wins = sum(1 for b in bets_in_range if b[5] == "Win")
        total = len(bets_in_range)
        print(f"  {label}: {wins}/{total} wins ({wins/total*100:.1f}% win rate)" if total > 0 else f"  {label}: 0 bets")

if __name__ == "__main__":
    import_bets()
