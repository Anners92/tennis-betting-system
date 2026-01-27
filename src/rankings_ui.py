"""
Rankings UI - Display ATP and WTA player rankings
"""

import tkinter as tk
from tkinter import ttk
from database import db

# Import colors from central config
from config import UI_COLORS


class RankingsUI:
    """Rankings viewer with ATP and WTA tabs."""

    def __init__(self, parent: tk.Tk = None):
        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("Player Rankings")
        self.root.configure(bg=UI_COLORS["bg_dark"])
        self.root.state('zoomed')  # Launch maximized

        self._setup_styles()
        self._create_ui()
        self._load_rankings()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Dark.TFrame", background=UI_COLORS["bg_dark"])
        style.configure("Card.TFrame", background=UI_COLORS["bg_card"])
        style.configure("Dark.TLabel", background=UI_COLORS["bg_dark"],
                        foreground=UI_COLORS["text_primary"])
        style.configure("Card.TLabel", background=UI_COLORS["bg_card"],
                        foreground=UI_COLORS["text_primary"])
        style.configure("Muted.TLabel", background=UI_COLORS["bg_card"],
                        foreground=UI_COLORS["text_secondary"])

        # Notebook (tabs) style
        style.configure("TNotebook", background=UI_COLORS["bg_dark"])
        style.configure("TNotebook.Tab", background=UI_COLORS["bg_medium"],
                        foreground=UI_COLORS["text_primary"], padding=[40, 10],
                        font=("Segoe UI", 11, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", UI_COLORS["accent"])],
                  foreground=[("selected", "white")],
                  padding=[("selected", [40, 10])])

        # Treeview style
        style.configure("Treeview",
                        background=UI_COLORS["bg_card"],
                        foreground=UI_COLORS["text_primary"],
                        fieldbackground=UI_COLORS["bg_card"],
                        rowheight=30)
        style.configure("Treeview.Heading",
                        background=UI_COLORS["bg_medium"],
                        foreground=UI_COLORS["text_primary"],
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview",
                  background=[("selected", UI_COLORS["accent"])],
                  foreground=[("selected", "white")])

    def _create_ui(self):
        """Create the main UI."""
        # Main container
        container = ttk.Frame(self.root, style="Dark.TFrame", padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(container, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(header_frame, text="Player Rankings", style="Dark.TLabel",
                  font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT)

        # Manage Rankings button
        manage_btn = tk.Button(
            header_frame,
            text="Manage Rankings",
            font=("Segoe UI", 10),
            fg="white",
            bg=UI_COLORS["accent"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self._open_rankings_manager,
            padx=15,
            pady=5
        )
        manage_btn.pack(side=tk.LEFT, padx=(20, 0))

        # Search box
        search_frame = ttk.Frame(header_frame, style="Dark.TFrame")
        search_frame.pack(side=tk.RIGHT)

        ttk.Label(search_frame, text="Search:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(0, 10))

        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30,
                                 font=("Segoe UI", 11))
        search_entry.pack(side=tk.LEFT)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # ATP Tab
        self.atp_frame = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(self.atp_frame, text="  ATP  ")
        self.atp_tree = self._create_rankings_tree(self.atp_frame)

        # WTA Tab
        self.wta_frame = ttk.Frame(self.notebook, style="Dark.TFrame")
        self.notebook.add(self.wta_frame, text="  WTA  ")
        self.wta_tree = self._create_rankings_tree(self.wta_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Loading...")
        status_bar = ttk.Label(container, textvariable=self.status_var, style="Muted.TLabel")
        status_bar.pack(fill=tk.X, pady=(10, 0))

    def _create_rankings_tree(self, parent) -> ttk.Treeview:
        """Create a treeview for rankings display."""
        # Frame for tree + scrollbar
        tree_frame = ttk.Frame(parent, style="Dark.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Treeview
        columns = ("rank", "name", "id", "country", "matches")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                            yscrollcommand=scrollbar.set)

        # Column headings
        tree.heading("rank", text="Rank")
        tree.heading("name", text="Player Name")
        tree.heading("id", text="ID")
        tree.heading("country", text="Country")
        tree.heading("matches", text="Matches")

        # Column widths
        tree.column("rank", width=60, anchor=tk.CENTER)
        tree.column("name", width=250, anchor=tk.W)
        tree.column("id", width=100, anchor=tk.CENTER)
        tree.column("country", width=80, anchor=tk.CENTER)
        tree.column("matches", width=80, anchor=tk.CENTER)

        tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=tree.yview)

        # Double-click to view player
        tree.bind("<Double-1>", lambda e: self._on_player_double_click(tree))

        return tree

    def _load_rankings(self):
        """Load rankings data from database (optimized with single query)."""
        atp_players = []
        wta_players = []

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Single optimized query:
            # - Only players with rankings
            # - Exclude aliases (LEFT JOIN to find non-aliased players)
            # - Include match count via subquery (including matches from aliased IDs)
            # - Exclude doubles (names with '/')
            cursor.execute('''
                SELECT
                    p.id,
                    p.name,
                    p.country,
                    p.current_ranking,
                    p.tour,
                    (SELECT COUNT(*) FROM matches m
                     WHERE m.winner_id = p.id OR m.loser_id = p.id
                        OR m.winner_id IN (SELECT alias_id FROM player_aliases WHERE canonical_id = p.id)
                        OR m.loser_id IN (SELECT alias_id FROM player_aliases WHERE canonical_id = p.id)
                    ) as match_count
                FROM players p
                LEFT JOIN player_aliases a ON p.id = a.alias_id
                WHERE p.current_ranking IS NOT NULL
                  AND p.current_ranking > 0
                  AND a.alias_id IS NULL
                  AND p.name NOT LIKE '%/%'
                ORDER BY p.current_ranking
            ''')

            for row in cursor.fetchall():
                player_data = {
                    'id': row['id'],
                    'name': row['name'],
                    'country': row['country'] or '',
                    'ranking': row['current_ranking'],
                    'match_count': row['match_count'] or 0
                }

                tour = row['tour']
                if tour == 'ATP':
                    atp_players.append(player_data)
                elif tour == 'WTA':
                    wta_players.append(player_data)

        # Store for search filtering
        self.atp_players = atp_players
        self.wta_players = wta_players

        # Populate trees
        self._populate_tree(self.atp_tree, atp_players)
        self._populate_tree(self.wta_tree, wta_players)

        # Update status
        self.status_var.set(f"ATP: {len(atp_players)} players  |  WTA: {len(wta_players)} players")

    def _populate_tree(self, tree: ttk.Treeview, players: list, filter_text: str = ""):
        """Populate a treeview with player data."""
        # Clear existing items
        tree.delete(*tree.get_children())

        filter_lower = filter_text.lower()

        for i, p in enumerate(players):
            # Apply search filter
            if filter_lower and filter_lower not in p['name'].lower():
                continue

            rank_str = f"#{p['ranking']}" if p['ranking'] else "N/A"
            tree.insert("", tk.END, iid=str(p['id']), values=(
                rank_str,
                p['name'],
                p['id'],
                p['country'] or "-",
                p['match_count']
            ))

    def _on_search(self, *args):
        """Handle search input."""
        filter_text = self.search_var.get()
        self._populate_tree(self.atp_tree, self.atp_players, filter_text)
        self._populate_tree(self.wta_tree, self.wta_players, filter_text)

    def _on_player_double_click(self, tree: ttk.Treeview):
        """Handle double-click on a player row."""
        selection = tree.selection()
        if selection:
            player_id = int(selection[0])
            # Could open player details here
            print(f"Selected player ID: {player_id}")

    def _open_rankings_manager(self):
        """Open the rankings manager window for manual ranking updates."""
        from rankings_manager import RankingsManager
        RankingsManager(self.root)


if __name__ == "__main__":
    app = RankingsUI()
    app.root.mainloop()
