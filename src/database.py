"""
Tennis Betting System - Database
SQLite schema and CRUD operations

IMPORTANT: All match data is validated before insertion.
See data_validation.py for validation rules.
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from contextlib import contextmanager

from config import DB_PATH, DATA_DIR, KELLY_STAKING, normalize_tournament_name

# Import validation after config to avoid circular imports
_validator = None
def _get_validator():
    global _validator
    if _validator is None:
        try:
            from data_validation import validator
            _validator = validator
        except ImportError:
            _validator = None
    return _validator


class TennisDatabase:
    """SQLite database manager for tennis betting system."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database and tables if they don't exist.

        For installed apps, copies seed files from Program Files
        to Public Documents on first run.
        Uses file locking to prevent race conditions with multiple instances.
        """
        import sys
        import shutil
        import time

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # If frozen, copy seed files from install folder on first run
        if getattr(sys, 'frozen', False):
            lock_file = DATA_DIR / ".seed_copy.lock"

            try:
                from config import INSTALL_DIR
                seed_data_dir = INSTALL_DIR / "data"

                # Use a lock file to prevent race conditions
                # Try to acquire lock with timeout
                lock_acquired = False
                for _ in range(10):  # Try for up to 5 seconds
                    try:
                        # Create lock file exclusively (fails if exists)
                        lock_fd = lock_file.open('x')
                        lock_fd.close()
                        lock_acquired = True
                        break
                    except FileExistsError:
                        # Another instance is copying, wait
                        time.sleep(0.5)

                if not lock_acquired:
                    # Lock file stuck, try to remove stale lock (older than 30s)
                    try:
                        if lock_file.exists():
                            lock_age = time.time() - lock_file.stat().st_mtime
                            if lock_age > 30:
                                lock_file.unlink()
                    except:
                        pass

                try:
                    # Only copy seed database on first install (no existing DB)
                    seed_db = seed_data_dir / "tennis_betting.db"

                    if seed_db.exists() and not self.db_path.exists():
                        shutil.copy2(seed_db, self.db_path)
                        print(f"Copied seed database to {self.db_path}")

                    # Always overwrite name_mappings.json with latest version (reference data, not user data)
                    mappings_dest = DATA_DIR / "name_mappings.json"
                    seed_mappings = seed_data_dir / "name_mappings.json"
                    if seed_mappings.exists():
                        shutil.copy2(seed_mappings, mappings_dest)
                        print(f"Updated name mappings at {mappings_dest}")
                finally:
                    # Release lock
                    try:
                        lock_file.unlink()
                    except:
                        pass

            except Exception as e:
                print(f"Could not copy seed files: {e}")

        self.create_tables()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_tables(self):
        """Create all database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Players table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    country TEXT,
                    hand TEXT,
                    height INTEGER,
                    dob TEXT,
                    current_ranking INTEGER,
                    peak_ranking INTEGER,
                    peak_ranking_date TEXT,
                    last_ta_update TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add columns if they don't exist (migration for existing DBs)
            migrations = [
                "ALTER TABLE players ADD COLUMN last_ta_update TEXT",
                "ALTER TABLE players ADD COLUMN peak_ranking_date TEXT",
                "ALTER TABLE bets ADD COLUMN market TEXT",
                "ALTER TABLE players ADD COLUMN performance_elo REAL",
                "ALTER TABLE players ADD COLUMN performance_rank INTEGER",
                "ALTER TABLE players ADD COLUMN tour TEXT",
            ]
            for migration in migrations:
                try:
                    cursor.execute(migration)
                except:
                    pass  # Column already exists

            # Tournaments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tournaments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    surface TEXT,
                    category TEXT,
                    location TEXT,
                    draw_size INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Matches table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY,
                    tournament_id TEXT,
                    tournament TEXT,
                    date TEXT,
                    round TEXT,
                    surface TEXT,
                    winner_id INTEGER,
                    loser_id INTEGER,
                    score TEXT,
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
                    w_ace INTEGER,
                    w_df INTEGER,
                    w_svpt INTEGER,
                    w_1stIn INTEGER,
                    w_1stWon INTEGER,
                    w_2ndWon INTEGER,
                    w_SvGms INTEGER,
                    w_bpSaved INTEGER,
                    w_bpFaced INTEGER,
                    l_ace INTEGER,
                    l_df INTEGER,
                    l_svpt INTEGER,
                    l_1stIn INTEGER,
                    l_1stWon INTEGER,
                    l_2ndWon INTEGER,
                    l_SvGms INTEGER,
                    l_bpSaved INTEGER,
                    l_bpFaced INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
                    FOREIGN KEY (winner_id) REFERENCES players(id),
                    FOREIGN KEY (loser_id) REFERENCES players(id)
                )
            """)

            # Rankings history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rankings_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    ranking_date TEXT NOT NULL,
                    ranking INTEGER NOT NULL,
                    points INTEGER,
                    FOREIGN KEY (player_id) REFERENCES players(id),
                    UNIQUE(player_id, ranking_date)
                )
            """)

            # Player surface stats (aggregated)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_surface_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER NOT NULL,
                    surface TEXT NOT NULL,
                    matches_played INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    avg_games_won REAL DEFAULT 0.0,
                    avg_games_lost REAL DEFAULT 0.0,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player_id) REFERENCES players(id),
                    UNIQUE(player_id, surface)
                )
            """)

            # Head to head records
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS head_to_head (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player1_id INTEGER NOT NULL,
                    player2_id INTEGER NOT NULL,
                    p1_wins INTEGER DEFAULT 0,
                    p2_wins INTEGER DEFAULT 0,
                    last_match_date TEXT,
                    p1_wins_by_surface TEXT DEFAULT '{}',
                    p2_wins_by_surface TEXT DEFAULT '{}',
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player1_id) REFERENCES players(id),
                    FOREIGN KEY (player2_id) REFERENCES players(id),
                    UNIQUE(player1_id, player2_id)
                )
            """)

            # Injuries tracking
            cursor.execute("""
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
                )
            """)

            # Bets tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_date TEXT NOT NULL,
                    tournament TEXT,
                    match_description TEXT,
                    player1 TEXT,
                    player2 TEXT,
                    market TEXT,
                    selection TEXT NOT NULL,
                    stake REAL NOT NULL,
                    odds REAL NOT NULL,
                    our_probability REAL,
                    implied_probability REAL,
                    ev_at_placement REAL,
                    result TEXT,
                    profit_loss REAL,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    settled_at TEXT
                )
            """)

            # Migrate existing bets table - add ALL possible missing columns
            bets_migrations = [
                "ALTER TABLE bets ADD COLUMN match_date TEXT",
                "ALTER TABLE bets ADD COLUMN tournament TEXT",
                "ALTER TABLE bets ADD COLUMN match_description TEXT",
                "ALTER TABLE bets ADD COLUMN player1 TEXT",
                "ALTER TABLE bets ADD COLUMN player2 TEXT",
                "ALTER TABLE bets ADD COLUMN market TEXT",
                "ALTER TABLE bets ADD COLUMN selection TEXT",
                "ALTER TABLE bets ADD COLUMN stake REAL",
                "ALTER TABLE bets ADD COLUMN odds REAL",
                "ALTER TABLE bets ADD COLUMN our_probability REAL",
                "ALTER TABLE bets ADD COLUMN implied_probability REAL",
                "ALTER TABLE bets ADD COLUMN ev_at_placement REAL",
                "ALTER TABLE bets ADD COLUMN result TEXT",
                "ALTER TABLE bets ADD COLUMN profit_loss REAL",
                "ALTER TABLE bets ADD COLUMN notes TEXT",
                "ALTER TABLE bets ADD COLUMN created_at TEXT",
                "ALTER TABLE bets ADD COLUMN settled_at TEXT",
                "ALTER TABLE bets ADD COLUMN in_progress INTEGER DEFAULT 0",
                "ALTER TABLE bets ADD COLUMN model TEXT",
                "ALTER TABLE bets ADD COLUMN factor_scores TEXT",  # JSON of individual factor scores
                "ALTER TABLE bets ADD COLUMN odds_at_close REAL",  # Closing odds for CLV tracking
                "ALTER TABLE bets ADD COLUMN clv REAL",  # Closing Line Value percentage
                "ALTER TABLE bets ADD COLUMN weighting TEXT",  # Weight profile used for this bet
            ]
            for migration in bets_migrations:
                try:
                    cursor.execute(migration)
                except Exception:
                    pass  # Column already exists

            # Copy date to match_date if match_date is empty
            try:
                cursor.execute("UPDATE bets SET match_date = date WHERE match_date IS NULL AND date IS NOT NULL")
            except Exception:
                pass

            # Upcoming matches (for bet suggestions)
            cursor.execute("""
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
                    player1_liquidity REAL,
                    player2_liquidity REAL,
                    total_matched REAL,
                    analyzed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player1_id) REFERENCES players(id),
                    FOREIGN KEY (player2_id) REFERENCES players(id)
                )
            """)

            # Add liquidity columns to upcoming_matches if missing (migration)
            upcoming_migrations = [
                "ALTER TABLE upcoming_matches ADD COLUMN player1_liquidity REAL",
                "ALTER TABLE upcoming_matches ADD COLUMN player2_liquidity REAL",
                "ALTER TABLE upcoming_matches ADD COLUMN total_matched REAL",
            ]
            for migration in upcoming_migrations:
                try:
                    cursor.execute(migration)
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Player aliases table - maps alternate IDs to canonical IDs
            # The canonical_id should be the ID used by the betting site (from upcoming_matches)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_aliases (
                    alias_id INTEGER PRIMARY KEY,
                    canonical_id INTEGER NOT NULL,
                    source TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (canonical_id) REFERENCES players(id)
                )
            """)

            # App settings table for storing metadata like last refresh time
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Betfair matches table for storing captured match data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS betfair_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT,
                    market_id TEXT,
                    tournament TEXT,
                    match_date TEXT,
                    player1_name TEXT,
                    player2_name TEXT,
                    player1_odds REAL,
                    player2_odds REAL,
                    player1_liquidity REAL,
                    player2_liquidity REAL,
                    total_matched REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance (wrapped in try-except for schema compatibility)
            index_statements = [
                "CREATE INDEX IF NOT EXISTS idx_matches_winner ON matches(winner_id)",
                "CREATE INDEX IF NOT EXISTS idx_matches_loser ON matches(loser_id)",
                "CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date)",
                "CREATE INDEX IF NOT EXISTS idx_matches_surface ON matches(surface)",
                "CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament_id)",
                "CREATE INDEX IF NOT EXISTS idx_rankings_player ON rankings_history(player_id)",
                "CREATE INDEX IF NOT EXISTS idx_rankings_date ON rankings_history(ranking_date)",
                "CREATE INDEX IF NOT EXISTS idx_surface_stats_player ON player_surface_stats(player_id)",
                "CREATE INDEX IF NOT EXISTS idx_h2h_players ON head_to_head(player1_id, player2_id)",
                "CREATE INDEX IF NOT EXISTS idx_bets_date ON bets(match_date)",
                "CREATE INDEX IF NOT EXISTS idx_players_name ON players(name)",
            ]
            for stmt in index_statements:
                try:
                    cursor.execute(stmt)
                except Exception:
                    # Column or table doesn't exist in this schema - skip this index
                    pass

    # =========================================================================
    # PLAYER CRUD
    # =========================================================================

    def insert_player(self, player_data: Dict) -> int:
        """Insert a player into the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO players
                (id, name, first_name, last_name, country, hand, height, dob)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_data.get('id'),
                player_data.get('name'),
                player_data.get('first_name'),
                player_data.get('last_name'),
                player_data.get('country'),
                player_data.get('hand'),
                player_data.get('height'),
                player_data.get('dob'),
            ))
            return cursor.lastrowid

    def insert_players_batch(self, players: List[Dict]):
        """Insert multiple players in batch."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO players
                (id, name, first_name, last_name, country, hand, height, dob)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    p.get('id'),
                    p.get('name'),
                    p.get('first_name'),
                    p.get('last_name'),
                    p.get('country'),
                    p.get('hand'),
                    p.get('height'),
                    p.get('dob'),
                ) for p in players
            ])

    def get_player(self, player_id: int) -> Optional[Dict]:
        """Get a player by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM players WHERE id = ?", (player_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_player_performance_elo(self, player_id: int, performance_elo: float):
        """Update a player's Performance Elo rating."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE players SET performance_elo = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (performance_elo, player_id)
            )

    def get_player_performance_elo(self, player_id: int) -> Optional[float]:
        """Get a player's Performance Elo. Returns None if not calculated."""
        canonical_id = self.get_canonical_id(player_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT performance_elo FROM players WHERE id = ?",
                (canonical_id,)
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
        return None

    def get_player_performance_rank(self, player_id: int) -> Optional[int]:
        """Get a player's Performance Rank (rank by Performance Elo). Returns None if not ranked."""
        canonical_id = self.get_canonical_id(player_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT performance_rank FROM players WHERE id = ?",
                (canonical_id,)
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                return int(row[0])
        return None

    def update_player_tour(self, player_id: int, tour: str):
        """Update a player's tour classification (ATP or WTA)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE players SET tour = ? WHERE id = ?",
                (tour, player_id)
            )

    def update_all_performance_ranks(self):
        """Rank all players by Performance Elo within their tour (highest = rank 1)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Clear all ranks first
            cursor.execute("UPDATE players SET performance_rank = NULL")
            # Assign ranks within each tour separately
            for tour in ('ATP', 'WTA'):
                cursor.execute("""
                    UPDATE players SET performance_rank = (
                        SELECT COUNT(*) + 1
                        FROM players AS p2
                        WHERE p2.performance_elo > players.performance_elo
                        AND p2.tour = ?
                    )
                    WHERE performance_elo IS NOT NULL AND tour = ?
                """, (tour, tour))

    def add_player(self, name: str, ranking: int = None, country: str = None,
                   hand: str = None) -> int:
        """
        Add a new player to the database.
        Returns the new player's ID.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Check if player already exists by name
            cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
            existing = cursor.fetchone()
            if existing:
                return existing[0]

            # Get next available ID (max + 1)
            cursor.execute("SELECT MAX(id) FROM players")
            max_id = cursor.fetchone()[0] or 0
            new_id = max_id + 1

            # Split name into first/last
            parts = name.strip().split()
            first_name = parts[0] if parts else name
            last_name = parts[-1] if len(parts) > 1 else ''

            cursor.execute("""
                INSERT INTO players (id, name, first_name, last_name, current_ranking, country, hand)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (new_id, name, first_name, last_name, ranking, country, hand))

            return new_id

    def get_canonical_id(self, player_id: int) -> int:
        """
        Translate a player ID to its canonical ID.
        The canonical ID is the one used by the betting site (from upcoming_matches).
        If no alias exists, returns the original ID.
        """
        if player_id is None:
            return None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT canonical_id FROM player_aliases WHERE alias_id = ?",
                (player_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else player_id

    def add_player_alias(self, alias_id: int, canonical_id: int, source: str = None):
        """
        Add a player ID alias mapping.
        Maps alias_id -> canonical_id (the betting site's ID).
        """
        if alias_id == canonical_id:
            return  # Don't create self-referential aliases
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO player_aliases (alias_id, canonical_id, source)
                VALUES (?, ?, ?)
            """, (alias_id, canonical_id, source))

    def get_all_player_ids(self, canonical_id: int) -> List[int]:
        """
        Get all IDs (canonical + aliases) for a player.
        Useful for querying matches across all ID variants.
        """
        ids = [canonical_id]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT alias_id FROM player_aliases WHERE canonical_id = ?",
                (canonical_id,)
            )
            ids.extend(row[0] for row in cursor.fetchall())
        return ids

    def get_player_match_count(self, player_id: int) -> int:
        """Get the number of matches for a player (including all ID aliases)."""
        # Get canonical ID and all aliases
        canonical_id = self.get_canonical_id(player_id)
        all_ids = self.get_all_player_ids(canonical_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(all_ids))
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM matches
                WHERE winner_id IN ({placeholders}) OR loser_id IN ({placeholders})
            """, all_ids + all_ids)
            row = cursor.fetchone()
            return row['count'] if row else 0

    def get_player_by_name(self, name: str) -> Optional[Dict]:
        """Get a player by name. Uses multiple matching strategies.

        Prefers real ATP/WTA players (positive IDs with rankings) over auto-created players.
        Uses name_mappings.json for custom name translations.

        IMPORTANT: This function handles different name formats:
        - Betfair: "Frederico Ferreira Silva" (FirstName LastName)
        - Database: "Ferreira Silva Frederico" (LastName FirstName)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Skip doubles players (contain "/")
            if '/' in name:
                return None

            fallback_result = None  # Store auto-created match as fallback

            # Strategy 0: Check name mappings file first
            try:
                from name_matcher import name_matcher
                # Check if there's a direct mapping to a player ID
                mapped_id = name_matcher.get_db_id(name)
                if mapped_id:
                    cursor.execute("SELECT * FROM players WHERE id = ?", (mapped_id,))
                    row = cursor.fetchone()
                    if row:
                        return dict(row)

                # Check if there's a mapping to a different name
                mapped_name = name_matcher.get_db_name(name)
                if mapped_name and mapped_name != name:
                    cursor.execute(
                        """SELECT * FROM players WHERE LOWER(name) = LOWER(?)
                           ORDER BY COALESCE(current_ranking, 999999) ASC LIMIT 1""",
                        (mapped_name,)
                    )
                    row = cursor.fetchone()
                    if row:
                        return dict(row)
            except ImportError:
                pass  # name_matcher not available

            # Normalize name: remove hyphens (Betfair uses "Auger-Aliassime", DB has "Auger Aliassime")
            name_normalized = name.replace('-', ' ').strip()
            parts = name_normalized.split()

            # Strategy 1: Exact match (case-insensitive)
            cursor.execute(
                """SELECT * FROM players WHERE LOWER(name) = LOWER(?)
                   ORDER BY
                       CASE WHEN id > 0 AND current_ranking IS NOT NULL THEN 0 ELSE 1 END,
                       COALESCE(current_ranking, 999999) ASC
                   LIMIT 1""",
                (name_normalized,)
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result['id'] > 0:
                    return result
                fallback_result = result

            # Strategy 2: Try reversed name order (handles DB format "LastName FirstName")
            # For "Frederico Ferreira Silva" try "Ferreira Silva Frederico"
            if len(parts) >= 2:
                # Try moving first name to end: "A B C" -> "B C A"
                reversed_name = ' '.join(parts[1:]) + ' ' + parts[0]
                cursor.execute(
                    """SELECT * FROM players WHERE id > 0 AND LOWER(name) = LOWER(?)
                       ORDER BY COALESCE(current_ranking, 999999) ASC LIMIT 1""",
                    (reversed_name,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

                # Also try full reversal: "A B C" -> "C B A"
                full_reversed = ' '.join(parts[::-1])
                cursor.execute(
                    """SELECT * FROM players WHERE id > 0 AND LOWER(name) = LOWER(?)
                       ORDER BY COALESCE(current_ranking, 999999) ASC LIMIT 1""",
                    (full_reversed,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # Strategy 3: All name parts must be present (in any order)
            # This is safer than partial matching
            if len(parts) >= 2:
                # Build query that requires ALL parts to be in the name
                conditions = ' AND '.join(['LOWER(name) LIKE ?' for _ in parts])
                params = [f'%{p.lower()}%' for p in parts]

                cursor.execute(
                    f"""SELECT * FROM players
                       WHERE id > 0 AND {conditions}
                       ORDER BY COALESCE(current_ranking, 999999) ASC
                       LIMIT 1""",
                    params
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # Strategy 4: First and last name in any order (for 2-part names)
            if len(parts) == 2:
                first, last = parts[0], parts[1]
                # Try both orders with exact word matching
                cursor.execute(
                    """SELECT * FROM players
                       WHERE id > 0 AND (
                           (LOWER(name) LIKE ? AND LOWER(name) LIKE ?) OR
                           LOWER(name) = LOWER(?)
                       )
                       ORDER BY COALESCE(current_ranking, 999999) ASC
                       LIMIT 1""",
                    (f'%{first}%', f'%{last}%', f'{last} {first}')
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # Strategy 5: Fuzzy match using all candidates (last resort)
            # Only for names with 2+ parts, and require high similarity
            if len(parts) >= 2:
                try:
                    from name_matcher import name_matcher
                    from difflib import SequenceMatcher

                    # Get potential candidates - search by each name part
                    candidates = []
                    for part in parts:
                        if len(part) >= 3:  # Only search reasonably long parts
                            cursor.execute(
                                """SELECT id, name, current_ranking FROM players
                                   WHERE id > 0 AND LOWER(name) LIKE ?
                                   ORDER BY COALESCE(current_ranking, 999999) ASC
                                   LIMIT 20""",
                                (f'%{part.lower()}%',)
                            )
                            candidates.extend([dict(r) for r in cursor.fetchall()])

                    # Deduplicate candidates
                    seen = set()
                    unique_candidates = []
                    for c in candidates:
                        if c['id'] not in seen:
                            seen.add(c['id'])
                            unique_candidates.append(c)

                    # Find best fuzzy match with high threshold (0.85)
                    best_match = name_matcher.find_best_match(name, unique_candidates, threshold=0.85)
                    if best_match:
                        cursor.execute("SELECT * FROM players WHERE id = ?", (best_match['id'],))
                        row = cursor.fetchone()
                        if row:
                            return dict(row)
                except ImportError:
                    pass

            # If no real player found, return the auto-created fallback (if any)
            return fallback_result

    def search_players(self, query: str, limit: int = 20) -> List[Dict]:
        """Search players by name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM players WHERE name LIKE ? ORDER BY current_ranking ASC LIMIT ?",
                (f"%{query}%", limit)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_players(self) -> List[Dict]:
        """Get all players."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM players ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def update_player_ranking(self, player_id: int, ranking: int, points: int = None):
        """Update a player's current ranking."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE players
                SET current_ranking = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (ranking, player_id))

            # Update peak ranking if needed
            cursor.execute("""
                UPDATE players
                SET peak_ranking = ?, peak_ranking_date = ?
                WHERE id = ? AND (peak_ranking IS NULL OR ? < peak_ranking)
            """, (ranking, datetime.now().isoformat()[:10], player_id, ranking))

    def update_player_info(self, player_id: int, info: Dict):
        """Update player profile information (country, hand, height, dob)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []

            if info.get('country'):
                updates.append("country = ?")
                params.append(info['country'])
            if info.get('hand'):
                updates.append("hand = ?")
                params.append(info['hand'])
            if info.get('height'):
                updates.append("height = ?")
                params.append(info['height'])
            if info.get('dob'):
                updates.append("dob = ?")
                params.append(info['dob'])

            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(player_id)
                cursor.execute(f"""
                    UPDATE players
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)

    def update_player_ta_timestamp(self, player_id: int):
        """Update the last Tennis Abstract update timestamp for a player."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE players
                SET last_ta_update = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), player_id))

    def player_needs_ta_update(self, player_id: int, hours: int = 6) -> bool:
        """Check if a player needs updating (not updated in last N hours)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_ta_update FROM players WHERE id = ?", (player_id,))
            row = cursor.fetchone()

            if not row or not row['last_ta_update']:
                return True  # Never updated

            try:
                last_update = datetime.fromisoformat(row['last_ta_update'])
                hours_since = (datetime.now() - last_update).total_seconds() / 3600
                return hours_since >= hours
            except:
                return True  # Invalid timestamp, needs update

    # =========================================================================
    # TOURNAMENT CRUD
    # =========================================================================

    def insert_tournament(self, tournament_data: Dict) -> str:
        """Insert a tournament into the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tournaments
                (id, name, surface, category, location, draw_size)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                tournament_data.get('id'),
                tournament_data.get('name'),
                tournament_data.get('surface'),
                tournament_data.get('category'),
                tournament_data.get('location'),
                tournament_data.get('draw_size'),
            ))
            return tournament_data.get('id')

    def get_tournament(self, tournament_id: str) -> Optional[Dict]:
        """Get a tournament by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def sync_tournament_names(self) -> Dict[str, int]:
        """
        Sync tournament names across all tables to use consistent Betfair naming.

        Applies these transformations:
        - Capitalize 'challenger' to 'Challenger'
        - Move 'ITF' from suffix to prefix ('Location ITF' -> 'ITF Location')
        - Strip year suffixes (2024, 2025, 2026, etc.)
        - Remove Grand Slam prefixes (Ladies/Men's/Women's)
        - Merge numbered tournaments ('Antalya 5 ITF' -> 'ITF Antalya')

        Returns:
            Dict with counts of updates per table
        """
        import re

        results = {'matches': 0, 'bets': 0, 'upcoming_matches': 0}

        with self.get_connection() as conn:
            cursor = conn.cursor()

            for table in ['matches', 'bets', 'upcoming_matches']:
                # Get all unique tournament names
                try:
                    cursor.execute(f'SELECT DISTINCT tournament FROM {table}')
                    tournaments = [row[0] for row in cursor.fetchall() if row[0]]
                except:
                    continue

                for old_name in tournaments:
                    new_name = old_name

                    # 1. Strip year suffixes (2020-2039)
                    new_name = re.sub(r'\s+20[2-3]\d$', '', new_name)

                    # 2. Remove Grand Slam prefixes
                    new_name = re.sub(r"^Ladies\s+", "", new_name)
                    new_name = re.sub(r"^Men's\s+", "", new_name)
                    new_name = re.sub(r"^Women's\s+", "", new_name)

                    # 3. Capitalize 'challenger'
                    new_name = re.sub(r'\bchallenger\b', 'Challenger', new_name, flags=re.IGNORECASE)

                    # 4. Move ITF from suffix to prefix
                    if re.search(r'\sITF$', new_name):
                        location = re.sub(r'\s+ITF$', '', new_name)
                        new_name = f'ITF {location}'

                    # 5. Merge numbered tournaments ('Antalya 5 ITF' -> 'ITF Antalya')
                    # Pattern: 'Location N ITF/Challenger/WTA' where N is a number
                    match = re.match(r'^(.+?)\s+\d{1,2}\s+(ITF|Challenger|WTA|ATP)$', new_name, re.IGNORECASE)
                    if match:
                        location = match.group(1)
                        level = match.group(2)
                        if level.upper() == 'ITF':
                            new_name = f'ITF {location}'
                        else:
                            new_name = f'{location} {level}'

                    # Also handle 'ITF Location N' format
                    match = re.match(r'^ITF\s+(.+?)\s+\d{1,2}$', new_name)
                    if match:
                        location = match.group(1)
                        new_name = f'ITF {location}'

                    new_name = new_name.strip()

                    # Update if changed
                    if old_name != new_name:
                        cursor.execute(f'UPDATE {table} SET tournament = ? WHERE tournament = ?',
                                      (new_name, old_name))
                        results[table] += cursor.rowcount

            conn.commit()

        return results

    # =========================================================================
    # MATCH CRUD
    # =========================================================================

    def insert_match(self, match_data: Dict, source: str = "unknown",
                     validate: bool = True) -> Optional[str]:
        """
        Insert a match into the database.

        Args:
            match_data: Dictionary containing match data
            source: Source of the data (for logging validation failures)
            validate: Whether to validate data before insertion (default True)

        Returns:
            Match ID if successful, None if validation failed
        """
        # Validate data before insertion
        if validate:
            validator = _get_validator()
            if validator:
                is_valid, errors = validator.validate_match(match_data, source)
                if not is_valid:
                    # Log and reject invalid data
                    print(f"[VALIDATION FAILED] {source}: {errors}")
                    return None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO matches
                (id, tournament_id, tournament, date, round, surface,
                 winner_id, loser_id, score, sets_won_w, sets_won_l,
                 games_won_w, games_won_l, minutes, winner_rank, loser_rank,
                 winner_rank_points, loser_rank_points, winner_seed, loser_seed, best_of,
                 w_ace, w_df, w_svpt, w_1stIn, w_1stWon, w_2ndWon, w_SvGms, w_bpSaved, w_bpFaced,
                 l_ace, l_df, l_svpt, l_1stIn, l_1stWon, l_2ndWon, l_SvGms, l_bpSaved, l_bpFaced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_data.get('id'),
                match_data.get('tournament_id'),
                match_data.get('tourney_name') or match_data.get('tournament'),
                match_data.get('date'),
                match_data.get('round'),
                match_data.get('surface'),
                match_data.get('winner_id'),
                match_data.get('loser_id'),
                match_data.get('score'),
                match_data.get('sets_won_w'),
                match_data.get('sets_won_l'),
                match_data.get('games_won_w'),
                match_data.get('games_won_l'),
                match_data.get('minutes'),
                match_data.get('winner_rank'),
                match_data.get('loser_rank'),
                match_data.get('winner_rank_points'),
                match_data.get('loser_rank_points'),
                match_data.get('winner_seed'),
                match_data.get('loser_seed'),
                match_data.get('best_of', 3),
                match_data.get('w_ace'),
                match_data.get('w_df'),
                match_data.get('w_svpt'),
                match_data.get('w_1stIn'),
                match_data.get('w_1stWon'),
                match_data.get('w_2ndWon'),
                match_data.get('w_SvGms'),
                match_data.get('w_bpSaved'),
                match_data.get('w_bpFaced'),
                match_data.get('l_ace'),
                match_data.get('l_df'),
                match_data.get('l_svpt'),
                match_data.get('l_1stIn'),
                match_data.get('l_1stWon'),
                match_data.get('l_2ndWon'),
                match_data.get('l_SvGms'),
                match_data.get('l_bpSaved'),
                match_data.get('l_bpFaced'),
            ))
            return match_data.get('id')

    def insert_matches_batch(self, matches: List[Dict], source: str = "unknown",
                              validate: bool = True) -> Tuple[int, int]:
        """
        Insert multiple matches in batch.

        Args:
            matches: List of match data dictionaries
            source: Source of the data (for logging validation failures)
            validate: Whether to validate data before insertion (default True)

        Returns:
            Tuple of (inserted_count, rejected_count)
        """
        # Filter out invalid matches if validation is enabled
        valid_matches = []
        rejected_count = 0

        if validate:
            validator = _get_validator()
            if validator:
                for match in matches:
                    is_valid, errors = validator.validate_match(match, source)
                    if is_valid:
                        valid_matches.append(match)
                    else:
                        rejected_count += 1
            else:
                valid_matches = matches
        else:
            valid_matches = matches

        if not valid_matches:
            return 0, rejected_count

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO matches
                (id, tournament_id, tournament, date, round, surface,
                 winner_id, loser_id, score, sets_won_w, sets_won_l,
                 games_won_w, games_won_l, minutes, winner_rank, loser_rank,
                 winner_rank_points, loser_rank_points, winner_seed, loser_seed, best_of,
                 w_ace, w_df, w_svpt, w_1stIn, w_1stWon, w_2ndWon, w_SvGms, w_bpSaved, w_bpFaced,
                 l_ace, l_df, l_svpt, l_1stIn, l_1stWon, l_2ndWon, l_SvGms, l_bpSaved, l_bpFaced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    m.get('id'),
                    m.get('tournament_id'),
                    m.get('tourney_name') or m.get('tournament'),
                    m.get('date'),
                    m.get('round'),
                    m.get('surface'),
                    m.get('winner_id'),
                    m.get('loser_id'),
                    m.get('score'),
                    m.get('sets_won_w'),
                    m.get('sets_won_l'),
                    m.get('games_won_w'),
                    m.get('games_won_l'),
                    m.get('minutes'),
                    m.get('winner_rank'),
                    m.get('loser_rank'),
                    m.get('winner_rank_points'),
                    m.get('loser_rank_points'),
                    m.get('winner_seed'),
                    m.get('loser_seed'),
                    m.get('best_of', 3),
                    m.get('w_ace'),
                    m.get('w_df'),
                    m.get('w_svpt'),
                    m.get('w_1stIn'),
                    m.get('w_1stWon'),
                    m.get('w_2ndWon'),
                    m.get('w_SvGms'),
                    m.get('w_bpSaved'),
                    m.get('w_bpFaced'),
                    m.get('l_ace'),
                    m.get('l_df'),
                    m.get('l_svpt'),
                    m.get('l_1stIn'),
                    m.get('l_1stWon'),
                    m.get('l_2ndWon'),
                    m.get('l_SvGms'),
                    m.get('l_bpSaved'),
                    m.get('l_bpFaced'),
                ) for m in valid_matches
            ])

        return len(valid_matches), rejected_count

    def get_player_matches(self, player_id: int, limit: int = None,
                           surface: str = None, since_date: str = None) -> List[Dict]:
        """Get matches for a player (including all ID aliases)."""
        # Get canonical ID and all aliases
        canonical_id = self.get_canonical_id(player_id)
        all_ids = self.get_all_player_ids(canonical_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(all_ids))
            query = f"""
                SELECT * FROM matches
                WHERE (winner_id IN ({placeholders}) OR loser_id IN ({placeholders}))
            """
            params = all_ids + all_ids

            if surface:
                query += " AND surface = ?"
                params.append(surface)

            if since_date:
                query += " AND date >= ?"
                params.append(since_date)

            query += " ORDER BY date DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_most_recent_match_date(self) -> str:
        """Get the most recent match date from the last month with comprehensive data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Find the most recent month with at least 50 matches (comprehensive data)
            cursor.execute("""
                SELECT substr(date, 1, 7) as month, MAX(date) as max_date, COUNT(*) as count
                FROM matches
                GROUP BY month
                HAVING count >= 50
                ORDER BY month DESC
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result and result['max_date']:
                return result['max_date'][:10]  # Return date portion only
            # Fallback: just get max date
            cursor.execute("SELECT MAX(date) as max_date FROM matches")
            result = cursor.fetchone()
            if result and result['max_date']:
                return result['max_date'][:10]
            return None

    def get_recent_matches(self, days: int = 3) -> List[Dict]:
        """Get matches from the last N days with player names."""
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*,
                       w.name as winner_name,
                       l.name as loser_name
                FROM matches m
                LEFT JOIN players w ON m.winner_id = w.id
                LEFT JOIN players l ON m.loser_id = l.id
                WHERE m.date >= ?
                ORDER BY m.date DESC
            """, (cutoff_date,))
            return [dict(row) for row in cursor.fetchall()]

    def get_h2h_matches(self, player1_id: int, player2_id: int) -> List[Dict]:
        """Get head-to-head matches between two players."""
        if player1_id is None or player2_id is None:
            return []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matches
                WHERE (winner_id = ? AND loser_id = ?)
                   OR (winner_id = ? AND loser_id = ?)
                ORDER BY date DESC
            """, (player1_id, player2_id, player2_id, player1_id))
            return [dict(row) for row in cursor.fetchall()]

    def get_match_count(self) -> int:
        """Get total number of matches in database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM matches")
            return cursor.fetchone()[0]

    # =========================================================================
    # RANKINGS HISTORY
    # =========================================================================

    def insert_ranking(self, player_id: int, ranking_date: str, ranking: int, points: int = None):
        """Insert a ranking record."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO rankings_history
                (player_id, ranking_date, ranking, points)
                VALUES (?, ?, ?, ?)
            """, (player_id, ranking_date, ranking, points))

    def insert_rankings_batch(self, rankings: List[Tuple]):
        """Insert multiple rankings in batch."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO rankings_history
                (player_id, ranking_date, ranking, points)
                VALUES (?, ?, ?, ?)
            """, rankings)

    def get_player_ranking_history(self, player_id: int, limit: int = 52) -> List[Dict]:
        """Get ranking history for a player."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM rankings_history
                WHERE player_id = ?
                ORDER BY ranking_date DESC
                LIMIT ?
            """, (player_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_ranking(self, player_id: int) -> Optional[Dict]:
        """Get the most recent ranking for a player."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM rankings_history
                WHERE player_id = ?
                ORDER BY ranking_date DESC
                LIMIT 1
            """, (player_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # =========================================================================
    # HEAD TO HEAD
    # =========================================================================

    def update_h2h(self, player1_id: int, player2_id: int):
        """Update head-to-head record from match history."""
        # Handle None player IDs
        if player1_id is None or player2_id is None:
            return

        # Ensure consistent ordering (smaller ID first)
        if player1_id > player2_id:
            player1_id, player2_id = player2_id, player1_id

        matches = self.get_h2h_matches(player1_id, player2_id)

        p1_wins = 0
        p2_wins = 0
        p1_wins_surface = {}
        p2_wins_surface = {}
        last_match_date = None

        for match in matches:
            surface = match.get('surface', 'Unknown')
            if last_match_date is None:
                last_match_date = match.get('date')

            if match['winner_id'] == player1_id:
                p1_wins += 1
                p1_wins_surface[surface] = p1_wins_surface.get(surface, 0) + 1
            else:
                p2_wins += 1
                p2_wins_surface[surface] = p2_wins_surface.get(surface, 0) + 1

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO head_to_head
                (player1_id, player2_id, p1_wins, p2_wins, last_match_date,
                 p1_wins_by_surface, p2_wins_by_surface, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                player1_id, player2_id, p1_wins, p2_wins, last_match_date,
                json.dumps(p1_wins_surface), json.dumps(p2_wins_surface)
            ))

    def get_h2h(self, player1_id: int, player2_id: int) -> Optional[Dict]:
        """Get head-to-head record between two players."""
        # Handle None player IDs
        if player1_id is None or player2_id is None:
            return None

        # Ensure consistent ordering
        if player1_id > player2_id:
            player1_id, player2_id = player2_id, player1_id
            swapped = True
        else:
            swapped = False

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM head_to_head
                WHERE player1_id = ? AND player2_id = ?
            """, (player1_id, player2_id))
            row = cursor.fetchone()

            if row:
                result = dict(row)
                result['p1_wins_by_surface'] = json.loads(result.get('p1_wins_by_surface', '{}'))
                result['p2_wins_by_surface'] = json.loads(result.get('p2_wins_by_surface', '{}'))

                if swapped:
                    # Swap the results back
                    result['p1_wins'], result['p2_wins'] = result['p2_wins'], result['p1_wins']
                    result['p1_wins_by_surface'], result['p2_wins_by_surface'] = \
                        result['p2_wins_by_surface'], result['p1_wins_by_surface']

                return result
            return None

    # =========================================================================
    # SURFACE STATS
    # =========================================================================

    def update_surface_stats(self, player_id: int):
        """Update aggregated surface stats for a player."""
        surfaces = ['Hard', 'Clay', 'Grass', 'Carpet']

        with self.get_connection() as conn:
            cursor = conn.cursor()

            for surface in surfaces:
                cursor.execute("""
                    SELECT
                        COUNT(*) as matches,
                        SUM(CASE WHEN winner_id = ? THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN loser_id = ? THEN 1 ELSE 0 END) as losses,
                        AVG(CASE WHEN winner_id = ? THEN games_won_w
                                 WHEN loser_id = ? THEN games_won_l END) as avg_games_won,
                        AVG(CASE WHEN winner_id = ? THEN games_won_l
                                 WHEN loser_id = ? THEN games_won_w END) as avg_games_lost
                    FROM matches
                    WHERE (winner_id = ? OR loser_id = ?) AND surface = ?
                """, (player_id, player_id, player_id, player_id,
                      player_id, player_id, player_id, player_id, surface))

                row = cursor.fetchone()
                matches = row[0] or 0
                wins = row[1] or 0
                losses = row[2] or 0
                avg_games_won = row[3] or 0
                avg_games_lost = row[4] or 0
                win_rate = wins / matches if matches > 0 else 0

                if matches > 0:
                    cursor.execute("""
                        INSERT OR REPLACE INTO player_surface_stats
                        (player_id, surface, matches_played, wins, losses,
                         win_rate, avg_games_won, avg_games_lost, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (player_id, surface, matches, wins, losses,
                          win_rate, avg_games_won, avg_games_lost))

    def get_surface_stats(self, player_id: int, surface: str = None) -> List[Dict]:
        """Get surface stats for a player."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if surface:
                cursor.execute("""
                    SELECT * FROM player_surface_stats
                    WHERE player_id = ? AND surface = ?
                """, (player_id, surface))
            else:
                cursor.execute("""
                    SELECT * FROM player_surface_stats
                    WHERE player_id = ?
                """, (player_id,))
            return [dict(row) for row in cursor.fetchall()]

    def recalculate_all_surface_stats(self) -> int:
        """Recalculate surface stats for all players from match data.
        Returns the number of stats updated."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Clear existing stats
            cursor.execute("DELETE FROM player_surface_stats")

            # Recalculate from matches
            cursor.execute("""
                INSERT INTO player_surface_stats (player_id, surface, matches_played, wins, losses, win_rate)
                SELECT
                    player_id,
                    surface,
                    COUNT(*) as matches_played,
                    SUM(won) as wins,
                    SUM(1 - won) as losses,
                    ROUND(CAST(SUM(won) AS FLOAT) / COUNT(*), 3) as win_rate
                FROM (
                    SELECT winner_id as player_id, surface, 1 as won
                    FROM matches WHERE surface IS NOT NULL
                    UNION ALL
                    SELECT loser_id as player_id, surface, 0 as won
                    FROM matches WHERE surface IS NOT NULL
                )
                WHERE player_id IS NOT NULL
                GROUP BY player_id, surface
            """)

            cursor.execute("SELECT COUNT(*) FROM player_surface_stats")
            return cursor.fetchone()[0]

    # =========================================================================
    # INJURIES
    # =========================================================================

    def add_injury(self, player_id: int, injury_type: str, body_part: str = None,
                   status: str = "Active", notes: str = None) -> int:
        """Add an injury record for a player."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO injuries
                (player_id, injury_type, body_part, reported_date, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (player_id, injury_type, body_part,
                  datetime.now().isoformat()[:10], status, notes))
            return cursor.lastrowid

    def get_player_injuries(self, player_id: int, active_only: bool = True) -> List[Dict]:
        """Get injuries for a player."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("""
                    SELECT * FROM injuries
                    WHERE player_id = ? AND status != 'Active'
                    ORDER BY reported_date DESC
                """, (player_id,))
            else:
                cursor.execute("""
                    SELECT * FROM injuries
                    WHERE player_id = ?
                    ORDER BY reported_date DESC
                """, (player_id,))
            return [dict(row) for row in cursor.fetchall()]

    def update_injury_status(self, injury_id: int, status: str, notes: str = None):
        """Update an injury status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE injuries
                SET status = ?, notes = COALESCE(?, notes), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, notes, injury_id))

    # =========================================================================
    # BETS
    # =========================================================================

    def add_bet(self, bet_data: Dict) -> int:
        """Add a bet record."""
        # Normalize tournament name to strip year suffixes (e.g., "2026")
        tournament = bet_data.get('tournament', '')
        if tournament:
            tournament = normalize_tournament_name(tournament)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bets
                (match_date, tournament, match_description, player1, player2, market,
                 selection, stake, odds, our_probability, implied_probability,
                 ev_at_placement, notes, model, factor_scores, weighting)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bet_data.get('match_date', datetime.now().isoformat()[:10]),
                tournament,
                bet_data.get('match_description'),
                bet_data.get('player1'),
                bet_data.get('player2'),
                bet_data.get('market'),
                bet_data.get('selection'),
                bet_data.get('stake'),
                bet_data.get('odds'),
                bet_data.get('our_probability'),
                bet_data.get('implied_probability'),
                bet_data.get('ev_at_placement'),
                bet_data.get('notes'),
                bet_data.get('model'),
                bet_data.get('factor_scores'),  # JSON string of factor scores
                bet_data.get('weighting'),  # Weight profile used
            ))
            return cursor.lastrowid

    def settle_bet(self, bet_id: int, result: str, profit_loss: float):
        """Settle a bet with result and profit/loss."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE bets
                SET result = ?, profit_loss = ?, settled_at = CURRENT_TIMESTAMP, in_progress = 0
                WHERE id = ?
            """, (result, profit_loss, bet_id))

    def delete_bet(self, bet_id: int):
        """Delete a bet by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bets WHERE id = ?", (bet_id,))

    def get_pending_bets(self) -> List[Dict]:
        """Get all unsettled bets."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM bets
                WHERE result IS NULL
                ORDER BY match_date DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_all_bets(self, limit: int = None) -> List[Dict]:
        """Get all bets. No limit by default."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if limit:
                cursor.execute("""
                    SELECT * FROM bets
                    ORDER BY match_date DESC
                    LIMIT ?
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT * FROM bets
                    ORDER BY match_date DESC
                """)
            return [dict(row) for row in cursor.fetchall()]

    def get_bet_by_id(self, bet_id: int) -> Optional[Dict]:
        """Get a single bet by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bets WHERE id = ?", (bet_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def check_duplicate_bet(self, match_description: str, selection: str, match_date: str = None, tournament: str = None, weighting: str = None) -> Optional[Dict]:
        """Check if a bet with the same tournament, match, selection, and weighting already exists.

        Returns the existing bet if found, None otherwise.
        Checks ALL bets (not just pending) to avoid duplicates for played matches.
        When weighting is provided, includes it in the uniqueness check (allows same match with different profiles).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build query based on available parameters
            if tournament and weighting:
                # Most precise: tournament + match + selection + weighting
                cursor.execute("""
                    SELECT * FROM bets
                    WHERE tournament = ? AND match_description = ? AND selection = ? AND weighting = ?
                    LIMIT 1
                """, (tournament, match_description, selection, weighting))
            elif tournament:
                # Tournament + match + selection (no weighting - legacy check)
                cursor.execute("""
                    SELECT * FROM bets
                    WHERE tournament = ? AND match_description = ? AND selection = ?
                    LIMIT 1
                """, (tournament, match_description, selection))
            elif match_date:
                # Match + selection + date (legacy behavior)
                cursor.execute("""
                    SELECT * FROM bets
                    WHERE match_description = ? AND selection = ? AND match_date LIKE ?
                    LIMIT 1
                """, (match_description, selection, match_date[:10] + '%'))
            else:
                # Fallback to original behavior
                cursor.execute("""
                    SELECT * FROM bets
                    WHERE match_description = ? AND selection = ? AND result IS NULL
                    LIMIT 1
                """, (match_description, selection))
            row = cursor.fetchone()
            return dict(row) if row else None

    def check_match_already_bet(self, match_description: str, tournament: str = None) -> Optional[Dict]:
        """Check if ANY bet exists for the same match (regardless of which player was selected).

        This prevents betting on both sides of the same match.
        Returns the existing bet if found, None otherwise.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if tournament:
                # Check by tournament + match description
                cursor.execute("""
                    SELECT * FROM bets
                    WHERE tournament = ? AND match_description = ?
                    LIMIT 1
                """, (tournament, match_description))
            else:
                # Fallback to just match description
                cursor.execute("""
                    SELECT * FROM bets
                    WHERE match_description = ?
                    LIMIT 1
                """, (match_description,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def update_bet(self, bet_id: int, bet_data: Dict):
        """Update an existing bet."""
        # Normalize tournament name to strip year suffixes (e.g., "2026")
        tournament = bet_data.get('tournament', '')
        if tournament:
            tournament = normalize_tournament_name(tournament)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # First, get the current result to recalculate profit_loss if needed
            cursor.execute("SELECT result FROM bets WHERE id = ?", (bet_id,))
            row = cursor.fetchone()
            current_result = row[0] if row else None

            # Calculate new profit_loss if bet is already settled
            profit_loss = None
            stake = bet_data.get('stake')
            odds = bet_data.get('odds')
            commission = KELLY_STAKING.get('exchange_commission', 0.05)

            if current_result and stake and odds:
                if current_result == 'Win':
                    # Apply Betfair commission to winnings
                    gross_profit = stake * (odds - 1)
                    profit_loss = gross_profit * (1 - commission)
                elif current_result == 'Loss':
                    profit_loss = -stake
                elif current_result == 'Void':
                    profit_loss = 0

            cursor.execute("""
                UPDATE bets SET
                    match_date = ?,
                    tournament = ?,
                    match_description = ?,
                    player1 = ?,
                    player2 = ?,
                    market = ?,
                    selection = ?,
                    stake = ?,
                    odds = ?,
                    our_probability = ?,
                    notes = ?,
                    profit_loss = COALESCE(?, profit_loss)
                WHERE id = ?
            """, (
                bet_data.get('match_date'),
                tournament,
                bet_data.get('match_description'),
                bet_data.get('player1'),
                bet_data.get('player2'),
                bet_data.get('market'),
                bet_data.get('selection'),
                stake,
                odds,
                bet_data.get('our_probability'),
                bet_data.get('notes'),
                profit_loss,
                bet_id
            ))

    def set_bet_in_progress(self, bet_id: int, in_progress: bool):
        """Set whether a bet is currently in progress (match is live)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE bets SET in_progress = ? WHERE id = ?",
                (1 if in_progress else 0, bet_id)
            )

    def update_closing_odds(self, bet_id: int, closing_odds: float) -> float:
        """
        Update the closing odds for a bet and calculate CLV.

        CLV (Closing Line Value) measures edge vs the closing line:
        CLV% = ((1/closing_odds) - (1/placement_odds)) / (1/placement_odds) * 100

        Positive CLV = you beat the closing line (got better odds)
        Negative CLV = closing line was better than your odds

        Returns the calculated CLV percentage.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get the placement odds
            cursor.execute("SELECT odds FROM bets WHERE id = ?", (bet_id,))
            row = cursor.fetchone()
            if not row or not row[0]:
                return None

            placement_odds = row[0]

            # Calculate CLV
            # implied_prob_at_placement = 1 / placement_odds
            # implied_prob_at_close = 1 / closing_odds
            # CLV = (close_prob - placement_prob) / placement_prob * 100
            if closing_odds and closing_odds > 0 and placement_odds > 0:
                placement_prob = 1 / placement_odds
                closing_prob = 1 / closing_odds
                clv = ((closing_prob - placement_prob) / placement_prob) * 100
            else:
                clv = None

            # Update the bet
            cursor.execute("""
                UPDATE bets
                SET odds_at_close = ?, clv = ?
                WHERE id = ?
            """, (closing_odds, clv, bet_id))

            return clv

    def get_clv_stats(self) -> Dict:
        """
        Get CLV statistics for settled bets that have closing odds recorded.

        Returns dict with:
        - avg_clv: Average CLV percentage across all bets with CLV data
        - positive_clv_pct: Percentage of bets that beat the closing line
        - total_with_clv: Number of bets with CLV data
        - clv_by_result: Average CLV for wins vs losses
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    AVG(clv) as avg_clv,
                    SUM(CASE WHEN clv > 0 THEN 1 ELSE 0 END) as positive_clv_count,
                    AVG(CASE WHEN result = 'Win' THEN clv END) as avg_clv_wins,
                    AVG(CASE WHEN result = 'Loss' THEN clv END) as avg_clv_losses
                FROM bets
                WHERE clv IS NOT NULL AND result IN ('Win', 'Loss')
            """)
            row = cursor.fetchone()

            total = row[0] or 0

            return {
                'total_with_clv': total,
                'avg_clv': row[1] if row[1] else 0,
                'positive_clv_pct': (row[2] / total * 100) if total > 0 else 0,
                'avg_clv_wins': row[3] if row[3] else 0,
                'avg_clv_losses': row[4] if row[4] else 0,
            }

    def sync_pending_bet_dates(self) -> int:
        """Sync pending bet dates from upcoming_matches and betfair_matches.

        Matches are found by tournament + player names (fuzzy matching).
        If a match is found and the date differs, the bet's match_date is updated.

        Returns the number of bets updated.
        """
        updated_count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get all pending bets
            cursor.execute("""
                SELECT id, player1, player2, match_date, tournament, match_description
                FROM bets
                WHERE result IS NULL
            """)
            pending_bets = cursor.fetchall()

            for bet in pending_bets:
                bet_id, player1, player2, current_date, tournament, match_desc = bet

                # Extract player names from match_description if not set
                if (not player1 or not player2) and match_desc:
                    for sep in [' vs ', ' v ', ' - ', ' VS ', ' V ']:
                        if sep in match_desc:
                            parts = match_desc.split(sep, 1)
                            if len(parts) == 2:
                                player1 = parts[0].strip()
                                player2 = parts[1].strip()
                                break

                if not player1 or not player2:
                    continue

                new_date = None

                # First try betfair_matches (most accurate for live/upcoming)
                cursor.execute("""
                    SELECT match_date FROM betfair_matches
                    WHERE (
                        (player1_name LIKE ? AND player2_name LIKE ?)
                        OR (player1_name LIKE ? AND player2_name LIKE ?)
                    )
                    ORDER BY match_date DESC
                    LIMIT 1
                """, (f'%{player1}%', f'%{player2}%', f'%{player2}%', f'%{player1}%'))

                match = cursor.fetchone()
                if match and match[0]:
                    new_date = match[0]

                # Fallback to upcoming_matches if not found
                if not new_date:
                    cursor.execute("""
                        SELECT date FROM upcoming_matches
                        WHERE (
                            (player1_name LIKE ? AND player2_name LIKE ?)
                            OR (player1_name LIKE ? AND player2_name LIKE ?)
                        )
                        LIMIT 1
                    """, (f'%{player1}%', f'%{player2}%', f'%{player2}%', f'%{player1}%'))

                    match = cursor.fetchone()
                    if match and match[0]:
                        new_date = match[0]

                # Update if we found a date and it differs
                if new_date and new_date != current_date:
                    cursor.execute(
                        "UPDATE bets SET match_date = ? WHERE id = ?",
                        (new_date, bet_id)
                    )
                    updated_count += 1

            conn.commit()

        return updated_count

    def backfill_model_tags(self) -> int:
        """Backfill model tags for bets that are missing them.

        Uses the calculate_bet_model function from config to determine
        which models each bet qualifies for based on probability, edge, and odds.

        Returns the number of bets updated.
        """
        from config import calculate_bet_model

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Find bets with NULL model
            cursor.execute("""
                SELECT id, our_probability, implied_probability, tournament, odds
                FROM bets
                WHERE model IS NULL
            """)
            bets_to_update = cursor.fetchall()

            if not bets_to_update:
                return 0

            updated_count = 0
            for bet in bets_to_update:
                bet_id = bet[0]
                our_prob = bet[1]
                impl_prob = bet[2]
                tournament = bet[3]
                odds = bet[4]

                # Calculate implied probability from odds if missing
                if impl_prob is None and odds and odds > 0:
                    impl_prob = 1.0 / odds

                # If our_probability is missing, estimate from odds (assume slight edge)
                if our_prob is None and odds and odds > 0:
                    impl_prob = 1.0 / odds
                    our_prob = min(0.95, impl_prob + 0.05)  # Assume 5% edge

                # Skip only if we still don't have probability data after estimation
                if our_prob is None or impl_prob is None:
                    continue

                # Calculate model tags
                model_tags = calculate_bet_model(our_prob, impl_prob, tournament, odds)

                # Update the bet
                cursor.execute(
                    "UPDATE bets SET model = ? WHERE id = ?",
                    (model_tags, bet_id)
                )
                updated_count += 1

            conn.commit()
            return updated_count

    def get_betting_stats(self) -> Dict:
        """Get overall betting statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_bets,
                    SUM(CASE WHEN result = 'Win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'Loss' THEN 1 ELSE 0 END) as losses,
                    SUM(stake) as total_staked,
                    SUM(COALESCE(profit_loss, 0)) as total_profit,
                    AVG(odds) as avg_odds
                FROM bets
            """)
            row = cursor.fetchone()

            total_staked = row[3] or 0
            total_profit = row[4] or 0

            wins = row[1] or 0
            losses = row[2] or 0
            settled = wins + losses

            return {
                'total_bets': row[0] or 0,
                'wins': wins,
                'losses': losses,
                'total_staked': total_staked,
                'total_profit': total_profit,
                'roi': (total_profit / total_staked * 100) if total_staked > 0 else 0,
                'avg_odds': row[5] or 0,
                'win_rate': (wins / settled * 100) if settled > 0 else 0,
            }

    # =========================================================================
    # UPCOMING MATCHES
    # =========================================================================

    def add_upcoming_match(self, match_data: Dict) -> int:
        """Add an upcoming match for analysis. Updates if match already exists."""
        # Normalize tournament name to strip year suffixes (e.g., "2026")
        tournament = match_data.get('tournament', '')
        if tournament:
            tournament = normalize_tournament_name(tournament)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Check if match already exists (same players and tournament)
            cursor.execute("""
                SELECT id FROM upcoming_matches
                WHERE player1_name = ? AND player2_name = ? AND tournament = ?
            """, (
                match_data.get('player1_name'),
                match_data.get('player2_name'),
                tournament,
            ))
            existing = cursor.fetchone()

            if existing:
                # Update existing match with new odds and liquidity
                # Reset analyzed=0 so match will be re-analyzed with new odds
                cursor.execute("""
                    UPDATE upcoming_matches
                    SET player1_odds = ?, player2_odds = ?, tournament = ?, surface = ?,
                        player1_liquidity = ?, player2_liquidity = ?, total_matched = ?,
                        analyzed = 0
                    WHERE id = ?
                """, (
                    match_data.get('player1_odds'),
                    match_data.get('player2_odds'),
                    tournament,
                    match_data.get('surface'),
                    match_data.get('player1_liquidity'),
                    match_data.get('player2_liquidity'),
                    match_data.get('total_matched'),
                    existing[0],
                ))
                return existing[0]
            else:
                # Insert new match
                cursor.execute("""
                    INSERT INTO upcoming_matches
                    (tournament, date, round, surface, player1_id, player2_id,
                     player1_name, player2_name, player1_odds, player2_odds,
                     player1_liquidity, player2_liquidity, total_matched)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tournament,
                    match_data.get('date'),
                    match_data.get('round'),
                    match_data.get('surface'),
                    match_data.get('player1_id'),
                    match_data.get('player2_id'),
                    match_data.get('player1_name'),
                    match_data.get('player2_name'),
                    match_data.get('player1_odds'),
                    match_data.get('player2_odds'),
                    match_data.get('player1_liquidity'),
                    match_data.get('player2_liquidity'),
                    match_data.get('total_matched'),
                ))
                return cursor.lastrowid

    def get_upcoming_matches(self, analyzed: bool = None) -> List[Dict]:
        """Get upcoming matches."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if analyzed is None:
                cursor.execute("SELECT * FROM upcoming_matches ORDER BY date")
            else:
                cursor.execute(
                    "SELECT * FROM upcoming_matches WHERE analyzed = ? ORDER BY date",
                    (1 if analyzed else 0,)
                )
            return [dict(row) for row in cursor.fetchall()]

    def update_upcoming_match_player_id(self, match_id: int, player_position: str,
                                         new_player_id: int):
        """
        Update the player ID for an upcoming match.
        player_position should be 'player1' or 'player2'.
        Also resets analyzed flag so match will be re-analyzed.
        """
        if player_position not in ('player1', 'player2'):
            raise ValueError("player_position must be 'player1' or 'player2'")

        column = f"{player_position}_id"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE upcoming_matches
                SET {column} = ?, analyzed = 0
                WHERE id = ?
            """, (new_player_id, match_id))

    def clear_upcoming_matches(self):
        """Clear all upcoming matches."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM upcoming_matches")

    # =========================================================================
    # DATA MANAGEMENT
    # =========================================================================

    def clear_import_data(self):
        """Clear all imported data (players, matches, rankings) for fresh import.
        Does NOT clear bets or upcoming_matches to preserve user data.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Clear in order to respect foreign keys
            cursor.execute("DELETE FROM head_to_head")
            cursor.execute("DELETE FROM player_surface_stats")
            cursor.execute("DELETE FROM rankings_history")
            cursor.execute("DELETE FROM matches")
            cursor.execute("DELETE FROM players")
            cursor.execute("DELETE FROM tournaments")

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_database_stats(self) -> Dict:
        """Get overall database statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            try:
                cursor.execute("SELECT COUNT(*) FROM players")
                stats['total_players'] = cursor.fetchone()[0]
            except Exception:
                stats['total_players'] = 0

            try:
                cursor.execute("SELECT COUNT(*) FROM matches")
                stats['total_matches'] = cursor.fetchone()[0]
            except Exception:
                stats['total_matches'] = 0

            try:
                cursor.execute("SELECT COUNT(*) FROM tournaments")
                stats['total_tournaments'] = cursor.fetchone()[0]
            except Exception:
                stats['total_tournaments'] = 0

            try:
                cursor.execute("SELECT MIN(date), MAX(date) FROM matches")
                row = cursor.fetchone()
                stats['earliest_match'] = row[0] if row else None
                stats['latest_match'] = row[1] if row else None
            except Exception:
                stats['earliest_match'] = None
                stats['latest_match'] = None

            try:
                cursor.execute("SELECT COUNT(*) FROM bets")
                stats['total_bets'] = cursor.fetchone()[0]
            except Exception:
                stats['total_bets'] = 0

            try:
                cursor.execute("""
                    SELECT surface, COUNT(*) as count
                    FROM matches
                    GROUP BY surface
                """)
                stats['matches_by_surface'] = {row[0]: row[1] for row in cursor.fetchall()}
            except Exception:
                stats['matches_by_surface'] = {}

            return stats

    # =========================================================================
    # APP SETTINGS
    # =========================================================================

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get an app setting value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT value FROM app_settings WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                return row[0] if row else default
            except Exception:
                return default

    def set_setting(self, key: str, value: str):
        """Set an app setting value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))

    def get_last_refresh(self, refresh_type: str = 'full') -> Optional[str]:
        """Get the last refresh timestamp.

        Args:
            refresh_type: 'full' or 'quick'

        Returns:
            ISO format timestamp string or None
        """
        key = f'last_{refresh_type}_refresh'
        return self.get_setting(key)

    def set_last_refresh(self, refresh_type: str = 'full'):
        """Set the last refresh timestamp to now.

        Args:
            refresh_type: 'full' or 'quick'
        """
        key = f'last_{refresh_type}_refresh'
        self.set_setting(key, datetime.now().isoformat())


# Create default instance
db = TennisDatabase()


if __name__ == "__main__":
    # Test database creation
    test_db = TennisDatabase()
    print("Database created successfully!")
    print(f"Database path: {DB_PATH}")
    stats = test_db.get_database_stats()
    print(f"Stats: {stats}")
