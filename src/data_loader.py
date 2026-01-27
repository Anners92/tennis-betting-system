"""
Tennis Betting System - Data Loader
Uses Tennis Explorer data from GitHub for all match data.
"""

import os
import sys
import ssl
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Callable
import tkinter as tk
from tkinter import ttk, messagebox

# Fix SSL certificates for frozen executables (PyInstaller)
if getattr(sys, 'frozen', False):
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    ssl_context = ssl.create_default_context(cafile=certifi.where())
else:
    ssl_context = ssl.create_default_context()

from config import SURFACE_MAPPING
from database import TennisDatabase, db


class DataLoader:
    """Load Tennis Explorer data into the database via GitHub."""

    def __init__(self, database: TennisDatabase = None):
        self.db = database or db
        self.progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable):
        """Set callback for progress updates: callback(message, progress_pct)"""
        self.progress_callback = callback

    def _report_progress(self, message: str, progress: float = None):
        """Report progress to callback if set."""
        if self.progress_callback:
            self.progress_callback(message, progress)
        else:
            print(message)

    def quick_refresh(self, months_back: int = 3) -> Dict:
        """Download and import latest Tennis Explorer data from GitHub.

        This is the primary data loading method. Downloads pre-scraped data
        from the GitHub repository which is updated daily.

        Args:
            months_back: Ignored (kept for compatibility)

        Returns:
            Dict with 'success', 'matches_updated', 'players_created' keys
        """
        from github_data_loader import GitHubDataLoader

        results = {
            'matches_updated': 0,
            'players_created': 0,
            'success': False,
        }

        try:
            loader = GitHubDataLoader()
            loader.set_progress_callback(self._report_progress)

            self._report_progress("Downloading latest Tennis Explorer data from GitHub...")

            # Download and import
            import_stats = loader.quick_refresh()

            if not import_stats.get('success'):
                self._report_progress("GitHub download failed, trying direct scrape...")
                return self._fallback_tennis_explorer_refresh(months_back)

            # Use correct keys from GitHubDataLoader result
            results['matches_updated'] = import_stats.get('matches_imported', 0)
            results['matches_scraped'] = import_stats.get('matches', 0)
            results['matches_skipped'] = import_stats.get('matches_skipped', 0)
            results['players_created'] = 0  # Players are locked, none created
            results['players_in_db'] = import_stats.get('players', 0)

            # Update surface stats
            self._report_progress("Updating surface statistics...")
            self.compute_surface_stats()

            # Update rankings
            self._report_progress("Updating player rankings...")
            self.update_player_rankings()

            results['success'] = True
            self._report_progress(
                f"Refresh complete! {results['matches_updated']} matches imported "
                f"({results['matches_skipped']} skipped due to unknown players)"
            )

        except Exception as e:
            self._report_progress(f"Refresh error: {e}")
            import traceback
            traceback.print_exc()

        return results

    def _fallback_tennis_explorer_refresh(self, months_back: int = 3) -> Dict:
        """Fallback to direct Tennis Explorer scraping if GitHub download fails."""
        from tennis_explorer_scraper import TennisExplorerScraper

        results = {
            'matches_updated': 0,
            'players_created': 0,
            'success': False,
        }

        try:
            scraper = TennisExplorerScraper()

            self._report_progress("Fetching recent match results from Tennis Explorer...")

            all_matches = scraper.fetch_recent_results(
                months_back=months_back,
                tour_types=["atp-single", "wta-single"],
                progress_callback=self._report_progress
            )

            if not all_matches:
                self._report_progress("No matches found!")
                return results

            self._report_progress(f"Found {len(all_matches)} total matches")

            import_stats = scraper.import_results_to_database(
                all_matches,
                progress_callback=self._report_progress
            )

            results['matches_updated'] = import_stats.get('matches_imported', 0)
            results['players_created'] = import_stats.get('players_created', 0)

            self.compute_surface_stats()
            self.update_player_rankings()

            results['success'] = True
            self._report_progress(
                f"Refresh complete! {results['matches_updated']} matches, "
                f"{results['players_created']} new players"
            )

        except Exception as e:
            self._report_progress(f"Refresh error: {e}")
            import traceback
            traceback.print_exc()

        return results

    def compute_surface_stats(self):
        """Compute win/loss stats per surface for all players."""
        self._report_progress("Computing surface statistics...")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Clear existing stats
            cursor.execute("DELETE FROM player_surface_stats")

            # Compute stats from matches
            cursor.execute("""
                INSERT INTO player_surface_stats (player_id, surface, wins, losses, win_rate)
                SELECT
                    player_id,
                    surface,
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

            # Get count of stats computed
            cursor.execute("SELECT COUNT(DISTINCT player_id) FROM player_surface_stats")
            player_count = cursor.fetchone()[0]

        self._report_progress(f"Computed surface stats for {player_count} players")

    def update_player_rankings(self):
        """Update player rankings from Tennis Explorer data in matches."""
        self._report_progress("Updating player rankings from match data...")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Update rankings from most recent matches where we have rank data
            cursor.execute("""
                UPDATE players SET current_ranking = (
                    SELECT COALESCE(
                        (SELECT winner_rank FROM matches
                         WHERE winner_id = players.id AND winner_rank IS NOT NULL
                         ORDER BY date DESC LIMIT 1),
                        (SELECT loser_rank FROM matches
                         WHERE loser_id = players.id AND loser_rank IS NOT NULL
                         ORDER BY date DESC LIMIT 1)
                    )
                )
                WHERE id IN (
                    SELECT DISTINCT winner_id FROM matches WHERE winner_rank IS NOT NULL
                    UNION
                    SELECT DISTINCT loser_id FROM matches WHERE loser_rank IS NOT NULL
                )
            """)

            updated = cursor.rowcount
            self._report_progress(f"Updated rankings for {updated} players")


class DataLoaderDialog:
    """Simple dialog for data refresh operations."""

    def __init__(self, parent, db: TennisDatabase):
        self.parent = parent
        self.loader = DataLoader(db)
        self.dialog = None

    def show_refresh_dialog(self):
        """Show dialog for quick refresh from GitHub."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Refresh Data")
        self.dialog.geometry("500x350")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center on parent
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 500) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 350) // 2
        self.dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Refresh Tennis Data", font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        ttk.Label(frame, text="Download latest match data from Tennis Explorer (via GitHub)").pack(anchor='w', pady=(5, 15))

        # Log area
        self.log_text = tk.Text(frame, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Progress bar
        self.progress = ttk.Progressbar(frame, mode='indeterminate', length=400)
        self.progress.pack(fill=tk.X, pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        self.refresh_btn = ttk.Button(btn_frame, text="Refresh Now", command=self._do_refresh)
        self.refresh_btn.pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _log(self, message: str):
        """Add message to log."""
        try:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
            self.dialog.update_idletasks()
        except tk.TclError:
            pass

    def _do_refresh(self):
        """Run the refresh in a thread."""
        import threading

        self.refresh_btn.configure(state=tk.DISABLED)
        self.progress.start(10)

        def refresh_thread():
            try:
                def progress_callback(msg, pct=None):
                    self.dialog.after(0, lambda: self._log(msg))

                self.loader.set_progress_callback(progress_callback)
                result = self.loader.quick_refresh()

                if result['success']:
                    self.dialog.after(0, lambda: self._log("\n✓ Data refresh complete!"))
                else:
                    self.dialog.after(0, lambda: self._log("\n✗ Refresh failed"))

            except Exception as e:
                self.dialog.after(0, lambda: self._log(f"\nError: {e}"))
            finally:
                self.dialog.after(0, self.progress.stop)
                self.dialog.after(0, lambda: self.refresh_btn.configure(state=tk.NORMAL))

        thread = threading.Thread(target=refresh_thread, daemon=True)
        thread.start()


# Alias for backward compatibility with main.py
DataLoaderUI = DataLoaderDialog
