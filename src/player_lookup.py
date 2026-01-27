"""
Tennis Betting System - Player Lookup
Search players and view detailed statistics
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import UI_COLORS, SURFACES, HAND_MAPPING, INJURY_STATUS
from database import db, TennisDatabase
from match_analyzer import MatchAnalyzer
from tennis_abstract_scraper import TennisAbstractScraper


class PlayerLookup:
    """Player search and statistics viewer."""

    def __init__(self, database: TennisDatabase = None):
        self.db = database or db
        self.analyzer = MatchAnalyzer(self.db)

    def search_players(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for players by name, filtering out aliased duplicates."""
        results = self.db.search_players(query, limit * 2)  # Get extra to account for filtered aliases

        # Filter to only show canonical players (not aliases)
        canonical_results = []
        for p in results:
            canonical_id = self.db.get_canonical_id(p['id'])
            if canonical_id == p['id']:
                canonical_results.append(p)
                if len(canonical_results) >= limit:
                    break

        return canonical_results

    def get_player_profile(self, player_id: int) -> Dict:
        """Get comprehensive player profile."""
        player = self.db.get_player(player_id)
        if not player:
            return {}

        # Get ranking history
        ranking_history = self.db.get_player_ranking_history(player_id, limit=52)

        # Get surface stats
        surface_stats = {}
        for surface in SURFACES:
            stats = self.analyzer.get_surface_stats(player_id, surface)
            surface_stats[surface] = stats

        # Get recent form
        form = self.analyzer.calculate_form_score(player_id)

        # Get recent matches
        recent_matches = self.db.get_player_matches(player_id, limit=20)

        # Get injuries
        injuries = self.db.get_player_injuries(player_id, active_only=False)

        # Calculate career stats
        all_matches = self.db.get_player_matches(player_id)
        total_matches = len(all_matches)
        wins = sum(1 for m in all_matches if m['winner_id'] == player_id)
        career_win_rate = wins / total_matches if total_matches > 0 else 0

        # Calculate this year's stats
        this_year = datetime.now().strftime("%Y")
        this_year_matches = [m for m in all_matches if m.get('date', '').startswith(this_year)]
        this_year_wins = sum(1 for m in this_year_matches if m['winner_id'] == player_id)
        this_year_win_rate = this_year_wins / len(this_year_matches) if this_year_matches else 0

        return {
            'player': player,
            'ranking_history': ranking_history,
            'surface_stats': surface_stats,
            'form': form,
            'recent_matches': recent_matches,
            'injuries': injuries,
            'career': {
                'total_matches': total_matches,
                'wins': wins,
                'losses': total_matches - wins,
                'win_rate': career_win_rate,
            },
            'this_year': {
                'matches': len(this_year_matches),
                'wins': this_year_wins,
                'losses': len(this_year_matches) - this_year_wins,
                'win_rate': this_year_win_rate,
            },
        }

    def add_injury(self, player_id: int, injury_type: str, body_part: str = None,
                   status: str = "Minor Concern", notes: str = None) -> int:
        """Add an injury record for a player."""
        return self.db.add_injury(player_id, injury_type, body_part, status, notes)

    def update_injury_status(self, injury_id: int, status: str, notes: str = None):
        """Update an injury status."""
        self.db.update_injury_status(injury_id, status, notes)


class PlayerLookupUI:
    """Tkinter UI for Player Lookup."""

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Player Lookup")
        self.root.geometry("1200x800")
        self.root.configure(bg=UI_COLORS["bg_dark"])

        self.lookup = PlayerLookup()
        self.scraper = TennisAbstractScraper()
        self.current_player_id = None

        self._setup_styles()
        self._build_ui()

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
        style.configure("CardTitle.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["accent"], font=("Segoe UI", 12, "bold"))
        style.configure("PlayerName.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 20, "bold"))
        style.configure("Stat.TLabel", background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"], font=("Segoe UI", 14, "bold"))

        style.configure("Treeview",
                       background=UI_COLORS["bg_medium"],
                       foreground=UI_COLORS["text_primary"],
                       fieldbackground=UI_COLORS["bg_medium"],
                       font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                       background=UI_COLORS["bg_light"],
                       foreground=UI_COLORS["text_primary"],
                       font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        """Build the main UI."""
        main_frame = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header with search
        header_frame = ttk.Frame(main_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(header_frame, text="Player Lookup", style="Title.TLabel").pack(side=tk.LEFT)

        # Search box
        search_frame = ttk.Frame(header_frame, style="Dark.TFrame")
        search_frame.pack(side=tk.RIGHT)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30,
                                 font=("Segoe UI", 11))
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<Return>', lambda e: self._search())
        search_entry.bind('<KeyRelease>', self._on_search_key)

        search_btn = tk.Button(
            search_frame,
            text="Search",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._search,
            padx=15,
            pady=5
        )
        search_btn.pack(side=tk.LEFT, padx=5)

        # Main content split
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel: Search results
        left_frame = ttk.Frame(paned, style="Dark.TFrame")
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Search Results", style="Dark.TLabel").pack(anchor=tk.W, pady=(0, 10))

        columns = ("name", "country", "rank")
        self.results_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=25)

        self.results_tree.heading("name", text="Name")
        self.results_tree.heading("country", text="Country")
        self.results_tree.heading("rank", text="Ranking")

        self.results_tree.column("name", width=180)
        self.results_tree.column("country", width=60)
        self.results_tree.column("rank", width=60)

        self.results_tree.pack(fill=tk.BOTH, expand=True)
        self.results_tree.bind("<<TreeviewSelect>>", self._on_player_select)

        # Right panel: Player details
        right_frame = ttk.Frame(paned, style="Dark.TFrame")
        paned.add(right_frame, weight=3)

        # Scrollable content
        detail_canvas = tk.Canvas(right_frame, bg=UI_COLORS["bg_dark"], highlightthickness=0)
        detail_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=detail_canvas.yview)
        self.detail_frame = ttk.Frame(detail_canvas, style="Dark.TFrame")

        detail_canvas.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        detail_canvas.pack(fill=tk.BOTH, expand=True)

        detail_canvas.create_window((0, 0), window=self.detail_frame, anchor=tk.NW)
        self.detail_frame.bind("<Configure>",
                               lambda e: detail_canvas.configure(scrollregion=detail_canvas.bbox("all")))

        # Placeholder message
        self.placeholder = ttk.Label(
            self.detail_frame,
            text="Search for a player to view their profile",
            style="Dark.TLabel"
        )
        self.placeholder.pack(pady=50)

    def _on_search_key(self, event):
        """Handle key release in search box - live search."""
        query = self.search_var.get()
        if len(query) >= 2:
            self._search()

    def _search(self):
        """Perform player search."""
        query = self.search_var.get().strip()
        if not query:
            return

        self.results_tree.delete(*self.results_tree.get_children())

        results = self.lookup.search_players(query)
        for player in results:
            rank = player.get('current_ranking')
            rank_str = f"#{rank}" if rank else "-"
            self.results_tree.insert("", tk.END, iid=player['id'], values=(
                player.get('name', ''),
                player.get('country', ''),
                rank_str,
            ))

    def _on_player_select(self, event):
        """Handle player selection."""
        selection = self.results_tree.selection()
        if not selection:
            return

        player_id = int(selection[0])
        self.current_player_id = player_id
        self._display_player_profile(player_id)

    def _display_player_profile(self, player_id: int):
        """Display the full player profile."""
        # Clear previous content
        for widget in self.detail_frame.winfo_children():
            widget.destroy()

        profile = self.lookup.get_player_profile(player_id)
        if not profile:
            ttk.Label(self.detail_frame, text="Player not found", style="Dark.TLabel").pack()
            return

        player = profile['player']

        # Player header card
        header_card = ttk.Frame(self.detail_frame, style="Card.TFrame", padding=20)
        header_card.pack(fill=tk.X, pady=10, padx=5)

        # Name and basic info
        name_frame = ttk.Frame(header_card, style="Card.TFrame")
        name_frame.pack(fill=tk.X)

        ttk.Label(name_frame, text=player.get('name', 'Unknown'), style="PlayerName.TLabel").pack(side=tk.LEFT)

        # Country flag placeholder and info
        info_text = f"{player.get('country', '')} | "
        hand = player.get('hand', 'U')
        info_text += f"{HAND_MAPPING.get(hand, 'Unknown')}-handed"
        if player.get('height'):
            info_text += f" | {player['height']}cm"
        if player.get('dob'):
            # Calculate age
            try:
                dob = datetime.strptime(player['dob'][:10], "%Y-%m-%d")
                age = (datetime.now() - dob).days // 365
                info_text += f" | Age: {age}"
            except:
                pass

        ttk.Label(name_frame, text=info_text, style="Card.TLabel").pack(side=tk.RIGHT)

        # Ranking info
        rank_frame = ttk.Frame(header_card, style="Card.TFrame")
        rank_frame.pack(fill=tk.X, pady=(10, 0))

        current_rank = player.get('current_ranking')
        peak_rank = player.get('peak_ranking')

        rank_info = f"Current Ranking: #{current_rank}" if current_rank else "Ranking: Unranked"
        if peak_rank:
            rank_info += f" | Peak: #{peak_rank}"

        ttk.Label(rank_frame, text=rank_info, style="CardTitle.TLabel").pack(side=tk.LEFT)

        # Add injury button
        injury_btn = tk.Button(
            rank_frame,
            text="+ Add Injury",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._add_injury_dialog(player_id),
            padx=10,
            pady=3
        )
        injury_btn.pack(side=tk.RIGHT)

        # Refresh from Tennis Abstract button
        refresh_btn = tk.Button(
            rank_frame,
            text="Refresh from Tennis Abstract",
            font=("Segoe UI", 9),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._refresh_from_tennis_abstract(player_id, player.get('name')),
            padx=10,
            pady=3
        )
        refresh_btn.pack(side=tk.RIGHT, padx=(0, 10))

        # Stats row
        stats_frame = ttk.Frame(self.detail_frame, style="Dark.TFrame")
        stats_frame.pack(fill=tk.X, pady=10)

        # Career stats card
        career = profile['career']
        career_card = ttk.Frame(stats_frame, style="Card.TFrame", padding=15)
        career_card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)

        ttk.Label(career_card, text="Career", style="CardTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(career_card, text=f"{career['wins']}W - {career['losses']}L", style="Stat.TLabel").pack(anchor=tk.W)
        ttk.Label(career_card, text=f"Win Rate: {career['win_rate']:.1%}", style="Card.TLabel").pack(anchor=tk.W)

        # This year stats card
        this_year = profile['this_year']
        year_card = ttk.Frame(stats_frame, style="Card.TFrame", padding=15)
        year_card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)

        ttk.Label(year_card, text=f"{datetime.now().year} Season", style="CardTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(year_card, text=f"{this_year['wins']}W - {this_year['losses']}L", style="Stat.TLabel").pack(anchor=tk.W)
        ttk.Label(year_card, text=f"Win Rate: {this_year['win_rate']:.1%}", style="Card.TLabel").pack(anchor=tk.W)

        # Form card
        form = profile['form']
        form_card = ttk.Frame(stats_frame, style="Card.TFrame", padding=15)
        form_card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)

        ttk.Label(form_card, text="Recent Form", style="CardTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(form_card, text=f"{form['score']:.0f}/100", style="Stat.TLabel").pack(anchor=tk.W)
        ttk.Label(form_card, text=f"Last {form['matches']}: {form['wins']}W-{form['losses']}L",
                 style="Card.TLabel").pack(anchor=tk.W)

        # Surface performance
        surface_card = ttk.Frame(self.detail_frame, style="Card.TFrame", padding=15)
        surface_card.pack(fill=tk.X, pady=10, padx=5)

        ttk.Label(surface_card, text="Surface Performance", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 10))

        surface_row = ttk.Frame(surface_card, style="Card.TFrame")
        surface_row.pack(fill=tk.X)

        surface_colors = {
            "Hard": UI_COLORS["surface_hard"],
            "Clay": UI_COLORS["surface_clay"],
            "Grass": UI_COLORS["surface_grass"],
            "Carpet": UI_COLORS["surface_carpet"],
        }

        for surface, stats in profile['surface_stats'].items():
            cell = ttk.Frame(surface_row, style="Card.TFrame")
            cell.pack(side=tk.LEFT, expand=True)

            color = surface_colors.get(surface, UI_COLORS["text_secondary"])
            lbl = tk.Label(cell, text=surface, font=("Segoe UI", 11, "bold"),
                          fg=color, bg=UI_COLORS["bg_medium"])
            lbl.pack()

            ttk.Label(cell, text=f"{stats['combined_win_rate']:.1%}", style="Stat.TLabel").pack()
            ttk.Label(cell, text=f"{stats['career_matches']} matches", style="Card.TLabel").pack()

        # Recent matches
        matches_card = ttk.Frame(self.detail_frame, style="Card.TFrame", padding=15)
        matches_card.pack(fill=tk.X, pady=10, padx=5)

        ttk.Label(matches_card, text="Recent Matches (Last 20)", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 10))

        columns = ("date", "tournament", "surface", "round", "opponent", "result", "score", "duration")
        matches_tree = ttk.Treeview(matches_card, columns=columns, show="headings", height=15)

        matches_tree.heading("date", text="Date")
        matches_tree.heading("tournament", text="Tournament")
        matches_tree.heading("surface", text="Surface")
        matches_tree.heading("round", text="Round")
        matches_tree.heading("opponent", text="Opponent")
        matches_tree.heading("result", text="W/L")
        matches_tree.heading("score", text="Score")
        matches_tree.heading("duration", text="Mins")

        matches_tree.column("date", width=85)
        matches_tree.column("tournament", width=140)
        matches_tree.column("surface", width=55)
        matches_tree.column("round", width=50)
        matches_tree.column("opponent", width=130)
        matches_tree.column("result", width=35)
        matches_tree.column("score", width=90)
        matches_tree.column("duration", width=45)

        for match in profile['recent_matches']:
            # Compare using canonical IDs (handles aliased player IDs)
            winner_canonical = db.get_canonical_id(match['winner_id'])
            player_canonical = db.get_canonical_id(player_id)
            won = winner_canonical == player_canonical

            # Determine opponent
            if won:
                opp_id = match['loser_id']
            else:
                opp_id = match['winner_id']

            opp = db.get_player(opp_id)
            opp_name = opp['name'] if opp else 'Unknown'

            # Duration
            mins = match.get('minutes')
            mins_str = str(mins) if mins else '-'

            matches_tree.insert("", tk.END, values=(
                match.get('date', '')[:10],
                match.get('tournament') or match.get('tourney_name', ''),
                match.get('surface', ''),
                match.get('round', ''),
                opp_name,
                "W" if won else "L",
                match.get('score', ''),
                mins_str,
            ))

        matches_tree.pack(fill=tk.X)

        # Injuries section
        if profile['injuries']:
            injury_card = ttk.Frame(self.detail_frame, style="Card.TFrame", padding=15)
            injury_card.pack(fill=tk.X, pady=10, padx=5)

            ttk.Label(injury_card, text="Injury History", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 10))

            for injury in profile['injuries'][:5]:
                injury_row = ttk.Frame(injury_card, style="Card.TFrame")
                injury_row.pack(fill=tk.X, pady=2)

                status = injury.get('status', 'Unknown')
                status_color = UI_COLORS["success"] if status == "Active" else UI_COLORS["warning"]

                ttk.Label(injury_row, text=f"{injury.get('injury_type', 'Unknown')}",
                         style="Card.TLabel").pack(side=tk.LEFT)
                status_lbl = tk.Label(injury_row, text=f"[{status}]",
                                     fg=status_color, bg=UI_COLORS["bg_medium"],
                                     font=("Segoe UI", 9))
                status_lbl.pack(side=tk.LEFT, padx=10)
                ttk.Label(injury_row, text=injury.get('reported_date', ''),
                         style="Card.TLabel").pack(side=tk.RIGHT)

    def _add_injury_dialog(self, player_id: int):
        """Show dialog to add an injury."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Injury")
        dialog.geometry("400x350")
        dialog.configure(bg=UI_COLORS["bg_dark"])
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, style="Dark.TFrame", padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Injury type
        ttk.Label(frame, text="Injury Type:", style="Dark.TLabel").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_var = tk.StringVar()
        type_entry = ttk.Entry(frame, textvariable=type_var, width=30)
        type_entry.grid(row=0, column=1, pady=5, padx=10)

        # Body part
        ttk.Label(frame, text="Body Part:", style="Dark.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        part_var = tk.StringVar()
        part_combo = ttk.Combobox(frame, textvariable=part_var, width=27,
                                   values=["Knee", "Ankle", "Wrist", "Shoulder", "Back", "Hip",
                                          "Elbow", "Foot", "Leg", "Arm", "Other"])
        part_combo.grid(row=1, column=1, pady=5, padx=10)

        # Status
        ttk.Label(frame, text="Status:", style="Dark.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar(value="Minor Concern")
        status_combo = ttk.Combobox(frame, textvariable=status_var, width=27,
                                     values=INJURY_STATUS, state="readonly")
        status_combo.grid(row=2, column=1, pady=5, padx=10)

        # Notes
        ttk.Label(frame, text="Notes:", style="Dark.TLabel").grid(row=3, column=0, sticky=tk.W, pady=5)
        notes_var = tk.StringVar()
        notes_entry = ttk.Entry(frame, textvariable=notes_var, width=30)
        notes_entry.grid(row=3, column=1, pady=5, padx=10)

        def save_injury():
            injury_type = type_var.get()
            if not injury_type:
                messagebox.showwarning("Required", "Please enter injury type.")
                return

            self.lookup.add_injury(
                player_id,
                injury_type,
                part_var.get() or None,
                status_var.get(),
                notes_var.get() or None
            )

            # Refresh display
            self._display_player_profile(player_id)
            dialog.destroy()

        save_btn = tk.Button(
            frame,
            text="Add Injury",
            font=("Segoe UI", 11),
            fg="white",
            bg=UI_COLORS["warning"],
            relief=tk.FLAT,
            cursor="hand2",
            command=save_injury,
            padx=20,
            pady=8
        )
        save_btn.grid(row=4, column=1, pady=20, sticky=tk.E)

    def _refresh_from_tennis_abstract(self, player_id: int, player_name: str):
        """Fetch recent matches from Tennis Abstract and update database."""
        # Show loading dialog
        loading = tk.Toplevel(self.root)
        loading.title("Fetching Data")
        loading.geometry("300x100")
        loading.configure(bg=UI_COLORS["bg_dark"])
        loading.transient(self.root)
        loading.grab_set()

        # Center the dialog
        loading.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 100) // 2
        loading.geometry(f"+{x}+{y}")

        ttk.Label(loading, text=f"Fetching data for {player_name}...",
                 style="Dark.TLabel").pack(pady=20)
        ttk.Label(loading, text="This may take a few seconds",
                 style="Dark.TLabel").pack()

        loading.update()

        # Fetch data in background
        def do_fetch():
            try:
                result = self.scraper.fetch_and_update_player(player_id, player_name)
                loading.destroy()

                if result['success']:
                    messagebox.showinfo(
                        "Refresh Complete",
                        f"Found {result['matches_found']} matches on Tennis Abstract.\n"
                        f"Added {result['matches_added']} new matches to database."
                    )
                    # Refresh the player profile to show new data
                    self._display_player_profile(player_id)
                else:
                    messagebox.showwarning("Refresh Failed", result['message'])

            except Exception as e:
                loading.destroy()
                messagebox.showerror("Error", f"Failed to fetch data: {str(e)}")

        # Run after a brief delay to let the loading dialog show
        self.root.after(100, do_fetch)

    def run(self):
        """Run the UI."""
        self.root.mainloop()


if __name__ == "__main__":
    app = PlayerLookupUI()
    app.run()
