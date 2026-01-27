"""
Create a seed database with ranked players and match history.
This database ships with the installer for out-of-the-box functionality.
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from database import db


def create_seed_database(output_path: Path = None):
    """
    Create a clean seed database with ranked players and match history.
    Returns the path to the created database.
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent / "dist" / "TennisBettingSystem" / "data" / "tennis_betting.db"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing seed database
    if output_path.exists():
        output_path.unlink()

    # Create fresh database with schema
    seed_conn = sqlite3.connect(output_path)
    seed_conn.row_factory = sqlite3.Row
    seed_cursor = seed_conn.cursor()

    # Create tables
    seed_cursor.executescript('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            country TEXT,
            hand TEXT,
            height INTEGER,
            current_ranking INTEGER,
            peak_ranking INTEGER,
            peak_ranking_date TEXT,
            tour TEXT DEFAULT 'ATP',
            last_ta_update TEXT,
            UNIQUE(name, tour)
        );

        CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY,
            date TEXT,
            tournament TEXT,
            surface TEXT,
            round TEXT,
            winner_id INTEGER,
            winner_name TEXT,
            loser_id INTEGER,
            loser_name TEXT,
            score TEXT,
            tour TEXT,
            tournament_id TEXT,
            tourney_name TEXT,
            sets_won_w INTEGER,
            sets_won_l INTEGER,
            games_won_w INTEGER,
            games_won_l INTEGER,
            minutes INTEGER,
            winner_rank INTEGER,
            loser_rank INTEGER,
            winner_rank_points INTEGER,
            loser_rank_points INTEGER,
            winner_seed INTEGER,
            loser_seed INTEGER,
            best_of INTEGER DEFAULT 3,
            FOREIGN KEY (winner_id) REFERENCES players(id),
            FOREIGN KEY (loser_id) REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS player_aliases (
            alias_id INTEGER PRIMARY KEY,
            canonical_id INTEGER NOT NULL,
            FOREIGN KEY (alias_id) REFERENCES players(id),
            FOREIGN KEY (canonical_id) REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_date TEXT,
            tournament TEXT,
            player1 TEXT,
            player2 TEXT,
            bet_on TEXT,
            odds REAL,
            stake REAL,
            potential_return REAL,
            result TEXT,
            profit_loss REAL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            market TEXT
        );

        CREATE TABLE IF NOT EXISTS upcoming_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament TEXT,
            date TEXT,
            round TEXT,
            surface TEXT,
            player1_id INTEGER,
            player2_id INTEGER,
            player1_name TEXT,
            player2_name TEXT,
            player1_odds REAL,
            player2_odds REAL,
            analyzed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player1_id) REFERENCES players(id),
            FOREIGN KEY (player2_id) REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS injuries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            injury_type TEXT,
            body_part TEXT,
            reported_date TEXT,
            status TEXT DEFAULT 'Active',
            severity TEXT,
            expected_return TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS tournaments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            surface TEXT,
            category TEXT,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            draw_size INTEGER
        );

        CREATE TABLE IF NOT EXISTS player_surface_stats (
            player_id INTEGER NOT NULL,
            surface TEXT NOT NULL,
            matches_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(id),
            PRIMARY KEY (player_id, surface)
        );

        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);
        CREATE INDEX IF NOT EXISTS idx_players_ranking ON players(current_ranking);
        CREATE INDEX IF NOT EXISTS idx_players_tour ON players(tour);
        CREATE INDEX IF NOT EXISTS idx_matches_winner ON matches(winner_id);
        CREATE INDEX IF NOT EXISTS idx_matches_loser ON matches(loser_id);
        CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
    ''')

    # Get ranked players from source database
    with db.get_connection() as source_conn:
        source_cursor = source_conn.cursor()

        # Get all ranked players, fixing NULL tours
        source_cursor.execute('''
            SELECT
                id, name, country, hand, height,
                current_ranking, peak_ranking, peak_ranking_date,
                COALESCE(tour, 'ATP') as tour,
                last_ta_update
            FROM players
            WHERE current_ranking IS NOT NULL
            ORDER BY
                CASE WHEN tour = 'ATP' THEN 0 ELSE 1 END,
                current_ranking
        ''')

        players = source_cursor.fetchall()

    # Insert players with new sequential IDs
    print(f"Inserting {len(players)} ranked players...")

    atp_count = 0
    wta_count = 0

    for i, p in enumerate(players, start=1):
        tour = p['tour'] if p['tour'] else 'ATP'

        seed_cursor.execute('''
            INSERT INTO players (id, name, country, hand, height,
                               current_ranking, peak_ranking, peak_ranking_date, tour, last_ta_update)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (i, p['name'], p['country'], p['hand'], p['height'],
              p['current_ranking'], p['peak_ranking'], p['peak_ranking_date'], tour, p['last_ta_update']))

        if tour == 'ATP':
            atp_count += 1
        else:
            wta_count += 1

    seed_conn.commit()

    # Copy matches from source database
    print("Copying match history...")
    with db.get_connection() as source_conn:
        source_cursor = source_conn.cursor()

        source_cursor.execute('''
            SELECT id, date, tournament, surface, round,
                   winner_id, winner_name, loser_id, loser_name, score,
                   tour, tournament_id, tourney_name,
                   sets_won_w, sets_won_l, games_won_w, games_won_l, minutes,
                   winner_rank, loser_rank, winner_rank_points, loser_rank_points,
                   winner_seed, loser_seed, best_of
            FROM matches
            ORDER BY date DESC
        ''')
        matches = source_cursor.fetchall()

    match_count = 0
    for m in matches:
        try:
            seed_cursor.execute('''
                INSERT INTO matches (id, date, tournament, surface, round,
                                    winner_id, winner_name, loser_id, loser_name, score,
                                    tour, tournament_id, tourney_name,
                                    sets_won_w, sets_won_l, games_won_w, games_won_l, minutes,
                                    winner_rank, loser_rank, winner_rank_points, loser_rank_points,
                                    winner_seed, loser_seed, best_of)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', tuple(m))
            match_count += 1
        except sqlite3.IntegrityError:
            pass  # Skip duplicates

    seed_conn.commit()
    print(f"  Copied {match_count} matches")

    # Get the date range of matches
    seed_cursor.execute("SELECT MIN(date), MAX(date) FROM matches")
    date_range = seed_cursor.fetchone()
    min_date = date_range[0] if date_range else "Unknown"
    max_date = date_range[1] if date_range else "Unknown"

    # Copy player surface stats
    print("Copying player surface stats...")
    with db.get_connection() as source_conn:
        source_cursor = source_conn.cursor()

        source_cursor.execute('''
            SELECT player_id, surface, matches_played, wins, losses, win_rate
            FROM player_surface_stats
        ''')
        stats = source_cursor.fetchall()

    stats_count = 0
    for s in stats:
        try:
            seed_cursor.execute('''
                INSERT INTO player_surface_stats (player_id, surface, matches_played, wins, losses, win_rate)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', tuple(s))
            stats_count += 1
        except sqlite3.IntegrityError:
            pass  # Skip duplicates

    seed_conn.commit()
    print(f"  Copied {stats_count} surface stat records")

    # Add metadata with seed creation timestamp
    seed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    seed_cursor.execute("INSERT INTO metadata (key, value) VALUES (?, ?)",
                       ('seed_created', seed_date))
    seed_cursor.execute("INSERT INTO metadata (key, value) VALUES (?, ?)",
                       ('match_data_from', min_date))
    seed_cursor.execute("INSERT INTO metadata (key, value) VALUES (?, ?)",
                       ('match_data_to', max_date))

    seed_conn.commit()
    seed_conn.close()

    print(f"\n{'='*50}")
    print(f"Seed database created: {output_path}")
    print(f"{'='*50}")
    print(f"  ATP players: {atp_count}")
    print(f"  WTA players: {wta_count}")
    print(f"  Total players: {atp_count + wta_count}")
    print(f"  Matches: {match_count}")
    print(f"  Surface stats: {stats_count}")
    print(f"  Match data: {min_date} to {max_date}")
    print(f"  Seed created: {seed_date}")
    print(f"{'='*50}")

    return output_path


if __name__ == "__main__":
    create_seed_database()
