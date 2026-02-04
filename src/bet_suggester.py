"""
Tennis Betting System - Bet Suggester
Find value bets from upcoming matches by comparing our probabilities to market odds
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Dict, List, Optional
import json

from config import (UI_COLORS, SURFACES, BETTING_SETTINGS, KELLY_STAKING, DB_PATH,
                     get_tour_level, calculate_bet_model, MODEL5_SETTINGS,
                     MODEL12_SETTINGS, check_m12_fade)
from database import db, TennisDatabase
from match_analyzer import MatchAnalyzer
from name_matcher import name_matcher
from te_import_dialog import open_te_import_dialog

# Try to import TennisAbstractScraper - may fail in frozen exe if selenium not available
try:
    from tennis_abstract_scraper import TennisAbstractScraper
    SCRAPER_AVAILABLE = True
except ImportError:
    TennisAbstractScraper = None
    SCRAPER_AVAILABLE = False

try:
    from cloud_sync import sync_bet_to_cloud
    CLOUD_SYNC_AVAILABLE = True
except ImportError:
    CLOUD_SYNC_AVAILABLE = False


class Tooltip:
    """Simple tooltip for tkinter widgets."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip, text=self.text, background="#333",
                        foreground="white", relief="solid", borderwidth=1,
                        font=("Segoe UI", 9), padx=8, pady=4, wraplength=300, justify=tk.LEFT)
        label.pack()

    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class TreeviewHeaderTooltip:
    """Tooltip for treeview column headers."""

    def __init__(self, treeview, column_tooltips: Dict[str, str]):
        self.treeview = treeview
        self.column_tooltips = column_tooltips
        self.tooltip = None
        self.current_column = None

        treeview.bind("<Motion>", self._on_motion)
        treeview.bind("<Leave>", self._hide)

    def _on_motion(self, event):
        # Check if we're in the header region (roughly first 25 pixels)
        if event.y > 25:
            self._hide()
            return

        # Determine which column we're over
        region = self.treeview.identify_region(event.x, event.y)
        if region != "heading":
            self._hide()
            return

        column = self.treeview.identify_column(event.x)
        # Convert #1, #2, etc. to column name
        try:
            col_index = int(column.replace("#", "")) - 1
            columns = self.treeview["columns"]
            if 0 <= col_index < len(columns):
                col_name = columns[col_index]
            else:
                self._hide()
                return
        except (ValueError, IndexError):
            self._hide()
            return

        # Check if this column has a tooltip
        if col_name not in self.column_tooltips:
            self._hide()
            return

        # Show tooltip if we moved to a new column
        if col_name != self.current_column:
            self._hide()
            self.current_column = col_name
            self._show(event.x_root, event.y_root, self.column_tooltips[col_name])

    def _show(self, x, y, text):
        self.tooltip = tk.Toplevel(self.treeview)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x + 10}+{y + 20}")

        label = tk.Label(self.tooltip, text=text, background="#333",
                        foreground="white", relief="solid", borderwidth=1,
                        font=("Segoe UI", 9), padx=8, pady=4, wraplength=350, justify=tk.LEFT)
        label.pack()

    def _hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
        self.current_column = None


# Tooltip definitions for metrics
METRIC_TOOLTIPS = {
    "Ranking": "Current ATP/WTA ranking and Elo rating. Higher Elo = stronger player. Large gaps favor the higher-ranked player.",
    "Form": "Recent performance score based on last 10 matches. Factors in wins/losses, opponent quality, and match significance.",
    "Surface": "Historical win rate on this surface type. Combines career stats with recent performance. Some players excel on specific surfaces.",
    "Head-to-Head": "Direct match record between these players. Recent H2H results weighted more heavily than older matches.",
    "Fatigue": "Rest and workload assessment. Factors in days since last match, matches in last 14/30 days, and match difficulty (duration, sets).",
    "Activity": "Player activity level based on recent match frequency. Returning/inactive players have unreliable rankings.",
    "Opp Quality": "Quality of recent opponents. Wins vs top players worth more, losses to low-ranked players penalized. Weighted by recency.",
    "Recency": "How recent the form data is. Matches in last 7 days weighted 100%, 7-30 days 70%, 30-90 days 40%, older 20%.",
    "Recent Loss": "Penalty for coming off a recent loss. Loss in last 3 days = -0.10, last 7 days = -0.05. 5-set losses add extra penalty.",
    "Momentum": "Tournament/surface momentum. Bonus for recent wins on the same surface type. Max +0.10 bonus.",
    "Perf Elo": "Performance Elo: results-based rating from the last 12 months. Shows how a player is actually performing vs their ATP ranking. Higher = outperforming their rank.",
}


class UnknownPlayerResolverDialog:
    """
    Dialog to resolve unknown players by matching them to database players
    or adding them as new players.
    """

    def __init__(self, parent, unknown_players: List[Dict], database: 'TennisDatabase'):
        """
        Args:
            parent: Parent tkinter window
            unknown_players: List of dicts with keys: player, match, stake, odds, bet_data,
                            match_id, player_position ('player1' or 'player2')
            database: TennisDatabase instance
        """
        self.parent = parent
        self.unknown_players = unknown_players
        self.db = database
        self.current_index = 0
        self.results = []  # List of (action, data) tuples

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Resolve Unknown Players")
        self.dialog.configure(bg=UI_COLORS["bg_dark"])
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 600) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self._build_ui()
        self._show_current_player()

    def _build_ui(self):
        """Build the dialog UI."""
        # Header
        self.header_label = tk.Label(
            self.dialog,
            text="Resolve Unknown Player (1 of X)",
            font=("Segoe UI", 14, "bold"),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"]
        )
        self.header_label.pack(pady=(15, 10))

        # Player info frame
        info_frame = tk.Frame(self.dialog, bg=UI_COLORS["bg_medium"], padx=15, pady=10)
        info_frame.pack(fill=tk.X, padx=20, pady=5)

        self.player_name_label = tk.Label(
            info_frame,
            text="Player Name",
            font=("Segoe UI", 12, "bold"),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["accent"]
        )
        self.player_name_label.pack(anchor=tk.W)

        self.match_label = tk.Label(
            info_frame,
            text="Match: ...",
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_secondary"]
        )
        self.match_label.pack(anchor=tk.W)

        self.bet_label = tk.Label(
            info_frame,
            text="Bet: ...",
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_secondary"]
        )
        self.bet_label.pack(anchor=tk.W)

        # Search frame
        search_frame = tk.Frame(self.dialog, bg=UI_COLORS["bg_dark"])
        search_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Label(
            search_frame,
            text="Search Database:",
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"]
        ).pack(side=tk.LEFT)

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search_changed)
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            insertbackground=UI_COLORS["text_primary"],
            width=40
        )
        self.search_entry.pack(side=tk.LEFT, padx=(10, 0))

        # Results frame
        results_frame = tk.Frame(self.dialog, bg=UI_COLORS["bg_dark"])
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        tk.Label(
            results_frame,
            text="Potential Matches:",
            font=("Segoe UI", 10, "bold"),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"]
        ).pack(anchor=tk.W)

        # Treeview for results
        columns = ("name", "ranking", "matches", "country")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=10)
        self.results_tree.heading("name", text="Name")
        self.results_tree.heading("ranking", text="Ranking")
        self.results_tree.heading("matches", text="Matches")
        self.results_tree.heading("country", text="Country")

        self.results_tree.column("name", width=250)
        self.results_tree.column("ranking", width=80)
        self.results_tree.column("matches", width=80)
        self.results_tree.column("country", width=80)

        self.results_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        self.results_tree.bind('<Double-1>', lambda e: self._use_selected())

        # Save mapping checkbox
        self.save_mapping_var = tk.BooleanVar(value=True)
        self.save_mapping_check = tk.Checkbutton(
            self.dialog,
            text="Save name mapping permanently (recommended)",
            variable=self.save_mapping_var,
            font=("Segoe UI", 9),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"],
            selectcolor=UI_COLORS["bg_medium"],
            activebackground=UI_COLORS["bg_dark"],
            activeforeground=UI_COLORS["text_primary"]
        )
        self.save_mapping_check.pack(pady=5)

        # Buttons frame
        btn_frame = tk.Frame(self.dialog, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        self.use_btn = tk.Button(
            btn_frame,
            text="Use Selected Player",
            command=self._use_selected,
            bg=UI_COLORS["success"],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=15, pady=8,
            cursor="hand2"
        )
        self.use_btn.pack(side=tk.LEFT, padx=5)

        self.add_new_btn = tk.Button(
            btn_frame,
            text="Add as New Player",
            command=self._add_new_player,
            bg=UI_COLORS["accent"],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=15, pady=8,
            cursor="hand2"
        )
        self.add_new_btn.pack(side=tk.LEFT, padx=5)

        self.skip_btn = tk.Button(
            btn_frame,
            text="Skip This Bet",
            command=self._skip_bet,
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            font=("Segoe UI", 10),
            padx=15, pady=8,
            cursor="hand2"
        )
        self.skip_btn.pack(side=tk.LEFT, padx=5)

        self.cancel_btn = tk.Button(
            btn_frame,
            text="Cancel All",
            command=self._cancel_all,
            bg=UI_COLORS["danger"],
            fg="white",
            font=("Segoe UI", 10),
            padx=15, pady=8,
            cursor="hand2"
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)

    def _show_current_player(self):
        """Display the current unknown player."""
        if self.current_index >= len(self.unknown_players):
            self.dialog.destroy()
            return

        player = self.unknown_players[self.current_index]
        total = len(self.unknown_players)

        self.header_label.config(
            text=f"Resolve Unknown Player ({self.current_index + 1} of {total})"
        )
        self.player_name_label.config(text=player['player'])
        self.match_label.config(text=f"Match: {player['match']}")
        self.bet_label.config(text=f"Bet: {player['stake']}u @ {player['odds']:.2f}")

        # Pre-populate search with player name
        self.search_var.set(player['player'])
        self._do_search()

    def _on_search_changed(self, *args):
        """Handle search text changes with debounce."""
        if hasattr(self, '_search_after'):
            self.dialog.after_cancel(self._search_after)
        self._search_after = self.dialog.after(300, self._do_search)

    def _do_search(self):
        """Perform the database search."""
        query = self.search_var.get().strip()
        if not query:
            return

        # Clear existing results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # Search database with fuzzy matching
        # First try exact/partial match
        results = self.db.search_players(query, limit=20)

        # Also try with surname only (last word)
        surname = query.split()[-1] if query else query
        if surname != query:
            surname_results = self.db.search_players(surname, limit=10)
            # Merge, avoiding duplicates
            seen_ids = {r['id'] for r in results}
            for r in surname_results:
                if r['id'] not in seen_ids:
                    results.append(r)

        # Sort by similarity to search query
        for r in results:
            r['_similarity'] = name_matcher.similarity_score(query, r['name'])
        results.sort(key=lambda x: x['_similarity'], reverse=True)

        # Display results
        for player in results[:15]:
            match_count = self.db.get_player_match_count(player['id'])
            self.results_tree.insert('', 'end', values=(
                player['name'],
                player.get('current_ranking') or '-',
                match_count,
                player.get('country') or '-'
            ), tags=(str(player['id']),))

    def _use_selected(self):
        """Use the selected player from the results."""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a player from the list.")
            return

        item = selection[0]
        tags = self.results_tree.item(item, 'tags')
        if not tags:
            return

        player_id = int(tags[0])
        player_name = self.results_tree.item(item, 'values')[0]
        current_player = self.unknown_players[self.current_index]
        betfair_name = current_player['player']

        # Save mapping if checkbox is checked
        if self.save_mapping_var.get():
            name_matcher.add_mapping(betfair_name, player_id)
            print(f"Saved mapping: '{betfair_name}' -> {player_id} ({player_name})")

        # Store result
        self.results.append({
            'action': 'matched',
            'bet_data': current_player['bet_data'],
            'player_id': player_id,
            'player_name': player_name,
            'match_id': current_player.get('match_id'),
            'player_position': current_player.get('player_position')
        })

        # Move to next player
        self.current_index += 1
        self._show_current_player()

    def _add_new_player(self):
        """Add the unknown player as a new player in the database."""
        current_player = self.unknown_players[self.current_index]
        betfair_name = current_player['player']

        # Show dialog to get player details
        add_dialog = tk.Toplevel(self.dialog)
        add_dialog.title("Add New Player")
        add_dialog.configure(bg=UI_COLORS["bg_dark"])
        add_dialog.geometry("400x300")
        add_dialog.transient(self.dialog)
        add_dialog.grab_set()

        # Center
        add_dialog.update_idletasks()
        x = self.dialog.winfo_x() + (self.dialog.winfo_width() - 400) // 2
        y = self.dialog.winfo_y() + (self.dialog.winfo_height() - 300) // 2
        add_dialog.geometry(f"+{x}+{y}")

        # Form
        form_frame = tk.Frame(add_dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(form_frame, text="Player Name:", bg=UI_COLORS["bg_dark"],
                 fg=UI_COLORS["text_primary"], font=("Segoe UI", 10)).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=betfair_name)
        name_entry = tk.Entry(form_frame, textvariable=name_var, width=30,
                              bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                              insertbackground=UI_COLORS["text_primary"])
        name_entry.grid(row=0, column=1, pady=5, padx=10)

        # Estimate ranking from odds
        odds = current_player['odds']
        estimated_rank = self._estimate_ranking_from_odds(odds)

        tk.Label(form_frame, text="Estimated Ranking:", bg=UI_COLORS["bg_dark"],
                 fg=UI_COLORS["text_primary"], font=("Segoe UI", 10)).grid(row=1, column=0, sticky=tk.W, pady=5)
        rank_var = tk.StringVar(value=str(estimated_rank) if estimated_rank else "")
        rank_entry = tk.Entry(form_frame, textvariable=rank_var, width=30,
                              bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                              insertbackground=UI_COLORS["text_primary"])
        rank_entry.grid(row=1, column=1, pady=5, padx=10)

        tk.Label(form_frame, text="Country (optional):", bg=UI_COLORS["bg_dark"],
                 fg=UI_COLORS["text_primary"], font=("Segoe UI", 10)).grid(row=2, column=0, sticky=tk.W, pady=5)
        country_var = tk.StringVar()
        country_entry = tk.Entry(form_frame, textvariable=country_var, width=30,
                                 bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                                 insertbackground=UI_COLORS["text_primary"])
        country_entry.grid(row=2, column=1, pady=5, padx=10)

        tk.Label(form_frame, text="Hand (L/R, optional):", bg=UI_COLORS["bg_dark"],
                 fg=UI_COLORS["text_primary"], font=("Segoe UI", 10)).grid(row=3, column=0, sticky=tk.W, pady=5)
        hand_var = tk.StringVar()
        hand_entry = tk.Entry(form_frame, textvariable=hand_var, width=30,
                              bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                              insertbackground=UI_COLORS["text_primary"])
        hand_entry.grid(row=3, column=1, pady=5, padx=10)

        # Note about new players
        tk.Label(form_frame, text="Note: New players will have no match history.\n"
                                  "The bet will proceed but analysis will be limited.",
                 bg=UI_COLORS["bg_dark"], fg=UI_COLORS["warning"],
                 font=("Segoe UI", 9), justify=tk.LEFT).grid(row=4, column=0, columnspan=2, pady=15)

        result = {'added': False}

        def do_add():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Name Required", "Please enter a player name.")
                return

            ranking = None
            if rank_var.get().strip():
                try:
                    ranking = int(rank_var.get().strip())
                except ValueError:
                    messagebox.showwarning("Invalid Ranking", "Ranking must be a number.")
                    return

            country = country_var.get().strip() or None
            hand = hand_var.get().strip().upper() or None
            if hand and hand not in ('L', 'R'):
                hand = None

            # Add to database
            new_id = self.db.add_player(name, ranking, country, hand)

            # Save mapping
            if self.save_mapping_var.get():
                name_matcher.add_mapping(betfair_name, new_id)
                print(f"Added new player and mapping: '{betfair_name}' -> {new_id} ({name})")

            result['added'] = True
            result['player_id'] = new_id
            result['player_name'] = name
            add_dialog.destroy()

        # Buttons
        btn_frame = tk.Frame(add_dialog, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        tk.Button(btn_frame, text="Add Player", command=do_add,
                  bg=UI_COLORS["success"], fg="white", font=("Segoe UI", 10, "bold"),
                  padx=15, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=add_dialog.destroy,
                  bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"], font=("Segoe UI", 10),
                  padx=15, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=5)

        add_dialog.wait_window()

        if result.get('added'):
            # Store result
            self.results.append({
                'action': 'added',
                'bet_data': current_player['bet_data'],
                'player_id': result['player_id'],
                'player_name': result['player_name'],
                'match_id': current_player.get('match_id'),
                'player_position': current_player.get('player_position')
            })

            # Move to next
            self.current_index += 1
            self._show_current_player()

    def _estimate_ranking_from_odds(self, odds: float) -> int:
        """Estimate a rough ranking from betting odds."""
        if not odds:
            return None
        # Simple heuristic: lower odds = better player
        if odds < 1.5:
            return 50
        elif odds < 2.0:
            return 100
        elif odds < 2.5:
            return 150
        elif odds < 3.0:
            return 200
        elif odds < 4.0:
            return 300
        else:
            return 500

    def _skip_bet(self):
        """Skip this bet without resolving the player."""
        current_player = self.unknown_players[self.current_index]
        self.results.append({
            'action': 'skipped',
            'bet_data': current_player['bet_data'],
            'player_name': current_player['player']
        })

        self.current_index += 1
        self._show_current_player()

    def _cancel_all(self):
        """Cancel the entire resolution process."""
        self.results = None
        self.dialog.destroy()

    def get_results(self) -> Optional[List[Dict]]:
        """
        Get the resolution results.
        Returns None if cancelled, otherwise list of result dicts.
        Each dict has 'action' ('matched', 'added', 'skipped') and relevant data.
        """
        self.dialog.wait_window()
        return self.results


class BetSuggester:
    """Find value betting opportunities."""

    def __init__(self, database: TennisDatabase = None):
        self.db = database or db
        self.analyzer = MatchAnalyzer(self.db)

    def _get_min_player_matches(self, match):
        """Get minimum match count between both players (for M5 data quality check)."""
        p1_id = match.get('player1_id')
        p2_id = match.get('player2_id')
        p1_count = db.get_player_match_count(p1_id) if p1_id else 0
        p2_count = db.get_player_match_count(p2_id) if p2_id else 0
        return min(p1_count, p2_count)

    def analyze_upcoming_match(self, match: Dict) -> Dict:
        """
        Analyze an upcoming match and determine value opportunities.
        """
        p1_id = match.get('player1_id')
        p2_id = match.get('player2_id')
        surface = match.get('surface', 'Hard')
        match_date = match.get('date')

        p1_odds = match.get('player1_odds')
        p2_odds = match.get('player2_odds')

        # Skip match if either player has odds below minimum (liquidity filter)
        # Exception: keep match if the other side has odds in M5 underdog range (>= 3.00)
        min_opponent_odds = KELLY_STAKING.get("min_opponent_odds", 1.10)
        m5_min_odds = MODEL5_SETTINGS.get("min_odds", 3.00) if MODEL5_SETTINGS.get("enabled") else 999
        p1_below = p1_odds and p1_odds < min_opponent_odds
        p2_below = p2_odds and p2_odds < min_opponent_odds
        if p1_below or p2_below:
            has_underdog = (p1_below and p2_odds and p2_odds >= m5_min_odds) or (p2_below and p1_odds and p1_odds >= m5_min_odds)
            if not has_underdog:
                return {
                    'match': match,
                    'analysis': {},
                    'p1_probability': 0.5,
                    'p2_probability': 0.5,
                    'confidence': 0,
                    'value_bets': [],
                    'p1_value': None,
                    'p2_value': None,
                    'skipped': 'low_opponent_odds',
                }

        # Get probability analysis (pass odds for WTA/unranked player estimation)
        analysis = self.analyzer.calculate_win_probability(
            p1_id, p2_id, surface, match_date, p1_odds, p2_odds,
            tournament=match.get('tournament')
        )

        result = {
            'match': match,
            'analysis': analysis,
            'p1_probability': analysis['p1_probability'],
            'p2_probability': analysis['p2_probability'],
            'confidence': analysis['confidence'],
            'value_bets': [],
            'p1_value': None,  # Always store both players' value analysis
            'p2_value': None,
        }

        # Extract serve data and activity data for edge modifiers
        serve_data = analysis.get('serve_data')
        activity_data = analysis.get('activity_data')

        # Check for value on P1
        if p1_odds:
            p1_value = self.analyzer.find_value(
                analysis['p1_probability'], p1_odds,
                player_name=match.get('player1_name', 'Player 1'),
                tournament=match.get('tournament'),
                surface=match.get('surface'),
                serve_data=serve_data, side='p1',
                activity_data=activity_data,
                weighted_advantage=analysis.get('weighted_advantage')
            )
            p1_value['player'] = match.get('player1_name', 'Player 1')
            p1_value['odds'] = p1_odds
            p1_value['selection'] = 'player1'
            # Add surface score for M11 detection (positive = favors P1)
            surface_factor = analysis.get('factors', {}).get('surface', {})
            p1_value['surface_score_for_pick'] = surface_factor.get('advantage', 0)
            result['p1_value'] = p1_value  # Always store
            if p1_value['is_value']:
                result['value_bets'].append(p1_value)

        # Check for value on P2
        if p2_odds:
            p2_value = self.analyzer.find_value(
                analysis['p2_probability'], p2_odds,
                player_name=match.get('player2_name', 'Player 2'),
                tournament=match.get('tournament'),
                surface=match.get('surface'),
                serve_data=serve_data, side='p2',
                activity_data=activity_data,
                weighted_advantage=analysis.get('weighted_advantage')
            )
            p2_value['player'] = match.get('player2_name', 'Player 2')
            p2_value['odds'] = p2_odds
            p2_value['selection'] = 'player2'
            # Add surface score for M11 detection (negate since P2 bet)
            surface_factor = analysis.get('factors', {}).get('surface', {})
            p2_value['surface_score_for_pick'] = -surface_factor.get('advantage', 0)
            result['p2_value'] = p2_value  # Always store
            if p2_value['is_value']:
                result['value_bets'].append(p2_value)

        # Set betting analysis
        set_probs = self.analyzer.calculate_set_probabilities(analysis['p1_probability'])
        result['set_probabilities'] = set_probs

        # ====================================================================
        # M12 (2-0 FADE) CHECK
        # If a value bet qualifies for Pure M3 or M5, and the opponent is a
        # heavy favourite (1.20-1.50), replace the bet with a 2-0 fade bet.
        # ====================================================================
        if MODEL12_SETTINGS.get("enabled", True) and result['value_bets']:
            transformed_bets = []
            for bet in result['value_bets']:
                # Calculate model for this bet
                models_str = calculate_bet_model(
                    bet.get('our_probability', 0.5),
                    bet.get('implied_probability', 0.5),
                    match.get('tournament', ''),
                    bet.get('odds'),
                    None,
                    serve_alignment=bet.get('serve_alignment'),
                    min_player_matches=self._get_min_player_matches(match),
                    activity_driven_edge=bet.get('activity_driven_edge', False),
                    activity_min_score=bet.get('activity_min_score'),
                    surface_score_for_pick=bet.get('surface_score_for_pick')
                )

                # Determine opponent info
                if bet.get('selection') == 'player1':
                    opponent_name = match.get('player2_name', 'Player 2')
                    opponent_match_odds = p2_odds
                    opponent_2_0_odds = match.get('p2_2_0_odds')
                else:
                    opponent_name = match.get('player1_name', 'Player 1')
                    opponent_match_odds = p1_odds
                    opponent_2_0_odds = match.get('p1_2_0_odds')

                # Check M12 trigger
                m12_check = check_m12_fade(models_str, opponent_match_odds, opponent_2_0_odds)

                if m12_check['triggers']:
                    if MODEL12_SETTINGS.get("replaces_original", True):
                        # Create transformed M12 bet
                        m12_bet = bet.copy()
                        m12_bet['player'] = opponent_name
                        m12_bet['odds'] = m12_check['odds']  # 2-0 odds
                        m12_bet['selection'] = 'player2' if bet.get('selection') == 'player1' else 'player1'
                        m12_bet['market_type'] = 'Set Handicap'
                        m12_bet['bet_type'] = '2-0'
                        m12_bet['is_m12_fade'] = True
                        m12_bet['m12_reason'] = m12_check['reason']
                        m12_bet['original_trigger'] = m12_check.get('original_trigger', '')
                        m12_bet['original_pick'] = bet.get('player')
                        m12_bet['original_odds'] = bet.get('odds')
                        m12_bet['original_models'] = models_str
                        # Recalculate implied prob and edge for the 2-0 market
                        m12_bet['implied_probability'] = 1 / m12_check['odds'] if m12_check['odds'] else 0
                        # Use estimated 71% win rate for favourite 2-0 when opp odds 1.20-1.50
                        m12_bet['our_probability'] = 0.71
                        m12_bet['edge'] = m12_bet['our_probability'] - m12_bet['implied_probability']
                        m12_bet['expected_value'] = m12_bet['edge'] * m12_check['odds']
                        transformed_bets.append(m12_bet)
                    else:
                        # Add M12 alongside original - keep the original bet
                        transformed_bets.append(bet)
                        # Create M12 fade bet too
                        m12_bet = bet.copy()
                        m12_bet['player'] = opponent_name
                        m12_bet['odds'] = m12_check['odds']  # 2-0 odds
                        m12_bet['selection'] = 'player2' if bet.get('selection') == 'player1' else 'player1'
                        m12_bet['market_type'] = 'Set Handicap'
                        m12_bet['bet_type'] = '2-0'
                        m12_bet['is_m12_fade'] = True
                        m12_bet['m12_reason'] = m12_check['reason']
                        m12_bet['original_trigger'] = m12_check.get('original_trigger', '')
                        m12_bet['original_pick'] = bet.get('player')
                        m12_bet['original_odds'] = bet.get('odds')
                        m12_bet['original_models'] = models_str
                        m12_bet['implied_probability'] = 1 / m12_check['odds'] if m12_check['odds'] else 0
                        m12_bet['our_probability'] = 0.71
                        m12_bet['edge'] = m12_bet['our_probability'] - m12_bet['implied_probability']
                        m12_bet['expected_value'] = m12_bet['edge'] * m12_check['odds']
                        transformed_bets.append(m12_bet)
                else:
                    # No M12, keep original bet
                    transformed_bets.append(bet)

            result['value_bets'] = transformed_bets

        return result

    def analyze_all_upcoming(self) -> List[Dict]:
        """
        Analyze all upcoming matches and return value opportunities.
        """
        matches = self.db.get_upcoming_matches(analyzed=False)
        results = []

        # Filter out matches in the past (more than 6 hours ago to allow for timezone differences)
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M")
        matches = [m for m in matches if m.get('date', '9999') >= cutoff]

        # Apply same minimum liquidity filter as the upcoming matches list
        MIN_MATCHED_LIQUIDITY = 25
        matches = [m for m in matches if (m.get('total_matched') or 0) >= MIN_MATCHED_LIQUIDITY]

        for match in matches:
            p1_id = match.get('player1_id')
            p2_id = match.get('player2_id')
            p1_name = match.get('player1_name', '')
            p2_name = match.get('player2_name', '')

            # Skip doubles matches
            if '/' in p1_name or '/' in p2_name:
                continue

            # Try to resolve missing player IDs using name matcher
            if not p1_id or not self.db.get_player(p1_id):
                mapped_id = name_matcher.get_db_id(p1_name)
                if mapped_id and self.db.get_player(mapped_id):
                    p1_id = mapped_id
                    match['player1_id'] = mapped_id

            if not p2_id or not self.db.get_player(p2_id):
                mapped_id = name_matcher.get_db_id(p2_name)
                if mapped_id and self.db.get_player(mapped_id):
                    p2_id = mapped_id
                    match['player2_id'] = mapped_id

            # Skip auto-created players (negative IDs = no real data, unreliable model output)
            if (p1_id and p1_id < 0) or (p2_id and p2_id < 0):
                continue

            # Now check if we have both player IDs
            if p1_id and p2_id:
                try:
                    analysis = self.analyze_upcoming_match(match)
                    results.append(analysis)
                    # Log every analysed match (bets and non-bets)
                    if not analysis.get('skipped'):
                        try:
                            self._log_match_analysis(analysis)
                        except Exception:
                            pass  # Don't break analysis flow
                except Exception as e:
                    print(f"Error analyzing match: {e}")

        # Sort by best value (highest EV)
        results.sort(key=lambda x: max(
            [v['expected_value'] for v in x['value_bets']] or [0]
        ), reverse=True)

        return results

    def _log_match_analysis(self, result: Dict):
        """Log a full match analysis to the match_analyses table."""
        match = result['match']
        analysis = result.get('analysis', {})
        factors = analysis.get('factors', {})

        # Extract factor advantages (-1 to +1, positive = favours P1)
        factor_data = {}
        for factor_name in ['form', 'surface', 'ranking', 'h2h', 'fatigue',
                            'recent_loss', 'momentum', 'performance_elo']:
            f = factors.get(factor_name, {})
            factor_data[f'factor_{factor_name}'] = f.get('advantage')

        # Extract ranking/elo from ranking factor data
        ranking_data = factors.get('ranking', {}).get('data', {})

        # Determine best value side
        p1_val = result.get('p1_value') or {}
        p2_val = result.get('p2_value') or {}
        p1_edge = p1_val.get('edge', 0) or 0
        p2_edge = p2_val.get('edge', 0) or 0

        if p1_edge >= p2_edge and p1_edge > 0:
            best_edge = p1_edge
            best_ev = p1_val.get('expected_value', 0)
            best_side = 'p1'
        elif p2_edge > 0:
            best_edge = p2_edge
            best_ev = p2_val.get('expected_value', 0)
            best_side = 'p2'
        else:
            best_edge = None
            best_ev = None
            best_side = None

        # Determine which models qualify for each side
        models = []
        for side, val in [('p1', p1_val), ('p2', p2_val)]:
            if val and val.get('is_value'):
                model = calculate_bet_model(
                    val.get('our_probability', 0.5),
                    val.get('implied_probability', 0.5),
                    match.get('tournament', ''),
                    val.get('odds'),
                    None,
                    serve_alignment=val.get('serve_alignment'),
                    min_player_matches=self._get_min_player_matches(match),
                    activity_driven_edge=val.get('activity_driven_edge', False),
                    activity_min_score=val.get('activity_min_score'),
                    surface_score_for_pick=None  # Not available at filter stage
                )
                if model and model != "None":
                    models.append(f"{side}:{model}")
        models_qualified = ','.join(models) if models else None

        data = {
            'match_date': match.get('date', '').split(' ')[0] if match.get('date') else None,
            'tournament': match.get('tournament'),
            'surface': match.get('surface'),
            'player1_name': match.get('player1_name'),
            'player2_name': match.get('player2_name'),
            'player1_id': match.get('player1_id'),
            'player2_id': match.get('player2_id'),
            'p1_odds': match.get('player1_odds'),
            'p2_odds': match.get('player2_odds'),
            'p1_probability': result.get('p1_probability'),
            'p2_probability': result.get('p2_probability'),
            'confidence': result.get('confidence'),
            'weighted_advantage': analysis.get('weighted_advantage'),
            'p1_rank': ranking_data.get('p1_rank'),
            'p2_rank': ranking_data.get('p2_rank'),
            'p1_elo': ranking_data.get('p1_elo'),
            'p2_elo': ranking_data.get('p2_elo'),
            'best_edge': best_edge,
            'best_ev': best_ev,
            'best_side': best_side,
            'models_qualified': models_qualified,
        }
        data.update(factor_data)

        # Look up serve stats for both players
        p1_serve = self.db.get_player_serve_stats(match.get('player1_id'))
        p2_serve = self.db.get_player_serve_stats(match.get('player2_id'))

        serve_map = {
            'first_serve_pct': 'serve_1st_pct',
            'first_serve_won_pct': 'serve_1st_won',
            'second_serve_won_pct': 'serve_2nd_won',
            'aces_per_match': 'aces_pm',
            'dfs_per_match': 'dfs_pm',
            'service_games_won_pct': 'svc_games_won',
            'return_1st_won_pct': 'return_1st_won',
            'return_2nd_won_pct': 'return_2nd_won',
            'bp_saved_pct': 'bp_saved',
            'bp_converted_pct': 'bp_converted',
            'return_games_won_pct': 'return_games_won',
        }
        for src_key, col_suffix in serve_map.items():
            data[f'p1_{col_suffix}'] = p1_serve.get(src_key) if p1_serve else None
            data[f'p2_{col_suffix}'] = p2_serve.get(src_key) if p2_serve else None

        # Extract dominance ratio and serve edge modifier data
        serve_data = result.get('analysis', {}).get('serve_data', {})
        data['p1_dominance_ratio'] = serve_data.get('p1_dr')
        data['p2_dominance_ratio'] = serve_data.get('p2_dr')

        # Get serve modifier from the best-value side
        best_val = p1_val if best_side == 'p1' else p2_val if best_side == 'p2' else {}
        data['serve_dr_gap'] = best_val.get('serve_dr_gap')
        data['serve_alignment'] = best_val.get('serve_alignment')
        data['serve_modifier'] = best_val.get('serve_modifier')

        # Activity data
        activity_data = result.get('analysis', {}).get('activity_data', {})
        p1_act = activity_data.get('p1', {})
        p2_act = activity_data.get('p2', {})
        data['p1_activity_score'] = p1_act.get('score')
        data['p2_activity_score'] = p2_act.get('score')
        data['activity_modifier'] = best_val.get('activity_modifier')

        self.db.log_match_analysis(data)

    def get_top_value_bets(self, min_ev: float = None, min_stake: float = 0.5) -> List[Dict]:
        """
        Get the best value bets from all upcoming matches.
        """
        min_ev = min_ev or BETTING_SETTINGS['min_ev_threshold']

        all_results = self.analyze_all_upcoming()
        value_bets = []

        for result in all_results:
            for bet in result['value_bets']:
                # Skip bets below minimum stake
                if bet.get('recommended_units', 0) < min_stake:
                    continue

                if bet['expected_value'] >= min_ev:
                    # Check if this is an M12 fade bet (already transformed)
                    if bet.get('is_m12_fade'):
                        model = f"Model 12 ({bet.get('original_trigger', 'fade')})"
                    else:
                        # Check if bet qualifies for any model
                        model = calculate_bet_model(
                            bet.get('our_probability', 0.5),
                            bet.get('implied_probability', 0.5),
                            result['match'].get('tournament', ''),
                            bet.get('odds'),
                            None,
                            serve_alignment=bet.get('serve_alignment'),
                            min_player_matches=self._get_min_player_matches(result['match']),
                            activity_driven_edge=bet.get('activity_driven_edge', False),
                            activity_min_score=bet.get('activity_min_score'),
                            surface_score_for_pick=None  # Not available at filter stage
                        )
                    if model == "None" or not model:
                        continue  # Skip bets that don't qualify for any model

                    bet['match_info'] = {
                        'tournament': result['match'].get('tournament'),
                        'date': result['match'].get('date'),
                        'round': result['match'].get('round'),
                        'surface': result['match'].get('surface'),
                        'player1': result['match'].get('player1_name'),
                        'player2': result['match'].get('player2_name'),
                    }
                    bet['confidence'] = result['confidence']
                    bet['our_p1_prob'] = result['p1_probability']
                    bet['our_p2_prob'] = result['p2_probability']
                    bet['model'] = model  # Store the model
                    # Include factor analysis for stake confidence adjustment
                    bet['factor_analysis'] = {
                        'factors': result.get('factors', {}),
                        'weighted_advantage': result.get('weighted_advantage', 0),
                    }
                    value_bets.append(bet)

        # Sort by EV
        value_bets.sort(key=lambda x: x['expected_value'], reverse=True)

        return value_bets


class BetSuggesterUI:
    """Tkinter UI for Bet Suggester."""

    def __init__(self, parent: tk.Tk = None, on_change_callback=None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Bet Suggester - Find Value Bets")
        self.root.configure(bg=UI_COLORS["bg_dark"])
        self.root.state('zoomed')  # Launch maximized

        self.on_change_callback = on_change_callback
        self.suggester = BetSuggester()
        self.players_cache = []
        self.scraper = TennisAbstractScraper() if SCRAPER_AVAILABLE else None

        self._setup_styles()
        self._build_ui()
        self._load_players()
        self._refresh_matches()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=UI_COLORS["bg_dark"])
        style.configure("Card.TFrame", background=UI_COLORS["bg_medium"])
        style.configure("Dark.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=UI_COLORS["bg_dark"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 16, "bold"))
        style.configure("Card.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 10))
        style.configure("Value.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["success"], font=("Segoe UI", 11, "bold"))
        style.configure("HighValue.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["warning"], font=("Segoe UI", 12, "bold"))

        # Treeview style
        style.configure("Treeview",
                       background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"],
                       fieldbackground=UI_COLORS["bg_medium"],
                       font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                       background=UI_COLORS["bg_light"],
                       foreground=UI_COLORS["text_primary"],
                       font=("Segoe UI", 10, "bold"))

    def _build_ui(self):
        """Build the main UI."""
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text="Bet Suggester", style="Title.TLabel").pack(side=tk.LEFT)

        # Action buttons
        btn_frame = ttk.Frame(header_frame, style="Dark.TFrame")
        btn_frame.pack(side=tk.RIGHT)

        add_match_btn = tk.Button(
            btn_frame,
            text="+ Add Match",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._add_match_dialog,
            padx=15,
            pady=5
        )
        add_match_btn.pack(side=tk.LEFT, padx=5)

        # Update Players button removed - now using GitHub data

        analyze_btn = tk.Button(
            btn_frame,
            text="Analyze All",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._analyze_all,
            padx=15,
            pady=5
        )
        analyze_btn.pack(side=tk.LEFT, padx=5)

        clear_btn = tk.Button(
            btn_frame,
            text="Clear Matches",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["danger"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._clear_matches,
            padx=15,
            pady=5
        )
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Filter button
        filter_btn = tk.Button(
            btn_frame,
            text="Filter",
            font=("Segoe UI", 10),
            fg="black",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._show_filter_dialog,
            padx=15,
            pady=5
        )
        filter_btn.pack(side=tk.LEFT, padx=5)

        # Filter settings (stored as instance variables)
        self.filter_settings = {
            'min_ev': 5,
            'max_ev': 500,
            'min_units': 0.5,
        }

        # Split view: Upcoming matches and Value bets
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel: Upcoming matches
        left_frame = ttk.Frame(paned, style="Dark.TFrame")
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Upcoming Matches", style="Dark.TLabel").pack(anchor=tk.W, pady=(0, 10))

        # Matches tree
        matches_frame = ttk.Frame(left_frame, style="Card.TFrame")
        matches_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("date", "time", "tournament", "player1", "player2", "surface", "liq", "p1_odds", "our_p1", "p1_ev", "p2_odds", "our_p2", "p2_ev", "status")
        self.matches_tree = ttk.Treeview(matches_frame, columns=columns, show="headings", height=20)

        # Configure headings with text and sort command
        heading_texts = {
            "date": "Date", "time": "Time", "tournament": "Tournament",
            "player1": "Player 1", "player2": "Player 2", "surface": "Surface",
            "liq": "Matched", "p1_odds": "P1 Odds", "our_p1": "Our P1", "p1_ev": "P1 EV",
            "p2_odds": "P2 Odds", "our_p2": "Our P2", "p2_ev": "P2 EV",
            "status": "Status"
        }
        for col in columns:
            self.matches_tree.heading(col, text=heading_texts.get(col, col),
                                      command=lambda c=col: self._sort_column(c, False))

        self.matches_tree.column("date", width=75)
        self.matches_tree.column("time", width=50)
        self.matches_tree.column("tournament", width=80)
        self.matches_tree.column("player1", width=90)
        self.matches_tree.column("player2", width=90)
        self.matches_tree.column("surface", width=45)
        self.matches_tree.column("liq", width=50)
        self.matches_tree.column("p1_odds", width=50)
        self.matches_tree.column("our_p1", width=45)
        self.matches_tree.column("p1_ev", width=45)
        self.matches_tree.column("p2_odds", width=50)
        self.matches_tree.column("our_p2", width=45)
        self.matches_tree.column("p2_ev", width=45)
        self.matches_tree.column("status", width=70)

        matches_scroll = ttk.Scrollbar(matches_frame, orient=tk.VERTICAL, command=self.matches_tree.yview)
        self.matches_tree.configure(yscrollcommand=matches_scroll.set)

        self.matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        matches_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to show match analysis
        self.matches_tree.bind('<Double-1>', self._on_match_double_click)

        # Add tooltips for column headers
        column_tooltips = {
            "status": (
                "Status Column Values:\n"
                "• ...  =  Calculating model odds\n"
                "• X% conf  =  Model confidence (higher is better)\n"
                "• X% conf*  =  Lower confidence (30-50%)\n"
                "• Rank only  =  Only ranking data available\n"
                "• Low data  =  Insufficient data for prediction\n"
                "• NO HISTORY  =  Neither player has match history\n"
                "• P1/P2 no hist  =  One player missing history\n"
                "• P1/P2 unknown  =  Player not found in database\n"
                "• Error  =  Analysis failed"
            ),
            "our_p1": "Our model's calculated odds for Player 1 based on all factors",
            "our_p2": "Our model's calculated odds for Player 2 based on all factors",
            "liq": (
                "Total Matched (£)\n"
                "Total amount already bet on this market.\n"
                "Higher = more market activity = more reliable odds.\n"
                "• <£100 = Very thin market (use caution)\n"
                "• £100-500 = Moderate activity\n"
                "• £500-2000 = Good activity\n"
                "• >£2000 = High activity (reliable)"
            ),
        }
        TreeviewHeaderTooltip(self.matches_tree, column_tooltips)

        # Store match data by tree item ID
        self.match_data_map = {}

        # Right panel: Value bets
        right_frame = ttk.Frame(paned, style="Dark.TFrame")
        paned.add(right_frame, weight=1)

        # Header with title and Add All button
        header_frame = ttk.Frame(right_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text="Value Bets Found", style="Dark.TLabel").pack(side=tk.LEFT)

        self.add_all_btn = tk.Button(
            header_frame,
            text="Add All to Tracker",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._add_all_to_tracker,
            padx=10,
            pady=3,
            state=tk.DISABLED
        )
        self.add_all_btn.pack(side=tk.RIGHT)

        # Sortable Treeview table for value bets
        table_frame = ttk.Frame(right_frame, style="Dark.TFrame")
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("tour", "time", "match", "selection", "type", "odds", "our_prob", "ev", "units", "conf", "serve", "models")
        self.value_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        # Configure columns with sorting
        col_config = [
            ("tour", "Tour", 70),
            ("time", "Time", 70),
            ("match", "Match", 140),
            ("selection", "Selection", 100),
            ("type", "Type", 45),
            ("odds", "Odds", 50),
            ("our_prob", "Our %", 50),
            ("ev", "EV", 50),
            ("units", "Units", 45),
            ("conf", "Conf", 40),
            ("serve", "Srv", 40),
            ("models", "Models", 70),
        ]

        for col_id, col_text, width in col_config:
            self.value_tree.heading(col_id, text=col_text,
                                    command=lambda c=col_id: self._sort_value_tree(c))
            self.value_tree.column(col_id, width=width, minwidth=width)

        # Make match column stretch
        self.value_tree.column("match", stretch=True)

        # Scrollbar for table
        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.value_tree.yview)
        self.value_tree.configure(yscrollcommand=tree_scroll.set)

        self.value_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to open match analysis
        self.value_tree.bind("<Double-1>", self._on_value_tree_double_click)

        # Bind right-click for context menu
        self.value_tree.bind("<Button-3>", self._on_value_tree_right_click)

        # Store current value bets data for sorting and bulk add
        self.current_value_bets = []
        self._sorted_column = None
        self._sort_reverse = False

        # Keep legacy value_frame for compatibility (hidden)
        self.value_canvas = tk.Canvas(right_frame, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        self.value_frame = ttk.Frame(self.value_canvas, style="Dark.TFrame")
        self._value_scroll_handler = lambda e: None  # Dummy handler

        # Summary stats at bottom
        self.summary_var = tk.StringVar(value="Add matches and click 'Analyze All' to find value bets")
        summary_label = ttk.Label(main_frame, textvariable=self.summary_var, style="Dark.TLabel")
        summary_label.pack(anchor=tk.W, pady=(10, 0))

    def _load_players(self):
        """Load players cache."""
        try:
            self.players_cache = db.get_all_players()
        except Exception as e:
            print(f"Error loading players: {e}")

    def _get_player_id(self, name: str) -> Optional[int]:
        """Get player ID from name."""
        for p in self.players_cache:
            if p['name'] == name:
                return p['id']
        # Try partial match
        for p in self.players_cache:
            if name.lower() in p['name'].lower():
                return p['id']
        return None

    def _refresh_matches(self):
        """Refresh the matches list - loads immediately, calculates odds in background."""
        self.matches_tree.delete(*self.matches_tree.get_children())
        self.match_data_map = {}

        matches = db.get_upcoming_matches()

        # First pass: load all matches immediately (no model odds yet)
        items_to_analyze = []
        for match in matches:
            # Extract date and time
            date_str = match.get('date', '')
            date_part = date_str[:10] if date_str else ''
            time_part = date_str[11:16] if len(date_str) > 11 else ''

            p1_name = match.get('player1_name', '')
            p2_name = match.get('player2_name', '')
            p1_id = match.get('player1_id')
            p2_id = match.get('player2_id')

            # Skip doubles matches completely
            if '/' in p1_name or '/' in p2_name:
                continue

            # Skip matches with low market activity (less than £25 matched)
            MIN_MATCHED_LIQUIDITY = 25
            total_matched = match.get('total_matched') or 0
            if total_matched < MIN_MATCHED_LIQUIDITY:
                continue

            # Skip matches where either player's odds are below minimum opponent odds
            # Exception: keep match if the other side has odds in M5 underdog range (>= 3.00)
            p1_odds_val = match.get('player1_odds') or 0
            p2_odds_val = match.get('player2_odds') or 0
            min_opponent_odds = KELLY_STAKING.get("min_opponent_odds", 1.10)
            m5_min_odds = MODEL5_SETTINGS.get("min_odds", 3.00) if MODEL5_SETTINGS.get("enabled") else 999
            p1_below = p1_odds_val > 0 and p1_odds_val < min_opponent_odds
            p2_below = p2_odds_val > 0 and p2_odds_val < min_opponent_odds
            if p1_below or p2_below:
                # Allow if the other side qualifies as a potential underdog bet
                has_underdog = (p1_below and p2_odds_val >= m5_min_odds) or (p2_below and p1_odds_val >= m5_min_odds)
                if not has_underdog:
                    continue

            # Try name_matcher to find correct player IDs if current ones have no history
            # BUT only replace if the original player ID doesn't exist in the database
            p1_history = 0
            p2_history = 0

            if p1_id:
                p1_exists = db.get_player(p1_id) is not None
                p1_history = db.get_player_match_count(p1_id)
                if p1_history == 0 and not p1_exists:
                    # Only try name_matcher if player doesn't exist in DB
                    mapped_id = name_matcher.get_db_id(p1_name)
                    if mapped_id and db.get_player(mapped_id):
                        p1_id = mapped_id
                        match['player1_id'] = mapped_id
                        p1_history = db.get_player_match_count(p1_id)

            if p2_id:
                p2_exists = db.get_player(p2_id) is not None
                p2_history = db.get_player_match_count(p2_id)
                if p2_history == 0 and not p2_exists:
                    # Only try name_matcher if player doesn't exist in DB
                    mapped_id = name_matcher.get_db_id(p2_name)
                    if mapped_id and db.get_player(mapped_id):
                        p2_id = mapped_id
                        match['player2_id'] = mapped_id
                        p2_history = db.get_player_match_count(p2_id)

            # Determine status based on player availability
            if not p1_id and not p2_id:
                status = "No players"
                our_p1_placeholder = ""
                our_p2_placeholder = ""
            elif not p1_id:
                status = "P1 unknown"
                our_p1_placeholder = ""
                our_p2_placeholder = ""
            elif not p2_id:
                status = "P2 unknown"
                our_p1_placeholder = ""
                our_p2_placeholder = ""
            else:
                # Check match history status
                if p1_history == 0 and p2_history == 0:
                    status = "NO HISTORY"
                elif p1_history == 0:
                    status = "P1 no hist"
                elif p2_history == 0:
                    status = "P2 no hist"
                else:
                    status = "..."
                our_p1_placeholder = "..."
                our_p2_placeholder = "..."

            # Show total matched (amount already bet on market - indicates reliability)
            total_matched = match.get('total_matched') or 0
            liq_display = f"{total_matched:.0f}" if total_matched else "-"

            item_id = self.matches_tree.insert("", tk.END, values=(
                date_part,
                time_part,
                match.get('tournament', ''),
                p1_name,
                p2_name,
                match.get('surface', ''),
                liq_display,
                match.get('player1_odds', ''),
                our_p1_placeholder,
                "",  # p1_ev placeholder
                match.get('player2_odds', ''),
                our_p2_placeholder,
                "",  # p2_ev placeholder
                status,
            ))
            self.match_data_map[item_id] = match

            # Queue for background analysis if we have both player IDs
            if p1_id and p2_id:
                items_to_analyze.append((item_id, match))

        # Second pass: calculate model odds in background thread
        if items_to_analyze:
            import threading
            threading.Thread(target=self._calculate_odds_background,
                           args=(items_to_analyze,), daemon=True).start()

    def _calculate_odds_background(self, items_to_analyze):
        """Calculate model odds and EVs in background and update UI."""
        for item_id, match in items_to_analyze:
            try:
                p1_id = match.get('player1_id')
                p2_id = match.get('player2_id')
                surface = match.get('surface', 'Hard')
                p1_odds = match.get('player1_odds')
                p2_odds = match.get('player2_odds')

                analysis = self.suggester.analyzer.calculate_win_probability(
                    p1_id, p2_id, surface, None, p1_odds, p2_odds,
                    tournament=match.get('tournament')
                )
                confidence = analysis.get('confidence', 0)

                our_p1_odds = ""
                our_p2_odds = ""
                p1_ev_str = ""
                p2_ev_str = ""
                status = "Low data"

                # Always show calculated odds, but indicate confidence level
                p1_prob = analysis.get('p1_probability', 0.5)
                p2_prob = analysis.get('p2_probability', 0.5)

                # Only show odds if we have a meaningful prediction (not just 50/50)
                if abs(p1_prob - 0.5) > 0.05 or confidence > 0.1:
                    if p1_prob > 0.01:
                        our_p1_odds = f"{1/p1_prob:.2f}"
                    if p2_prob > 0.01:
                        our_p2_odds = f"{1/p2_prob:.2f}"

                    if confidence >= 0.5:
                        status = f"{confidence*100:.0f}% conf"
                    elif confidence >= 0.3:
                        status = f"{confidence*100:.0f}% conf*"
                    else:
                        status = "Rank only"

                # Calculate EVs for both players
                if p1_odds:
                    p1_value = self.suggester.analyzer.find_value(p1_prob, float(p1_odds), log=False)
                    p1_ev = p1_value.get('expected_value', 0)
                    p1_ev_str = f"{p1_ev*100:+.0f}%" if p1_ev != 0 else "-"
                if p2_odds:
                    p2_value = self.suggester.analyzer.find_value(p2_prob, float(p2_odds), log=False)
                    p2_ev = p2_value.get('expected_value', 0)
                    p2_ev_str = f"{p2_ev*100:+.0f}%" if p2_ev != 0 else "-"

                # Update UI on main thread
                self.root.after(0, lambda iid=item_id, p1=our_p1_odds, p1ev=p1_ev_str, p2=our_p2_odds, p2ev=p2_ev_str, s=status:
                               self._update_odds_cell(iid, p1, p1ev, p2, p2ev, s))
            except Exception as e:
                # Clear the placeholder on error
                self.root.after(0, lambda iid=item_id:
                               self._update_odds_cell(iid, "", "", "", "", "Error"))

    def _update_odds_cell(self, item_id, our_p1_odds, p1_ev, our_p2_odds, p2_ev, status=""):
        """Update the model odds and EV cells for a specific row."""
        try:
            if self.matches_tree.exists(item_id):
                values = list(self.matches_tree.item(item_id, 'values'))
                values[8] = our_p1_odds   # our_p1 column
                values[9] = p1_ev         # p1_ev column
                values[11] = our_p2_odds  # our_p2 column
                values[12] = p2_ev        # p2_ev column
                if status:
                    values[13] = status   # status column
                self.matches_tree.item(item_id, values=values)
        except tk.TclError:
            pass  # Widget may have been destroyed

    def _sort_column(self, col, reverse):
        """Sort treeview by column."""
        data = [(self.matches_tree.set(item, col), item) for item in self.matches_tree.get_children('')]

        # Try numeric sort for odds columns
        if col in ('p1_odds', 'our_p1', 'p2_odds', 'our_p2'):
            try:
                data.sort(key=lambda x: float(x[0]) if x[0] else 999, reverse=reverse)
            except ValueError:
                data.sort(reverse=reverse)
        # Sort EV columns (handle +/-% format)
        elif col in ('p1_ev', 'p2_ev'):
            def ev_sort_key(x):
                val = x[0]
                if not val or val == '-':
                    return -999
                try:
                    return float(val.replace('%', '').replace('+', ''))
                except:
                    return -999
            data.sort(key=ev_sort_key, reverse=reverse)
        else:
            data.sort(reverse=reverse)

        for index, (val, item) in enumerate(data):
            self.matches_tree.move(item, '', index)

        # Toggle sort direction for next click
        self.matches_tree.heading(col, command=lambda: self._sort_column(col, not reverse))

    def _on_match_double_click(self, event):
        """Handle double-click on a match to show analysis."""
        selection = self.matches_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        match = self.match_data_map.get(item_id)

        if match:
            self._show_match_analysis(match)

    def _show_match_analysis(self, match: Dict):
        """Show detailed match analysis in a popup dialog - compact layout, no scrolling."""
        p1_name = match.get('player1_name', 'Player 1')
        p2_name = match.get('player2_name', 'Player 2')
        p1_id = match.get('player1_id')
        p2_id = match.get('player2_id')
        surface = match.get('surface', 'Hard')
        p1_odds = match.get('player1_odds')
        p2_odds = match.get('player2_odds')

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Match Analysis: {p1_name} vs {p2_name}")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)

        # Maximise the dialog window
        dialog.state('zoomed')

        # Scrollable main frame
        outer_frame = ttk.Frame(dialog, style="Dark.TFrame")
        outer_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(outer_frame, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        main_frame = ttk.Frame(canvas, style="Dark.TFrame", padding=10)
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        main_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget == dialog else None)

        # Header row: Tournament + Date + TE Import button
        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 5))
        header_text = f"{match.get('tournament', 'Unknown')} - {surface} - {match.get('date', 'TBD')}"
        ttk.Label(header_frame, text=header_text, style="Dark.TLabel",
                  font=("Segoe UI", 10)).pack(side=tk.LEFT)

        # Refresh button to reload data after import
        def refresh_analysis():
            dialog.destroy()
            self._show_match_analysis(match)

        refresh_btn = tk.Button(
            header_frame,
            text="Refresh",
            font=("Segoe UI", 9),
            fg="white",
            bg="#22c55e",  # Green
            relief=tk.FLAT,
            cursor="hand2",
            command=refresh_analysis,
            padx=10,
            pady=2
        )
        refresh_btn.pack(side=tk.RIGHT, padx=5)

        # TE Import button for quick data correction
        te_import_btn = tk.Button(
            header_frame,
            text="TE Import",
            font=("Segoe UI", 9),
            fg="white",
            bg="#06b6d4",  # Cyan
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: open_te_import_dialog(dialog),
            padx=10,
            pady=2
        )
        te_import_btn.pack(side=tk.RIGHT, padx=5)

        # Change Player button - to fix mismatched player IDs
        def show_change_player_dialog():
            self._show_change_player_dialog(match, dialog, refresh_analysis)

        change_player_btn = tk.Button(
            header_frame,
            text="Change Player",
            font=("Segoe UI", 9),
            fg="white",
            bg="#f59e0b",  # Amber
            relief=tk.FLAT,
            cursor="hand2",
            command=show_change_player_dialog,
            padx=10,
            pady=2
        )
        change_player_btn.pack(side=tk.RIGHT, padx=5)

        # Check if we have player IDs for analysis
        if not p1_id or not p2_id:
            ttk.Label(main_frame, text="Cannot analyze: Player IDs not found in database.",
                      style="Dark.TLabel", foreground=UI_COLORS["danger"]).pack(pady=20)
            return

        # Check match history for both players
        p1_matches = db.get_player_match_count(p1_id)
        p2_matches = db.get_player_match_count(p2_id)
        players_missing_history = []
        if p1_matches == 0:
            players_missing_history.append((p1_id, p1_name))
        if p2_matches == 0:
            players_missing_history.append((p2_id, p2_name))

        if players_missing_history:
            warning_frame = ttk.Frame(main_frame, style="Card.TFrame")
            warning_frame.pack(fill=tk.X, pady=(0, 5))

            warning_text = "WARNING: " + " | ".join([f"{name} has NO match history" for _, name in players_missing_history])
            tk.Label(warning_frame, text=warning_text,
                     font=("Segoe UI", 9, "bold"), fg=UI_COLORS["danger"],
                     bg=UI_COLORS["bg_medium"], padx=10, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Run analysis
        try:
            print(f"BET_SUGGESTER DEBUG: Analyzing match p1_id={p1_id} ({p1_name}) vs p2_id={p2_id} ({p2_name})")
            from match_analyzer import MatchAnalyzer
            analyzer = MatchAnalyzer()
            result = analyzer.calculate_win_probability(p1_id, p2_id, surface, None, p1_odds, p2_odds,
                                                       tournament=match.get('tournament'))
            p1_prob = result['p1_probability'] * 100
            p2_prob = result['p2_probability'] * 100

            # Calculate value bets to determine which player has value
            p1_has_value = False
            p2_has_value = False
            p1_ev = 0
            p2_ev = 0
            p1_units = 0
            p2_units = 0
            p1_tier = ""
            p2_tier = ""
            if p1_odds and p2_odds:
                # log=False since main analysis already logged this
                serve_data_raw = result.get('serve_data') or result.get('factors', {}).get('serve', {}).get('data')
                activity_data_raw = result.get('activity_data')
                p1_value = analyzer.find_value(result['p1_probability'], float(p1_odds), log=False,
                                                serve_data=serve_data_raw, side='p1', activity_data=activity_data_raw)
                p2_value = analyzer.find_value(result['p2_probability'], float(p2_odds), log=False,
                                                serve_data=serve_data_raw, side='p2', activity_data=activity_data_raw)
                p1_ev = p1_value['expected_value']
                p2_ev = p2_value['expected_value']
                p1_units = p1_value.get('recommended_units', 0)
                p2_units = p2_value.get('recommended_units', 0)
                p1_tier = p1_value.get('stake_tier', 'standard')
                p2_tier = p2_value.get('stake_tier', 'standard')
                # Determine which player has the better value bet (must have units)
                if (p1_ev > 0 and p1_units > 0) or (p2_ev > 0 and p2_units > 0):
                    if p1_ev > p2_ev and p1_units > 0:
                        p1_has_value = True
                    elif p2_units > 0:
                        p2_has_value = True

            # === CONTEXT WARNINGS (level mismatch, rust, near-breakout) ===
            context_warnings = result.get('context_warnings', [])
            if context_warnings:
                ctx_frame = ttk.Frame(main_frame, style="Dark.TFrame")
                ctx_frame.pack(fill=tk.X, pady=(0, 5))
                for warn in context_warnings:
                    tk.Label(ctx_frame, text=warn,
                             font=("Segoe UI", 9, "bold"), fg="#f59e0b",
                             bg=UI_COLORS["bg_dark"], padx=10, pady=3,
                             anchor="w").pack(fill=tk.X)

            # === TOP ROW: Probabilities + Bet Buttons ===
            top_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=8)
            top_frame.pack(fill=tk.X, pady=5)

            # Player 1 section (Blue)
            p1_section = ttk.Frame(top_frame, style="Card.TFrame")
            p1_section.pack(side=tk.LEFT, expand=True)
            p1_name_label = tk.Label(p1_section, text=p1_name, font=("Segoe UI", 10, "bold"),
                     fg=UI_COLORS["player1"], bg=UI_COLORS["bg_medium"], cursor="hand2")
            p1_name_label.pack()
            p1_name_label.bind("<Button-1>", lambda e, pid=p1_id, pname=p1_name: self._open_player_profile(dialog, pid, pname))
            tk.Label(p1_section, text=f"ID: {p1_id}", font=("Segoe UI", 7),
                     fg=UI_COLORS["text_secondary"], bg=UI_COLORS["bg_medium"]).pack()
            tk.Label(p1_section, text=f"{p1_prob:.1f}%", font=("Segoe UI", 18, "bold"),
                     fg=UI_COLORS["player1"], bg=UI_COLORS["bg_medium"]).pack()
            if p1_odds:
                p1_btn = tk.Button(p1_section, text=f"Back @ {float(p1_odds):.2f}",
                    font=("Segoe UI", 9, "bold"), fg="white", bg="#1976d2",
                    relief=tk.FLAT, cursor="hand2", padx=10, pady=3,
                    command=lambda: self._place_bet_from_analysis(match, p1_name, p1_odds, result['p1_probability']))
                p1_btn.pack(pady=(5, 0))
            # Value bet indicator for Player 1
            if p1_has_value:
                tier_labels = {"standard": "Standard", "confident": "Confident", "strong": "Strong"}
                tier_label = tier_labels.get(p1_tier, "")
                p1_units_str = f"{p1_units:.1f}".rstrip('0').rstrip('.') if p1_units % 1 else f"{int(p1_units)}"
                value_badge = tk.Label(p1_section, text=f"★ VALUE BET  {p1_units_str}U ({tier_label})",
                    font=("Segoe UI", 10, "bold"), fg="white", bg=UI_COLORS["success"],
                    padx=12, pady=4)
                value_badge.pack(pady=(8, 0))
            # Low data warning for Player 1
            if p1_matches < 10:
                low_data_label = tk.Label(p1_section, text=f"⚠ LOW DATA ({p1_matches} matches) - Click to edit",
                    font=("Segoe UI", 8), fg=UI_COLORS["danger"], bg=UI_COLORS["bg_medium"], cursor="hand2")
                low_data_label.pack(pady=(5, 0))
                low_data_label.bind("<Button-1>", lambda e, pid=p1_id, pname=p1_name: self._open_player_profile(dialog, pid, pname))

            # VS + Confidence
            vs_frame = ttk.Frame(top_frame, style="Card.TFrame")
            vs_frame.pack(side=tk.LEFT, padx=15)
            ttk.Label(vs_frame, text="vs", style="Card.TLabel", font=("Segoe UI", 12)).pack()
            ttk.Label(vs_frame, text=f"Conf: {result['confidence']*100:.0f}%",
                      style="Card.TLabel", font=("Segoe UI", 9)).pack()

            # Player 2 section (Yellow)
            p2_section = ttk.Frame(top_frame, style="Card.TFrame")
            p2_section.pack(side=tk.LEFT, expand=True)
            p2_name_label = tk.Label(p2_section, text=p2_name, font=("Segoe UI", 10, "bold"),
                     fg=UI_COLORS["player2"], bg=UI_COLORS["bg_medium"], cursor="hand2")
            p2_name_label.pack()
            p2_name_label.bind("<Button-1>", lambda e, pid=p2_id, pname=p2_name: self._open_player_profile(dialog, pid, pname))
            tk.Label(p2_section, text=f"ID: {p2_id}", font=("Segoe UI", 7),
                     fg=UI_COLORS["text_secondary"], bg=UI_COLORS["bg_medium"]).pack()
            tk.Label(p2_section, text=f"{p2_prob:.1f}%", font=("Segoe UI", 18, "bold"),
                     fg=UI_COLORS["player2"], bg=UI_COLORS["bg_medium"]).pack()
            if p2_odds:
                p2_btn = tk.Button(p2_section, text=f"Back @ {float(p2_odds):.2f}",
                    font=("Segoe UI", 9, "bold"), fg="black", bg="#ffc107",
                    relief=tk.FLAT, cursor="hand2", padx=10, pady=3,
                    command=lambda: self._place_bet_from_analysis(match, p2_name, p2_odds, result['p2_probability']))
                p2_btn.pack(pady=(5, 0))
            # Value bet indicator for Player 2
            if p2_has_value:
                tier_labels = {"standard": "Standard", "confident": "Confident", "strong": "Strong"}
                tier_label = tier_labels.get(p2_tier, "")
                p2_units_str = f"{p2_units:.1f}".rstrip('0').rstrip('.') if p2_units % 1 else f"{int(p2_units)}"
                value_badge = tk.Label(p2_section, text=f"★ VALUE BET  {p2_units_str}U ({tier_label})",
                    font=("Segoe UI", 10, "bold"), fg="white", bg=UI_COLORS["success"],
                    padx=12, pady=4)
                value_badge.pack(pady=(8, 0))
            # Low data warning for Player 2
            if p2_matches < 10:
                low_data_label = tk.Label(p2_section, text=f"⚠ LOW DATA ({p2_matches} matches) - Click to edit",
                    font=("Segoe UI", 8), fg=UI_COLORS["danger"], bg=UI_COLORS["bg_medium"], cursor="hand2")
                low_data_label.pack(pady=(5, 0))
                low_data_label.bind("<Button-1>", lambda e, pid=p2_id, pname=p2_name: self._open_player_profile(dialog, pid, pname))

            # === MIDDLE ROW: Factor Analysis (left) + Recent Matches (right) ===
            middle_frame = ttk.Frame(main_frame, style="Dark.TFrame")
            middle_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            # Factor Analysis on the left (original detailed table)
            self._create_analysis_table(middle_frame, result, p1_name, p2_name, p1_id, p2_id, surface, pack_side=tk.LEFT)

            # Recent Matches on the right
            recent_frame = ttk.Frame(middle_frame, style="Card.TFrame", padding=10)
            recent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

            ttk.Label(recent_frame, text="Recent Matches", style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

            matches_row = ttk.Frame(recent_frame, style="Card.TFrame")
            matches_row.pack(fill=tk.BOTH, expand=True)

            # Player 1 matches (Blue)
            p1_matches_frame = ttk.Frame(matches_row, style="Card.TFrame")
            p1_matches_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
            tk.Label(p1_matches_frame, text=p1_name[:20], font=("Segoe UI", 9, "bold"),
                     fg=UI_COLORS["player1"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)
            p1_matches = db.get_player_matches(p1_id, limit=10) if p1_id else []
            self._create_matches_list(p1_matches_frame, p1_matches, p1_id)

            # Player 2 matches (Yellow)
            p2_matches_frame = ttk.Frame(matches_row, style="Card.TFrame")
            p2_matches_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
            tk.Label(p2_matches_frame, text=p2_name[:20], font=("Segoe UI", 9, "bold"),
                     fg=UI_COLORS["player2"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)
            p2_matches = db.get_player_matches(p2_id, limit=10) if p2_id else []
            self._create_matches_list(p2_matches_frame, p2_matches, p2_id)

            # === BOTTOM ROW: Value Analysis (left) + Serve Stats (center) + Analysis Summary (right) ===
            bottom_frame = ttk.Frame(main_frame, style="Dark.TFrame")
            bottom_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            # Compute serve alignment for display
            serve_data_raw = result.get('serve_data') or result.get('factors', {}).get('serve', {}).get('data')
            if serve_data_raw and serve_data_raw.get('has_data'):
                serve_align_p1 = analyzer._calculate_serve_edge_modifier(serve_data_raw, 'p1')
                serve_align_p2 = analyzer._calculate_serve_edge_modifier(serve_data_raw, 'p2')
            else:
                serve_align_p1 = serve_align_p2 = None

            if p1_odds and p2_odds:
                # 3-column layout: Value | Serve Stats | Summary
                bottom_frame.columnconfigure(0, weight=1)
                bottom_frame.columnconfigure(1, weight=1)
                bottom_frame.columnconfigure(2, weight=1)
                bottom_frame.rowconfigure(0, weight=1)

                # Value Analysis on the left
                value_frame = ttk.Frame(bottom_frame, style="Card.TFrame", padding=10)
                value_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
                self._create_value_content(value_frame, result, p1_name, p2_name,
                                           float(p1_odds), float(p2_odds), analyzer)

                # Serve Stats in the center
                serve_frame = ttk.Frame(bottom_frame, style="Card.TFrame", padding=10)
                serve_frame.grid(row=0, column=1, sticky="nsew", padx=5)
                self._create_serve_stats_content(serve_frame, p1_id, p2_id, p1_name, p2_name,
                                                  serve_align_p1, serve_align_p2)

                # Analysis Summary on the right
                summary_frame = ttk.Frame(bottom_frame, style="Card.TFrame", padding=10)
                summary_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
                self._create_analysis_summary_detailed(summary_frame, result, p1_name, p2_name, p1_odds, p2_odds)
            else:
                # No odds — just show serve stats
                bottom_frame.columnconfigure(0, weight=1)
                bottom_frame.rowconfigure(0, weight=1)

                serve_frame = ttk.Frame(bottom_frame, style="Card.TFrame", padding=10)
                serve_frame.grid(row=0, column=0, sticky="nsew")
                self._create_serve_stats_content(serve_frame, p1_id, p2_id, p1_name, p2_name,
                                                  serve_align_p1, serve_align_p2)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Analysis error details:\n{error_details}")  # Print to console for debugging
            ttk.Label(main_frame, text=f"Analysis error: {str(e)}",
                      style="Dark.TLabel", foreground=UI_COLORS["danger"]).pack(pady=20)

    def _create_analysis_table_compact(self, parent, result: Dict, p1_name: str, p2_name: str):
        """Create a compact factor analysis table."""
        table_frame = ttk.Frame(parent, style="Card.TFrame", padding=8)
        table_frame.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(table_frame, text="Factor Analysis", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 3))

        factors = result.get('factors', {})
        factor_order = ['ranking', 'form', 'surface', 'h2h', 'fatigue',
                        'recent_loss', 'momentum', 'performance_elo']

        # Header row
        header_frame = ttk.Frame(table_frame, style="Card.TFrame")
        header_frame.pack(fill=tk.X)
        headers = ["Factor", p1_name[:8], p2_name[:8], "Adv", "Wt"]
        widths = [75, 50, 50, 40, 30]
        for h, w in zip(headers, widths):
            ttk.Label(header_frame, text=h, style="Card.TLabel",
                      font=("Segoe UI", 7, "bold"), width=w//7).pack(side=tk.LEFT, padx=1)

        # Data rows
        for factor_key in factor_order:
            if factor_key not in factors:
                continue
            factor_data = factors[factor_key]
            if not isinstance(factor_data, dict) or 'advantage' not in factor_data:
                continue

            row_frame = ttk.Frame(table_frame, style="Card.TFrame")
            row_frame.pack(fill=tk.X, pady=1)

            # Factor name
            display_name = factor_key.replace('_', ' ').title()[:10]
            ttk.Label(row_frame, text=display_name, style="Card.TLabel",
                      font=("Segoe UI", 7), width=10).pack(side=tk.LEFT, padx=1)

            # P1 value
            p1_val = self._get_factor_value(factor_key, factor_data, 'p1')
            ttk.Label(row_frame, text=p1_val[:7], style="Card.TLabel",
                      font=("Segoe UI", 7), width=7).pack(side=tk.LEFT, padx=1)

            # P2 value
            p2_val = self._get_factor_value(factor_key, factor_data, 'p2')
            ttk.Label(row_frame, text=p2_val[:7], style="Card.TLabel",
                      font=("Segoe UI", 7), width=7).pack(side=tk.LEFT, padx=1)

            # Advantage
            adv = factor_data.get('advantage', 0)
            adv_color = UI_COLORS["success"] if adv > 0 else UI_COLORS["danger"] if adv < 0 else UI_COLORS["text_secondary"]
            tk.Label(row_frame, text=f"{adv:+.2f}", font=("Segoe UI", 7),
                     fg=adv_color, bg=UI_COLORS["bg_medium"], width=5).pack(side=tk.LEFT, padx=1)

            # Weight
            weight = factor_data.get('weight', 0) * 100
            ttk.Label(row_frame, text=f"{weight:.0f}%", style="Card.TLabel",
                      font=("Segoe UI", 7), width=4).pack(side=tk.LEFT, padx=1)

    def _get_factor_value(self, factor_key: str, factor_data: Dict, player: str) -> str:
        """Get display value for a factor."""
        try:
            if factor_key == 'ranking':
                data = factor_data.get('data', {})
                rank = data.get(f'{player}_rank', '?')
                return f"#{rank}"
            elif factor_key == 'form':
                p_data = factor_data.get(player, {})
                return f"{p_data.get('wins', 0)}W-{p_data.get('losses', 0)}L"
            elif factor_key == 'surface':
                p_data = factor_data.get(player, {})
                rate = p_data.get('combined_win_rate', 0) * 100
                return f"{rate:.0f}%"
            elif factor_key == 'h2h':
                data = factor_data.get('data', {})
                return f"{data.get(f'{player}_wins', 0)}W"
            elif factor_key == 'fatigue':
                p_data = factor_data.get(player, {})
                return p_data.get('status', 'OK')[:7]
            elif factor_key == 'opponent_quality':
                p_data = factor_data.get(player, {})
                return f"{p_data.get('score', 0):.2f}"
            elif factor_key == 'recency':
                p_data = factor_data.get(player, {})
                return f"{p_data.get('score', 0):.2f}"
            elif factor_key == 'recent_loss':
                p_data = factor_data.get(player, {})
                return f"{p_data.get('penalty', 0):.2f}"
            elif factor_key == 'momentum':
                p_data = factor_data.get(player, {})
                return f"{p_data.get('bonus', 0):.2f}"
        except Exception:
            pass
        return "-"

    def _create_analysis_summary_compact(self, parent, result: Dict, p1_name: str, p2_name: str,
                                          p1_odds, p2_odds):
        """Create a compact narrative summary."""
        factors = result.get('factors', {})
        p1_prob = result['p1_probability'] * 100
        p2_prob = result['p2_probability'] * 100
        model_favors = p1_name if p1_prob > p2_prob else p2_name
        model_fav_prob = max(p1_prob, p2_prob)

        ttk.Label(parent, text="Analysis Summary", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        # Model vs Betfair comparison
        if p1_odds and p2_odds:
            try:
                p1_implied = (1 / float(p1_odds)) * 100
                p2_implied = (1 / float(p2_odds)) * 100
                betfair_favors = p1_name if p1_implied > p2_implied else p2_name
                betfair_fav_prob = max(p1_implied, p2_implied)

                # Model prediction
                model_frame = ttk.Frame(parent, style="Card.TFrame")
                model_frame.pack(fill=tk.X, pady=2)
                ttk.Label(model_frame, text="Model: ", style="Card.TLabel",
                          font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
                ttk.Label(model_frame, text=f"{p1_name} {p1_prob:.0f}% - {p2_name} {p2_prob:.0f}%",
                          style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)

                # Betfair odds
                betfair_frame = ttk.Frame(parent, style="Card.TFrame")
                betfair_frame.pack(fill=tk.X, pady=2)
                ttk.Label(betfair_frame, text="Betfair: ", style="Card.TLabel",
                          font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
                ttk.Label(betfair_frame, text=f"{p1_name} {p1_implied:.0f}% - {p2_name} {p2_implied:.0f}%",
                          style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)

                # Agreement/Disagreement
                agree_frame = ttk.Frame(parent, style="Card.TFrame")
                agree_frame.pack(fill=tk.X, pady=(5, 2))

                if model_favors == betfair_favors:
                    tk.Label(agree_frame, text=f"Agreement: Both favor {model_favors}",
                             font=("Segoe UI", 9), fg=UI_COLORS["text_secondary"],
                             bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)
                else:
                    tk.Label(agree_frame, text=f"DISAGREEMENT",
                             font=("Segoe UI", 9, "bold"), fg=UI_COLORS["warning"],
                             bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)
                    tk.Label(parent, text=f"  Model favors {model_favors} ({model_fav_prob:.0f}%)",
                             font=("Segoe UI", 8), fg=UI_COLORS["success"],
                             bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)
                    tk.Label(parent, text=f"  Betfair favors {betfair_favors} ({betfair_fav_prob:.0f}%)",
                             font=("Segoe UI", 8), fg=UI_COLORS["text_secondary"],
                             bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

            except (ValueError, ZeroDivisionError):
                pass

        # Key factors - grouped by who they favor
        key_factors_p1 = []
        key_factors_p2 = []
        for factor_key, factor_data in factors.items():
            if isinstance(factor_data, dict) and 'advantage' in factor_data and 'weight' in factor_data:
                contrib = abs(factor_data['advantage'] * factor_data['weight'])
                if contrib > 0.008:
                    name = factor_key.replace('_', ' ').title()
                    if factor_data['advantage'] > 0:
                        key_factors_p1.append((name, contrib))
                    else:
                        key_factors_p2.append((name, contrib))

        key_factors_p1.sort(key=lambda x: x[1], reverse=True)
        key_factors_p2.sort(key=lambda x: x[1], reverse=True)

        # Show factors for each player
        if key_factors_p1:
            ttk.Label(parent, text=f"Favoring {p1_name}:", style="Card.TLabel",
                      font=("Segoe UI", 8, "bold")).pack(anchor=tk.W, pady=(8, 0))
            factors_text = ", ".join([f[0] for f in key_factors_p1[:3]])
            ttk.Label(parent, text=f"  {factors_text}", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(anchor=tk.W)

        if key_factors_p2:
            ttk.Label(parent, text=f"Favoring {p2_name}:", style="Card.TLabel",
                      font=("Segoe UI", 8, "bold")).pack(anchor=tk.W, pady=(5, 0))
            factors_text = ", ".join([f[0] for f in key_factors_p2[:3]])
            ttk.Label(parent, text=f"  {factors_text}", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(anchor=tk.W)

    def _create_value_section_compact(self, parent, result: Dict, p1_name: str, p2_name: str,
                                       p1_odds: float, p2_odds: float, analyzer):
        """Create a compact value analysis section."""
        ttk.Label(parent, text="Value Analysis", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 3))

        serve_data_raw = result.get('serve_data') or result.get('factors', {}).get('serve', {}).get('data')
        activity_data_raw = result.get('activity_data')
        p1_value = analyzer.find_value(result['p1_probability'], p1_odds, log=False,
                                        serve_data=serve_data_raw, side='p1', activity_data=activity_data_raw)
        p2_value = analyzer.find_value(result['p2_probability'], p2_odds, log=False,
                                        serve_data=serve_data_raw, side='p2', activity_data=activity_data_raw)

        p1_implied = (1 / p1_odds) * 100
        p2_implied = (1 / p2_odds) * 100
        p1_prob = result['p1_probability'] * 100
        p2_prob = result['p2_probability'] * 100

        # Compact grid
        row1 = ttk.Frame(parent, style="Card.TFrame")
        row1.pack(fill=tk.X)
        ttk.Label(row1, text=f"{p1_name[:12]}: Odds {p1_odds:.2f} | Model {p1_prob:.0f}% vs Implied {p1_implied:.0f}%",
                  style="Card.TLabel", font=("Segoe UI", 7)).pack(side=tk.LEFT)

        ev1 = p1_value.get('expected_value', 0)
        ev1_color = UI_COLORS["success"] if ev1 > 0 else UI_COLORS["danger"]
        tk.Label(row1, text=f"EV: {ev1*100:+.1f}%", font=("Segoe UI", 7, "bold"),
                 fg=ev1_color, bg=UI_COLORS["bg_medium"]).pack(side=tk.RIGHT)

        row2 = ttk.Frame(parent, style="Card.TFrame")
        row2.pack(fill=tk.X)
        ttk.Label(row2, text=f"{p2_name[:12]}: Odds {p2_odds:.2f} | Model {p2_prob:.0f}% vs Implied {p2_implied:.0f}%",
                  style="Card.TLabel", font=("Segoe UI", 7)).pack(side=tk.LEFT)

        ev2 = p2_value.get('expected_value', 0)
        ev2_color = UI_COLORS["success"] if ev2 > 0 else UI_COLORS["danger"]
        tk.Label(row2, text=f"EV: {ev2*100:+.1f}%", font=("Segoe UI", 7, "bold"),
                 fg=ev2_color, bg=UI_COLORS["bg_medium"]).pack(side=tk.RIGHT)

        # Recommendation
        if ev1 > 0.05 or ev2 > 0.05:
            better = p1_name if ev1 > ev2 else p2_name
            better_ev = max(ev1, ev2)
            ttk.Label(parent, text=f"Value bet: {better} ({better_ev*100:.1f}% edge)",
                      style="Card.TLabel", font=("Segoe UI", 8, "bold"),
                      foreground=UI_COLORS["success"]).pack(anchor=tk.W, pady=(3, 0))

    def _create_matches_list_compact(self, parent, matches: list, player_id: int):
        """Create a very compact list of recent matches."""
        from datetime import datetime

        if not matches:
            ttk.Label(parent, text="No matches", style="Card.TLabel",
                      font=("Segoe UI", 7), foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W)
            return

        today = datetime.now()
        # Get canonical ID for comparison (handles aliased player IDs)
        player_canonical = db.get_canonical_id(player_id)

        for match in matches[:5]:  # Limit to 5
            # Compare using canonical IDs
            winner_canonical = db.get_canonical_id(match.get('winner_id'))
            won = winner_canonical == player_canonical
            result_color = UI_COLORS["success"] if won else UI_COLORS["danger"]
            result_text = "W" if won else "L"

            opp_id = match.get('loser_id') if won else match.get('winner_id')
            opp_name = "Unknown"
            if opp_id:
                opp = db.get_player(opp_id)
                if opp:
                    opp_name = opp.get('name', 'Unknown')
                    # Shorten: "Novak Djokovic" -> "Djokovic"
                    if ' ' in opp_name:
                        opp_name = opp_name.split()[-1]

            # Days ago
            date_str = match.get('date', '')[:10]
            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
                days_text = f"{days_ago}d"
            except:
                days_text = "?"

            # Compact line: "W Djokovic (3d)"
            line_text = f"{result_text} {opp_name[:10]} ({days_text})"
            tk.Label(parent, text=line_text, font=("Segoe UI", 7),
                     fg=result_color, bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

    def _create_recent_matches_section(self, parent, p1_id: int, p1_name: str, p2_id: int, p2_name: str):
        """Create section showing recent matches for both players."""
        matches_frame = ttk.Frame(parent, style="Card.TFrame", padding=15)
        matches_frame.pack(fill=tk.X, pady=10)

        ttk.Label(matches_frame, text="Recent Matches", style="Card.TLabel",
                  font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))

        # Side by side layout
        columns_frame = ttk.Frame(matches_frame, style="Card.TFrame")
        columns_frame.pack(fill=tk.X)

        # Player 1 matches
        p1_frame = ttk.Frame(columns_frame, style="Card.TFrame")
        p1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(p1_frame, text=p1_name, style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        p1_matches = db.get_player_matches(p1_id, limit=5) if p1_id else []
        self._create_matches_list(p1_frame, p1_matches, p1_id)

        # Player 2 matches
        p2_frame = ttk.Frame(columns_frame, style="Card.TFrame")
        p2_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        ttk.Label(p2_frame, text=p2_name, style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        p2_matches = db.get_player_matches(p2_id, limit=5) if p2_id else []
        self._create_matches_list(p2_frame, p2_matches, p2_id)

    def _create_matches_list(self, parent, matches: list, player_id: int):
        """Create a compact list of matches with days ago indicator."""
        from datetime import datetime

        if not matches:
            ttk.Label(parent, text="No recent matches found", style="Card.TLabel",
                      foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=5)
            return

        today = datetime.now()
        # Get canonical ID for comparison (handles aliased player IDs)
        player_canonical = db.get_canonical_id(player_id)

        for match in matches:
            match_frame = ttk.Frame(parent, style="Card.TFrame")
            match_frame.pack(fill=tk.X, pady=2)

            # Determine if player won (compare using canonical IDs)
            winner_canonical = db.get_canonical_id(match.get('winner_id'))
            won = winner_canonical == player_canonical
            result_color = UI_COLORS["success"] if won else UI_COLORS["danger"]
            result_text = "W" if won else "L"

            # Get opponent info
            if won:
                opp_id = match.get('loser_id')
            else:
                opp_id = match.get('winner_id')

            # Try to get opponent name and ranking from database
            opp_name = "Unknown"
            opp_rank = None
            if opp_id:
                opp_player = db.get_player(opp_id)
                if opp_player:
                    opp_name = opp_player.get('name', 'Unknown')
                    opp_rank = opp_player.get('current_ranking')
                    # Shorten name if needed
                    if len(opp_name) > 20:
                        parts = opp_name.split()
                        if len(parts) > 1:
                            opp_name = f"{parts[0][0]}. {parts[-1]}"

            # Calculate days ago
            date_str = match.get('date', '')[:10] if match.get('date') else ''
            days_ago = '?'
            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except:
                pass

            # Score - format tiebreakers properly
            score = self._format_score(match.get('score', ''))

            # Surface
            surface = match.get('surface', '')[:1] if match.get('surface') else ''

            # Format: [W/L] vs Opponent (#Rank) (Score) - Xd ago [S]
            tk.Label(match_frame, text=result_text, fg=result_color, bg=UI_COLORS["bg_medium"],
                     font=("Segoe UI", 8, "bold"), width=2).pack(side=tk.LEFT)

            # Build match text with opponent rank
            match_text = f"vs {opp_name}"
            if opp_rank:
                match_text += f" (#{opp_rank})"
            if score:
                match_text += f" {score}"

            ttk.Label(match_frame, text=match_text, style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(5, 0))

            # Days ago and surface on right
            meta_text = f"{days_ago}d"
            if surface:
                meta_text += f" [{surface}]"

            # Color code recency
            if isinstance(days_ago, int):
                if days_ago <= 7:
                    days_color = UI_COLORS["success"]  # Recent = good data
                elif days_ago <= 30:
                    days_color = UI_COLORS["text_secondary"]
                else:
                    days_color = UI_COLORS["warning"]  # Old data
            else:
                days_color = UI_COLORS["text_secondary"]

            tk.Label(match_frame, text=meta_text, fg=days_color, bg=UI_COLORS["bg_medium"],
                     font=("Segoe UI", 8)).pack(side=tk.RIGHT)

    def _format_score(self, score: str) -> str:
        """Format score to properly display tiebreakers.

        Converts scores like '7-63, 6-3' to '7-6(3), 6-3'
        and '62-7, 6-4' to '6-7(2), 6-4'
        """
        if not score:
            return score

        import re

        sets = score.split(', ')
        formatted_sets = []

        for s in sets:
            s = s.strip()
            # Check for tiebreaker patterns like "7-63" or "63-7"
            # A tiebreaker set is when one side has 7 and the score looks odd

            match = re.match(r'^(\d+)-(\d+)$', s)
            if match:
                left, right = match.groups()

                # Check if it's a tiebreaker (7-6x or 6x-7)
                if left == '7' and len(right) > 1 and right.startswith('6'):
                    # 7-63 -> 7-6(3)
                    tb_score = right[1:]
                    formatted_sets.append(f"7-6({tb_score})")
                elif right == '7' and len(left) > 1 and left.startswith('6'):
                    # 63-7 -> 6-7(3)
                    tb_score = left[1:]
                    formatted_sets.append(f"6-7({tb_score})")
                else:
                    formatted_sets.append(s)
            else:
                formatted_sets.append(s)

        return ', '.join(formatted_sets)

    def _show_fatigue_details(self, fatigue_data: Dict, p1_name: str, p2_name: str):
        """Show detailed fatigue breakdown in a popup."""
        p1 = fatigue_data.get('p1', {})
        p2 = fatigue_data.get('p2', {})

        popup = tk.Toplevel(self.root)
        popup.title("Fatigue Breakdown")
        popup.geometry("750x650")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(popup, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(popup, orient=tk.VERTICAL, command=canvas.yview)
        content = ttk.Frame(canvas, style="Card.TFrame", padding=20)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=content, anchor=tk.NW)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(content, text="Fatigue Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="Raw metrics → Score calculation",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Create unified table
        table = ttk.Frame(content, style="Card.TFrame")
        table.pack(fill=tk.X, pady=10)

        # Header row
        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(table, text=header, style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)

        # Get values
        p1_rust = p1.get('rust_penalty', 0)
        p2_rust = p2.get('rust_penalty', 0)

        # Unified rows: section headers, metrics, and calculated scores together
        rows = [
            # REST SECTION
            ("header", "REST COMPONENT", "", ""),
            ("metric", "  Days Since Last Match", str(p1.get('days_since_match', '?')), str(p2.get('days_since_match', '?'))),
            ("sub", "  └ Rust Penalty", f"-{p1_rust:.1f}" if p1_rust > 0 else "0", f"-{p2_rust:.1f}" if p2_rust > 0 else "0"),
            ("score", "  → Rest Score", f"{p1.get('rest_component', 0):.1f} / 40", f"{p2.get('rest_component', 0):.1f} / 40"),

            # WORKLOAD SECTION
            ("header", "WORKLOAD COMPONENT", "", ""),
            ("metric", "  Matches (7 days)", str(p1.get('matches_7d', 0)), str(p2.get('matches_7d', 0))),
            ("metric", "  Matches (14 days)", str(p1.get('matches_14d', 0)), str(p2.get('matches_14d', 0))),
            ("metric", "  Matches (30 days)", str(p1.get('matches_30d', 0)), str(p2.get('matches_30d', 0))),
            ("metric", "  Difficulty (7 days)", f"{p1.get('difficulty_7d', 0):.1f} pts", f"{p2.get('difficulty_7d', 0):.1f} pts"),
            ("score", "  → Workload Score", f"{p1.get('workload_component', 0):.1f} / 40", f"{p2.get('workload_component', 0):.1f} / 40"),

            # BASE & TOTAL
            ("header", "BASE FITNESS", "", ""),
            ("score", "  → Base Score", "20 / 20", "20 / 20"),

            ("divider", "", "", ""),
            ("total", "TOTAL SCORE", f"{p1.get('score', 0):.1f} / 100", f"{p2.get('score', 0):.1f} / 100"),
            ("status", "Status", p1.get('status', '?'), p2.get('status', '?')),
        ]

        for row_idx, (row_type, label, v1, v2) in enumerate(rows, 1):
            if row_type == "header":
                # Section header - bold, with top padding
                ttk.Label(table, text=label, style="Card.TLabel",
                          font=("Segoe UI", 9, "bold")).grid(row=row_idx, column=0, padx=10, pady=(10, 2), sticky=tk.W)
            elif row_type == "metric":
                # Raw metric - normal
                ttk.Label(table, text=label, style="Card.TLabel",
                          foreground=UI_COLORS["text_secondary"]).grid(row=row_idx, column=0, padx=10, pady=1, sticky=tk.W)
                ttk.Label(table, text=v1, style="Card.TLabel",
                          foreground=UI_COLORS["text_secondary"]).grid(row=row_idx, column=1, padx=10, pady=1, sticky=tk.W)
                ttk.Label(table, text=v2, style="Card.TLabel",
                          foreground=UI_COLORS["text_secondary"]).grid(row=row_idx, column=2, padx=10, pady=1, sticky=tk.W)
            elif row_type == "sub":
                # Sub-item (like rust penalty) - muted
                ttk.Label(table, text=label, style="Card.TLabel",
                          foreground=UI_COLORS["text_secondary"]).grid(row=row_idx, column=0, padx=10, pady=1, sticky=tk.W)
                p1_color = "#f87171" if p1_rust > 0 else UI_COLORS["text_secondary"]
                p2_color = "#f87171" if p2_rust > 0 else UI_COLORS["text_secondary"]
                ttk.Label(table, text=v1, style="Card.TLabel",
                          foreground=p1_color).grid(row=row_idx, column=1, padx=10, pady=1, sticky=tk.W)
                ttk.Label(table, text=v2, style="Card.TLabel",
                          foreground=p2_color).grid(row=row_idx, column=2, padx=10, pady=1, sticky=tk.W)
            elif row_type == "score":
                # Calculated score - accent color
                ttk.Label(table, text=label, style="Card.TLabel",
                          foreground="#6366f1").grid(row=row_idx, column=0, padx=10, pady=2, sticky=tk.W)
                ttk.Label(table, text=v1, style="Card.TLabel",
                          foreground="#6366f1").grid(row=row_idx, column=1, padx=10, pady=2, sticky=tk.W)
                ttk.Label(table, text=v2, style="Card.TLabel",
                          foreground="#6366f1").grid(row=row_idx, column=2, padx=10, pady=2, sticky=tk.W)
            elif row_type == "divider":
                # Visual separator
                ttk.Separator(table, orient="horizontal").grid(row=row_idx, column=0, columnspan=3, sticky="ew", pady=8)
            elif row_type == "total":
                # Total score - bold and prominent
                ttk.Label(table, text=label, style="Card.TLabel",
                          font=("Segoe UI", 10, "bold")).grid(row=row_idx, column=0, padx=10, pady=3, sticky=tk.W)
                ttk.Label(table, text=v1, style="Card.TLabel",
                          font=("Segoe UI", 10, "bold"), foreground="#4ade80").grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
                ttk.Label(table, text=v2, style="Card.TLabel",
                          font=("Segoe UI", 10, "bold"), foreground="#4ade80").grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)
            elif row_type == "status":
                # Status row
                ttk.Label(table, text=label, style="Card.TLabel").grid(row=row_idx, column=0, padx=10, pady=2, sticky=tk.W)
                ttk.Label(table, text=v1, style="Card.TLabel").grid(row=row_idx, column=1, padx=10, pady=2, sticky=tk.W)
                ttk.Label(table, text=v2, style="Card.TLabel").grid(row=row_idx, column=2, padx=10, pady=2, sticky=tk.W)

        # Difficulty scale explanation
        scale_frame = ttk.Frame(content, style="Card.TFrame")
        scale_frame.pack(fill=tk.X, pady=(15, 10))

        ttk.Label(scale_frame, text="Match Difficulty Scale:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        scale_text = "0.5 pts = Walkover/Retirement  |  1.0 pts = Quick 2-setter  |  2.0 pts = Competitive 3-setter  |  3.0 pts = Marathon 5-setter"
        ttk.Label(scale_frame, text=scale_text, style="Card.TLabel",
                  foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(5, 0))

        # Recent matches for both players (side by side)
        matches_frame = ttk.Frame(content, style="Card.TFrame")
        matches_frame.pack(fill=tk.X, pady=(15, 0))

        ttk.Label(matches_frame, text="Recent Matches (with difficulty)", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))

        columns = ttk.Frame(matches_frame, style="Card.TFrame")
        columns.pack(fill=tk.X)

        # Get player IDs from the database by searching names
        p1_id = None
        p2_id = None
        for p in self.players_cache:
            if p['name'] == p1_name:
                p1_id = p['id']
            if p['name'] == p2_name:
                p2_id = p['id']

        # Player 1 column
        p1_col = ttk.Frame(columns, style="Card.TFrame")
        p1_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        ttk.Label(p1_col, text=p1_name, style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        if p1_id:
            p1_matches = db.get_player_matches(p1_id, limit=5)
            self._create_fatigue_matches_list(p1_col, p1_matches, p1_id)

        # Player 2 column
        p2_col = ttk.Frame(columns, style="Card.TFrame")
        p2_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        ttk.Label(p2_col, text=p2_name, style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        if p2_id:
            p2_matches = db.get_player_matches(p2_id, limit=5)
            self._create_fatigue_matches_list(p2_col, p2_matches, p2_id)

        # Close button
        close_btn = tk.Button(content, text="Close", font=("Segoe UI", 10), fg="white",
                             bg=UI_COLORS["accent"], relief=tk.FLAT, cursor="hand2",
                             command=popup.destroy, padx=15, pady=5)
        close_btn.pack(pady=(20, 0))

    def _create_fatigue_matches_list(self, parent, matches: list, player_id: int):
        """Create matches list with difficulty indicators for fatigue popup."""
        from match_analyzer import MatchAnalyzer
        analyzer = MatchAnalyzer()

        if not matches:
            ttk.Label(parent, text="No recent matches", style="Card.TLabel",
                      foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W)
            return

        # Get canonical ID for comparison (handles aliased player IDs)
        player_canonical = db.get_canonical_id(player_id)

        for match in matches:
            match_frame = ttk.Frame(parent, style="Card.TFrame")
            match_frame.pack(fill=tk.X, pady=2)

            # Compare using canonical IDs
            winner_canonical = db.get_canonical_id(match.get('winner_id'))
            won = winner_canonical == player_canonical
            result_color = UI_COLORS["success"] if won else UI_COLORS["danger"]

            # Calculate difficulty
            difficulty = analyzer.calculate_match_difficulty(match, player_id)
            diff_color = UI_COLORS["warning"] if difficulty >= 2.0 else UI_COLORS["text_secondary"]

            # Get opponent
            opp_id = match.get('loser_id') if won else match.get('winner_id')
            opp_name = "Unknown"
            if opp_id:
                opp = db.get_player(opp_id)
                if opp:
                    opp_name = opp.get('name', 'Unknown')
                    if len(opp_name) > 12:
                        parts = opp_name.split()
                        opp_name = f"{parts[0][0]}. {parts[-1]}" if len(parts) > 1 else opp_name[:12]

            date_str = match.get('date', '')[:10]
            score = match.get('score', '')[:10]

            # W/L indicator
            tk.Label(match_frame, text="W" if won else "L", fg=result_color,
                     bg=UI_COLORS["bg_medium"], font=("Segoe UI", 8, "bold"), width=2).pack(side=tk.LEFT)

            # Match info
            ttk.Label(match_frame, text=f"vs {opp_name} ({score})", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=5)

            # Difficulty on right
            tk.Label(match_frame, text=f"{difficulty:.1f}", fg=diff_color,
                     bg=UI_COLORS["bg_medium"], font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT)

    def _show_ranking_details(self, ranking_data: Dict, p1_name: str, p2_name: str):
        """Show detailed ranking breakdown in a popup."""
        data = ranking_data.get('data', {})

        popup = tk.Toplevel(self.root)
        popup.title("Ranking Breakdown")
        popup.geometry("650x500")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        content = ttk.Frame(popup, style="Card.TFrame", padding=20)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(content, text="Ranking Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="Compares player rankings using Elo conversion",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Main comparison table
        table = ttk.Frame(content, style="Card.TFrame")
        table.pack(fill=tk.X, pady=10)

        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(table, text=header, style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)

        # Data rows
        p1_rank = data.get('p1_rank', '?')
        p2_rank = data.get('p2_rank', '?')
        p1_est = "~" if data.get('p1_estimated') else ""
        p2_est = "~" if data.get('p2_estimated') else ""

        rows = [
            ("Current Rank", f"{p1_est}#{p1_rank}", f"{p2_est}#{p2_rank}"),
            ("Elo Rating", f"{data.get('p1_elo', 0):.0f}", f"{data.get('p2_elo', 0):.0f}"),
            ("Trajectory", f"{data.get('p1_trajectory', 0):+.2f}", f"{data.get('p2_trajectory', 0):+.2f}"),
        ]

        for row_idx, (label, v1, v2) in enumerate(rows, 1):
            ttk.Label(table, text=label, style="Card.TLabel").grid(row=row_idx, column=0, padx=10, pady=3, sticky=tk.W)
            ttk.Label(table, text=v1, style="Card.TLabel").grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
            ttk.Label(table, text=v2, style="Card.TLabel").grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)

        # Elo Formula explanation
        formula_frame = ttk.Frame(content, style="Card.TFrame")
        formula_frame.pack(fill=tk.X, pady=(15, 10))

        ttk.Label(formula_frame, text="Elo Conversion Formula:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(formula_frame, text="Elo = 2500 - 150 * log2(rank)", style="Card.TLabel",
                  foreground=UI_COLORS["accent"], font=("Consolas", 10)).pack(anchor=tk.W, pady=(5, 0))
        ttk.Label(formula_frame, text="Higher Elo = stronger player. Each doubling of rank loses ~150 Elo.",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(5, 0))

        # Win probability calculation
        prob_frame = ttk.Frame(content, style="Card.TFrame")
        prob_frame.pack(fill=tk.X, pady=(15, 10))

        ttk.Label(prob_frame, text="Win Probability Calculation:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(prob_frame, text="P(win) = 1 / (1 + 10^((Elo2 - Elo1) / 400))", style="Card.TLabel",
                  foreground=UI_COLORS["accent"], font=("Consolas", 10)).pack(anchor=tk.W, pady=(5, 0))

        elo_prob = data.get('elo_win_prob', 0.5)
        ttk.Label(prob_frame, text=f"Elo-based win probability for {p1_name}: {elo_prob*100:.1f}%",
                  style="Card.TLabel").pack(anchor=tk.W, pady=(5, 0))

        # Final advantage
        adv_frame = ttk.Frame(content, style="Card.TFrame")
        adv_frame.pack(fill=tk.X, pady=(15, 0))

        advantage = ranking_data.get('advantage', 0)
        favors = p1_name if advantage > 0 else p2_name if advantage < 0 else "Neither"
        adv_color = UI_COLORS["player1"] if advantage > 0 else UI_COLORS["player2"] if advantage < 0 else UI_COLORS["text_secondary"]

        ttk.Label(adv_frame, text="Final Advantage:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        tk.Label(adv_frame, text=f"{abs(advantage):.3f} favoring {favors}",
                 font=("Segoe UI", 11, "bold"), fg=adv_color, bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=(5, 0))

    def _show_form_details(self, form_data: Dict, p1_name: str, p2_name: str, p1_id: int = None, p2_id: int = None):
        """Show detailed form breakdown in a popup."""
        from datetime import datetime

        today = datetime.now()

        # Fetch matches from DB first to calculate accurate stats
        p1_matches = db.get_player_matches(p1_id, limit=10) if p1_id else []
        p2_matches = db.get_player_matches(p2_id, limit=10) if p2_id else []
        p1_canonical = db.get_canonical_id(p1_id) if p1_id else None
        p2_canonical = db.get_canonical_id(p2_id) if p2_id else None

        # Calculate wins/losses from actual matches
        p1_wins, p1_losses = 0, 0
        for match in p1_matches:
            winner_canonical = db.get_canonical_id(match.get('winner_id'))
            if winner_canonical == p1_canonical:
                p1_wins += 1
            else:
                p1_losses += 1

        p2_wins, p2_losses = 0, 0
        for match in p2_matches:
            winner_canonical = db.get_canonical_id(match.get('winner_id'))
            if winner_canonical == p2_canonical:
                p2_wins += 1
            else:
                p2_losses += 1

        # Calculate form scores (simple win percentage scaled to 100)
        p1_total = p1_wins + p1_losses
        p2_total = p2_wins + p2_losses
        p1_score = (p1_wins / p1_total * 100) if p1_total > 0 else 50.0
        p2_score = (p2_wins / p2_total * 100) if p2_total > 0 else 50.0

        popup = tk.Toplevel(self.root)
        popup.title("Form Breakdown")
        popup.geometry("800x650")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(popup, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(popup, orient=tk.VERTICAL, command=canvas.yview)
        content = ttk.Frame(canvas, style="Card.TFrame", padding=20)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=content, anchor=tk.NW)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(content, text="Form Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="Recent match results with recency decay and opponent strength weighting",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Summary scores
        summary = ttk.Frame(content, style="Card.TFrame")
        summary.pack(fill=tk.X, pady=10)

        ttk.Label(summary, text="Summary:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))

        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(summary, text=header, style="Card.TLabel",
                      font=("Segoe UI", 9, "bold")).grid(row=1, column=col, padx=10, pady=3, sticky=tk.W)

        rows = [
            ("Record", f"{p1_wins}W - {p1_losses}L", f"{p2_wins}W - {p2_losses}L"),
            ("Form Score", f"{p1_score:.1f} / 100", f"{p2_score:.1f} / 100"),
        ]
        for row_idx, (label, v1, v2) in enumerate(rows, 2):
            ttk.Label(summary, text=label, style="Card.TLabel").grid(row=row_idx, column=0, padx=10, pady=2, sticky=tk.W)
            ttk.Label(summary, text=v1, style="Card.TLabel").grid(row=row_idx, column=1, padx=10, pady=2, sticky=tk.W)
            ttk.Label(summary, text=v2, style="Card.TLabel").grid(row=row_idx, column=2, padx=10, pady=2, sticky=tk.W)

        # Decay formula
        formula_frame = ttk.Frame(content, style="Card.TFrame")
        formula_frame.pack(fill=tk.X, pady=(15, 10))

        ttk.Label(formula_frame, text="Recency Decay Formula:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(formula_frame, text="weight = 0.9 ^ match_index", style="Card.TLabel",
                  foreground=UI_COLORS["accent"], font=("Consolas", 10)).pack(anchor=tk.W, pady=(5, 0))
        ttk.Label(formula_frame, text="Most recent match = 100% weight, 2nd = 90%, 3rd = 81%, etc.",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(5, 0))

        # Match lists side by side
        matches_frame = ttk.Frame(content, style="Card.TFrame")
        matches_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

        ttk.Label(matches_frame, text="Recent Matches (Last 10):", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))

        columns = ttk.Frame(matches_frame, style="Card.TFrame")
        columns.pack(fill=tk.BOTH, expand=True)

        # Player 1 matches
        p1_col = ttk.Frame(columns, style="Card.TFrame")
        p1_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        tk.Label(p1_col, text=p1_name[:20], font=("Segoe UI", 9, "bold"),
                 fg=UI_COLORS["player1"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

        for idx, match in enumerate(p1_matches):
            winner_canonical = db.get_canonical_id(match.get('winner_id'))
            won = winner_canonical == p1_canonical
            result = "W" if won else "L"
            color = UI_COLORS["success"] if won else UI_COLORS["danger"]

            # Get opponent info
            opp_id = match.get('loser_id') if won else match.get('winner_id')
            opp_name = "Unknown"
            opp_rank = ""
            if opp_id:
                opp_player = db.get_player(opp_id)
                if opp_player:
                    opp_name = opp_player.get('name', 'Unknown')
                    if len(opp_name) > 18:
                        parts = opp_name.split()
                        if len(parts) > 1:
                            opp_name = f"{parts[0][0]}. {parts[-1]}"
                    rank = opp_player.get('current_ranking')
                    if rank:
                        opp_rank = f" #{rank}"

            # Calculate days ago
            date_str = match.get('date', '')[:10]
            days_ago = '?'
            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except:
                pass

            weight = 0.9 ** idx

            row = ttk.Frame(p1_col, style="Card.TFrame")
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=result, fg=color, bg=UI_COLORS["bg_medium"],
                     font=("Segoe UI", 8, "bold"), width=2).pack(side=tk.LEFT)
            ttk.Label(row, text=f"vs {opp_name}{opp_rank} ({days_ago}d) w={weight:.2f}", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=5)

        # Player 2 matches
        p2_col = ttk.Frame(columns, style="Card.TFrame")
        p2_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        tk.Label(p2_col, text=p2_name[:20], font=("Segoe UI", 9, "bold"),
                 fg=UI_COLORS["player2"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

        for idx, match in enumerate(p2_matches):
            winner_canonical = db.get_canonical_id(match.get('winner_id'))
            won = winner_canonical == p2_canonical
            result = "W" if won else "L"
            color = UI_COLORS["success"] if won else UI_COLORS["danger"]

            # Get opponent info
            opp_id = match.get('loser_id') if won else match.get('winner_id')
            opp_name = "Unknown"
            opp_rank = ""
            if opp_id:
                opp_player = db.get_player(opp_id)
                if opp_player:
                    opp_name = opp_player.get('name', 'Unknown')
                    if len(opp_name) > 18:
                        parts = opp_name.split()
                        if len(parts) > 1:
                            opp_name = f"{parts[0][0]}. {parts[-1]}"
                    rank = opp_player.get('current_ranking')
                    if rank:
                        opp_rank = f" #{rank}"

            # Calculate days ago
            date_str = match.get('date', '')[:10]
            days_ago = '?'
            try:
                match_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_ago = (today - match_date).days
            except:
                pass

            weight = 0.9 ** idx

            row = ttk.Frame(p2_col, style="Card.TFrame")
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=result, fg=color, bg=UI_COLORS["bg_medium"],
                     font=("Segoe UI", 8, "bold"), width=2).pack(side=tk.LEFT)
            ttk.Label(row, text=f"vs {opp_name}{opp_rank} ({days_ago}d) w={weight:.2f}", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=5)

    def _show_surface_details(self, surface_data: Dict, p1_name: str, p2_name: str, surface: str):
        """Show detailed surface breakdown in a popup."""
        p1 = surface_data.get('p1', {})
        p2 = surface_data.get('p2', {})

        popup = tk.Toplevel(self.root)
        popup.title("Surface Breakdown")
        popup.geometry("550x400")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        content = ttk.Frame(popup, style="Card.TFrame", padding=20)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(content, text=f"Surface Breakdown ({surface})", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="Win rate on current surface with match count reliability indicator",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Main comparison table
        table = ttk.Frame(content, style="Card.TFrame")
        table.pack(fill=tk.X, pady=10)

        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(table, text=header, style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)

        p1_wr = p1.get('combined_win_rate', 0.5) * 100
        p2_wr = p2.get('combined_win_rate', 0.5) * 100
        p1_matches = p1.get('career_matches', 0)
        p2_matches = p2.get('career_matches', 0)

        rows = [
            ("Win Rate", f"{p1_wr:.1f}%", f"{p2_wr:.1f}%"),
            ("Matches Played", str(p1_matches), str(p2_matches)),
        ]

        for row_idx, (label, v1, v2) in enumerate(rows, 1):
            ttk.Label(table, text=label, style="Card.TLabel").grid(row=row_idx, column=0, padx=10, pady=3, sticky=tk.W)
            ttk.Label(table, text=v1, style="Card.TLabel").grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
            ttk.Label(table, text=v2, style="Card.TLabel").grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)

        # Sample size warnings
        warning_frame = ttk.Frame(content, style="Card.TFrame")
        warning_frame.pack(fill=tk.X, pady=(15, 10))

        if p1_matches < 20 or p2_matches < 20:
            ttk.Label(warning_frame, text="Low Sample Size Warning:", style="Card.TLabel",
                      font=("Segoe UI", 10, "bold"), foreground=UI_COLORS["warning"]).pack(anchor=tk.W)
            if p1_matches < 20:
                ttk.Label(warning_frame, text=f"  {p1_name}: Only {p1_matches} matches on {surface} (< 20 recommended)",
                          style="Card.TLabel", foreground=UI_COLORS["warning"]).pack(anchor=tk.W, pady=(5, 0))
            if p2_matches < 20:
                ttk.Label(warning_frame, text=f"  {p2_name}: Only {p2_matches} matches on {surface} (< 20 recommended)",
                          style="Card.TLabel", foreground=UI_COLORS["warning"]).pack(anchor=tk.W, pady=(5, 0))
        else:
            ttk.Label(warning_frame, text="Sample Size: Adequate for both players (20+ matches)",
                      style="Card.TLabel", foreground=UI_COLORS["success"]).pack(anchor=tk.W)

        # Final advantage
        adv_frame = ttk.Frame(content, style="Card.TFrame")
        adv_frame.pack(fill=tk.X, pady=(15, 0))

        advantage = surface_data.get('advantage', 0)
        favors = p1_name if advantage > 0 else p2_name if advantage < 0 else "Neither"
        adv_color = UI_COLORS["player1"] if advantage > 0 else UI_COLORS["player2"] if advantage < 0 else UI_COLORS["text_secondary"]

        ttk.Label(adv_frame, text="Final Advantage:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        tk.Label(adv_frame, text=f"{abs(advantage):.3f} favoring {favors}",
                 font=("Segoe UI", 11, "bold"), fg=adv_color, bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=(5, 0))

    def _show_h2h_details(self, h2h_data: Dict, p1_name: str, p2_name: str):
        """Show detailed head-to-head breakdown in a popup."""
        data = h2h_data.get('data', {})

        popup = tk.Toplevel(self.root)
        popup.title("Head-to-Head Breakdown")
        popup.geometry("700x500")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(popup, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(popup, orient=tk.VERTICAL, command=canvas.yview)
        content = ttk.Frame(canvas, style="Card.TFrame", padding=20)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=content, anchor=tk.NW)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(content, text="Head-to-Head Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="Historical record between these players",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        p1_wins = data.get('p1_wins', 0)
        p2_wins = data.get('p2_wins', 0)
        total = p1_wins + p2_wins

        # Overall record
        record_frame = ttk.Frame(content, style="Card.TFrame")
        record_frame.pack(fill=tk.X, pady=10)

        ttk.Label(record_frame, text="Overall Record:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        if total == 0:
            tk.Label(record_frame, text="No previous meetings between these players",
                     font=("Segoe UI", 11), fg=UI_COLORS["warning"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=(5, 0))
        else:
            record_text = f"{p1_name}: {p1_wins} wins  |  {p2_name}: {p2_wins} wins"
            tk.Label(record_frame, text=record_text,
                     font=("Segoe UI", 11, "bold"), fg=UI_COLORS["text_primary"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=(5, 0))

        # Match history
        matches = data.get('matches', [])
        if matches:
            history_frame = ttk.Frame(content, style="Card.TFrame")
            history_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

            ttk.Label(history_frame, text="Match History:", style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))

            # Table headers
            header_frame = ttk.Frame(history_frame, style="Card.TFrame")
            header_frame.pack(fill=tk.X)
            headers = ["Date", "Tournament", "Surface", "Winner", "Score"]
            widths = [80, 150, 60, 120, 100]
            for header, width in zip(headers, widths):
                ttk.Label(header_frame, text=header, style="Card.TLabel",
                          font=("Segoe UI", 9, "bold"), width=width//8).pack(side=tk.LEFT, padx=3)

            # Match rows
            for match in matches[:10]:  # Limit to 10 most recent
                row_frame = ttk.Frame(history_frame, style="Card.TFrame")
                row_frame.pack(fill=tk.X, pady=1)

                date = match.get('date', '')[:10]
                tourney = (match.get('tournament') or match.get('tourney_name') or 'Unknown')[:18]
                surface = match.get('surface', '?')[:8]
                winner = match.get('winner_name', 'Unknown')[:15]
                score = match.get('score', '')[:12]

                # Highlight winner
                winner_color = UI_COLORS["player1"] if p1_name in winner else UI_COLORS["player2"]

                ttk.Label(row_frame, text=date, style="Card.TLabel", font=("Segoe UI", 8), width=10).pack(side=tk.LEFT, padx=3)
                ttk.Label(row_frame, text=tourney, style="Card.TLabel", font=("Segoe UI", 8), width=18).pack(side=tk.LEFT, padx=3)
                ttk.Label(row_frame, text=surface, style="Card.TLabel", font=("Segoe UI", 8), width=8).pack(side=tk.LEFT, padx=3)
                tk.Label(row_frame, text=winner, font=("Segoe UI", 8), fg=winner_color, bg=UI_COLORS["bg_medium"], width=15).pack(side=tk.LEFT, padx=3)
                ttk.Label(row_frame, text=score, style="Card.TLabel", font=("Segoe UI", 8), width=12).pack(side=tk.LEFT, padx=3)

        # Final advantage
        adv_frame = ttk.Frame(content, style="Card.TFrame")
        adv_frame.pack(fill=tk.X, pady=(15, 0))

        advantage = h2h_data.get('advantage', 0)
        favors = p1_name if advantage > 0 else p2_name if advantage < 0 else "Neither"
        adv_color = UI_COLORS["player1"] if advantage > 0 else UI_COLORS["player2"] if advantage < 0 else UI_COLORS["text_secondary"]

        ttk.Label(adv_frame, text="Final Advantage:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        tk.Label(adv_frame, text=f"{abs(advantage):.3f} favoring {favors}",
                 font=("Segoe UI", 11, "bold"), fg=adv_color, bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=(5, 0))

    def _show_activity_details(self, activity_data: Dict, p1_name: str, p2_name: str):
        """Show detailed activity breakdown in a popup."""
        p1 = activity_data.get('p1', {})
        p2 = activity_data.get('p2', {})

        popup = tk.Toplevel(self.root)
        popup.title("Activity Breakdown")
        popup.geometry("550x400")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        content = ttk.Frame(popup, style="Card.TFrame", padding=20)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(content, text="Activity Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="Recent match frequency — edge modifier, not a weighted factor",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Main comparison table
        table = ttk.Frame(content, style="Card.TFrame")
        table.pack(fill=tk.X, pady=10)

        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(table, text=header, style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)

        p1_status = p1.get('status', 'Active')
        p2_status = p2.get('status', 'Active')
        p1_score = p1.get('score', 100)
        p2_score = p2.get('score', 100)
        p1_matches = p1.get('match_count_90d', 'N/A')
        p2_matches = p2.get('match_count_90d', 'N/A')
        p1_gap = p1.get('max_gap_days', 'N/A')
        p2_gap = p2.get('max_gap_days', 'N/A')

        rows = [
            ("Status", p1_status, p2_status),
            ("Activity Score", f"{p1_score:.0f} / 100", f"{p2_score:.0f} / 100"),
            ("Matches (90d)", str(p1_matches), str(p2_matches)),
            ("Max Gap (days)", str(p1_gap), str(p2_gap)),
        ]

        for row_idx, (label, v1, v2) in enumerate(rows, 1):
            ttk.Label(table, text=label, style="Card.TLabel").grid(row=row_idx, column=0, padx=10, pady=3, sticky=tk.W)

            # Color code by activity level
            def _act_color(score_str):
                try:
                    s = float(score_str.split('/')[0].strip())
                    if s >= 70: return UI_COLORS["success"]
                    elif s >= 40: return UI_COLORS["warning"]
                    else: return UI_COLORS["danger"]
                except:
                    return UI_COLORS["text_secondary"]

            v1_color = _act_color(str(p1_score)) if row_idx <= 2 else UI_COLORS["text_secondary"]
            v2_color = _act_color(str(p2_score)) if row_idx <= 2 else UI_COLORS["text_secondary"]

            tk.Label(table, text=v1, font=("Segoe UI", 9), fg=v1_color, bg=UI_COLORS["bg_medium"]).grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
            tk.Label(table, text=v2, font=("Segoe UI", 9), fg=v2_color, bg=UI_COLORS["bg_medium"]).grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)

        # Explanation notice
        notice_frame = ttk.Frame(content, style="Card.TFrame")
        notice_frame.pack(fill=tk.X, pady=(20, 10))

        ttk.Label(notice_frame, text="How it works:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold"), foreground=UI_COLORS["warning"]).pack(anchor=tk.W)
        ttk.Label(notice_frame, text="When either player has low activity, ranking/Elo signals are unreliable.",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(5, 0))
        ttk.Label(notice_frame, text="Edge is reduced up to 40% and stake up to 30% based on min activity score.",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W)

    def _show_opponent_quality_details(self, opp_data: Dict, p1_name: str, p2_name: str):
        """Show detailed opponent quality breakdown in a popup."""
        p1 = opp_data.get('p1', {})
        p2 = opp_data.get('p2', {})

        popup = tk.Toplevel(self.root)
        popup.title("Opponent Quality Breakdown")
        popup.geometry("750x550")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(popup, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(popup, orient=tk.VERTICAL, command=canvas.yview)
        content = ttk.Frame(canvas, style="Card.TFrame", padding=20)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=content, anchor=tk.NW)
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(content, text="Opponent Quality Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="Average strength of recent opponents faced",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Summary
        summary = ttk.Frame(content, style="Card.TFrame")
        summary.pack(fill=tk.X, pady=10)

        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(summary, text=header, style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)

        p1_avg = p1.get('avg_opponent_rank', 100)
        p2_avg = p2.get('avg_opponent_rank', 100)
        p1_score = p1.get('score', 0)
        p2_score = p2.get('score', 0)

        rows = [
            ("Avg Opponent Rank", f"#{p1_avg:.0f}", f"#{p2_avg:.0f}"),
            ("Quality Score", f"{p1_score:.3f}", f"{p2_score:.3f}"),
        ]

        for row_idx, (label, v1, v2) in enumerate(rows, 1):
            ttk.Label(summary, text=label, style="Card.TLabel").grid(row=row_idx, column=0, padx=10, pady=3, sticky=tk.W)
            ttk.Label(summary, text=v1, style="Card.TLabel").grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
            ttk.Label(summary, text=v2, style="Card.TLabel").grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)

        # Calculation explanation
        calc_frame = ttk.Frame(content, style="Card.TFrame")
        calc_frame.pack(fill=tk.X, pady=(15, 10))

        ttk.Label(calc_frame, text="Score Calculation:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(calc_frame, text="Lower avg opponent rank = higher quality = positive score",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(5, 0))
        ttk.Label(calc_frame, text="Score range: -1.0 (weak opponents) to +1.0 (strong opponents)",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W)

        # Recent opponents lists
        opp_frame = ttk.Frame(content, style="Card.TFrame")
        opp_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

        ttk.Label(opp_frame, text="Recent Opponents:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))

        columns = ttk.Frame(opp_frame, style="Card.TFrame")
        columns.pack(fill=tk.BOTH, expand=True)

        # Player 1 opponents
        p1_col = ttk.Frame(columns, style="Card.TFrame")
        p1_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        tk.Label(p1_col, text=p1_name[:20], font=("Segoe UI", 9, "bold"),
                 fg=UI_COLORS["player1"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

        for opp in p1.get('opponents', [])[:6]:
            opp_name = opp.get('name', 'Unknown')[:15]
            opp_rank = opp.get('rank', '?')
            ttk.Label(p1_col, text=f"vs {opp_name} (#{opp_rank})", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(anchor=tk.W, pady=1)

        # Player 2 opponents
        p2_col = ttk.Frame(columns, style="Card.TFrame")
        p2_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        tk.Label(p2_col, text=p2_name[:20], font=("Segoe UI", 9, "bold"),
                 fg=UI_COLORS["player2"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

        for opp in p2.get('opponents', [])[:6]:
            opp_name = opp.get('name', 'Unknown')[:15]
            opp_rank = opp.get('rank', '?')
            ttk.Label(p2_col, text=f"vs {opp_name} (#{opp_rank})", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(anchor=tk.W, pady=1)

    def _show_recency_details(self, recency_data: Dict, p1_name: str, p2_name: str):
        """Show detailed recency breakdown in a popup."""
        p1 = recency_data.get('p1', {})
        p2 = recency_data.get('p2', {})

        popup = tk.Toplevel(self.root)
        popup.title("Recency Breakdown")
        popup.geometry("700x500")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        content = ttk.Frame(popup, style="Card.TFrame", padding=20)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(content, text="Recency Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="How recent the form data is - recent matches weighted higher",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Weight tiers explanation
        tiers_frame = ttk.Frame(content, style="Card.TFrame")
        tiers_frame.pack(fill=tk.X, pady=10)

        ttk.Label(tiers_frame, text="Weight Tiers:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        tiers = [
            ("Last 7 days", "100% weight", UI_COLORS["success"]),
            ("7-30 days", "70% weight", "#22d3ee"),
            ("30-90 days", "40% weight", UI_COLORS["warning"]),
            ("90+ days", "20% weight", UI_COLORS["danger"]),
        ]

        for tier_name, weight, color in tiers:
            row = ttk.Frame(tiers_frame, style="Card.TFrame")
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"  {tier_name}:", style="Card.TLabel", width=15).pack(side=tk.LEFT)
            tk.Label(row, text=weight, font=("Segoe UI", 9), fg=color, bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)

        # Summary scores
        summary = ttk.Frame(content, style="Card.TFrame")
        summary.pack(fill=tk.X, pady=(15, 10))

        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(summary, text=header, style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)

        p1_score = p1.get('score', 0)
        p2_score = p2.get('score', 0)

        ttk.Label(summary, text="Recency Score", style="Card.TLabel").grid(row=1, column=0, padx=10, pady=3, sticky=tk.W)
        ttk.Label(summary, text=f"{p1_score:.3f}", style="Card.TLabel").grid(row=1, column=1, padx=10, pady=3, sticky=tk.W)
        ttk.Label(summary, text=f"{p2_score:.3f}", style="Card.TLabel").grid(row=1, column=2, padx=10, pady=3, sticky=tk.W)

        # Match dates with weights
        dates_frame = ttk.Frame(content, style="Card.TFrame")
        dates_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

        ttk.Label(dates_frame, text="Recent Match Dates with Weights:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))

        columns = ttk.Frame(dates_frame, style="Card.TFrame")
        columns.pack(fill=tk.BOTH, expand=True)

        # Player 1 matches
        p1_col = ttk.Frame(columns, style="Card.TFrame")
        p1_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        tk.Label(p1_col, text=p1_name[:20], font=("Segoe UI", 9, "bold"),
                 fg=UI_COLORS["player1"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

        for match in p1.get('matches', [])[:6]:
            date = match.get('date', '')[:10]
            days_ago = match.get('days_ago', 0)
            weight = match.get('weight', 0)
            ttk.Label(p1_col, text=f"{date} ({days_ago}d ago) w={weight:.1f}", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(anchor=tk.W, pady=1)

        # Player 2 matches
        p2_col = ttk.Frame(columns, style="Card.TFrame")
        p2_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        tk.Label(p2_col, text=p2_name[:20], font=("Segoe UI", 9, "bold"),
                 fg=UI_COLORS["player2"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

        for match in p2.get('matches', [])[:6]:
            date = match.get('date', '')[:10]
            days_ago = match.get('days_ago', 0)
            weight = match.get('weight', 0)
            ttk.Label(p2_col, text=f"{date} ({days_ago}d ago) w={weight:.1f}", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(anchor=tk.W, pady=1)

    def _show_recent_loss_details(self, loss_data: Dict, p1_name: str, p2_name: str):
        """Show detailed recent loss breakdown in a popup."""
        p1 = loss_data.get('p1', {})
        p2 = loss_data.get('p2', {})

        popup = tk.Toplevel(self.root)
        popup.title("Recent Loss Breakdown")
        popup.geometry("600x450")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        content = ttk.Frame(popup, style="Card.TFrame", padding=20)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(content, text="Recent Loss Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text="Penalty for coming off a recent loss",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Penalty tiers explanation
        tiers_frame = ttk.Frame(content, style="Card.TFrame")
        tiers_frame.pack(fill=tk.X, pady=10)

        ttk.Label(tiers_frame, text="Penalty Tiers:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        tiers = [
            ("Loss in last 3 days", "-0.10 penalty", UI_COLORS["danger"]),
            ("Loss in last 7 days", "-0.05 penalty", UI_COLORS["warning"]),
            ("5-set loss (additional)", "-0.05 extra", UI_COLORS["danger"]),
        ]

        for tier_name, penalty, color in tiers:
            row = ttk.Frame(tiers_frame, style="Card.TFrame")
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"  {tier_name}:", style="Card.TLabel", width=25).pack(side=tk.LEFT)
            tk.Label(row, text=penalty, font=("Segoe UI", 9), fg=color, bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)

        # Player details
        details_frame = ttk.Frame(content, style="Card.TFrame")
        details_frame.pack(fill=tk.X, pady=(20, 10))

        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(details_frame, text=header, style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)

        p1_penalty = p1.get('penalty', 0)
        p2_penalty = p2.get('penalty', 0)
        p1_last_loss = p1.get('last_loss_date', 'None recent')
        p2_last_loss = p2.get('last_loss_date', 'None recent')
        p1_days = p1.get('days_since_loss', '-')
        p2_days = p2.get('days_since_loss', '-')

        rows = [
            ("Last Loss", str(p1_last_loss)[:10], str(p2_last_loss)[:10]),
            ("Days Ago", str(p1_days), str(p2_days)),
            ("Penalty", f"{p1_penalty:.2f}" if p1_penalty else "None", f"{p2_penalty:.2f}" if p2_penalty else "None"),
        ]

        for row_idx, (label, v1, v2) in enumerate(rows, 1):
            ttk.Label(details_frame, text=label, style="Card.TLabel").grid(row=row_idx, column=0, padx=10, pady=3, sticky=tk.W)

            # Color code penalties
            v1_color = UI_COLORS["danger"] if p1_penalty else UI_COLORS["success"]
            v2_color = UI_COLORS["danger"] if p2_penalty else UI_COLORS["success"]

            if row_idx == 3:  # Penalty row
                tk.Label(details_frame, text=v1, font=("Segoe UI", 9), fg=v1_color, bg=UI_COLORS["bg_medium"]).grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
                tk.Label(details_frame, text=v2, font=("Segoe UI", 9), fg=v2_color, bg=UI_COLORS["bg_medium"]).grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)
            else:
                ttk.Label(details_frame, text=v1, style="Card.TLabel").grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
                ttk.Label(details_frame, text=v2, style="Card.TLabel").grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)

    def _show_momentum_details(self, momentum_data: Dict, p1_name: str, p2_name: str, surface: str):
        """Show detailed momentum breakdown in a popup."""
        p1 = momentum_data.get('p1', {})
        p2 = momentum_data.get('p2', {})

        popup = tk.Toplevel(self.root)
        popup.title("Momentum Breakdown")
        popup.geometry("550x400")
        popup.configure(bg=UI_COLORS["bg_dark"])
        popup.transient(self.root)

        content = ttk.Frame(popup, style="Card.TFrame", padding=20)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(content, text="Momentum Breakdown", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(content, text=f"Recent wins on {surface} in last 14 days",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(0, 15))

        # Bonus explanation
        bonus_frame = ttk.Frame(content, style="Card.TFrame")
        bonus_frame.pack(fill=tk.X, pady=10)

        ttk.Label(bonus_frame, text="Bonus Calculation:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(bonus_frame, text="  +0.03 bonus per win on same surface (last 14 days)",
                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"]).pack(anchor=tk.W, pady=(5, 0))
        ttk.Label(bonus_frame, text="  Maximum bonus capped at +0.10",
                  style="Card.TLabel", foreground=UI_COLORS["warning"]).pack(anchor=tk.W, pady=(5, 0))

        # Player details
        details_frame = ttk.Frame(content, style="Card.TFrame")
        details_frame.pack(fill=tk.X, pady=(20, 10))

        headers = ["", p1_name[:18], p2_name[:18]]
        for col, header in enumerate(headers):
            ttk.Label(details_frame, text=header, style="Card.TLabel",
                      font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)

        p1_wins = p1.get('surface_wins', 0)
        p2_wins = p2.get('surface_wins', 0)
        p1_bonus = p1.get('bonus', 0)
        p2_bonus = p2.get('bonus', 0)

        rows = [
            (f"Wins on {surface} (14d)", str(p1_wins), str(p2_wins)),
            ("Bonus", f"+{p1_bonus:.2f}" if p1_bonus else "None", f"+{p2_bonus:.2f}" if p2_bonus else "None"),
        ]

        for row_idx, (label, v1, v2) in enumerate(rows, 1):
            ttk.Label(details_frame, text=label, style="Card.TLabel").grid(row=row_idx, column=0, padx=10, pady=3, sticky=tk.W)

            # Color code bonuses
            v1_color = UI_COLORS["success"] if p1_bonus else UI_COLORS["text_secondary"]
            v2_color = UI_COLORS["success"] if p2_bonus else UI_COLORS["text_secondary"]

            if row_idx == 2:  # Bonus row
                tk.Label(details_frame, text=v1, font=("Segoe UI", 9, "bold"), fg=v1_color, bg=UI_COLORS["bg_medium"]).grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
                tk.Label(details_frame, text=v2, font=("Segoe UI", 9, "bold"), fg=v2_color, bg=UI_COLORS["bg_medium"]).grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)
            else:
                ttk.Label(details_frame, text=v1, style="Card.TLabel").grid(row=row_idx, column=1, padx=10, pady=3, sticky=tk.W)
                ttk.Label(details_frame, text=v2, style="Card.TLabel").grid(row=row_idx, column=2, padx=10, pady=3, sticky=tk.W)

        # Cap notice
        if p1_bonus >= 0.10 or p2_bonus >= 0.10:
            cap_frame = ttk.Frame(content, style="Card.TFrame")
            cap_frame.pack(fill=tk.X, pady=(15, 0))
            if p1_bonus >= 0.10:
                ttk.Label(cap_frame, text=f"{p1_name} has reached the maximum +0.10 bonus cap",
                          style="Card.TLabel", foreground=UI_COLORS["warning"]).pack(anchor=tk.W)
            if p2_bonus >= 0.10:
                ttk.Label(cap_frame, text=f"{p2_name} has reached the maximum +0.10 bonus cap",
                          style="Card.TLabel", foreground=UI_COLORS["warning"]).pack(anchor=tk.W)

    def _create_analysis_table(self, parent, result: Dict, p1_name: str, p2_name: str, p1_id: int = None, p2_id: int = None, surface: str = None, pack_side=None):
        """Create the detailed analysis breakdown table with 9 factors."""
        table_frame = ttk.Frame(parent, style="Card.TFrame", padding=10)
        if pack_side:
            table_frame.pack(side=pack_side, fill=tk.Y, pady=5)
        else:
            table_frame.pack(fill=tk.X, pady=5)

        ttk.Label(table_frame, text="Factor Analysis (9 Factors)", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        # Create table headers with player colors
        header_frame = ttk.Frame(table_frame, style="Card.TFrame")
        header_frame.pack(fill=tk.X)

        headers = ["Factor", p1_name[:18], p2_name[:18], "Adv", "Wt", "Contrib"]
        widths = [110, 150, 150, 60, 45, 60]
        header_colors = [None, UI_COLORS["player1"], UI_COLORS["player2"], None, None, None]

        for i, (header, width) in enumerate(zip(headers, widths)):
            if header_colors[i]:
                lbl = tk.Label(header_frame, text=header, font=("Segoe UI", 9, "bold"),
                              fg=header_colors[i], bg=UI_COLORS["bg_medium"], width=width//8)
            else:
                lbl = ttk.Label(header_frame, text=header, style="Card.TLabel",
                               font=("Segoe UI", 9, "bold"), width=width//8)
            lbl.grid(row=0, column=i, padx=3, pady=2, sticky=tk.W)

        # Factor rows
        factors = result.get('factors', {})
        row_num = 1

        # 1. Rankings (show ~ prefix if estimated from odds)
        rankings = factors.get('ranking', {}).get('data', {})
        ranking_factor = factors.get('ranking', {})
        p1_rank_str = f"~#{rankings.get('p1_rank', '?')}" if rankings.get('p1_estimated') else f"#{rankings.get('p1_rank', '?')}"
        p2_rank_str = f"~#{rankings.get('p2_rank', '?')}" if rankings.get('p2_estimated') else f"#{rankings.get('p2_rank', '?')}"
        self._add_table_row_v2(table_frame, "1. Ranking ▸",
                           f"{p1_rank_str} (Elo:{rankings.get('p1_elo', 0):.0f})",
                           f"{p2_rank_str} (Elo:{rankings.get('p2_elo', 0):.0f})",
                           ranking_factor.get('advantage', 0),
                           ranking_factor.get('weight', 0.2),
                           row_num,
                           on_click=lambda rf=ranking_factor: self._show_ranking_details(rf, p1_name, p2_name))
        row_num += 1

        # 2. Form
        form = factors.get('form', {})
        p1_form = form.get('p1', {})
        p2_form = form.get('p2', {})
        self._add_table_row_v2(table_frame, "2. Form ▸",
                           f"{p1_form.get('wins', 0)}W-{p1_form.get('losses', 0)}L ({p1_form.get('score', 50):.0f})",
                           f"{p2_form.get('wins', 0)}W-{p2_form.get('losses', 0)}L ({p2_form.get('score', 50):.0f})",
                           form.get('advantage', 0),
                           form.get('weight', 0.20),
                           row_num,
                           on_click=lambda f=form, pid1=p1_id, pid2=p2_id: self._show_form_details(f, p1_name, p2_name, pid1, pid2))
        row_num += 1

        # 3. Surface
        surf = factors.get('surface', {})
        p1_surf = surf.get('p1', {})
        p2_surf = surf.get('p2', {})
        self._add_table_row_v2(table_frame, "3. Surface ▸",
                           f"{p1_surf.get('combined_win_rate', 0.5)*100:.0f}% ({p1_surf.get('career_matches', 0)}m)",
                           f"{p2_surf.get('combined_win_rate', 0.5)*100:.0f}% ({p2_surf.get('career_matches', 0)}m)",
                           surf.get('advantage', 0),
                           surf.get('weight', 0.15),
                           row_num,
                           on_click=lambda s=surf, sfc=surface: self._show_surface_details(s, p1_name, p2_name, sfc))
        row_num += 1

        # 4. H2H
        h2h_factor = factors.get('h2h', {})
        h2h = h2h_factor.get('data', {})
        self._add_table_row_v2(table_frame, "4. Head-to-Head ▸",
                           f"{h2h.get('p1_wins', 0)} wins",
                           f"{h2h.get('p2_wins', 0)} wins",
                           h2h_factor.get('advantage', 0),
                           h2h_factor.get('weight', 0.10),
                           row_num,
                           on_click=lambda hf=h2h_factor: self._show_h2h_details(hf, p1_name, p2_name))
        row_num += 1

        # 5. Fatigue (clickable for details)
        fatigue = factors.get('fatigue', {})
        p1_fat = fatigue.get('p1', {})
        p2_fat = fatigue.get('p2', {})
        self._add_table_row_v2(table_frame, "5. Fatigue ▸",
                           f"{p1_fat.get('status', '?')} ({p1_fat.get('score', 0):.0f}/100)",
                           f"{p2_fat.get('status', '?')} ({p2_fat.get('score', 0):.0f}/100)",
                           fatigue.get('advantage', 0),
                           fatigue.get('weight', 0.05),
                           row_num,
                           on_click=lambda: self._show_fatigue_details(fatigue, p1_name, p2_name))
        row_num += 1

        # 6. Activity (edge modifier)
        activity = factors.get('activity', {})
        p1_act = activity.get('p1', {})
        p2_act = activity.get('p2', {})
        self._add_table_row_v2(table_frame, "6. Activity ▸",
                           f"{p1_act.get('status', 'Active')} ({p1_act.get('score', 100):.0f})",
                           f"{p2_act.get('status', 'Active')} ({p2_act.get('score', 100):.0f})",
                           0.0,  # Edge modifier, not a weighted advantage
                           0.00,  # Not a weighted factor
                           row_num,
                           on_click=lambda a=activity: self._show_activity_details(a, p1_name, p2_name))
        row_num += 1

        # 7. Recent Loss
        recent_loss = factors.get('recent_loss', {})
        p1_rl = recent_loss.get('p1', {})
        p2_rl = recent_loss.get('p2', {})
        p1_penalty = p1_rl.get('penalty', 0)
        p2_penalty = p2_rl.get('penalty', 0)
        self._add_table_row_v2(table_frame, "7. Recent Loss ▸",
                           f"Penalty: {p1_penalty:.2f}" if p1_penalty else "No penalty",
                           f"Penalty: {p2_penalty:.2f}" if p2_penalty else "No penalty",
                           recent_loss.get('advantage', 0),
                           recent_loss.get('weight', 0.08),
                           row_num,
                           on_click=lambda rl=recent_loss: self._show_recent_loss_details(rl, p1_name, p2_name))
        row_num += 1

        # 8. Momentum
        momentum = factors.get('momentum', {})
        p1_mom = momentum.get('p1', {})
        p2_mom = momentum.get('p2', {})
        p1_bonus = p1_mom.get('bonus', 0)
        p2_bonus = p2_mom.get('bonus', 0)
        self._add_table_row_v2(table_frame, "8. Momentum ▸",
                           f"Bonus: +{p1_bonus:.2f}" if p1_bonus else "No bonus",
                           f"Bonus: +{p2_bonus:.2f}" if p2_bonus else "No bonus",
                           momentum.get('advantage', 0),
                           momentum.get('weight', 0.02),
                           row_num,
                           on_click=lambda m=momentum, sfc=surface: self._show_momentum_details(m, p1_name, p2_name, sfc))

        # 9. Performance Elo
        row_num += 1
        perf_elo_factor = factors.get('performance_elo', {})
        perf_elo_data = perf_elo_factor.get('data', {})
        p1_pe = perf_elo_data.get('p1_performance_elo', 0)
        p2_pe = perf_elo_data.get('p2_performance_elo', 0)
        p1_pe_has = perf_elo_data.get('p1_has_data', False)
        p2_pe_has = perf_elo_data.get('p2_has_data', False)
        p1_pe_rank = perf_elo_data.get('p1_performance_rank')
        p2_pe_rank = perf_elo_data.get('p2_performance_rank')
        p1_rank_str = f" (#{p1_pe_rank})" if p1_pe_rank else ""
        p2_rank_str = f" (#{p2_pe_rank})" if p2_pe_rank else ""
        p1_pe_str = (f"{p1_pe:.0f}{p1_rank_str}" if p1_pe_has else f"~{p1_pe:.0f}")
        p2_pe_str = (f"{p2_pe:.0f}{p2_rank_str}" if p2_pe_has else f"~{p2_pe:.0f}")
        self._add_table_row_v2(table_frame, "9. Perf Elo",
                           p1_pe_str, p2_pe_str,
                           perf_elo_factor.get('advantage', 0),
                           perf_elo_factor.get('weight', 0.12),
                           row_num)

        # Separator
        ttk.Separator(table_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # Weighted Advantage Summary
        weighted_adv = result.get('weighted_advantage', 0)
        summary_frame = ttk.Frame(table_frame, style="Card.TFrame")
        summary_frame.pack(fill=tk.X)

        ttk.Label(summary_frame, text="Total Weighted Advantage:", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

        adv_color = UI_COLORS["player1"] if weighted_adv > 0 else UI_COLORS["player2"] if weighted_adv < 0 else UI_COLORS["text_secondary"]
        adv_text = f"{abs(weighted_adv):.4f}"
        favored = p1_name if weighted_adv > 0 else p2_name if weighted_adv < 0 else "Even"
        tk.Label(summary_frame, text=f"  {adv_text} ({favored} favored)",
                 font=("Segoe UI", 10, "bold"), fg=adv_color, bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)

        # Notes section
        notes_frame = ttk.Frame(table_frame, style="Card.TFrame")
        notes_frame.pack(fill=tk.X, pady=(10, 0))

        # Estimated ranking note
        if rankings.get('p1_estimated') or rankings.get('p2_estimated'):
            est_label = ttk.Label(notes_frame, text="~ = Ranking estimated from Betfair odds",
                                  style="Card.TLabel", foreground=UI_COLORS["text_secondary"],
                                  font=("Segoe UI", 8))
            est_label.pack(anchor=tk.W)

        # Large gap indicator
        if rankings.get('is_large_gap', False):
            gap_label = ttk.Label(notes_frame, text="Large ranking gap - Elo probability weighted higher",
                                  style="Card.TLabel", foreground=UI_COLORS["warning"],
                                  font=("Segoe UI", 8))
            gap_label.pack(anchor=tk.W)

        # Form contradiction indicator
        if result.get('form_contradiction'):
            contra_label = ttk.Label(notes_frame, text="Form contradicts ranking - Model weighted 90%",
                                     style="Card.TLabel", foreground=UI_COLORS["warning"],
                                     font=("Segoe UI", 8))
            contra_label.pack(anchor=tk.W)

    def _add_table_row(self, parent, factor: str, p1_val: str, p2_val: str,
                       advantage: float, weight: float, row: int):
        """Add a row to the analysis table."""
        row_frame = ttk.Frame(parent, style="Card.TFrame")
        row_frame.pack(fill=tk.X)

        # Determine advantage color
        if advantage > 0.1:
            adv_color = UI_COLORS["success"]
            adv_text = f"+{advantage:.2f}"
        elif advantage < -0.1:
            adv_color = UI_COLORS["danger"]
            adv_text = f"{advantage:.2f}"
        else:
            adv_color = UI_COLORS["text_secondary"]
            adv_text = f"{advantage:.2f}"

        values = [factor, p1_val, p2_val, adv_text, f"{weight*100:.0f}%"]
        widths = [120, 200, 200, 100, 80]

        for i, (val, width) in enumerate(zip(values, widths)):
            if i == 3:  # Advantage column
                lbl = tk.Label(row_frame, text=val, font=("Segoe UI", 9),
                              fg=adv_color, bg=UI_COLORS["bg_medium"], width=width//8)
            else:
                lbl = ttk.Label(row_frame, text=val, style="Card.TLabel", width=width//8)

            # Add tooltip to factor name column
            if i == 0 and factor in METRIC_TOOLTIPS:
                lbl.configure(cursor="question_arrow")
                Tooltip(lbl, METRIC_TOOLTIPS[factor])
            lbl.grid(row=0, column=i, padx=5, pady=2, sticky=tk.W)

    def _add_table_row_v2(self, parent, factor: str, p1_val: str, p2_val: str,
                          advantage: float, weight: float, row: int, on_click=None):
        """Add a row to the analysis table with contribution column."""
        row_frame = ttk.Frame(parent, style="Card.TFrame")
        row_frame.pack(fill=tk.X)

        # Calculate contribution (advantage * weight)
        contribution = advantage * weight

        # Format values - show absolute values, color indicates which player is favored
        adv_text = f"{abs(advantage):.2f}"
        contrib_text = f"{abs(contribution):.3f}"

        values = [factor, p1_val, p2_val, adv_text, f"{weight*100:.0f}%", contrib_text]
        widths = [110, 150, 150, 60, 45, 60]

        # Use player colors for Adv/Contrib: Blue for P1 favored (positive), Yellow for P2 favored (negative)
        if advantage > 0:
            adv_color = UI_COLORS["player1"]  # Blue - favors P1
        elif advantage < 0:
            adv_color = UI_COLORS["player2"]  # Yellow - favors P2
        else:
            adv_color = UI_COLORS["text_secondary"]

        row_labels = []  # Store labels for click binding
        for i, (val, width) in enumerate(zip(values, widths)):
            if i == 3:  # Advantage column - player colors
                lbl = tk.Label(row_frame, text=val, font=("Segoe UI", 8),
                              fg=adv_color, bg=UI_COLORS["bg_medium"], width=width//7)
            elif i == 5:  # Contribution column - player colors
                lbl = tk.Label(row_frame, text=val, font=("Segoe UI", 8),
                              fg=adv_color, bg=UI_COLORS["bg_medium"], width=width//7)
            else:
                lbl = ttk.Label(row_frame, text=val, style="Card.TLabel",
                               font=("Segoe UI", 8), width=width//7)

            # Add tooltip to factor name column
            factor_name = factor.split('. ')[-1] if '. ' in factor else factor
            factor_name = factor_name.replace(' ▸', '')  # Strip click indicator for tooltip lookup
            if i == 0 and factor_name in METRIC_TOOLTIPS:
                if not on_click:  # Only show question cursor if not clickable
                    lbl.configure(cursor="question_arrow")
                Tooltip(lbl, METRIC_TOOLTIPS[factor_name])
            lbl.grid(row=0, column=i, padx=3, pady=1, sticky=tk.W)
            row_labels.append(lbl)

        # Make row clickable if callback provided
        if on_click:
            for lbl in row_labels:
                lbl.configure(cursor="hand2")
                lbl.bind("<Button-1>", lambda e: on_click())
            row_frame.configure(cursor="hand2")
            row_frame.bind("<Button-1>", lambda e: on_click())

    def _create_analysis_summary(self, parent, result: Dict, p1_name: str, p2_name: str,
                                  p1_odds, p2_odds):
        """Create a narrative summary of the analysis with key factors explanation."""
        factors = result.get('factors', {})

        # Header
        ttk.Label(parent, text="Analysis Summary", style="Card.TLabel",
                  font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))

        # Our Model's Prediction
        p1_prob = result['p1_probability'] * 100
        p2_prob = result['p2_probability'] * 100
        model_favors = p1_name if p1_prob > p2_prob else p2_name
        model_prob = max(p1_prob, p2_prob)

        pred_frame = ttk.Frame(parent, style="Card.TFrame")
        pred_frame.pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(pred_frame, text="Model Prediction: ", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(pred_frame, text=f"{p1_name} {p1_prob:.1f}% - {p2_name} {p2_prob:.1f}%",
                  style="Card.TLabel").pack(side=tk.LEFT)

        # Betfair's Implied Odds
        if p1_odds and p2_odds:
            try:
                p1_implied = (1 / float(p1_odds)) * 100
                p2_implied = (1 / float(p2_odds)) * 100
                betfair_frame = ttk.Frame(parent, style="Card.TFrame")
                betfair_frame.pack(anchor=tk.W, pady=(0, 10))
                ttk.Label(betfair_frame, text="Betfair Implied: ", style="Card.TLabel",
                          font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
                ttk.Label(betfair_frame, text=f"{p1_name} {p1_implied:.1f}% - {p2_name} {p2_implied:.1f}%",
                          style="Card.TLabel").pack(side=tk.LEFT)
            except (ValueError, ZeroDivisionError):
                p1_implied = p2_implied = None
        else:
            p1_implied = p2_implied = None

        # Separator
        sep = ttk.Frame(parent, style="Card.TFrame", height=1)
        sep.pack(fill=tk.X, pady=5)
        sep.configure(style="Dark.TFrame")

        # Identify key factors (those with significant contribution)
        key_factors_p1 = []  # Factors favoring player 1
        key_factors_p2 = []  # Factors favoring player 2

        factor_display_names = {
            'ranking': 'Ranking/Elo',
            'form': 'Recent Form',
            'surface': 'Surface Record',
            'h2h': 'Head-to-Head',
            'fatigue': 'Fatigue/Rest',
            'activity': 'Activity Level',
            'opponent_quality': 'Opponent Quality',
            'recency': 'Match Recency',
            'recent_loss': 'Recent Loss',
            'momentum': 'Momentum',
            'performance_elo': 'Performance Elo'
        }

        for factor_key, factor_data in factors.items():
            if isinstance(factor_data, dict) and 'advantage' in factor_data and 'weight' in factor_data:
                adv = factor_data['advantage']
                weight = factor_data['weight']
                contribution = adv * weight

                # Only include factors with meaningful contribution (>0.005)
                if abs(contribution) > 0.005:
                    display_name = factor_display_names.get(factor_key, factor_key.title())
                    detail = self._get_factor_detail(factor_key, factor_data, p1_name, p2_name)

                    if contribution > 0:
                        key_factors_p1.append((display_name, detail, contribution))
                    else:
                        key_factors_p2.append((display_name, detail, abs(contribution)))

        # Sort by contribution magnitude
        key_factors_p1.sort(key=lambda x: x[2], reverse=True)
        key_factors_p2.sort(key=lambda x: x[2], reverse=True)

        # Display Key Factors for model favorite
        if model_favors == p1_name and key_factors_p1:
            ttk.Label(parent, text=f"Key Factors Favoring {p1_name}:",
                      style="Card.TLabel", font=("Segoe UI", 9, "bold"),
                      foreground=UI_COLORS["success"]).pack(anchor=tk.W, pady=(5, 3))
            for name, detail, _ in key_factors_p1[:4]:
                bullet = f"  • {name}: {detail}"
                ttk.Label(parent, text=bullet, style="Card.TLabel",
                          font=("Segoe UI", 8), wraplength=350).pack(anchor=tk.W)
        elif model_favors == p2_name and key_factors_p2:
            ttk.Label(parent, text=f"Key Factors Favoring {p2_name}:",
                      style="Card.TLabel", font=("Segoe UI", 9, "bold"),
                      foreground=UI_COLORS["success"]).pack(anchor=tk.W, pady=(5, 3))
            for name, detail, _ in key_factors_p2[:4]:
                bullet = f"  • {name}: {detail}"
                ttk.Label(parent, text=bullet, style="Card.TLabel",
                          font=("Segoe UI", 8), wraplength=350).pack(anchor=tk.W)

        # Also show factors for the other player if significant
        other_factors = key_factors_p2 if model_favors == p1_name else key_factors_p1
        other_name = p2_name if model_favors == p1_name else p1_name
        if other_factors:
            ttk.Label(parent, text=f"Factors Favoring {other_name}:",
                      style="Card.TLabel", font=("Segoe UI", 9, "bold"),
                      foreground=UI_COLORS["warning"]).pack(anchor=tk.W, pady=(8, 3))
            for name, detail, _ in other_factors[:3]:
                bullet = f"  • {name}: {detail}"
                ttk.Label(parent, text=bullet, style="Card.TLabel",
                          font=("Segoe UI", 8), wraplength=350).pack(anchor=tk.W)

        # Betting Edge / Model Validation
        if p1_implied and p2_implied:
            sep2 = ttk.Frame(parent, style="Card.TFrame", height=1)
            sep2.pack(fill=tk.X, pady=8)
            sep2.configure(style="Dark.TFrame")

            # Calculate edge
            if model_favors == p1_name:
                model_edge = p1_prob - p1_implied
                betfair_favors = p1_name if p1_implied > p2_implied else p2_name
            else:
                model_edge = p2_prob - p2_implied
                betfair_favors = p1_name if p1_implied > p2_implied else p2_name

            ttk.Label(parent, text="Model vs Market:",
                      style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 3))

            if model_favors == betfair_favors:
                agreement_text = f"Both agree: {model_favors} is the favorite"
                edge_text = f"Edge: Model gives {abs(model_edge):.1f}% {'more' if model_edge > 0 else 'less'} than Betfair"
            else:
                agreement_text = f"Disagreement! Model: {model_favors}, Betfair: {betfair_favors}"
                edge_text = f"Potential value on {model_favors} (model sees {model_prob:.1f}% vs market's {100 - model_prob:.1f}%)"

            ttk.Label(parent, text=f"  {agreement_text}", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(anchor=tk.W)
            ttk.Label(parent, text=f"  {edge_text}", style="Card.TLabel",
                      font=("Segoe UI", 8)).pack(anchor=tk.W)

    def _get_factor_detail(self, factor_key: str, factor_data: Dict, p1_name: str, p2_name: str) -> str:
        """Generate human-readable detail for a factor."""
        try:
            if factor_key == 'ranking':
                data = factor_data.get('data', {})
                p1_rank = data.get('p1_rank', '?')
                p2_rank = data.get('p2_rank', '?')
                return f"#{p1_rank} vs #{p2_rank}"

            elif factor_key == 'form':
                p1_data = factor_data.get('p1', {})
                p2_data = factor_data.get('p2', {})
                p1_record = f"{p1_data.get('wins', 0)}W-{p1_data.get('losses', 0)}L"
                p2_record = f"{p2_data.get('wins', 0)}W-{p2_data.get('losses', 0)}L"
                return f"{p1_name}: {p1_record}, {p2_name}: {p2_record}"

            elif factor_key == 'surface':
                p1_rate = factor_data.get('p1', {}).get('combined_win_rate', 0) * 100
                p2_rate = factor_data.get('p2', {}).get('combined_win_rate', 0) * 100
                return f"{p1_name}: {p1_rate:.0f}%, {p2_name}: {p2_rate:.0f}%"

            elif factor_key == 'h2h':
                data = factor_data.get('data', {})
                p1_wins = data.get('p1_wins', 0)
                p2_wins = data.get('p2_wins', 0)
                if p1_wins == 0 and p2_wins == 0:
                    return "No previous meetings"
                return f"{p1_name} leads {p1_wins}-{p2_wins}" if p1_wins > p2_wins else f"{p2_name} leads {p2_wins}-{p1_wins}"

            elif factor_key == 'fatigue':
                p1_status = factor_data.get('p1', {}).get('status', 'Unknown')
                p2_status = factor_data.get('p2', {}).get('status', 'Unknown')
                return f"{p1_name}: {p1_status}, {p2_name}: {p2_status}"

            elif factor_key == 'activity':
                p1_act = factor_data.get('p1', {})
                p2_act = factor_data.get('p2', {})
                return f"{p1_name}: {p1_act.get('status', 'Active')} ({p1_act.get('score', 100):.0f}), {p2_name}: {p2_act.get('status', 'Active')} ({p2_act.get('score', 100):.0f})"

            elif factor_key == 'opponent_quality':
                p1_score = factor_data.get('p1', {}).get('score', 0)
                p2_score = factor_data.get('p2', {}).get('score', 0)
                return f"Recent opponent strength weighted"

            elif factor_key == 'recency':
                return "How recent the form data is"

            elif factor_key == 'recent_loss':
                p1_pen = factor_data.get('p1', {}).get('penalty', 0)
                p2_pen = factor_data.get('p2', {}).get('penalty', 0)
                if p1_pen > 0 or p2_pen > 0:
                    if p1_pen > p2_pen:
                        return f"{p1_name} coming off recent loss"
                    else:
                        return f"{p2_name} coming off recent loss"
                return "Neither player has recent loss penalty"

            elif factor_key == 'momentum':
                p1_bonus = factor_data.get('p1', {}).get('bonus', 0)
                p2_bonus = factor_data.get('p2', {}).get('bonus', 0)
                if p1_bonus > p2_bonus:
                    return f"{p1_name} has tournament momentum"
                elif p2_bonus > p1_bonus:
                    return f"{p2_name} has tournament momentum"
                return "Similar momentum"

        except Exception:
            pass
        return ""

    def _create_value_section(self, parent, result: Dict, p1_name: str, p2_name: str,
                               p1_odds: float, p2_odds: float, analyzer, pack_side=None):
        """Create the value analysis section."""
        value_frame = ttk.Frame(parent, style="Card.TFrame", padding=15)
        if pack_side:
            value_frame.pack(side=pack_side, fill=tk.Y, pady=10)
        else:
            value_frame.pack(fill=tk.X, pady=10)

        ttk.Label(value_frame, text="Value Analysis", style="Card.TLabel",
                  font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))

        # Calculate value for both players (log=False for UI display, with serve edge modifier)
        serve_data_raw = result.get('serve_data') or result.get('factors', {}).get('serve', {}).get('data')
        activity_data_raw = result.get('activity_data')
        p1_value = analyzer.find_value(result['p1_probability'], p1_odds, log=False,
                                        serve_data=serve_data_raw, side='p1', activity_data=activity_data_raw)
        p2_value = analyzer.find_value(result['p2_probability'], p2_odds, log=False,
                                        serve_data=serve_data_raw, side='p2', activity_data=activity_data_raw)

        # Create comparison table
        row_frame = ttk.Frame(value_frame, style="Card.TFrame")
        row_frame.pack(fill=tk.X)

        # Headers with player colors
        headers = ["", p1_name[:25], p2_name[:25]]
        header_colors = [None, UI_COLORS["player1"], UI_COLORS["player2"]]
        for i, h in enumerate(headers):
            if header_colors[i]:
                tk.Label(row_frame, text=h, font=("Segoe UI", 9, "bold"),
                         fg=header_colors[i], bg=UI_COLORS["bg_medium"]).grid(row=0, column=i, padx=15, pady=2)
            else:
                ttk.Label(row_frame, text=h, style="Card.TLabel",
                          font=("Segoe UI", 9, "bold")).grid(row=0, column=i, padx=15, pady=2)

        # Odds row
        ttk.Label(row_frame, text="Betfair Odds", style="Card.TLabel").grid(row=1, column=0, padx=10, pady=2, sticky=tk.W)
        ttk.Label(row_frame, text=f"{p1_odds:.2f}", style="Card.TLabel").grid(row=1, column=1, padx=10, pady=2)
        ttk.Label(row_frame, text=f"{p2_odds:.2f}", style="Card.TLabel").grid(row=1, column=2, padx=10, pady=2)

        # Implied probability
        ttk.Label(row_frame, text="Implied Prob", style="Card.TLabel").grid(row=2, column=0, padx=10, pady=2, sticky=tk.W)
        ttk.Label(row_frame, text=f"{p1_value['implied_probability']*100:.1f}%", style="Card.TLabel").grid(row=2, column=1, padx=10, pady=2)
        ttk.Label(row_frame, text=f"{p2_value['implied_probability']*100:.1f}%", style="Card.TLabel").grid(row=2, column=2, padx=10, pady=2)

        # Our probability
        ttk.Label(row_frame, text="Our Prob", style="Card.TLabel").grid(row=3, column=0, padx=10, pady=2, sticky=tk.W)
        ttk.Label(row_frame, text=f"{p1_value['our_probability']*100:.1f}%", style="Card.TLabel").grid(row=3, column=1, padx=10, pady=2)
        ttk.Label(row_frame, text=f"{p2_value['our_probability']*100:.1f}%", style="Card.TLabel").grid(row=3, column=2, padx=10, pady=2)

        # Edge - use player colors
        ttk.Label(row_frame, text="Edge", style="Card.TLabel").grid(row=4, column=0, padx=10, pady=2, sticky=tk.W)
        tk.Label(row_frame, text=f"{p1_value['edge']*100:.1f}%", fg=UI_COLORS["player1"],
                 bg=UI_COLORS["bg_medium"], font=("Segoe UI", 9)).grid(row=4, column=1, padx=10, pady=2)
        tk.Label(row_frame, text=f"{p2_value['edge']*100:.1f}%", fg=UI_COLORS["player2"],
                 bg=UI_COLORS["bg_medium"], font=("Segoe UI", 9)).grid(row=4, column=2, padx=10, pady=2)

        # Expected Value - use player colors
        ttk.Label(row_frame, text="Expected Value", style="Card.TLabel").grid(row=5, column=0, padx=10, pady=2, sticky=tk.W)
        tk.Label(row_frame, text=f"{p1_value['expected_value']*100:.1f}%", fg=UI_COLORS["player1"],
                 bg=UI_COLORS["bg_medium"], font=("Segoe UI", 9, "bold")).grid(row=5, column=1, padx=10, pady=2)
        tk.Label(row_frame, text=f"{p2_value['expected_value']*100:.1f}%", fg=UI_COLORS["player2"],
                 bg=UI_COLORS["bg_medium"], font=("Segoe UI", 9, "bold")).grid(row=5, column=2, padx=10, pady=2)

        # Recommendation
        rec_frame = ttk.Frame(value_frame, style="Card.TFrame")
        rec_frame.pack(fill=tk.X, pady=(15, 0))

        if p1_value['is_value'] or p2_value['is_value']:
            best_bet = p1_name if p1_value['expected_value'] > p2_value['expected_value'] else p2_name
            best_ev = max(p1_value['expected_value'], p2_value['expected_value'])
            best_units = max(p1_value.get('recommended_units', 0), p2_value.get('recommended_units', 0))
            best_tier = p1_value.get('stake_tier', 'standard') if p1_value['expected_value'] > p2_value['expected_value'] else p2_value.get('stake_tier', 'standard')

            if best_ev > 0 and best_units > 0:
                tier_label = {"standard": "Standard", "confident": "Confident", "strong": "Strong"}.get(best_tier, "")
                # Format units nicely (1, 1.5, 2, etc.)
                units_str = f"{best_units:.1f}".rstrip('0').rstrip('.') if best_units % 1 else f"{int(best_units)}"
                unit_word = "unit" if best_units == 1 else "units"
                rec_text = f"✓ Value bet: {best_bet} (EV: +{best_ev*100:.1f}%, {units_str} {unit_word} - {tier_label})"
                rec_color = UI_COLORS["success"]
            elif best_ev > 0:
                rec_text = f"✓ Value bet: {best_bet} (EV: +{best_ev*100:.1f}%)"
                rec_color = UI_COLORS["success"]
            else:
                rec_text = "✗ No value found"
                rec_color = UI_COLORS["text_secondary"]
        else:
            rec_text = "✗ No value found at current odds"
            rec_color = UI_COLORS["text_secondary"]

        tk.Label(rec_frame, text=rec_text, font=("Segoe UI", 10, "bold"),
                 fg=rec_color, bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

    def _create_value_content(self, parent, result: Dict, p1_name: str, p2_name: str,
                               p1_odds: float, p2_odds: float, analyzer):
        """Create the value analysis content (no frame wrapper)."""
        ttk.Label(parent, text="Value Analysis", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 8))

        # Calculate value for both players (log=False for UI display, with serve edge modifier)
        serve_data_raw = result.get('serve_data') or result.get('factors', {}).get('serve', {}).get('data')
        activity_data_raw = result.get('activity_data')
        p1_value = analyzer.find_value(result['p1_probability'], p1_odds, log=False,
                                        serve_data=serve_data_raw, side='p1', activity_data=activity_data_raw)
        p2_value = analyzer.find_value(result['p2_probability'], p2_odds, log=False,
                                        serve_data=serve_data_raw, side='p2', activity_data=activity_data_raw)

        # Create comparison table
        row_frame = ttk.Frame(parent, style="Card.TFrame")
        row_frame.pack(fill=tk.X)

        # Headers with player colors
        headers = ["", p1_name[:20], p2_name[:20]]
        header_colors = [None, UI_COLORS["player1"], UI_COLORS["player2"]]
        for i, h in enumerate(headers):
            if header_colors[i]:
                tk.Label(row_frame, text=h, font=("Segoe UI", 9, "bold"),
                         fg=header_colors[i], bg=UI_COLORS["bg_medium"]).grid(row=0, column=i, padx=10, pady=2)
            else:
                ttk.Label(row_frame, text=h, style="Card.TLabel",
                          font=("Segoe UI", 9, "bold")).grid(row=0, column=i, padx=10, pady=2)

        # Odds row
        ttk.Label(row_frame, text="Betfair Odds", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=1, column=0, padx=8, pady=1, sticky=tk.W)
        ttk.Label(row_frame, text=f"{p1_odds:.2f}", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=1, column=1, padx=8, pady=1)
        ttk.Label(row_frame, text=f"{p2_odds:.2f}", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=1, column=2, padx=8, pady=1)

        # Implied probability
        ttk.Label(row_frame, text="Implied Prob", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=2, column=0, padx=8, pady=1, sticky=tk.W)
        ttk.Label(row_frame, text=f"{p1_value['implied_probability']*100:.1f}%", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=2, column=1, padx=8, pady=1)
        ttk.Label(row_frame, text=f"{p2_value['implied_probability']*100:.1f}%", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=2, column=2, padx=8, pady=1)

        # Our probability
        ttk.Label(row_frame, text="Our Prob", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=3, column=0, padx=8, pady=1, sticky=tk.W)
        ttk.Label(row_frame, text=f"{p1_value['our_probability']*100:.1f}%", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=3, column=1, padx=8, pady=1)
        ttk.Label(row_frame, text=f"{p2_value['our_probability']*100:.1f}%", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=3, column=2, padx=8, pady=1)

        # Edge - use player colors
        ttk.Label(row_frame, text="Edge", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=4, column=0, padx=8, pady=1, sticky=tk.W)
        tk.Label(row_frame, text=f"{p1_value['edge']*100:.1f}%", fg=UI_COLORS["player1"],
                 bg=UI_COLORS["bg_medium"], font=("Segoe UI", 8)).grid(row=4, column=1, padx=8, pady=1)
        tk.Label(row_frame, text=f"{p2_value['edge']*100:.1f}%", fg=UI_COLORS["player2"],
                 bg=UI_COLORS["bg_medium"], font=("Segoe UI", 8)).grid(row=4, column=2, padx=8, pady=1)

        # Expected Value - use player colors
        ttk.Label(row_frame, text="Expected Value", style="Card.TLabel", font=("Segoe UI", 8)).grid(row=5, column=0, padx=8, pady=1, sticky=tk.W)
        tk.Label(row_frame, text=f"{p1_value['expected_value']*100:.1f}%", fg=UI_COLORS["player1"],
                 bg=UI_COLORS["bg_medium"], font=("Segoe UI", 8, "bold")).grid(row=5, column=1, padx=8, pady=1)
        tk.Label(row_frame, text=f"{p2_value['expected_value']*100:.1f}%", fg=UI_COLORS["player2"],
                 bg=UI_COLORS["bg_medium"], font=("Segoe UI", 8, "bold")).grid(row=5, column=2, padx=8, pady=1)

        # Recommendation
        rec_frame = ttk.Frame(parent, style="Card.TFrame")
        rec_frame.pack(fill=tk.X, pady=(10, 0))

        if p1_value['is_value'] or p2_value['is_value']:
            best_bet = p1_name if p1_value['expected_value'] > p2_value['expected_value'] else p2_name
            best_ev = max(p1_value['expected_value'], p2_value['expected_value'])
            best_units = max(p1_value.get('recommended_units', 0), p2_value.get('recommended_units', 0))
            best_tier = p1_value.get('stake_tier', 'standard') if p1_value['expected_value'] > p2_value['expected_value'] else p2_value.get('stake_tier', 'standard')

            if best_ev > 0 and best_units > 0:
                tier_label = {"standard": "Std", "confident": "Conf", "strong": "Strong"}.get(best_tier, "")
                rec_text = f"Value bet: {best_bet}"
                rec_detail = f"EV: +{best_ev*100:.1f}%, {best_units}U ({tier_label})"
                rec_color = UI_COLORS["success"]
            elif best_ev > 0:
                rec_text = f"Value bet: {best_bet}"
                rec_detail = f"EV: +{best_ev*100:.1f}%"
                rec_color = UI_COLORS["success"]
            else:
                rec_text = "No value found"
                rec_detail = ""
                rec_color = UI_COLORS["text_secondary"]
        else:
            rec_text = "No value at current odds"
            rec_detail = ""
            rec_color = UI_COLORS["text_secondary"]

        tk.Label(rec_frame, text=rec_text, font=("Segoe UI", 9, "bold"),
                 fg=rec_color, bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)
        if rec_detail:
            tk.Label(rec_frame, text=rec_detail, font=("Segoe UI", 8),
                     fg=rec_color, bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

    def _create_serve_stats_content(self, parent, p1_id, p2_id, p1_name, p2_name,
                                      serve_alignment_p1=None, serve_alignment_p2=None):
        """Create serve/return stats comparison table with alignment indicator."""
        from database import db

        ttk.Label(parent, text="Serve / Return Stats", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 8))

        # Serve alignment indicator (edge modifier)
        if serve_alignment_p1 or serve_alignment_p2:
            align_frame = ttk.Frame(parent, style="Card.TFrame")
            align_frame.pack(fill=tk.X, pady=(0, 8))

            ttk.Label(align_frame, text="Edge Modifier:", style="Card.TLabel",
                      font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

            for label, align_info in [(p1_name, serve_alignment_p1), (p2_name, serve_alignment_p2)]:
                if align_info:
                    alignment = align_info.get('alignment', 'no_data')
                    dr_gap = align_info.get('dr_gap', 0)
                    if alignment == 'aligned':
                        color = UI_COLORS["success"]
                        symbol = f"ALIGNED (DR gap {dr_gap:.2f})"
                    elif alignment == 'conflicted':
                        reduction = (1 - align_info.get('modifier', 1.0)) * 100
                        color = UI_COLORS["danger"]
                        symbol = f"CONFLICT (DR gap {dr_gap:.2f}, edge -{reduction:.0f}%)"
                    elif alignment == 'neutral':
                        color = UI_COLORS["success"]
                        symbol = f"OK (DR gap {dr_gap:.2f} — no concern)"
                    else:
                        color = UI_COLORS["text_secondary"]
                        symbol = "No data"

                    tk.Label(align_frame, text=f"  {label[:20]}: {symbol}",
                             font=("Segoe UI", 8), fg=color, bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

            # Separator
            ttk.Frame(align_frame, style="Dark.TFrame", height=1).pack(fill=tk.X, pady=(5, 0))

        p1_serve = db.get_player_serve_stats(p1_id) if p1_id else None
        p2_serve = db.get_player_serve_stats(p2_id) if p2_id else None

        if not p1_serve and not p2_serve:
            ttk.Label(parent, text="No serve data available",
                      style="Card.TLabel", foreground=UI_COLORS["text_secondary"],
                      font=("Segoe UI", 9)).pack(anchor=tk.W, pady=10)
            return

        row_frame = ttk.Frame(parent, style="Card.TFrame")
        row_frame.pack(fill=tk.X)

        # Headers
        headers = ["", p1_name[:20], p2_name[:20]]
        header_colors = [None, UI_COLORS["player1"], UI_COLORS["player2"]]
        for i, h in enumerate(headers):
            if header_colors[i]:
                tk.Label(row_frame, text=h, font=("Segoe UI", 9, "bold"),
                         fg=header_colors[i], bg=UI_COLORS["bg_medium"]).grid(
                    row=0, column=i, padx=8, pady=2)
            else:
                ttk.Label(row_frame, text=h, style="Card.TLabel",
                          font=("Segoe UI", 9, "bold")).grid(
                    row=0, column=i, padx=8, pady=2)

        # Stat rows: (label, key, format, lower_is_better)
        stats = [
            # Section: Serve
            ("SERVE", None, None, False),
            ("1st Serve %", "first_serve_pct", "pct", False),
            ("1st Serve Won", "first_serve_won_pct", "pct", False),
            ("2nd Serve Won", "second_serve_won_pct", "pct", False),
            ("Aces/Match", "aces_per_match", "dec", False),
            ("DFs/Match", "dfs_per_match", "dec", True),
            ("Svc Games Won", "service_games_won_pct", "pct", False),
            # Section: Return
            ("RETURN", None, None, False),
            ("Return 1st Won", "return_1st_won_pct", "pct", False),
            ("Return 2nd Won", "return_2nd_won_pct", "pct", False),
            ("BP Converted", "bp_converted_pct", "pct", False),
            ("Ret Games Won", "return_games_won_pct", "pct", False),
            # Section: Overall
            ("OVERALL", None, None, False),
            ("BP Saved", "bp_saved_pct", "pct", False),
            ("Dominance Ratio", "dominance_ratio", "dec", False),
            ("Tiebreak Won", "tiebreak_won_pct", "pct", False),
        ]

        row_idx = 1
        for label, key, fmt, lower_is_better in stats:
            if key is None:
                # Section header
                ttk.Label(row_frame, text=label, style="Card.TLabel",
                          font=("Segoe UI", 8, "bold")).grid(
                    row=row_idx, column=0, columnspan=3, padx=8, pady=(6, 1), sticky=tk.W)
                row_idx += 1
                continue

            p1_val = p1_serve.get(key) if p1_serve else None
            p2_val = p2_serve.get(key) if p2_serve else None

            # Determine which is better
            p1_better = False
            p2_better = False
            if p1_val is not None and p2_val is not None:
                if lower_is_better:
                    p1_better = p1_val < p2_val
                    p2_better = p2_val < p1_val
                else:
                    p1_better = p1_val > p2_val
                    p2_better = p2_val > p1_val

            # Format values
            def fmt_val(val):
                if val is None:
                    return "—"
                if fmt == "pct":
                    return f"{val:.1f}%"
                return f"{val:.2f}"

            # Label
            ttk.Label(row_frame, text=label, style="Card.TLabel",
                      font=("Segoe UI", 8)).grid(
                row=row_idx, column=0, padx=8, pady=1, sticky=tk.W)

            # P1 value
            p1_color = UI_COLORS["success"] if p1_better else UI_COLORS["text_secondary"]
            tk.Label(row_frame, text=fmt_val(p1_val), font=("Segoe UI", 8),
                     fg=p1_color, bg=UI_COLORS["bg_medium"]).grid(
                row=row_idx, column=1, padx=8, pady=1)

            # P2 value
            p2_color = UI_COLORS["success"] if p2_better else UI_COLORS["text_secondary"]
            tk.Label(row_frame, text=fmt_val(p2_val), font=("Segoe UI", 8),
                     fg=p2_color, bg=UI_COLORS["bg_medium"]).grid(
                row=row_idx, column=2, padx=8, pady=1)

            row_idx += 1

        # Source attribution
        ttk.Label(parent, text="Source: Tennis Ratio", style="Card.TLabel",
                  foreground=UI_COLORS["text_secondary"],
                  font=("Segoe UI", 7)).pack(anchor=tk.W, pady=(8, 0))

    def _create_analysis_summary_detailed(self, parent, result: Dict, p1_name: str, p2_name: str,
                                           p1_odds, p2_odds):
        """Create a detailed narrative summary of the analysis."""
        factors = result.get('factors', {})
        p1_prob = result['p1_probability'] * 100
        p2_prob = result['p2_probability'] * 100
        model_favors = p1_name if p1_prob > p2_prob else p2_name
        model_fav_prob = max(p1_prob, p2_prob)

        ttk.Label(parent, text="Analysis Summary", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 8))

        # Model vs Betfair comparison
        try:
            p1_implied = (1 / float(p1_odds)) * 100
            p2_implied = (1 / float(p2_odds)) * 100
            betfair_favors = p1_name if p1_implied > p2_implied else p2_name
            betfair_fav_prob = max(p1_implied, p2_implied)

            # Model prediction line with player colors
            model_frame = ttk.Frame(parent, style="Card.TFrame")
            model_frame.pack(anchor=tk.W, pady=1)
            ttk.Label(model_frame, text="Model: ", style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)
            tk.Label(model_frame, text=f"{p1_name} {p1_prob:.0f}%", font=("Segoe UI", 9),
                     fg=UI_COLORS["player1"], bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)
            ttk.Label(model_frame, text=" vs ", style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)
            tk.Label(model_frame, text=f"{p2_name} {p2_prob:.0f}%", font=("Segoe UI", 9),
                     fg=UI_COLORS["player2"], bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)

            # Betfair line with player colors
            betfair_frame = ttk.Frame(parent, style="Card.TFrame")
            betfair_frame.pack(anchor=tk.W, pady=1)
            ttk.Label(betfair_frame, text="Betfair: ", style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)
            tk.Label(betfair_frame, text=f"{p1_name} {p1_implied:.0f}%", font=("Segoe UI", 9),
                     fg=UI_COLORS["player1"], bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)
            ttk.Label(betfair_frame, text=" vs ", style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)
            tk.Label(betfair_frame, text=f"{p2_name} {p2_implied:.0f}%", font=("Segoe UI", 9),
                     fg=UI_COLORS["player2"], bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)

            # Agreement/Disagreement - highlighted
            model_color = UI_COLORS["player1"] if model_favors == p1_name else UI_COLORS["player2"]
            if model_favors == betfair_favors:
                agree_frame = ttk.Frame(parent, style="Card.TFrame")
                agree_frame.pack(anchor=tk.W, pady=(5, 2))
                ttk.Label(agree_frame, text="Both favor ", style="Card.TLabel", font=("Segoe UI", 9)).pack(side=tk.LEFT)
                tk.Label(agree_frame, text=model_favors, font=("Segoe UI", 9, "bold"),
                         fg=model_color, bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)
            else:
                betfair_color = UI_COLORS["player1"] if betfair_favors == p1_name else UI_COLORS["player2"]
                tk.Label(parent, text="DISAGREE:", font=("Segoe UI", 9, "bold"),
                         fg=UI_COLORS["warning"], bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=(5, 0))
                disagree_frame = ttk.Frame(parent, style="Card.TFrame")
                disagree_frame.pack(anchor=tk.W, pady=1)
                ttk.Label(disagree_frame, text="  Model: ", style="Card.TLabel", font=("Segoe UI", 8)).pack(side=tk.LEFT)
                tk.Label(disagree_frame, text=model_favors, font=("Segoe UI", 8, "bold"),
                         fg=model_color, bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)
                ttk.Label(disagree_frame, text=", Market: ", style="Card.TLabel", font=("Segoe UI", 8)).pack(side=tk.LEFT)
                tk.Label(disagree_frame, text=betfair_favors, font=("Segoe UI", 8, "bold"),
                         fg=betfair_color, bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)

            # Edge explanation
            if model_favors != betfair_favors:
                edge = model_fav_prob - (100 - betfair_fav_prob)
                edge_frame = ttk.Frame(parent, style="Card.TFrame")
                edge_frame.pack(anchor=tk.W)
                ttk.Label(edge_frame, text="  Edge on ", style="Card.TLabel", font=("Segoe UI", 8)).pack(side=tk.LEFT)
                tk.Label(edge_frame, text=f"{model_favors}: {edge:.1f}%", font=("Segoe UI", 8, "bold"),
                         fg=model_color, bg=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)

        except (ValueError, ZeroDivisionError):
            pass

        # Key factors section
        key_factors_p1 = []
        key_factors_p2 = []

        factor_names = {
            'ranking': 'Ranking', 'form': 'Form', 'surface': 'Surface',
            'h2h': 'H2H', 'fatigue': 'Fatigue', 'activity': 'Activity',
            'opponent_quality': 'Opp Quality', 'recency': 'Recency',
            'recent_loss': 'Recent Loss', 'momentum': 'Momentum'
        }

        for factor_key, factor_data in factors.items():
            if isinstance(factor_data, dict) and 'advantage' in factor_data and 'weight' in factor_data:
                contrib = factor_data['advantage'] * factor_data['weight']
                if abs(contrib) > 0.005:
                    name = factor_names.get(factor_key, factor_key.title())
                    if contrib > 0:
                        key_factors_p1.append((name, contrib))
                    else:
                        key_factors_p2.append((name, abs(contrib)))

        key_factors_p1.sort(key=lambda x: x[1], reverse=True)
        key_factors_p2.sort(key=lambda x: x[1], reverse=True)

        # Display factors for each player
        ttk.Label(parent, text="Key Factors:", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(8, 2))

        if key_factors_p1:
            factors_list = ", ".join([f[0] for f in key_factors_p1[:4]])
            tk.Label(parent, text=f"{p1_name}: {factors_list}",
                     font=("Segoe UI", 8), fg=UI_COLORS["player1"],
                     bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=1)

        if key_factors_p2:
            factors_list = ", ".join([f[0] for f in key_factors_p2[:4]])
            tk.Label(parent, text=f"{p2_name}: {factors_list}",
                     font=("Segoe UI", 8), fg=UI_COLORS["player2"],
                     bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W, pady=1)

        # Additional insights
        weighted_adv = result.get('weighted_advantage', 0)
        confidence = result.get('confidence', 0) * 100

        ttk.Label(parent, text="Model Confidence:", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(8, 2))

        conf_color = UI_COLORS["success"] if confidence > 70 else UI_COLORS["warning"] if confidence > 50 else UI_COLORS["text_secondary"]
        conf_text = "High" if confidence > 70 else "Medium" if confidence > 50 else "Low"
        tk.Label(parent, text=f"{conf_text} ({confidence:.0f}%) - Weighted advantage: {abs(weighted_adv):.3f}",
                 font=("Segoe UI", 8), fg=conf_color,
                 bg=UI_COLORS["bg_medium"]).pack(anchor=tk.W)

    def _add_match_dialog(self):
        """Show dialog to add a new upcoming match."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Upcoming Match")
        dialog.geometry("500x450")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, style="Dark.TFrame", padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Tournament
        ttk.Label(frame, text="Tournament:", style="Dark.TLabel").grid(row=0, column=0, sticky=tk.W, pady=5)
        tournament_var = tk.StringVar()
        tournament_entry = ttk.Entry(frame, textvariable=tournament_var, width=40)
        tournament_entry.grid(row=0, column=1, pady=5, padx=10)

        # Date
        ttk.Label(frame, text="Date (YYYY-MM-DD):", style="Dark.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(frame, textvariable=date_var, width=40)
        date_entry.grid(row=1, column=1, pady=5, padx=10)

        # Surface
        ttk.Label(frame, text="Surface:", style="Dark.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        surface_var = tk.StringVar(value="Hard")
        surface_combo = ttk.Combobox(frame, textvariable=surface_var, values=SURFACES, width=37, state="readonly")
        surface_combo.grid(row=2, column=1, pady=5, padx=10)

        # Player 1
        ttk.Label(frame, text="Player 1:", style="Dark.TLabel").grid(row=3, column=0, sticky=tk.W, pady=5)
        p1_var = tk.StringVar()
        p1_combo = ttk.Combobox(frame, textvariable=p1_var, width=37)
        p1_combo['values'] = [p['name'] for p in self.players_cache][:100]
        p1_combo.grid(row=3, column=1, pady=5, padx=10)

        def filter_p1(event):
            typed = p1_var.get().lower()
            if len(typed) >= 2:
                filtered = [p['name'] for p in self.players_cache if typed in p['name'].lower()][:20]
                p1_combo['values'] = filtered

        p1_combo.bind('<KeyRelease>', filter_p1)

        # Player 1 Odds
        ttk.Label(frame, text="Player 1 Odds:", style="Dark.TLabel").grid(row=4, column=0, sticky=tk.W, pady=5)
        p1_odds_var = tk.StringVar()
        p1_odds_entry = ttk.Entry(frame, textvariable=p1_odds_var, width=40)
        p1_odds_entry.grid(row=4, column=1, pady=5, padx=10)

        # Player 2
        ttk.Label(frame, text="Player 2:", style="Dark.TLabel").grid(row=5, column=0, sticky=tk.W, pady=5)
        p2_var = tk.StringVar()
        p2_combo = ttk.Combobox(frame, textvariable=p2_var, width=37)
        p2_combo['values'] = [p['name'] for p in self.players_cache][:100]
        p2_combo.grid(row=5, column=1, pady=5, padx=10)

        def filter_p2(event):
            typed = p2_var.get().lower()
            if len(typed) >= 2:
                filtered = [p['name'] for p in self.players_cache if typed in p['name'].lower()][:20]
                p2_combo['values'] = filtered

        p2_combo.bind('<KeyRelease>', filter_p2)

        # Player 2 Odds
        ttk.Label(frame, text="Player 2 Odds:", style="Dark.TLabel").grid(row=6, column=0, sticky=tk.W, pady=5)
        p2_odds_var = tk.StringVar()
        p2_odds_entry = ttk.Entry(frame, textvariable=p2_odds_var, width=40)
        p2_odds_entry.grid(row=6, column=1, pady=5, padx=10)

        # Round
        ttk.Label(frame, text="Round:", style="Dark.TLabel").grid(row=7, column=0, sticky=tk.W, pady=5)
        round_var = tk.StringVar(value="R32")
        round_combo = ttk.Combobox(frame, textvariable=round_var,
                                    values=["F", "SF", "QF", "R16", "R32", "R64", "R128"], width=37)
        round_combo.grid(row=7, column=1, pady=5, padx=10)

        def save_match():
            p1_name = p1_var.get()
            p2_name = p2_var.get()

            if not p1_name or not p2_name:
                messagebox.showwarning("Missing Info", "Please enter both players.")
                return

            p1_id = self._get_player_id(p1_name)
            p2_id = self._get_player_id(p2_name)

            try:
                p1_odds = float(p1_odds_var.get()) if p1_odds_var.get() else None
                p2_odds = float(p2_odds_var.get()) if p2_odds_var.get() else None
            except ValueError:
                messagebox.showwarning("Invalid Odds", "Please enter valid decimal odds.")
                return

            match_data = {
                'tournament': tournament_var.get(),
                'date': date_var.get(),
                'surface': surface_var.get(),
                'round': round_var.get(),
                'player1_id': p1_id,
                'player2_id': p2_id,
                'player1_name': p1_name,
                'player2_name': p2_name,
                'player1_odds': p1_odds,
                'player2_odds': p2_odds,
            }

            db.add_upcoming_match(match_data)
            self._refresh_matches()
            dialog.destroy()

        # Save button
        save_btn = tk.Button(
            frame,
            text="Add Match",
            font=("Segoe UI", 11),
            fg="white",
            bg=UI_COLORS["success"],
            relief=tk.FLAT,
            cursor="hand2",
            command=save_match,
            padx=20,
            pady=8
        )
        save_btn.grid(row=8, column=1, pady=20, sticky=tk.E)

    def _show_filter_dialog(self):
        """Show filter settings dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Filter Settings")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog on parent window
        dialog_width = 350
        dialog_height = 300
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_width = self.root.winfo_width()
        parent_height = self.root.winfo_height()
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        frame = ttk.Frame(dialog, style="Dark.TFrame", padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Filter Value Bets", style="Dark.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor=tk.W, pady=(0, 15))

        # Min EV
        min_ev_frame = ttk.Frame(frame, style="Dark.TFrame")
        min_ev_frame.pack(fill=tk.X, pady=5)
        ttk.Label(min_ev_frame, text="Min EV (%):", style="Dark.TLabel").pack(side=tk.LEFT)
        min_ev_var = tk.IntVar(value=self.filter_settings['min_ev'])
        min_ev_spin = ttk.Spinbox(min_ev_frame, from_=0, to=100, width=8, textvariable=min_ev_var)
        min_ev_spin.pack(side=tk.RIGHT)

        # Max EV
        max_ev_frame = ttk.Frame(frame, style="Dark.TFrame")
        max_ev_frame.pack(fill=tk.X, pady=5)
        ttk.Label(max_ev_frame, text="Max EV (%):", style="Dark.TLabel").pack(side=tk.LEFT)
        max_ev_var = tk.IntVar(value=self.filter_settings['max_ev'])
        max_ev_spin = ttk.Spinbox(max_ev_frame, from_=1, to=500, width=8, textvariable=max_ev_var)
        max_ev_spin.pack(side=tk.RIGHT)

        # Min Units
        units_frame = ttk.Frame(frame, style="Dark.TFrame")
        units_frame.pack(fill=tk.X, pady=5)
        ttk.Label(units_frame, text="Min Units:", style="Dark.TLabel").pack(side=tk.LEFT)
        units_var = tk.IntVar(value=self.filter_settings['min_units'])
        units_spin = ttk.Spinbox(units_frame, from_=0, to=5, width=8, textvariable=units_var)
        units_spin.pack(side=tk.RIGHT)

        # Buttons
        btn_frame = ttk.Frame(frame, style="Dark.TFrame")
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        def apply_filters():
            self.filter_settings['min_ev'] = min_ev_var.get()
            self.filter_settings['max_ev'] = max_ev_var.get()
            self.filter_settings['min_units'] = units_var.get()
            dialog.destroy()
            # Re-analyze with new filters
            self._analyze_all()

        def reset_defaults():
            min_ev_var.set(5)
            max_ev_var.set(100)
            units_var.set(0.5)

        reset_btn = tk.Button(
            btn_frame, text="Reset Defaults", font=("Segoe UI", 10),
            fg="white", bg=UI_COLORS["bg_light"], relief=tk.FLAT,
            cursor="hand2", command=reset_defaults, padx=10, pady=5
        )
        reset_btn.pack(side=tk.LEFT)

        apply_btn = tk.Button(
            btn_frame, text="Apply & Analyze", font=("Segoe UI", 10),
            fg="white", bg=UI_COLORS["accent"], relief=tk.FLAT,
            cursor="hand2", command=apply_filters, padx=15, pady=5
        )
        apply_btn.pack(side=tk.RIGHT)

    def _analyze_all(self):
        """Analyze all upcoming matches and display in sortable table."""
        # Clear previous results
        self.value_tree.delete(*self.value_tree.get_children())
        self.current_value_bets = []
        self.add_all_btn.config(state=tk.DISABLED)

        try:
            results = self.suggester.analyze_all_upcoming()
            value_count = 0
            total_ev = 0
            skipped_low_stake = 0
            skipped_low_ev = 0
            skipped_high_ev = 0
            skipped_no_model = 0
            min_ev = self.filter_settings['min_ev'] / 100.0
            max_ev = self.filter_settings['max_ev'] / 100.0
            min_units = self.filter_settings['min_units']

            for result in results:
                if result['value_bets']:
                    for bet in result['value_bets']:
                        # Skip bets below minimum units
                        if bet.get('recommended_units', 0) < min_units:
                            skipped_low_stake += 1
                            continue

                        # Skip bets below minimum EV threshold
                        if bet.get('expected_value', 0) < min_ev:
                            skipped_low_ev += 1
                            continue

                        # Skip bets above maximum EV threshold
                        if bet.get('expected_value', 0) > max_ev:
                            skipped_high_ev += 1
                            continue

                        # Calculate model qualification early to filter out non-qualifying bets
                        match = result['match']
                        analysis = result.get('analysis')
                        factor_scores = None
                        surface_score_for_pick = None
                        if analysis and 'factors' in analysis:
                            is_p1_bet = bet.get('selection') == 'player1'
                            factor_scores = {
                                'is_p1_bet': is_p1_bet,
                                'factors': {
                                    fname: {'advantage': fdata.get('advantage', 0)}
                                    for fname, fdata in analysis['factors'].items()
                                }
                            }
                            # Surface score adjusted for pick direction (for M11)
                            surface_data = analysis['factors'].get('surface', {})
                            raw_surface = surface_data.get('advantage', 0) if isinstance(surface_data, dict) else 0
                            surface_score_for_pick = raw_surface if is_p1_bet else -raw_surface

                        models = calculate_bet_model(
                            bet['our_probability'],
                            bet['implied_probability'],
                            match.get('tournament', ''),
                            bet['odds'],
                            factor_scores,
                            serve_alignment=bet.get('serve_alignment'),
                            min_player_matches=self.suggester._get_min_player_matches(match),
                            activity_driven_edge=bet.get('activity_driven_edge', False),
                            activity_min_score=bet.get('activity_min_score'),
                            surface_score_for_pick=surface_score_for_pick
                        )

                        # Skip bets that don't qualify for any model
                        if models == "None" or not models:
                            skipped_no_model += 1
                            continue

                        # Store bet data for table and bulk add
                        # Get both players' EVs
                        p1_ev = result['p1_value']['expected_value'] if result.get('p1_value') else 0
                        p2_ev = result['p2_value']['expected_value'] if result.get('p2_value') else 0
                        bet_data = {
                            'match': match,
                            'bet': bet,
                            'analysis': result.get('analysis'),  # Store full analysis for factor scores
                            'confidence': result['confidence'],
                            'p1_probability': result['p1_probability'],
                            'p2_probability': result['p2_probability'],
                            # For sorting
                            'tour': get_tour_level(match.get('tournament', '')),
                            'tournament': match.get('tournament', ''),  # Full tournament name for model calc
                            'time': match.get('date', ''),
                            'match_str': f"{match.get('player1_name', 'P1')} vs {match.get('player2_name', 'P2')}",
                            'selection': bet['player'],
                            'bet_type': bet.get('bet_type', 'MW'),  # MW = Match Winner, 2-0 = Set betting
                            'market_type': bet.get('market_type', 'MATCH_ODDS'),  # For M12 fade bets
                            'is_m12_fade': bet.get('is_m12_fade', False),
                            'odds': bet['odds'],
                            'our_prob': bet['our_probability'],
                            'implied_prob': bet['implied_probability'],  # For model calculation
                            'ev': bet['expected_value'],
                            'p1_ev': p1_ev,  # Both players' EVs
                            'p2_ev': p2_ev,
                            'units': bet.get('recommended_units', 0),
                            # Value confidence indicator
                            'value_confidence': bet.get('value_confidence', 'medium'),
                            'in_sweet_spot': bet.get('in_sweet_spot', True),
                            'prob_ratio': bet.get('prob_ratio', 1.0),
                            # Serve alignment edge modifier
                            'serve_alignment': bet.get('serve_alignment', 'neutral'),
                            'serve_modifier': bet.get('serve_modifier', 1.0),
                            'activity_driven_edge': bet.get('activity_driven_edge', False),
                            'activity_min_score': bet.get('activity_min_score'),
                            'surface_score_for_pick': surface_score_for_pick,
                        }
                        self.current_value_bets.append(bet_data)
                        value_count += 1
                        total_ev += bet['expected_value']

            # Populate the table
            self._populate_value_tree()

            # Enable Add All button if we have bets
            if value_count > 0:
                self.add_all_btn.config(state=tk.NORMAL)

            summary_text = f"Found {value_count} value bet(s) from {len(results)} matches."
            filtered_count = skipped_low_stake + skipped_low_ev + skipped_high_ev + skipped_no_model
            if filtered_count > 0:
                summary_text += f" ({filtered_count} filtered, {skipped_no_model} no model)"
            if value_count > 0:
                summary_text += f" Total EV: {total_ev:.2%}"
            self.summary_var.set(summary_text)

        except Exception as e:
            messagebox.showerror("Analysis Error", str(e))

        # Notify main window to refresh stats (e.g. analysed counter)
        if self.on_change_callback:
            try:
                self.on_change_callback()
            except Exception:
                pass

    def _populate_value_tree(self):
        """Populate the value bets treeview with current data."""
        self.value_tree.delete(*self.value_tree.get_children())

        for i, bet_data in enumerate(self.current_value_bets):
            # Format display values
            time_str = bet_data['time'][:10] if bet_data['time'] else ""
            match_str = bet_data['match_str'][:35] + "..." if len(bet_data['match_str']) > 35 else bet_data['match_str']
            odds_str = f"{bet_data['odds']:.2f}"
            prob_str = f"{bet_data['our_prob']*100:.0f}%"
            ev_str = f"{bet_data['ev']*100:.1f}%"
            units_str = f"{bet_data['units']:.1f}".rstrip('0').rstrip('.')

            # Value confidence indicator with symbols
            value_conf = bet_data.get('value_confidence', 'medium')
            prob_ratio = bet_data.get('prob_ratio', 1.0)
            in_sweet = bet_data.get('in_sweet_spot', True)

            # Build confidence display: ratio + indicator
            if value_conf == 'high':
                conf_str = f"{prob_ratio:.1f}x"  # Green - safe
                tag = "conf_high"
            elif value_conf == 'medium':
                conf_str = f"{prob_ratio:.1f}x"  # Yellow - caution
                tag = "conf_medium"
            else:
                conf_str = f"{prob_ratio:.1f}x"  # Red - risky
                tag = "conf_low"

            # Add sweet spot indicator
            if not in_sweet:
                odds_str = f"{bet_data['odds']:.2f}*"  # Asterisk for outside sweet spot

            # Build factor_scores for model calculation
            factor_scores = None
            analysis = bet_data.get('analysis')
            if analysis and 'factors' in analysis:
                bet_obj = bet_data.get('bet', {})
                is_p1_bet = bet_obj.get('selection') == 'player1'
                factor_scores = {
                    'is_p1_bet': is_p1_bet,
                    'factors': {
                        fname: {'advantage': fdata.get('advantage', 0)}
                        for fname, fdata in analysis['factors'].items()
                    }
                }

            # Calculate model qualification
            models = calculate_bet_model(
                bet_data['our_prob'],
                bet_data.get('implied_prob', 1 / bet_data['odds'] if bet_data['odds'] else 0),
                bet_data.get('tournament', ''),
                bet_data.get('odds'),
                factor_scores,
                serve_alignment=bet_data.get('serve_alignment'),
                activity_driven_edge=bet_data.get('activity_driven_edge', False),
                activity_min_score=bet_data.get('activity_min_score'),
                surface_score_for_pick=bet_data.get('surface_score_for_pick')
            )
            # Shorten for display: "Model 1, Model 2" -> "1, 2"
            models_short = models.replace("Model ", "")

            # Serve alignment indicator
            serve_align = bet_data.get('serve_alignment', 'no_data')
            if serve_align in ('aligned', 'neutral'):
                serve_str = "OK"
            elif serve_align == 'conflicted':
                reduction = (1 - bet_data.get('serve_modifier', 1.0)) * 100
                serve_str = f"-{reduction:.0f}%"
            else:
                serve_str = "--"

            # Determine bet type (Match Winner or 2-0)
            bet_type_str = bet_data.get('bet_type', 'MW')  # MW = Match Winner
            if bet_type_str == '2-0':
                bet_type_str = '2-0'
            else:
                bet_type_str = 'MW'

            self.value_tree.insert("", tk.END, iid=str(i), values=(
                bet_data.get('tour', '?'),
                time_str,
                match_str,
                bet_data['selection'],
                bet_type_str,
                odds_str,
                prob_str,
                ev_str,
                units_str,
                conf_str,
                serve_str,
                models_short,
            ), tags=(tag,))

        # Configure tag colors based on value confidence
        self.value_tree.tag_configure("conf_high", foreground="#22c55e")    # Green - safe bet
        self.value_tree.tag_configure("conf_medium", foreground="#f59e0b")  # Yellow - caution
        self.value_tree.tag_configure("conf_low", foreground="#ef4444")     # Red - likely model error

    def _sort_value_tree(self, column):
        """Sort the value tree by the specified column."""
        # Toggle sort direction if same column
        if self._sorted_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sorted_column = column
            self._sort_reverse = False

        # Define sort key based on column
        if column == "time":
            key_func = lambda x: x['time']
        elif column == "match":
            key_func = lambda x: x['match_str'].lower()
        elif column == "selection":
            key_func = lambda x: x['selection'].lower()
        elif column == "odds":
            key_func = lambda x: x['odds']
        elif column == "our_prob":
            key_func = lambda x: x['our_prob']
        elif column == "ev":
            key_func = lambda x: x['ev']
        elif column == "units":
            key_func = lambda x: x['units']
        elif column == "conf":
            key_func = lambda x: x.get('prob_ratio', 1.0)
        else:
            return

        # Sort the data
        self.current_value_bets.sort(key=key_func, reverse=self._sort_reverse)

        # Repopulate tree
        self._populate_value_tree()

        # Update column header to show sort direction
        for col in ("time", "match", "selection", "odds", "our_prob", "ev", "units"):
            text = {"time": "Time", "match": "Match", "selection": "Selection",
                    "odds": "Odds", "our_prob": "Our %", "ev": "EV", "units": "Units"}[col]
            if col == column:
                text += " ▼" if self._sort_reverse else " ▲"
            self.value_tree.heading(col, text=text)

    def _on_value_tree_double_click(self, event):
        """Handle double-click on value tree to open match analysis."""
        selection = self.value_tree.selection()
        if selection:
            idx = int(selection[0])
            if 0 <= idx < len(self.current_value_bets):
                bet_data = self.current_value_bets[idx]
                self._show_match_analysis(bet_data['match'])

    def _on_value_tree_right_click(self, event):
        """Show context menu on right-click."""
        # Select the item under cursor
        item = self.value_tree.identify_row(event.y)
        if item:
            self.value_tree.selection_set(item)

            # Create context menu
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Add to Tracker", command=lambda: self._add_selected_to_tracker(item))
            menu.add_command(label="View Analysis", command=lambda: self._on_value_tree_double_click(None))
            menu.post(event.x_root, event.y_root)

    def _add_selected_to_tracker(self, item):
        """Add a single selected bet to tracker."""
        idx = int(item)
        if 0 <= idx < len(self.current_value_bets):
            bet_data = self.current_value_bets[idx]
            self._quick_place_bet(bet_data['match'], bet_data['bet'])

    def _add_all_to_tracker(self):
        """Add all displayed value bets to the bet tracker."""
        if not self.current_value_bets:
            messagebox.showinfo("No Bets", "No value bets to add.")
            return

        # SAFEGUARD: Check for unknown players (not in database)
        # These have been losing at -71.5% ROI - don't auto-add them
        unknown_player_bets = []
        known_player_bets = []

        for bet_data in self.current_value_bets:
            analysis = bet_data.get('analysis', {})
            bet = bet_data['bet']
            match = bet_data['match']

            # Check if selection is an unknown player (ranking was estimated from odds)
            is_unknown = False
            selection_is_p1 = bet.get('selection') == 'player1'

            if analysis and 'factors' in analysis:
                ranking_data = analysis['factors'].get('ranking', {}).get('data', {})
                if selection_is_p1 and ranking_data.get('p1_estimated', False):
                    is_unknown = True
                elif not selection_is_p1 and ranking_data.get('p2_estimated', False):
                    is_unknown = True

            if is_unknown:
                player_name = bet.get('player', 'Unknown')
                odds = bet.get('odds', 0)
                stake = bet.get('recommended_units', 0)
                # Determine player position
                player_position = 'player1' if selection_is_p1 else 'player2'
                unknown_player_bets.append({
                    'bet_data': bet_data,
                    'player': player_name,
                    'odds': odds,
                    'stake': stake,
                    'match': f"{match.get('player1_name', '')} vs {match.get('player2_name', '')}",
                    'match_id': match.get('id'),
                    'player_position': player_position
                })
            else:
                known_player_bets.append(bet_data)

        # If unknown players found, show custom dialog with 3 options
        if unknown_player_bets:
            choice = self._show_unknown_players_dialog(unknown_player_bets, known_player_bets)

            if choice == 'cancel':
                return
            elif choice == 'review':
                # Open the resolver dialog
                resolver = UnknownPlayerResolverDialog(
                    self.root,
                    unknown_player_bets,
                    db
                )
                results = resolver.get_results()

                if results is None:
                    # User cancelled
                    return

                # Process results - update database and re-analyze resolved matches
                resolved_bets = []
                skipped_count = 0
                matches_to_reanalyze = set()

                for result in results:
                    if result['action'] == 'skipped':
                        skipped_count += 1
                        continue

                    # Update the upcoming_matches table with the correct player ID
                    match_id = result.get('match_id')
                    player_position = result.get('player_position')
                    player_id = result.get('player_id')

                    if match_id and player_position and player_id:
                        db.update_upcoming_match_player_id(match_id, player_position, player_id)
                        matches_to_reanalyze.add(match_id)

                    resolved_bets.append(result['bet_data'])

                # Re-analyze the resolved matches to get proper probabilities
                if matches_to_reanalyze:
                    print(f"Re-analyzing {len(matches_to_reanalyze)} match(es) with resolved players...")
                    # Get fresh match data and re-analyze
                    updated_bets = []
                    for bet_data in resolved_bets:
                        match_id = bet_data['match'].get('id')
                        if match_id in matches_to_reanalyze:
                            # Get fresh match data from database
                            matches = db.get_upcoming_matches()
                            fresh_match = next((m for m in matches if m['id'] == match_id), None)
                            if fresh_match:
                                # Re-analyze with the new player ID
                                try:
                                    new_analysis = self.suggester.analyze_upcoming_match(fresh_match)
                                    # Find the bet for the same selection
                                    selection = bet_data['bet'].get('selection')
                                    if selection == 'player1' and new_analysis.get('p1_value'):
                                        new_bet = new_analysis['p1_value']
                                    elif selection == 'player2' and new_analysis.get('p2_value'):
                                        new_bet = new_analysis['p2_value']
                                    else:
                                        # Keep original if no value found
                                        updated_bets.append(bet_data)
                                        continue

                                    updated_bets.append({
                                        'match': fresh_match,
                                        'bet': new_bet,
                                        'analysis': new_analysis.get('analysis')
                                    })
                                except Exception as e:
                                    print(f"Error re-analyzing match: {e}")
                                    updated_bets.append(bet_data)
                            else:
                                updated_bets.append(bet_data)
                        else:
                            updated_bets.append(bet_data)

                    resolved_bets = updated_bets

                # Combine known and resolved bets
                bets_to_add = known_player_bets + resolved_bets
                skipped_unknown = skipped_count

            elif choice == 'known_only':
                # User chose to proceed with known players only
                bets_to_add = known_player_bets
                skipped_unknown = len(unknown_player_bets)
        else:
            # No unknown players - proceed with all
            bets_to_add = self.current_value_bets
            skipped_unknown = 0

        # Confirm action
        count = len(bets_to_add)
        if count == 0:
            messagebox.showinfo("No Bets", "No bets to add after filtering.")
            return

        if not messagebox.askyesno("Confirm", f"Add {count} bet(s) to the tracker?"):
            return

        try:
            added = 0
            skipped = 0
            added_this_batch = set()  # Track duplicates within this Add All operation

            for bet_data in bets_to_add:
                match = bet_data['match']
                bet = bet_data['bet']
                analysis = bet_data.get('analysis')

                match_description = f"{match.get('player1_name', '')} vs {match.get('player2_name', '')}"
                selection = bet.get('player', '')
                match_date = match.get('date', '')

                # Get tournament for duplicate checking
                tournament = match.get('tournament', '')

                # Get market type (SET_BETTING for M12 2-0 bets, MATCH_ODDS for normal)
                market_type = bet.get('market_type', 'MATCH_ODDS')

                # Check for duplicate within this batch (handles duplicate upcoming matches)
                # Include market type in batch key to allow 2-0 and MW bets on same match
                batch_key = (tournament, match_description, selection, market_type)
                if batch_key in added_this_batch:
                    skipped += 1
                    continue

                # Check for duplicate bet in database (includes settled bets)
                if db.check_duplicate_bet(match_description, selection, match_date, tournament):
                    skipped += 1
                    continue

                # Also check if ANY bet exists for this match (prevents betting same match twice)
                # Pass market type - allows SET_BETTING (2-0) and MATCH_ODDS to coexist
                if db.check_match_already_bet(match_description, tournament, market_type):
                    skipped += 1
                    continue

                recommended_stake = bet.get('recommended_units', 1)

                # Extract full factor data for display
                factor_scores = None
                if analysis and 'factors' in analysis:
                    factors = analysis['factors']
                    is_p1_bet = bet.get('selection') == 'player1'

                    # Store full factor data for display
                    factor_scores = {
                        'is_p1_bet': is_p1_bet,
                        'p1_name': match.get('player1_name', 'P1'),
                        'p2_name': match.get('player2_name', 'P2'),
                        'factors': {}
                    }

                    for factor_name, factor_data in factors.items():
                        advantage = factor_data.get('advantage', 0)
                        weight = factor_data.get('weight', 0)
                        contribution = advantage * weight

                        # Store full data
                        factor_scores['factors'][factor_name] = {
                            'p1': factor_data.get('p1'),
                            'p2': factor_data.get('p2'),
                            'data': factor_data.get('data'),  # For ranking/h2h
                            'advantage': advantage,
                            'weight': weight,
                            'contribution': round(contribution, 4)
                        }

                # Prepare bet data for database
                import json

                # Determine market name for display
                if market_type == 'Set Handicap':
                    market_name = f"Set Betting ({bet.get('bet_type', '2-0')})"
                else:
                    market_name = 'Match Winner'

                db_bet = {
                    'match_date': match.get('date', datetime.now().strftime("%Y-%m-%d")),
                    'tournament': match.get('tournament', ''),
                    'match_description': match_description,
                    'player1': match.get('player1_name', ''),
                    'player2': match.get('player2_name', ''),
                    'market': market_type,  # Store the market type for duplicate checking
                    'selection': f"{selection} {bet.get('bet_type', '')}" if bet.get('bet_type') == '2-0' else selection,
                    'stake': recommended_stake,
                    'odds': bet.get('odds'),
                    'our_probability': bet.get('our_probability'),
                    'implied_probability': bet.get('implied_probability'),
                    'ev_at_placement': bet.get('expected_value'),
                    'notes': f"Surface: {match.get('surface', '')} | Kelly: {bet.get('kelly_stake_pct', 0):.1f}% | Disagree: {bet.get('disagreement_level', 'N/A')}" + (f" | M12 fade of {bet.get('original_trigger', '')}" if bet.get('is_m12_fade') else ""),
                    'factor_scores': json.dumps(factor_scores) if factor_scores else None,
                    'weighting': 'Default',  # Single default weight profile
                }

                # For M12 fade bets, set model directly
                if bet.get('is_m12_fade'):
                    db_bet['model'] = f"Model 12 ({bet.get('original_trigger', 'fade')})"
                else:
                    # Calculate model tags (M1, M3, M5, etc.)
                    db_bet['model'] = calculate_bet_model(
                        db_bet.get('our_probability', 0.5),
                        db_bet.get('implied_probability', 0.5),
                        db_bet.get('tournament', ''),
                        db_bet.get('odds'),
                        factor_scores,
                        serve_alignment=bet_data.get('serve_alignment'),
                        min_player_matches=self.suggester._get_min_player_matches(match),
                        activity_driven_edge=bet.get('activity_driven_edge', False),
                        activity_min_score=bet.get('activity_min_score'),
                        surface_score_for_pick=bet_data.get('surface_score_for_pick')
                    )

                # Skip bets that don't qualify for any model
                if db_bet['model'] == "None" or not db_bet['model']:
                    skipped += 1
                    continue

                bet_id = db.add_bet(db_bet)
                added += 1
                added_this_batch.add(batch_key)

                # Sync to cloud for Discord monitor
                if CLOUD_SYNC_AVAILABLE:
                    try:
                        db_bet['id'] = bet_id
                        sync_bet_to_cloud(db_bet)
                    except Exception:
                        pass  # Silent fail - cloud sync is optional

            # Build success message
            msg_parts = [f"Added {added} bet(s) to the tracker."]
            if skipped > 0:
                msg_parts.append(f"{skipped} skipped (duplicates/data quality).")
            if skipped_unknown > 0:
                msg_parts.append(f"{skipped_unknown} unknown player bet(s) blocked.")
            messagebox.showinfo("Success", "\n".join(msg_parts))

            # Disable button after adding
            self.add_all_btn.config(state=tk.DISABLED)

            # Refresh bet tracker if it's open
            try:
                from bet_tracker import BetTrackerUI
                if BetTrackerUI._instance is not None and BetTrackerUI._root_window is not None:
                    if BetTrackerUI._root_window.winfo_exists():
                        BetTrackerUI._instance._refresh_data()
            except Exception:
                pass

            # Update main dashboard stats
            try:
                main_window = self.root.nametowidget('.')
                if hasattr(main_window, 'main_app') and hasattr(main_window.main_app, '_update_stats'):
                    main_window.main_app._update_stats()
            except Exception:
                pass

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add bets: {e}")

    def _show_unknown_players_dialog(self, unknown_players: List[Dict],
                                      known_players: List[Dict]) -> str:
        """
        Show a custom dialog for handling unknown players.
        Returns: 'review', 'known_only', or 'cancel'
        """
        unknown_list = "\n".join([
            f"  - {u['player']} ({u['stake']}u @ {u['odds']:.2f})"
            for u in unknown_players
        ])

        # Create custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Unknown Players Detected")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.geometry("550x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 550) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")

        result = {'choice': 'cancel'}

        # Warning icon and header
        header_frame = tk.Frame(dialog, bg=UI_COLORS["bg_dark"])
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))

        tk.Label(
            header_frame,
            text="⚠️",
            font=("Segoe UI", 24),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["warning"]
        ).pack(side=tk.LEFT)

        tk.Label(
            header_frame,
            text=f"  {len(unknown_players)} Unknown Player(s) Detected",
            font=("Segoe UI", 14, "bold"),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_primary"]
        ).pack(side=tk.LEFT)

        # Player list
        list_frame = tk.Frame(dialog, bg=UI_COLORS["bg_medium"], padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(
            list_frame,
            text=unknown_list,
            font=("Consolas", 10),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            justify=tk.LEFT
        ).pack(anchor=tk.W)

        # Warning message
        tk.Label(
            dialog,
            text="These players have no form/ranking data.\n"
                 "Probability is estimated from odds only.\n"
                 "Historical ROI on unknown players: -71.5%",
            font=("Segoe UI", 10),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["danger"],
            justify=tk.LEFT
        ).pack(padx=20, pady=10)

        # Buttons frame
        btn_frame = tk.Frame(dialog, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X, padx=20, pady=(10, 20))

        def set_choice(choice):
            result['choice'] = choice
            dialog.destroy()

        # Review & Match button (primary action)
        tk.Button(
            btn_frame,
            text="Review & Match",
            command=lambda: set_choice('review'),
            bg=UI_COLORS["accent"],
            fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=20, pady=10,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

        # Add tooltip explanation
        review_note = tk.Label(
            btn_frame,
            text="(Find in DB or add new)",
            font=("Segoe UI", 8),
            bg=UI_COLORS["bg_dark"],
            fg=UI_COLORS["text_secondary"]
        )
        review_note.pack(side=tk.LEFT)

        # Add Known Only button
        if len(known_players) > 0:
            tk.Button(
                btn_frame,
                text=f"Add {len(known_players)} Known Only",
                command=lambda: set_choice('known_only'),
                bg=UI_COLORS["success"],
                fg="white",
                font=("Segoe UI", 10),
                padx=15, pady=10,
                cursor="hand2"
            ).pack(side=tk.LEFT, padx=(20, 5))

        # Cancel button
        tk.Button(
            btn_frame,
            text="Cancel",
            command=lambda: set_choice('cancel'),
            bg=UI_COLORS["bg_medium"],
            fg=UI_COLORS["text_primary"],
            font=("Segoe UI", 10),
            padx=15, pady=10,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=5)

        dialog.wait_window()
        return result['choice']

    def _create_value_bet_card(self, match: Dict, bet: Dict, p1_prob: float, p2_prob: float, confidence: float):
        """Create a value bet display card."""
        card = ttk.Frame(self.value_frame, style="Card.TFrame", padding=15)
        card.pack(fill=tk.X, pady=5, padx=5)

        # Make card clickable to open match analysis
        def open_analysis(event=None):
            self._show_match_analysis(match)

        def bind_click_recursive(widget, exclude_buttons=True):
            """Bind click to widget and all children, except buttons."""
            widget_class = widget.winfo_class()
            if exclude_buttons and widget_class in ('Button', 'TButton'):
                return
            widget.bind("<Button-1>", open_analysis)
            widget.configure(cursor="hand2")
            for child in widget.winfo_children():
                bind_click_recursive(child, exclude_buttons)

        # Header row
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill=tk.X)

        # Match info
        match_info = f"{match.get('tournament', 'Unknown')} - {match.get('round', '')}"
        ttk.Label(header, text=match_info, style="Card.TLabel").pack(side=tk.LEFT)

        # EV badge
        ev = bet['expected_value']
        ev_style = "HighValue.TLabel" if bet['is_high_value'] else "Value.TLabel"
        ev_label = ttk.Label(header, text=f"EV: {ev:.1%}", style=ev_style)
        ev_label.pack(side=tk.RIGHT)

        # Players
        players_text = f"{match.get('player1_name', 'P1')} vs {match.get('player2_name', 'P2')}"
        ttk.Label(card, text=players_text, style="Card.TLabel").pack(anchor=tk.W, pady=(5, 0))

        # Surface and date
        meta_text = f"{match.get('surface', 'Unknown')} | {match.get('date', '')}"
        ttk.Label(card, text=meta_text, style="Card.TLabel").pack(anchor=tk.W)

        # Value bet details
        details_frame = ttk.Frame(card, style="Card.TFrame")
        details_frame.pack(fill=tk.X, pady=(10, 0))

        # Selection
        sel_frame = ttk.Frame(details_frame, style="Card.TFrame")
        sel_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(sel_frame, text="Selection:", style="Card.TLabel").pack(anchor=tk.W)
        ttk.Label(sel_frame, text=bet['player'], style="Value.TLabel").pack(anchor=tk.W)

        # Odds
        odds_frame = ttk.Frame(details_frame, style="Card.TFrame")
        odds_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(odds_frame, text="Odds:", style="Card.TLabel").pack(anchor=tk.W)
        ttk.Label(odds_frame, text=f"{bet['odds']:.2f}", style="Card.TLabel").pack(anchor=tk.W)

        # Our probability
        prob_frame = ttk.Frame(details_frame, style="Card.TFrame")
        prob_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(prob_frame, text="Our Prob:", style="Card.TLabel").pack(anchor=tk.W)
        ttk.Label(prob_frame, text=f"{bet['our_probability']:.1%}", style="Card.TLabel").pack(anchor=tk.W)

        # Implied probability
        impl_frame = ttk.Frame(details_frame, style="Card.TFrame")
        impl_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(impl_frame, text="Implied:", style="Card.TLabel").pack(anchor=tk.W)
        ttk.Label(impl_frame, text=f"{bet['implied_probability']:.1%}", style="Card.TLabel").pack(anchor=tk.W)

        # Edge
        edge_frame = ttk.Frame(details_frame, style="Card.TFrame")
        edge_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(edge_frame, text="Edge:", style="Card.TLabel").pack(anchor=tk.W)
        edge_color = UI_COLORS["success"] if bet['edge'] > 0 else UI_COLORS["danger"]
        edge_label = tk.Label(edge_frame, text=f"{bet['edge']:.1%}",
                             fg=edge_color, bg=UI_COLORS["bg_medium"],
                             font=("Segoe UI", 10))
        edge_label.pack(anchor=tk.W)

        # Model qualification
        model_frame = ttk.Frame(details_frame, style="Card.TFrame")
        model_frame.pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(model_frame, text="Models:", style="Card.TLabel").pack(anchor=tk.W)
        models = calculate_bet_model(
            bet['our_probability'],
            bet['implied_probability'],
            match.get('tournament', ''),
            bet.get('odds'),
            None,  # factor_scores not available in card view
            serve_alignment=bet.get('serve_alignment'),
            activity_driven_edge=bet.get('activity_driven_edge', False),
            activity_min_score=bet.get('activity_min_score'),
            surface_score_for_pick=bet.get('surface_score_for_pick')
        )
        # Color code: green if any model qualifies, gold for Model 1
        model_color = "#FFD700" if "Model 1" in models else (UI_COLORS["success"] if models != "None" else UI_COLORS["text_secondary"])
        tk.Label(model_frame, text=models,
                fg=model_color, bg=UI_COLORS["bg_medium"],
                font=("Segoe UI", 9)).pack(anchor=tk.W)

        # Recommended stake (units)
        stake_frame = ttk.Frame(details_frame, style="Card.TFrame")
        stake_frame.pack(side=tk.LEFT)
        ttk.Label(stake_frame, text="Rec. Stake:", style="Card.TLabel").pack(anchor=tk.W)
        units = bet.get('recommended_units', 0)
        tier = bet.get('stake_tier', 'standard')
        tier_labels = {"standard": "Std", "confident": "Conf", "strong": "Strong", "no_bet": ""}
        if units > 0:
            # Format units nicely (1, 1.5, 2, etc.)
            units_str = f"{units:.1f}".rstrip('0').rstrip('.') if units % 1 else f"{int(units)}"
            unit_word = "unit" if units == 1 else "units"
            stake_text = f"{units_str} {unit_word} ({tier_labels.get(tier, '')})"
        else:
            stake_text = "No bet"
        ttk.Label(stake_frame, text=stake_text, style="Card.TLabel").pack(anchor=tk.W)

        # Confidence
        conf_label = ttk.Label(card, text=f"Confidence: {confidence:.0%}", style="Card.TLabel")
        conf_label.pack(anchor=tk.E, pady=(5, 0))

        # Quick bet button
        bet_btn = tk.Button(
            card,
            text="Place Bet",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._quick_place_bet(match, bet),
            padx=10,
            pady=3
        )
        bet_btn.pack(anchor=tk.E, pady=(5, 0))

        # Bind click to card and all children (except the Place Bet button)
        bind_click_recursive(card)

        # Bind mousewheel scrolling to card and all children
        def bind_scroll_recursive(widget):
            widget.bind("<MouseWheel>", self._value_scroll_handler)
            for child in widget.winfo_children():
                bind_scroll_recursive(child)

        bind_scroll_recursive(card)

    def _quick_place_bet(self, match: Dict, bet: Dict):
        """Quick add bet to tracker with pre-filled data."""
        try:
            from bet_tracker import BetTrackerUI

            # Prepare prefill data for the bet tracker
            prefill_data = {
                'date': match.get('date', datetime.now().strftime("%Y-%m-%d")),
                'tournament': match.get('tournament', ''),
                'match_description': f"{match.get('player1_name', '')} vs {match.get('player2_name', '')}",
                'market': 'Match Winner',
                'selection': bet.get('player', ''),
                'odds': bet.get('odds'),
                'our_probability': bet.get('our_probability'),
                'notes': f"Surface: {match.get('surface', '')} | EV: {bet.get('expected_value', 0)*100:.1f}%",
            }

            # Open bet tracker with pre-filled data
            BetTrackerUI(self.root, prefill_bet=prefill_data)

        except ImportError as e:
            messagebox.showerror("Error", f"Could not open Bet Tracker: {e}")

    def _show_change_player_dialog(self, match: Dict, parent_dialog, refresh_callback):
        """Show dialog to change a player in the match to fix mismatches."""
        dialog = tk.Toplevel(parent_dialog)
        dialog.title("Change Player")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.geometry("550x500")
        dialog.transient(parent_dialog)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = parent_dialog.winfo_x() + (parent_dialog.winfo_width() - 550) // 2
        y = parent_dialog.winfo_y() + (parent_dialog.winfo_height() - 500) // 2
        dialog.geometry(f"+{x}+{y}")

        main_frame = tk.Frame(dialog, bg=UI_COLORS["bg_dark"], padx=20, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(main_frame, text="Change Player", font=("Segoe UI", 14, "bold"),
                 bg=UI_COLORS["bg_dark"], fg=UI_COLORS["text_primary"]).pack(anchor="w")
        tk.Label(main_frame, text="Select which player to change and search for the correct one",
                 font=("Segoe UI", 9), bg=UI_COLORS["bg_dark"],
                 fg=UI_COLORS["text_secondary"]).pack(anchor="w", pady=(5, 15))

        # Current players
        p1_name = match.get('player1_name', 'Unknown')
        p2_name = match.get('player2_name', 'Unknown')
        p1_id = match.get('player1_id')
        p2_id = match.get('player2_id')

        # Get match counts
        p1_matches = db.get_player_match_count(p1_id) if p1_id else 0
        p2_matches = db.get_player_match_count(p2_id) if p2_id else 0

        # Player selection frame
        players_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_medium"], padx=10, pady=10)
        players_frame.pack(fill=tk.X, pady=(0, 15))

        selected_player = tk.StringVar(value="player1")

        # Player 1 row
        p1_frame = tk.Frame(players_frame, bg=UI_COLORS["bg_medium"])
        p1_frame.pack(fill=tk.X, pady=5)
        tk.Radiobutton(p1_frame, variable=selected_player, value="player1",
                       bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                       selectcolor=UI_COLORS["bg_dark"], activebackground=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)
        p1_label = f"{p1_name} (ID: {p1_id}, {p1_matches} matches)"
        p1_color = UI_COLORS["danger"] if p1_matches == 0 else UI_COLORS["text_primary"]
        tk.Label(p1_frame, text=p1_label, font=("Segoe UI", 10),
                 bg=UI_COLORS["bg_medium"], fg=p1_color).pack(side=tk.LEFT, padx=5)

        # Player 2 row
        p2_frame = tk.Frame(players_frame, bg=UI_COLORS["bg_medium"])
        p2_frame.pack(fill=tk.X, pady=5)
        tk.Radiobutton(p2_frame, variable=selected_player, value="player2",
                       bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                       selectcolor=UI_COLORS["bg_dark"], activebackground=UI_COLORS["bg_medium"]).pack(side=tk.LEFT)
        p2_label = f"{p2_name} (ID: {p2_id}, {p2_matches} matches)"
        p2_color = UI_COLORS["danger"] if p2_matches == 0 else UI_COLORS["text_primary"]
        tk.Label(p2_frame, text=p2_label, font=("Segoe UI", 10),
                 bg=UI_COLORS["bg_medium"], fg=p2_color).pack(side=tk.LEFT, padx=5)

        # Search section
        tk.Label(main_frame, text="Search for replacement player:",
                 font=("Segoe UI", 10, "bold"), bg=UI_COLORS["bg_dark"],
                 fg=UI_COLORS["text_primary"]).pack(anchor="w", pady=(10, 5))

        search_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_dark"])
        search_frame.pack(fill=tk.X, pady=(0, 10))

        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var,
                                font=("Segoe UI", 10), bg=UI_COLORS["bg_medium"],
                                fg=UI_COLORS["text_primary"], insertbackground="white", width=40)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        # Results listbox
        results_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_medium"])
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        results_listbox = tk.Listbox(results_frame, font=("Segoe UI", 10),
                                     bg=UI_COLORS["bg_medium"], fg=UI_COLORS["text_primary"],
                                     selectbackground=UI_COLORS["primary"],
                                     selectforeground="white", height=8)
        results_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Store player data for results
        results_data = []

        def search_players(*args):
            query = search_var.get().strip()
            results_listbox.delete(0, tk.END)
            results_data.clear()

            if len(query) < 2:
                return

            # Search database for matching players
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, current_ranking
                    FROM players
                    WHERE name LIKE ? OR name LIKE ? OR name LIKE ?
                    ORDER BY
                        CASE WHEN current_ranking IS NULL THEN 1 ELSE 0 END,
                        current_ranking ASC
                    LIMIT 20
                ''', (f'{query}%', f'% {query}%', f'%{query}%'))

                for row in cursor.fetchall():
                    player_id, name, ranking = row
                    match_count = db.get_player_match_count(player_id)
                    rank_str = f"#{ranking}" if ranking else "unranked"
                    display = f"{name} ({rank_str}, {match_count} matches)"
                    results_listbox.insert(tk.END, display)
                    results_data.append({'id': player_id, 'name': name, 'ranking': ranking})

        search_var.trace('w', search_players)

        # Buttons
        btn_frame = tk.Frame(main_frame, bg=UI_COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X)

        def apply_change():
            selection = results_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a player from the search results.")
                return

            new_player = results_data[selection[0]]
            which_player = selected_player.get()

            # Update the upcoming_matches table
            match_id = match.get('id')
            if not match_id:
                messagebox.showerror("Error", "Match ID not found.")
                return

            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    if which_player == "player1":
                        cursor.execute('''
                            UPDATE upcoming_matches
                            SET player1_id = ?, player1_name = ?
                            WHERE id = ?
                        ''', (new_player['id'], new_player['name'], match_id))
                        old_name = p1_name
                    else:
                        cursor.execute('''
                            UPDATE upcoming_matches
                            SET player2_id = ?, player2_name = ?
                            WHERE id = ?
                        ''', (new_player['id'], new_player['name'], match_id))
                        old_name = p2_name

                messagebox.showinfo("Success",
                    f"Changed {old_name} to {new_player['name']}\n\nClick OK to refresh the analysis.")
                dialog.destroy()
                refresh_callback()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update player: {e}")

        apply_btn = tk.Button(btn_frame, text="Apply Change", font=("Segoe UI", 10),
                              fg="white", bg="#22c55e", relief=tk.FLAT, cursor="hand2",
                              command=apply_change, padx=15, pady=5)
        apply_btn.pack(side=tk.LEFT)

        cancel_btn = tk.Button(btn_frame, text="Cancel", font=("Segoe UI", 10),
                               fg="white", bg="#475569", relief=tk.FLAT, cursor="hand2",
                               command=dialog.destroy, padx=15, pady=5)
        cancel_btn.pack(side=tk.RIGHT)

        # Focus search entry
        search_entry.focus_set()

    def _open_player_profile(self, parent, player_id: int, player_name: str):
        """Open player profile popup when clicking on player name."""
        from database_ui import open_player_profile
        open_player_profile(parent, player_id, player_name)

    def _place_bet_from_analysis(self, match: Dict, player_name: str, odds, our_probability: float):
        """Place bet from the match analysis dialog."""
        try:
            from bet_tracker import BetTrackerUI

            # Calculate EV if we have odds
            ev = 0
            if odds and our_probability:
                odds_float = float(odds)
                ev = (our_probability * (odds_float - 1)) - (1 - our_probability)

            # Prepare prefill data for the bet tracker
            prefill_data = {
                'date': match.get('date', datetime.now().strftime("%Y-%m-%d")),
                'tournament': match.get('tournament', ''),
                'match_description': f"{match.get('player1_name', '')} vs {match.get('player2_name', '')}",
                'market': 'Match Winner',
                'selection': player_name,
                'odds': float(odds) if odds else None,
                'our_probability': our_probability,
                'notes': f"Surface: {match.get('surface', '')} | EV: {ev*100:.1f}%",
            }

            # Open bet tracker with pre-filled data
            BetTrackerUI(self.root, prefill_bet=prefill_data)

        except Exception as e:
            messagebox.showerror("Error", f"Could not open Bet Tracker: {e}")

    def _clear_matches(self):
        """Clear all upcoming matches."""
        if messagebox.askyesno("Confirm", "Clear all upcoming matches?"):
            db.clear_upcoming_matches()
            self._refresh_matches()
            for widget in self.value_frame.winfo_children():
                widget.destroy()
            self.summary_var.set("All matches cleared")

    def _open_rankings_manager(self):
        """Open the rankings manager window for manual ranking updates."""
        from rankings_manager import RankingsManager
        RankingsManager(self.root)

    def _fetch_player_history(self, player_id: int, player_name: str, dialog, match: Dict):
        """Fetch match history for a player - shows search dialog with options."""
        print(f"DEBUG _fetch_player_history: player_id={player_id}, player_name={player_name}")
        print(f"DEBUG match data: p1_id={match.get('player1_id')}, p1_name={match.get('player1_name')}, p2_id={match.get('player2_id')}, p2_name={match.get('player2_name')}")
        self._show_player_search_dialog(player_id, player_name, dialog)

    def _show_player_search_dialog(self, player_id: int, player_name: str, parent_dialog):
        """Show a dialog to search for and fetch player history."""
        from tennis_explorer_scraper import TennisExplorerScraper
        import threading
        import webbrowser

        # Create search dialog
        search_dialog = tk.Toplevel(parent_dialog)
        search_dialog.title(f"Find Match History - {player_name}")
        search_dialog.geometry("500x400")
        search_dialog.configure(bg=UI_COLORS["bg_dark"])
        search_dialog.transient(parent_dialog)

        # Center
        search_dialog.update_idletasks()
        x = parent_dialog.winfo_x() + (parent_dialog.winfo_width() - 500) // 2
        y = parent_dialog.winfo_y() + (parent_dialog.winfo_height() - 400) // 2
        search_dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(search_dialog, style="Dark.TFrame", padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Search input
        tk.Label(main_frame, text="Search Tennis Explorer:", font=("Segoe UI", 10),
                fg="white", bg=UI_COLORS["bg_dark"]).pack(anchor=tk.W)

        search_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        search_frame.pack(fill=tk.X, pady=(5, 10))

        search_var = tk.StringVar(value=player_name)
        search_entry = tk.Entry(search_frame, textvariable=search_var, font=("Segoe UI", 11),
                               bg=UI_COLORS["bg_medium"], fg="white", insertbackground="white", width=35)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Results list
        tk.Label(main_frame, text="Search Results:", font=("Segoe UI", 10),
                fg="white", bg=UI_COLORS["bg_dark"]).pack(anchor=tk.W)

        results_frame = ttk.Frame(main_frame, style="Card.TFrame")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        results_listbox = tk.Listbox(results_frame, font=("Consolas", 10),
                                     bg=UI_COLORS["bg_medium"], fg="white",
                                     selectbackground=UI_COLORS["accent"], height=10)
        results_listbox.pack(fill=tk.BOTH, expand=True)

        # Store search results data
        search_results = []

        status_label = tk.Label(main_frame, text="", font=("Segoe UI", 9),
                               fg=UI_COLORS["text_secondary"], bg=UI_COLORS["bg_dark"])
        status_label.pack(anchor=tk.W, pady=(5, 0))

        def do_search():
            search_term = search_var.get().strip()
            if not search_term:
                return

            results_listbox.delete(0, tk.END)
            search_results.clear()
            status_label.config(text="Searching...")
            search_dialog.update()

            def run_search():
                try:
                    scraper = TennisExplorerScraper()
                    # Search using last name
                    name_parts = search_term.lower().split()
                    last_name = name_parts[-1] if name_parts else search_term

                    url = f"https://www.tennisexplorer.com/list-players/?search-text-pl={last_name}"
                    response = scraper.session.get(url, timeout=15)

                    if response.status_code != 200:
                        search_dialog.after(0, lambda: status_label.config(text="Search failed"))
                        return

                    from bs4 import BeautifulSoup
                    import re
                    soup = BeautifulSoup(response.text, 'html.parser')
                    player_links = soup.select('a[href*="/player/"]')

                    results = []
                    seen_slugs = set()
                    for link in player_links:
                        href = link.get('href', '')
                        text = link.get_text().strip()
                        match = re.search(r'/player/([^/]+)/?', href)
                        if match and text and match.group(1) not in seen_slugs:
                            slug = match.group(1)
                            seen_slugs.add(slug)
                            results.append({'name': text, 'slug': slug, 'url': f"https://www.tennisexplorer.com/player/{slug}/"})

                    def update_results():
                        search_results.clear()
                        search_results.extend(results[:20])
                        for r in search_results:
                            results_listbox.insert(tk.END, r['name'])
                        status_label.config(text=f"Found {len(search_results)} players")

                    search_dialog.after(0, update_results)

                except Exception as e:
                    search_dialog.after(0, lambda: status_label.config(text=f"Error: {e}"))

            threading.Thread(target=run_search).start()

        search_btn = tk.Button(search_frame, text="Search", font=("Segoe UI", 10),
                              fg="white", bg=UI_COLORS["accent"], relief=tk.FLAT,
                              command=do_search, padx=15)
        search_btn.pack(side=tk.LEFT)

        # Buttons frame
        btn_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        def open_in_browser():
            sel = results_listbox.curselection()
            if sel and search_results:
                url = search_results[sel[0]]['url']
                webbrowser.open(url)

        def fetch_selected():
            sel = results_listbox.curselection()
            if not sel or not search_results:
                messagebox.showwarning("No Selection", "Please select a player from the results.")
                return

            selected = search_results[sel[0]]
            status_label.config(text=f"Fetching history for {selected['name']}...")
            search_dialog.update()

            def run_fetch():
                try:
                    scraper = TennisExplorerScraper()
                    profile = scraper.fetch_player_profile(selected['slug'])

                    if not profile:
                        search_dialog.after(0, lambda: status_label.config(text="Could not fetch profile"))
                        return

                    matches = profile.get('matches', [])

                    if not matches:
                        def no_matches():
                            status_label.config(text=f"No matches on profile - may need to check manually")
                            messagebox.showinfo(
                                "No Matches Found",
                                f"No match history found on {selected['name']}'s profile.\n\n"
                                f"Click 'Open in Browser' to view the profile and check manually.\n\n"
                                f"The player may not have recent matches listed, or they may be on a different page."
                            )
                        search_dialog.after(0, no_matches)
                        return

                    # Import matches
                    stats = scraper.fetch_player_match_history(
                        player_id, player_name, limit=6,
                        progress_callback=lambda m: search_dialog.after(0, lambda: status_label.config(text=m))
                    )

                    def on_complete():
                        if stats['success'] and stats['matches_imported'] > 0:
                            search_dialog.destroy()
                            parent_dialog.destroy()
                            messagebox.showinfo(
                                "History Imported",
                                f"Imported {stats['matches_imported']} matches.\n\n"
                                f"Re-open the match analysis to see updated data."
                            )
                            self._refresh_matches()
                        else:
                            status_label.config(text=stats.get('message', 'No matches imported'))

                    search_dialog.after(0, on_complete)

                except Exception as e:
                    search_dialog.after(0, lambda: status_label.config(text=f"Error: {e}"))

            threading.Thread(target=run_fetch).start()

        tk.Button(btn_frame, text="Open in Browser", font=("Segoe UI", 9),
                 fg="white", bg=UI_COLORS["warning"], relief=tk.FLAT,
                 command=open_in_browser, padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(btn_frame, text="Fetch Selected Player's History", font=("Segoe UI", 9, "bold"),
                 fg="white", bg=UI_COLORS["success"], relief=tk.FLAT,
                 command=fetch_selected, padx=15, pady=5).pack(side=tk.LEFT)

        # Auto-search on open
        search_dialog.after(100, do_search)

    def _update_all_match_players(self):
        """Update all players in the current matches list from Tennis Abstract."""
        if not self.scraper:
            messagebox.showwarning(
                "Feature Unavailable",
                "Tennis Abstract scraper is not available.\n\n"
                "This feature requires Selenium which may not be installed."
            )
            return

        # Get unique players from the matches list
        # Skip players with negative IDs (auto-added WTA/ITF players - Tennis Abstract is ATP only)
        # Skip doubles players (names containing "/")
        all_players = {}
        skipped_non_atp = 0
        skipped_doubles = 0
        for item_id, match in self.match_data_map.items():
            p1_id = match.get('player1_id')
            p2_id = match.get('player2_id')
            p1_name = match.get('player1_name', '')
            p2_name = match.get('player2_name', '')

            # Only include ATP singles players (positive IDs, no "/" in name)
            if p1_id and p1_name and p1_id not in all_players:
                if '/' in p1_name:
                    skipped_doubles += 1
                elif p1_id > 0:
                    all_players[p1_id] = p1_name
                else:
                    skipped_non_atp += 1
            if p2_id and p2_name and p2_id not in all_players:
                if '/' in p2_name:
                    skipped_doubles += 1
                elif p2_id > 0:
                    all_players[p2_id] = p2_name
                else:
                    skipped_non_atp += 1

        if not all_players:
            msg = "No ATP singles players to update."
            if skipped_non_atp > 0:
                msg += f"\n\n({skipped_non_atp} WTA/ITF players skipped)"
            if skipped_doubles > 0:
                msg += f"\n({skipped_doubles} doubles players skipped)"
            messagebox.showinfo("No Players", msg)
            return

        # Filter out players updated within last 6 hours
        players_to_update = {
            pid: name for pid, name in all_players.items()
            if db.player_needs_ta_update(pid, hours=6)
        }

        if not players_to_update:
            messagebox.showinfo("All Up To Date",
                                f"All {len(all_players)} players were updated within the last 6 hours.")
            return

        # Confirm
        recently_updated = len(all_players) - len(players_to_update)
        msg = f"Update {len(players_to_update)} ATP singles player(s) from Tennis Abstract?"
        if recently_updated > 0:
            msg += f"\n\n({recently_updated} already updated within 6 hours)"
        if skipped_non_atp > 0:
            msg += f"\n({skipped_non_atp} WTA/ITF players skipped)"
        if skipped_doubles > 0:
            msg += f"\n({skipped_doubles} doubles players skipped)"
        msg += "\n\nThis may take a moment."

        if not messagebox.askyesno("Update Players", msg):
            return

        # Show progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("Updating Players")
        progress_dialog.geometry("450x200")
        progress_dialog.configure(bg=UI_COLORS["bg_dark"])
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        progress_frame = ttk.Frame(progress_dialog, style="Dark.TFrame", padding=20)
        progress_frame.pack(fill=tk.BOTH, expand=True)

        status_var = tk.StringVar(value="Starting...")
        status_label = ttk.Label(progress_frame, textvariable=status_var, style="Dark.TLabel")
        status_label.pack(pady=10)

        progress_var = tk.StringVar(value="0 / 0")
        progress_label = ttk.Label(progress_frame, textvariable=progress_var, style="Dark.TLabel",
                                   font=("Segoe UI", 12, "bold"))
        progress_label.pack(pady=5)

        results_text = tk.Text(progress_frame, height=5, width=50, bg=UI_COLORS["bg_medium"],
                               fg=UI_COLORS["text_primary"], font=("Segoe UI", 9))
        results_text.pack(pady=10, fill=tk.X)

        progress_dialog.update()

        # Update each player
        total = len(players_to_update)
        success_count = 0
        matches_added = 0

        for i, (player_id, player_name) in enumerate(players_to_update.items(), 1):
            status_var.set(f"Fetching: {player_name}")
            progress_var.set(f"{i} / {total}")
            progress_dialog.update()

            try:
                result = self.scraper.fetch_and_update_player(player_id, player_name)
                if result['success']:
                    success_count += 1
                    matches_added += result.get('matches_added', 0)
                results_text.insert(tk.END, f"{player_name}: {result['message']}\n")
                results_text.see(tk.END)
            except Exception as e:
                results_text.insert(tk.END, f"{player_name}: Error - {str(e)}\n")
                results_text.see(tk.END)

            progress_dialog.update()

        status_var.set("Complete!")
        progress_var.set(f"Updated {success_count}/{total} players, {matches_added} new matches")

        # Add close button
        close_btn = tk.Button(
            progress_frame,
            text="Close",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=progress_dialog.destroy,
            padx=15,
            pady=5
        )
        close_btn.pack(pady=10)

    def _refresh_players_from_ta(self, p1_id: int, p1_name: str, p2_id: int, p2_name: str, dialog):
        """Refresh both players' recent matches from Tennis Abstract."""
        if not self.scraper:
            messagebox.showwarning(
                "Feature Unavailable",
                "Tennis Abstract scraper is not available.\n\n"
                "This feature requires Selenium which may not be installed."
            )
            return

        # Show progress
        progress_dialog = tk.Toplevel(dialog)
        progress_dialog.title("Refreshing Data")
        progress_dialog.geometry("400x150")
        progress_dialog.configure(bg=UI_COLORS["bg_dark"])
        progress_dialog.transient(dialog)
        progress_dialog.grab_set()

        progress_frame = ttk.Frame(progress_dialog, style="Dark.TFrame", padding=20)
        progress_frame.pack(fill=tk.BOTH, expand=True)

        status_var = tk.StringVar(value=f"Fetching data for {p1_name}...")
        status_label = ttk.Label(progress_frame, textvariable=status_var, style="Dark.TLabel")
        status_label.pack(pady=10)

        progress_dialog.update()

        results = []

        # Fetch Player 1
        try:
            result1 = self.scraper.fetch_and_update_player(p1_id, p1_name)
            results.append(f"{p1_name}: {result1['message']}")
        except Exception as e:
            results.append(f"{p1_name}: Error - {str(e)}")

        status_var.set(f"Fetching data for {p2_name}...")
        progress_dialog.update()

        # Fetch Player 2
        try:
            result2 = self.scraper.fetch_and_update_player(p2_id, p2_name)
            results.append(f"{p2_name}: {result2['message']}")
        except Exception as e:
            results.append(f"{p2_name}: Error - {str(e)}")

        progress_dialog.destroy()

        # Show results
        result_msg = "\n".join(results)
        messagebox.showinfo("Refresh Complete", result_msg)

        # Close and reopen the analysis dialog to show updated data
        dialog.destroy()

    def run(self):
        """Run the UI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = BetSuggesterUI()
    app.run()
