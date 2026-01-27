"""
Match Data Loader - Scrapes match data from Tennis Explorer
Uses the same robust name matching as manual imports.
Players are locked - only matches are imported, linked to existing players.
"""

import sqlite3
import sys
import os
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime


class GitHubDataLoader:
    """Load tennis match data by scraping Tennis Explorer.

    Uses the same robust name matching as manual imports.
    Players are locked - only matches are imported, linked to existing players.
    """

    def __init__(self, data_dir: Path = None):
        if data_dir is None:
            from config import DATA_DIR
            data_dir = DATA_DIR
        self.data_dir = data_dir
        self.progress_callback: Optional[Callable] = None
        self.months_to_fetch = 12  # Default: fetch 12 months of data

    def set_progress_callback(self, callback: Callable):
        """Set callback for progress updates."""
        self.progress_callback = callback

    def _report_progress(self, message: str, progress: float = None):
        """Report progress."""
        if self.progress_callback:
            self.progress_callback(message, progress)
        else:
            print(message)

    def download_data(self) -> bool:
        """'Download' is now just a pass-through - scraping happens in import."""
        self._report_progress("Ready to scrape match data from Tennis Explorer...")
        self._report_progress("Click 'Quick Import' to fetch and import matches.")
        return True

    def get_last_updated(self) -> Optional[str]:
        """Get the last match date in the database."""
        try:
            from config import DB_PATH
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(date) FROM matches")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except:
            return None

    def import_to_main_database(self) -> dict:
        """Scrape matches from Tennis Explorer and import to database.

        Players are LOCKED - only matches are imported, linked to existing players.
        Uses the same robust PlayerNameMatcher as manual imports.
        """
        from config import DB_PATH
        from tennis_explorer_scraper import TennisExplorerScraper, PlayerNameMatcher

        stats = {
            'success': False,
            'players': 0,
            'matches': 0,
            'matches_imported': 0,
            'matches_skipped': 0
        }

        try:
            # Get player count
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM players")
            stats['players'] = cursor.fetchone()[0]
            conn.close()

            if stats['players'] == 0:
                self._report_progress("No players in database. Cannot import matches.")
                return stats

            self._report_progress(f"Database has {stats['players']} players (locked)")

            # Load player name matcher
            self._report_progress("Building player name index...")
            name_matcher = PlayerNameMatcher()
            conn = sqlite3.connect(DB_PATH)
            name_matcher.load_players(conn)
            conn.close()
            self._report_progress(f"Indexed {len(name_matcher.players)} players for matching")

            # Scrape matches from Tennis Explorer
            scraper = TennisExplorerScraper()

            self._report_progress(f"Scraping {self.months_to_fetch} months of ATP matches...")
            atp_matches = scraper.fetch_recent_results(
                months_back=self.months_to_fetch,
                tour_types=["atp-single"],
                progress_callback=lambda msg: self._report_progress(msg)
            )

            self._report_progress(f"Scraping {self.months_to_fetch} months of WTA matches...")
            wta_matches = scraper.fetch_recent_results(
                months_back=self.months_to_fetch,
                tour_types=["wta-single"],
                progress_callback=lambda msg: self._report_progress(msg)
            )

            self._report_progress(f"Scraping {self.months_to_fetch} months of ITF Women matches...")
            itf_women_matches = scraper.fetch_recent_results(
                months_back=self.months_to_fetch,
                tour_types=["itf-women-single"],
                progress_callback=lambda msg: self._report_progress(msg)
            )

            self._report_progress(f"Scraping {self.months_to_fetch} months of ITF Men matches...")
            itf_men_matches = scraper.fetch_recent_results(
                months_back=self.months_to_fetch,
                tour_types=["itf-men-single"],
                progress_callback=lambda msg: self._report_progress(msg)
            )

            all_matches = atp_matches + wta_matches + itf_women_matches + itf_men_matches
            stats['matches'] = len(all_matches)
            self._report_progress(f"Scraped {len(all_matches)} total matches")

            if not all_matches:
                self._report_progress("No matches found to import")
                return stats

            # Import matches, matching to existing players only
            self._report_progress("Importing matches (players locked - no new players)...")

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Don't delete existing matches - just add new ones with INSERT OR IGNORE
            # This preserves manually imported matches

            imported = 0
            skipped = 0
            name_match_failures = []

            for match in all_matches:
                winner_name = match.get('winner_name', '')
                loser_name = match.get('loser_name', '')

                if not winner_name or not loser_name:
                    skipped += 1
                    continue

                # Look up players using robust name matcher
                winner_id = name_matcher.find_player_id(winner_name)
                loser_id = name_matcher.find_player_id(loser_name)

                # Skip if either player not found (players are locked)
                if not winner_id or not loser_id:
                    skipped += 1
                    # Track first 20 name match failures for debugging
                    if len(name_match_failures) < 20:
                        if not winner_id:
                            name_match_failures.append(f"Winner not found: {winner_name}")
                        if not loser_id:
                            name_match_failures.append(f"Loser not found: {loser_name}")
                    continue

                # Get canonical names
                canonical_winner = name_matcher.get_player_name(winner_id) or winner_name
                canonical_loser = name_matcher.get_player_name(loser_id) or loser_name

                # Check for duplicate - same players within 3 days
                match_date = match.get('date', '')
                try:
                    cursor.execute('''
                        SELECT id FROM matches
                        WHERE winner_id = ? AND loser_id = ?
                        AND date BETWEEN date(?, '-3 days') AND date(?, '+3 days')
                        LIMIT 1
                    ''', (winner_id, loser_id, match_date, match_date))

                    if cursor.fetchone():
                        # Duplicate match exists, skip
                        skipped += 1
                        continue
                except:
                    pass

                # Generate unique match ID
                match_id = f"TE_{match_date}_{winner_id}_{loser_id}"

                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO matches
                        (id, tournament, date, surface, winner_id, loser_id,
                         winner_name, loser_name, score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        match_id,
                        match.get('tournament', ''),
                        match_date,
                        match.get('surface', 'Hard'),
                        winner_id,
                        loser_id,
                        canonical_winner,
                        canonical_loser,
                        match.get('score', '')
                    ))

                    if cursor.rowcount > 0:
                        imported += 1

                except Exception as e:
                    skipped += 1
                    continue

                # Progress update
                if imported > 0 and imported % 1000 == 0:
                    self._report_progress(f"Imported {imported} matches...")

            conn.commit()
            conn.close()

            stats['matches_imported'] = imported
            stats['matches_skipped'] = skipped
            stats['success'] = True

            self._report_progress(f"Import complete: {imported} matches imported, {skipped} skipped")

            # Report name matching failures if any
            if name_match_failures:
                self._report_progress(f"Name match failures (first {len(name_match_failures)}):")
                for failure in name_match_failures[:10]:
                    self._report_progress(f"  - {failure}")

        except Exception as e:
            self._report_progress(f"Import error: {e}")
            import traceback
            traceback.print_exc()

        return stats

    def quick_refresh(self) -> dict:
        """Scrape and import data in one step."""
        return self.import_to_main_database()

    def quick_refresh_recent(self, days: int = 7) -> dict:
        """Quick refresh - only fetch matches from the last N days.

        This is much faster than the full refresh as it only scrapes
        recent days instead of multiple months.

        Args:
            days: Number of days to look back (default 7)

        Returns:
            Dict with import statistics
        """
        from config import DB_PATH
        from tennis_explorer_scraper import TennisExplorerScraper, PlayerNameMatcher

        stats = {
            'success': False,
            'players': 0,
            'matches': 0,
            'matches_imported': 0,
            'matches_skipped': 0
        }

        try:
            # Get player count
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM players")
            stats['players'] = cursor.fetchone()[0]
            conn.close()

            if stats['players'] == 0:
                self._report_progress("No players in database. Cannot import matches.")
                return stats

            self._report_progress(f"Database has {stats['players']} players (locked)")

            # Load player name matcher
            self._report_progress("Building player name index...")
            name_matcher = PlayerNameMatcher()
            conn = sqlite3.connect(DB_PATH)
            name_matcher.load_players(conn)
            conn.close()
            self._report_progress(f"Indexed {len(name_matcher.players)} players for matching")

            # Scrape matches from Tennis Explorer - only last N days
            scraper = TennisExplorerScraper()

            self._report_progress(f"Scraping last {days} days of ATP matches...")
            atp_matches = scraper.fetch_recent_days(
                days_back=days,
                tour_type="atp-single",
                progress_callback=lambda msg: self._report_progress(msg)
            )

            self._report_progress(f"Scraping last {days} days of WTA matches...")
            wta_matches = scraper.fetch_recent_days(
                days_back=days,
                tour_type="wta-single",
                progress_callback=lambda msg: self._report_progress(msg)
            )

            self._report_progress(f"Scraping last {days} days of ITF Women matches...")
            itf_women_matches = scraper.fetch_recent_days(
                days_back=days,
                tour_type="itf-women-single",
                progress_callback=lambda msg: self._report_progress(msg)
            )

            self._report_progress(f"Scraping last {days} days of ITF Men matches...")
            itf_men_matches = scraper.fetch_recent_days(
                days_back=days,
                tour_type="itf-men-single",
                progress_callback=lambda msg: self._report_progress(msg)
            )

            all_matches = atp_matches + wta_matches + itf_women_matches + itf_men_matches
            stats['matches'] = len(all_matches)
            self._report_progress(f"Scraped {len(all_matches)} total matches from last {days} days")

            if not all_matches:
                self._report_progress("No new matches found")
                stats['success'] = True
                return stats

            # Import matches, matching to existing players only
            self._report_progress("Importing matches (players locked - no new players)...")

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            imported = 0
            skipped = 0
            name_match_failures = []

            for match in all_matches:
                winner_name = match.get('winner_name', '')
                loser_name = match.get('loser_name', '')

                if not winner_name or not loser_name:
                    skipped += 1
                    continue

                # Look up players using robust name matcher
                winner_id = name_matcher.find_player_id(winner_name)
                loser_id = name_matcher.find_player_id(loser_name)

                # Skip if either player not found (players are locked)
                if not winner_id or not loser_id:
                    skipped += 1
                    if len(name_match_failures) < 20:
                        if not winner_id:
                            name_match_failures.append(f"Winner not found: {winner_name}")
                        if not loser_id:
                            name_match_failures.append(f"Loser not found: {loser_name}")
                    continue

                # Get canonical names
                canonical_winner = name_matcher.get_player_name(winner_id) or winner_name
                canonical_loser = name_matcher.get_player_name(loser_id) or loser_name

                # Check for duplicate - same players within 3 days
                match_date = match.get('date', '')
                try:
                    cursor.execute('''
                        SELECT id FROM matches
                        WHERE winner_id = ? AND loser_id = ?
                        AND date BETWEEN date(?, '-3 days') AND date(?, '+3 days')
                        LIMIT 1
                    ''', (winner_id, loser_id, match_date, match_date))

                    if cursor.fetchone():
                        # Duplicate match exists, skip
                        skipped += 1
                        continue
                except:
                    pass

                # Generate unique match ID
                match_id = f"TE_{match_date}_{winner_id}_{loser_id}"

                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO matches
                        (id, tournament, date, surface, winner_id, loser_id,
                         winner_name, loser_name, score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        match_id,
                        match.get('tournament', ''),
                        match_date,
                        match.get('surface', 'Hard'),
                        winner_id,
                        loser_id,
                        canonical_winner,
                        canonical_loser,
                        match.get('score', '')
                    ))

                    if cursor.rowcount > 0:
                        imported += 1

                except Exception as e:
                    skipped += 1
                    continue

            conn.commit()
            conn.close()

            stats['matches_imported'] = imported
            stats['matches_skipped'] = skipped
            stats['success'] = True

            self._report_progress(f"Quick refresh complete: {imported} matches imported, {skipped} skipped")

            # Report name matching failures if any
            if name_match_failures:
                self._report_progress(f"Name match failures (first {len(name_match_failures)}):")
                for failure in name_match_failures[:5]:
                    self._report_progress(f"  - {failure}")

        except Exception as e:
            self._report_progress(f"Quick refresh error: {e}")
            import traceback
            traceback.print_exc()

        return stats


if __name__ == "__main__":
    loader = GitHubDataLoader()
    loader.set_progress_callback(lambda msg, pct=None: print(msg))
    result = loader.quick_refresh()
    print(f"\nResult: {result}")
