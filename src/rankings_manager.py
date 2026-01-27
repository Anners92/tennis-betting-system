"""
Tennis Betting System - Rankings Manager
Simple UI for manually updating player rankings in the database.
Also supports bulk download of ATP/WTA rankings from Tennis Explorer.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Optional, List, Dict

from config import UI_COLORS
from database import db


class RankingsManager:
    """Window for managing player rankings."""

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Rankings Manager")
        self.root.geometry("900x600")
        self.root.configure(bg=UI_COLORS["bg_dark"])

        self._setup_styles()
        self._create_widgets()
        self._load_players()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=UI_COLORS["bg_dark"])
        style.configure("Card.TFrame", background=UI_COLORS["bg_medium"])
        style.configure(
            "Dark.TLabel",
            background=UI_COLORS["bg_dark"],
            foreground=UI_COLORS["text_primary"],
            font=("Segoe UI", 10)
        )
        style.configure(
            "Title.TLabel",
            background=UI_COLORS["bg_dark"],
            foreground=UI_COLORS["text_primary"],
            font=("Segoe UI", 16, "bold")
        )
        style.configure(
            "Treeview",
            background=UI_COLORS["bg_medium"],
            foreground=UI_COLORS["text_primary"],
            fieldbackground=UI_COLORS["bg_medium"],
            rowheight=28,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            background=UI_COLORS["bg_light"],
            foreground=UI_COLORS["text_primary"],
            font=("Segoe UI", 10, "bold")
        )
        style.map("Treeview", background=[("selected", UI_COLORS["accent"])])

    def _create_widgets(self):
        """Create the UI widgets."""
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title and download button row
        title_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        title_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(title_frame, text="Player Rankings Manager", style="Title.TLabel").pack(side=tk.LEFT)

        # Update unranked players button (for those below 1500)
        update_unranked_btn = tk.Button(
            title_frame,
            text="2. Update Below 1500",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._update_unranked_players,
            padx=15,
            pady=8
        )
        update_unranked_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # Download rankings button
        download_btn = tk.Button(
            title_frame,
            text="1. Download Top 1500",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._download_rankings,
            padx=15,
            pady=8
        )
        download_btn.pack(side=tk.RIGHT)

        # View unmatched button
        unmatched_btn = tk.Button(
            title_frame,
            text="View Unmatched",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._view_unmatched_players,
            padx=10,
            pady=5
        )
        unmatched_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # Rankings info label
        self.rankings_info_var = tk.StringVar(value="")
        self._update_rankings_info()
        rankings_info = tk.Label(
            title_frame,
            textvariable=self.rankings_info_var,
            font=("Segoe UI", 9),
            fg=UI_COLORS["text_secondary"],
            bg=UI_COLORS["bg_dark"]
        )
        rankings_info.pack(side=tk.RIGHT, padx=(0, 15))

        # Search frame
        search_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        search_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(search_frame, text="Search:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 10))

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search)
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 11),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            insertbackground=UI_COLORS["text_primary"],
            relief=tk.FLAT,
            width=40
        )
        search_entry.pack(side=tk.LEFT, padx=(0, 20), ipady=5)

        # Filter: Show only unranked
        self.unranked_only = tk.BooleanVar(value=False)
        unranked_cb = tk.Checkbutton(
            search_frame,
            text="Show unranked only",
            variable=self.unranked_only,
            command=self._on_search,
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"],
            selectcolor=UI_COLORS["bg_medium"],
            activebackground=UI_COLORS["bg_dark"],
            activeforeground=UI_COLORS["text_primary"]
        )
        unranked_cb.pack(side=tk.LEFT, padx=(0, 20))

        # Filter: Show only upcoming match players
        self.upcoming_only = tk.BooleanVar(value=False)
        upcoming_cb = tk.Checkbutton(
            search_frame,
            text="Upcoming matches only",
            variable=self.upcoming_only,
            command=self._on_search,
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"],
            selectcolor=UI_COLORS["bg_medium"],
            activebackground=UI_COLORS["bg_dark"],
            activeforeground=UI_COLORS["text_primary"]
        )
        upcoming_cb.pack(side=tk.LEFT)

        # Filter: Show only players with no match history
        self.no_history_only = tk.BooleanVar(value=False)
        no_history_cb = tk.Checkbutton(
            search_frame,
            text="No match history",
            variable=self.no_history_only,
            command=self._on_search,
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"],
            selectcolor=UI_COLORS["bg_medium"],
            activebackground=UI_COLORS["bg_dark"],
            activeforeground=UI_COLORS["text_primary"]
        )
        no_history_cb.pack(side=tk.LEFT, padx=(0, 10))

        # Players list
        list_frame = ttk.Frame(main_frame, style="Card.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        columns = ("id", "name", "country", "ranking", "matches")
        self.players_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.players_tree.heading("id", text="ID")
        self.players_tree.heading("name", text="Player Name")
        self.players_tree.heading("country", text="Country")
        self.players_tree.heading("ranking", text="Current Rank")
        self.players_tree.heading("matches", text="Matches")

        self.players_tree.column("id", width=80, anchor=tk.CENTER)
        self.players_tree.column("name", width=300)
        self.players_tree.column("country", width=80, anchor=tk.CENTER)
        self.players_tree.column("ranking", width=120, anchor=tk.CENTER)
        self.players_tree.column("matches", width=80, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.players_tree.yview)
        self.players_tree.configure(yscrollcommand=scrollbar.set)

        self.players_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection
        self.players_tree.bind('<<TreeviewSelect>>', self._on_select)
        self.players_tree.bind('<Double-1>', self._on_double_click)

        # Edit frame
        edit_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        edit_frame.pack(fill=tk.X)

        # Selected player info
        info_frame = ttk.Frame(edit_frame, style="Card.TFrame")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text="Selected:", style="Dark.TLabel").pack(side=tk.LEFT)
        self.selected_label = ttk.Label(info_frame, text="None", style="Dark.TLabel")
        self.selected_label.pack(side=tk.LEFT, padx=(10, 0))

        # Ranking input
        input_frame = ttk.Frame(edit_frame, style="Card.TFrame")
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="New Ranking:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 10))

        self.ranking_var = tk.StringVar()
        self.ranking_entry = tk.Entry(
            input_frame,
            textvariable=self.ranking_var,
            font=("Segoe UI", 12),
            bg=UI_COLORS["bg_light"],
            fg=UI_COLORS["text_primary"],
            insertbackground=UI_COLORS["text_primary"],
            relief=tk.FLAT,
            width=10
        )
        self.ranking_entry.pack(side=tk.LEFT, padx=(0, 15), ipady=5)
        self.ranking_entry.bind('<Return>', lambda e: self._update_ranking())

        # Update button
        update_btn = tk.Button(
            input_frame,
            text="Update Ranking",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._update_ranking,
            padx=20,
            pady=8
        )
        update_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Clear ranking button
        clear_btn = tk.Button(
            input_frame,
            text="Clear Ranking",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._clear_ranking,
            padx=15,
            pady=8
        )
        clear_btn.pack(side=tk.LEFT)

        # Fetch match history button
        fetch_history_btn = tk.Button(
            input_frame,
            text="Fetch Match History",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["primary"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._fetch_match_history,
            padx=15,
            pady=8
        )
        fetch_history_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_label = tk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            fg=UI_COLORS["text_secondary"],
            bg=UI_COLORS["bg_dark"],
            anchor=tk.W
        )
        status_label.pack(fill=tk.X, pady=(10, 0))

        # Store data
        self.all_players = []
        self.selected_player_id = None
        self.upcoming_player_ids = set()

    def _load_players(self):
        """Load all players from database."""
        self.all_players = db.get_all_players()

        # Cache match counts for players (on-demand in _filter_players for performance)
        self.match_counts = {}

        # Get players in upcoming matches
        upcoming = db.get_upcoming_matches()
        self.upcoming_player_ids = set()
        for match in upcoming:
            if match.get('player1_id'):
                self.upcoming_player_ids.add(match['player1_id'])
            if match.get('player2_id'):
                self.upcoming_player_ids.add(match['player2_id'])

        self._filter_players()
        self.status_var.set(f"Loaded {len(self.all_players)} players")

    def _filter_players(self):
        """Filter and display players based on search and filters."""
        self.players_tree.delete(*self.players_tree.get_children())

        search_term = self.search_var.get().lower().strip()
        show_unranked = self.unranked_only.get()
        show_upcoming = self.upcoming_only.get()
        show_no_history = self.no_history_only.get()

        count = 0
        no_history_count = 0
        for player in self.all_players:
            # Apply filters
            if search_term and search_term not in player['name'].lower():
                continue

            if show_unranked and player.get('current_ranking'):
                continue

            if show_upcoming and player['id'] not in self.upcoming_player_ids:
                continue

            # Get match count (cache for performance)
            player_id = player['id']
            if player_id not in self.match_counts:
                self.match_counts[player_id] = db.get_player_match_count(player_id)
            match_count = self.match_counts[player_id]

            # Filter by no history
            if show_no_history and match_count > 0:
                continue

            if match_count == 0:
                no_history_count += 1

            # Add to tree
            ranking = player.get('current_ranking') or "-"
            country = player.get('country') or "-"
            match_display = str(match_count) if match_count > 0 else "NONE"

            self.players_tree.insert("", tk.END, values=(
                player['id'],
                player['name'],
                country,
                ranking,
                match_display
            ))
            count += 1

            # Limit display for performance
            if count >= 500:
                break

        status = f"Showing {count} players"
        if count >= 500:
            status += " (limited to 500)"
        if show_upcoming and no_history_count > 0:
            status += f" - {no_history_count} have NO match history!"
        self.status_var.set(status)

    def _on_search(self, *args):
        """Handle search input change."""
        self._filter_players()

    def _on_select(self, event):
        """Handle player selection."""
        selection = self.players_tree.selection()
        if not selection:
            return

        item = self.players_tree.item(selection[0])
        values = item['values']

        self.selected_player_id = values[0]
        player_name = values[1]
        current_rank = values[3]

        self.selected_label.config(text=f"{player_name} (ID: {self.selected_player_id})")

        # Pre-fill ranking entry if exists
        if current_rank and current_rank != "-":
            self.ranking_var.set(str(current_rank))
        else:
            self.ranking_var.set("")

        self.ranking_entry.focus()
        self.ranking_entry.select_range(0, tk.END)

    def _on_double_click(self, event):
        """Handle double-click - focus ranking entry."""
        self._on_select(event)

    def _update_ranking(self):
        """Update the selected player's ranking."""
        if not self.selected_player_id:
            messagebox.showwarning("No Selection", "Please select a player first.")
            return

        ranking_str = self.ranking_var.get().strip()
        if not ranking_str:
            messagebox.showwarning("No Ranking", "Please enter a ranking number.")
            return

        try:
            ranking = int(ranking_str)
            if ranking <= 0:
                raise ValueError("Ranking must be positive")
        except ValueError:
            messagebox.showerror("Invalid Ranking", "Please enter a valid positive number.")
            return

        # Update database
        db.update_player_ranking(self.selected_player_id, ranking)

        # Update local data
        for player in self.all_players:
            if player['id'] == self.selected_player_id:
                player['current_ranking'] = ranking
                break

        # Refresh display
        self._filter_players()

        # Find and select the player again
        for item in self.players_tree.get_children():
            if self.players_tree.item(item)['values'][0] == self.selected_player_id:
                self.players_tree.selection_set(item)
                self.players_tree.see(item)
                break

        self.status_var.set(f"Updated ranking to {ranking}")
        messagebox.showinfo("Success", f"Ranking updated to {ranking}")

    def _clear_ranking(self):
        """Clear the selected player's ranking."""
        if not self.selected_player_id:
            messagebox.showwarning("No Selection", "Please select a player first.")
            return

        if not messagebox.askyesno("Confirm", "Clear this player's ranking?"):
            return

        # Update database with NULL
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE players SET current_ranking = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (self.selected_player_id,))

        # Update local data
        for player in self.all_players:
            if player['id'] == self.selected_player_id:
                player['current_ranking'] = None
                break

        # Refresh
        self._filter_players()
        self.ranking_var.set("")
        self.status_var.set("Ranking cleared")

    def _fetch_match_history(self):
        """Fetch match history for the selected player from Tennis Explorer."""
        if not self.selected_player_id:
            messagebox.showwarning("No Selection", "Please select a player first.")
            return

        # Get player name
        player_name = None
        for player in self.all_players:
            if player['id'] == self.selected_player_id:
                player_name = player['name']
                break

        if not player_name:
            messagebox.showerror("Error", "Could not find player name.")
            return

        # Confirm
        current_matches = self.match_counts.get(self.selected_player_id, 0)
        if not messagebox.askyesno(
            "Fetch Match History",
            f"Fetch match history for {player_name}?\n\n"
            f"Current matches in database: {current_matches}\n\n"
            f"This will download their recent matches from Tennis Explorer "
            f"and import them into the database."
        ):
            return

        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("Fetching Match History")
        progress_dialog.geometry("400x150")
        progress_dialog.configure(bg=UI_COLORS["bg_dark"])
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        # Center
        progress_dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 150) // 2
        progress_dialog.geometry(f"+{x}+{y}")

        progress_label = tk.Label(
            progress_dialog,
            text="Starting...",
            font=("Segoe UI", 11),
            fg="white",
            bg=UI_COLORS["bg_dark"],
            wraplength=380
        )
        progress_label.pack(pady=30, padx=20)

        def update_progress(msg):
            progress_label.config(text=msg)
            progress_dialog.update()

        def run_fetch():
            try:
                from tennis_explorer_scraper import TennisExplorerScraper
                scraper = TennisExplorerScraper()
                stats = scraper.fetch_player_match_history(
                    self.selected_player_id,
                    player_name,
                    limit=6,
                    progress_callback=update_progress
                )
                self.root.after(0, lambda: self._on_fetch_complete(progress_dialog, stats, player_name))
            except Exception as e:
                self.root.after(0, lambda: self._on_fetch_error(progress_dialog, str(e)))

        import threading
        thread = threading.Thread(target=run_fetch)
        thread.start()

    def _on_fetch_complete(self, dialog, stats, player_name):
        """Handle fetch completion."""
        dialog.destroy()

        # Clear match count cache to force refresh
        if self.selected_player_id in self.match_counts:
            del self.match_counts[self.selected_player_id]

        # Refresh display
        self._filter_players()

        if stats['success']:
            messagebox.showinfo(
                "Match History Imported",
                f"Successfully imported match history for {player_name}!\n\n"
                f"Matches found: {stats['matches_found']}\n"
                f"Matches imported: {stats['matches_imported']}\n"
                f"New opponent records: {stats['players_created']}"
            )
        else:
            messagebox.showwarning(
                "Fetch Result",
                f"Could not fully import match history:\n\n{stats['message']}"
            )

    def _on_fetch_error(self, dialog, error):
        """Handle fetch error."""
        dialog.destroy()
        messagebox.showerror("Fetch Error", f"Error fetching match history:\n\n{error}")

    def _update_rankings_info(self):
        """Update the rankings info label with cache status."""
        try:
            from rankings_downloader import RankingsDownloader
            downloader = RankingsDownloader()
            downloaded_at = downloader.get_rankings_age()
            if downloaded_at:
                # Parse and format the date
                from datetime import datetime
                dt = datetime.fromisoformat(downloaded_at)
                age_str = dt.strftime("%Y-%m-%d %H:%M")
                self.rankings_info_var.set(f"Last updated: {age_str}")
            else:
                self.rankings_info_var.set("No rankings downloaded yet")
        except Exception as e:
            self.rankings_info_var.set("")

    def _download_rankings(self):
        """Download ATP and WTA rankings from Tennis Explorer."""
        if not messagebox.askyesno(
            "Download Rankings",
            "Download ATP and WTA rankings from Tennis Explorer?\n\n"
            "This will fetch rankings for the top 2000 players in each tour "
            "and update your local database.\n\n"
            "This may take a few minutes."
        ):
            return

        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("Downloading Rankings")
        progress_dialog.geometry("500x300")
        progress_dialog.configure(bg=UI_COLORS["bg_dark"])
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        # Center the dialog
        progress_dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 300) // 2
        progress_dialog.geometry(f"+{x}+{y}")

        progress_label = tk.Label(
            progress_dialog,
            text="Initializing...",
            font=("Segoe UI", 11),
            fg="white",
            bg=UI_COLORS["bg_dark"]
        )
        progress_label.pack(pady=20)

        # Progress log
        log_text = tk.Text(
            progress_dialog,
            height=10,
            font=("Consolas", 9),
            fg="white",
            bg=UI_COLORS["bg_medium"],
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        log_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def update_progress(msg):
            progress_label.config(text=msg)
            log_text.insert(tk.END, msg + "\n")
            log_text.see(tk.END)
            progress_dialog.update()

        def run_download():
            try:
                from rankings_downloader import download_and_update_rankings
                stats = download_and_update_rankings(max_rank=2000, progress_callback=update_progress)

                # Update UI on completion
                self.root.after(0, lambda: self._on_download_complete(progress_dialog, stats))

            except Exception as e:
                self.root.after(0, lambda: self._on_download_error(progress_dialog, str(e)))

        # Run in separate thread
        thread = threading.Thread(target=run_download)
        thread.start()

    def _on_download_complete(self, dialog, stats):
        """Handle download completion."""
        dialog.destroy()

        # Refresh the players list
        self._load_players()

        # Update rankings info
        self._update_rankings_info()

        messagebox.showinfo(
            "Rankings Downloaded",
            f"Successfully downloaded rankings!\n\n"
            f"ATP: {stats.get('atp_total', 0)} players downloaded, {stats.get('atp_updated', 0)} updated in DB\n"
            f"WTA: {stats.get('wta_total', 0)} players downloaded, {stats.get('wta_updated', 0)} updated in DB\n\n"
            f"Players not matched: {stats.get('not_found', 0)}"
        )

    def _on_download_error(self, dialog, error):
        """Handle download error."""
        dialog.destroy()
        messagebox.showerror("Download Error", f"Failed to download rankings:\n\n{error}")

    def _update_unranked_players(self):
        """Update rankings for players below top 1500 from their profiles."""
        # Check if there are upcoming matches
        upcoming = db.get_upcoming_matches()
        if not upcoming:
            messagebox.showinfo(
                "No Matches",
                "No upcoming matches found.\n\nLoad some matches first in the Bet Suggester."
            )
            return

        # Count players who need updating (rank 1500 or None)
        unranked_players = []
        seen_names = set()  # Track names to avoid duplicates
        already_ranked = 0
        doubles_skipped = 0
        for match in upcoming:
            for pid_key, name_key in [('player1_id', 'player1_name'), ('player2_id', 'player2_name')]:
                pid = match.get(pid_key)
                pname = match.get(name_key)
                if pid and pname:
                    # Skip doubles matches (names contain " / ")
                    if ' / ' in pname:
                        doubles_skipped += 1
                        continue
                    # Skip if we've seen this ID
                    if pid in [p[0] for p in unranked_players]:
                        continue
                    # Skip if we've seen a similar name (duplicate players in DB)
                    name_lower = pname.lower().strip()
                    is_duplicate = False
                    for seen in seen_names:
                        if name_lower.startswith(seen) or seen.startswith(name_lower):
                            is_duplicate = True
                            break
                    if is_duplicate:
                        continue
                    player = db.get_player(pid)
                    if player:
                        rank = player.get('current_ranking')
                        if rank == 1500 or rank is None:
                            unranked_players.append((pid, pname))
                            seen_names.add(name_lower)
                        else:
                            already_ranked += 1

        if not unranked_players:
            messagebox.showinfo(
                "All Ranked",
                f"All singles players in upcoming matches already have accurate rankings.\n\n"
                f"{already_ranked} players with rankings from the top 1500 list.\n"
                f"{doubles_skipped} doubles matches excluded."
            )
            return

        if not messagebox.askyesno(
            "Update Unranked Players",
            f"Found {len(unranked_players)} singles players ranked below 1500.\n\n"
            f"Fetch their actual rankings from Tennis Explorer profiles?\n\n"
            f"({already_ranked} already ranked, {doubles_skipped} doubles matches excluded)"
        ):
            return

        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("Updating Player Rankings")
        progress_dialog.geometry("500x350")
        progress_dialog.configure(bg=UI_COLORS["bg_dark"])
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        # Center
        progress_dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        progress_dialog.geometry(f"+{x}+{y}")

        progress_label = tk.Label(
            progress_dialog,
            text="Initializing...",
            font=("Segoe UI", 11),
            fg="white",
            bg=UI_COLORS["bg_dark"]
        )
        progress_label.pack(pady=20)

        log_text = tk.Text(
            progress_dialog,
            height=12,
            font=("Consolas", 9),
            fg="white",
            bg=UI_COLORS["bg_medium"],
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        log_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        def update_progress(msg):
            progress_label.config(text=msg.split('...')[0] + '...' if '...' in msg else msg)
            log_text.insert(tk.END, msg + "\n")
            log_text.see(tk.END)
            progress_dialog.update()

        def run_update():
            try:
                from rankings_downloader import update_unranked_players_from_profiles
                stats = update_unranked_players_from_profiles(progress_callback=update_progress)
                self.root.after(0, lambda: self._on_unranked_update_complete(progress_dialog, stats))
            except Exception as e:
                self.root.after(0, lambda: self._on_download_error(progress_dialog, str(e)))

        thread = threading.Thread(target=run_update)
        thread.start()

    def _view_unmatched_players(self):
        """View and manage unmatched players."""
        from rankings_downloader import get_unmatched_players, search_rankings_for_player, add_rankings_mapping

        unmatched = get_unmatched_players()

        if not unmatched:
            messagebox.showinfo(
                "No Unmatched Players",
                "No unmatched players found.\n\nRun 'Download Top 1500' first to generate the list."
            )
            return

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Unmatched Players")
        dialog.geometry("800x500")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)

        # Instructions
        tk.Label(
            dialog,
            text="Players that couldn't be matched to rankings (showing first 100):",
            font=("Segoe UI", 10),
            fg=UI_COLORS["text_secondary"],
            bg=UI_COLORS["bg_dark"]
        ).pack(pady=(15, 5))

        # Frame for list and search
        main_frame = ttk.Frame(dialog, style="Dark.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Left: Unmatched list
        left_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            left_frame,
            text="Unmatched Players:",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["bg_dark"]
        ).pack(anchor=tk.W)

        unmatched_listbox = tk.Listbox(
            left_frame,
            font=("Consolas", 10),
            bg=UI_COLORS["bg_medium"],
            fg="white",
            selectbackground=UI_COLORS["accent"],
            height=15,
            width=35
        )
        unmatched_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        for p in unmatched[:100]:
            unmatched_listbox.insert(tk.END, p['name'])

        # Right: Search and mapping
        right_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(20, 0))

        tk.Label(
            right_frame,
            text="Search Rankings:",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=UI_COLORS["bg_dark"]
        ).pack(anchor=tk.W)

        search_var = tk.StringVar()
        search_entry = tk.Entry(
            right_frame,
            textvariable=search_var,
            font=("Segoe UI", 11),
            bg=UI_COLORS["bg_medium"],
            fg="white",
            insertbackground="white",
            width=30
        )
        search_entry.pack(fill=tk.X, pady=5)

        results_listbox = tk.Listbox(
            right_frame,
            font=("Consolas", 10),
            bg=UI_COLORS["bg_medium"],
            fg="white",
            selectbackground=UI_COLORS["accent"],
            height=10,
            width=35
        )
        results_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        def do_search(*args):
            term = search_var.get().strip()
            results_listbox.delete(0, tk.END)
            if len(term) >= 2:
                results = search_rankings_for_player(term)
                for r in results[:20]:
                    results_listbox.insert(tk.END, f"#{r['rank']} {r['name']}")

        search_entry.bind('<KeyRelease>', do_search)

        # Add mapping button
        def add_mapping_click():
            unmatched_sel = unmatched_listbox.curselection()
            results_sel = results_listbox.curselection()

            if not unmatched_sel or not results_sel:
                messagebox.showwarning("Select Both", "Select a player from both lists to create a mapping.")
                return

            db_name = unmatched_listbox.get(unmatched_sel[0])
            rankings_entry = results_listbox.get(results_sel[0])
            # Extract name from "#{rank} {name}"
            rankings_name = rankings_entry.split(' ', 1)[1] if ' ' in rankings_entry else rankings_entry

            add_rankings_mapping(db_name, rankings_name)
            messagebox.showinfo("Mapping Added", f"Added mapping:\n\n'{db_name}'\n→\n'{rankings_name}'\n\nRe-run 'Download Top 1500' to apply.")

        add_btn = tk.Button(
            right_frame,
            text="Add Mapping (Select from both lists)",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            command=add_mapping_click,
            pady=8
        )
        add_btn.pack(fill=tk.X, pady=10)

        # Auto-fill search when selecting unmatched player
        def on_unmatched_select(event):
            sel = unmatched_listbox.curselection()
            if sel:
                name = unmatched_listbox.get(sel[0])
                # Use last name for search
                parts = name.split()
                if parts:
                    search_var.set(parts[-1] if len(parts) > 1 else parts[0])
                    do_search()

        unmatched_listbox.bind('<<ListboxSelect>>', on_unmatched_select)

    def _on_unranked_update_complete(self, dialog, stats):
        """Handle upcoming players update completion."""
        dialog.destroy()
        self._load_players()
        self._update_rankings_info()

        # Build details
        if stats.get('updates'):
            details = "\n".join([
                f"  • {u['player_name']}: Rank {u['ranking']}"
                for u in stats['updates'][:15]
            ])
            if len(stats['updates']) > 15:
                details += f"\n  ... and {len(stats['updates']) - 15} more"
        else:
            details = "No updates"

        doubles_info = f"\nDoubles excluded: {stats.get('doubles_skipped', 0)}" if stats.get('doubles_skipped', 0) > 0 else ""
        messagebox.showinfo(
            "Rankings Updated",
            f"Updated {stats.get('updated', 0)} players\n"
            f"Failed: {stats.get('failed', 0)}{doubles_info}\n\n"
            f"Updates:\n{details}"
        )

    def run(self):
        """Run the rankings manager window."""
        self.root.mainloop()


def open_rankings_manager(parent: tk.Tk = None):
    """Open the rankings manager window."""
    manager = RankingsManager(parent)
    if not parent:
        manager.run()
    return manager


if __name__ == "__main__":
    manager = RankingsManager()
    manager.run()
